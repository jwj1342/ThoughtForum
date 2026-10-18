"""Offline SecretBench measurement: what one post carries from its author to a frozen reader.

    python -m benchmark.measure --backend hf --n 40 --speech honest,omit,lie --channel none,text,latent,both \
        --writer random:16,chunk:16 --out runs/measure

No forum is run. For each project the producer's context is synthesized (the forum's own prompts, the
reference `encode` and a templated report), and the report either states the true format (honest),
leaves it out (omit) or states a false one (lie). The reader, the same frozen model, gets the post
through one channel: nothing, the text, the latent post, or both. It then (a) is asked what
`encode(sample)` returns and (b) implements the consumers. Per condition:

- transmission: consumer code that passes its isolated hidden tests
- known_in_code / said_in_code: consumer code that uses the true tag / the tag the author stated
  (under lie these are "follows what the author knows" vs "follows what it says"; under omit,
  known_in_code is what leaks although the author never said it)
- known_in_answer: the true tag in the reader's answer when asked directly
- use_report_gap: known_in_code - known_in_answer; > 0 means interrogation under-reports the post
- transplant (latent only): the reader gets another project's post; other_in_code counts that
  project's tag in the reader's code, a causal check that the content comes from the post.

Writers: `random:K` is the method (untrained gist head with K queries), `chunk:K` the pooling baseline.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from collections import defaultdict

from benchmark.evaluate import isolated_ok
from benchmark.secret_tasks import EXPLICIT, SPEECH, VAGUE, false_secret, forum_block, producer_context, report, \
    secret_item, use_item
from benchmark.secretbench import make_project
from forum import prompts as P
from model.backends.base import LATENT_MARK

log = logging.getLogger("measure")
CHANNELS = ("none", "text", "latent", "both")
TAGGED = ("decode", "is_record")   # the consumers whose code must contain the tag


def make_post(writer, project, speech: str, tmpl_i: int):
    """(text, latent) of the producer's post under `speech`; the latent is None without a writer."""
    tmpl = (VAGUE if speech == "omit" else EXPLICIT)[tmpl_i % 3]
    text = report(project, speech, tmpl)
    ctx = producer_context(project, text)
    return text, (writer.write(ctx[:-1], text) if writer is not None else None)


def read(backend, project, channel: str, text: str, lat, consumers, max_new_tokens: int) -> dict:
    """The reader's answer about `encode`, and its code for each consumer."""
    lats = [lat] if channel in ("latent", "both") else []
    msg = {"none": "(no message)", "text": text, "latent": LATENT_MARK.format(i=0),
           "both": text + "\n" + LATENT_MARK.format(i=0)}[channel]
    q, record = secret_item(project, msg)
    answer = backend.chat([{"role": "system", "content": P.PROBE_SYSTEM}, {"role": "user", "content": q}], lats,
                          purpose="probe", meta={"question": "secret"}, max_new_tokens=40).text
    out = {"answer": answer.strip()[:120], "answer_exact": record in answer, "code": {}, "ok": {}}
    block = forum_block(channel, text)
    for name in consumers:
        prompt, _, system = use_item(project, name, block)
        g = backend.chat([{"role": "system", "content": system}, {"role": "user", "content": prompt}], lats,
                         purpose="implement", meta={"subtask": project.subtask(name), "agent": "reader", "attempt": 0},
                         max_new_tokens=max_new_tokens)
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


def conditions(speeches, channels, writers):
    """(speech, channel, writer spec, transplant); `none` needs neither speech nor writer."""
    out = [("-", "none", "-", False)] if "none" in channels else []
    for sp in speeches:
        if "text" in channels:
            out.append((sp, "text", "-", False))
        for w in writers:
            out += [(sp, ch, w, False) for ch in ("latent", "both") if ch in channels]
            if "latent" in channels and sp == "honest":
                out.append((sp, "latent", w, True))
    return out


def make_writer_spec(backend, spec: str):
    from model.writers import make_writer
    kind, _, k = spec.partition(":")
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
               **{k: mean(k) for k in ("transmission", "known_in_code", "said_in_code", "known_in_answer", "other_in_code")}}
        kc, ka = row["known_in_code"], row["known_in_answer"]
        row["use_report_gap"] = round(kc - ka, 4) if kc is not None and ka is not None else None
        out.append(row)
    return out


def table(summary) -> str:
    cols = ["speech", "channel", "writer", "transplant", "n", "transmission", "known_in_code", "said_in_code",
            "known_in_answer", "use_report_gap", "other_in_code"]
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
    log.info("%d projects (%.1f bits) x %d conditions -> %s", len(projects), projects[0].meta["bits"], len(conds), a.out)

    writers, rows = {}, []
    with open(os.path.join(a.out, "rows.jsonl"), "w") as f:
        for sp, ch, w, transplant in conds:
            if w != "-" and w not in writers:
                writers[w] = make_writer_spec(backend, w)
            posts = [make_post(writers.get(w), p, "honest" if sp == "-" else sp, i) for i, p in enumerate(projects)]
            for i, p in enumerate(projects):
                j = (i + 1) % len(projects) if transplant else i   # transplant: the next project's post
                text, lat = posts[j]
                r = read(backend, p, ch, text, lat, consumers, a.max_new_tokens)
                said = false_secret(p) if sp == "lie" else None
                other = projects[j].meta["secret"] if transplant else None
                row = {"project": p.pid, "speech": sp, "channel": ch, "writer": w, "transplant": transplant,
                       "score": score(p, said, other, r), **r}
                rows.append(row)
                f.write(json.dumps(row) + "\n")
            log.info("done %s/%s/%s%s", sp, ch, w, " transplant" if transplant else "")
    summary = summarize(rows)
    with open(os.path.join(a.out, "summary.json"), "w") as f:
        json.dump({"config": vars(a), "bits": projects[0].meta["bits"], "summary": summary}, f, indent=1)
    print(table(summary))


if __name__ == "__main__":
    main()
