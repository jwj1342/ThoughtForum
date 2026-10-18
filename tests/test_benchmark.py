"""Tasks, workspace, sandbox, evaluation and SecretBench. Standard library only."""
import os
import random
import unittest

from benchmark import secret_tasks as S
from benchmark.evaluate import evaluate, isolated_ok, run
from benchmark.sandbox import run_tests
from benchmark.tasks import _first_test_only, load_classeval, parse_task_spec, private_skeleton, toy_projects
from benchmark.workspace import Workspace, normalize_method

DATA = os.path.join(os.path.dirname(__file__), "..", "data", "ClassEval_data.json")


class TestCode(unittest.TestCase):
    def test_normalize_variants(self):
        classeval = "def f(self, x):\n        if x:\n            return 1\n        return 0"
        decorated = "@staticmethod\n    def g(n):\n        return n + 1"
        fenced = "Sure!\n```python\nclass A:\n    def f(self, x):\n        return x * 2\n```\nDone."
        self.assertTrue(normalize_method(classeval, "f").startswith("def f(self, x):\n    if x:"))
        self.assertTrue(normalize_method(decorated, "g").startswith("def g(n):"))
        self.assertIn("return x * 2", normalize_method(fenced, "f"))
        self.assertIsNone(normalize_method("no code here", "f"))

    def test_first_test_only(self):
        src = "class T(unittest.TestCase):\n    def setUp(self):\n        pass\n\n    def test_a(self):\n        pass\n\n    def test_b(self):\n        pass\n"
        out = _first_test_only(src)
        self.assertIn("setUp", out)
        self.assertIn("test_a", out)
        self.assertNotIn("test_b", out)

    def test_toy_reference_and_stub(self):
        p = toy_projects()[0]
        ws = Workspace(p)
        for s in p.subtasks:
            self.assertTrue(run(p, ws.reference(), s.hidden_test).ok, s.name)
        self.assertFalse(run(p, ws.assemble(), p.subtasks[0].hidden_test).ok)

    def test_isolated_separates_dependency_failure(self):
        p = toy_projects()[0]
        ws = Workspace(p)
        ws.try_set("total", "def total(self):\n    return -1\n", "a")
        ws.try_set("report", normalize_method(p.subtask("report").solution, "report"), "b")
        test = p.subtask("report").hidden_test
        self.assertFalse(run(p, ws.assemble(), test).ok)          # broken dependency drags it down
        self.assertTrue(run(p, ws.isolated("report"), test).ok)   # its own code is fine
        self.assertFalse(run(p, ws.isolated("total"), p.subtask("total").hidden_test).ok)
        res = evaluate(p, ws)
        self.assertTrue(res["methods"]["report"]["iso_ok"])
        self.assertFalse(res["methods"]["report"]["ok"])
        self.assertFalse(res["class_pass"])

    def test_sandbox_timeout(self):
        r = run_tests("", "import unittest\nclass T(unittest.TestCase):\n    def test_x(self):\n        while True:\n"
                          "            pass\n", timeout=2)
        self.assertTrue(r.timeout and not r.ok)

    @unittest.skipUnless(os.path.exists(DATA), "ClassEval data not downloaded")
    def test_classeval_staticmethod_assembly(self):
        p = load_classeval(DATA, ids=[3])[0]  # ArrangementCalculator: two @staticmethods
        ws = Workspace(p)
        for s in p.subtasks:
            self.assertTrue(run(p, ws.reference(), s.hidden_test).ok, s.name)

    @unittest.skipUnless(os.path.exists(DATA), "ClassEval data not downloaded")
    def test_private_spec_hides_other_docstrings(self):
        import ast
        p = parse_task_spec("classeval:0", DATA, 3, os.path.join(os.path.dirname(DATA), "classeval_valid.json"))[0]
        names = p.names
        sk = private_skeleton(p.skeleton, {names[0]})
        compile(sk, "<skeleton>", "exec")
        doc = lambda n: ast.get_docstring(next(f for f in ast.walk(ast.parse(sk))
                                               if isinstance(f, ast.FunctionDef) and f.name == n))
        self.assertTrue(doc(names[0]))
        self.assertTrue(all(doc(n) is None for n in names[1:]))
        self.assertEqual(private_skeleton(p.skeleton, set(names)), p.skeleton)


