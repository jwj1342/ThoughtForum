"""Fast checks of the harness, using the mock backend. Run: python -m unittest discover -s tests"""
import os
import ast
import tempfile
import unittest

from forum.agent import force_done, parse_status, pick_option
from model.backends.mock import MockBackend
from forum.config import RunConfig
from forum.posts import Forum, Post
from forum.orchestrator import run_project
from forum.run import conditions, run_condition
from benchmark.sandbox import run_tests
from benchmark.tasks import _first_test_only, load_classeval, parse_task_spec, toy_projects
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
            self.assertTrue(run_tests(ws.reference(), p.test_prelude + s.hidden_test).ok, s.name)
        self.assertFalse(run_tests(ws.assemble(), p.test_prelude + p.subtasks[0].hidden_test).ok)

    def test_isolated_separates_dependency_failure(self):
        p = toy_projects()[0]
        ws = Workspace(p)
        ws.try_set("total", "def total(self):\n    return -1\n", "a")
        ws.try_set("report", normalize_method(p.subtask("report").solution, "report"), "b")
        hidden = p.test_prelude + p.subtask("report").hidden_test
        self.assertFalse(run_tests(ws.assemble(), hidden).ok)          # broken dependency drags it down
        self.assertTrue(run_tests(ws.isolated("report"), hidden).ok)   # its own code is fine
        self.assertFalse(run_tests(ws.isolated("total"), p.test_prelude + p.subtask("total").hidden_test).ok)

    @unittest.skipUnless(os.path.exists(DATA), "ClassEval data not downloaded")
    def test_classeval_staticmethod_assembly(self):
        p = load_classeval(DATA, ids=[3])[0]  # ArrangementCalculator: two @staticmethods
        ws = Workspace(p)
        for s in p.subtasks:
            self.assertTrue(run_tests(ws.reference(), p.test_prelude + s.hidden_test).ok, s.name)


class TestProtocol(unittest.TestCase):
    def test_status_helpers(self):
        self.assertEqual(parse_status("STATUS: partial\nmore"), "PARTIAL")
        self.assertEqual(parse_status("nothing"), "UNKNOWN")
        self.assertEqual(parse_status(force_done("STATUS: BLOCKED\nx")), "DONE")
        self.assertEqual(pick_option("I'll take `select_all`.", ["select", "select_all"]), "select_all")

    def test_flat_structure_hides_anchor(self):
        cfg = RunConfig(channel="text", structure="flat").validate()
        f = Forum(cfg, MockBackend(), [], 0)
        f.write(Post(0, "p", "agent1", 0, "add", "DONE", "STATUS: DONE\nadds", version=1))
        block, _, log = f.render(f.select("agent0", "total", []), {"add": 1})
        self.assertNotIn("`add`", block)
        self.assertEqual(log[0]["anchor"], "add")

    def test_attested_reopens_false_done(self):
        cfg = RunConfig(trust="attested").validate()
        f = Forum(cfg, MockBackend(), [], 0)
        f.write(Post(0, "p", "agent1", 0, "add", "DONE", "STATUS: DONE", verified={"ok": False}))
        self.assertFalse(f.closed("add"))
        blind = Forum(RunConfig().validate(), MockBackend(), [], 0)
        blind.write(Post(0, "p", "agent1", 0, "add", "DONE", "STATUS: DONE", verified={"ok": False}))
        self.assertTrue(blind.closed("add"))

    def test_shuffle_swaps_payload(self):
        cfg = RunConfig(channel="text", control="shuffle").validate()
        bank = [Post(0, "other", "agent9", 0, "x", "DONE", "foreign message")]
        f = Forum(cfg, MockBackend(), bank, 0)
        f.write(Post(0, "p", "agent1", 0, "add", "DONE", "own message"))
        block, _, _ = f.render(f.select("agent0", "add", []), {})
        self.assertIn("foreign message", block)


