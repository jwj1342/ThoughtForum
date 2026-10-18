"""Writers for a local HuggingFace model. `GistWriter` with an untrained head is the method.

- GistWriter: k query vectors are appended after the author's whole context, and their
  final-layer states, mapped into the input space, are the post. With `random_head` the
  queries are random vocabulary embeddings and nothing is trained; a trained head (a learned
  residual map on top) is only an ablation.
- ChunkMeanWriter: the final-layer states of the author's message tokens, pooled into k
  contiguous chunk means. It sees only what the author said, and pooling erases instance content.
"""
from __future__ import annotations

import torch

from model.backends.base import Latent
from model.writers import Writer


class WriteHead(torch.nn.Module):
    """k query vectors q, plus a residual map out(e) = e + (e A) B + bias. B = 0 at init: the identity."""

    def __init__(self, q: torch.Tensor, r: int = 64):
        super().__init__()
        d = q.shape[1]
        self.q = torch.nn.Parameter(q.clone().float())
        self.a = torch.nn.Parameter(torch.randn(d, r) / d ** 0.5)
        self.b = torch.nn.Parameter(torch.zeros(r, d))
        self.bias = torch.nn.Parameter(torch.zeros(d))

    @property
    def k(self) -> int:
        return self.q.shape[0]

    def out(self, e):
        return e + (e @ self.a) @ self.b + self.bias


def random_head(emb: torch.nn.Embedding, k: int = 16, seed: int = 0, r: int = 64) -> WriteHead:
    """The untrained head: k random vocabulary embeddings as queries and the identity map."""
    n = emb.weight.shape[0]   # skip the first ids (bytes and other rare pieces); same draw as all earlier runs
    ids = torch.randint(min(1000, n // 4), min(n, 50000), (k,), generator=torch.Generator().manual_seed(seed))
    return WriteHead(emb.weight[ids].detach().float(), r)


def load_head(spec: str, backend) -> WriteHead:
    """`random:K[:SEED]` for the untrained head (the method), or the path of a saved head."""
    if spec.startswith("random"):
        head = random_head(backend.emb, *[int(x) for x in spec.split(":")[1:]])
    else:
        st = torch.load(spec, map_location=backend.device, weights_only=True)
        head = WriteHead(st["q"], st["a"].shape[1])
        head.load_state_dict(st)
    return head.to(backend.device).eval()


def _post(e: torch.Tensor, purpose: str, **meta) -> Latent:
    e = e.to(torch.float16).cpu()
    return Latent(e, e.shape[0], nbytes=e.numel() * 2, origin=purpose, meta=meta)


class GistWriter(Writer):
    def __init__(self, backend, head: WriteHead):
        self.backend, self.head = backend, head

    def gist(self, ctx_emb: torch.Tensor, grad: bool = False) -> torch.Tensor:
        """The post for a context given as input embeddings; with grad=True the head can be trained."""
        h = self.backend.read_after(ctx_emb, self.head.q, grad=grad)
        with torch.set_grad_enabled(grad):
            return self.head.out(self.backend.to_input_space(h))

    @torch.no_grad()
    def write(self, messages, response, latents=(), *, purpose="report", meta=None):
        b = self.backend
        resp = b.text_embeddings(response or " ")
        e = self.gist(torch.cat([b.embed_chat(messages, latents), resp], 0))
        return _post(e, purpose, src_tokens=resp.shape[0], writer="gist")


class ChunkMeanWriter(Writer):
    def __init__(self, backend, k: int = 16):
        self.backend, self.k = backend, k

    @torch.no_grad()
    def write(self, messages, response, latents=(), *, purpose="report", meta=None):
        b = self.backend
        resp = b.text_embeddings(response or " ")
        h = b.final_states(torch.cat([b.embed_chat(messages, latents), resp], 0))[-resp.shape[0]:]
        if h.shape[0] > 1:
            h = h[:-1]  # the last state predicts end-of-turn, i.e. a control token
        z = torch.stack([c.mean(0) for c in torch.tensor_split(h.float(), min(self.k, h.shape[0]), dim=0)])
        return _post(b.to_input_space(z), purpose, src_tokens=resp.shape[0])
