"""Execution-based evaluation: hidden tests are the only ground truth, and agents never see them.

Two readings of a method's hidden test:
- on the team's assembled module (does the class work as built?), and
- isolated: every other method at its reference solution, so the test measures only this
  method's own code and not the brokenness of methods it calls.
"""
from __future__ import annotations

from benchmark.sandbox import TestResult, run_tests
from benchmark.workspace import Workspace, normalize_method


def run(project, module_src: str, test_src: str) -> TestResult:
    return run_tests(module_src, project.test_prelude + "\n" + test_src)


def hidden(project, ws: Workspace, name: str) -> tuple[TestResult, TestResult]:
    """(hidden test on the team's module, isolated hidden test) for one method."""
    test = project.subtask(name).hidden_test
    return run(project, ws.assemble(), test), run(project, ws.isolated(name), test)


def evaluate(project, ws: Workspace) -> dict:
    per = {}
    for s in project.subtasks:
        r, iso = hidden(project, ws, s.name)
        per[s.name] = {"ok": r.ok, "iso_ok": iso.ok, "passed": r.passed, "total": r.total,
                       "author": ws.author.get(s.name), "deps": s.deps, "code": ws.code.get(s.name)}
    dep = [s for s in project.subtasks if s.deps]
    integ = run(project, ws.assemble(), project.integration_test).ok if project.integration_test else None
    return {"methods": per, "integration_ok": integ,
            "method_pass": sum(v["ok"] for v in per.values()) / len(per),
            "method_pass_iso": sum(v["iso_ok"] for v in per.values()) / len(per),
            # methods that call teammates' methods: where knowing their interfaces matters
            "dep_pass_iso": (sum(per[s.name]["iso_ok"] for s in dep) / len(dep)) if dep else None,
            "n_dep": len(dep),
            "class_pass": all(v["ok"] for v in per.values()) and integ is not False}


def isolated_ok(project, name: str, reply: str) -> tuple[bool, str | None]:
    """Score one model reply for method `name` in isolation, as `method_pass_iso` does in the forum."""
    code = normalize_method(reply, name)
    ws = Workspace(project)
    ok = bool(code) and ws.try_set(name, code, "reader") and \
        run(project, ws.isolated(name), project.subtask(name).hidden_test).ok
    return ok, code