class TestPipeline(unittest.TestCase):
    def test_end_to_end_mock(self):
        p = toy_projects()[0]
        for channel in ("none", "text", "latent"):
            cfg = RunConfig(channel=channel, rounds=6, overclaim_frac=0.34).validate()
            rec, events, probes = run_project(p, MockBackend(p_correct=0.5), cfg, [], seed=1)
            self.assertIn("class_pass", rec)
            self.assertTrue(any(e["type"] == "work" for e in events))
            if channel == "latent":  # mock latents are lossless, so probes must be perfect
                self.assertTrue(all(r["self"]["correct"]["anchor"] for r in probes))

    def test_crosscheck_runs_peer_tests(self):
        p = toy_projects()[0]
        cfg = RunConfig(channel="text", trust="crosscheck", rounds=6).validate()
        rec, events, _ = run_project(p, MockBackend(p_correct=0.5), cfg, [], seed=2)
        peers = [e for e in events if e["type"] == "peer"]
        self.assertTrue(peers)
        self.assertTrue(all(e["tests_valid_on_reference"] for e in peers))  # mock peers copy the hidden tests
        self.assertEqual(rec.get("peer_checks", 0), len(peers))

    def test_deceive_marks_only_failed_done(self):
        p = toy_projects()[0]
        cfg = RunConfig(channel="latent", overclaim_frac=0.34, overclaim_mode="deceive", rounds=8).validate()
        rec, events, _ = run_project(p, MockBackend(p_correct=0.0), cfg, [], seed=3)
        work = [e for e in events if e["type"] == "work"]
        lies = [e for e in work if e["falsified"]]
        self.assertTrue(lies)
        self.assertTrue(all(e["overclaimer"] and e["claimed"] == "DONE" and not e["visible_ok"] for e in lies))
        self.assertFalse(any(e["falsified"] for e in work if not e["overclaimer"]))

    def test_private_spec_hides_other_docstrings(self):
        from benchmark.tasks import private_skeleton
        p = parse_task_spec("classeval:0", "data/ClassEval_data.json", 3, "data/classeval_valid.json")[0]
        names = p.names
        sk = private_skeleton(p.skeleton, {names[0]})
        compile(sk, "<skeleton>", "exec")
        doc = lambda n: ast.get_docstring(next(f for f in ast.walk(ast.parse(sk))
                                               if isinstance(f, ast.FunctionDef) and f.name == n))
        self.assertTrue(doc(names[0]))
        self.assertTrue(all(doc(n) is None for n in names[1:]))
        self.assertEqual(private_skeleton(p.skeleton, set(names)), p.skeleton)
        cfg = RunConfig(channel="text", spec="private", rounds=4).validate()
        rec, _, _ = run_project(toy_projects()[0], MockBackend(p_correct=0.5), cfg, [], seed=4)
        self.assertIn("dep_pass_iso", rec)

    def test_secretbench_references_and_privacy(self):
        from benchmark.tasks import private_skeleton
        ps = parse_task_spec("secret:6", "", 3, None)
        self.assertEqual(len({p.meta["secret"]["tag"] for p in ps}), 6)
        for p in ps:
            ws = Workspace(p)
            ref = ws.reference()
            sec = p.meta["secret"]
            for st in p.subtasks:
                self.assertTrue(run_tests(ref, p.test_prelude + "\n" + st.hidden_test).ok, (p.pid, st.name))
                if st.name != "encode":   # neither the consumer's view nor its visible test leaks the format
                    view = private_skeleton(p.skeleton, {st.name}) + st.visible_test
                    self.assertNotIn(sec["tag"], view)
        rec, _, _ = run_project(ps[0], MockBackend(p_correct=1.0), RunConfig(spec="private", rounds=4).validate(), [], seed=5)
        self.assertEqual(rec["method_pass"], 1.0)

    def test_deps_wait_reads_producer_first(self):
        p = parse_task_spec("secret:1", "", 3, None)[0]
        cfg = RunConfig(channel="text", spec="private", deps_wait=True, rounds=4).validate()
        _, events, _ = run_project(p, MockBackend(p_correct=1.0), cfg, [], seed=6)
        work = [e for e in events if e["type"] == "work" and e["method"] != "encode"]
        self.assertTrue(work and all(any(r["anchor"] == "encode" for r in e["read"]) for e in work))
        # a producer that keeps failing: teammates wait while it is owned, then take it over
        _, events, _ = run_project(p, MockBackend(p_correct=0.0), cfg, [], seed=6)
        self.assertTrue(any(e["type"] == "wait" for e in events))
        self.assertGreater(len({e["agent"] for e in events if e["type"] == "work" and e["method"] == "encode"}), 1)

    def test_memory_and_text_artifact(self):
        p = parse_task_spec("secret:1", "", 3, None)[0]

        class Rec(MockBackend):
            def chat(self, messages, latents=(), **kw):
                if kw.get("purpose") == "implement":
                    self.seen.append(messages[-1]["content"])
                return super().chat(messages, latents, **kw)

        for memory in (False, True):
            b = Rec(p_correct=1.0)
            b.seen = []
            cfg = RunConfig(channel="none", spec="private", memory=memory, n_agents=1, rounds=4).validate()
            run_project(p, b, cfg, [], seed=0)
            consumer = [t for t in b.seen if "implement the method `encode`" not in t]
            self.assertTrue(consumer)
            self.assertEqual(all("Your own earlier code for `encode`" in t for t in consumer), memory)
        cfg = RunConfig(channel="text", source="artifact", spec="private", n_agents=1, rounds=1).validate()
        self.assertIn("-artifact", cfg.tag())
        _, events, _ = run_project(p, MockBackend(p_correct=1.0), cfg, [], seed=0)
        rep = next(e["report"] for e in events if e["type"] == "work")
        self.assertTrue(rep.startswith("STATUS: DONE") and "def encode(" in rep)

    def test_secret_tasks_match_forum_prompts(self):
        import random
        from benchmark import secret_tasks as S
        p = parse_task_spec("secret:1", "", 3, None)[0]

        class Rec(MockBackend):
            def chat(self, messages, latents=(), **kw):
                if kw.get("purpose") == "implement":
                    self.seen.append(messages[-1]["content"])
                return super().chat(messages, latents, **kw)

        b = Rec(p_correct=1.0)
        b.seen = []
        cfg = RunConfig(channel="text", spec="private", n_agents=3, rounds=2, probe=False).validate()
        _, events, _ = run_project(p, b, cfg, [], seed=0)
        enc_prompt = next(t for t in b.seen if "implement the method `encode`" in t)
        self.assertEqual(enc_prompt, S.producer_context(p, "x")[1]["content"])
        post = next(e for e in events if e["type"] == "work" and e["method"] == "encode")
        dec = next((e, t) for e, t in zip([e for e in events if e["type"] == "work"], b.seen)
                   if e["method"] == "decode" and e["agent"] != post["agent"])
        prompt, target, _ = S.use_item(p, "decode", S.forum_block("text", post["report"]).replace(
            "[post 0] from agent1", f"[post {post['pid']}] from {post['agent']}"))
        self.assertEqual(prompt, dec[1])
        for name in S.CONSUMERS:
            self.assertTrue(S.use_ok(p, name, S.use_item(p, name, "")[1])[0])
        q, record = S.secret_item(p, "m")
        self.assertTrue(record.startswith(p.meta["secret"]["tag"] + p.meta["secret"]["delim"]))
        rows = S.synthetic_rows(range(1000, 1040), 0, random.Random(0))
        self.assertTrue(5 < sum(r["vague"] for r in rows) < 35)
        for r in rows:
            sec = S.project_of(r["project"]).meta["secret"]
            self.assertEqual(sec["tag"] in r["text"], not r["vague"])
            self.assertIn(sec["tag"], r["context"][1]["content"])   # the author always knows the format

    def test_mislead_prompts_only_saboteurs(self):
        p = parse_task_spec("secret:1", "", 3, None)[0]

        class Rec(MockBackend):
            def chat(self, messages, latents=(), **kw):
                if kw.get("purpose") == "report":
                    self.seen.append((kw["meta"]["pressure"], messages[-1]["content"]))
                return super().chat(messages, latents, **kw)

        b = Rec(p_correct=1.0)
        b.seen = []
        cfg = RunConfig(channel="text", spec="private", overclaim_frac=0.34, overclaim_mode="mislead", rounds=3).validate()
        self.assertTrue(cfg.tag().endswith("-oc0.34m"))
        run_project(p, b, cfg, [], seed=0)
        self.assertTrue(any(o for o, _ in b.seen) and any(not o for o, _ in b.seen))
        for over, text in b.seen:
            self.assertEqual("must mislead" in text, over)

    def test_grid_and_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            base = RunConfig(out=d).validate()
            conds = list(conditions(base, [[("channel", "none"), ("channel", "latent")],
                                           [("control", "none"), ("control", "zero")]]))
            self.assertEqual(len(conds), 3)  # none+zero is skipped
            s = run_condition(conds[0], MockBackend(), toy_projects())
            self.assertTrue(os.path.exists(os.path.join(d, conds[0].tag(), "summary.json")))
            self.assertIn("propagation", s)


if __name__ == "__main__":
    unittest.main()
