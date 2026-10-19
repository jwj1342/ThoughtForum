"""Tasks, workspace, sandbox, evaluation and SecretBench. Standard library only."""
import os
import random
import unittest

from benchmark import secret_tasks as S
from benchmark.evaluate import evaluate, isolated_ok, run
from benchmark.sandbox import run_tests
from benchmark.secretbench import CONSUMERS, PRODUCERS, make_project
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
        self.assertEqual(ws.forbidden_calls("report", ws.code["report"]), [])   # without `calls`, it may call any
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
    def test_references_pass_and_formats_stay_private(self):
        ps = parse_task_spec("secret:40", "", 3, None)
        self.assertEqual(len({p.class_name for p in ps}), 40)
        for p in ps[:12]:
            ref = Workspace(p).reference()
            tags = [f["tag"] for f in p.meta["formats"].values()]
            for st in p.subtasks:
                self.assertTrue(run(p, ref, st.hidden_test).ok, (p.pid, st.name))
                if st.name in CONSUMERS:   # neither a consumer's view nor its visible test leaks a format
                    view = private_skeleton(p.skeleton, {st.name}) + st.visible_test
                    self.assertFalse(any(t in view for t in tags), (p.pid, st.name))

    def test_hidden_tests_need_the_formats(self):
        for p in (make_project(5), make_project(6)):
            for name, deps in CONSUMERS.items():
                d = deps[-1]
                sol = normalize_method(p.subtask(name).solution, name)
                wrong = sol.replace(repr(p.meta["formats"][d]["delim"]), repr(S.false_format(p, d)["delim"]))
                self.assertTrue(isolated_ok(p, name, f"```python\n{sol}```")[0], name)
                self.assertFalse(isolated_ok(p, name, f"```python\n{wrong}```")[0], name)
        # nor can a consumer pass by delegating to the (reference) methods it may not call
        p = make_project(5)
        f = p.meta["fields"]
        cheats = {"get_field": "def get_field(self, s, name):\n    return self.decode(s)[name]\n",
                  "migrate": "def migrate(self, s):\n    return self.export(**self.decode(s))\n",
                  "is_record": "def is_record(self, s):\n    try:\n        self.decode(s)\n        return True\n"
                               "    except ValueError:\n        return False\n"}
        ws = Workspace(p)
        for name, code in cheats.items():
            self.assertFalse(isolated_ok(p, name, f"```python\n{code}```")[0], name)
            self.assertTrue(ws.forbidden_calls(name, code), name)   # and the harness says why
        self.assertEqual(ws.forbidden_calls("migrate", cheats["migrate"]), ["decode", "export"])
        for name in CONSUMERS:   # the references do their own work
            self.assertEqual(ws.forbidden_calls(name, normalize_method(p.subtask(name).solution, name)), [], name)

    def test_reports_and_questions(self):
        p = make_project(7)
        for d in PRODUCERS:
            true, fake = p.meta["formats"][d], S.false_format(p, d)
            self.assertTrue(all(fake[k] != true[k] for k in ("tag", "delim", "order")))
            for k in range(3):
                self.assertIn(true["tag"], S.report(p, d, "honest", k))
                lie = S.report(p, d, "lie", k)
                self.assertTrue(fake["tag"] in lie and true["tag"] not in lie)
                self.assertNotIn(true["tag"], S.report(p, d, "omit", k))
            ctx = S.producer_context(p, d, "x")
            self.assertIn(true["tag"], ctx[1]["content"] + ctx[2]["content"])   # the author always knows its format
            _, answer = S.question(p, d, "m")
            self.assertTrue(answer.startswith(true["tag"] + true["delim"]))
        p8 = S.project_of("Secret8_0_2")
        self.assertEqual((len(p8.meta["formats"]["encode"]["tag"]), p8.pid), (8, "Secret8_0_2"))
        self.assertGreater(p8.meta["bits"]["encode"], p.meta["bits"]["encode"])

    def test_forum_block_kinds(self):
        from forum import prompts as P
        posts = [("[post 0] from agent1 on `encode`", "x")]
        self.assertEqual(S.forum_block("none", posts), "")
        self.assertIn("x", S.forum_block("session", posts))
        self.assertTrue("x" not in S.forum_block("latent", posts) and "<<LATENT:0>>" in S.forum_block("latent", posts))
        self.assertIn(P.KV_NOTE, S.forum_block("stream", posts))
        with self.assertRaises(KeyError):   # an unknown kind must not silently fall back to the text
            S.forum_block("self_step0", posts)

    def _measure(self, *args):
        import contextlib
        import io
        import json
        import tempfile
        from benchmark import measure
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
            measure.main(["--backend", "mock", "--out", d, *args])
            with open(os.path.join(d, "summary.json")) as f:
                summary = {(r["speech"], r["channel"], r["transplant"]): r for r in json.load(f)["summary"]}
            with open(os.path.join(d, "rows.jsonl")) as f:
                return summary, [json.loads(line) for line in f]

    def test_measure_on_the_mock(self):
        summary, rows = self._measure("--n", "3", "--channel", "none,full_spec,text,artifact,session,latent,stream",
                                      "--transplant")
        self.assertEqual(len(summary), 3 + 3 * 4 + 2)   # none, full_spec, artifact; 4 channels per speech; 2 transplants
        self.assertEqual(len(rows), len(summary) * 3 * len(CONSUMERS))
        self.assertIsNotNone(summary[("lie", "text", False)]["said"])
        self.assertIsNotNone(summary[("honest", "stream", True)]["other"])
        self.assertTrue(all(set(r["answers"]) == {"encode", "export"} for r in rows if r["consumer"] == "migrate"))
        self.assertTrue(all(r["post_bytes"] > 0 for r in rows if r["channel"] == "session"))
        self.assertTrue(all(isinstance(r["delegated"], list) for r in rows))

    def test_measure_load(self):
        from benchmark import measure
        from model.backends.mock import MockBackend
        _, rows = self._measure("--n", "4", "--load", "3", "--channel", "text,stream", "--speech", "lie")
        self.assertEqual({r["load"] for r in rows}, {3})
        posts = [measure.Post(make_project(0), "encode", "honest", 0, "session", None),
                 measure.Post(make_project(1), "export", "honest", 0, "session", None)]
        _, block, _ = measure.reader(MockBackend(), "session", posts, qualified=True)
        self.assertIn(f"[post 1] from agent2 on `{make_project(1).class_name}.export`", block)
        self.assertIn("[assistant]", block)


if __name__ == "__main__":
    unittest.main()
