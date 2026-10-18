"""A trained read-in map for latent posts (E1a; an ablation, not part of the method).

    f(z) = z + (z A) B + b,   with B = 0 at init, so the untrained adapter is the identity.
"""
from __future__ import annotations

import torch


class ReadAdapter(torch.nn.Module):
    def __init__(self, d: int, r: int = 64):
        super().__init__()
        self.a = torch.nn.Parameter(torch.randn(d, r) / d ** 0.5)
        self.b = torch.nn.Parameter(torch.zeros(r, d))
        self.bias = torch.nn.Parameter(torch.zeros(d))

    def forward(self, z):
        return z + (z @ self.a) @ self.b + self.bias


def load_adapter(path: str, device) -> ReadAdapter:
    st = torch.load(path, map_location=device, weights_only=True)
    m = ReadAdapter(st["a"].shape[0], st["a"].shape[1]).to(device)
    m.load_state_dict(st)
    return m.eval()
