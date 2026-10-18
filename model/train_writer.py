"""E1w: learn the protocol's writer, so that frozen peers can read latent posts.

    python -m model.train_writer --latents 'runs/e0p_<id>/task1/*/latents.pt' --out runs/e1w

E1a trained the reader and kept the training-free writer (chunk means of the message's
hidden states). It recovered coarse state but not which method a post was about, which
points at the writer: pooling throws instance content away. Here the reader stays frozen
and stock, and the writer is trained instead:

    k learnable query vectors are appended after the author's message, in the author's own
    context; their final-layer states, mapped by W_a and a residual map g, are the post.

The head (queries plus g) belongs to the protocol, not to any agent: it runs on trusted
inference, so an agent cannot swap in its own encoder (see the threat model in forum_focus).

Only the k query positions need gradients. The context is run once without them and
handed over as a KV cache, so each step costs one forward pass over the context plus a
short backward pass.

The objectives and the evaluation are those of E1a (train_reader.py): recon, anchor,
verified, claim; split by project; "self" vs "other" latent. The verified target is the
CI result, so the writer is trained to carry the truth even when the message lies.

Limitation: rows store the writer's context with the latents it read replaced by a text
placeholder, so the head is trained without injected latents in its context.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import random
import time

import torch

from model.backends.base import LATENT_RE, Latent
from model.train_reader import batch_loss, evaluate, examples

PLACEHOLDER = "(latent message)"


class WriteHead(torch.nn.Module):
    def __init__(self, q: torch.Tensor, r: int = 64):
        super().__init__()
        d = q.shape[1]
        self.q = torch.nn.Parameter(q.clone().float())
        self.a = torch.nn.Parameter(torch.randn(d, r) / d ** 0.5)
        self.b = torch.nn.Parameter(torch.zeros(r, d))
        self.bias = torch.nn.Parameter(torch.zeros(d))

    @property
    def k(self) -> int:
        return self.q.shape[0]

    def out(self, e):
        return e + (e @ self.a) @ self.b + self.bias


def random_head(emb: torch.nn.Embedding, k: int = 16, seed: int = 0, r: int = 64) -> WriteHead:
    """The untrained head: k random vocabulary embeddings as queries and an identity map (b = 0).
    Same draw as `train_secret` at step 0."""
    ids = torch.randint(1000, min(emb.weight.shape[0], 50000), (k,), generator=torch.Generator().manual_seed(seed))
    return WriteHead(emb.weight[ids].detach().float(), r)


def load_head(path: str, device: str = "cuda", emb: torch.nn.Embedding | None = None) -> WriteHead:
    """A saved head, or `random:K[:SEED]` for the untrained one (needs the model's embeddings)."""
    if path.startswith("random"):
        parts = [int(x) for x in path.split(":")[1:]]
        return random_head(emb, *parts).to(device).eval()
    st = torch.load(path, map_location=device, weights_only=True)
    h = WriteHead(st["q"], st["a"].shape[1]).to(device)
    h.load_state_dict(st)
    return h.eval()


def context_embeddings(backend, context, max_ctx: int):
    """Embed a saved writer context (messages ending with the author's post), last max_ctx positions."""
    msgs = [{**m, "content": LATENT_RE.sub(PLACEHOLDER, m["content"])} for m in context]
    ctx, _ = backend._embed(backend._render(msgs[:-1]), [])
    ids = backend.tok(msgs[-1]["content"] or " ", add_special_tokens=False, return_tensors="pt").input_ids.to(backend.device)
    full = torch.cat([ctx, backend.emb(ids)[0]], 0)
    return full[-max_ctx:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--latents", nargs="+", required=True, help="latents.pt files or globs (rows need 'context')")
    ap.add_argument("--model", default=os.environ.get("LF_MODEL", "/scratch/jwj/models/Qwen3-8B"))
    ap.add_argument("--out", default="runs/e1w")
    ap.add_argument("--k", type=int, default=16)
    ap.add_argument("--rank", type=int, default=64)
    ap.add_argument("--steps", type=int, default=1500)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--lr", type=float, default=5e-4)
    ap.add_argument("--max-ctx", type=int, default=3072)
    ap.add_argument("--tasks", default="recon,anchor,verified,claim")
    ap.add_argument("--holdout", type=float, default=0.25)
    ap.add_argument("--folds", type=int, default=0, help="cross-fitting: hold out fold --fold of this many")
    ap.add_argument("--fold", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--eval-rows", type=int, default=200)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    torch.manual_seed(a.seed)
    rng = random.Random(a.seed)

    files = sorted({f for g in a.latents for f in glob.glob(g)})
    rows = [r for f in files for r in torch.load(f, weights_only=False)]
    rows = [r for r in rows if r.get("context") and r.get("options") and r["text"].strip()]
    projects = sorted({r["project"] for r in rows})
    rng.shuffle(projects)
    if a.folds:
        test_p = set(projects[a.fold::a.folds])
    else:
        test_p = set(projects[: max(1, int(len(projects) * a.holdout))])
    with open(os.path.join(a.out, "test_projects.json"), "w") as f:
        json.dump(sorted(test_p), f)   # for a clean forum run: --tasks classeval:@<this file>
    train = [r for r in rows if r["project"] not in test_p]
    test = [r for r in rows if r["project"] in test_p]
    rng.shuffle(test)
    test = test[: a.eval_rows]
    print(f"{len(files)} files, {len(rows)} posts with context; train {len(train)} / test {len(test)} "
          f"({len(test_p)} projects)", flush=True)

    from model.backends.hf import HFBackend
    backend = HFBackend(a.model)
    for p in backend.model.parameters():
        p.requires_grad_(False)
    vocab = backend.emb.weight.shape[0]
    init = backend.emb.weight[torch.randint(1000, min(vocab, 50000), (a.k,), generator=torch.Generator().manual_seed(a.seed))]
    head = WriteHead(init.detach().float(), a.rank).to(backend.device)
    backend.writer_head = head

    @torch.no_grad()
    def eval_rows():
        head.eval()
        out = []
        for r in test:
            e = backend.gist(context_embeddings(backend, r["context"], a.max_ctx))
            out.append({**r, "latent": e.to(torch.float16).cpu()})
        return evaluate(backend, out, a.seed, a.eval_rows)

    log = {"config": vars(a), "files": files, "n_train": len(train), "n_test": len(test)}
    log["eval_step0"] = eval_rows()
    print("step 0", json.dumps(log["eval_step0"]), flush=True)

    tasks = tuple(a.tasks.split(","))
    opt = torch.optim.AdamW(head.parameters(), lr=a.lr, weight_decay=0.0)
    head.train()
    t0 = time.time()
    for step in range(1, a.steps + 1):
        items = []
        for r in rng.sample(train, a.batch):
            e = backend.gist(context_embeddings(backend, r["context"], a.max_ctx), grad=True)
            task_items = examples(r, tasks)
            for _, prompt, target in rng.sample(task_items, min(2, len(task_items))):
                items.append((prompt, target, Latent(e, e.shape[0])))
        loss = batch_loss(backend, items)
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(head.parameters(), 1.0)
        opt.step()
        if step % 50 == 0:
            print(f"step {step} loss {loss.item():.4f} ({(time.time() - t0) / step:.2f}s/step)", flush=True)
    log["train_s"] = round(time.time() - t0, 1)
    log["eval_final"] = eval_rows()
    print("final", json.dumps(log["eval_final"]), flush=True)
    torch.save(head.state_dict(), os.path.join(a.out, "writer_head.pt"))
    with open(os.path.join(a.out, "train_log.json"), "w") as f:
        json.dump(log, f, indent=1)


if __name__ == "__main__":
    main()
