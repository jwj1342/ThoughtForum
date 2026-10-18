"""Keep only ClassEval projects whose reference solution passes in our sandbox.

Some tasks need packages we do not install, or touch files; dropping them up front keeps
agent failures distinguishable from harness failures.

    python -m benchmark.validate --data data/ClassEval_data.json --out data/classeval_valid.json
"""
from __future__ import annotations

import argparse
import json

from benchmark.evaluate import run
from benchmark.tasks import load_classeval
from benchmark.workspace import Workspace, normalize_method


def check(project, repeat: int = 2) -> tuple[bool, str]:
    """Reference must pass every test `repeat` times (drops time- or randomness-dependent tasks)."""
    for s in project.subtasks:
        if normalize_method(s.solution, s.name) is None:
            return False, f"reference for {s.name} does not parse"
    ref = Workspace(project).reference()
    for s in project.subtasks:
        for kind, test in (("hidden", s.hidden_test), ("visible", s.visible_test)):
            for _ in range(repeat):
                r = run(project, ref, test)
                if not r.ok:
                    return False, f"{s.name} {kind}: {r.brief()[:160]}"
    if project.integration_test:
        for _ in range(repeat):
            r = run(project, ref, project.integration_test)
            if not r.ok:
                return False, f"integration: {r.brief()[:160]}"
    return True, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/ClassEval_data.json")
    ap.add_argument("--out", default="data/classeval_valid.json")
    a = ap.parse_args()
    ok, bad = [], {}
    for p in load_classeval(a.data, min_methods=1):
        try:
            good, why = check(p)
        except Exception as e:  # malformed skeleton etc.
            good, why = False, f"harness error: {type(e).__name__}: {e}"[:160]
        (ok.append(p.pid) if good else bad.__setitem__(p.pid, why))
    with open(a.out, "w") as f:
        json.dump(ok, f, indent=0)
    with open(a.out.replace(".json", "_rejected.json"), "w") as f:
        json.dump(bad, f, indent=1)
    print(f"valid {len(ok)}  rejected {len(bad)}")
    for k, v in bad.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
