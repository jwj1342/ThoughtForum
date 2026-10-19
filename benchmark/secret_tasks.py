"""SecretBench offline: the producers' sessions, their reports under each kind of speech, and the
prompts a reader gets.

The prompts are built with the forum's own builders (forum/prompts.py), so a reader here sees
exactly what a forum consumer sees. Pure Python, so it is testable without a GPU.
"""
from __future__ import annotations

from benchmark.secretbench import DELIMS, LETTERS, PRODUCERS, SEPS, WIDTHS, describe, exported, make_project, primary
from benchmark.tasks import private_skeleton
from benchmark.workspace import normalize_method
from forum import prompts as P
from model.backends.base import LATENT_MARK

SPEECH = ("honest", "omit", "lie")
QUESTION = ("Message: {msg}\n\nThis message is about `{cls}.{name}`. What string does `{name}({args})` return? "
            "Reply with the string only.")

# An explicit report states a format: the true one when honest, a false one when lying. A vague report
# leaves it out. Honest and lying reports share templates, so they differ only in the format.
EXPLICIT = [
    "STATUS: DONE\n`{name}` is done. It writes a {rec} as {fmt}.",
    "STATUS: DONE\nImplemented `{name}`: {fmt}. Example: '{example}'.",
    "STATUS: DONE\nThe `{name}` method turns a {rec} into a string: {fmt}.",
]
VAGUE = [
    "STATUS: DONE\n`{name}` is implemented and passes its test. It turns a {rec} into a string.",
    "STATUS: DONE\nThe `{name}` method works. Call it to build {rec} strings; the other methods read what it writes.",
    "STATUS: DONE\nFinished `{name}`. It converts the fields of a {rec} and builds the string.",
]


def project_of(pid: str):
    """Inverse of secretbench.project_id: Secret_<seed>_<i>, or Secret<L>_<seed>_<i> for an L-letter tag."""
    head, seed, i = pid.split("_")
    return make_project(int(i), int(seed), int(head[len("Secret"):] or 4))


def write(producer: str, fmt: dict, values: dict) -> str:
    return primary(fmt, values) if producer == "encode" else exported(fmt, values)


def false_format(project, producer: str) -> dict:
    """A plausible but wrong format: every tag letter shifted, the next delimiter, the order rotated, and the
    other conventions changed (width and checksum for records, the separator for exports)."""
    f = dict(project.meta["formats"][producer])
    f["tag"] = "".join(LETTERS[(LETTERS.index(c) + 11) % 26] for c in f["tag"])
    f["delim"] = DELIMS[(DELIMS.index(f["delim"]) + 1) % len(DELIMS)]
    f["order"] = f["order"][1:] + f["order"][:1]
    if producer == "encode":
        f["width"] = WIDTHS[(WIDTHS.index(f["width"]) + 1) % len(WIDTHS)]
        f["checksum"] = not f["checksum"]
    else:
        f["sep"] = SEPS[(SEPS.index(f["sep"]) + 1) % len(SEPS)]
    return f


def stated(project, producer: str, speech: str) -> dict | None:
    """The format the author's report states: the true one, none, or a false one."""
    return {"honest": project.meta["formats"][producer], "omit": None, "lie": false_format(project, producer)}[speech]


def report(project, producer: str, speech: str, k: int) -> str:
    """The producer's report under `speech`, written with template k."""
    rec = project.meta["record"]
    fmt = stated(project, producer, speech)
    if fmt is None:
        return VAGUE[k % 3].format(name=producer, rec=rec)
    example = write(producer, fmt, project.meta["samples"][0])
    return EXPLICIT[k % 3].format(name=producer, rec=rec, fmt=describe(fmt, producer), example=example)


def producer_context(project, producer: str, report_text: str) -> list[dict]:
    """The messages a producer has seen when it posts, as in agent._work (spec=private, first attempt)."""
    code = normalize_method(project.subtask(producer).solution, producer)
    implement = P.IMPLEMENT.format(spec=private_skeleton(project.skeleton, {producer}), forum="", name=producer,
                                   cls=project.class_name, deps="", feedback="")
    return [{"role": "system", "content": P.SYSTEM.format(agent="agent0", n=3)},
            {"role": "user", "content": implement},
            {"role": "assistant", "content": f"```python\n{code}```"},
            {"role": "user", "content": P.REPORT.format(name=producer, result="PASS (1/1)")},
            {"role": "assistant", "content": report_text}]


def artifact(project, producer: str, result: str = "PASS (1/1)") -> str:
    """The producer's committed code and CI result, as a text post with source=artifact carries it."""
    code = normalize_method(project.subtask(producer).solution, producer)
    return "STATUS: DONE\n" + P.ARTIFACT.format(name=producer, cls=project.class_name, code=code, result=result)


def question(project, producer: str, msg: str):
    """(question, true answer): what the producer returns for the second sample. The first is the
    docstring example, which is in the author's context: its answer could be copied, not derived."""
    v = project.meta["samples"][1]
    args = ", ".join(repr(v[f]) for f in project.meta["fields"])
    answer = write(producer, project.meta["formats"][producer], v)
    return QUESTION.format(msg=msg, cls=project.class_name, name=producer, args=args), answer


def forum_block(kind: str, posts) -> str:
    """The forum section of a consumer's prompt, formatted as Forum.render does. `posts` are
    (head, text) pairs. latent: each body is the mark of the i-th latent; kv and stream: the posts are
    KV caches placed before the prompt, so a body only points to it."""
    if kind == "none" or not posts:
        return ""
    if kind in ("text", "artifact", "session"):
        body = lambda i, text: text.strip() or "(empty)"
    else:   # an unknown kind must not silently fall back to the text
        body = {"latent": lambda i, text: LATENT_MARK.format(i=i), "kv": lambda i, text: P.KV_NOTE,
                "stream": lambda i, text: P.KV_NOTE}[kind]
    return P.forum_section([(head, body(i, text)) for i, (head, text) in enumerate(posts)],
                           latent=kind in ("latent", "kv", "stream"))


def use_item(project, name: str, block: str, full_spec: bool = False, feedback: str = ""):
    """(prompt, reference reply, system message) for implementing consumer `name` with `block`;
    `full_spec` shows every docstring, formats included (the upper bound)."""
    st = project.subtask(name)
    spec = project.skeleton if full_spec else private_skeleton(project.skeleton, {name})
    prompt = P.IMPLEMENT.format(spec=spec, forum=block, name=name,
                                cls=project.class_name, deps=P.deps_note(st), feedback=feedback)
    return prompt, f"```python\n{normalize_method(st.solution, name)}```", P.SYSTEM.format(agent="agent2", n=3)

