"""Command-line entry point. The model is loaded once, then reused across every grid condition.

    python -m forum.run --backend mock --tasks toy
    python -m forum.run --backend hf --tasks classeval:0-9 \
        --grid channel=none,text,latent --grid control=none,shuffle --out runs/e0

The grid is a cartesian product. Conditions that make no sense, such as a control
without a channel, are skipped.
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import itertools
import json
import os
import random
import sys

from model.backends import make_backend
from forum.config import RunConfig
from forum.metrics import flat_row, summarize
from forum.orchestrator import latent_dump, run_project, write_jsonl
from benchmark.tasks import parse_task_spec


def _coerce(field, value: str):
    t = field.type if isinstance(field.type, type) else {"int": int, "float": float, "bool": bool}.get(str(field.type), str)
    if t is bool:
        return value.lower() in ("1", "true", "yes")
    return t(value)


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    fields = {f.name: f for f in dataclasses.fields(RunConfig)}
    for name, f in fields.items():
        ap.add_argument("--" + name.replace("_", "-"), dest=name, default=None)
    ap.add_argument("--grid", action="append", default=[], help="key=v1,v2 (repeatable)")
    a = ap.parse_args(argv)
    base = RunConfig(**{k: _coerce(fields[k], v) for k, v in vars(a).items() if k in fields and v is not None})
    grid = []
    for g in a.grid:
        k, _, vs = g.partition("=")
        grid.append([(k, _coerce(fields[k], v)) for v in vs.split(",")])
    return base, grid


def conditions(base: RunConfig, grid):
    seen = set()
    for combo in itertools.product(*grid) if grid else [()]:
        try:
            cfg = base.replace(**dict(combo))
        except ValueError:
            continue
        if cfg.tag() not in seen:
            seen.add(cfg.tag())
            yield cfg


def run_condition(cfg: RunConfig, backend, projects) -> dict:
    out = os.path.join(cfg.out, cfg.tag())
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "config.json"), "w") as f:
        json.dump(dataclasses.asdict(cfg), f, indent=1)
    bank, records, events, probes = [], [], [], []
    for i, p in enumerate(projects):
        rec, ev, pr = run_project(p, backend, cfg, bank, seed=cfg.seed * 1000 + i)
        records.append(rec); events += ev; probes += pr
        print(f"  [{cfg.tag()}] {p.pid}: method_pass={rec['method_pass']:.2f} class_pass={rec['class_pass']} "
              f"declared={rec['declared_done']} false_done={rec['false_done']}/{rec['claims_done']} ({rec['wall_s']}s)",
              flush=True)
    write_jsonl(os.path.join(out, "projects.jsonl"), records)
    write_jsonl(os.path.join(out, "events.jsonl"), events)
    write_jsonl(os.path.join(out, "probes.jsonl"), probes)
    if cfg.save_latents and cfg.channel == "latent" and cfg.backend == "hf":
        import torch
        torch.save(latent_dump(bank, projects), os.path.join(out, "latents.pt"))
    s = summarize(cfg, records, events, probes)
    with open(os.path.join(out, "summary.json"), "w") as f:
        json.dump(s, f, indent=1)
    return s


def main(argv=None):
    base, grid = parse_args(argv)
    base.validate()
    random.seed(base.seed)
    projects = parse_task_spec(base.tasks, base.data_path, base.min_methods, base.valid_ids)
    if not projects:
        sys.exit("no projects selected")
    conds = list(conditions(base, grid))
    print(f"{len(projects)} projects x {len(conds)} conditions -> {base.out}", flush=True)
    backend = make_backend(base)
    rows = []
    for cfg in conds:
        s = run_condition(cfg, backend, projects)
        rows.append(flat_row(s))
        print(json.dumps({k: s[k] for k in ("condition", "method_pass", "class_pass", "false_declaration")}), flush=True)
    os.makedirs(base.out, exist_ok=True)
    with open(os.path.join(base.out, "summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print("wrote", os.path.join(base.out, "summary.csv"))


if __name__ == "__main__":
    main()
