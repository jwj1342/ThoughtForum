"""The multi-agent forum on the mock backend. Standard library only."""
import os
import tempfile
import unittest

from benchmark import secret_tasks as S
from benchmark.secretbench import CONSUMERS
from benchmark.tasks import parse_task_spec, toy_projects
from forum.agent import force_done, parse_status, pick_option
from forum.config import RunConfig
from forum.posts import Forum, Post
from forum.run import conditions, run_condition
from model.backends.mock import MockBackend
from tests.helpers import RecordingMock, run


class TestProtocol(unittest.TestCase):
    def test_status_helpers(self):
        self.assertEqual(parse_status("STATUS: partial\nmore"), "PARTIAL")
        self.assertEqual(parse_status("nothing"), "UNKNOWN")
        self.assertEqual(parse_status(force_done("STATUS: BLOCKED\nx")), "DONE")
        self.assertEqual(pick_option("I'll take `select_all`.", ["select", "select_all"]), "select_all")

    def test_flat_structure_hides_anchor(self):
        f = Forum(RunConfig(channel="text", structure="flat").validate(), [], 0)
        f.write(Post(0, "p", "agent1", 0, "add", "DONE", "STATUS: DONE\nadds", version=1))
        block, _, log = f.render(f.select("agent0", "total", []), {"add": 1})
        self.assertNotIn("`add`", block)
        self.assertEqual(log[0]["anchor"], "add")

    def test_attested_reopens_false_done(self):
        f = Forum(RunConfig(trust="attested").validate(), [], 0)
        f.write(Post(0, "p", "agent1", 0, "add", "DONE", "STATUS: DONE", verified={"ok": False}))
        self.assertFalse(f.closed("add"))
        blind = Forum(RunConfig().validate(), [], 0)
        blind.write(Post(0, "p", "agent1", 0, "add", "DONE", "STATUS: DONE", verified={"ok": False}))
        self.assertTrue(blind.closed("add"))

    def test_controls(self):
        bank = [Post(0, "other", "agent9", 0, "x", "DONE", "foreign message")]
        f = Forum(RunConfig(channel="text", control="shuffle").validate(), bank, 0)
        f.write(Post(0, "p", "agent1", 0, "add", "DONE", "own message"))
        self.assertIn("foreign message", f.render(f.select("agent0", "add", []), {})[0])
        z = Forum(RunConfig(channel="text", control="zero").validate(), [], 0)
        z.write(Post(0, "p", "agent1", 0, "add", "DONE", "own message"))
        self.assertNotIn("own message", z.render(z.select("agent0", "add", []), {})[0])

    def test_config_rejects_impossible_conditions(self):
        with self.assertRaises(ValueError):
            RunConfig(channel="none", control="shuffle").validate()
        with self.assertRaises(ValueError):
            RunConfig(backend="api", channel="latent").validate()


