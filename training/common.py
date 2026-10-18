"""Pieces shared by the training ablations (reader.py, writer.py, secret.py).

The language model stays frozen everywhere; only a small head or adapter is trained. Losses
are next-token cross-entropy on the target tokens of (prompt, target, latent) items, with the
same chat prompts the forum uses.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import time

import torch

from forum import prompts as P
from model.backends import DEFAULT_MODEL
from model.backends.base import LATENT_RE

log = logging.getLogger("training")
PLACEHOLDER = "(latent message)"


def arg_parser(doc: str, out: str, steps: int, lr: float, batch: int) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=doc, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=DEFAULT_MODEL, help="local path or HuggingFace Hub id (env LF_MODEL)")
    ap.add_argument("--out", default=out)
    ap.add_argument("--steps", type=int, default=steps)
    ap.add_argument("--lr", type=float, default=lr)
    ap.add_argument("--batch", type=int, default=batch)
    ap.add_argument("--seed", type=int, default=0)
    return ap


def start(a) -> random.Random:
    """Logging, output directory and seeds; returns the data RNG."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    os.makedirs(a.out, exist_ok=True)
    torch.manual_seed(a.seed)
    return random.Random(a.seed)


def save_json(out: str, name: str, obj):
    with open(os.path.join(out, name), "w") as f:
        json.dump(obj, f, indent=1)


def project_split(rows, rng, holdout: float = 0.25, folds: int = 0, fold: int = 0):
    """(train, test, test projects): split by project, by a holdout fraction or one of `folds` folds."""
    projects = sorted({r["project"] for r in rows})
    rng.shuffle(projects)
    test_p = set(projects[fold::folds]) if folds else set(projects[: max(1, int(len(projects) * holdout))])
    return ([r for r in rows if r["project"] not in test_p], [r for r in rows if r["project"] in test_p], test_p)


def context_embeddings(backend, context, max_ctx: int):
    """Embed a saved writer context (messages ending with the author's post), last max_ctx positions.
    Latent posts the author had read are replaced by a text placeholder."""
    msgs = [{**m, "content": LATENT_RE.sub(PLACEHOLDER, m["content"])} for m in context]
    full = torch.cat([backend.embed_chat(msgs[:-1]), backend.text_embeddings(msgs[-1]["content"] or " ")], 0)
    return full[-max_ctx:]


def build(backend, prompt, target, lat, system=P.PROBE_SYSTEM):
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    ctx = backend.embed_chat(msgs, [lat])
    t_ids = backend.tok(target + "<|im_end|>", add_special_tokens=False, return_tensors="pt").input_ids[0].to(backend.device)
    emb = torch.cat([ctx, backend.emb(t_ids[None])[0]], 0)
    labels = torch.cat([torch.full((ctx.shape[0],), -100, device=backend.device), t_ids])
    return emb, labels


def batch_loss(backend, items):
    """Mean target-token loss over items (prompt, target, latent[, system])."""
    embs, labs = zip(*(build(backend, *it) for it in items))
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


def fit(params, steps: int, lr: float, loss_fn, on_step=None, every: int = 50) -> float:
    """AdamW with gradient clipping. `loss_fn(step)` returns one batch's loss; `on_step(step)` runs
    after each update. Returns the wall time in seconds."""
    params = [p for p in params if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=lr, weight_decay=0.0)
    t0 = time.time()
    for step in range(1, steps + 1):
        loss = loss_fn(step)
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(params, 1.0)
        opt.step()
        if step % every == 0:
            log.info("step %d loss %.4f (%.2fs/step)", step, loss.item(), (time.time() - t0) / step)
        if on_step is not None:
            on_step(step)
    return round(time.time() - t0, 1)
