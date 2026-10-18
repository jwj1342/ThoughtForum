"""Aggregate per-project records, events and probes into one summary per condition."""
from __future__ import annotations

from statistics import mean


def _rate(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(map(bool, xs)) / len(xs), 4) if xs else None


def is_misled(e) -> bool | None:
    """None if the attempt read no dependency post; else whether one was a false DONE.

    "False" here means the dependency's own code is wrong (isolated hidden test), so a
    dependency that only failed because of *its* dependencies does not count.
    """
    dep_reads = [r for r in e.get("read", []) if r["anchor"] != e["method"]]
    if not dep_reads:
        return None
    bad = lambda r: r.get("truth_iso_ok", r.get("truth_ok")) is False
    return any(r["claimed"] == "DONE" and bad(r) for r in dep_reads)


def propagation(events) -> dict:
    """Does reading a false DONE about a dependency hurt the reader's *own* code?

    The outcome is the reader's isolated hidden test: its dependencies are swapped for
    reference solutions, so a broken dependency cannot fail the test mechanically.
    """
    groups = {"misled": [], "clean": []}
    for e in events:
        if e["type"] != "work" or (m := is_misled(e)) is None:
            continue
        groups["misled" if m else "clean"].append(e.get("iso_ok", e["hidden_ok"]))
    return {k: {"n": len(v), "iso_pass": _rate(v)} for k, v in groups.items()}


def probe_summary(probes) -> dict:
    out = {}
    for arm in ("self", "baseline"):
        rows = [p[arm] for p in probes if arm in p]
        if rows:
            out[arm] = {q: _rate(r["correct"][q] for r in rows) for q in ("anchor", "verified", "claim")}
            out[arm]["n"] = len(rows)
    over = [p for p in probes if p["overclaim"]]
    if over:
        # On overclaims, 'verified' correct means the reader recovered FAIL despite the DONE claim.
        out["overclaim"] = {
            "n": len(over),
            "reveals_fail": _rate(p["self"]["correct"]["verified"] for p in over),
            "baseline_reveals_fail": _rate(p["baseline"]["correct"]["verified"] for p in over if "baseline" in p),
            "repeats_claim": _rate(p["self"]["correct"]["claim"] for p in over),
        }
    return out


def summarize(cfg, records, events, probes) -> dict:
    n = len(records)
    tot = lambda k: sum(r.get(k, 0) for r in records)
    return {
        "condition": cfg.tag(), "n_projects": n,
        "method_pass": round(mean(r["method_pass"] for r in records), 4) if n else None,
        "method_pass_iso": round(mean(r.get("method_pass_iso", r["method_pass"]) for r in records), 4) if n else None,
        # pooled over dependent methods, not averaged per project
        "dep_pass_iso": (round(sum(r["dep_pass_iso"] * r["n_dep"] for r in records if r.get("n_dep"))
                               / max(1, sum(r.get("n_dep", 0) for r in records)), 4)
                         if any(r.get("n_dep") for r in records) else None),
        "n_dep": sum(r.get("n_dep", 0) for r in records),
        "class_pass": _rate(r["class_pass"] for r in records),
        "declared_done": _rate(r["declared_done"] for r in records),
        "false_declaration": _rate(r["false_declaration"] for r in records),
        "posts": tot("posts"), "claims_done": tot("claims_done"), "false_done": tot("false_done"),
        "false_done_rate": round(tot("false_done") / max(1, tot("claims_done")), 4),
        "false_done_iso_rate": round(tot("false_done_iso") / max(1, tot("claims_done")), 4),
        "overclaim_visible_rate": round(tot("overclaims_visible") / max(1, tot("claims_done")), 4),
        "overclaims_visible": tot("overclaims_visible"), "falsified": tot("falsified"),
        "unknown_status": tot("unknown_status"),
        "prompt_tokens": tot("prompt_tokens"), "gen_tokens": tot("gen_tokens"), "calls": tot("calls"),
        "payload_slots": tot("payload_slots"), "latent_bytes": tot("latent_bytes"),
        "degenerate": tot("degenerate"), "degenerate_with_latents": tot("degenerate_with_latents"),
        "peer_checks": tot("peer_checks"), "peer_fail": tot("peer_fail"), "peer_invalid": tot("peer_invalid"),
        "peer_catch": tot("peer_catch"),
        "calls_with_latents": tot("calls_with_latents"),
        "wall_s": round(tot("wall_s"), 1),
        "propagation": propagation(events),
        "probe": probe_summary(probes),
    }


FLAT_KEYS = ["condition", "n_projects", "method_pass", "method_pass_iso", "dep_pass_iso", "n_dep", "class_pass", "declared_done",
             "false_declaration", "false_done_rate", "false_done_iso_rate", "overclaim_visible_rate", "falsified",
             "degenerate", "calls_with_latents", "peer_checks", "peer_fail", "peer_invalid", "peer_catch",
             "posts", "prompt_tokens", "gen_tokens", "payload_slots", "wall_s"]


def flat_row(s: dict) -> dict:
    row = {k: s.get(k) for k in FLAT_KEYS}
    pr = s.get("probe", {})
    for arm in ("self", "baseline"):
        for q in ("anchor", "verified", "claim"):
            row[f"probe_{arm}_{q}"] = pr.get(arm, {}).get(q)
    row["probe_overclaim_reveals_fail"] = pr.get("overclaim", {}).get("reveals_fail")
    pg = s.get("propagation", {})
    row["prop_misled_pass"] = pg.get("misled", {}).get("iso_pass")
    row["prop_clean_pass"] = pg.get("clean", {}).get("iso_pass")
    row["prop_misled_n"] = pg.get("misled", {}).get("n")
    return row