class TestSecretBench(unittest.TestCase):
    def test_references_pass_and_format_stays_private(self):
        ps = parse_task_spec("secret:6", "", 3, None)
        self.assertEqual(len({p.meta["secret"]["tag"] for p in ps}), 6)
        for p in ps:
            ref = Workspace(p).reference()
            sec = p.meta["secret"]
            for st in p.subtasks:
                self.assertTrue(run(p, ref, st.hidden_test).ok, (p.pid, st.name))
                if st.name != "encode":   # neither the consumer's view nor its visible test leaks the format
                    self.assertNotIn(sec["tag"], private_skeleton(p.skeleton, {st.name}) + st.visible_test)

    def test_offline_items(self):
        p = parse_task_spec("secret:1", "", 3, None)[0]
        for name in S.CONSUMERS:
            self.assertTrue(isolated_ok(p, name, S.use_item(p, name, "")[1])[0])
        self.assertFalse(isolated_ok(p, "decode", "def decode(self, s):\n    return {}\n")[0])
        _, record = S.secret_item(p, "m")
        self.assertTrue(record.startswith(p.meta["secret"]["tag"] + p.meta["secret"]["delim"]))
        rows = S.synthetic_rows(range(1000, 1040), 0, random.Random(0))
        self.assertTrue(5 < sum(r["vague"] for r in rows) < 35)
        for r in rows:
            sec = S.project_of(r["project"]).meta["secret"]
            self.assertEqual(sec["tag"] in r["text"], not r["vague"])
            self.assertIn(sec["tag"], r["context"][1]["content"])   # the author always knows the format

    def test_forum_block_kinds(self):
        self.assertEqual(S.forum_block("none", "x"), "")
        self.assertIn("x", S.forum_block("text", "x"))
        self.assertNotIn("x", S.forum_block("latent", "x"))
        self.assertTrue("x" in S.forum_block("both", "x") and "<<LATENT:0>>" in S.forum_block("both", "x"))
        with self.assertRaises(KeyError):   # an unknown kind must not silently fall back to the text
            S.forum_block("self_step0", "x")

    def test_speech_variants(self):
        p = parse_task_spec("secret:1", "", 3, None)[0]
        true, fake = p.meta["secret"], S.false_secret(p)
        self.assertTrue(all(fake[k] != true[k] for k in ("tag", "delim", "order")))
        for tmpl in S.EXPLICIT:
            honest, lie = S.report(p, "honest", tmpl), S.report(p, "lie", tmpl)
            self.assertIn(true["tag"], honest)
            self.assertTrue(fake["tag"] in lie and true["tag"] not in lie)
        for tmpl in S.VAGUE:
            self.assertNotIn(true["tag"], S.report(p, "omit", tmpl))
        p8 = S.project_of("Secret8_0_2")
        self.assertEqual((len(p8.meta["secret"]["tag"]), p8.pid), (8, "Secret8_0_2"))
        self.assertGreater(p8.meta["bits"], p.meta["bits"])

    def test_measure_on_the_mock(self):
        import json
        import tempfile
        from benchmark import measure
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
            measure.main(["--backend", "mock", "--n", "2", "--out", d])
            with open(os.path.join(d, "summary.json")) as f:
                rows = {(r["speech"], r["channel"], r["transplant"]): r for r in json.load(f)["summary"]}
        self.assertEqual(len(rows), 1 + 3 * 3 + 1)   # none; text/latent/both per speech; one transplant
        self.assertIsNotNone(rows[("lie", "text", False)]["said_in_code"])
        self.assertIsNotNone(rows[("honest", "latent", True)]["other_in_code"])


if __name__ == "__main__":
    unittest.main()
