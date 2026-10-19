"""Offline SecretBench measurement: what posts carry from their authors to a frozen reader.

    python -m benchmark.measure --n 300 --seed 0 --out runs/offline/seed0

No forum is run. For every project, both producers' sessions are synthesized with the forum's own
prompts (the reference code and a templated report). The report states the true format (honest),
leaves it out (omit) or states a false one (lie). Each consumer then gets the posts of the producers
it depends on (one, or two for `migrate`) through one channel and implements the method; the reader
is also asked what each producer returns.

Channels:
- none: no posts, the floor. full_spec: no posts, but every docstring is shown, formats included:
  the ceiling.
- text: the author's report. artifact: the producer's code and CI result as text (the same under
  every speech). session: the author's whole session as text.
- latent: k soft tokens read from the author's context (GistWriter, `--latent-head`).
- kv: each post is its author's KV cache, written on its own; a reader's posts are laid end to end.
- stream: the posts are written into one shared KV stream, each on top of the ones before it
  (KVStream); a reader generates after the segments of its posts.

`--load M` gives every reader M posts: those of its producers plus posts of other projects, in a
random order. `--transplant` adds, for the honest speech and the latent channels, a control in which
the reader gets another project's posts instead of its own.

A reader whose first answer calls methods the consumer may not call (it would fail in isolation
whatever it knows) is told so, as the forum's visible test tells an author, and answers once more.

One row per (project, consumer): `ok` (its isolated hidden tests pass), `delegated` (the methods its
first answer called but may not), `known` and `said` (the
share of its producers whose true tag / falsely stated tag appears in its code), `other` (under
transplant, the share of the other project's tags), the answers to the producer questions, and
cost: prompt tokens, KV entries the reader attends to, and post bytes. analysis/stats.py turns the
rows into confidence intervals and paired tests.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
from collections import defaultdict

from benchmark.evaluate import isolated_ok
from benchmark.workspace import Workspace
from benchmark.secret_tasks import SPEECH, artifact, forum_block, producer_context, question, report, stated, use_item
from benchmark.secretbench import CONSUMERS, PRODUCERS, make_project
from forum import prompts as P

log = logging.getLogger("measure")
CHANNELS = ("none", "full_spec", "text", "artifact", "session", "latent", "kv", "stream")
TEXTS = ("text", "artifact", "session")
LATENTS = ("latent", "kv", "stream")


class Post:
    """One producer's post in one condition: its text, its context, and (latent / kv) its payload."""

    def __init__(self, project, producer, speech, k, channel, writer):
        self.project, self.producer = project, producer
        self.report = report(project, producer, speech, k)
        self.context = producer_context(project, producer, self.report)
        self.text = {"artifact": artifact(project, producer), "session": P.transcript(self.context)}.get(channel, self.report)
        self.payload = writer.write(self.context[:-1], self.report) if channel in ("latent", "kv") else None
        self.label = project   # the class its head names; under transplant, the reader's own

    def nbytes(self, channel):
        return len(self.text.encode()) if channel in TEXTS else getattr(self.payload, "nbytes", 0)


def reader(backend, channel, posts, stream=None, qualified=False):
    """(chat, forum block, KV entries the reader attends to) for a reader that gets `posts` through `channel`.
    Heads name the method as the forum does; `qualified` adds the class (posts of several projects)."""
    heads = [P.post_head(t, f"agent{t + 1}", f"{q.label.class_name}.{q.producer}" if qualified else q.producer)
             for t, q in enumerate(posts)]
    block = forum_block(channel, list(zip(heads, [q.text for q in posts])))
    if channel == "stream":
        prefix = stream.prefix([q.payload for q in posts])
        return (lambda msgs, n, **kw: stream.chat(prefix, msgs, max_new_tokens=n, **kw)), block, getattr(prefix, "k", 0)
    if channel == "kv":
        from model.kv_posts import chat_after, concat
        prefix = concat(backend, [q.payload for q in posts])
        return (lambda msgs, n, **kw: chat_after(backend, prefix, msgs, max_new_tokens=n)), block, prefix.k
    lats = [q.payload for q in posts] if channel == "latent" else []
    return (lambda msgs, n, **kw: backend.chat(msgs, lats, max_new_tokens=n, **kw)), block, sum(l.k for l in lats)


