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


class MockStream:
    """The shared stream on the mock backend: a post is a MockWriter record, a prefix the list of them."""

    def __init__(self, backend, k: int = 16):
        self.backend, self.writer = backend, MockWriter(k)

    def append(self, messages, response, meta=None) -> Latent:
        return self.writer.write(messages, response, meta=meta, purpose="stream")

    def prefix(self, posts):
        return list(posts)

    def chat(self, prefix, messages, **kw):
        return self.backend.chat(messages, prefix, **kw)


def make_stream(backend):
    """A fresh shared stream for one project: MockStream on the mock backend, KVStream otherwise."""
    if backend.name == "mock":
        return MockStream(backend)
    if not backend.reads_latents:
        raise ValueError(f"the {backend.name} backend cannot hold a latent stream; use --backend hf")
    from model.kv_posts import KVStream
    return KVStream(backend)


def make_writer(backend, k: int = 16, head: str = "") -> Writer:
    """MockWriter for the mock backend; GistWriter if a head is given (`random:16` = the method);
    ChunkMeanWriter otherwise."""
    if backend.name == "mock":
        return MockWriter(k)
    if not backend.reads_latents:
        raise ValueError(f"the {backend.name} backend cannot write latent posts; use --backend hf")
    from model.hf_writers import ChunkMeanWriter, GistWriter, load_head
    return GistWriter(backend, load_head(head, backend)) if head else ChunkMeanWriter(backend, k)
