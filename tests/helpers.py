"""Shared helpers for the tests."""
from forum.orchestrator import run_project
from forum.run import writer_for
from model.backends.mock import MockBackend


def run(project, cfg, backend=None, seed=0, bank=None):
    """One forum project on the mock backend (or the given one): (record, events, probes)."""
    backend = backend or MockBackend()
    return run_project(project, backend, writer_for(cfg, backend), cfg, [] if bank is None else bank, seed=seed)


class RecordingMock(MockBackend):
    """A mock that keeps the last user message of every call with the given purpose."""

    def __init__(self, purpose: str, **kw):
        super().__init__(**kw)
        self.purpose, self.seen = purpose, []

    def chat(self, messages, latents=(), **kw):
        if kw.get("purpose") == self.purpose:
            self.seen.append((kw.get("meta") or {}, messages[-1]["content"]))
        return super().chat(messages, latents, **kw)
