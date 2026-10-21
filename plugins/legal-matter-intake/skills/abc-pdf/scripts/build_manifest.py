#!/usr/bin/env python3
"""
Build manifest.json from all available engine outputs in the extraction directory.
Supports pdfplumber, docling, tesseract, and liteparse outputs.
"""

import argparse
import json
import os
import re
import sys


ENGINE_FILES = {
    "pdfplumber": "pdfplumber_output.md",
    "docling": "docling_output.md",
    "tesseract": "tesseract_output.md",
    "liteparse": "liteparse_output.md",
}


def quality_metrics(md_text: str, pdf_page_count: int) -> dict:
    """Compute quality metrics for a markdown output."""
    lines = md_text.split("\n")
    total_chars = len(md_text)
    alnum_chars = sum(1 for c in md_text if c.isalnum())
    alnum_ratio = alnum_chars / max(total_chars, 1)
    chars_per_page = total_chars / max(pdf_page_count, 1)
    lines_per_page = len(lines) / max(pdf_page_count, 1)

    markers_found = 0
    if re.search(r"\[\d+\]", md_text):
        markers_found += 1
    if re.search(r"HIGH COURT|SUPREME COURT|CONSTITUTIONAL COURT|COURT OF APPEAL",
                 md_text, re.IGNORECASE):
        markers_found += 1
    if re.search(r"^#+\s*ORDER|^ORDER\s*$", md_text, re.MULTILINE):
        markers_found += 1
    if re.search(r"\b\w+\s+(AJ|AJA|JA?)\b", md_text):
        markers_found += 1
    if re.search(r"\d{2,}/\d{4}|\[\d{4}\]\s*ZA", md_text):
        markers_found += 1

    heading_count = len(re.findall(r"^#{1,6}\s+", md_text, re.MULTILINE))
    table_count = len(re.findall(r"^\|.*\|.*\|", md_text, re.MULTILINE))

    return {
        "total_chars": total_chars,
        "total_lines": len(lines),
        "alnum_ratio": round(alnum_ratio, 4),
        "chars_per_page": round(chars_per_page, 1),
        "lines_per_page": round(lines_per_page, 1),
        "structural_markers": markers_found,
        "heading_count": heading_count,
        "table_count": table_count,
    }


def detect_scanned_pages(pdf_path: str) -> dict:
    """Detect text vs scanned pages."""
    import pdfplumber
    text_pages = 0
    scanned_pages = 0
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text and text.strip():
                text_pages += 1
            else:
                scanned_pages += 1
    return {
        "total": text_pages + scanned_pages,
        "text_pages": text_pages,
        "scanned_pages": scanned_pages,
    }


def main():
    parser = argparse.ArgumentParser(description="Build manifest from engine outputs")
    parser.add_argument("pdf_path", help="Path to the original PDF")
    parser.add_argument("engine_dir", help="Directory containing engine outputs")
    args = parser.parse_args()

    pdf_path = os.path.abspath(args.pdf_path)
    engine_dir = os.path.abspath(args.engine_dir)

    if not os.path.exists(pdf_path):
        print(f"ERROR: PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    # Get page info
    page_info = detect_scanned_pages(pdf_path)
    total_pages = page_info["total"]

    # Scan for engine outputs
    results = []
    for engine_name, filename in ENGINE_FILES.items():
        filepath = os.path.join(engine_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                md_text = f.read()
            metrics = quality_metrics(md_text, total_pages)
            results.append({
                "engine": engine_name,
                "output_path": filepath,
                "elapsed_seconds": 0,  # not tracked here
                "success": True,
                "error": None,
                "metrics": metrics,
            })

    if not results:
        print("ERROR: No engine outputs found in " + engine_dir, file=sys.stderr)
        sys.exit(1)

    manifest = {
        "pdf_path": pdf_path,
        "page_info": page_info,
        "engine_dir": engine_dir,
        "results": results,
    }

    manifest_path = os.path.join(engine_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Manifest: {manifest_path}")
    print(f"Pages: {total_pages} (text: {page_info['text_pages']}, scanned: {page_info['scanned_pages']})")
    print(f"Engines found: {len(results)}")
    print()

    # Print comparison table
    print(f"{'Engine':<12} {'Chars':>8} {'Alnum%':>8} {'Ch/pg':>8} "
          f"{'Headings':>8} {'Tables':>8} {'Markers':>8}")
    print("-" * 72)
    for r in results:
        m = r["metrics"]
        print(f"{r['engine']:<12} {m['total_chars']:>8} "
              f"{m['alnum_ratio']:>7.1%} {m['chars_per_page']:>8.0f} "
              f"{m['heading_count']:>8} {m['table_count']:>8} "
              f"{m['structural_markers']:>8}")


if __name__ == "__main__":
    main()
