#!/usr/bin/env python3
"""
Enhanced consensus merger for multi-engine PDF extraction.
Reads manifest.json and produces a single merged Markdown by selecting
the best content from each engine's output.

Merge strategies (in priority order):
1. Section-level merge — if 2+ engines have markdown headings, pick best version
   of each section
2. Page-level merge — split by page separators, pick best version of each page
3. Best-overall — use the single highest-scoring engine

The key insight: pdfplumber gives the cleanest text for native pages (no OCR noise),
Docling gives the best structure (headings, tables), tesseract provides fast OCR,
and liteparse provides a second OCR opinion. The merger picks the best of each
per-section or per-page.
"""

import argparse
import json
import os
import re
import sys


def score_engine(metrics: dict) -> float:
    """
    Composite quality score. Higher is better.
    Weights: character quality (40), density (20), structure (20), headings (10), tables (10).
    """
    if not metrics:
        return 0.0

    score = 0.0
    # Character quality — garbled OCR is useless
    score += metrics.get("alnum_ratio", 0) * 40

    # Content density
    cpp = metrics.get("chars_per_page", 0)
    if cpp >= 500:
        score += 20
    elif cpp >= 200:
        score += 10

    # Structural markers
    score += min(metrics.get("structural_markers", 0), 5) * 4  # max 20

    # Headings
    score += min(metrics.get("heading_count", 0), 20) * 0.5  # max 10

    # Tables
    score += min(metrics.get("table_count", 0), 10) * 1.0  # max 10

    return round(score, 2)


def section_quality(text: str) -> float:
    """Score a single section's quality."""
    if not text.strip():
        return 0.0

    chars = len(text)
    alnum = sum(1 for c in text if c.isalnum())
    ratio = alnum / max(chars, 1)

    length_score = min(chars / 200, 1.0) * 10
    quality_score = ratio * 30
    para_count = len([p for p in text.split("\n\n") if p.strip()])
    structure_score = min(para_count, 10) * 1.0

    return length_score + quality_score + structure_score


def normalize_heading(heading: str) -> str:
    """Normalize a heading for fuzzy matching across engines."""
    h = heading.lower().strip()
    h = re.sub(r"^#+\s*", "", h)
    h = re.sub(r"[^a-z0-9\s]", "", h)
    h = re.sub(r"\s+", " ", h).strip()
    return h


def split_into_sections(md_text: str) -> list:
    """Split markdown into sections based on headings."""
    pattern = r"^(#{1,6}\s+.+)$"
    parts = re.split(pattern, md_text, flags=re.MULTILINE)

    sections = []
    if parts[0].strip():
        sections.append(("__preamble__", parts[0]))

    i = 1
    while i < len(parts):
        heading = parts[i].strip() if i < len(parts) else ""
        content = parts[i + 1] if i + 1 < len(parts) else ""
        sections.append((heading, content))
        i += 2

    return sections


def split_into_pages(md_text: str) -> list:
    """
    Split text into pages using common page separators.
    Handles: --- (pdfplumber), page markers, form feeds.
    """
    # Try splitting on horizontal rules (pdfplumber style)
    pages = re.split(r"\n\n---\n\n", md_text)
    if len(pages) > 1:
        return pages

    # Try splitting on page markers
    pages = re.split(r"(?:^|\n)(?:<!-- Page \d+|Page \d+ of \d+|\f)", md_text)
    pages = [p for p in pages if p.strip()]
    if len(pages) > 1:
        return pages

    # No page structure found — return whole document
    return [md_text]


def merge_by_sections(engine_outputs: list) -> tuple:
    """Section-level merge: for each heading, pick the best engine's version."""
    engine_sections = {}
    for eo in engine_outputs:
        sections = split_into_sections(eo["text"])
        normalized = {}
        for heading, content in sections:
            key = normalize_heading(heading) if heading != "__preamble__" else "__preamble__"
            normalized[key] = (heading, content)
        engine_sections[eo["engine"]] = normalized

    # Collect all unique section keys in order of first appearance
    seen_keys = []
    for eo in engine_outputs:
        for key in engine_sections[eo["engine"]]:
            if key not in seen_keys:
                seen_keys.append(key)

    merged_parts = []
    choices = []
    for key in seen_keys:
        best_engine = None
        best_score = -1
        best_content = ""
        best_heading = ""

        for eo in engine_outputs:
            if key in engine_sections[eo["engine"]]:
                heading, content = engine_sections[eo["engine"]][key]
                score = section_quality(content)
                if score > best_score:
                    best_score = score
                    best_engine = eo["engine"]
                    best_content = content
                    best_heading = heading

        if best_heading and best_heading != "__preamble__":
            merged_parts.append(best_heading)
        merged_parts.append(best_content)
        choices.append({
            "section": key,
            "chosen_engine": best_engine,
            "score": round(best_score, 2),
        })

    return "\n".join(merged_parts), choices