class TestPipeline(unittest.TestCase):
    def test_end_to_end_mock(self):
        p = toy_projects()[0]
        for channel in ("none", "text", "latent"):
            cfg = RunConfig(channel=channel, rounds=6, overclaim_frac=0.34).validate()
            rec, events, probes = run(p, cfg, MockBackend(p_correct=0.5), seed=1)
            self.assertIn("class_pass", rec)
            self.assertTrue(any(e["type"] == "work" for e in events))
            if channel == "latent":  # mock latents are lossless, so probes must be perfect
                self.assertTrue(all(r["self"]["correct"]["anchor"] for r in probes))

    def test_crosscheck_runs_peer_tests(self):
        cfg = RunConfig(channel="text", trust="crosscheck", rounds=6).validate()
        rec, events, _ = run(toy_projects()[0], cfg, MockBackend(p_correct=0.5), seed=2)
        peers = [e for e in events if e["type"] == "peer"]
        self.assertTrue(peers)
        self.assertTrue(all(e["tests_valid_on_reference"] for e in peers))  # mock peers copy the hidden tests
        self.assertEqual(rec.get("peer_checks", 0), len(peers))

    def test_deceive_marks_only_failed_done(self):
        cfg = RunConfig(channel="latent", overclaim_frac=0.34, overclaim_mode="deceive", rounds=8).validate()
        _, events, _ = run(toy_projects()[0], cfg, MockBackend(p_correct=0.0), seed=3)
        work = [e for e in events if e["type"] == "work"]
        lies = [e for e in work if e["falsified"]]
        self.assertTrue(lies)
        self.assertTrue(all(e["overclaimer"] and e["claimed"] == "DONE" and not e["visible_ok"] for e in lies))
        self.assertFalse(any(e["falsified"] for e in work if not e["overclaimer"]))

    def test_private_spec_reports_dependent_methods(self):
        cfg = RunConfig(channel="text", spec="private", rounds=4).validate()
        rec, _, _ = run(toy_projects()[0], cfg, MockBackend(p_correct=0.5), seed=4)
        self.assertIn("dep_pass_iso", rec)
        p = parse_task_spec("secret:1", "", 3, None)[0]
        rec, _, _ = run(p, RunConfig(spec="private", rounds=4).validate(), MockBackend(p_correct=1.0), seed=5)
        self.assertEqual(rec["method_pass"], 1.0)

    def assert_reads_posted_deps(self, events):
        """Every consumer attempt reads the latest post on each of its producers, unless it wrote that post."""
        author, checked = {}, 0
        for e in events:
            if e["type"] != "work":
                continue
            if e["method"] in CONSUMERS:
                expected = {d for d in CONSUMERS[e["method"]] if author.get(d, e["agent"]) != e["agent"]}
                self.assertLessEqual(expected, {r["anchor"] for r in e["read"]}, e["method"])
                checked += bool(expected)
            author[e["method"]] = e["agent"]
        self.assertGreater(checked, 0)

    def test_consumers_read_the_producer_posts(self):
        p = parse_task_spec("secret:1", "", 3, None)[0]
        cfg = RunConfig(channel="text", spec="private", rounds=4).validate()
        _, events, _ = run(p, cfg, MockBackend(p_correct=1.0), seed=6)
        self.assert_reads_posted_deps(events)

    def test_stream_channel(self):
        p = parse_task_spec("secret:1", "", 3, None)[0]
        for control in ("none", "zero"):
            cfg = RunConfig(channel="stream", spec="private", rounds=4, control=control).validate()
            rec, events, probes = run(p, cfg, MockBackend(p_correct=1.0), seed=6)
            self.assert_reads_posted_deps(events)
            self.assertEqual(rec.get("calls_with_latents", 0) > 0, control == "none")   # zero: no segments
            self.assertEqual(probes, [])
        with self.assertRaises(ValueError):
            RunConfig(channel="stream", source="artifact").validate()
        cfg = RunConfig(channel="text", source="session", spec="private", rounds=4).validate()
        b = RecordingMock("implement", p_correct=1.0)
        _, events, _ = run(p, cfg, b, seed=6)
        self.assertTrue(all(e["report"].startswith("[system]") for e in events if e["type"] == "work"))
        read = [t for _, t in b.seen if "[assistant]" in t]
        self.assertTrue(read)   # consumers got whole sessions, each without the posts its author had read
        self.assertTrue(all(t.count("Messages from teammates") == 1 for t in read))

    def test_memory_and_text_artifact(self):
        p = parse_task_spec("secret:1", "", 3, None)[0]
        for memory in (False, True):
            b = RecordingMock("implement", p_correct=1.0)
            cfg = RunConfig(channel="none", spec="private", memory=memory, n_agents=1, rounds=4).validate()
            run(p, cfg, b)   # one agent, dependencies first: it wrote `encode` before any reader of it
            consumer = [t for meta, t in b.seen if meta["subtask"].name in ("decode", "is_record", "get_field")]
            self.assertTrue(consumer)
            self.assertEqual(all("Your own earlier code for `encode`" in t for t in consumer), memory)
        cfg = RunConfig(channel="text", source="artifact", spec="private", n_agents=1, rounds=1).validate()
        self.assertIn("-artifact", cfg.tag())
        _, events, _ = run(p, cfg, MockBackend(p_correct=1.0))
        rep = next(e["report"] for e in events if e["type"] == "work")
        self.assertTrue(rep.startswith("STATUS: DONE") and "def encode(" in rep)

    def test_offline_benchmark_sees_the_forum_prompts(self):
        p = parse_task_spec("secret:1", "", 3, None)[0]
        b = RecordingMock("implement", p_correct=1.0)
        cfg = RunConfig(channel="text", spec="private", n_agents=3, rounds=2, probe=False).validate()
        _, events, _ = run(p, cfg, b)
        prompts = [t for _, t in b.seen]
        self.assertEqual(next(t for t in prompts if "implement the method `encode`" in t),
                         S.producer_context(p, "encode", "x")[1]["content"])
        post = next(e for e in events if e["type"] == "work" and e["method"] == "encode")
        work = [e for e in events if e["type"] == "work"]
        consumer = next(t for e, t in zip(work, prompts) if e["method"] == "decode" and e["agent"] != post["agent"]
                        and e["pid"] > post["pid"])
        head = f"[post {post['pid']}] from {post['agent']} on `encode`"
        prompt, _, _ = S.use_item(p, "decode", S.forum_block("text", [(head, post["report"])]))
        self.assertEqual(prompt, consumer)

    def test_mislead_prompts_only_saboteurs(self):
        p = parse_task_spec("secret:1", "", 3, None)[0]
        b = RecordingMock("report", p_correct=1.0)
        cfg = RunConfig(channel="text", spec="private", overclaim_frac=0.34, overclaim_mode="mislead", rounds=3).validate()
        self.assertTrue(cfg.tag().endswith("-oc0.34m"))
        run(p, cfg, b)
        flags = [(meta["pressure"], text) for meta, text in b.seen]
        self.assertTrue(any(o for o, _ in flags) and any(not o for o, _ in flags))
        for over, text in flags:
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
