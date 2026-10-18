"""E1s: can a latent post carry an arbitrary secret to a frozen reader? Offline SecretBench evaluation,
with an optional training ablation of the writer head.

    python -m training.secret --test-latents 'runs/e0s_<id>/private/latent-*/latents.pt' --steps 0 --out runs/e1s

SecretBench producers (`encode`) know a random record format (about 23 bits); consumers do not
(benchmark/secretbench.py). With `--steps 0` this evaluates the method itself: the untrained
gist head (random vocabulary queries, identity map). With steps > 0 the head is trained on:

- secret: write the record that `encode(<sample>)` returns (target: the exact string)
- use: implement a consumer method, prompted exactly as in the forum (target: the reference code)
- recon: rewrite the post in plain text

Training data is synthetic (benchmark/secret_tasks.py): the producer's real prompts, the
reference `encode` as its answer and a templated report; half the reports leave the format out.
Evaluation uses real producer posts from forum runs, on secrets the head never saw. Arms:
none (no post), text (the post's own text), self (its latent), other (another project's latent).
"use" is scored like the forum's method_pass_iso: hidden tests, all other methods at reference.
"""
from __future__ import annotations

import json
import random
import time

import torch

from benchmark.evaluate import isolated_ok
from benchmark.secret_tasks import CONSUMERS, forum_block, project_of, secret_item, synthetic_rows, use_item
from forum import prompts as P
from forum.dump import dump_files
from model.backends.base import LATENT_MARK, Latent
from training.common import arg_parser, batch_loss, context_embeddings, fit, log, save_json, start
from training.reader import RECON


def real_rows(files) -> list[dict]:
    """First producer post per project that says DONE and is correct, from forum latent dumps."""
    out, seen = [], set()
    for f in files:
        for r in torch.load(f, weights_only=False):
            if (r["anchor"] == "encode" and r.get("context") and r["project"].startswith("Secret_")
                    and r["claimed"] == "DONE" and r.get("truth_iso_ok") and r["project"] not in seen):
                seen.add(r["project"])
                out.append(r)
    return out


def train_items(project, row, lat, tasks, rng):
    out = []
    if "secret" in tasks:
        q, a = secret_item(project, LATENT_MARK.format(i=0))
        out.append((q, a, lat))
    if "use" in tasks:
        q, a, system = use_item(project, rng.choice(CONSUMERS), forum_block("latent"))
        out.append((q, a, lat, system))
    if "recon" in tasks and row["text"].strip():
        out.append((RECON.format(msg=LATENT_MARK.format(i=0)), row["text"].strip()[:400], lat))
    return out


def ask_secret(backend, project, msg, lats):
    """The reader is asked what `encode(sample)` returns. Returns (answer, true record)."""
    q, record = secret_item(project, msg)
    g = backend.chat([{"role": "system", "content": P.PROBE_SYSTEM}, {"role": "user", "content": q}], lats,
                     purpose="probe", max_new_tokens=40)
    return g.text, record


def use(backend, project, name, block, lats, max_new_tokens):
    """The reader implements consumer `name`; returns (passes the isolated hidden test, code)."""
    prompt, _, system = use_item(project, name, block)
    g = backend.chat([{"role": "system", "content": system}, {"role": "user", "content": prompt}], lats,
                     purpose="implement", max_new_tokens=max_new_tokens)
    ok, code = isolated_ok(project, name, g.text)
    return ok, code or g.text


@torch.no_grad()
def evaluate(backend, rows, arm: str, latents=None, max_new_tokens: int = 384):
    """Per row: does the reader recover the record, and do its consumer methods pass the hidden tests?"""
    res = []
    for j, r in enumerate(rows):
        p = project_of(r["project"])
        s = p.meta["secret"]
        lats = [latents[j]] if arm in ("self", "other") else []
        msg = LATENT_MARK.format(i=0) if lats else (r["text"] if arm == "text" else "(no message)")
        answer, record = ask_secret(backend, p, msg, lats)
        out = {"project": r["project"], "arm": arm, "answer": answer.strip()[:120], "secret_exact": record in answer,
               "tag": s["tag"] in answer, "tag_delim": (s["tag"] + s["delim"]) in answer}
        block = forum_block("latent" if lats else arm, r["text"])
        for name in CONSUMERS:
            out[name], code = use(backend, p, name, block, lats, max_new_tokens)
            out[name + "_code"] = code[:600]
        res.append(out)
    return res


def summarize(res) -> dict:
    rate = lambda k: round(sum(bool(x[k]) for x in res) / len(res), 4) if res else None
    used = [x[n] for x in res for n in CONSUMERS]
    return {"n": len(res), "secret_exact": rate("secret_exact"), "tag": rate("tag"), "tag_delim": rate("tag_delim"),
            **{n: rate(n) for n in CONSUMERS}, "use": round(sum(used) / len(used), 4) if used else None}


