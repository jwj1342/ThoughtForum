"""Compare conditions in a run directory, with project-level bootstrap CIs. Pure Python.

    python -m analysis.tables runs/smoke_<jobid>            # markdown table to stdout
    python -m analysis.tables runs/e0_<id>/task* --md out.md

Rates over projects (method_pass, class_pass, false_declaration) use a percentile
bootstrap over projects. Probe accuracies and propagation pass rates are proportions
over posts or attempts, so they get Wilson intervals.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import random

from forum.metrics import is_misled


def _jsonl(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def boot(xs, n=2000, seed=0):
    xs = [float(x) for x in xs if x is not None]
    if not xs:
        return None, None, None
    rng = random.Random(seed)
    m = sum(xs) / len(xs)
    means = sorted(sum(rng.choice(xs) for _ in xs) / len(xs) for _ in range(n))
    return m, means[int(0.025 * n)], means[int(0.975 * n) - 1]


def wilson(k, n, z=1.96):
    if not n:
        return None, None, None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def fmt(t):
    m, lo, hi = t
    return "–" if m is None else f"{m:.2f} [{lo:.2f},{hi:.2f}]"


def condition_stats(d):
    proj = _jsonl(os.path.join(d, "projects.jsonl"))
    probes = _jsonl(os.path.join(d, "probes.jsonl"))
    events = _jsonl(os.path.join(d, "events.jsonl"))
    s = {"condition": os.path.basename(d.rstrip("/")), "n": len(proj)}
    for k in ("method_pass", "method_pass_iso", "class_pass", "false_declaration"):
        s[k] = boot([p.get(k) for p in proj])
    s["tokens/proj"] = sum(p.get("prompt_tokens", 0) + p.get("gen_tokens", 0) for p in proj) / max(1, len(proj))
    work = [(e, is_misled(e)) for e in events if e["type"] == "work"]
    misled = [e.get("iso_ok", e["hidden_ok"]) for e, m in work if m is True]
    clean = [e.get("iso_ok", e["hidden_ok"]) for e, m in work if m is False]
    s["pass|misled"] = wilson(sum(misled), len(misled))
    s["pass|clean"] = wilson(sum(clean), len(clean))
    for arm in ("self", "baseline"):
        rows = [p[arm] for p in probes if arm in p]
        for q in ("anchor", "verified"):
            s[f"{arm}:{q}"] = wilson(sum(r["correct"][q] for r in rows), len(rows))
    over = [p for p in probes if p.get("overclaim")]
    s["reveals_fail"] = wilson(sum(p["self"]["correct"]["verified"] for p in over), len(over))
    return s


COLS = ["condition", "n", "method_pass", "method_pass_iso", "class_pass", "false_declaration", "pass|misled", "pass|clean",
        "self:anchor", "baseline:anchor", "self:verified", "baseline:verified", "reveals_fail", "tokens/proj"]


def table(stats):
    lines = ["| " + " | ".join(COLS) + " |", "|" + "---|" * len(COLS)]
    for s in stats:
        cells = []
        for c in COLS:
            v = s.get(c)
            cells.append(fmt(v) if isinstance(v, tuple) else (f"{v:.0f}" if isinstance(v, float) else str(v)))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+", help="run dirs (each holds one subdir per condition)")
    ap.add_argument("--md", help="also write the table to this file")
    a = ap.parse_args()
    conds = sorted({os.path.dirname(p) for r in a.runs for p in glob.glob(os.path.join(r, "*", "projects.jsonl"))})
    out = table([condition_stats(c) for c in conds])
    print(out)
    if a.md:
        with open(a.md, "w", encoding="utf-8") as f:
            f.write(out + "\n")


if __name__ == "__main__":
    main()
