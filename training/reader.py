"""E1a: learn a read-in adapter so a frozen reader can interrogate latent posts (an ablation).

    python -m training.reader --latents 'runs/e0_<id>/task1/*/latents.pt' --out runs/e1a

The model and the writer stay frozen. Only a low-rank residual map on the received vectors is
trained (model/read_adapter.py; identity at step 0, so step 0 is the training-free channel).

The objectives use the same prompts as forum/probe.py, so the evaluation measures exactly what
breakpoint interrogation asks:
- recon: rewrite the message in plain text (target: the author's text)
- anchor: which method is it about (target: the post's method)
- verified: did the code pass CI (target: the CI result, not the author's claim)
- claim: does the author say DONE

Train and eval are split by project. In the eval, "self" uses the post's own latent and "other"
a latent from a different post, scored against the true post's labels; a gain only counts if
self beats other. Accuracy is also reported on overclaims (claim=DONE, CI=FAIL), where answering
FAIL means the latent carries the truth that the text hides.
"""
from __future__ import annotations

import json

import torch

from forum import prompts as P
from forum.dump import dump_files, load_rows
from forum.probe import score
from model.backends.base import LATENT_MARK, Latent
from model.read_adapter import ReadAdapter
from training.common import arg_parser, batch_loss, fit, log, project_split, save_json, start

RECON = "Message: {msg}\n\nRewrite this message in plain text."


def examples(row, tasks):
    """(task, user_prompt, target) for one post."""
    out, msg = [], LATENT_MARK.format(i=0)
    if "recon" in tasks and row["text"].strip():
        out.append(("recon", RECON.format(msg=msg), row["text"].strip()[:400]))
    if "anchor" in tasks:
        out.append(("anchor", P.PROBE["anchor"].format(msg=msg, cls=row["class_name"], options=", ".join(row["options"])),
                    row["anchor"]))
    if "verified" in tasks:
        out.append(("verified", P.PROBE["verified"].format(msg=msg), "PASS" if row["verified_ok"] else "FAIL"))
    if "claim" in tasks:
        out.append(("claim", P.PROBE["claim"].format(msg=msg), "YES" if row["claimed"] == "DONE" else "NO"))
    return out


def _rate(xs):
    return round(sum(xs) / len(xs), 4) if xs else None


@torch.no_grad()
def evaluate(backend, rows, seed=0, max_rows=200):
    """Probe accuracy with the post's own latent ("self") and another post's ("other")."""
    import random
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
                ok = score(task, g.text, target, r["options"])
                res[task][arm].append(ok)
                if task == "verified" and r["claimed"] == "DONE" and not r["verified_ok"]:
                    over[arm].append(ok)
            if r["text"].strip():
                recon[arm].append(batch_loss(backend, [(RECON.format(msg=LATENT_MARK.format(i=0)),
                                                        r["text"].strip()[:400], lat)]).item())
    out = {k: {a: _rate(v[a]) for a in v} for k, v in res.items()}
    out["n"] = len(rows)
    pv = _rate([bool(r["verified_ok"]) for r in rows])
    pc = _rate([r["claimed"] == "DONE" for r in rows])
    out["majority"] = {"verified": max(pv, 1 - pv) if pv is not None else None,
                       "claim": max(pc, 1 - pc) if pc is not None else None,
                       "anchor": _rate([1 / len(r["options"]) for r in rows])}
    out["overclaim_reveals_fail"] = {a: _rate(v) for a, v in over.items()} | {"n": len(over["self"])}
    out["recon_loss"] = {a: (round(sum(v) / len(v), 4) if v else None) for a, v in recon.items()}
    return out


def main():
    ap = arg_parser(__doc__, out="runs/e1a", steps=600, lr=2e-4, batch=8)
    ap.add_argument("--latents", nargs="+", required=True, help="latents.pt files or globs")
    ap.add_argument("--rank", type=int, default=64)
    ap.add_argument("--tasks", default="recon,anchor,verified,claim")
    ap.add_argument("--holdout", type=float, default=0.25)
    ap.add_argument("--data", default="data/ClassEval_data.json", help="fills in method names for old dumps")
    ap.add_argument("--eval-rows", type=int, default=200)
    a = ap.parse_args()
    rng = start(a)

    files = dump_files(a.latents)
    rows = load_rows(files)
    if any(not r.get("options") for r in rows):  # dumps written before options were saved
        from benchmark.tasks import load_classeval
        info = {p.pid: (p.class_name, p.names) for p in load_classeval(a.data, min_methods=1)}
        for r in rows:
            if not r.get("options") and r["project"] in info:
                r["class_name"], r["options"] = info[r["project"]]
    rows = [r for r in rows if r.get("options")]
    train, test, test_p = project_split(rows, rng, a.holdout)
    rng.shuffle(test)
    log.info("%d files, %d posts; train %d / test %d (%d projects)", len(files), len(rows), len(train), len(test), len(test_p))

    from model.backends.hf import HFBackend
    backend = HFBackend.load(a.model)
    adapter = ReadAdapter(backend.emb.weight.shape[1], a.rank).to(backend.device)
    backend.latent_map = adapter

    run_log = {"config": vars(a), "files": files, "n_train": len(train), "n_test": len(test)}
    adapter.eval()
    run_log["eval_step0"] = evaluate(backend, test, a.seed, a.eval_rows)   # identity map = training-free channel
    log.info("step 0 %s", json.dumps(run_log["eval_step0"]))

    pool = [(p, y, r) for r in train for _, p, y in examples(r, tuple(a.tasks.split(",")))]

    def loss_fn(step):
        return batch_loss(backend, [(p, y, Latent(r["latent"], r["latent"].shape[0])) for p, y, r in rng.sample(pool, a.batch)])

    backend.model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    backend.model.train()
    adapter.train()
    run_log["train_s"] = fit(adapter.parameters(), a.steps, a.lr, loss_fn)
    backend.model.eval()
    adapter.eval()
    run_log["eval_final"] = evaluate(backend, test, a.seed, a.eval_rows)
    log.info("final %s", json.dumps(run_log["eval_final"]))
    torch.save(adapter.state_dict(), f"{a.out}/adapter.pt")
    save_json(a.out, "train_log.json", run_log)


if __name__ == "__main__":
    main()
