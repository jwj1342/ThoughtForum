"""KV posts: the author's KV cache, whole or sparsified, placed before the reader's prompt.

The post is the cache the author already holds after writing its report, so it carries what the
author's context contains (its code, the test result, its own words), not only what it said.
`budget` keeps B entries per layer and KV head:
- `snap`: the positions the author's own report attends to most (SnapKV with the report as the
  observation window), plus the first 4 positions (attention sinks);
- `recent`: the first 4 and the last B - 4 positions, mostly the report itself (a control);
- `uniform`: the first 4 and B - 4 evenly spaced positions (a control for the selection).
Entries keep their original positions; the reader's tokens are placed after the author's last
position, so to the reader the post looks like an earlier session with most entries evicted.
This is the KV-sharing family of LatentMAS / KVComm / C2C, here between untrusted authors.

Several posts are written independently and never attended to each other. Laid side by side
(`concat`) the reader reads their content but attributes it to the wrong post. `assemble` adds a
short text caption after each post (who wrote it, on what) that the reader prefills: the caption
attends to the post just before it, which binds the post to its explicit provenance.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import torch
import torch.nn.functional as F
from transformers import DynamicCache

from model.backends.base import TEMPERATURE, Generation, Latent

SINKS = 4


@dataclass
class KVPost:
    layers: list            # per layer (keys, values), each [1, kv_heads, S, head_dim], on CPU
    end: int                # the author's sequence length; the reader's first position
    k: int                  # entries kept per head (S)
    nbytes: int = 0
    shared: int = 0         # leading positions every author has in common (the system turn)


def _layer_kv(cache, i):
    if hasattr(cache, "layers"):           # transformers >= 4.56
        return cache.layers[i].keys, cache.layers[i].values
    return cache.key_cache[i], cache.value_cache[i]


class KVWriter:
    """write(messages, response) -> KVPost. `mode` is full | snap | recent | uniform."""

    def __init__(self, backend, mode: str = "full", budget: int = 0, pool: int = 5):
        assert mode in ("full", "snap", "recent", "uniform") and (mode == "full" or budget > SINKS)
        self.b, self.mode, self.budget, self.pool = backend, mode, budget, pool

    @torch.no_grad()
    def write(self, messages, response, latents=(), *, purpose="report", meta=None) -> KVPost:
        b = self.b
        head = b.render(messages)                                       # ends with the assistant header
        full = b.render(messages + [{"role": "assistant", "content": response}], add_generation_prompt=False)
        ids = b.tok(full, add_special_tokens=False, return_tensors="pt").input_ids.to(b.device)
        start = min(b.count_tokens(head), ids.shape[1] - 1)             # the report's first token
        out = b.model.model(input_ids=ids, use_cache=True, output_hidden_states=self.mode == "snap")
        n = ids.shape[1]
        layers = []
        for i in range(len(b.model.model.layers)):
            k, v = _layer_kv(out.past_key_values, i)
            if self.mode != "full" and n > self.budget:
                keep = self._keep(i, out.hidden_states, k, start, n) if self.mode == "snap" else \
                    self._fixed(n, k.device).expand(k.shape[1], -1)
                idx = keep[None, :, :, None].expand(-1, -1, -1, k.shape[-1])
                k, v = k.gather(2, idx), v.gather(2, idx)
            layers.append((k.cpu(), v.cpu()))
        s = layers[0][0].shape[2]
        nbytes = sum(t.numel() * t.element_size() for kv in layers for t in kv)
        shared = b.count_tokens(b.render(messages[:1], add_generation_prompt=False)) \
            if messages and messages[0]["role"] == "system" else 0
        return KVPost(layers, n, s, nbytes, shared)

    def _fixed(self, n, device):
        rest = self.budget - SINKS
        tail = torch.arange(n - rest, n) if self.mode == "recent" else torch.linspace(SINKS, n - 1, rest).round().long()
        return torch.cat([torch.arange(SINKS), tail]).to(device)

    def _keep(self, i, hidden, keys, start, n):
        """[kv_heads, B] positions that the report's queries attend to most in layer i."""
        layer = self.b.model.model.layers[i]
        attn = layer.self_attn
        x = layer.input_layernorm(hidden[i][0, start:])                 # the report's inputs to layer i
        hd = keys.shape[-1]
        q = attn.q_norm(attn.q_proj(x).view(x.shape[0], -1, hd)).transpose(0, 1)    # [heads, w, hd]
        pos = torch.arange(start, n, device=x.device)[None]
        cos, sin = self.b.model.model.rotary_emb(x[None], pos)
        q = q * cos[0] + _rotate_half(q) * sin[0]
        kvh, w = keys.shape[1], q.shape[1]
        q = q.view(kvh, -1, w, hd)                                       # grouped-query heads
        scores = torch.einsum("hgwd,hnd->hgwn", q.float(), keys[0].float()) / math.sqrt(hd)
        causal = torch.arange(n, device=x.device)[None] > pos[0][:, None]    # [w, n]
        prob = scores.masked_fill(causal, float("-inf")).softmax(-1).sum((1, 2))   # [kv_heads, n]
        prob = F.max_pool1d(prob[:, None], self.pool, 1, self.pool // 2)[:, 0]
        prob[:, :SINKS] = float("inf")
        return prob.topk(self.budget, -1).indices.sort(-1).values


def _rotate_half(x):
    h = x.shape[-1] // 2
    return torch.cat((-x[..., h:], x[..., :h]), -1)


@torch.no_grad()
def concat(backend, posts, layout: str = "sequential", dedup: bool = False) -> KVPost:
    """One prefix from several posts written independently.
    - sequential: one after another; each post's keys are rotated forward by the positions before it
      (RoPE rotations compose, and attention only sees relative positions), so the reader sees
      consecutive earlier sessions;
    - parallel: every post keeps the positions it was written at, as in parallel context encoding (APE).
    `dedup` keeps the shared system turn once, from the first post (whole posts only)."""
    if len(posts) == 1:
        return posts[0]
    assert layout in ("sequential", "parallel") and (not dedup or all(p.k == p.end for p in posts))
    cut = min(p.shared for p in posts) if dedup else 0
    dev, off, end, parts = backend.device, 0, 0, []
    for t, p in enumerate(posts):
        c = cut if t else 0
        delta = off - c if layout == "sequential" else 0
        parts.append([(_shift(backend, k[:, :, c:], delta), v[:, :, c:].to(dev)) for k, v in p.layers])
        off, end = delta + p.end, max(end, delta + p.end)
    layers = [(torch.cat([q[i][0] for q in parts], 2), torch.cat([q[i][1] for q in parts], 2))
              for i in range(len(parts[0]))]
    return KVPost(layers, end, layers[0][0].shape[2], sum(t.numel() * t.element_size() for kv in layers for t in kv),
                  posts[0].shared)


def _shift(backend, k, delta: int):
    """Keys written at positions p, rotated to positions p + delta."""
    dev = backend.device
    cos, sin = backend.model.model.rotary_emb(torch.zeros(1, device=dev), torch.tensor([[delta]], device=dev))
    cos, sin = cos[:, None], sin[:, None]                               # [1, 1, 1, head_dim]
    k = k.to(dev).float()
    return (k * cos + _rotate_half(k) * sin).to(backend.model.dtype)


@torch.no_grad()
def assemble(backend, posts, captions) -> KVPost:
    """Posts end to end, each followed by its caption, which the reader prefills on top of what is before it."""
    b, dev = backend, backend.device
    cache, s, pos = DynamicCache(), 0, 0
    for p, cap in zip(posts, captions):
        for i, (k, v) in enumerate(p.layers):
            cache.update(_shift(b, k, pos), v.to(dev), i)
        s, pos = s + p.k, pos + p.end
        ids = b.tok(cap, add_special_tokens=False, return_tensors="pt").input_ids.to(dev)
        m = ids.shape[1]
        b.model.model(input_ids=ids, past_key_values=cache, use_cache=True,
                      position_ids=torch.arange(pos, pos + m, device=dev)[None],
                      cache_position=torch.arange(s, s + m, device=dev),
                      attention_mask=torch.ones(1, s + m, dtype=torch.long, device=dev))
        s, pos = s + m, pos + m
    layers = [_layer_kv(cache, i) for i in range(len(posts[0].layers))]
    return KVPost(layers, pos, s, sum(p.nbytes for p in posts), posts[0].shared)


class KVStream:
    """The forum as one append-only KV cache. Each post is the author's session encoded on top of every
    post before it, so posts can see each other and compose (posts encoded one by one do not: R17);
    every post is encoded once, by its author. Readers generate after the segments they select."""

    def __init__(self, backend):
        self.b, self.layers, self.pos, self.segs = backend, None, 0, []

    @torch.no_grad()
    def append(self, messages, response, meta=None) -> Latent:
        b, dev = self.b, self.b.device
        text = b.render(messages + [{"role": "assistant", "content": response}], add_generation_prompt=False)
        ids = b.tok(text, add_special_tokens=False, return_tensors="pt").input_ids.to(dev)
        cache = DynamicCache()
        for i, (k, v) in enumerate(self.layers or []):
            cache.update(k, v, i)
        s, m = (self.layers[0][0].shape[2] if self.layers else 0), ids.shape[1]
        b.model.model(input_ids=ids, past_key_values=cache, use_cache=True,
                      position_ids=torch.arange(self.pos, self.pos + m, device=dev)[None],
                      cache_position=torch.arange(s, s + m, device=dev),
                      attention_mask=torch.ones(1, s + m, dtype=torch.long, device=dev))
        self.layers = [_layer_kv(cache, i) for i in range(len(b.model.model.layers))]
        self.segs.append((s, s + m))
        self.pos += m
        per = sum(t[:, :, :1].numel() * t.element_size() for kv in self.layers for t in kv)
        return Latent({"segment": len(self.segs) - 1}, m, nbytes=m * per, origin="stream", meta=dict(meta or {}))

    def prefix(self, posts) -> KVPost:
        """The segments of `posts`, in stream order; they keep their positions, as if the rest were evicted."""
        spans = sorted(self.segs[p.data["segment"]] for p in posts)
        layers = [(torch.cat([k[:, :, a:z] for a, z in spans], 2), torch.cat([v[:, :, a:z] for a, z in spans], 2))
                  for k, v in self.layers]
        return KVPost(layers, self.pos, layers[0][0].shape[2], sum(p.nbytes for p in posts))

    def chat(self, prefix, messages, *, purpose="", meta=None, max_new_tokens=512, temperature=TEMPERATURE):
        return chat_after(self.b, prefix, messages, max_new_tokens=max_new_tokens, temperature=temperature)

    def close(self):
        """Free the stream's GPU memory (a project's stream is several GB)."""
        self.layers, self.segs = None, []
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


@torch.no_grad()
def chat_after(backend, post: KVPost, messages, *, max_new_tokens=512, temperature=TEMPERATURE) -> Generation:
    """Generate the reader's reply with `post` as a prefix cache; sampling as HFBackend.chat."""
    b = backend
    cache = DynamicCache()
    for i, (k, v) in enumerate(post.layers):
        cache.update(k.to(b.device), v.to(b.device), i)
    ids = b.tok(b.render(messages), add_special_tokens=False, return_tensors="pt").input_ids.to(b.device)
    eos = b.model.generation_config.eos_token_id
    eos = set(eos if isinstance(eos, (list, tuple)) else [eos])
    s, pos, new = post.k, post.end, []
    for _ in range(max_new_tokens):
        m = ids.shape[1]
        out = b.model(input_ids=ids, past_key_values=cache, use_cache=True,
                      position_ids=torch.arange(pos, pos + m, device=b.device)[None],
                      cache_position=torch.arange(s, s + m, device=b.device),
                      attention_mask=torch.ones(1, s + m, dtype=torch.long, device=b.device), logits_to_keep=1)
        tok = _sample(out.logits[0, -1].float(), temperature)
        s, pos = s + m, pos + m
        if tok in eos:
            break
        new.append(tok)
        ids = torch.tensor([[tok]], device=b.device)
    n_prompt = b.count_tokens(b.render(messages))
    return Generation(b.tok.decode(new, skip_special_tokens=True).strip(), n_prompt, len(new))


def _sample(logits, temperature, top_k=20, top_p=0.95) -> int:
    if temperature <= 0:
        return int(logits.argmax())
    vals, idx = (logits / temperature).topk(top_k)
    p = vals.softmax(-1)
    drop = p.cumsum(-1) - p > top_p          # keep the smallest prefix with mass >= top_p
    p = p.masked_fill(drop, 0)
    return int(idx[torch.multinomial(p / p.sum(), 1)])