def merge_by_pages(engine_outputs: list) -> tuple:
    """
    Page-level merge: split each engine's output into pages,
    then for each page pick the best version.
    """
    engine_pages = {}
    max_pages = 0
    for eo in engine_outputs:
        pages = split_into_pages(eo["text"])
        engine_pages[eo["engine"]] = pages
        max_pages = max(max_pages, len(pages))

    if max_pages <= 1:
        # Can't do page-level merge
        return None, None

    merged_parts = []
    choices = []

    for page_idx in range(max_pages):
        best_engine = None
        best_score = -1
        best_content = ""

        for eo in engine_outputs:
            pages = engine_pages[eo["engine"]]
            if page_idx < len(pages):
                content = pages[page_idx]
                score = section_quality(content)
                if score > best_score:
                    best_score = score
                    best_engine = eo["engine"]
                    best_content = content

        merged_parts.append(best_content)
        choices.append({
            "section": f"page_{page_idx + 1}",
            "chosen_engine": best_engine,
            "score": round(best_score, 2),
        })

    return "\n\n---\n\n".join(merged_parts), choices


def _normalize_line(line: str) -> str:
    """Normalize a line for loss-check matching: lowercase, alnum only."""
    return re.sub(r"[^a-z0-9]", "", line.lower())


def recover_lost_content(merged: str, engine_outputs: list) -> tuple:
    """
    Content loss-check: find substantive lines that at least one engine
    captured but the merged output does not contain (observed failure:
    a page footer present in tesseract's output was dropped because the
    per-section winner was docling, which had missed it).

    Returns (recovered_lines, report_entries). Conservative on purpose:
    only lines with real content are considered, matching is fuzzy, and
    recovered lines are appended under an explicit marker rather than
    spliced in, so a human (or the vision gate) decides placement.
    """
    import difflib

    merged_norm_lines = [_normalize_line(l) for l in merged.splitlines() if l.strip()]
    merged_blob = _normalize_line(merged)

    recovered = []
    report = []
    seen_norms = []

    for eo in engine_outputs:
        for line in eo["text"].splitlines():
            stripped = line.strip()
            if len(stripped) < 12 or stripped.startswith(("#", "|", "<!--", "-", "*", "!")):
                continue
            norm = _normalize_line(stripped)
            if len(norm) < 12:
                continue
            alnum_ratio = sum(c.isalnum() for c in stripped) / len(stripped)
            if alnum_ratio < 0.5:
                continue  # likely OCR noise
            # Already in the merged output (substring or fuzzy line match)?
            if norm in merged_blob:
                continue
            if any(difflib.SequenceMatcher(None, norm, m).ratio() >= 0.75
                   for m in merged_norm_lines if abs(len(m) - len(norm)) < max(len(norm), 20)):
                continue
            # Already recovered (dedupe across engines)?
            if any(difflib.SequenceMatcher(None, norm, s).ratio() >= 0.8 for s in seen_norms):
                continue
            seen_norms.append(norm)
            recovered.append(stripped)
            report.append({"engine": eo["engine"], "line": stripped})

    return recovered, report


def merge_best_overall(engine_outputs: list) -> tuple:
    """Fall back to the single best engine."""
    best = max(engine_outputs, key=lambda eo: eo["score"])
    return best["text"], [{"section": "__full_document__",
                           "chosen_engine": best["engine"],
                           "score": best["score"]}]


