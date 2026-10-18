"""A local HuggingFace model: chat generation with latent posts spliced in, plus the primitives
that writers (model/writers.py) use to read an author's context.

Latent posts enter the reader's prompt as soft tokens at each LATENT_MARK; the reader's own
context stays as it is, the post is added, not swapped in for its cache. Vectors read from
the model's final layer are carried into the input-embedding space by `to_input_space`:
W_a, the ridge solution of W_out @ W_a ≈ W_in (the input/output alignment LatentMAS uses),
then the span of the chat-control tokens is removed (vectors near `<|im_end|>` or `</think>`
break the reader's turn structure) and the result is rescaled to the mean embedding norm.
"""
from __future__ import annotations

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, GenerationConfig

from model.backends.base import TEMPERATURE, Backend, Generation, Latent, LATENT_RE

CONTROL_TOKENS = ("<think>", "</think>", "<|im_start|>", "<|im_end|>")


def default_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class HFBackend(Backend):
    name = "hf"

    def __init__(self, model, tok, enable_thinking: bool = False, align_lambda: float = 1e-2):
        self.model = model.eval()
        for p in self.model.parameters():   # the language model itself is never trained here
            p.requires_grad_(False)
        self.tok = tok
        self.device = next(model.parameters()).device
        self.enable_thinking = enable_thinking
        self.emb = model.get_input_embeddings()
        self.latent_map = None   # optional map applied to every latent a reader receives (a trained adapter)
        self._build_alignment(align_lambda)

    @classmethod
    def load(cls, path: str, dtype: str = "bfloat16", device: str | None = None, **kw) -> "HFBackend":
        """`path` is a local directory or a HuggingFace Hub id such as Qwen/Qwen3-8B."""
        tok = AutoTokenizer.from_pretrained(path)
        model = AutoModelForCausalLM.from_pretrained(path, torch_dtype=getattr(torch, dtype))
        return cls(model.to(device or default_device()), tok, **kw)

    @torch.no_grad()
    def _build_alignment(self, lam: float):
        w_in = self.emb.weight.float()
        w_out = self.model.get_output_embeddings().weight.float()
        gram = w_out.T @ w_out
        gram += lam * gram.diagonal().mean() * torch.eye(gram.shape[0], device=gram.device)
        self.w_a = torch.linalg.solve(gram, w_out.T @ w_in).to(self.model.dtype)
        self.target_norm = w_in.norm(dim=-1).mean().item()
        ids = sorted(set(self.tok.all_special_ids) | {i for i in map(self.tok.convert_tokens_to_ids, CONTROL_TOKENS)
                                                      if i is not None and i != self.tok.unk_token_id})
        self.ctrl_basis = torch.linalg.qr(w_in[ids].T)[0].to(self.model.dtype)   # [d, n_ctrl]
        del w_in, w_out, gram
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # ---- prompts ----------------------------------------------------------------------
    def count_tokens(self, text: str) -> int:
        return len(self.tok(text, add_special_tokens=False).input_ids)

    def render(self, messages, add_generation_prompt: bool = True) -> str:
        return self.tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=add_generation_prompt,
                                            enable_thinking=self.enable_thinking)

    def text_embeddings(self, text: str) -> torch.Tensor:
        ids = self.tok(text, add_special_tokens=False, return_tensors="pt").input_ids.to(self.device)
        return self.emb(ids)[0]

    def embed(self, text: str, latents=()) -> torch.Tensor:
        """Embed rendered text, splicing latents[i] in at every <<LATENT:i>>."""
        parts = []
        for j, piece in enumerate(LATENT_RE.split(text)):
            if j % 2:
                v = latents[int(piece)].data.to(self.device)
                if self.latent_map is not None:
                    v = self.latent_map(v.float())
                parts.append(v.to(self.model.dtype))
            elif piece:
                parts.append(self.text_embeddings(piece))
        return torch.cat(parts, 0)

    def embed_chat(self, messages, latents=()) -> torch.Tensor:
        return self.embed(self.render(messages), latents)

    # ---- generation -------------------------------------------------------------------
    @torch.no_grad()
    def chat(self, messages, latents=(), *, purpose="", meta=None, max_new_tokens=512, temperature=TEMPERATURE):
        """Sampling with top-p 0.95 and top-k 20 (Qwen3's defaults), or greedy at temperature 0."""
        emb = self.embed_chat(messages, latents)
        sample = temperature > 0
        gc = GenerationConfig(max_new_tokens=max_new_tokens, eos_token_id=self.model.generation_config.eos_token_id,
                              pad_token_id=self.tok.pad_token_id or self.tok.eos_token_id,
                              do_sample=sample, temperature=temperature if sample else 1.0,
                              top_p=0.95 if sample else 1.0, top_k=20 if sample else 50)
        # use_model_defaults=False: run exactly this config. Otherwise transformers >= 4.50 silently replaces
        # every value equal to its global default (do_sample=False, temperature=1, ...) with the model's own,
        # which turned all earlier "greedy" runs into sampling at the model's defaults.
        out = self.model.generate(inputs_embeds=emb[None], generation_config=gc, use_model_defaults=False,
                                  attention_mask=torch.ones(1, emb.shape[0], dtype=torch.long, device=self.device))
        new = out[0]  # with inputs_embeds only, generate returns just the new tokens
        return Generation(self.tok.decode(new, skip_special_tokens=True).strip(), emb.shape[0], int(new.shape[0]))

    # ---- reading a context (used by writers) --------------------------------------------
    def final_states(self, emb: torch.Tensor) -> torch.Tensor:
        """Final-layer hidden states of a sequence of input embeddings, [n, d]."""
        return self.model.model(inputs_embeds=emb[None], use_cache=False).last_hidden_state[0]

    def read_after(self, ctx_emb: torch.Tensor, queries: torch.Tensor, grad: bool = False) -> torch.Tensor:
        """Final-layer states of `queries` appended after `ctx_emb`, [k, d]. The context is run once
        without gradients and handed over as a KV cache, so only the query positions can be trained."""
        with torch.no_grad():
            cache = self.model.model(inputs_embeds=ctx_emb[None], use_cache=True).past_key_values
        with torch.set_grad_enabled(grad):
            return self.model.model(inputs_embeds=queries.to(self.model.dtype)[None], past_key_values=cache,
                                    use_cache=True).last_hidden_state[0]

    def to_input_space(self, h: torch.Tensor) -> torch.Tensor:
        """Final-layer states -> input embeddings: W_a, off the control-token span, mean embedding norm."""
        e = h.to(self.w_a.dtype) @ self.w_a
        e = e - (e @ self.ctrl_basis) @ self.ctrl_basis.T
        e = e.float()
        return e * (self.target_norm / e.norm(dim=-1, keepdim=True).clamp_min(1e-6))
