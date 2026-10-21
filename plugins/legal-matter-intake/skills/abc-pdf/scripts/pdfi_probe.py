#!/usr/bin/env python3
"""
pdf-inspector probe — fast, sandboxed pre-triage for abc-pdf.

Runs as an ISOLATED CHILD PROCESS under a hard memory cap so that a malformed
or hostile PDF cannot take down the parent triage run. pdf-inspector has no
guard against decompression bombs (a crafted 2 GB flate stream will allocate
2 GB), so the RLIMIT_AS cap below is mandatory, not optional.

Emits a single JSON object on stdout. Any failure exits non-zero with no
stdout, which triage.py treats as "probe unavailable" and falls back to the
pdfplumber page walk.

ADVISORY ONLY. This probe never produces text for extraction. pdf-inspector's
Markdown is not used anywhere in abc-pdf, because it silently wraps
hanging-indent legal prose in Markdown table pipes and inlines superscript
footnote markers into the running text (sometimes inside a case name).
Extraction remains the job of pdfplumber / Docling / OCR.

What it contributes:
  1. Classification in milliseconds instead of a full pdfplumber page walk.
  2. Per-page OCR routing, so OCR runs only on pages that need it.
  3. Broken-font-encoding detection — the gap this probe exists to close.
     pdfplumber happily returns "(cid:4)(cid:1)(cid:30)" garbage for PDFs with
     broken CID/ToUnicode maps, and the character-density heuristic in
     triage.py counts that as high-quality native text, selecting the "fast"
     strategy and shipping garbage. pdf-inspector flags it.
"""

import argparse
import json
import os
import resource
import sys

# Hard cap on address space for this process. A decompression bomb hits this
# and raises rather than exhausting the machine.
MEM_CAP_BYTES = 2 * 1024 * 1024 * 1024

# Pages sampled for the encoding check. pdf-inspector's `pages` argument is
# 1-INDEXED (page 0 silently yields nothing). Sampling first / middle / last
# catches broken fonts that only appear later in a record, while keeping the
# cost at roughly 150-200 ms even on a 269-page document.
MAX_SAMPLE_PAGES = 8


def _apply_memory_cap() -> None:
    try:
        resource.setrlimit(resource.RLIMIT_AS, (MEM_CAP_BYTES, MEM_CAP_BYTES))
    except (ValueError, OSError):
        # Some platforms (notably macOS) refuse RLIMIT_AS. The parent also
        # imposes a wall-clock timeout, so continue.
        pass


def _sample_pages(page_count: int) -> list:
    """First, middle and last pages, 1-indexed, capped at MAX_SAMPLE_PAGES."""
    if page_count <= MAX_SAMPLE_PAGES:
        return list(range(1, page_count + 1))
    head = [1, 2, 3]
    mid = page_count // 2
    middle = [mid, mid + 1]
    tail = [page_count - 2, page_count - 1, page_count]
    return sorted({p for p in head + middle + tail if 1 <= p <= page_count})


def probe(pdf_path: str) -> dict:
    import pdf_inspector

    classification = pdf_inspector.classify_pdf(pdf_path)
    page_count = classification.page_count

    # pages_needing_ocr from classify_pdf is 0-indexed; normalise to 1-indexed
    # so everything downstream of this probe speaks printed-page numbers.
    pages_needing_ocr = sorted(p + 1 for p in classification.pages_needing_ocr)

    result = {
        "available": True,
        "pdf_type": classification.pdf_type,
        "page_count": page_count,
        "confidence": round(classification.confidence, 3),
        "pages_needing_ocr": pages_needing_ocr,
        "encoding_broken": False,
        "encoding_check": "not_run",
        "sampled_pages": [],
    }

    # Encoding check: only meaningful where a text layer is claimed at all.
    if classification.pdf_type in ("text_based", "mixed") and page_count > 0:
        sample = _sample_pages(page_count)
        try:
            sampled = pdf_inspector.process_pdf(pdf_path, sample)
            result["encoding_broken"] = bool(sampled.has_encoding_issues)
            result["encoding_check"] = "sampled"
            result["sampled_pages"] = sample
        except Exception as exc:  # noqa: BLE001 - probe must never be fatal
            result["encoding_check"] = f"failed: {type(exc).__name__}"

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fast sandboxed pdf-inspector probe (advisory only)"
    )
    parser.add_argument("pdf_path", help="Path to the PDF file")
    args = parser.parse_args()

    _apply_memory_cap()

    if not os.path.exists(args.pdf_path):
        print(f"ERROR: PDF not found: {args.pdf_path}", file=sys.stderr)
        sys.exit(1)

    try:
        print(json.dumps(probe(args.pdf_path)))
    except ImportError:
        print("pdf-inspector not installed", file=sys.stderr)
        sys.exit(2)
    except MemoryError:
        print("memory cap hit — possible decompression bomb", file=sys.stderr)
        sys.exit(3)
    except Exception as exc:  # noqa: BLE001
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(4)


if __name__ == "__main__":
    main()
