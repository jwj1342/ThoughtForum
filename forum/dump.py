"""The latents.pt dump (`--save-latents true`): every latent post with its ground truth.

Training scripts and offline analyses read these rows. `context` is the author's context the
post was read from, kept so a writer can be re-run or trained offline.
"""
from __future__ import annotations

import glob


def latent_dump(bank, projects=()) -> list[dict]:
    info = {p.pid: (p.class_name, p.names) for p in projects}
    return [{"pid": p.pid, "project": p.project, "anchor": p.anchor, "claimed": p.claimed,
             "verified_ok": (p.verified or {}).get("ok"), "truth_ok": (p.truth or {}).get("ok"),
             "truth_iso_ok": (p.truth or {}).get("iso_ok"), "falsified": p.falsified, "text": p.text,
             "author": p.author, "overclaimer": p.meta.get("overclaimer", False),
             "context": p.meta.get("context"),
             "origin": p.latent.origin, "class_name": info.get(p.project, ("", []))[0],
             "options": info.get(p.project, ("", []))[1], "latent": p.latent.data}
            for p in bank if p.latent is not None]


def dump_files(patterns) -> list[str]:
    """Expand file names and globs, sorted and without duplicates."""
    return sorted({f for g in patterns for f in glob.glob(g)})


def load_rows(patterns) -> list[dict]:
    import torch
    return [r for f in dump_files(patterns) for r in torch.load(f, weights_only=False)]
