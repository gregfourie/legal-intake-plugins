#!/usr/bin/env python3
"""Scan a matter's _inbox/ and write scan.json with per-file signals and a
suggested route. Read-only: never moves, edits or deletes anything.

Usage: python3 scan_inbox.py <inbox_dir> [--out scan.json]
Needs: poppler (pdfinfo, pdftotext). Optional: pypdf (outline check),
python-docx (author).
"""
import argparse, hashlib, json, re, subprocess, sys

OWN_AUTHORS = []
PROFILE = {}
from collections import defaultdict
from pathlib import Path

JUNK = {".DS_Store", "Thumbs.db"}
COPY_MARK = re.compile(r"\(\d+\)$|\bcopy\b", re.I)
KNOWN = {".pdf", ".eml", ".msg", ".docx", ".doc", ".xlsx", ".xls", ".csv", ".pptx", ".txt", ".md"}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=120).stdout
    except Exception:
        return ""


def pdf_info(p):
    out = {}
    m = re.search(r"Pages:\s+(\d+)", run(["pdfinfo", str(p)]))
    pages = int(m.group(1)) if m else 0
    out["pages"] = pages
    # sample up to first 5 pages for text density and signals
    last = min(pages, 5) if pages else 5
    text = run(["pdftotext", "-f", "1", "-l", str(last), "-layout", str(p), "-"])
    per_page = len(text.strip()) / max(last, 1)
    out["chars_per_page_sample"] = round(per_page)
    out["text_layer"] = "none" if per_page < 50 else "partial" if per_page < 400 else "full"
    low = text.lower()
    hits = sum(low.count(k) for k in ("from:", "sent:", "to:", "subject:"))
    out["email_chain_signal"] = hits >= 6
    out["judgment_signal"] = bool(
        any(m in low for m in PROFILE.get("judgment_source_markers", []))
        or (re.search(r"case\s*no", low) and "judgment" in low)
        # generic neutral citation, e.g. [2024] ABC 12
        or re.search(r"\[\d{4}\]\s*[a-z]{2,8}\s*(?:civ|crim|admin)?\s*\d+", low)
        or any(re.search(rx, low, re.IGNORECASE)
               for rx in PROFILE.get("judgment_patterns", []))
    )
    try:
        from pypdf import PdfReader
        out["has_outline"] = bool(PdfReader(str(p)).outline)
    except Exception:
        out["has_outline"] = None  # unknown
    return out


def docx_author(p):
    try:
        import docx
        cp = docx.Document(str(p)).core_properties
        return {"docx_author": cp.author or "", "docx_last_modified_by": cp.last_modified_by or ""}
    except Exception:
        return {"docx_author": None}


def version_key(stem):
    s = stem.lower()
    s = re.sub(r"\(\d+\)", "", s)
    s = re.sub(r"\b(v|ver|version|rev)[\s_-]*\d+\b", "", s)  # needs a number: keeps "Smith v Jones"
    s = re.sub(r"\b(draft|final|clean|marked|tracked|copy)[\s_-]*\d*\b", "", s)
    s = re.sub(r"\d{1,4}[-_. ]\d{1,2}[-_. ]\d{1,4}", "", s)  # dates
    s = re.sub(r"\b\d{6,8}\b", "", s)
    s = re.sub(r"[\s_\-.]+", " ", s).strip()
    return s


def find_profile(start, explicit=None):
    if explicit:
        return json.loads(Path(explicit).read_text())
    for d in [Path(start).resolve(), *Path(start).resolve().parents]:
        f = d / "_intake-profile.json"
        if f.is_file():
            return json.loads(f.read_text())
    return {}


