"""SecretBench prompts and targets for E1s (train_secret.py); pure Python, so it is testable without a GPU.

The prompts are built exactly as the forum builds them (agent._work, Forum.render), so a head
trained on them sees at test time what a forum consumer sees.
"""
from __future__ import annotations

import random
import re

from forum import prompts as P
from model.backends.base import LATENT_MARK
from benchmark.sandbox import run_tests
from benchmark.secretbench import make_project
from benchmark.tasks import private_skeleton
from benchmark.workspace import Workspace, normalize_method

CONSUMERS = ("decode", "is_record", "get_field")
SECRET_Q = ("Message: {msg}\n\nThis message is about `{cls}.encode`. What string does "
            "`encode({args})` return? Reply with the string only.")

# report templates; the vague ones do not state the format
EXPLICIT = [
    "STATUS: DONE\nThe `encode` method turns a {rec} into a record: the tag '{tag}', then {order}, joined by '{delim}'.",
    "STATUS: DONE\n`encode` is done. Records look like '{example}' (tag, then {order}, separator '{delim}').",
    "STATUS: DONE\nImplemented `encode`: it returns '{tag}' followed by {order}, all separated by '{delim}'. Values go through str().",
]
VAGUE = [
    "STATUS: DONE\n`encode` is implemented and passes its test. It turns a {rec} into a record string.",
    "STATUS: DONE\nThe `encode` method works. Call it to build {rec} records; the other methods read what it writes.",
    "STATUS: DONE\nFinished `encode`. It converts the fields of a {rec} to strings and builds the record.",
]


def project_of(pid: str):
    _, seed, i = pid.split("_")
    return make_project(int(i), int(seed))


def _sample(project):
    """(argument string, record) for the first sample of the project's encode doctest."""
    doc = project.subtask("encode").doc
    m = re.search(r">>> c\.encode\((.*)\)\n\s*'(.*)'", doc)
    return m.group(1), m.group(2)


def producer_context(project, report: str) -> list[dict]:
    """The messages a producer has seen when it posts, as in agent._work (spec=private, first attempt)."""
    st = project.subtask("encode")
    code = normalize_method(st.solution, "encode")
    implement = P.IMPLEMENT.format(spec=private_skeleton(project.skeleton, {"encode"}), forum="", name="encode",
                                   cls=project.class_name, deps="", feedback="")
    return [{"role": "system", "content": P.SYSTEM.format(agent="agent0", n=3)},
            {"role": "user", "content": implement},
            {"role": "assistant", "content": f"```python\n{code}```"},
            {"role": "user", "content": P.REPORT.format(name="encode", result="PASS (1/1)")},
            {"role": "assistant", "content": report}]


def synthetic_rows(ids, seed: int, rng: random.Random) -> list[dict]:
    rows = []
    for i in ids:
        p = make_project(i, seed)
        s = p.meta["secret"]
        rec = p.skeleton.split("Stores ")[1].split("s as strings")[0]
        tmpl = rng.choice(EXPLICIT if rng.random() < 0.5 else VAGUE)
        report = tmpl.format(rec=rec, tag=s["tag"], delim=s["delim"], order=", ".join(s["order"]), example=_sample(p)[1])
        rows.append({"project": p.pid, "anchor": "encode", "text": report, "context": producer_context(p, report),
                     "claimed": "DONE", "verified_ok": True, "vague": tmpl in VAGUE})
    return rows


def forum_block(kind: str, text: str = "") -> str:
    """The forum section of a consumer's prompt, formatted as Forum.render does for one post."""
    if kind == "none":
        return ""
    body = LATENT_MARK.format(i=0) if kind == "latent" else (text.strip() or "(empty)")
    title = "Messages from teammates" + (" (latent)" if kind == "latent" else "")
    return f"{title}:\n[post 0] from agent1 on `encode`:\n{body}\n\n"


def secret_item(project, msg: str):
    args, record = _sample(project)
    return SECRET_Q.format(msg=msg, cls=project.class_name, args=args), record


def use_item(project, name: str, block: str):
    st = project.subtask(name)
    prompt = P.IMPLEMENT.format(spec=private_skeleton(project.skeleton, {name}), forum=block, name=name,
                                cls=project.class_name,
                                deps=" It may call these methods, which teammates implement: `encode`.", feedback="")
    return prompt, f"```python\n{normalize_method(st.solution, name)}```", P.SYSTEM.format(agent="agent2", n=3)


def use_ok(project, name: str, reply: str) -> tuple[bool, str | None]:
    """Score a consumer reply as the forum's method_pass_iso does: hidden tests, other methods at reference."""
    code = normalize_method(reply, name)
    ws = Workspace(project)
    ok = bool(code) and ws.try_set(name, code, "reader") and \
        run_tests(ws.isolated(name), project.test_prelude + "\n" + project.subtask(name).hidden_test).ok
    return ok, code