def tags(project, producers, fmt_of):
    return [f["tag"] for f in (fmt_of(project, d) for d in producers) if f]


def share(code, ts):
    return sum(t in code for t in ts) / len(ts) if ts else None


def conditions(speeches, channels, transplant):
    fixed = ("none", "full_spec", "artifact")   # the same under every speech
    out = [("-", ch, False) for ch in fixed if ch in channels]
    for sp in speeches:
        out += [(sp, ch, False) for ch in channels if ch not in fixed]
        if transplant and sp == "honest":
            out += [(sp, ch, True) for ch in channels if ch in LATENTS]
    return out


def make_writers(backend, channels, latent_head):
    w = {}
    if "latent" in channels:
        from model.writers import make_writer
        w["latent"] = make_writer(backend, head=latent_head)
    if "kv" in channels:
        from model.kv_posts import KVWriter
        w["kv"] = KVWriter(backend)
    return w


def run_project(backend, i, projects, sp, ch, transplant, a, writers, rng):
    """Rows for the consumers of project i under one condition."""
    p = projects[i]
    src = projects[(i + 1) % len(projects)] if transplant else p        # whose posts the reader gets
    speech = "honest" if sp == "-" else sp
    k = i + a.seed
    own = {d: Post(src, d, speech, k, ch, writers.get(ch)) for d in PRODUCERS}
    for q in own.values():
        q.label = p
    others = [j for j in range(len(projects)) if j != i]
    distract = [Post(projects[j], rng.choice(PRODUCERS), speech, j + a.seed, ch, writers.get(ch))
                for j in rng.sample(others, max(0, a.load - 1))] if a.load else []
    stream = None
    if ch == "stream":   # one stream per project: its posts and the distractors, written in a random order
        from model.writers import make_stream
        order = list(own.values()) + distract
        rng.shuffle(order)
        stream = make_stream(backend)
        for q in order:
            q.payload = stream.append(q.context[:-1], q.report)

    answers = {}
    for d in PRODUCERS:   # can the reader say what the producer returns, from that producer's post alone?
        chat, block, _ = reader(backend, "none" if ch in ("none", "full_spec") else ch, [own[d]], stream)
        msg = block.strip() or "(no message)"
        q, truth = question(p, d, msg)
        g = chat([{"role": "system", "content": P.PROBE_SYSTEM}, {"role": "user", "content": q}], 60,
                 purpose="probe", meta={"question": d})
        answers[d] = {"answer": g.text.strip()[:160], "exact": truth in g.text}

    rows = []
    for name, deps in CONSUMERS.items():
        posts = [own[d] for d in deps]
        if a.load:
            posts += distract[: a.load - len(posts)]
            rng.shuffle(posts)
        silent = ch in ("none", "full_spec")
        chat, block, entries = reader(backend, "none" if silent else ch, [] if silent else posts, stream,
                                      qualified=bool(a.load))
        fb = ""
        for attempt in (0, 1):   # once more only if the first attempt calls methods it may not call
            prompt, _, system = use_item(p, name, block, full_spec=ch == "full_spec", feedback=fb)
            g = chat([{"role": "system", "content": system}, {"role": "user", "content": prompt}], a.max_new_tokens,
                     purpose="implement", meta={"subtask": p.subtask(name), "agent": "reader", "attempt": attempt})
            ok, code = isolated_ok(p, name, g.text)
            if attempt == 0:
                tokens = g.prompt_tokens
                delegated = Workspace(p).forbidden_calls(name, code) if code else []
                if not delegated:
                    break
                fb = P.FEEDBACK.format(code=code, result=P.not_callable(name, delegated))
        code = code or g.text
        rows.append({
            "project": p.pid, "consumer": name, "speech": sp, "channel": ch, "transplant": transplant,
            "load": a.load, "seed": a.seed, "ok": bool(ok), "delegated": delegated,
            "known": share(code, tags(p, deps, lambda pr, d: pr.meta["formats"][d])),
            "said": share(code, tags(p, deps, lambda pr, d: stated(pr, d, sp))) if sp == "lie" else None,
            "other": share(code, tags(src, deps, lambda pr, d: pr.meta["formats"][d])) if transplant else None,
            "answers": {d: answers[d] for d in deps},
            "prompt_tokens": tokens, "kv_entries": entries,
            "post_bytes": 0 if silent else sum(q.nbytes(ch) for q in posts),
            "code": code[:900]})
    if stream is not None:
        stream.close()
    return rows


