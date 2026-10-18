#!/usr/bin/env python3
"""Download open-access PDFs listed in index.csv into pdf/ and record them in the pdf_file column.

Sources: arXiv (arxiv_id), OpenReview forum/pdf links, ACL Anthology links, or any paper_url ending in .pdf.
Requests are sequential and spaced >= --delay seconds apart (arXiv asks for <= 1 request / 3 s).
Existing valid PDFs are skipped, so the script can be re-run safely.

Usage (from paper/):  python3 tools/fetch_pdfs.py [--dry-run] [--limit N] [--delay 3.5]
"""
import argparse
import csv
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "pdf"
UA = "AgentMindCommunicate-litreview/1.0 (academic literature index; polite single-stream downloader)"


def pdf_url(row):
    aid = row["arxiv_id"].strip()
    if aid:
        return f"https://arxiv.org/pdf/{aid}"
    url = row["paper_url"].strip()
    m = re.search(r"openreview\.net/(?:forum|pdf)\?id=([\w-]+)", url)
    if m:
        return f"https://openreview.net/pdf?id={m.group(1)}"
    m = re.search(r"aclanthology\.org/([\w.-]+?)/?(?:\.pdf)?$", url)
    if m:
        return f"https://aclanthology.org/{m.group(1)}.pdf"
    if url.lower().endswith(".pdf"):
        return url
    return ""


def file_name(row):
    short = re.sub(r"[^A-Za-z0-9]+", "-", row["short_name"] or row["title"]).strip("-")[:40] or "paper"
    stem = row["arxiv_id"].strip() or row["id"].strip()
    return f"{stem}_{short}.pdf"


def is_pdf(path):
    try:
        with path.open("rb") as f:
            return path.stat().st_size > 1024 and f.read(5) == b"%PDF-"
    except OSError:
        return False


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    tmp = dest.with_suffix(".part")
    with urllib.request.urlopen(req, timeout=90) as resp, tmp.open("wb") as out:
        while chunk := resp.read(1 << 16):
            out.write(chunk)
    if not is_pdf(tmp):
        tmp.unlink(missing_ok=True)
        raise ValueError("response is not a PDF")
    tmp.replace(dest)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="max downloads this run (0 = no limit)")
    ap.add_argument("--delay", type=float, default=3.5, help="seconds between requests")
    args = ap.parse_args()

    index = ROOT / "index.csv"
    with index.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields, rows = reader.fieldnames, list(reader)

    PDF_DIR.mkdir(exist_ok=True)
    done = skipped = failed = 0
    for row in rows:
        url = pdf_url(row)
        if not url:
            continue
        dest = PDF_DIR / file_name(row)
        rel = f"pdf/{dest.name}"
        if is_pdf(dest):
            row["pdf_file"] = rel
            skipped += 1
            continue
        if args.limit and done >= args.limit:
            break
        if args.dry_run:
            print(f"would fetch {url} -> {rel}")
            done += 1
            continue
        try:
            download(url, dest)
            row["pdf_file"] = rel
            done += 1
            print(f"ok    {rel}", flush=True)
        except Exception as e:  # keep going; failures are reported at the end
            row["pdf_file"] = ""
            failed += 1
            print(f"FAIL  {row['id']}: {url} ({e})", flush=True)
        time.sleep(args.delay)

    if not args.dry_run:
        with index.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    print(f"downloaded {done}, already present {skipped}, failed {failed}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
