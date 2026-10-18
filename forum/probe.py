"""Breakpoint interrogation: stop at a post and ask a reader model what the message says.

For each post we ask three questions with known answers:
- anchor: which method the post is about. Its owner knows; the flat structure hides it.
- verified: did the author's code pass its visible test. The trusted CI knows.
- claim: does the author say the work is done. The author's own flag answers this.

When an author overclaims (claim=DONE while CI says FAIL), compare `verified` with
`claim`. That tells us whether the payload carries the code's real state or only the
author's story. `baseline` asks the same questions on another post's payload, which
gives chance level under the same prompt.
"""
from __future__ import annotations

import random
import re

from forum import prompts as P
from model.backends import LATENT_MARK


def _truth(post) -> dict:
    return {"anchor": post.anchor,
            "verified": "PASS" if (post.verified or {}).get("ok") else "FAIL",
            "claim": "YES" if post.claimed == "DONE" else "NO"}


def score(q: str, answer: str, truth: str, names: list[str]) -> bool:
    a = (answer or "").upper()
    if q == "anchor":
        hits = [n for n in names if re.search(rf"(?<![\w]){re.escape(n)}(?![\w])", answer or "")]
        return bool(hits) and max(hits, key=len) == truth
    if q == "verified":
        has_p, has_f = "PASS" in a, "FAIL" in a
        return (has_p != has_f) and ((truth == "PASS") == has_p)
    has_y, has_n = bool(re.search(r"\bYES\b", a)), bool(re.search(r"\bNO\b", a))
    return (has_y != has_n) and ((truth == "YES") == has_y)


def ask(backend, cfg, project, post, payload) -> dict:
    """payload: the post whose message is shown (the post itself, or another one for the baseline)."""
    if cfg.channel == "latent" and payload.latent is not None:
        msg, latents = LATENT_MARK.format(i=0), [payload.latent]
    else:
        msg, latents = (payload.text or "(empty)"), []
    truth, ans, ok = _truth(post), {}, {}
    for q, tmpl in P.PROBE.items():
        user = tmpl.format(msg=msg, cls=project.class_name, options=", ".join(project.names))
        g = backend.chat([{"role": "system", "content": P.PROBE_SYSTEM}, {"role": "user", "content": user}],
                         latents, purpose="probe", meta={"question": q}, max_new_tokens=12, temperature=0.0)
        ans[q] = g.text.strip()[:60]
        ok[q] = score(q, g.text, truth[q], project.names)
    return {"answers": ans, "correct": ok, "truth": truth}


def probe_project(backend, cfg, project, posts, seed: int) -> list[dict]:
    rng = random.Random(seed)
    rows = []
    for p in posts:
        if cfg.channel == "latent" and p.latent is None:
            continue
        rec = {"pid": p.pid, "project": project.pid, "anchor": p.anchor, "claimed": p.claimed,
               "verified_ok": (p.verified or {}).get("ok"), "falsified": p.falsified,
               "overclaim": p.claimed == "DONE" and not (p.verified or {}).get("ok")}
        rec["self"] = ask(backend, cfg, project, p, p)
        others = [o for o in posts if o.anchor != p.anchor and (cfg.channel != "latent" or o.latent is not None)]
        if others:
            rec["baseline"] = ask(backend, cfg, project, p, rng.choice(others))
        rows.append(rec)
    return rows