def main():
    parser = argparse.ArgumentParser(description="Consensus merge of multi-engine outputs")
    parser.add_argument("manifest_path", help="Path to manifest.json")
    parser.add_argument("--output", "-o", help="Output merged markdown path")
    parser.add_argument("--strategy", "-s",
                        choices=["section", "page", "best", "auto"],
                        default="auto",
                        help="Merge strategy (default: auto)")
    args = parser.parse_args()

    with open(args.manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Load successful engine outputs
    engine_outputs = []
    for r in manifest["results"]:
        if r["success"] and r.get("output_path") and os.path.exists(r["output_path"]):
            with open(r["output_path"], "r", encoding="utf-8") as f:
                text = f.read()
            score = score_engine(r["metrics"])
            engine_outputs.append({
                "engine": r["engine"],
                "text": text,
                "metrics": r["metrics"],
                "score": score,
            })

    if not engine_outputs:
        print("ERROR: No successful engine outputs found.", file=sys.stderr)
        sys.exit(1)

    strategy = "single_engine"
    if len(engine_outputs) == 1:
        print(f"Only one engine succeeded ({engine_outputs[0]['engine']}), using it directly.")
        merged = engine_outputs[0]["text"]
        choices = [{"section": "__full_document__",
                    "chosen_engine": engine_outputs[0]["engine"],
                    "score": engine_outputs[0]["score"]}]
    else:
        # Print scores
        print("Engine scores:")
        for eo in sorted(engine_outputs, key=lambda x: x["score"], reverse=True):
            print(f"  {eo['engine']}: {eo['score']}")

        strategy = args.strategy
        if strategy == "auto":
            # Try section merge first (need 2+ engines with headings)
            engines_with_headings = sum(
                1 for eo in engine_outputs
                if eo["metrics"] and eo["metrics"].get("heading_count", 0) >= 3
            )
            if engines_with_headings >= 2:
                strategy = "section"
            else:
                # Try page merge (need 2+ engines with pages)
                has_pages = sum(
                    1 for eo in engine_outputs
                    if len(split_into_pages(eo["text"])) > 1
                )
                strategy = "page" if has_pages >= 2 else "best"
            print(f"Auto-selected strategy: {strategy}")

        if strategy == "section":
            merged, choices = merge_by_sections(engine_outputs)
        elif strategy == "page":
            merged, choices = merge_by_pages(engine_outputs)
            if merged is None:
                print("Page merge failed, falling back to best-overall")
                strategy = "best"
                merged, choices = merge_best_overall(engine_outputs)
        else:
            merged, choices = merge_best_overall(engine_outputs)

    # Content loss-check: recover substantive lines the winning engines dropped
    lost_report = []
    if len(engine_outputs) > 1:
        recovered, lost_report = recover_lost_content(merged, engine_outputs)
        if recovered:
            merged += (
                "\n\n<!-- RECOVERED CONTENT (merge loss-check): the lines below were "
                "captured by at least one engine but absent from the merged text. "
                "Verify placement against the page image before relying on them. -->\n"
            )
            merged += "\n".join(f"> {l}" for l in recovered) + "\n"
            print(f"\nWARNING: loss-check recovered {len(recovered)} line(s) dropped by the merge; "
                  f"appended under RECOVERED CONTENT marker. Verify against the page image.")

    # Determine output path
    if args.output:
        out_path = args.output
    else:
        pdf_stem = os.path.splitext(os.path.basename(manifest["pdf_path"]))[0]
        out_path = os.path.join(manifest["engine_dir"], f"{pdf_stem}_merged.md")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(merged)

    # Save merge report
    report = {
        "strategy_used": strategy,
        "engine_scores": {eo["engine"]: eo["score"] for eo in engine_outputs},
        "section_choices": choices,
        "recovered_content": lost_report,
        "output_path": out_path,
    }
    report_path = os.path.join(os.path.dirname(out_path), "merge_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\nMerged output: {out_path}")
    print(f"Merge report: {report_path}")

    # Print engine contribution breakdown
    if len(choices) > 1:
        print(f"\nEngine contributions ({len(choices)} sections/pages):")
        engine_counts = {}
        for c in choices:
            eng = c["chosen_engine"]
            engine_counts[eng] = engine_counts.get(eng, 0) + 1
        for eng, count in sorted(engine_counts.items(), key=lambda x: -x[1]):
            pct = count / len(choices) * 100
            print(f"  {eng}: {count} ({pct:.0f}%)")


if __name__ == "__main__":
    main()
