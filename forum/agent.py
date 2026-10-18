"""A role-free peer agent: pick an open method, read the forum, implement, test, post."""
from __future__ import annotations

import ast
import random
import re

from forum import prompts as P
from forum.posts import Post
from benchmark.sandbox import TestResult, run_tests
from benchmark.tasks import private_skeleton
from benchmark.workspace import normalize_method

_STATUS = re.compile(r"STATUS:\s*(DONE|PARTIAL|BLOCKED)", re.I)


def parse_status(text: str) -> str:
    m = _STATUS.search(text or "")
    return m.group(1).upper() if m else "UNKNOWN"


def force_done(text: str) -> str:
    if _STATUS.search(text or ""):
        return _STATUS.sub("STATUS: DONE", text, count=1)
    return "STATUS: DONE\n" + (text or "")


def is_degenerate(text: str) -> bool:
    """Generation broke down: stray think tags, or a short phrase repeated over and over."""
    t = text or ""
    if "</think>" in t or "<think>" in t:
        return True
    words = t.split()
    return len(words) >= 40 and len(set(words[-40:])) <= 4


def extract_test_class(text: str) -> str | None:
    """The first fenced block that parses and defines a unittest.TestCase subclass."""
    for block in re.findall(r"```(?:python|py)?\s*\n(.*?)```", text or "", re.S) or [text or ""]:
        try:
            tree = ast.parse(block)
        except SyntaxError:
            continue
        if any(isinstance(n, ast.ClassDef) and "TestCase" in ast.unparse(n.bases[0] if n.bases else n) for n in tree.body):
            return block
    return None


def pick_option(text: str, options: list[str]) -> str | None:
    t = (text or "").strip().strip("`'\". ")
    if t in options:
        return t
    hits = [o for o in options if re.search(rf"(?<![\w]){re.escape(o)}(?![\w])", text or "")]
    return max(hits, key=len) if hits else None


