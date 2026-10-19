from __future__ import annotations

import dataclasses
import os
from dataclasses import dataclass

from model.backends import DEFAULT_MODEL
from model.backends.base import TEMPERATURE

CHOICES = {
    # mock: no model (tests). hf: a local HuggingFace model, needed for latent posts. api: any
    # OpenAI-compatible endpoint (text only), key from the environment variable api_key_env.
    "backend": ("mock", "hf", "api"),
    # what a forum post carries to readers. stream: the forum is one append-only KV cache; each post is
    # the author's session encoded on top of all posts before it, and readers generate after the
    # segments of the posts they get (model/kv_posts.py, KVStream)
    "channel": ("none", "text", "latent", "stream"),
    # how posts are routed: threads keyed by method name, or one broadcast pool without topics
    "structure": ("anchored", "flat"),
    # blind: readers get posts as written. attested: the trusted CI tags each post with what
    # the code actually does, and a subtask counts as closed only if CI agrees with the claim.
    # crosscheck: attested, plus another agent writes tests for the method from its docstring
    # alone (never from the author's message); closing also needs those tests to pass in CI.
    "trust": ("blind", "attested", "crosscheck"),
    # report: latent of the author's own message. artifact: latent of the code plus CI log,
    # computed by the trusted harness, so the author cannot shape its content. With the text
    # channel, artifact posts the code and CI log as text (the explicit "read my code" baseline).
    # session (text only): the author's whole session as text, what a stream post holds, minus the
    # forum posts it read (those are posts of their own).
    "source": ("report", "artifact", "session"),
    # content controls applied to every post a reader receives: another post's payload, or an empty one
    "control": ("none", "shuffle", "zero"),
    # always: the harness rewrites the STATUS line of overclaiming agents to DONE (crude; the body may
    # still describe the failure). pressure: only prompt them. deceive: they are told to write a coherent
    # DONE message whatever the test said, so a hidden failure leaves no trace in the text itself.
    # mislead: claims stay honest, but the message misstates the method's interface or output format,
    # plausibly and specifically (a saboteur; tests whether a latent post follows words or knowledge).
    "overclaim_mode": ("always", "pressure", "deceive", "mislead"),
    "choose": ("llm", "greedy"),
    # full: every agent sees all docstrings. private: an agent sees only the docstring of the method it
    # works on; the others show just their signatures, so callers must learn interfaces from the forum.
    "spec": ("full", "private"),
}


@dataclass
class RunConfig:
    backend: str = "mock"
    model: str = DEFAULT_MODEL     # hf: local path or Hub id (env LF_MODEL); api: the provider's model name
    enable_thinking: bool = False
    mock_p_correct: float = 0.6
    api_base: str = os.environ.get("LF_API_BASE", "")   # e.g. https://api.openai.com/v1
    api_key_env: str = "LF_API_KEY"   # name of the environment variable holding the key (never the key itself)
    api_extra: str = ""               # JSON merged into each request, e.g. '{"enable_thinking": false}'
    reader_adapter: str = ""       # path to a trained read-in adapter (training/reader.py); "" = training-free
    writer_head: str = ""          # gist writer: "random:16" (untrained, the method) or a trained head's path; "" = chunk means

    tasks: str = "toy"
    data_path: str = "data/ClassEval_data.json"
    valid_ids: str = "data/classeval_valid.json"
    min_methods: int = 3
    spec: str = "full"

    n_agents: int = 3
    rounds: int = 8
    max_attempts: int = 2          # implement-test cycles before an agent releases a subtask
    choose: str = "llm"
    deps_first: bool = True        # offer methods whose dependencies are closed first (others only if none are)
    memory: bool = False           # an agent sees its own last code for dependencies it wrote itself

    channel: str = "text"
    structure: str = "anchored"
    trust: str = "blind"
    source: str = "report"
    control: str = "none"
    read_k: int = 4                # posts a reader receives per prompt
    latent_k: int = 16             # vectors per latent post

    overclaim_frac: float = 0.0
    overclaim_mode: str = "always"

    max_new_tokens: int = 640
    temperature: float = TEMPERATURE   # Qwen3's sampling defaults (top-p 0.95, top-k 20); 0 = greedy
    seed: int = 0
    probe: bool = True
    save_latents: bool = False
    out: str = "runs/debug"

    def validate(self) -> "RunConfig":
        for k, allowed in CHOICES.items():
            if getattr(self, k) not in allowed:
                raise ValueError(f"{k}={getattr(self, k)!r} not in {allowed}")
        if self.channel == "none" and self.control != "none":
            raise ValueError("controls need a channel")
        if self.source == "artifact" and self.channel == "none":
            raise ValueError("source=artifact needs a channel")
        if self.backend == "api" and self.channel in ("latent", "stream"):
            raise ValueError("latent posts need a local model: use --backend hf (the api backend is text only)")
        if self.source == "session" and self.channel != "text":
            raise ValueError("source=session is the text version of a stream post: channel=text")
        if self.channel == "stream" and self.source != "report":
            raise ValueError("stream posts are the author's own session: source=report")
        return self

    def replace(self, **kw) -> "RunConfig":
        return dataclasses.replace(self, **kw).validate()

    def tag(self) -> str:
        t = f"{self.channel}-{self.structure}-{self.trust}"
        if self.spec != "full":
            t += f"-spec_{self.spec}"
        if self.memory:
            t += "-mem"
        if self.source != "report":
            t += f"-{self.source}"
        if self.control != "none":
            t += f"-ctl_{self.control}"
        if self.reader_adapter:
            t += "-ra"
        if self.writer_head:
            t += "-wh"
        if self.overclaim_frac:
            t += f"-oc{self.overclaim_frac:g}{self.overclaim_mode[0]}"
        return t
