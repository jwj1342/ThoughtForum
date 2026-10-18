"""Writers turn an author's context into a latent post.

A writer gets what the author has seen (chat messages, plus any latent posts it read) and the
author's own message, and returns k vectors in the reader's input space. Posts are computed by
trusted inference from the author's real context; agents never hand in vectors of their own.

- GistWriter (model/hf_writers.py) is the method: k query vectors read the author's whole context.
- ChunkMeanWriter (model/hf_writers.py) is the baseline it replaces: pooled states of the message.
- MockWriter is an idealized, lossless record of the post, for testing the pipeline without a model.
"""
from __future__ import annotations

import re

from model.backends.base import Latent


class Writer:
    def write(self, messages: list[dict], response: str, latents=(), *, purpose: str = "report",
              meta: dict | None = None) -> Latent:
        raise NotImplementedError


class MockWriter(Writer):
    def __init__(self, k: int = 16):
        self.k = k

    def write(self, messages, response, latents=(), *, purpose="report", meta=None):
        meta = meta or {}
        m = re.search(r"STATUS:\s*(DONE|PARTIAL|BLOCKED)", response)
        rec = {"anchor": meta.get("anchor"), "visible_ok": meta.get("visible_ok"), "claimed": m.group(1) if m else None}
        return Latent(rec, self.k, nbytes=self.k * 4096 * 2, origin=purpose)


def make_writer(backend, k: int = 16, head: str = "") -> Writer:
    """MockWriter for the mock backend; GistWriter if a head is given (`random:16` = the method);
    ChunkMeanWriter otherwise."""
    if backend.name == "mock":
        return MockWriter(k)
    if not backend.reads_latents:
        raise ValueError(f"the {backend.name} backend cannot write latent posts; use --backend hf")
    from model.hf_writers import ChunkMeanWriter, GistWriter, load_head
    return GistWriter(backend, load_head(head, backend)) if head else ChunkMeanWriter(backend, k)
