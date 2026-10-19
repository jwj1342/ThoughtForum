"""Offline SecretBench measurement: what one post carries from its author to a frozen reader.

    python -m benchmark.measure --backend hf --n 40 --speech honest,omit,lie --channel none,text,latent,both \
        --writer random:16,chunk:16 --out runs/measure
    python -m benchmark.measure --channel none,text,artifact,kv --writer kv:full,kv:snap:64 --out runs/measure_kv

No forum is run. For each project the producer's context is synthesized (the forum's own prompts, the
reference `encode` and a templated report), and the report either states the true format (honest),
leaves it out (omit) or states a false one (lie). The reader, the same frozen model, gets the post
through one channel: nothing, the text, the latent post, both, the producer's code pasted as text
(`artifact`, independent of what the author says), the report followed by that code (`text_artifact`),
the author's whole session pasted as a message (`transcript`: what a whole KV post holds, in the same
order), or the author's KV cache placed before the reader's prompt (`kv`, model/kv_posts.py). It then (a) is asked what
`encode(sample)` returns and (b) implements the consumers. Per condition:

- transmission: consumer code that passes its isolated hidden tests
- known_in_code / said_in_code: consumer code that uses the true tag / the tag the author stated
  (under lie these are "follows what the author knows" vs "follows what it says"; under omit,
  known_in_code is what leaks although the author never said it)
- known_in_answer: the true tag in the reader's answer when asked directly
- use_report_gap: known_in_code - known_in_answer; > 0 means interrogation under-reports the post
- transplant (latent only): the reader gets another project's post; other_in_code counts that
  project's tag in the reader's code, a causal check that the content comes from the post.

`--posts M` is the load setting: the reader gets M posts at once, its producer's and those of M - 1
other projects, in a random order, each headed with its class. `kv` posts are laid end to end, or with
`--layout parallel` all at the positions they were written at, or with `--layout captioned` each followed by
a text caption the reader prefills (its head line: who wrote it, on what); `--dedup` keeps the shared system turn once;
`--joint` is the diagnostic: the M sessions are encoded together in one pass, as if one author had them all.

Writers: `random:K` is the method (untrained gist head with K queries), `chunk:K` the pooling baseline;
for `kv`: `kv:full`, `kv:snap:B` (B entries the report attends to most), `kv:recent:B` (the last B),
`kv:uniform:B` (evenly spaced); all but `full` also keep the first 4 entries.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
from collections import defaultdict

from benchmark.evaluate import isolated_ok
from benchmark.secret_tasks import EXPLICIT, SPEECH, VAGUE, artifact, false_secret, forum_block, producer_context, \
    report, secret_item, use_item
from benchmark.secretbench import make_project
from forum import prompts as P
from model.backends.base import LATENT_MARK

log = logging.getLogger("measure")
CHANNELS = ("none", "text", "artifact", "text_artifact", "transcript", "latent", "both", "kv")
TEXTS = ("text", "artifact", "text_artifact", "transcript")
TAGGED = ("decode", "is_record")   # the consumers whose code must contain the tag


def make_post(writer, project, speech: str, tmpl_i: int):
    """(text, latent) of the producer's post under `speech`; the latent is None without a writer."""
    tmpl = (VAGUE if speech == "omit" else EXPLICIT)[tmpl_i % 3]
    text = report(project, speech, tmpl)
    ctx = producer_context(project, text)
    return text, (writer.write(ctx[:-1], text) if writer is not None else None)


def text_of(channel, project, report_text) -> str:
    """The text a text-channel post carries."""
    if channel == "artifact":
        return artifact(project)
    if channel == "text_artifact":
        return report_text + "\n\n" + artifact(project, status=False)
    if channel == "transcript":
        return P.transcript(producer_context(project, report_text))
    return report_text


def reader_chat(backend, channel, lat):
    """chat(messages, max_new_tokens, **kw) for a reader that receives `lat` through `channel`."""
    if channel == "kv":
        from model.kv_posts import chat_after
        return lambda msgs, n, **kw: chat_after(backend, lat, msgs, max_new_tokens=n)
    lats = [lat] if channel in ("latent", "both") else []
    return lambda msgs, n, **kw: backend.chat(msgs, lats, max_new_tokens=n, **kw)


def present(channel, text):
    """(the message the reader is asked about, the forum block it writes code with) for one post."""
    msg = text if channel in TEXTS else {"none": "(no message)", "latent": LATENT_MARK.format(i=0),
                                         "both": text + "\n" + LATENT_MARK.format(i=0), "kv": P.KV_NOTE}[channel]
    return msg, forum_block("text" if channel in TEXTS else channel, text)


