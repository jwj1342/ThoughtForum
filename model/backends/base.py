from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Placeholder that a prompt uses to say "insert latent message i here".
LATENT_MARK = "<<LATENT:{i}>>"
LATENT_RE = re.compile(r"<<LATENT:(\d+)>>")


@dataclass
class Generation:
    text: str
    prompt_tokens: int = 0     # text tokens + latent slots fed to the model
    gen_tokens: int = 0


@dataclass
class Latent:
    """An opaque message: k vectors in the reader's input-embedding space."""
    data: Any                  # torch.Tensor [k, d] for HF; a dict for the mock backend
    k: int
    nbytes: int = 0
    origin: str = "report"     # report | artifact | zero | mean | noise | shuffle
    meta: dict = field(default_factory=dict)


class Backend:
    """Interface shared by all model backends.

    `chat` generates text from chat messages. Any `LATENT_MARK` in the messages is
    replaced by the vectors of `latents[i]`. `encode` returns the latent message for
    `response`, read in the context of `messages`.
    """

    name = "base"

    def chat(self, messages: list[dict], latents: list[Latent] = (), *, purpose: str = "",
             meta: dict | None = None, max_new_tokens: int = 512, temperature: float = 0.0) -> Generation:
        raise NotImplementedError

    def encode(self, messages: list[dict], response: str, latents: list[Latent] = (), *, k: int = 16,
               purpose: str = "", meta: dict | None = None) -> Latent:
        raise NotImplementedError

    def transform(self, lat: Latent, kind: str, bank: list[Latent], seed: int) -> Latent:
        """Content controls: zero | mean | noise (shuffle is handled by the forum)."""
        raise NotImplementedError

    def count_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)
