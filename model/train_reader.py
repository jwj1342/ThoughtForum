"""E1a: learn a read-in adapter so a frozen reader can interrogate latent posts.

    python -m model.train_reader --latents 'runs/e0_<id>/task1/*/latents.pt' --out runs/e1a

The model (Qwen3-8B) and the writer stay frozen. Only a low-rank residual map on the
received vectors is trained:

    f(z) = z + (z A) B + b,   with B = 0 at init, so step 0 is the training-free channel.

The objectives use the same prompts as `probe.py`, so the evaluation measures exactly
what breakpoint interrogation asks:
- recon: rewrite the message in plain text (target: the author's text)
- anchor: which method is it about (target: the post's method)
- verified: did the code pass CI (target: the CI result, not the author's claim)
- claim: does the author say DONE

Train and eval are split by project. In the eval, "self" uses the post's own latent and
"other" swaps in a latent from a different post, while the scoring still uses the true
post's labels. A gain only counts if self beats other. Accuracy is also reported on the
overclaim subset (claim=DONE, CI=FAIL), where answering FAIL means the latent carries
the truth that the text hides.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import random

import torch

from forum import prompts as P
from model.backends.base import LATENT_MARK, Latent
from forum.probe import _score

RECON = "Message: {msg}\n\nRewrite this message in plain text."


class ReadAdapter(torch.nn.Module):
    def __init__(self, d: int, r: int = 64):
        super().__init__()
        self.a = torch.nn.Parameter(torch.randn(d, r) / d ** 0.5)
        self.b = torch.nn.Parameter(torch.zeros(r, d))
        self.bias = torch.nn.Parameter(torch.zeros(d))

    def forward(self, z):
        return z + (z @ self.a) @ self.b + self.bias


def load_adapter(path: str, device: str = "cuda") -> ReadAdapter:
    st = torch.load(path, map_location=device, weights_only=True)
    m = ReadAdapter(st["a"].shape[0], st["a"].shape[1]).to(device)
    m.load_state_dict(st)
    return m.eval()


def examples(row, tasks):
    """(task, user_prompt, target) for one post."""
    out = []
    opts = ", ".join(row["options"])
    if "recon" in tasks and row["text"].strip():
        out.append(("recon", RECON.format(msg=LATENT_MARK.format(i=0)), row["text"].strip()[:400]))
    if "anchor" in tasks:
        out.append(("anchor", P.PROBE["anchor"].format(msg=LATENT_MARK.format(i=0), cls=row["class_name"], options=opts),
                    row["anchor"]))
    if "verified" in tasks:
        out.append(("verified", P.PROBE["verified"].format(msg=LATENT_MARK.format(i=0)),
                    "PASS" if row["verified_ok"] else "FAIL"))
    if "claim" in tasks:
        out.append(("claim", P.PROBE["claim"].format(msg=LATENT_MARK.format(i=0)),
                    "YES" if row["claimed"] == "DONE" else "NO"))
    return out


def build(backend, prompt, target, lat, system=P.PROBE_SYSTEM):
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    ctx, _ = backend._embed(backend._render(msgs), [lat])
    t_ids = backend.tok(target + "<|im_end|>", add_special_tokens=False, return_tensors="pt").input_ids[0].to(backend.device)
    emb = torch.cat([ctx, backend.emb(t_ids[None])[0]], 0)
    labels = torch.cat([torch.full((ctx.shape[0],), -100, device=backend.device), t_ids])
    return emb, labels


def batch_loss(backend, items):
    embs, labs = zip(*(build(backend, *it) for it in items))   # (prompt, target, latent[, system])
    n = max(e.shape[0] for e in embs)
    d = embs[0].shape[1]
    x = torch.zeros(len(embs), n, d, dtype=embs[0].dtype, device=backend.device)
    y = torch.full((len(embs), n), -100, dtype=torch.long, device=backend.device)
    m = torch.zeros(len(embs), n, dtype=torch.long, device=backend.device)
    for i, (e, l) in enumerate(zip(embs, labs)):
        x[i, :e.shape[0]], y[i, :e.shape[0]], m[i, :e.shape[0]] = e, l, 1
    # logits only where there is a target: full-vocabulary logits over long prompts do not fit
    h = backend.model.model(inputs_embeds=x, attention_mask=m, use_cache=False).last_hidden_state[:, :-1]
    y = y[:, 1:]
    keep = y != -100
    return torch.nn.functional.cross_entropy(backend.model.lm_head(h[keep]).float(), y[keep])


@torch.no_grad()
def evaluate(backend, rows, seed=0, max_rows=200):
    rng = random.Random(seed)
    rows = rows[:max_rows]
    res = {k: {"self": [], "other": []} for k in ("anchor", "verified", "claim")}
    over = {"self": [], "other": []}
    recon = {"self": [], "other": []}
    for r in rows:
        others = [o for o in rows if (o["project"], o["anchor"]) != (r["project"], r["anchor"])]
        o = rng.choice(others) if others else r
        for arm, src in (("self", r), ("other", o)):
            lat = Latent(src["latent"], src["latent"].shape[0])
            for task, prompt, target in examples(r, ("anchor", "verified", "claim")):
                g = backend.chat([{"role": "system", "content": P.PROBE_SYSTEM}, {"role": "user", "content": prompt}],
                                 [lat], purpose="probe", max_new_tokens=12)
                ok = _score(task, g.text, target if task != "anchor" else r["anchor"], r["options"])
                res[task][arm].append(ok)
                if task == "verified" and r["claimed"] == "DONE" and not r["verified_ok"]:
                    over[arm].append(ok)
            if r["text"].strip():
                recon[arm].append(batch_loss(backend, [(RECON.format(msg=LATENT_MARK.format(i=0)),
                                                        r["text"].strip()[:400], lat)]).item())
    rate = lambda xs: round(sum(xs) / len(xs), 4) if xs else None
    out = {k: {a: rate(v[a]) for a in v} for k, v in res.items()}
    out["n"] = len(rows)
    pv = rate([bool(r["verified_ok"]) for r in rows])
    pc = rate([r["claimed"] == "DONE" for r in rows])
    out["majority"] = {"verified": max(pv, 1 - pv) if pv is not None else None,
                       "claim": max(pc, 1 - pc) if pc is not None else None,
                       "anchor": rate([1 / len(r["options"]) for r in rows])}
    out["overclaim_reveals_fail"] = {a: rate(v) for a, v in over.items()} | {"n": len(over["self"])}
    out["recon_loss"] = {a: (round(sum(v) / len(v), 4) if v else None) for a, v in recon.items()}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--latents", nargs="+", required=True, help="latents.pt files or globs")
    ap.add_argument("--model", default=os.environ.get("LF_MODEL", "/scratch/jwj/models/Qwen3-8B"))
    ap.add_argument("--out", default="runs/e1a")
    ap.add_argument("--rank", type=int, default=64)
    ap.add_argument("--steps", type=int, default=600)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--tasks", default="recon,anchor,verified,claim")
    ap.add_argument("--holdout", type=float, default=0.25)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--data", default="data/ClassEval_data.json")
    ap.add_argument("--eval-rows", type=int, default=200)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    torch.manual_seed(a.seed)
    rng = random.Random(a.seed)

    files = sorted({f for g in a.latents for f in glob.glob(g)})
    rows = [r for f in files for r in torch.load(f, weights_only=False)]
    if any(not r.get("options") for r in rows):  # dumps written before options were saved
        from benchmark.tasks import load_classeval
        info = {p.pid: (p.class_name, p.names) for p in load_classeval(a.data, min_methods=1)}
        for r in rows:
            if not r.get("options") and r["project"] in info:
                r["class_name"], r["options"] = info[r["project"]]
    rows = [r for r in rows if r.get("options")]
    projects = sorted({r["project"] for r in rows})
    rng.shuffle(projects)
    test_p = set(projects[: max(1, int(len(projects) * a.holdout))])
    train = [r for r in rows if r["project"] not in test_p]
    test = [r for r in rows if r["project"] in test_p]
    rng.shuffle(test)
    print(f"{len(files)} files, {len(rows)} posts; train {len(train)} / test {len(test)} ({len(test_p)} projects)", flush=True)

    from model.backends.hf import HFBackend
    backend = HFBackend(a.model)
    for p in backend.model.parameters():
        p.requires_grad_(False)
    adapter = ReadAdapter(backend.emb.weight.shape[1], a.rank).to(backend.device)
    backend.reader_adapter = adapter

    log = {"config": vars(a), "files": files, "n_train": len(train), "n_test": len(test)}
    adapter.eval()
    log["eval_step0"] = evaluate(backend, test, a.seed, a.eval_rows)        # identity map = training-free channel
    print("step 0", json.dumps(log["eval_step0"]), flush=True)

    tasks = tuple(a.tasks.split(","))
    pool = [(t, p, y, r) for r in train for t, p, y in examples(r, tasks)]
    opt = torch.optim.AdamW(adapter.parameters(), lr=a.lr, weight_decay=0.0)
    backend.model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    backend.model.train()
    adapter.train()
    for step in range(1, a.steps + 1):
        items = [(p, y, Latent(r["latent"], r["latent"].shape[0])) for _, p, y, r in rng.sample(pool, a.batch)]
        loss = batch_loss(backend, items)
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(adapter.parameters(), 1.0)
        opt.step()
        if step % 50 == 0:
            print(f"step {step} loss {loss.item():.4f}", flush=True)
    backend.model.eval()
    adapter.eval()
    log["eval_final"] = evaluate(backend, test, a.seed, a.eval_rows)
    print("final", json.dumps(log["eval_final"]), flush=True)
    torch.save(adapter.state_dict(), os.path.join(a.out, "adapter.pt"))
    with open(os.path.join(a.out, "train_log.json"), "w") as f:
        json.dump(log, f, indent=1)


if __name__ == "__main__":
    main()
