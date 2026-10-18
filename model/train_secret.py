"""E1s: can a trained latent post carry an arbitrary secret to a frozen reader?

    python -m model.train_secret --test-latents 'runs/e0s_<id>/private/latent-*/latents.pt' --out runs/e1s

SecretBench producers (`encode`) know a random record format (about 23 bits); consumers do not
(secretbench.py). In the forum, text carried it half the time (E0s: 0.43 consumer pass) and the
training-free latent not at all (0.008). Here the writer head of E1w is trained so that the stock,
frozen reader can use the latent post alone:

- secret: write the record that `encode(<sample>)` returns (target: the exact string)
- use: implement a consumer method, prompted exactly as in the forum (target: the reference code)
- recon: rewrite the post in plain text

Training data is synthetic, so nothing has to be generated: the producer's real prompts, the
reference `encode` as its answer and a templated report. Half the reports leave the format out,
so the head must take it from what the author knew (its spec and code), not from what it said.
That is also a risk: a latent post can disclose what its author chose not to write.

Evaluation uses real producer posts from forum runs, on secrets the head never saw. Arms:
none (no post), text (the post's own text), self (its latent), other (another project's latent).
"use" is scored like the forum's method_pass_iso: hidden tests, all other methods at reference.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import random
import time

import torch

from forum import prompts as P
from model.backends.base import LATENT_MARK, Latent
from benchmark.secret_tasks import CONSUMERS, forum_block, project_of, secret_item, synthetic_rows, use_item, use_ok
from model.train_reader import RECON, batch_loss
from model.train_writer import WriteHead, context_embeddings

def real_rows(paths) -> list[dict]:
    """First producer post per project that says DONE and is correct, from forum latent dumps."""
    out, seen = [], set()
    for f in paths:
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


@torch.no_grad()
def evaluate(backend, rows, arm: str, latents=None, max_new_tokens: int = 384):
    """Per row: does the reader recover the record, and do its consumer methods pass the hidden tests?"""
    res = []
    for j, r in enumerate(rows):
        p = project_of(r["project"])
        s = p.meta["secret"]
        lats = [latents[j]] if arm in ("self", "other") else []
        msg = LATENT_MARK.format(i=0) if lats else (r["text"] if arm == "text" else "(no message)")
        q, record = secret_item(p, msg)
        g = backend.chat([{"role": "system", "content": P.PROBE_SYSTEM}, {"role": "user", "content": q}], lats,
                         purpose="probe", max_new_tokens=40)
        out = {"project": r["project"], "arm": arm, "answer": g.text.strip()[:120],
               "secret_exact": record in g.text, "tag": s["tag"] in g.text,
               "tag_delim": (s["tag"] + s["delim"]) in g.text}
        block = forum_block("latent" if lats else arm, r["text"])
        for name in CONSUMERS:
            prompt, _, system = use_item(p, name, block)
            g = backend.chat([{"role": "system", "content": system}, {"role": "user", "content": prompt}], lats,
                             purpose="implement", max_new_tokens=max_new_tokens)
            ok, code = use_ok(p, name, g.text)
            out[name] = ok
            out[name + "_code"] = (code or g.text)[:600]
        res.append(out)
    return res


def summarize(res) -> dict:
    rate = lambda k: round(sum(bool(x[k]) for x in res) / len(res), 4) if res else None
    use = [x[n] for x in res for n in CONSUMERS]
    return {"n": len(res), "secret_exact": rate("secret_exact"), "tag": rate("tag"), "tag_delim": rate("tag_delim"),
            **{n: rate(n) for n in CONSUMERS}, "use": round(sum(use) / len(use), 4) if use else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-latents", nargs="+", required=True, help="SecretBench forum dumps (rows need 'context')")
    ap.add_argument("--model", default=os.environ.get("LF_MODEL", "/scratch/jwj/models/Qwen3-8B"))
    ap.add_argument("--out", default="runs/e1s")
    ap.add_argument("--n-train", type=int, default=1000, help="synthetic projects, ids 1000.. (test uses 0..)")
    ap.add_argument("--k", type=int, default=16)
    ap.add_argument("--rank", type=int, default=64)
    ap.add_argument("--steps", type=int, default=1500)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--lr", type=float, default=5e-4)
    ap.add_argument("--max-ctx", type=int, default=3072)
    ap.add_argument("--tasks", default="secret,use,recon")
    ap.add_argument("--init", default="", help="start from a trained writer head (e.g. E1w's)")
    ap.add_argument("--eval-rows", type=int, default=40)
    ap.add_argument("--skip-baselines", action="store_true", help="skip the none / text / step-0 arms")
    ap.add_argument("--q-only", action="store_true", help="train only the query vectors; the map g stays identity")
    ap.add_argument("--eval-every", type=int, default=0,
                    help="track decode use and record recovery on 20 real and 20 synthetic held-out posts")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    torch.manual_seed(a.seed)
    rng = random.Random(a.seed)

    files = sorted({f for g in a.test_latents for f in glob.glob(g)})
    test = real_rows(files)[: a.eval_rows]
    train = synthetic_rows(range(1000, 1000 + a.n_train), 0, rng)
    assert not {r["project"] for r in test} & {r["project"] for r in train}
    print(f"train {len(train)} synthetic posts; test {len(test)} real posts from {len(files)} files", flush=True)

    from model.backends.hf import HFBackend
    backend = HFBackend(a.model)
    for p in backend.model.parameters():
        p.requires_grad_(False)
    if a.init:
        st = torch.load(a.init, map_location=backend.device, weights_only=True)
        head = WriteHead(st["q"], st["a"].shape[1]).to(backend.device)
        head.load_state_dict(st)
    else:
        vocab = backend.emb.weight.shape[0]
        init = backend.emb.weight[torch.randint(1000, min(vocab, 50000), (a.k,), generator=torch.Generator().manual_seed(a.seed))]
        head = WriteHead(init.detach().float(), a.rank).to(backend.device)
    backend.writer_head = head
    val = synthetic_rows(range(2000, 2020), 0, random.Random(a.seed + 1))   # held-out synthetic, for selection
    log = {"config": vars(a), "files": files, "n_train": len(train), "n_test": len(test), "eval": {}, "track": []}
    details = []

    def latents_for(rows):
        head.eval()
        return [Latent(backend.gist(context_embeddings(backend, r["context"], a.max_ctx)).to(torch.float16), a.k)
                for r in rows]

    def run_arm(arm, lats=None):
        t = time.time()
        res = evaluate(backend, test, arm, lats)
        details.extend(res)
        log["eval"][arm] = summarize(res) | {"eval_s": round(time.time() - t, 1)}
        print(arm, json.dumps(log["eval"][arm]), flush=True)

    @torch.no_grad()
    def track(step):
        """Cheap trajectory: secret probe and `decode` on 20 real test and 20 synthetic held-out posts."""
        out = {"step": step}
        for name, rows in (("real", test[:20]), ("synthetic", val)):
            lats = latents_for(rows)
            ex, dec = [], []
            for r, lat in zip(rows, lats):
                p = project_of(r["project"])
                q, record = secret_item(p, LATENT_MARK.format(i=0))
                g = backend.chat([{"role": "system", "content": P.PROBE_SYSTEM}, {"role": "user", "content": q}],
                                 [lat], purpose="probe", max_new_tokens=40)
                ex.append(record in g.text)
                prompt, _, system = use_item(p, "decode", forum_block("latent"))
                g = backend.chat([{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                                 [lat], purpose="implement", max_new_tokens=256)
                dec.append(use_ok(p, "decode", g.text)[0])
            out[name] = {"secret_exact": sum(ex) / max(1, len(ex)), "decode": sum(dec) / max(1, len(dec))}
        log["track"].append(out)
        print("track", json.dumps(out), flush=True)
        head.train()
        return out["synthetic"]["decode"] + out["synthetic"]["secret_exact"]

    if not a.skip_baselines:
        for arm in ("none", "text"):
            run_arm(arm)
        run_arm("self_step0", latents_for(test))

    tasks = tuple(a.tasks.split(","))
    if a.q_only:
        for n, prm in head.named_parameters():
            prm.requires_grad_(n == "q")
    opt = torch.optim.AdamW([prm for prm in head.parameters() if prm.requires_grad], lr=a.lr, weight_decay=0.0)
    best = track(0) if a.eval_every and a.steps else None
    # The "use" prompts are long and the loss backpropagates through the whole frozen reader, so
    # recompute its activations. Checkpointing is active only in train mode, and in train mode HF
    # drops the KV cache that gist() needs, so the model is in train mode only for the loss pass.
    backend.model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    head.train()
    t0 = time.time()
    for step in range(1, a.steps + 1):
        items = []
        for r in rng.sample(train, a.batch):
            p = project_of(r["project"])
            e = backend.gist(context_embeddings(backend, r["context"], a.max_ctx), grad=True)
            lat = Latent(e, e.shape[0])
            cand = train_items(p, r, lat, tasks, rng)
            items.extend(rng.sample(cand, min(2, len(cand))))
        backend.model.train()
        loss = batch_loss(backend, items)
        backend.model.eval()
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(head.parameters(), 1.0)
        opt.step()
        if step % 50 == 0:
            print(f"step {step} loss {loss.item():.4f} ({(time.time() - t0) / step:.2f}s/step)", flush=True)
        if a.eval_every and step % a.eval_every == 0:
            score = track(step)
            if score > best:
                best = score
                torch.save(head.state_dict(), os.path.join(a.out, "writer_head_best.pt"))
    log["train_s"] = round(time.time() - t0, 1)
    torch.save(head.state_dict(), os.path.join(a.out, "writer_head.pt"))

    if not test:
        with open(os.path.join(a.out, "train_log.json"), "w") as f:
            json.dump(log, f, indent=1)
        return
    lats = latents_for(test)
    run_arm("self", lats)
    perm = list(range(len(test)))
    while len(test) > 1 and any(i == j for i, j in enumerate(perm)):
        rng.shuffle(perm)
    run_arm("other", [lats[j] for j in perm])
    with open(os.path.join(a.out, "train_log.json"), "w") as f:
        json.dump(log, f, indent=1)
    with open(os.path.join(a.out, "eval_rows.jsonl"), "w") as f:
        for x in details:
            f.write(json.dumps(x) + "\n")


if __name__ == "__main__":
    main()
