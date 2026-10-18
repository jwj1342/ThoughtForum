"""Run unittest code against an assembled module in a throwaway directory.

This is the trusted CI of the zero-trust setting. It isolates by process only, with a
timeout, rlimits, a temp cwd, and `python -I`; that is enough for ClassEval-style tasks.
Use Apptainer before running untrusted repo-level code.
"""
from __future__ import annotations

import json
import os
import resource
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict

_MARK = "__LF_RESULT__"
_RUNNER = f'''

if __name__ == "__main__":
    import json as _j, sys as _s, unittest as _u
    _suite = _u.defaultTestLoader.loadTestsFromModule(_s.modules["__main__"])
    _res = _u.TestResult()
    _suite.run(_res)
    _bad = _res.failures + _res.errors
    print("{_MARK}" + _j.dumps({{"total": _res.testsRun, "failures": len(_res.failures),
        "errors": len(_res.errors), "failed": [t.id().split(".")[-1] for t, _ in _bad],
        "first_error": _bad[0][1][-600:] if _bad else ""}}))
'''


@dataclass
class TestResult:
    total: int = 0
    failures: int = 0
    errors: int = 0
    failed: list | None = None
    first_error: str = ""
    timeout: bool = False

    @property
    def passed(self) -> int:
        return self.total - self.failures - self.errors

    @property
    def ok(self) -> bool:
        return self.total > 0 and self.failures == 0 and self.errors == 0 and not self.timeout

    def brief(self) -> str:
        if self.timeout:
            return "FAIL (timeout)"
        if self.total == 0:
            return "FAIL (tests could not run: " + self.first_error.strip().splitlines()[-1][:200] + ")" \
                if self.first_error.strip() else "FAIL (no tests ran)"
        head = f"{'PASS' if self.ok else 'FAIL'} ({self.passed}/{self.total})"
        return head if self.ok else head + ": " + self.first_error.strip()[-300:]

    def to_dict(self):
        d = asdict(self)
        d["ok"] = self.ok
        return d


def _limits(cpu_s: int):
    def fn():
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s + 1))
        resource.setrlimit(resource.RLIMIT_AS, (2 << 30, 2 << 30))
    return fn


def run_tests(module_src: str, test_src: str, timeout: int = 10) -> TestResult:
    root = os.environ.get("SLURM_TMPDIR") or None
    with tempfile.TemporaryDirectory(dir=root, prefix="lf_") as d:
        path = os.path.join(d, "case.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(module_src + "\n\n" + test_src + _RUNNER)
        try:
            p = subprocess.run([sys.executable, "-I", path], cwd=d, capture_output=True, text=True,
                               timeout=timeout, preexec_fn=_limits(timeout),
                               env={"PATH": os.environ.get("PATH", ""), "HOME": d})
        except subprocess.TimeoutExpired:
            return TestResult(timeout=True, first_error="timeout")
        for line in reversed(p.stdout.splitlines()):
            if line.startswith(_MARK):
                return TestResult(**json.loads(line[len(_MARK):]))
        return TestResult(first_error=(p.stderr or p.stdout)[-600:])
