"""Linear probes on saved latent posts. This is the trained-decoder side of interrogability.

    python -m analysis.linprobe runs/smoke_<id>/latent-anchored-blind-oc0.34a/latents.pt

For each target we fit an L2 logistic regression on the mean-pooled latent vectors.
Cross-validation is grouped by project, so a probe cannot memorize one project's
surface tokens. We report AUROC, along with a label-permutation baseline.
- verified: did the code pass its visible test (truth from CI)
- claim: did the author mark DONE
- verified|claimed: restricted to posts that claimed DONE. Can the latent still tell the
  real PASS from FAIL? This is the overclaim case behind hypothesis H4.
- hidden|visible_pass: restricted to posts whose code passed its visible test. Does the latent
  predict the isolated hidden-test result, i.e. bugs that the CI gate cannot see?
"""
from __future__ import annotations

import json
import os
import random
import sys

import torch


def auroc(scores, labels):
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def fit_predict(xtr, ytr, xte, l2=1e-2, steps=200):
    mu, sd = xtr.mean(0), xtr.std(0).clamp_min(1e-4)
    xtr, xte = (xtr - mu) / sd, (xte - mu) / sd
    w = torch.zeros(xtr.shape[1], requires_grad=True)
    b = torch.zeros(1, requires_grad=True)
    opt = torch.optim.LBFGS([w, b], max_iter=steps, line_search_fn="strong_wolfe")

    def closure():
        opt.zero_grad()
        loss = torch.nn.functional.binary_cross_entropy_with_logits(xtr @ w + b, ytr) + l2 * (w * w).sum()
        loss.backward()
        return loss
    opt.step(closure)
    with torch.no_grad():
        return (xte @ w + b).tolist()


def grouped_cv(x, y, groups, folds=5, seed=0):
    uniq = sorted(set(groups))
    random.Random(seed).shuffle(uniq)
    fold_of = {g: i % folds for i, g in enumerate(uniq)}
    scores, labels = [], []
    for f in range(min(folds, len(uniq))):
        tr = [i for i, g in enumerate(groups) if fold_of[g] != f]
        te = [i for i, g in enumerate(groups) if fold_of[g] == f]
        if not te or len({y[i] for i in tr}) < 2:
            continue
        s = fit_predict(x[tr], torch.tensor([float(y[i]) for i in tr]), x[te])
        scores += s
        labels += [y[i] for i in te]
    return auroc(scores, labels), len(labels)


# name -> (which posts, label). Labels come from the trusted harness, never from the author.
TARGETS = {
    "verified": (lambda r: True, lambda r: bool(r["verified_ok"])),
    "claim": (lambda r: True, lambda r: r["claimed"] == "DONE"),
    "verified|claimed": (lambda r: r["claimed"] == "DONE", lambda r: bool(r["verified_ok"])),
    # Beyond CI: the code passed its visible test; does the latent know whether it is actually right?
    "hidden|visible_pass": (lambda r: bool(r["verified_ok"]) and r.get("truth_iso_ok") is not None,
                            lambda r: bool(r["truth_iso_ok"])),
}


def probe_all(x_all, rows, seed=0, perm=True):
    out = {}
    for name, (keep, label) in TARGETS.items():
        idx = [i for i, r in enumerate(rows) if keep(r)]
        y = [label(rows[i]) for i in idx]
        if len(set(y)) < 2:
            out[name] = {"n": len(idx), "auroc": None, "note": "one class only"}
            continue
        x, g = x_all[idx], [rows[i]["project"] for i in idx]
        a, n = grouped_cv(x, y, g, seed=seed)
        out[name] = {"n": n, "pos_rate": round(sum(y) / len(y), 3), "auroc": a}
        if perm:
            shuffled = y[:]
            random.Random(seed + 1).shuffle(shuffled)
            out[name]["perm_auroc"] = grouped_cv(x, shuffled, g, seed=seed)[0]
    return out


def run(path, seed=0):
    rows = torch.load(path, weights_only=False)
    x_all = torch.stack([r["latent"].float().mean(0) for r in rows])
    return {"n_posts": len(rows), **probe_all(x_all, rows, seed)}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("latents", nargs="+")
    ap.add_argument("--pool", default="", help="write one pooled result over all files to this path")
    a = ap.parse_args()
    if a.pool:
        # Controls only change what readers receive, so posts from all conditions are comparable.
        # Grouping the folds by project keeps every copy of a project in the same fold.
        rows = [r for p in a.latents for r in torch.load(p, weights_only=False)]
        x_all = torch.stack([r["latent"].float().mean(0) for r in rows])
        res = {"files": a.latents, "n_posts": len(rows), **probe_all(x_all, rows)}
        with open(a.pool, "w") as f:
            json.dump(res, f, indent=1)
        print(json.dumps({k: v for k, v in res.items() if k != "files"}, indent=1))
        return
    res = {}
    for p in a.latents:
        r = run(p)
        res[p] = r
        with open(os.path.join(os.path.dirname(p), "linprobe.json"), "w") as f:
            json.dump(r, f, indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
