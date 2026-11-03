"""What is behind a pass rate. Point estimates only; analysis/stats.py gives the intervals.

    python -m analysis.breakdown measure "runs/offline_<id>/*/rows.jsonl"
    python -m analysis.breakdown forum runs/forum_<id>/*/*/*/

- measure: by consumer, the pass rate and the share of first answers that call forbidden methods;
  by condition, the share of code with the true and the falsely stated tag, what a reader answers when
  asked what a producer returns (by tag: an exact match would mostly measure the answer's format; a
  session-text reader answers in the author's "STATUS: ..." style), prompt tokens and post size.
- forum: the retries behind a pass rate (posts, rounds, share of DONE claims), first-attempt
  delegation, and how often an author's first report states its true tag (the log keeps a post's
  first 400 characters, so this means nothing for session text).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from collections import defaultdict

from benchmark.secret_tasks import false_format, project_of
from benchmark.secretbench import CONSUMERS, PRODUCERS


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else float("nan")


def probe_tags(rows) -> dict:
    """{condition: (share of answers with the true tag, with the false tag)}; one answer per
    (project, producer, seed), since consumers of one producer share its probe."""
    seen, out = {}, defaultdict(list)
    for r in rows:
        for d, a in r["answers"].items():
            key = (r["project"], d, r["seed"], label(r))
            if key not in seen:
                seen[key] = True
                p = project_of(r["project"])
                out[label(r)].append((p.meta["formats"][d]["tag"] in a["answer"], false_format(p, d)["tag"] in a["answer"]))
    return {k: (mean([t for t, _ in v]), mean([f for _, f in v])) for k, v in out.items()}


def label(r) -> str:
    return f"{r['speech']}/{r['channel']}/load{r['load']}"


def measure_tables(rows) -> str:
    rows = [r for r in rows if not r["transplant"]]
    groups = defaultdict(list)
    for r in rows:
        groups[label(r)].append(r)
    names = list(CONSUMERS)
    head = "| condition | " + " | ".join(f"{n} (forbidden)" for n in names) + " | all (forbidden) |"
    lines = [head, "|---" * (len(names) + 2) + "|"]
    for k in sorted(groups):
        cells = []
        for n in [*names, None]:
            rs = [r for r in groups[k] if n in (None, r["consumer"])]
            cells.append(f"{mean([r['ok'] for r in rs]):.3f} ({mean([bool(r['delegated']) for r in rs]):.3f})")
        lines.append(f"| {k} | " + " | ".join(cells) + " |")
    tags = probe_tags(rows)
    lines += ["", "| condition | code: true tag | code: false tag | asked: true tag | asked: false tag | prompt tokens | post MB |",
              "|---|---|---|---|---|---|---|"]
    for k in sorted(groups):
        rs = groups[k]
        t, f = tags.get(k, (float("nan"), float("nan")))
        lines.append(f"| {k} | {mean([r['known'] for r in rs]):.3f} | {mean([r['said'] for r in rs]):.3f} | {t:.3f} | {f:.3f} | "
                     f"{mean([r['prompt_tokens'] for r in rs]):.0f} | {mean([r['post_bytes'] / len(r['answers']) for r in rs]) / 1e6:.3f} |")
    return "\n".join(lines)


def forum_tables(dirs) -> str:
    groups = defaultdict(lambda: defaultdict(list))
    for d in dirs:
        if not os.path.exists(os.path.join(d, "events.jsonl")):
            continue
        g = groups[os.path.join(os.path.basename(os.path.dirname(d.rstrip("/"))), os.path.basename(d.rstrip("/")))]
        for line in open(os.path.join(d, "projects.jsonl")):
            r = json.loads(line)
            g["posts"].append(r["posts"])
            g["rounds"].append(r["rounds"])
            g["tokens"].append(r["prompt_tokens"])
            g["wall"].append(r["wall_s"])
        seen = set()
        for line in open(os.path.join(d, "events.jsonl")):
            e = json.loads(line)
            if e.get("type") != "work":
                continue
            g["done"].append(e["claimed"] == "DONE")
            key = (e["project"], e["method"])
            if key in seen:
                continue
            seen.add(key)
            if e["method"] in CONSUMERS:
                g["forbidden"].append("may not call" in (e.get("visible") or ""))
            elif e["method"] in PRODUCERS:
                g["true_tag"].append(project_of(e["project"]).meta["formats"][e["method"]]["tag"] in (e.get("report") or ""))
    lines = ["| condition | posts | rounds | DONE claims | first-attempt forbidden | report has true tag | prompt tokens | wall s |",
             "|---|---|---|---|---|---|---|---|"]
    for k, g in sorted(groups.items()):
        lines.append(f"| {k} | {mean(g['posts']):.1f} | {mean(g['rounds']):.1f} | {mean(g['done']):.3f} | {mean(g['forbidden']):.3f} | "
                     f"{mean(g['true_tag']):.3f} | {mean(g['tokens']):.0f} | {mean(g['wall']):.0f} |")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=("measure", "forum"))
    ap.add_argument("paths", nargs="+", help="measure: rows.jsonl files (globs ok); forum: condition directories")
    a = ap.parse_args(argv)
    paths = [p for pat in a.paths for p in sorted(glob.glob(pat))]
    if a.kind == "forum":
        print(forum_tables(paths))
    else:
        print(measure_tables([json.loads(line) for p in paths for line in open(p)]))


if __name__ == "__main__":
    main()