def summarize(rows) -> list[dict]:
    groups = defaultdict(list)
    for r in rows:
        groups[(r["speech"], r["channel"], r["transplant"])].append(r)
    mean = lambda xs: round(sum(xs) / len(xs), 4) if xs else None
    out = []
    for (sp, ch, tr), rs in groups.items():
        vals = lambda k: [r[k] for r in rs if r[k] is not None]
        out.append({"speech": sp, "channel": ch, "transplant": tr, "n": len(rs), "pass": mean([r["ok"] for r in rs]),
                    "delegated": mean([bool(r["delegated"]) for r in rs]),
                    "known": mean(vals("known")), "said": mean(vals("said")), "other": mean(vals("other")),
                    "answer": mean([a["exact"] for r in rs for a in r["answers"].values()]),
                    "prompt_tokens": mean(vals("prompt_tokens")), "kv_entries": mean(vals("kv_entries")),
                    "post_kb": mean([r["post_bytes"] / 1024 for r in rs])})
    return out


def table(summary) -> str:
    cols = ["speech", "channel", "transplant", "n", "pass", "delegated", "known", "said", "other", "answer", "prompt_tokens",
            "kv_entries", "post_kb"]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join("–" if s[c] is None else str(s[c]) for c in cols) + " |" for s in summary]
    return "\n".join(lines)


def main(argv=None):
    from model.backends import DEFAULT_MODEL
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend", default="hf", choices=("hf", "mock"))
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--n", type=int, default=300, help="projects 0 .. n-1")
    ap.add_argument("--seed", type=int, default=0, help="sampling seed; also rotates the report templates")
    ap.add_argument("--tag-len", type=int, default=4, help="tag letters: the amount of information to carry")
    ap.add_argument("--speech", default=",".join(SPEECH))
    ap.add_argument("--channel", default=",".join(CHANNELS))
    ap.add_argument("--load", type=int, default=0, help="M > 0: every reader gets M posts, its own and other projects'")
    ap.add_argument("--transplant", action="store_true", help="add the transplant control (honest, latent channels)")
    ap.add_argument("--latent-head", default="random:16", help="the soft-token writer: random:K or a trained head")
    ap.add_argument("--max-new-tokens", type=int, default=512)
    ap.add_argument("--out", default="runs/offline")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    os.makedirs(a.out, exist_ok=True)
    if a.backend == "mock":
        from model.backends.mock import MockBackend
        backend = MockBackend(p_correct=0.5)
    else:
        from model.backends.hf import HFBackend
        backend = HFBackend.load(a.model)
    channels = a.channel.split(",")
    projects = [make_project(i, 0, a.tag_len) for i in range(a.n)]
    conds = conditions(a.speech.split(","), channels, a.transplant)
    writers = make_writers(backend, channels, a.latent_head)
    log.info("%d projects x %d conditions, load %d, seed %d -> %s", len(projects), len(conds), a.load, a.seed, a.out)
    rows = []
    with open(os.path.join(a.out, "rows.jsonl"), "w") as f:
        for sp, ch, transplant in conds:
            rng = random.Random(f"{a.seed}-{sp}-{ch}-{transplant}")
            backend.reseed(a.seed)
            for i in range(len(projects)):
                for r in run_project(backend, i, projects, sp, ch, transplant, a, writers, rng):
                    rows.append(r)
                    f.write(json.dumps(r) + "\n")
            log.info("done %s/%s%s", sp, ch, " transplant" if transplant else "")
    summary = summarize(rows)
    with open(os.path.join(a.out, "summary.json"), "w") as f:
        json.dump({"config": vars(a), "summary": summary}, f, indent=1)
    print(table(summary))


if __name__ == "__main__":
    main()
