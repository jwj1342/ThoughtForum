"""HF transformers backend: text generation, plus latent posts injected as soft tokens.

Two training-free writers turn an author's context into k vectors:

- chunk means (the default, `encode` without a writer head): final-layer states of the author's
  message tokens, pooled into k contiguous chunk means. This destroys instance content (R13).
- gist (`writer_head` set, see `gist`): k query vectors are appended after the author's whole
  context and their final-layer states are taken. With the untrained head (random vocabulary
  embeddings as queries, identity map) this is the method in doc/method.md.

Both pass through `_to_input_space`: W_a, the ridge solution of W_out @ W_a ≈ W_in (the input /
output alignment used by LatentMAS), then the span of the chat-control tokens is removed and the
result rescaled to the mean embedding norm. Readers get the vectors spliced into their prompt at
a LATENT_MARK. The reader keeps its own context: the post is added, not swapped in for its cache.
"""
from __future__ import annotations

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, GenerationConfig

from .base import Backend, Generation, Latent, LATENT_RE


class HFBackend(Backend):
    name = "hf"

    def __init__(self, model_path: str, dtype: str = "bfloat16", device: str = "cuda",
                 align_lambda: float = 1e-2, enable_thinking: bool = False):
        self.tok = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path, torch_dtype=getattr(torch, dtype), local_files_only=True).to(device).eval()
        self.device = device
        self.enable_thinking = enable_thinking
        self.emb = self.model.get_input_embeddings()
        self._build_alignment(align_lambda)
        self.reader_adapter = None   # optional nn.Module applied to every latent a reader receives (E1a)
        self.writer_head = None      # optional trained writer (train_writer.WriteHead) replacing chunk means (E1w)

    @torch.no_grad()
    def _build_alignment(self, lam: float):
        w_in = self.emb.weight.float()
        w_out = self.model.get_output_embeddings().weight.float()
        gram = w_out.T @ w_out
        gram += lam * gram.diagonal().mean() * torch.eye(gram.shape[0], device=gram.device)
        self.w_a = torch.linalg.solve(gram, w_out.T @ w_in).to(self.model.dtype)
        self.target_norm = w_in.norm(dim=-1).mean().item()
        # Orthonormal basis of the chat-control tokens' embeddings (<|im_end|>, </think>, ...).
        # Latents are projected off this span: a smoke run showed that vectors near these
        # directions break the reader's turn structure ("</think> Okay Okay ...").
        ids = sorted({i for i in self.tok.all_special_ids} |
                     {self.tok.convert_tokens_to_ids(t) for t in ("<think>", "</think>", "<|im_start|>", "<|im_end|>")
                      if self.tok.convert_tokens_to_ids(t) is not None})
        self.ctrl_basis = torch.linalg.qr(w_in[ids].T)[0].to(self.model.dtype)   # [d, n_ctrl]
        del w_in, w_out, gram
        torch.cuda.empty_cache()

    def count_tokens(self, text: str) -> int:
        return len(self.tok(text, add_special_tokens=False).input_ids)

    def _render(self, messages, add_generation_prompt=True) -> str:
        return self.tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=add_generation_prompt,
                                            enable_thinking=self.enable_thinking)

    def _embed(self, text: str, latents) -> tuple[torch.Tensor, int]:
        """Embed rendered text, splicing latents[i] in at every <<LATENT:i>>."""
        parts, n = [], 0
        for j, piece in enumerate(LATENT_RE.split(text)):
            if j % 2:
                v = latents[int(piece)].data.to(self.device)
                if self.reader_adapter is not None:
                    v = self.reader_adapter(v.float())
                v = v.to(self.model.dtype)
            elif piece:
                ids = self.tok(piece, add_special_tokens=False, return_tensors="pt").input_ids.to(self.device)
                v = self.emb(ids)[0]
            else:
                continue
            parts.append(v)
            n += v.shape[0]
        return torch.cat(parts, 0), n

    @torch.no_grad()
    def chat(self, messages, latents=(), *, purpose="", meta=None, max_new_tokens=512, temperature=0.0):
        emb, n_prompt = self._embed(self._render(messages), latents)
        gc = GenerationConfig(max_new_tokens=max_new_tokens, eos_token_id=self.model.generation_config.eos_token_id,
                              pad_token_id=self.tok.pad_token_id or self.tok.eos_token_id,
                              do_sample=temperature > 0, temperature=temperature if temperature > 0 else 1.0,
                              top_p=0.95 if temperature > 0 else 1.0, top_k=20 if temperature > 0 else 50)
        out = self.model.generate(inputs_embeds=emb[None], generation_config=gc,
                                  attention_mask=torch.ones(1, emb.shape[0], dtype=torch.long, device=self.device))
        new = out[0]  # with inputs_embeds only, generate returns just the new tokens
        return Generation(self.tok.decode(new, skip_special_tokens=True).strip(), n_prompt, int(new.shape[0]))

    @torch.no_grad()
    def encode(self, messages, response, latents=(), *, k=16, purpose="", meta=None):
        ctx, _ = self._embed(self._render(messages), latents)
        r_ids = self.tok(response or " ", add_special_tokens=False, return_tensors="pt").input_ids.to(self.device)
        full = torch.cat([ctx, self.emb(r_ids)[0]], 0)
        if self.writer_head is not None:
            e = self.gist(full).to(torch.float16).cpu()
            return Latent(e, e.shape[0], nbytes=e.numel() * 2, origin=purpose or "report",
                          meta={"src_tokens": int(r_ids.shape[1]), "writer": "head"})
        h = self.model.model(inputs_embeds=full[None], use_cache=False).last_hidden_state[0, -r_ids.shape[1]:]
        if h.shape[0] > 1:
            h = h[:-1]  # the last state predicts end-of-turn, i.e. a control token
        z = torch.stack([c.mean(0) for c in torch.tensor_split(h.float(), min(k, h.shape[0]), dim=0)])
        e = self._to_input_space(z).to(torch.float16).cpu()
        return Latent(e, e.shape[0], nbytes=e.numel() * 2, origin=purpose or "report",
                      meta={"src_tokens": int(r_ids.shape[1])})

    def _to_input_space(self, z):
        """Final-layer states -> input embeddings: W_a, off the control-token span, mean embedding norm."""
        e = z.to(self.w_a.dtype) @ self.w_a
        e = e - (e @ self.ctrl_basis) @ self.ctrl_basis.T
        e = e.float()
        return e * (self.target_norm / e.norm(dim=-1, keepdim=True).clamp_min(1e-6))

    def gist(self, ctx_emb, grad: bool = False):
        """Trained writer: the head's k query vectors read the context, which is passed as a KV cache.

        Only the query positions are computed with gradients (train_writer.py)."""
        head = self.writer_head
        with torch.no_grad():
            cache = self.model.model(inputs_embeds=ctx_emb[None], use_cache=True).past_key_values
        with torch.set_grad_enabled(grad):
            h = self.model.model(inputs_embeds=head.q.to(self.model.dtype)[None], past_key_values=cache,
                                 use_cache=True).last_hidden_state[0]
            return head.out(self._to_input_space(h))

    def transform(self, lat, kind, bank, seed):
        x = lat.data
        if kind == "zero":
            y = torch.zeros_like(x)
        elif kind == "mean":
            pool = [b.data.float() for b in bank if b is not lat and b.data is not None and torch.is_tensor(b.data)]
            m = torch.cat(pool, 0).mean(0, keepdim=True) if pool else torch.zeros(1, x.shape[1])
            y = (m * (self.target_norm / m.norm(dim=-1, keepdim=True).clamp_min(1e-6))).expand_as(x).to(x.dtype)
        elif kind == "noise":
            g = torch.Generator().manual_seed(seed)
            y = torch.randn(x.shape, generator=g)
            y = (y * (self.target_norm / y.norm(dim=-1, keepdim=True))).to(x.dtype)
        else:
            raise ValueError(kind)
        return Latent(y, lat.k, lat.nbytes, origin=kind)
