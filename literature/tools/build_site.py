#!/usr/bin/env python3
"""Validate index.csv and bundle it (plus the markdown documents) into assets/data.js.

index.csv is the single source of truth. literature_review.html loads
assets/data.js, so the page works when opened directly via file:// (no server).
Also bundled: literature_review.md, research_directions.md, coding_focus.md, and ../doc/research_notes.md (+ ../doc/RP.md)
(each direction doc with its .json map data), incident/*.md and deep_read/<id>.md
(one deep-reading note per index id).

Usage (from paper/):  python3 tools/build_site.py [--strict]
"""
import argparse
import csv
import datetime as dt
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

COLUMNS = [
    "id", "short_name", "title", "authors", "first_author", "date",
    "venue", "venue_status", "venue_evidence", "arxiv_id", "paper_url", "pdf_file",
    "summary_zh", "contribution_types", "core_contribution_zh",
    "category", "subcategory", "secondary_categories", "channel", "training", "heterogeneous",
    "code_url", "code_open", "data_url", "data_open",
    "relevance", "in_window", "tags", "notes", "verified",
]
REQUIRED = ["id", "title", "date", "venue", "summary_zh", "contribution_types",
            "category", "channel", "relevance", "in_window"]

# Taxonomy shown on the page; order = display order.
TAXONOMY = [
    {"code": "latent-state", "zh": "隐状态 / Latent 通信", "en": "Latent & hidden-state communication", "tier": "core",
     "desc": "Agent 之间直接交换 hidden state、activation、latent thought、embedding 或 soft token，而非解码成文字。"},
    {"code": "kv-cache", "zh": "KV-Cache 通信", "en": "KV-cache communication", "tier": "core",
     "desc": "通过 KV-cache 传递或共享语义（cache-to-cache、共享 latent working memory、跨模型 KV 迁移）。"},
    {"code": "parameter", "zh": "参数层通信", "en": "Parameter-level communication", "tier": "core",
     "desc": "以权重 / LoRA / adapter / 生成参数为载体传递知识或行为，包括经蒸馏的 subliminal 传递。"},
    {"code": "compressed-lang", "zh": "压缩 / 涌现语言", "en": "Compressed & emergent protocols", "tier": "adjacent",
     "desc": "Token 层面但非人类可读的协议：压缩消息、涌现语言、通信效率优化、neuralese 漂移。"},
    {"code": "no-message", "zh": "无消息协调", "en": "Coordination without messages", "tier": "adjacent",
     "desc": "不发消息也能协调：Theory of Mind、Schelling / focal point、convention、同权重自我识别、默契合谋。"},
    {"code": "covert", "zh": "隐蔽信道 / 合谋", "en": "Covert channels & collusion", "tier": "adjacent",
     "desc": "文字为载体但含义被隐藏：steganography、encoded reasoning、secret collusion、subliminal signal 及其检测。"},
    {"code": "stigmergy", "zh": "共享记忆 / Stigmergy", "en": "Shared memory & stigmergy", "tier": "adjacent",
     "desc": "通过修改共享环境沟通：blackboard、共享记忆、公共 wiki / 记事本、跨实例笔记导致的行为漂移。"},
    {"code": "coding-mas", "zh": "多 Agent 编程（场景）", "en": "Multi-agent coding (scenario)", "tier": "adjacent",
     "desc": "多 agent 协作完成编程任务的系统、benchmark、失败分析与训练方法；通信本身仍是文本，作为隐式通信研究的落地场景收录。"},
    {"code": "latent-reasoning-bg", "zh": "单体 Latent 推理（背景）", "en": "Single-agent latent reasoning", "tier": "background",
     "desc": "单个模型在连续 latent 空间推理（Coconut 等），为多 agent latent 通信提供技术底座。"},
]
CATEGORIES = [t["code"] for t in TAXONOMY]

