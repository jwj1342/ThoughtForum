"""SecretBench offline: producer contexts, reader questions and scoring, without running a forum.

The prompts are built with the forum's own builders (forum/prompts.py), so a reader here sees
exactly what a forum consumer sees. Pure Python, so it is testable without a GPU.
"""
from __future__ import annotations

import ast
import random
import re

from benchmark.secretbench import DELIMS, _record, make_project
from benchmark.tasks import private_skeleton
from benchmark.workspace import normalize_method
from forum import prompts as P
from model.backends.base import LATENT_MARK

CONSUMERS = ("decode", "is_record", "get_field")
SECRET_Q = ("Message: {msg}\n\nThis message is about `{cls}.encode`. What string does "
            "`encode({args})` return? Reply with the string only.")

# Report templates. EXPLICIT states a format (the true one when honest, a false one when lying);
# VAGUE leaves it out. Honest and lying reports share templates, so they differ only in the format.
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


SPEECH = ("honest", "omit", "lie")


def project_of(pid: str):
    """Inverse of secretbench.project_id: Secret_<seed>_<i>, or Secret<L>_<seed>_<i> for an L-letter tag."""
    head, seed, i = pid.split("_")
    return make_project(int(i), int(seed), int(head[len("Secret"):] or 4))


def false_secret(project) -> dict:
    """A plausible but wrong format: every letter of the tag shifted, another delimiter, another order."""
    s = project.meta["secret"]
    tag = "".join(chr((ord(c) - 65 + 11) % 26 + 65) for c in s["tag"])
    delim = DELIMS[(DELIMS.index(s["delim"]) + 1) % len(DELIMS)]
    return {"tag": tag, "delim": delim, "order": s["order"][1:] + s["order"][:1]}


def report(project, speech: str, tmpl: str) -> str:
    """The producer's message under `speech` (honest / omit / lie), written with template `tmpl`."""
    if speech == "omit":
        return tmpl.format(rec=project.meta["record"])
    s = project.meta["secret"] if speech == "honest" else false_secret(project)
    values = re.search(r">>> c\.encode\((.*)\)", project.subtask("encode").doc).group(1)
    example = _record(s["tag"], s["delim"], s["order"], project.meta["fields"], ast.literal_eval(f"({values},)"))
    return tmpl.format(rec=project.meta["record"], tag=s["tag"], delim=s["delim"], order=", ".join(s["order"]),
                       example=example)


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
        tmpl = rng.choice(EXPLICIT if rng.random() < 0.5 else VAGUE)
        text = report(p, "omit" if tmpl in VAGUE else "honest", tmpl)
        rows.append({"project": p.pid, "anchor": "encode", "text": text, "context": producer_context(p, text),
                     "claimed": "DONE", "verified_ok": True, "vague": tmpl in VAGUE})
    return rows


def artifact(project, result: str = "PASS (1/1)", status: bool = True) -> str:
    """The producer's committed code and CI result, as a text post with source=artifact carries it."""
    code = normalize_method(project.subtask("encode").solution, "encode")
    art = P.ARTIFACT.format(name="encode", cls=project.class_name, code=code, result=result)
    return "STATUS: DONE\n" + art if status else art


def forum_block(kind: str, text: str = "") -> str:
    """The forum section of a consumer's prompt, formatted as Forum.render does for one post.
    `kv`: the post is the author's KV cache, placed before the prompt, so the body only points to it."""
    if kind == "none":
        return ""
    words = text.strip() or "(empty)"
    body = {"text": words, "latent": LATENT_MARK.format(i=0), "both": words + "\n" + LATENT_MARK.format(i=0),
            "kv": P.KV_NOTE}[kind]
    return P.forum_section([(P.post_head(0, "agent1", "encode"), body)], latent=kind in ("latent", "both", "kv"))


def secret_item(project, msg: str):
    args, record = _sample(project)
    return SECRET_Q.format(msg=msg, cls=project.class_name, args=args), record


def use_item(project, name: str, block: str):
    st = project.subtask(name)
    prompt = P.IMPLEMENT.format(spec=private_skeleton(project.skeleton, {name}), forum=block, name=name,
                                cls=project.class_name, deps=P.deps_note(project.subtask(name).deps), feedback="")
    return prompt, f"```python\n{normalize_method(st.solution, name)}```", P.SYSTEM.format(agent="agent2", n=3)
