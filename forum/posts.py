"""The shared "thought forum" agents communicate through.

What is fixed, and what the experiment varies:
- Every post is stored with provenance: author, round, the subtask it concerns, and the
  workspace version of that subtask at writing time.
- `structure` decides routing. `anchored` gives one thread per method, and a reader gets
  the threads of its own method and its dependencies. `flat` is a single broadcast pool;
  readers get the most recent posts without being told what each post is about.
- `channel` decides the payload readers see: the author's text, or k latent vectors.
- `trust=attested` adds a tag written by the trusted CI to each post. The tag reports the
  visible-test result of the code at that version, and marks the post stale if the code
  has changed since.
- `control` swaps payloads at read time: `shuffle` shows another post's payload, `zero` an
  empty one, so we can tell whether a channel carries content or only format.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from forum import prompts as P
from model.backends import LATENT_MARK, Latent


@dataclass
class Post:
    pid: int
    project: str
    author: str
    round: int
    anchor: str                    # method the post is about (ground truth; hidden from readers in flat mode)
    claimed: str                   # DONE | PARTIAL | BLOCKED | UNKNOWN, as parsed from the author's message
    text: str = ""
    latent: Latent | None = None
    version: int = 0
    verified: dict | None = None   # trusted CI, visible test at write time
    truth: dict | None = None      # hidden test at write time; for analysis only, never shown
    falsified: bool = False        # DONE although the visible test failed, by fault injection or instruction
    meta: dict = field(default_factory=dict)


class Forum:
    def __init__(self, cfg, bank: list[Post], seed: int):
        self.cfg, self.bank = cfg, bank
        self.posts: list[Post] = []
        self.rng = random.Random(seed)
        self._next = len(bank)

    def write(self, post: Post) -> Post:
        post.pid = self._next
        self._next += 1
        self.posts.append(post)
        self.bank.append(post)
        return post

    def latest(self, anchor: str) -> Post | None:
        for p in reversed(self.posts):
            if p.anchor == anchor:
                return p
        return None

    def closed(self, anchor: str) -> bool:
        """Is the subtask finished as far as the team can tell? Under attestation, CI must agree."""
        p = self.latest(anchor)
        if p is None or p.claimed != "DONE":
            return False
        if self.cfg.trust in ("attested", "crosscheck"):
            v = p.verified or {}
            return bool(v.get("ok")) and (self.cfg.trust == "attested" or v.get("peer_ok") is not False)
        return True

    def ci_tag(self, p: Post, stale: bool = False) -> str:
        if self.cfg.trust == "blind" or p.verified is None:
            return ""
        v = p.verified
        tag = f" [CI: visible test {'PASS' if v.get('ok') else 'FAIL'}"
        if self.cfg.trust == "crosscheck" and "peer_ok" in v:
            tag += f"; peer tests {'PASS' if v['peer_ok'] else 'FAIL: ' + v.get('peer_brief', '')[:120]}"
        return tag + (", STALE" if stale else "") + "]"

    def select(self, reader: str, focus: str, deps: list[str]) -> list[Post]:
        if self.cfg.channel == "none":
            return []
        if self.cfg.structure == "anchored":
            picked = [self.latest(a) for a in deps + [focus]]
            picked = [p for p in picked if p is not None and p.author != reader]
        else:
            picked = [p for p in reversed(self.posts) if p.author != reader]
        return picked[: self.cfg.read_k]

    def _payload(self, post: Post):
        """Apply the content control. Returns (text, latent)."""
        ctl = self.cfg.control
        if ctl == "shuffle":
            others = [b for b in self.bank if (b.project, b.anchor) != (post.project, post.anchor)
                      and (b.latent is not None or self.cfg.channel == "text")]
            if others:
                o = self.rng.choice(others)
                return o.text, o.latent
            ctl = "zero"   # nothing to swap in yet
        if ctl == "zero":
            if self.cfg.channel == "text":
                return "(message withheld)" if self.cfg.control == "shuffle" else "", None
            return post.text, post.latent.blank()
        return post.text, post.latent

    def render(self, posts: list[Post], versions: dict[str, int]) -> tuple[str, list[Latent], list[dict]]:
        """Format posts for a prompt. Returns (block, latents, read_log)."""
        if not posts:
            return "", [], []
        entries, latents, log = [], [], []
        for p in posts:
            stale = versions.get(p.anchor, p.version) != p.version
            head = P.post_head(p.pid, p.author, p.anchor if self.cfg.structure == "anchored" else None) \
                + self.ci_tag(p, stale)
            text, lat = self._payload(p)
            if self.cfg.channel == "latent":
                body = LATENT_MARK.format(i=len(latents))
                latents.append(lat)
            else:
                body = text.strip() or "(empty)"
            entries.append((head, body))
            log.append({"pid": p.pid, "anchor": p.anchor, "author": p.author, "claimed": p.claimed,
                        "verified_ok": (p.verified or {}).get("ok"), "truth_ok": (p.truth or {}).get("ok"),
                        "truth_iso_ok": (p.truth or {}).get("iso_ok"),
                        "falsified": p.falsified, "stale": stale})
        return P.forum_section(entries, latent=self.cfg.channel == "latent"), latents, log

    def board(self, project, owner: dict[str, str]) -> str:
        """The explicit skeleton: who works on what, and the 1-bit DONE flag each author sets.

        The flag is the claim channel, and it is identical across `channel` conditions.
        Message content (what was built, how to call it) travels only through posts.
        """
        rows = []
        for s in project.subtasks:
            p = self.latest(s.name)
            if s.name in owner:
                row = f"taken by {owner[s.name]}"
            elif p is not None and p.claimed == "DONE":
                row = f"marked done by {p.author}"
                if self.cfg.trust != "blind" and p.verified is not None:
                    row += self.ci_tag(p) + ("" if self.closed(s.name) else " -> reopened")
            else:
                row = "open"
            rows.append(f"- `{s.name}`: {row}")
        return "\n".join(rows)
