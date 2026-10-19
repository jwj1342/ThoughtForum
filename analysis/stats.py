"""Item-level statistics: cluster-bootstrap CIs per condition and paired comparisons between conditions.

    python -m analysis.stats forum runs/e0st_<id>/mislead/*/ runs/e0s4_<id>/text/*/
    python -m analysis.stats measure runs/measure_kv_<id>/*/rows.jsonl --ref "lie/text/-/1"

An item is one consumer method of one project; it passes when its isolated hidden tests pass.
- forum: methods with dependencies none of which the method's own author wrote (the ones that
  measure the channel: SecretBench consumers, ClassEval callers); with --items all, every method.
- measure: every (project, consumer, seed) row of benchmark/measure.py, grouped by speech /
  channel / load (and "T" for the transplant control); seeds are repeated measures of one item.

Items of one project are correlated, so intervals resample projects (cluster bootstrap, 95%).
Two conditions are compared on the projects they share: the difference of pass rates with a
paired cluster-bootstrap CI, and an exact McNemar test on the items both conditions have
(two-sided; discordant items only). p-values are Holm-adjusted over the comparisons of one call.
With --ref, each condition is compared with the reference; otherwise every pair is compared.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import random
from collections import defaultdict

from analysis.paired import sign_test


def forum_items(cond_dir: str, which: str = "cross") -> dict:
    """{(project, method, seed): passed} for one forum condition directory."""
    with open(os.path.join(cond_dir, "config.json")) as f:
        seed = json.load(f).get("seed", 0)
    out = {}
    for line in open(os.path.join(cond_dir, "projects.jsonl")):
        r = json.loads(line)
        methods = r["methods"]
        for m, v in methods.items():
            deps = v.get("deps", [])
            if which == "cross" and (not deps or v.get("author") in {methods[d].get("author") for d in deps}):
                continue
            out[(r["project"], m, seed)] = bool(v["iso_ok"])
    return out


def measure_items(paths) -> dict:
    """{condition label: {(project, consumer, seed): passed}} from measure rows.jsonl files."""
    conds = defaultdict(dict)
    for path in paths:
        for line in open(path):
            r = json.loads(line)
            label = f"{r['speech']}/{r['channel']}/load{r['load']}" + ("/T" if r["transplant"] else "")
            conds[label][(r["project"], r["consumer"], r["seed"])] = bool(r["ok"])
    return dict(conds)


def _by_project(items: dict) -> dict:
    g = defaultdict(list)
    for key, ok in items.items():   # key[0] is the project
        g[key[0]].append(ok)
    return g


def rate(groups, projects) -> float:
    k = sum(sum(groups[p]) for p in projects if p in groups)
    n = sum(len(groups[p]) for p in projects if p in groups)
    return k / n if n else float("nan")


def cluster_ci(items: dict, n_boot: int = 4000, seed: int = 0):
    g = _by_project(items)
    ps = sorted(g)
    rng = random.Random(seed)
    est = rate(g, ps)
    reps = sorted(rate(g, [rng.choice(ps) for _ in ps]) for _ in range(n_boot))
    return est, reps[int(0.025 * n_boot)], reps[int(0.975 * n_boot) - 1]


def compare(a: dict, b: dict, n_boot: int = 4000, seed: int = 0) -> dict:
    """b - a on the projects both have: difference, paired cluster-bootstrap CI, exact McNemar on shared items."""
    ga, gb = _by_project(a), _by_project(b)
    ps = sorted(set(ga) & set(gb))
    rng = random.Random(seed)
    diff = rate(gb, ps) - rate(ga, ps)
    reps = []
    for _ in range(n_boot):
        s = [rng.choice(ps) for _ in ps]
        reps.append(rate(gb, s) - rate(ga, s))
    reps.sort()
    shared = set(a) & set(b)
    only_a = sum(a[k] and not b[k] for k in shared)
    only_b = sum(b[k] and not a[k] for k in shared)
    return {"diff": diff, "lo": reps[int(0.025 * n_boot)], "hi": reps[int(0.975 * n_boot) - 1],
            "projects": len(ps), "shared": len(shared), "only_a": only_a, "only_b": only_b,
            "p": sign_test(only_a, only_b)}


def holm(ps: list[float]) -> list[float]:
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = run
    return adj


def report(conds: dict, ref: str | None = None, n_boot: int = 4000) -> str:
    conds = {k: v for k, v in conds.items() if v}   # e.g. a forum run in which no reader had another's post
    lines = ["| condition | items | projects | pass rate [95% CI] |", "|---|---|---|---|"]
    for name, items in conds.items():
        m, lo, hi = cluster_ci(items, n_boot)
        lines.append(f"| {name} | {len(items)} | {len(_by_project(items))} | {m:.3f} [{lo:.3f}, {hi:.3f}] |")
    names = list(conds)
    pairs = [(ref, n) for n in names if n != ref] if ref in conds else [(x, y) for i, x in enumerate(names) for y in names[i + 1:]]
    res = [compare(conds[x], conds[y], n_boot) for x, y in pairs]
    adj = holm([r["p"] for r in res])
    lines += ["", "| B vs A | B - A [95% CI] | projects | shared items | A only / B only | McNemar p (Holm) |",
              "|---|---|---|---|---|---|"]
    for (x, y), r, p in zip(pairs, res, adj):
        lines.append(f"| {y} vs {x} | {r['diff']:+.3f} [{r['lo']:+.3f}, {r['hi']:+.3f}] | {r['projects']} | {r['shared']} | "
                     f"{r['only_a']} / {r['only_b']} | {r['p']:.2g} ({p:.2g}) |")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=("forum", "measure"))
    ap.add_argument("paths", nargs="+", help="forum: condition directories; measure: rows.jsonl files (globs ok)")
    ap.add_argument("--items", default="cross", choices=("cross", "all"), help="forum items")
    ap.add_argument("--ref", help="compare every condition with this one only")
    ap.add_argument("--only", help="measure: comma-separated substrings; keep conditions containing any")
    ap.add_argument("--boot", type=int, default=4000)
    a = ap.parse_args(argv)
    paths = [p for pat in a.paths for p in sorted(glob.glob(pat))]
    if a.kind == "forum":   # the same condition under several seeds pools into one entry
        conds = defaultdict(dict)
        for d in paths:
            if os.path.exists(os.path.join(d, "projects.jsonl")):
                conds[os.path.basename(d.rstrip("/"))].update(forum_items(d, a.items))
        conds = dict(conds)
    else:
        conds = measure_items(paths)
        if a.only:
            keep = a.only.split(",")
            conds = {k: v for k, v in conds.items() if any(s in k for s in keep) or k == a.ref}
    print(report(conds, a.ref, a.boot))


if __name__ == "__main__":
    main()
