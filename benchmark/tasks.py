"""Projects that several agents build together.

A project is one Python class. Each method is a subtask that a single agent implements.
Every method gets two tests: a *visible* one (its first test case, which agents may run)
and a *hidden* one (the method's full test class, used only for evaluation).
Test classes that belong to no single method become the project's integration test.
"""
from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field


@dataclass
class Subtask:
    name: str
    doc: str               # signature + docstring, as shown to agents
    deps: list[str]        # other methods of the same class it depends on (and whose posts it reads)
    visible_test: str      # test class reduced to its first test case
    hidden_test: str       # full test class for this method
    solution: str = ""     # reference implementation (never shown to agents)
    calls: list[str] | None = None   # the methods it may call; None: its deps. Others are stubs when it is tested alone

    def callable(self) -> list[str]:
        return self.deps if self.calls is None else self.calls


@dataclass
class Project:
    pid: str
    class_name: str
    skeleton: str          # importable module: imports + class with docstring-only method stubs
    subtasks: list[Subtask]
    test_prelude: str = "import unittest\n"
    integration_test: str = ""
    meta: dict = field(default_factory=dict)

    def subtask(self, name: str) -> Subtask:
        return next(s for s in self.subtasks if s.name == name)

    @property
    def names(self) -> list[str]:
        return [s.name for s in self.subtasks]


def _first_test_only(test_class_src: str) -> str:
    """Keep setUp/helpers and the first `test*` method of a single test class."""
    tree = ast.parse(test_class_src)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    tests = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test")]
    if len(tests) <= 1:
        return test_class_src
    lines = test_class_src.splitlines()
    drop = set()
    for n in tests[1:]:
        start = (n.decorator_list[0].lineno if n.decorator_list else n.lineno) - 1
        drop.update(range(start, n.end_lineno))
    return "\n".join(l for i, l in enumerate(lines) if i not in drop) + "\n"


def _split_test_module(test_src: str):
    """Return (prelude, {class_name: source}) for a unittest module."""
    tree = ast.parse(test_src)
    lines = test_src.splitlines()
    classes, first = {}, None
    for n in tree.body:
        if isinstance(n, ast.ClassDef):
            first = n.lineno if first is None else first
            classes[n.name] = "\n".join(lines[n.lineno - 1 - len(n.decorator_list):n.end_lineno]) + "\n"
    prelude = "\n".join(lines[: (first or 1) - 1]).strip() + "\n"
    return prelude, classes


def load_classeval(path: str, ids: list[int] | None = None, min_methods: int = 3,
                   only_ids: set[str] | None = None) -> list[Project]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    out = []
    for i, x in enumerate(data):
        if ids is not None and i not in ids:
            continue
        if only_ids is not None and x["task_id"] not in only_ids:
            continue
        methods = x["methods_info"]
        if len(methods) < min_methods:
            continue
        prelude, classes = _split_test_module(x["test"])
        method_classes = {m["test_class"] for m in methods}
        subtasks = []
        for m in methods:
            hidden = classes.get(m["test_class"]) or m["test_code"]
            subtasks.append(Subtask(
                name=m["method_name"],
                doc=m["method_description"],
                deps=[d for d in m["dependencies"].get("method_dependencies", []) if d != m["method_name"]],
                visible_test=_first_test_only(hidden),
                hidden_test=hidden,
                solution=m["solution_code"],
            ))
        names = {s.name for s in subtasks}
        for s in subtasks:
            s.deps = [d for d in s.deps if d in names]
        integ = "".join(src for name, src in classes.items() if name not in method_classes)
        out.append(Project(pid=x["task_id"], class_name=x["class_name"], skeleton=x["skeleton"],
                           subtasks=subtasks, test_prelude=prelude or "import unittest\n",
                           integration_test=integ,
                           meta={"description": x["class_description"].strip()}))
    return out


_TOY_SKELETON = '''class Inventory:
    """A tiny stock ledger shared by a warehouse team."""

    def __init__(self):
        self.items = {}

    def add(self, name, qty):
        """
        Add qty units of name. qty must be a positive int, otherwise raise ValueError.
        :return: int, the new quantity of name
        """

    def remove(self, name, qty):
        """
        Remove qty units of name if enough are in stock; drop the key when it reaches 0.
        :return: bool, True if removed, False if not enough stock
        """

    def total(self):
        """
        :return: int, total units over all items
        """

    def report(self):
        """
        :return: str, formatted as "<n> items, <total> units" (uses self.total())
        """
'''

_TOY_SOLUTIONS = {
    "add": "def add(self, name, qty):\n    if not isinstance(qty, int) or qty <= 0:\n        raise ValueError('qty')\n"
           "    self.items[name] = self.items.get(name, 0) + qty\n    return self.items[name]\n",
    "remove": "def remove(self, name, qty):\n    if self.items.get(name, 0) < qty:\n        return False\n"
              "    self.items[name] -= qty\n    if self.items[name] == 0:\n        del self.items[name]\n    return True\n",
    "total": "def total(self):\n    return sum(self.items.values())\n",
    "report": "def report(self):\n    return f'{len(self.items)} items, {self.total()} units'\n",
}

