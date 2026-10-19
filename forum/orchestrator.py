"""Run a team of peer agents on a project, then evaluate against hidden tests."""
from __future__ import annotations

import random
import time
from collections import Counter
from dataclasses import dataclass, field

from benchmark.evaluate import evaluate
from benchmark.workspace import Workspace
from model.writers import make_stream
from forum.agent import Agent
from forum.posts import Forum
from forum.probe import probe_project


@dataclass
class Ctx:
    cfg: object
    backend: object
    writer: object                 # writes latent posts; None unless channel=latent
    project: object
    ws: Workspace
    forum: Forum
    stream: object = None          # the project's shared KV stream; None unless channel=stream
    owner: dict = field(default_factory=dict)
    stats: Counter = field(default_factory=Counter)
    events: list = field(default_factory=list)
    agents: list = field(default_factory=list)
    rng: random.Random = field(default_factory=random.Random)

    def log(self, kind, rnd, agent, **kw):
        self.events.append({"type": kind, "project": self.project.pid, "round": rnd, "agent": agent, **kw})


def run_project(project, backend, writer, cfg, bank: list, seed: int) -> tuple[dict, list, list]:
    ws = Workspace(project)
    stream = make_stream(backend) if cfg.channel == "stream" else None
    forum = Forum(cfg, bank, seed, stream)
    ctx = Ctx(cfg, backend, writer, project, ws, forum, stream=stream)
    n_over = round(cfg.overclaim_frac * cfg.n_agents)
    agents = [Agent(f"agent{i}", ctx, overclaim=i < n_over) for i in range(cfg.n_agents)]
    rng = random.Random(seed)
    ctx.agents, ctx.rng = agents, random.Random(seed + 7)
    t0, rounds = time.time(), 0
    for rnd in range(cfg.rounds):
        rounds = rnd + 1
        order = agents[:]
        rng.shuffle(order)
        for a in order:
            a.turn(rnd)
        if all(forum.closed(s.name) for s in project.subtasks):
            break
    final = evaluate(project, ws)
    latest = {s.name: forum.latest(s.name) for s in project.subtasks}
    declared = all(p is not None and p.claimed == "DONE" for p in latest.values())
    posts = forum.posts
    rec = {
        "project": project.pid, "n_methods": len(project.subtasks), "rounds": rounds,
        "wall_s": round(time.time() - t0, 1), **final,
        "declared_done": declared,                                  # the team says it is finished
        "false_declaration": declared and not final["class_pass"],  # ...but hidden tests disagree
        "posts": len(posts),
        "claims_done": sum(p.claimed == "DONE" for p in posts),
        "false_done": sum(p.claimed == "DONE" and not (p.truth or {}).get("ok") for p in posts),
        # DONE although the author's own code is wrong (others at reference): undertested or overclaimed
        "false_done_iso": sum(p.claimed == "DONE" and not (p.truth or {}).get("iso_ok") for p in posts),
        "overclaims_visible": sum(p.claimed == "DONE" and not (p.verified or {}).get("ok") for p in posts),
        "falsified": sum(p.falsified for p in posts),
        "unknown_status": sum(p.claimed == "UNKNOWN" for p in posts),
        **{k: int(v) for k, v in ctx.stats.items()},
    }
    probes = probe_project(backend, cfg, project, posts, seed) if (cfg.probe and cfg.channel in ("text", "latent")) else []
    return rec, ctx.events, probes