ENUMS = {
    "venue_status": {"published", "accepted", "preprint", "workshop", "report"},
    "contribution_types": {"method", "benchmark", "dataset", "metric", "empirical", "theory",
                           "survey", "position", "system", "report"},
    "category": set(CATEGORIES),
    "secondary_categories": set(CATEGORIES),
    "channel": {"hidden-state", "kv-cache", "embedding", "soft-token", "parameter", "logits",
                "compressed-text", "stego-text", "natural-text", "shared-env", "none"},
    "training": {"training-free", "SFT", "RL", "other", "n/a"},
    "heterogeneous": {"yes", "no", "n/a"},
    "code_open": {"yes", "no", "announced"},
    "data_open": {"yes", "no", "announced", "n/a"},
    "relevance": {"core", "adjacent", "background"},
    "in_window": {"yes", "no"},
}
MULTI = {"contribution_types", "secondary_categories", "channel", "tags"}

# Spectrum from most explicit to most implicit; drives the "channel spectrum" bar.
CHANNEL_SPECTRUM = [
    ("natural-text", "自然语言"), ("compressed-text", "压缩 token"), ("stego-text", "隐写文本"),
    ("shared-env", "共享环境"), ("soft-token", "Soft token"), ("embedding", "Embedding"),
    ("logits", "Logits"), ("hidden-state", "Hidden state"), ("kv-cache", "KV-cache"),
    ("parameter", "参数"), ("none", "无信道"),
]


def split_multi(value):
    return [v.strip() for v in value.split(";") if v.strip()]


def load_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            sys.exit(f"index.csv is missing columns: {missing}")
        return list(reader)


def validate(rows):
    errors, warnings = [], []
    seen = set()
    for i, r in enumerate(rows, start=2):  # header is line 1
        rid = r["id"].strip() or f"<line {i}>"
        if rid in seen:
            errors.append(f"{rid}: duplicate id")
        seen.add(rid)
        for col in REQUIRED:
            if not r[col].strip():
                errors.append(f"{rid}: empty required field '{col}'")
        if r["date"] and not re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", r["date"].strip()):
            errors.append(f"{rid}: bad date '{r['date']}'")
        for col, allowed in ENUMS.items():
            vals = split_multi(r[col]) if col in MULTI else ([r[col].strip()] if r[col].strip() else [])
            for v in vals:
                if v not in allowed:
                    errors.append(f"{rid}: '{col}' has invalid value '{v}'")
        if r["code_open"] == "yes" and not r["code_url"].strip():
            errors.append(f"{rid}: code_open=yes but code_url empty")
        # PDFs are not in git (tools/fetch_pdfs.py downloads them): check only once they are there
        if r["pdf_file"].strip() and (ROOT / "pdf").is_dir() and not (ROOT / r["pdf_file"].strip()).is_file():
            warnings.append(f"{rid}: pdf_file not found: {r['pdf_file']}")
    return errors, warnings


def read_md(rel):
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def read_notes(ids):
    """deep_read/<id>.md -> {id: markdown}; files whose stem is not an index id are reported."""
    notes, warnings = {}, []
    d = ROOT / "deep_read"
    for p in sorted(d.glob("*.md")) if d.is_dir() else []:
        if p.stem.startswith("_") or p.stem.lower() == "readme":
            continue
        if p.stem in ids:
            notes[p.stem] = p.read_text(encoding="utf-8")
        else:
            warnings.append(f"deep_read/{p.name}: no index.csv row with id '{p.stem}'")
    return notes, warnings


def check_links(docs, ids, notes):
    """Markdown links (#paper:<id>) must hit an index row, (#note:<id>) a deep_read note."""
    warnings = []
    for name, md in docs.items():
        for kind, ref in sorted(set(re.findall(r"\(#(paper|note):([^)\s]+)\)", md))):
            if ref not in (ids if kind == "paper" else notes):
                warnings.append(f"{name}: #{kind}:{ref} does not resolve")
    return warnings