def main():
    ap = arg_parser(__doc__, out="runs/e1s", steps=1500, lr=5e-4, batch=4)
    ap.add_argument("--test-latents", nargs="+", required=True, help="SecretBench forum dumps (rows need 'context')")
    ap.add_argument("--n-train", type=int, default=1000, help="synthetic projects, ids 1000.. (test uses 0..)")
    ap.add_argument("--k", type=int, default=16)
    ap.add_argument("--rank", type=int, default=64)
    ap.add_argument("--max-ctx", type=int, default=3072)
    ap.add_argument("--tasks", default="secret,use,recon")
    ap.add_argument("--init", default="", help="start from a saved writer head")
    ap.add_argument("--eval-rows", type=int, default=40)
    ap.add_argument("--skip-baselines", action="store_true", help="skip the none / text / step-0 arms")
    ap.add_argument("--q-only", action="store_true", help="train only the query vectors; the map stays identity")
    ap.add_argument("--eval-every", type=int, default=0,
                    help="track decode use and record recovery on 20 real and 20 synthetic held-out posts")
    a = ap.parse_args()
    rng = start(a)

    files = dump_files(a.test_latents)
    test = real_rows(files)[: a.eval_rows]
    train = synthetic_rows(range(1000, 1000 + a.n_train), 0, rng)
    assert not {r["project"] for r in test} & {r["project"] for r in train}
    log.info("train %d synthetic posts; test %d real posts from %d files", len(train), len(test), len(files))

    from model.backends.hf import HFBackend
    from model.hf_writers import GistWriter, load_head, random_head
    backend = HFBackend.load(a.model)
    head = load_head(a.init, backend) if a.init else random_head(backend.emb, a.k, a.seed, a.rank).to(backend.device)
    writer = GistWriter(backend, head)
    val = synthetic_rows(range(2000, 2020), 0, random.Random(a.seed + 1))   # held-out synthetic, for selection
    run_log = {"config": vars(a), "files": files, "n_train": len(train), "n_test": len(test), "eval": {}, "track": []}
    details = []

    def latents_for(rows):
        head.eval()
        return [Latent(writer.gist(context_embeddings(backend, r["context"], a.max_ctx)).to(torch.float16), a.k)
                for r in rows]

    def run_arm(arm, lats=None):
        t = time.time()
        res = evaluate(backend, test, arm, lats)
        details.extend(res)
        run_log["eval"][arm] = summarize(res) | {"eval_s": round(time.time() - t, 1)}
        log.info("%s %s", arm, json.dumps(run_log["eval"][arm]))

    @torch.no_grad()
    def track(step):
        """Cheap trajectory: secret probe and `decode` on 20 real test and 20 synthetic held-out posts."""
        out = {"step": step}
        for name, rows in (("real", test[:20]), ("synthetic", val)):
            ex, dec = [], []
            for r, lat in zip(rows, latents_for(rows)):
                p = project_of(r["project"])
                answer, record = ask_secret(backend, p, LATENT_MARK.format(i=0), [lat])
                ex.append(record in answer)
                dec.append(use(backend, p, "decode", forum_block("latent"), [lat], 256)[0])
            out[name] = {"secret_exact": sum(ex) / max(1, len(ex)), "decode": sum(dec) / max(1, len(dec))}
        run_log["track"].append(out)
        log.info("track %s", json.dumps(out))
        head.train()
        return out["synthetic"]["decode"] + out["synthetic"]["secret_exact"]

    if not a.skip_baselines:
        for arm in ("none", "text"):
            run_arm(arm)
        run_arm("self_step0", latents_for(test))

    if a.steps:
        tasks = tuple(a.tasks.split(","))
        if a.q_only:
            for n, prm in head.named_parameters():
                prm.requires_grad_(n == "q")
        best = [track(0) if a.eval_every else None]
        # The "use" prompts are long and the loss backpropagates through the whole frozen reader, so
        # recompute its activations. Checkpointing is active only in train mode, and in train mode HF
        # drops the KV cache that gist() needs, so the model is in train mode only for the loss pass.
        backend.model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        head.train()

        def loss_fn(step):
            items = []
            for r in rng.sample(train, a.batch):
                e = writer.gist(context_embeddings(backend, r["context"], a.max_ctx), grad=True)
                cand = train_items(project_of(r["project"]), r, Latent(e, e.shape[0]), tasks, rng)
                items.extend(rng.sample(cand, min(2, len(cand))))
            backend.model.train()
            loss = batch_loss(backend, items)
            backend.model.eval()
            return loss

        def on_step(step):
            if a.eval_every and step % a.eval_every == 0:
                score = track(step)
                if score > best[0]:
                    best[0] = score
                    torch.save(head.state_dict(), f"{a.out}/writer_head_best.pt")

        run_log["train_s"] = fit(head.parameters(), a.steps, a.lr, loss_fn, on_step)
    torch.save(head.state_dict(), f"{a.out}/writer_head.pt")

    if test:
        lats = latents_for(test)
        run_arm("self", lats)
        perm = list(range(len(test)))
        while len(test) > 1 and any(i == j for i, j in enumerate(perm)):
            rng.shuffle(perm)
        run_arm("other", [lats[j] for j in perm])
        with open(f"{a.out}/eval_rows.jsonl", "w") as f:
            for x in details:
                f.write(json.dumps(x) + "\n")
    save_json(a.out, "train_log.json", run_log)


if __name__ == "__main__":
    main()
