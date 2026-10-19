"""What every model backend offers: chat generation, with latent posts spliced into the prompt."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Decoding used by every run so far: Qwen3's own sampling defaults. temperature=0 means greedy.
TEMPERATURE = 0.6

# Placeholder that a prompt uses to say "insert latent post i here".
LATENT_MARK = "<<LATENT:{i}>>"
LATENT_RE = re.compile(r"<<LATENT:(\d+)>>")


@dataclass
class Generation:
    text: str
    prompt_tokens: int = 0     # text tokens + latent slots fed to the model
    gen_tokens: int = 0


@dataclass
class Latent:
    """An opaque post: k vectors in the reader's input-embedding space."""
    data: Any                  # torch.Tensor [k, d] for HF; a dict for the mock backend
    k: int
    nbytes: int = 0
    origin: str = "report"     # report | artifact | zero
    meta: dict = field(default_factory=dict)

    def blank(self) -> "Latent":
        """Same shape, no content: the `zero` control."""
        data = self.data * 0 if hasattr(self.data, "shape") else {}
        return Latent(data, self.k, self.nbytes, origin="zero")


class Backend:
    """`chat` generates text from chat messages; every LATENT_MARK in them is replaced by the
    vectors of `latents[i]`. Backends that cannot read latents (`api`) reject them."""

    name = "base"
    reads_latents = True

    def chat(self, messages: list[dict], latents: list[Latent] = (), *, purpose: str = "",
             meta: dict | None = None, max_new_tokens: int = 512, temperature: float = TEMPERATURE) -> Generation:
        raise NotImplementedError

    def count_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    def reseed(self, seed: int):
        """Make the sampling of the calls that follow reproducible under `seed`."""
