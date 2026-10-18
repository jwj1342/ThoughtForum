"""Control for H4: does a latent carry the code's real state *beyond its own text*?

    python -m analysis.neutral_probe runs/e0_<id>/task1/*/latents.pt --out runs/e0_<id>/neutral_probe.json

Every saved post is encoded a second time: same message text, same k, but in a neutral
context with no project, code or test log. The same grouped-CV linear probes are then
fit on both versions:

- writer: the latent as posted, read in the author's own context
- neutral: the latent of the text alone

If `verified|claimed` AUROC is much higher for writer than for neutral, the latent leaks
the true CI state that the (possibly falsified) message text does not contain. If the
two are close, the probe was just reading the text.
"""
from __future__ import annotations

import argparse
import json

import torch

from analysis.linprobe import grouped_cv, probe_all
from forum.dump import dump_files, load_rows
from model.backends import DEFAULT_MODEL

NEUTRAL = [{"role": "system", "content": "You are reading a short message."},
           {"role": "user", "content": "Read the message."}]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("latents", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    a = ap.parse_args()
    files = dump_files(a.latents)
    rows = [r for r in load_rows(files) if r["text"].strip()]
    from model.backends.hf import HFBackend
    from model.hf_writers import ChunkMeanWriter
    b = HFBackend.load(a.model)
    neutral = torch.stack([ChunkMeanWriter(b, r["latent"].shape[0]).write(NEUTRAL, r["text"]).data.float().mean(0)
                           for r in rows])
    writer = torch.stack([r["latent"].float().mean(0) for r in rows])
    res = {"files": files, "n_posts": len(rows), "n_falsified": sum(r["falsified"] for r in rows),
           "writer": probe_all(writer, rows, perm=False), "neutral": probe_all(neutral, rows, perm=False)}
    # The sharpest slice: posts whose text was falsified to DONE vs honest DONE posts.
    done = [i for i, r in enumerate(rows) if r["claimed"] == "DONE"]
    y = [rows[i]["falsified"] for i in done]
    if len(set(y)) == 2:
        g = [rows[i]["project"] for i in done]
        res["falsified_vs_honest_done"] = {
            "writer": grouped_cv(writer[done], y, g)[0], "neutral": grouped_cv(neutral[done], y, g)[0], "n": len(done)}
    # Deceive mode: every report of a deceiving agent carries the same instruction to claim DONE, so
    # among its DONE posts the only difference between honest and lying ones is the test result.
    dec = [i for i, r in enumerate(rows) if r.get("overclaimer") and r["claimed"] == "DONE"]
    y = [rows[i]["falsified"] for i in dec]
    if len(set(y)) == 2:
        g = [rows[i]["project"] for i in dec]
        res["deceiver_lie_vs_true_done"] = {
            "writer": grouped_cv(writer[dec], y, g)[0], "neutral": grouped_cv(neutral[dec], y, g)[0],
            "n": len(dec), "lie_rate": round(sum(y) / len(y), 3)}
    with open(a.out, "w") as f:
        json.dump(res, f, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "files"}, indent=1))


if __name__ == "__main__":
    main()
