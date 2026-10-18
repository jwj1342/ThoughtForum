"""E1w: train the writer head instead of the reader (an ablation; the method itself is untrained).

    python -m training.writer --latents 'runs/e0p_<id>/task1/*/latents.pt' --out runs/e1w

E1a trained the reader and kept the chunk-mean writer. It recovered coarse state but not which
method a post was about, which pointed at the writer: pooling throws instance content away.
Here the reader stays frozen and stock, and the gist writer's head (k queries plus a residual
map, model/hf_writers.py) is trained instead. The head belongs to the protocol and runs on
trusted inference, so an agent cannot swap in its own encoder.

Only the k query positions need gradients: the context is run once without them and handed
over as a KV cache. Objectives and evaluation are those of E1a (training/reader.py). The
verified target is the CI result, so the writer is trained to carry the truth even when the
message lies.

Limitation: saved contexts have the latents their author read replaced by a text placeholder,
so the head is trained without injected latents in its context.
"""
from __future__ import annotations

import json

import torch

from forum.dump import dump_files, load_rows
from model.backends.base import Latent
from training.common import arg_parser, batch_loss, context_embeddings, fit, log, project_split, save_json, start
from training.reader import evaluate, examples


def main():
    ap = arg_parser(__doc__, out="runs/e1w", steps=1500, lr=5e-4, batch=4)
    ap.add_argument("--latents", nargs="+", required=True, help="latents.pt files or globs (rows need 'context')")
    ap.add_argument("--k", type=int, default=16)
    ap.add_argument("--rank", type=int, default=64)
    ap.add_argument("--max-ctx", type=int, default=3072)
    ap.add_argument("--tasks", default="recon,anchor,verified,claim")
    ap.add_argument("--holdout", type=float, default=0.25)
    ap.add_argument("--folds", type=int, default=0, help="cross-fitting: hold out fold --fold of this many")
    ap.add_argument("--fold", type=int, default=0)
    ap.add_argument("--eval-rows", type=int, default=200)
    a = ap.parse_args()
    rng = start(a)

    files = dump_files(a.latents)
    rows = [r for r in load_rows(files) if r.get("context") and r.get("options") and r["text"].strip()]
    train, test, test_p = project_split(rows, rng, a.holdout, a.folds, a.fold)
    save_json(a.out, "test_projects.json", sorted(test_p))   # for a clean forum run: --tasks classeval:@<this file>
    rng.shuffle(test)
    test = test[: a.eval_rows]
    log.info("%d files, %d posts with context; train %d / test %d (%d projects)",
             len(files), len(rows), len(train), len(test), len(test_p))

    from model.backends.hf import HFBackend
    from model.hf_writers import GistWriter, random_head
    backend = HFBackend.load(a.model)
    head = random_head(backend.emb, a.k, a.seed, a.rank).to(backend.device)
    writer = GistWriter(backend, head)

    @torch.no_grad()
    def eval_rows():
        head.eval()
        out = [{**r, "latent": writer.gist(context_embeddings(backend, r["context"], a.max_ctx)).to(torch.float16).cpu()}
               for r in test]
        return evaluate(backend, out, a.seed, a.eval_rows)

    run_log = {"config": vars(a), "files": files, "n_train": len(train), "n_test": len(test)}
    run_log["eval_step0"] = eval_rows()
    log.info("step 0 %s", json.dumps(run_log["eval_step0"]))

    tasks = tuple(a.tasks.split(","))

    def loss_fn(step):
        items = []
        for r in rng.sample(train, a.batch):
            e = writer.gist(context_embeddings(backend, r["context"], a.max_ctx), grad=True)
            task_items = examples(r, tasks)
            for _, prompt, target in rng.sample(task_items, min(2, len(task_items))):
                items.append((prompt, target, Latent(e, e.shape[0])))
        return batch_loss(backend, items)

    head.train()
    run_log["train_s"] = fit(head.parameters(), a.steps, a.lr, loss_fn)
    run_log["eval_final"] = eval_rows()
    log.info("final %s", json.dumps(run_log["eval_final"]))
    torch.save(head.state_dict(), f"{a.out}/writer_head.pt")
    save_json(a.out, "train_log.json", run_log)


if __name__ == "__main__":
    main()