def appendix(title, md):
    """Append a standalone markdown doc under one '## title' heading, demoting its own headings by one level."""
    if not md:
        return ""
    body = re.sub(r"^(#{1,5}) ", lambda m: "#" + m.group(1) + " ", md, flags=re.M)
    body = re.sub(r"^## [^\n]*\n", "", body, count=1)  # drop the doc's own (demoted) title line
    return f"\n\n---\n\n## {title}\n\n" + body


def split_method(md, heading="检索方法"):
    """Pull the methodology section (## ...检索方法...) out of the review for its own tab."""
    m = re.search(rf"^## [^\n]*{heading}[^\n]*$", md, flags=re.M)
    if not m:
        return ""
    nxt = re.search(r"^## ", md[m.end():], flags=re.M)
    return md[m.start(): m.end() + nxt.start()] if nxt else md[m.start():]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = ap.parse_args()

    rows = load_rows(ROOT / "index.csv")
    errors, warnings = validate(rows)
    ids = {r["id"].strip() for r in rows}
    notes, note_warnings = read_notes(ids)
    docs = {
        "literature_review.md": read_md("literature_review.md"),
        "research_directions.md": read_md("research_directions.md"),
        "coding_focus.md": read_md("coding_focus.md"),
        "coding_infra.md": read_md("coding_infra.md"),
        "forum_focus.md": read_md("../doc/research_notes.md"),
        "incident/openai_hf_2026.md": read_md("incident/openai_hf_2026.md"),
        **{f"deep_read/{k}.md": v for k, v in notes.items()},
    }
    warnings += note_warnings + check_links(docs, ids, notes)
    maps = {}
    for name in ("research_directions.json", "coding_directions.json"):
        f = ROOT / name
        try:
            maps[name] = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else []
        except json.JSONDecodeError as e:
            errors.append(f"{name}: {e}")
            maps[name] = []
    for w in warnings:
        print("WARN ", w)
    for e in errors:
        print("ERROR", e)
    if errors or (args.strict and warnings):
        sys.exit(f"{len(errors)} error(s), {len(warnings)} warning(s); data.js not written")

    papers = [{c: r[c].strip() for c in COLUMNS} for r in rows]
    review = docs["literature_review.md"]
    bundle = {
        "built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "taxonomy": TAXONOMY,
        "spectrum": [{"code": c, "zh": z} for c, z in CHANNEL_SPECTRUM],
        "columns": COLUMNS,
        "papers": papers,
        "reviewMd": review,
        "methodMd": split_method(review),
        "incidentMd": docs["incident/openai_hf_2026.md"],
        "sourcesMd": read_md("incident/sources.md"),
        "directionsMd": docs["research_directions.md"],
        "directionsMap": maps["research_directions.json"],
        "codingMd": docs["coding_focus.md"] + appendix("附录：Nibi 可行性调研（benchmark、模型、工具链、集群约束）",
                                                       docs["coding_infra.md"]),
        "codingMap": maps["coding_directions.json"],
        "forumMd": docs["forum_focus.md"] + appendix("附录：研究计划（RP.md 原文）", read_md("../doc/RP.md")),
        "notes": notes,
    }
    out = ROOT / "assets" / "data.js"
    out.write_text("/* Generated by tools/build_site.py from index.csv - do not edit by hand. */\n"
                   "window.LIT = " + json.dumps(bundle, ensure_ascii=False, indent=1) + ";\n",
                   encoding="utf-8")

    cats = Counter(p["category"] for p in papers)
    print(f"OK  {len(papers)} papers -> {out.relative_to(ROOT)}  ({len(warnings)} warning(s))")
    for code in CATEGORIES:
        print(f"    {code:22s} {cats.get(code, 0)}")
    print(f"    with PDF: {sum(bool(p['pdf_file']) for p in papers)}  "
          f"code open: {sum(p['code_open'] == 'yes' for p in papers)}  "
          f"in window: {sum(p['in_window'] == 'yes' for p in papers)}  "
          f"deep-read notes: {len(notes)}")


if __name__ == "__main__":
    main()
