"""analysis/stats.py: intervals, paired tests, and which forum items count. Standard library only."""
import json
import os
import tempfile
import unittest

from analysis.stats import cluster_ci, compare, forum_items, holm


class TestStats(unittest.TestCase):
    def test_paired_comparison(self):
        a = {(f"p{i}", m, 0): m == "x" for i in range(30) for m in ("x", "y")}   # half pass
        b = {k: True for k in a}
        r = compare(a, b, n_boot=500)
        self.assertAlmostEqual(r["diff"], 0.5)
        self.assertEqual((r["projects"], r["only_a"], r["only_b"]), (30, 0, 30))
        self.assertLess(r["p"], 1e-6)
        m, lo, hi = cluster_ci(a, 500)
        self.assertEqual((m, lo, hi), (0.5, 0.5, 0.5))   # every project is at 0.5: no spread between clusters

    def test_holm(self):
        self.assertEqual(holm([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06])

    def test_forum_items_keep_methods_whose_producers_someone_else_wrote(self):
        methods = {"encode": {"iso_ok": True, "author": "a0", "deps": []},
                   "decode": {"iso_ok": True, "author": "a1", "deps": ["encode"]},
                   "get_field": {"iso_ok": False, "author": "a0", "deps": ["encode"]}}
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "config.json"), "w") as f:
                json.dump({"seed": 2}, f)
            with open(os.path.join(d, "projects.jsonl"), "w") as f:
                f.write(json.dumps({"project": "P", "methods": methods}) + "\n")
            self.assertEqual(forum_items(d), {("P", "decode", 2): True})
            self.assertEqual(len(forum_items(d, "all")), 3)


if __name__ == "__main__":
    unittest.main()