def present_many(channel, texts, projects):
    """The load setting: one post per project, each headed with its class."""
    entries = [(P.post_head(t, f"agent{t + 1}", f"{p.class_name}.encode"), text if channel in TEXTS else P.KV_NOTE)
               for t, (text, p) in enumerate(zip(texts, projects))]
    block = P.forum_section(entries, latent=channel == "kv")
    return block.strip(), block


def read(project, chat, msg: str, block: str, consumers, max_new_tokens: int) -> dict:
    """The reader's answer about `encode`, and its code for each consumer."""
    q, record = secret_item(project, msg)
    answer = chat([{"role": "system", "content": P.PROBE_SYSTEM}, {"role": "user", "content": q}], 40,
                  purpose="probe", meta={"question": "secret"}).text
    out = {"answer": answer.strip()[:120], "answer_exact": record in answer, "code": {}, "ok": {}}
    for name in consumers:
        prompt, _, system = use_item(project, name, block)
        g = chat([{"role": "system", "content": system}, {"role": "user", "content": prompt}], max_new_tokens,
                 purpose="implement", meta={"subtask": project.subtask(name), "agent": "reader", "attempt": 0})
        out["ok"][name], code = isolated_ok(project, name, g.text)
        out["code"][name] = (code or g.text)[:800]
    return out


def score(project, said: dict | None, other: dict | None, r: dict) -> dict:
    tag = project.meta["secret"]["tag"]
    codes = [r["code"][n] for n in TAGGED if n in r["code"]]
    frac = lambda t: sum(t in c for c in codes) / len(codes) if codes and t else None
    return {"transmission": sum(r["ok"].values()) / len(r["ok"]),
            "known_in_code": frac(tag), "said_in_code": frac(said["tag"]) if said else None,
            "known_in_answer": float(tag in r["answer"]), "other_in_code": frac(other["tag"]) if other else None}


def post_kb(channel, text, lat) -> float | None:
    """What the post costs to store and send: UTF-8 text, or the latent / KV tensors."""
    if channel == "none":
        return None
    n = len(text.encode()) if channel in TEXTS else getattr(lat, "nbytes", 0)
    if channel == "both":
        n += len(text.encode())
    return round(n / 1024, 1)


def conditions(speeches, channels, writers):
    """(speech, channel, writer spec, transplant). `none` and `artifact` do not depend on what the
    author says; `kv` pairs with the kv:* writers, `latent` and `both` with the others."""
    out = [("-", ch, "-", False) for ch in ("none", "artifact") if ch in channels]
    kv = [w for w in writers if w.startswith("kv:")]
    soft = [w for w in writers if not w.startswith("kv:")]
    for sp in speeches:
        out += [(sp, ch, "-", False) for ch in ("text", "text_artifact", "transcript") if ch in channels]
        for chs, ws in ((("latent", "both"), soft), (("kv",), kv)):
            for w in ws:
                out += [(sp, ch, w, False) for ch in chs if ch in channels]
                if chs[0] in channels and sp == "honest":
                    out.append((sp, chs[0], w, True))
    return out


def make_writer_spec(backend, spec: str):
    from model.writers import make_writer
    kind, _, k = spec.partition(":")
    if kind == "kv":
        from model.kv_posts import KVWriter
        mode, _, budget = k.partition(":")
        return KVWriter(backend, mode, int(budget or 0))
    return make_writer(backend, int(k or 16)) if kind == "chunk" else make_writer(backend, head=spec)


def summarize(rows) -> list[dict]:
    groups = defaultdict(list)
    for r in rows:
        groups[(r["speech"], r["channel"], r["writer"], r["transplant"])].append(r["score"])
    out = []
    for (sp, ch, w, tr), scores in groups.items():
        mean = lambda k: (round(sum(v[k] for v in scores if v[k] is not None) /
                                max(1, sum(v[k] is not None for v in scores)), 4)
                          if any(v[k] is not None for v in scores) else None)
        row = {"speech": sp, "channel": ch, "writer": w, "transplant": tr, "n": len(scores),
               **{k: mean(k) for k in ("transmission", "known_in_code", "said_in_code", "known_in_answer", "other_in_code",
                                       "post_kb")}}
        kc, ka = row["known_in_code"], row["known_in_answer"]
        row["use_report_gap"] = round(kc - ka, 4) if kc is not None and ka is not None else None
        out.append(row)
    return out


def table(summary) -> str:
    cols = ["speech", "channel", "writer", "transplant", "n", "transmission", "known_in_code", "said_in_code",
            "known_in_answer", "use_report_gap", "other_in_code", "post_kb"]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join("–" if s[c] is None else str(s[c]) for c in cols) + " |" for s in summary]
    return "\n".join(lines)


