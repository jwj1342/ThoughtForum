"""Paired comparison of conditions on the same methods (isolated hidden tests).

    python -m analysis.paired runs/e0p_<id>/task*/*/ --deps-only

Each condition directory holds a projects.jsonl. Methods are matched across conditions by
(project, method). For each pair of conditions we count the discordant methods (passes in
A only / in B only) and give a two-sided exact sign test. That is more sensitive than
comparing pooled rates when the conditions share the same projects.
"""
from __future__ import annotations

import argparse
import json
import math
import os

from benchmark.tasks import load_classeval


def sign_test(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def load(cond_dir):
    with open(os.path.join(cond_dir, "config.json")) as f:
        tag = json.load(f).get("tag") or os.path.basename(os.path.normpath(cond_dir))
    out = {}
    with open(os.path.join(cond_dir, "projects.jsonl")) as f:
        for line in f:
            r = json.loads(line)
            for m, v in r["methods"].items():
                out[(r["project"], m)] = bool(v["iso_ok"])
    return os.path.basename(os.path.normpath(cond_dir)) or tag, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--deps-only", action="store_true", help="only methods that call other methods")
    ap.add_argument("--data", default="data/ClassEval_data.json")
    a = ap.parse_args()
    conds = [load(d) for d in a.dirs if os.path.exists(os.path.join(d, "projects.jsonl"))]
    keys = set.intersection(*(set(c[1]) for c in conds))
    if a.deps_only:
        dep = {(p.pid, s.name) for p in load_classeval(a.data, min_methods=1) for s in p.subtasks if s.deps}
        keys &= dep
    keys = sorted(keys)
    print(f"{len(keys)} methods shared by {len(conds)} conditions" + (" (dependent only)" if a.deps_only else ""))
    for name, r in conds:
        print(f"  {name:48s} {sum(r[k] for k in keys) / len(keys):.3f}")
    print("pairwise: A-only / B-only, exact sign test p")
    for i, (na, ra) in enumerate(conds):
        for nb, rb in conds[i + 1:]:
            b = sum(ra[k] and not rb[k] for k in keys)
            c = sum(rb[k] and not ra[k] for k in keys)
            print(f"  {na} vs {nb}: {b} / {c}, p={sign_test(b, c):.3f}")


if __name__ == "__main__":
    main()
