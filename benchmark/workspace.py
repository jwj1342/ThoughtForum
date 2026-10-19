"""The shared repository: the only ground truth in a zero-trust team.

Agents may only change the method they currently own. Each write bumps that method's
version, so forum posts written against an older version can be detected as stale.
"""
from __future__ import annotations

import ast
import re
import textwrap

from benchmark.tasks import Project

_FENCE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.S)


def _candidates(block: str):
    lines = block.strip("\n").splitlines()
    rest = [l for l in lines[1:] if l.strip()]
    if rest:
        # ClassEval style: the first line lost its indentation, the rest kept class-member indentation.
        ind = lambda l: len(l) - len(l.lstrip())
        heads = [ind(l) for l in rest if l.lstrip().startswith(("def ", "async def ", "@"))]
        base = min(heads) if heads else max(min(map(ind, rest)) - 4, 0)
        yield textwrap.dedent("\n".join([" " * base + lines[0].lstrip()] + lines[1:]))
    yield textwrap.dedent(block)


def normalize_method(text: str, name: str) -> str | None:
    """Extract `def name(...)` from model output; return it dedented to column 0, without decorators."""
    blocks = _FENCE.findall(text) or [text]
    blocks = sorted(blocks, key=lambda b: f"def {name}(" not in b)
    for block in blocks:
        for src in _candidates(block):
            try:
                tree = ast.parse(src)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                    seg = "\n".join(src.splitlines()[node.lineno - 1:node.end_lineno])
                    return textwrap.dedent(seg).rstrip() + "\n"
    return None


class Workspace:
    def __init__(self, project: Project):
        self.p = project
        self.code: dict[str, str] = {}
        self.author: dict[str, str] = {}
        self.version: dict[str, int] = {s.name: 0 for s in project.subtasks}
        self._ranges = self._method_ranges()

    def _method_ranges(self):
        tree = ast.parse(self.p.skeleton)
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == self.p.class_name)
        names = set(self.p.names)
        return {n.name: (n.lineno - 1, n.end_lineno, n.col_offset)
                for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names}

    def _render(self, code: dict[str, str]) -> str:
        lines = self.p.skeleton.splitlines()
        for name, (start, end, col) in sorted(self._ranges.items(), key=lambda kv: -kv[1][0]):
            if name in code:
                lines[start:end] = textwrap.indent(code[name], " " * col).rstrip("\n").splitlines()
        return "\n".join(lines) + "\n"

    def assemble(self, override: dict[str, str] | None = None) -> str:
        return self._render({**self.code, **(override or {})})

    def try_set(self, name: str, func_src: str, author: str) -> bool:
        """Write a method if the assembled module still parses; returns success."""
        try:
            ast.parse(self.assemble({name: func_src}))
        except SyntaxError:
            return False
        self.code[name] = func_src
        self.author[name] = author
        self.version[name] += 1
        return True

    def _refs(self) -> dict[str, str]:
        if not hasattr(self, "_ref_cache"):
            refs = {s.name: normalize_method(s.solution, s.name) for s in self.p.subtasks}
            self._ref_cache = {k: v for k, v in refs.items() if v}
        return self._ref_cache

    def reference(self) -> str:
        return self._render(self._refs())

    def isolated(self, name: str) -> str:
        """`name` as the team wrote it, every other method at its reference solution.

        A method's hidden test then measures only its own code, not the brokenness of the methods it
        calls. This separates being misled from mere dependency failure. A task that lists the methods
        it may call (`Subtask.calls`, as SecretBench does) gets stubs that raise for all the others, so it
        cannot pass by delegating to correct reference code it was never meant to call.
        """
        st = self.p.subtask(name)
        allowed = set(self._refs()) if st.calls is None else set(st.calls)
        stub = lambda k: f"def {k}(self, *args, **kwargs):\n    raise NotImplementedError({k!r} + ' is not available here')\n"
        mix = {k: v if k in allowed else stub(k) for k, v in self._refs().items() if k != name}
        if name in self.code:
            mix[name] = self.code[name]
        return self._render(mix)