def main(argv=None):
    from model.backends import DEFAULT_MODEL
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend", default="hf", choices=("hf", "mock"))
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--n", type=int, default=40, help="projects (ids --start ..)")
    ap.add_argument("--start", type=int, default=3000, help="first project id; forum runs and training use 0.. and 1000..")
    ap.add_argument("--tag-len", type=int, default=4, help="tag letters: the amount of information to carry")
    ap.add_argument("--speech", default=",".join(SPEECH))
    ap.add_argument("--channel", default=",".join(CHANNELS))
    ap.add_argument("--writer", default="random:16", help="comma-separated: random:K (the method), chunk:K, or a head path")
    ap.add_argument("--consumers", default=",".join(TAGGED))
    ap.add_argument("--posts", type=int, default=0, help="M > 0: the load setting with M posts per reader")
    ap.add_argument("--layout", default="sequential", choices=("sequential", "parallel", "captioned"),
                    help="kv posts under load")
    ap.add_argument("--dedup", action="store_true", help="kv posts under load: keep the shared system turn once")
    ap.add_argument("--joint", action="store_true", help="kv posts under load: encode the M sessions in one pass")
    ap.add_argument("--max-new-tokens", type=int, default=384)
    ap.add_argument("--out", default="runs/measure")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    os.makedirs(a.out, exist_ok=True)

    if a.backend == "mock":
        from model.backends.mock import MockBackend
        backend = MockBackend(p_correct=0.5)
    else:
        from model.backends.hf import HFBackend
        backend = HFBackend.load(a.model)
    projects = [make_project(i, 0, a.tag_len) for i in range(a.start, a.start + a.n)]
    consumers = a.consumers.split(",")
    conds = conditions(a.speech.split(","), a.channel.split(","), a.writer.split(","))
    if a.posts and any(ch not in TEXTS + ("kv",) for _, ch, _, _ in conds):
        ap.error("--posts works with the text channels and kv")
    log.info("%d projects (%.1f bits) x %d conditions -> %s", len(projects), projects[0].meta["bits"], len(conds), a.out)

    writers, rows = {}, []
    with open(os.path.join(a.out, "rows.jsonl"), "w") as f:
        for sp, ch, w, transplant in conds:
            if w != "-" and w not in writers:
                writers[w] = make_writer_spec(backend, w)
            posts = [make_post(writers.get(w), p, "honest" if sp == "-" else sp, i) for i, p in enumerate(projects)]
            posts = [(text_of(ch, p, text), lat) for (text, lat), p in zip(posts, projects)]
            for i, p in enumerate(projects):
                j = (i + 1) % len(projects) if transplant else i   # transplant: the next project's post
                if a.posts:
                    idx = [(j + t) % len(projects) for t in range(a.posts)]
                    random.Random(i).shuffle(idx)
                    msg, block = present_many(ch, [posts[x][0] for x in idx], [projects[x] for x in idx])
                    lat = None
                    if ch == "kv" and a.joint:
                        joint = [m for x in idx for m in producer_context(projects[x], posts[x][0])]
                        lat = writers[w].write(joint[:-1], joint[-1]["content"])
                    elif ch == "kv" and a.layout == "captioned":
                        from model.kv_posts import assemble
                        caps = [P.post_head(t, f"agent{t + 1}", f"{projects[x].class_name}.encode") + ": the session above\n"
                                for t, x in enumerate(idx)]
                        lat = assemble(backend, [posts[x][1] for x in idx], caps)
                    elif ch == "kv":
                        from model.kv_posts import concat
                        lat = concat(backend, [posts[x][1] for x in idx], a.layout, a.dedup)
                    kb = round(sum(post_kb(ch, *posts[x]) for x in idx), 1)
                else:
                    text, lat = posts[j]
                    msg, block = present(ch, text)
                    kb = post_kb(ch, text, lat)
                r = read(p, reader_chat(backend, ch, lat), msg, block, consumers, a.max_new_tokens)
                said = false_secret(p) if sp == "lie" else None
                other = projects[j].meta["secret"] if transplant else None
                row = {"project": p.pid, "speech": sp, "channel": ch, "writer": w, "transplant": transplant,
                       "posts": a.posts or 1, "score": score(p, said, other, r) | {"post_kb": kb}, **r}
                rows.append(row)
                f.write(json.dumps(row) + "\n")
            log.info("done %s/%s/%s%s", sp, ch, w, " transplant" if transplant else "")
    summary = summarize(rows)
    with open(os.path.join(a.out, "summary.json"), "w") as f:
        json.dump({"config": vars(a), "bits": projects[0].meta["bits"], "summary": summary}, f, indent=1)
    print(table(summary))


if __name__ == "__main__":
    main()