class Agent:
    def __init__(self, name: str, ctx, overclaim: bool = False):
        self.name, self.ctx, self.overclaim = name, ctx, overclaim
        cfg = ctx.cfg
        self.system = P.SYSTEM.format(agent=name, n=cfg.n_agents)
        if overclaim and cfg.overclaim_mode == "pressure":
            self.system += P.PRESSURE
        self.current: str | None = None
        self.attempt = 0
        self.last: dict[str, tuple[str, str]] = {}   # method -> (code, visible result)

    def _spec(self, keep) -> str:
        sk = self.ctx.project.skeleton
        return sk if self.ctx.cfg.spec == "full" else private_skeleton(sk, keep)

    # ---- one turn -------------------------------------------------------------------
    def turn(self, rnd: int):
        c = self.ctx
        if self.current is None:
            options = [s.name for s in c.project.subtasks if not c.forum.closed(s.name) and s.name not in c.owner]
            if not options:
                c.log("idle", rnd, self.name)
                return
            if c.cfg.deps_first:
                ready = [o for o in options if all(c.forum.closed(d) for d in c.project.subtask(o).deps)]
                # deps_wait: rather than start a method blind, wait while a teammate is still writing
                # one of its dependencies (no deadlock: only waits on dependencies someone owns)
                pending = {d for o in options for d in c.project.subtask(o).deps if not c.forum.closed(d)}
                if not ready and c.cfg.deps_wait and pending & set(c.owner):
                    c.log("wait", rnd, self.name, on=sorted(pending & set(c.owner)))
                    return
                options = ready or options
            self.current, self.attempt = self._choose(rnd, options), 0
            c.owner[self.current] = self.name
        self._work(rnd, c.project.subtask(self.current))

    def _llm(self, msgs, latents, purpose, meta, max_new_tokens):
        c = self.ctx
        g = c.backend.chat(msgs, latents, purpose=purpose, meta=meta, max_new_tokens=max_new_tokens,
                           temperature=c.cfg.temperature)
        c.stats["prompt_tokens"] += g.prompt_tokens
        c.stats["gen_tokens"] += g.gen_tokens
        c.stats["calls"] += 1
        c.stats["degenerate"] += is_degenerate(g.text)
        if latents:
            c.stats["calls_with_latents"] += 1
            c.stats["degenerate_with_latents"] += is_degenerate(g.text)
        return g

    def peer_check(self, rnd, st, post):
        """Zero-trust verification: write tests from the docstring only, let CI run them."""
        c = self.ctx
        msgs = [{"role": "system", "content": self.system},
                {"role": "user", "content": P.PEER_TEST.format(spec=self._spec({st.name}), name=st.name, cls=c.project.class_name)}]
        g = self._llm(msgs, [], "peer_test", {"subtask": st, "agent": self.name}, 640)
        tests = extract_test_class(g.text)
        if tests is None:
            post.verified.update(peer_ok=None, peer_brief="no valid test class", peer_by=self.name)
            c.log("peer", rnd, self.name, method=st.name, pid=post.pid, valid_tests=False)
            return
        res = run_tests(c.ws.assemble(), c.project.test_prelude + "\n" + tests)
        ref = run_tests(c.ws.reference(), c.project.test_prelude + "\n" + tests)  # analysis only: are the tests right?
        post.verified.update(peer_ok=res.ok, peer_brief=res.brief()[:200], peer_by=self.name, peer_valid=ref.ok)
        c.stats["peer_checks"] += 1
        c.stats["peer_fail"] += not res.ok
        c.stats["peer_invalid"] += not ref.ok
        c.stats["peer_catch"] += (not res.ok) and ref.ok and not (post.truth or {}).get("iso_ok")
        c.log("peer", rnd, self.name, method=st.name, pid=post.pid, valid_tests=True, peer_ok=res.ok,
              tests_valid_on_reference=ref.ok, author_iso_ok=(post.truth or {}).get("iso_ok"), brief=res.brief()[:200])

    def _choose(self, rnd, options):
        c = self.ctx
        if c.cfg.choose == "greedy" or len(options) == 1:
            ready = [o for o in options if all(c.forum.closed(d) for d in c.project.subtask(o).deps)]
            pick, how, raw = (ready or options)[0], "greedy", ""
        else:
            recent = [p for p in reversed(c.forum.posts) if p.author != self.name][: c.cfg.read_k] \
                if c.cfg.channel != "none" else []
            block, latents, _ = c.forum.render(recent, c.ws.version)
            msgs = [{"role": "system", "content": self.system},
                    {"role": "user", "content": P.CHOOSE.format(spec=self._spec(()), board=c.forum.board(c.project, c.owner),
                                                                forum=block, options=", ".join(f"`{o}`" for o in options))}]
            g = self._llm(msgs, latents, "choose", {"options": options}, 24)
            pick, how, raw = pick_option(g.text, options), "llm", g.text[:80]
            if pick is None:
                pick, how = options[0], "fallback"
        c.log("choose", rnd, self.name, method=pick, how=how, options=options, raw=raw if how != "greedy" else "")
        return pick

    def _work(self, rnd, st):
        c, cfg = self.ctx, self.ctx.cfg
        posts = c.forum.select(self.name, st.name, st.deps)
        block, latents, read_log = c.forum.render(posts, c.ws.version)
        deps = (" It may call these methods, which teammates implement: "
                + ", ".join(f"`{d}`" for d in st.deps) + ".") if st.deps else ""
        fb = P.FEEDBACK.format(code=self.last[st.name][0], result=self.last[st.name][1]) if st.name in self.last else ""
        if cfg.memory:   # what the agent itself wrote earlier; without it, agents forget their own work
            fb = "".join(P.OWN.format(name=d, code=self.last[d][0]) for d in st.deps if d in self.last) + fb
        msgs = [{"role": "system", "content": self.system},
                {"role": "user", "content": P.IMPLEMENT.format(spec=self._spec({st.name}), forum=block, name=st.name,
                                                               cls=c.project.class_name, deps=deps, feedback=fb)}]
        g = self._llm(msgs, latents, "implement", {"subtask": st, "agent": self.name, "attempt": self.attempt},
                      cfg.max_new_tokens)
        code = normalize_method(g.text, st.name)
        wrote = code is not None and c.ws.try_set(st.name, code, self.name)
        module = c.ws.assemble()
        if wrote:
            vis = run_tests(module, c.project.test_prelude + "\n" + st.visible_test)
        else:
            vis = TestResult(first_error=f"no valid definition of `{st.name}` was found in the reply")
        hid = run_tests(module, c.project.test_prelude + "\n" + st.hidden_test)
        iso = run_tests(c.ws.isolated(st.name), c.project.test_prelude + "\n" + st.hidden_test)
        self.attempt += 1
        self.last[st.name] = (code or g.text[-1500:], vis.brief())

        # The instruction goes to every report of a deceiving agent, pass or fail, so its honest and
        # dishonest DONE posts differ only in the test result, not in the prompt.
        deceive = self.overclaim and cfg.overclaim_mode == "deceive"
        mislead = self.overclaim and cfg.overclaim_mode == "mislead"
        report = P.REPORT.format(name=st.name, result=vis.brief()) + (P.DECEIVE.format(name=st.name) if deceive else "") \
            + (P.MISLEAD.format(name=st.name) if mislead else "")
        rep_msgs = msgs + [{"role": "assistant", "content": g.text}, {"role": "user", "content": report}]
        rep = self._llm(rep_msgs, latents, "report",
                        {"subtask": st, "visible_ok": vis.ok, "pressure": self.overclaim}, 160)
        text, claimed, falsified = rep.text, parse_status(rep.text), False
        if self.overclaim and cfg.overclaim_mode == "always" and claimed != "DONE":
            text, claimed, falsified = force_done(text), "DONE", True
        elif deceive and not vis.ok:
            # The model wrote the lie itself; the harness only makes sure the claim is DONE.
            falsified = True
            if claimed != "DONE":
                text, claimed = force_done(text), "DONE"

        lat = None
        if cfg.channel == "latent":
            meta = {"anchor": st.name, "visible_ok": vis.ok}
            if cfg.source == "report":
                enc_msgs = rep_msgs + [{"role": "assistant", "content": text}]
                lat = c.backend.encode(rep_msgs, text, latents, k=cfg.latent_k, purpose="report", meta=meta)
            else:
                art = P.ARTIFACT.format(name=st.name, cls=c.project.class_name,
                                        code=c.ws.code.get(st.name, "(no code)"), result=vis.brief())
                art_msgs = [{"role": "system", "content": P.ARTIFACT_SYSTEM},
                            {"role": "user", "content": "Read the artifact."}]
                enc_msgs = art_msgs + [{"role": "assistant", "content": art}]
                lat = c.backend.encode(art_msgs, art, (), k=cfg.latent_k, purpose="artifact", meta=meta)
            c.stats["latent_bytes"] += lat.nbytes
            c.stats["payload_slots"] += lat.k
        elif cfg.channel == "text":
            if cfg.source == "artifact":   # post the committed code and CI log, keep only the STATUS line
                text = f"STATUS: {claimed}\n" + P.ARTIFACT.format(name=st.name, cls=c.project.class_name,
                                                                code=c.ws.code.get(st.name, "(no code)"), result=vis.brief())
            c.stats["payload_slots"] += c.backend.count_tokens(text)

        post = c.forum.write(Post(0, c.project.pid, self.name, rnd, st.name, claimed, text, lat,
                                  version=c.ws.version[st.name], verified=vis.to_dict(),
                                  truth={**hid.to_dict(), "iso_ok": iso.ok}, falsified=falsified,
                                  meta={"overclaimer": self.overclaim,
                                        # the writer's context, kept only for offline training of a writer
                                        **({"context": enc_msgs} if lat is not None and cfg.save_latents else {})}))
        if cfg.trust == "crosscheck" and claimed == "DONE" and vis.ok:
            peers = [a for a in c.agents if a is not self]
            if peers:
                c.rng.choice(peers).peer_check(rnd, st, post)
        released = claimed == "DONE" or self.attempt >= cfg.max_attempts
        c.log("work", rnd, self.name, method=st.name, attempt=self.attempt, wrote=wrote, visible=vis.brief()[:200],
              visible_ok=vis.ok, hidden_ok=hid.ok, iso_ok=iso.ok, hidden_passed=hid.passed, hidden_total=hid.total,
              claimed=claimed, falsified=falsified, overclaimer=self.overclaim, pid=post.pid, read=read_log,
              report=text[:400], released=released)
        if released:
            c.owner.pop(st.name, None)
            self.current = None