_TOY_TESTS = {
    "add": '''class InventoryTestAdd(unittest.TestCase):
    def test_add_1(self):
        self.assertEqual(Inventory().add('a', 2), 2)

    def test_add_2(self):
        inv = Inventory(); inv.add('a', 2)
        self.assertEqual(inv.add('a', 3), 5)

    def test_add_3(self):
        with self.assertRaises(ValueError):
            Inventory().add('a', 0)
''',
    "remove": '''class InventoryTestRemove(unittest.TestCase):
    def test_remove_1(self):
        inv = Inventory(); inv.items = {'a': 3}
        self.assertTrue(inv.remove('a', 2))

    def test_remove_2(self):
        inv = Inventory(); inv.items = {'a': 1}
        self.assertFalse(inv.remove('a', 2))

    def test_remove_3(self):
        inv = Inventory(); inv.items = {'a': 2}
        inv.remove('a', 2)
        self.assertNotIn('a', inv.items)
''',
    "total": '''class InventoryTestTotal(unittest.TestCase):
    def test_total_1(self):
        inv = Inventory(); inv.items = {'a': 2, 'b': 3}
        self.assertEqual(inv.total(), 5)

    def test_total_2(self):
        self.assertEqual(Inventory().total(), 0)
''',
    "report": '''class InventoryTestReport(unittest.TestCase):
    def test_report_1(self):
        inv = Inventory(); inv.items = {'a': 2, 'b': 3}
        self.assertEqual(inv.report(), '2 items, 5 units')

    def test_report_2(self):
        self.assertEqual(Inventory().report(), '0 items, 0 units')
''',
}

_TOY_INTEGRATION = '''class InventoryTest(unittest.TestCase):
    def test_flow(self):
        inv = Inventory()
        inv.add('a', 4); inv.add('b', 1)
        self.assertTrue(inv.remove('a', 4))
        self.assertEqual(inv.report(), '1 items, 1 units')
'''


def toy_projects() -> list[Project]:
    """Built-in project for offline smoke tests (no download needed)."""
    tree = ast.parse(_TOY_SKELETON)
    lines = _TOY_SKELETON.splitlines()
    cls = tree.body[0]
    docs = {n.name: "\n".join(lines[n.lineno - 1:n.end_lineno]).strip()
            for n in cls.body if isinstance(n, ast.FunctionDef) and n.name != "__init__"}
    deps = {"report": ["total"]}
    subtasks = [Subtask(name=n, doc=docs[n], deps=deps.get(n, []), visible_test=_first_test_only(_TOY_TESTS[n]),
                        hidden_test=_TOY_TESTS[n], solution=_TOY_SOLUTIONS[n]) for n in docs]
    return [Project(pid="toy_inventory", class_name="Inventory", skeleton=_TOY_SKELETON, subtasks=subtasks,
                    integration_test=_TOY_INTEGRATION, meta={"description": "toy"})]


def private_skeleton(skeleton: str, keep=()) -> str:
    """The skeleton as one agent sees it under spec=private.

    Methods in `keep` (and `__init__`, and the class docstring) keep their docstrings; every other
    method is cut down to its signature, so what it returns has to be learned from teammates.
    """
    try:
        tree = ast.parse(skeleton)
    except SyntaxError:
        return skeleton
    cuts = []
    for cls in tree.body:
        if not isinstance(cls, ast.ClassDef):
            continue
        for fn in cls.body:
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) or fn.name in keep or fn.name == "__init__":
                continue
            doc = fn.body[0] if fn.body else None
            if isinstance(doc, ast.Expr) and isinstance(doc.value, ast.Constant) and isinstance(doc.value.value, str):
                cuts.append((doc.lineno, doc.end_lineno, doc.col_offset))
    lines = skeleton.splitlines()
    for a, b, col in sorted(cuts, reverse=True):
        lines[a - 1:b] = [" " * col + "..."]
    return "\n".join(lines)


def parse_task_spec(spec: str, data_path: str, min_methods: int, valid_ids_path: str | None = None) -> list[Project]:
    """'toy' | 'classeval:all' | 'classeval:0-9' | 'classeval:3,7,12' | 'classeval:@ids.json' | 'secret:40'.

    `@ids.json` is a JSON list of project ids, e.g. the held-out projects a trained head never saw.

    Indices count over the projects that survive filtering (min_methods, validity list).
    """
    if spec == "toy":
        return toy_projects()
    kind, _, sel = spec.partition(":")
    if kind == "secret":   # 'secret:40' (projects 0-39) or 'secret:40-59'
        from benchmark.secretbench import make_project
        a, _, b = sel.partition("-")
        ids = range(int(a), int(b) + 1) if b else range(int(a or 40))
        return [make_project(i) for i in ids]
    if kind != "classeval":
        raise ValueError(f"unknown task spec {spec!r}")
    only = None
    if valid_ids_path:
        try:
            with open(valid_ids_path) as f:
                only = set(json.load(f))
        except FileNotFoundError:
            only = None
    projects = load_classeval(data_path, min_methods=min_methods, only_ids=only)
    if sel in ("", "all"):
        return projects
    if sel.startswith("@"):
        with open(sel[1:]) as f:
            keep = set(json.load(f))
        return [p for p in projects if p.pid in keep]
    idx: list[int] = []
    for part in sel.split(","):
        if "-" in part:
            a, b = part.split("-")
            idx.extend(range(int(a), int(b) + 1))
        else:
            idx.append(int(part))
    return [projects[i] for i in idx if i < len(projects)]