def suggest(r):
    ext, flags = r["ext"], []
    if r.get("quarantine"):
        return "QUARANTINE", flags
    if ext == ".eml":
        return "matter-mail", flags
    if ext == ".msg":
        return "email-chain-extraction", flags
    if ext == ".pdf":
        route = "pdf-intake"
        if r.get("email_chain_signal"):
            flags.append("email-chain-extraction")
        if r.get("judgment_signal"):
            flags.append("caselaw-fetch")
        if r.get("text_layer") in ("none", "partial"):
            flags.append("legibility-review or handwriting-narration (check page image)")
        if r.get("pages", 0) >= 50 and r.get("has_outline") is False:
            flags.append("pdf-bookmarks")
        if r.get("pages", 0) > 100:
            flags.append("FLAG large-record analysis")
        return route, flags
    if ext in (".docx", ".doc"):
        a = (r.get("docx_author") or "").lower()
        if a and OWN_AUTHORS and not any(o in a for o in OWN_AUTHORS):
            flags.append("FLAG redline (author: %s)" % r["docx_author"])
        elif a and not OWN_AUTHORS:
            flags.append("note: docx author %s" % r["docx_author"])
        return "docx", flags
    if ext in (".xlsx", ".xls", ".csv"):
        return "xlsx", flags
    if ext == ".pptx":
        return "pptx", flags
    return "file-reading", flags


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inbox")
    ap.add_argument("--out", default=None)
    ap.add_argument("--own-author", default="",
                    help="comma-separated names that identify the user as docx author")
    ap.add_argument("--profile", default=None,
                    help="jurisdiction profile JSON (default: _intake-profile.json in the inbox or a parent)")
    a = ap.parse_args()
    OWN_AUTHORS[:] = [n.strip().lower() for n in a.own_author.split(",") if n.strip()]
    PROFILE.update(find_profile(a.inbox, a.profile))
    if not OWN_AUTHORS:
        OWN_AUTHORS[:] = [n.lower() for n in PROFILE.get("own_authors", [])]
    inbox = Path(a.inbox)
    if not inbox.is_dir():
        sys.exit(f"Not a folder: {inbox}")

    rows, seen = [], {}
    for p in sorted(x for x in inbox.rglob("*") if x.is_file()):
        r = {"file": str(p.relative_to(inbox)), "ext": p.suffix.lower(), "size": p.stat().st_size}
        if p.name in JUNK or p.name.startswith("~$") or r["size"] == 0:
            r["quarantine"] = "junk or empty"
        else:
            h = sha(p)
            r["sha256"] = h
            seen.setdefault(h, []).append(r)
        if not r.get("quarantine"):
            if r["ext"] == ".pdf":
                r.update(pdf_info(p))
            elif r["ext"] == ".docx":
                r.update(docx_author(p))
            if r["ext"] not in KNOWN:
                r["unknown_type"] = True
            r["version_key"] = version_key(p.stem)
        rows.append(r)

    # duplicates: keep the copy without "(1)" / "copy" markers, quarantine the rest
    for h, group in seen.items():
        if len(group) > 1:
            group.sort(key=lambda r: (bool(COPY_MARK.search(Path(r["file"]).stem)), len(r["file"]), r["file"]))
            keep = group[0]["file"]
            for r in group[1:]:
                r["quarantine"] = f"duplicate of {keep}"
                r["duplicate_of"] = keep
                r.pop("version_key", None)

    clusters = defaultdict(list)
    for r in rows:
        if r.get("version_key"):
            clusters[(r["version_key"], r["ext"])].append(r["file"])
    for r in rows:
        k = (r.get("version_key"), r["ext"])
        if len(clusters.get(k, [])) > 1:
            r["version_cluster"] = clusters[k]

    for r in rows:
        route, flags = suggest(r)
        if r.get("version_cluster"):
            flags.append("draft-version-control")
        r["suggested_route"], r["also_consider"] = route, flags

    result = {"inbox": str(inbox), "file_count": len(rows), "files": rows}
    js = json.dumps(result, indent=2)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(js)
        print(f"Wrote {a.out} ({len(rows)} files)")
    else:
        print(js)


if __name__ == "__main__":
    main()
