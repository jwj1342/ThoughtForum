"""Deterministic stand-in for an LLM, so the pipeline can be tested without a model or a GPU.

The mock reads its decisions from `meta`. It writes the reference solution with probability
`p_correct`, and a stub otherwise. Paired with MockWriter, whose latent post is an idealized,
lossless record, routing, controls and probes can be checked end to end. It says nothing about
what a real model's latents carry.
"""
from __future__ import annotations

import hashlib

from model.backends.base import Backend, Generation, LATENT_RE


def _u(*parts) -> float:
    h = hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


class MockBackend(Backend):
    name = "mock"

    def __init__(self, p_correct: float = 0.6, seed: int = 0):
        self.p_correct = p_correct
        self.seed = seed

    def chat(self, messages, latents=(), *, purpose="", meta=None, max_new_tokens=512, temperature=0.0):
        meta = meta or {}
        n_lat = sum(len(LATENT_RE.findall(m["content"])) for m in messages)
        n_prompt = sum(self.count_tokens(m["content"]) for m in messages) + 16 * n_lat
        if purpose == "choose":
            text = meta["options"][0]
        elif purpose == "implement":
            st = meta["subtask"]
            good = _u(self.seed, meta.get("agent"), st.name, meta.get("attempt")) < self.p_correct
            text = "```python\n" + (st.solution if good else f"def {st.name}(self, *args, **kwargs):\n    return None\n") + "```"
        elif purpose == "report":
            status = "DONE" if meta.get("visible_ok") or meta.get("pressure") else "PARTIAL"
            text = f"STATUS: {status}\n`{meta['subtask'].name}` implemented per docstring."
        elif purpose == "peer_test":
            text = "```python\n" + meta["subtask"].hidden_test.replace("class ", "class Peer", 1) + "```"
        elif purpose == "probe":
            text = self._probe(latents, meta)
        else:
            text = ""
        return Generation(text, n_prompt, self.count_tokens(text))

    @staticmethod
    def _probe(latents, meta):
        rec = latents[0].data if latents and isinstance(latents[0].data, dict) else {}
        q = meta.get("question")
        if not rec:
            return "unknown"
        if q == "anchor":
            return rec.get("anchor", "unknown")
        if q == "verified":
            return "PASS" if rec.get("visible_ok") else "FAIL"
        if q == "claim":
            return "YES" if rec.get("claimed") == "DONE" else "NO"
        return "unknown"
