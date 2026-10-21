#!/usr/bin/env python3
"""
PDF triage — analyze a PDF and recommend an extraction strategy.

Checks which engines are actually available and adjusts recommendations
accordingly. This makes the skill portable across environments where
not all engines may be installed.

Strategies:
  fast     — pdfplumber only (100% native text, high density)
  standard — pdfplumber + best available OCR engine
  full     — all available engines (mostly scanned, or re-extract)

pdf-inspector pre-probe
-----------------------
When `pdf-inspector` is installed, scripts/pdfi_probe.py runs first as a
sandboxed child process. It is ADVISORY ONLY — its Markdown is never used for
extraction — but it contributes three things the pdfplumber page walk cannot:

  1. Broken-font-encoding detection. pdfplumber returns literal
     "(cid:4)(cid:1)(cid:30)" garbage for PDFs with broken CID/ToUnicode maps,
     and because those sequences are long, the chars-per-page heuristic below
     scores them as HIGH density and selects the `fast` strategy — shipping
     garbage as the extracted text of a judgment. The probe flags this and
     forces `full`.
  2. Classification in milliseconds, so large records skip the full page walk.
  3. Per-page OCR routing, so OCR targets only the pages that need it.

If pdf-inspector is absent or the probe fails for any reason, triage falls
back to the original pdfplumber-only behaviour unchanged.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys

# Wall-clock ceiling for the probe. A legitimate probe finishes in about a
# second even on a 2,000-page document, so anything near this ceiling is
# pathological (a decompression bomb grinds for ~22s before the memory cap
# bites). On timeout we fall back to the pdfplumber-only path.
PROBE_TIMEOUT_SECONDS = 30

# Above this page count, trust the probe's classification and sample pages for
# the density measure instead of walking every page with pdfplumber.
FULL_SCAN_PAGE_LIMIT = 50


def check_engine_availability(venv_py: str) -> dict:
    """Check which engines are actually available in this environment."""
    available = {"pdfplumber": True}  # Always available (setup.sh guarantees it)

    # Check pytesseract
    try:
        subprocess.run(
            [venv_py, "-c", "import pytesseract"],
            capture_output=True, timeout=10
        )
        available["tesseract"] = shutil.which("tesseract") is not None
    except Exception:
        available["tesseract"] = False

    # Check docling
    try:
        result = subprocess.run(
            [venv_py, "-c", "from docling.document_converter import DocumentConverter"],
            capture_output=True, timeout=10
        )
        available["docling"] = result.returncode == 0
    except Exception:
        available["docling"] = False

    # Check liteparse
    available["liteparse"] = (
        shutil.which("lit") is not None or shutil.which("liteparse") is not None
    )

    # Check easyocr — may live in a non-standard path set by EASYOCR_PATH env var
    easyocr_extra = os.environ.get("EASYOCR_PATH", "")
    easyocr_env = {**os.environ}
    if easyocr_extra:
        easyocr_env["PYTHONPATH"] = (
            easyocr_extra + os.pathsep + easyocr_env.get("PYTHONPATH", "")
        )
    try:
        result = subprocess.run(
            [venv_py, "-c", "import easyocr"],
            capture_output=True, timeout=15, env=easyocr_env
        )
        available["easyocr"] = result.returncode == 0
    except Exception:
        available["easyocr"] = False

    return available


def run_pdfi_probe(venv_py: str, pdf_path: str) -> dict:
    """Run the sandboxed pdf-inspector probe. Never raises.

    Returns {"available": False, ...} whenever pdf-inspector is missing or the
    probe fails, so every caller can proceed with the pdfplumber-only path.
    """
    probe_script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "pdfi_probe.py")
    if not os.path.exists(probe_script):
        return {"available": False, "note": "pdfi_probe.py not present"}

    try:
        proc = subprocess.run(
            [venv_py, probe_script, pdf_path],
            capture_output=True, text=True, timeout=PROBE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return {"available": False,
                "note": f"probe exceeded {PROBE_TIMEOUT_SECONDS}s — falling back"}
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "note": f"probe error: {type(exc).__name__}"}

    if proc.returncode != 0 or not proc.stdout.strip():
        note = (proc.stderr or "").strip().splitlines()
        return {"available": False,
                "note": note[-1] if note else f"probe exit {proc.returncode}"}

    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"available": False, "note": "probe returned unparseable output"}


def assess_text_quality(text: str) -> dict:
    """Judge extracted text by its CHARACTER, not its volume.

    The density heuristic in analyze_pdf() is blind to corruption because
    "(cid:NNN)" runs inflate the character count. These checks look at what the
    characters actually are.

    Note this examines PDFPLUMBER's output specifically. pdf-inspector's
    `has_encoding_issues` reports whether *pdf-inspector* could decode the
    fonts, which is not the same question — it flags some documents (notably
    CJK Identity-H) that pdfplumber decodes perfectly well.
    """
    stripped = text.strip()
    if not stripped:
        return {"corrupt": False, "empty": True, "cid_ratio": 0.0,
                "alnum_ratio": 0.0, "replacement_chars": 0}

    cid_count = stripped.count("(cid:")
    replacement = stripped.count("�")
    # Each "(cid:NNN)" is ~9 characters, so weight by that to estimate how
    # much of the text is unmapped glyphs rather than real content.
    cid_ratio = min(1.0, (cid_count * 9) / len(stripped))
    alnum_ratio = sum(c.isalnum() or c.isspace() for c in stripped) / len(stripped)

    corrupt = (
        cid_ratio > 0.05
        or replacement / len(stripped) > 0.05
        or alnum_ratio < 0.60
    )
    return {
        "corrupt": corrupt,
        "empty": False,
        "cid_ratio": round(cid_ratio, 3),
        "alnum_ratio": round(alnum_ratio, 3),
        "replacement_chars": replacement,
    }


def analyze_pdf(pdf_path: str, probe: dict = None) -> dict:
    """Analyze a PDF and return triage information.

    `probe` is an optional pdf-inspector probe result. When present it can
    (a) restrict the pdfplumber walk to a sample on large documents, and
    (b) override the strategy where the text layer is known to be corrupt.
    """
    import pdfplumber

    probe = probe or {}
    probe_ok = bool(probe.get("available"))

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)

        # On large records, a full page walk is the slowest part of triage.
        # With a trustworthy probe classification, sample instead.
        sampled = False
        indices = range(total_pages)
        if probe_ok and total_pages > FULL_SCAN_PAGE_LIMIT:
            step = max(1, total_pages // FULL_SCAN_PAGE_LIMIT)
            indices = list(range(0, total_pages, step))[:FULL_SCAN_PAGE_LIMIT]
            sampled = True

        text_pages = 0
        scanned_pages = 0
        total_chars = 0
        examined = 0
        sample_text = []

        for i in indices:
            text = pdf.pages[i].extract_text() or ""
            chars = len(text.strip())
            total_chars += chars
            examined += 1
            if text.strip():
                text_pages += 1
                if len(sample_text) < 10:
                    sample_text.append(text)
            else:
                scanned_pages += 1

    quality = assess_text_quality("\n".join(sample_text))
    chars_per_page = total_chars / max(examined, 1)
    text_ratio = text_pages / max(examined, 1)
    scanned_ratio = scanned_pages / max(examined, 1)

    # Determine ideal strategy (before checking availability)
    if text_ratio == 1.0 and chars_per_page >= 800:
        strategy = "fast"
        reason = f"All {examined} pages examined have native text with good density ({chars_per_page:.0f} chars/page)"
    elif scanned_ratio > 0.5:
        strategy = "full"
        reason = f"{scanned_pages}/{examined} pages examined are scanned — need multiple OCR engines"
    elif text_ratio == 1.0 and chars_per_page < 800:
        strategy = "standard"
        reason = f"Text present but low density ({chars_per_page:.0f} chars/page) — may be poor OCR overlay"
    else:
        strategy = "standard"
        reason = f"Mixed content: {text_pages} text pages, {scanned_pages} scanned (of {examined} examined)"

    result = {
        "pdf_path": os.path.abspath(pdf_path),
        "total_pages": total_pages,
        "pages_examined": examined,
        "sampled_scan": sampled,
        "text_pages": text_pages,
        "scanned_pages": scanned_pages,
        "chars_per_page": round(chars_per_page, 1),
        "text_ratio": round(text_ratio, 3),
        "strategy": strategy,
        "reason": reason,
        "text_quality": quality,
    }

    # ---- corruption override (runs with or without pdf-inspector) ----------
    # This check works on pdfplumber's own output, so it protects the pipeline
    # even when the probe is unavailable.
    if quality["corrupt"]:
        result["strategy"] = "full"
        result["encoding_warning"] = True
        result["reason"] = (
            f"CORRUPT TEXT LAYER — pdfplumber's output fails quality checks "
            f"(unmapped-glyph ratio {quality['cid_ratio']}, alphanumeric ratio "
            f"{quality['alnum_ratio']}) despite {chars_per_page:.0f} chars/page. "
            f"Character volume is inflated by the corruption itself. OCR required."
        )

    # ---- pdf-inspector overrides -------------------------------------------
    if probe_ok:
        result["pdfi"] = {
            "pdf_type": probe.get("pdf_type"),
            "confidence": probe.get("confidence"),
            "encoding_broken": probe.get("encoding_broken"),
            "pages_needing_ocr": probe.get("pages_needing_ocr", []),
        }
        result["pages_needing_ocr"] = probe.get("pages_needing_ocr", [])

        # pdf-inspector reports a font-decoding problem. Cross-check it against
        # what pdfplumber actually produced before escalating: the two engines
        # decode fonts differently, and pdf-inspector flags some documents
        # (notably CJK Identity-H) that pdfplumber reads perfectly. Escalating
        # on the probe alone would send clean documents to OCR unnecessarily.
        if probe.get("encoding_broken"):
            if quality["corrupt"] or quality["empty"]:
                result["strategy"] = "full"
                result["encoding_warning"] = True
                result["reason"] = (
                    "BROKEN FONT ENCODING — confirmed by both pdf-inspector and "
                    "a quality check of pdfplumber's own output. The text layer "
                    "decodes to garbage even though character density looks "
                    "healthy. Text layer is NOT trustworthy; OCR required."
                )
            else:
                # Disagreement: pdf-inspector cannot decode the fonts but
                # pdfplumber's text passes quality checks. Verify against OCR
                # rather than trusting either engine outright.
                if result["strategy"] == "fast":
                    result["strategy"] = "standard"
                result["encoding_uncertain"] = True
                result["reason"] += (
                    " | pdf-inspector reports a font-decoding problem but "
                    "pdfplumber's output passes quality checks (alphanumeric "
                    f"ratio {quality['alnum_ratio']}). Engines disagree — "
                    "verifying against OCR rather than taking the fast path."
                )

        # Probe says scanned but pdfplumber found a text layer: almost always
        # a poor OCR overlay on images. Do not take the fast path.
        elif probe.get("pdf_type") in ("scanned", "image_based") and strategy == "fast":
            result["strategy"] = "standard"
            result["reason"] = (
                f"pdfplumber found a text layer but pdf-inspector classifies "
                f"this as {probe.get('pdf_type')} (confidence "
                f"{probe.get('confidence')}) — likely an OCR overlay; verifying "
                f"against OCR"
            )
    else:
        result["pdfi"] = {"available": False,
                          "note": probe.get("note", "pdf-inspector not installed")}

    return result


def select_engines(strategy: str, available: dict) -> list:
    """Select which engines to use based on strategy and availability."""
    engines = ["pdfplumber"]  # Always included

    if strategy == "fast":
        return engines

    # For standard/full, add the best available OCR engines.
    # easyocr is preferred over tesseract for image-heavy or dark-background PDFs;
    # docling leads because it also reconstructs document structure (headings, tables).
    ocr_engines_by_preference = ["docling", "easyocr", "tesseract", "liteparse"]

    if strategy == "standard":
        # Add up to 1-2 OCR engines
        for eng in ocr_engines_by_preference:
            if available.get(eng):
                engines.append(eng)
                if len(engines) >= 3:
                    break
    elif strategy == "full":
        # Add all available engines
        for eng in ocr_engines_by_preference:
            if available.get(eng):
                engines.append(eng)

    return engines


def main():
    parser = argparse.ArgumentParser(description="Triage a PDF for extraction strategy")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("--force-strategy", choices=["fast", "standard", "full"],
                        help="Override the auto-detected strategy")
    parser.add_argument("--json", action="store_true", help="Output as JSON only")
    parser.add_argument("--venv-python", help="Path to venv Python (for engine checks)")
    parser.add_argument("--no-pdfi", action="store_true",
                        help="Skip the pdf-inspector pre-probe entirely")
    args = parser.parse_args()

    if not os.path.exists(args.pdf_path):
        print(f"ERROR: PDF not found: {args.pdf_path}", file=sys.stderr)
        sys.exit(1)

    # Check engine availability
    venv_py = args.venv_python or sys.executable
    available = check_engine_availability(venv_py)

    # Fast sandboxed pre-probe (advisory; degrades silently if unavailable)
    probe = {"available": False, "note": "probe skipped (--no-pdfi)"}
    if not args.no_pdfi:
        probe = run_pdfi_probe(venv_py, args.pdf_path)

    # Analyze the PDF
    result = analyze_pdf(args.pdf_path, probe)

    if args.force_strategy:
        # A forced strategy still may not silently override a corrupt text
        # layer — downgrading to `fast` there would ship garbage.
        if args.force_strategy == "fast" and result.get("encoding_warning"):
            result["reason"] += (
                " | '--force-strategy fast' REFUSED: the text layer is corrupt."
            )
        else:
            result["strategy"] = args.force_strategy
            result["reason"] = f"Strategy forced to '{args.force_strategy}'"

    # Select engines based on strategy + availability
    engines = select_engines(result["strategy"], available)
    result["engines"] = engines
    result["available_engines"] = available

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"PDF: {result['pdf_path']}")
        scan_note = " [sampled]" if result.get("sampled_scan") else ""
        print(f"Pages: {result['total_pages']} "
              f"(examined: {result['pages_examined']}{scan_note}, "
              f"text: {result['text_pages']}, scanned: {result['scanned_pages']})")
        print(f"Density: {result['chars_per_page']:.0f} chars/page")

        pdfi = result.get("pdfi", {})
        if pdfi.get("pdf_type"):
            print(f"pdf-inspector: {pdfi['pdf_type']} "
                  f"(confidence {pdfi.get('confidence')})")
            ocr_pages = pdfi.get("pages_needing_ocr") or []
            if ocr_pages:
                shown = ocr_pages[:20]
                more = "" if len(ocr_pages) <= 20 else f" (+{len(ocr_pages) - 20} more)"
                print(f"  Pages needing OCR: {shown}{more}")
        else:
            print(f"pdf-inspector: not used — {pdfi.get('note', 'unavailable')}")

        q = result.get("text_quality", {})
        if not q.get("empty"):
            print(f"Text quality: alphanumeric {q.get('alnum_ratio')}, "
                  f"unmapped-glyph ratio {q.get('cid_ratio')}")

        if result.get("encoding_warning"):
            print("")
            print("  *** WARNING: BROKEN FONT ENCODING ***")
            print("  The text layer decodes to garbage. Do NOT use text-layer")
            print("  output. OCR is required, and any extracted text from this")
            print("  document must be treated as unverified until checked.")
            print("")
        elif result.get("encoding_uncertain"):
            print("")
            print("  NOTE: engines disagree on font decoding. pdfplumber's text")
            print("  looks clean but pdf-inspector could not decode the fonts.")
            print("  Verifying against OCR rather than taking the fast path.")
            print("")

        print(f"Strategy: {result['strategy'].upper()}")
        print(f"Engines: {', '.join(result['engines'])}")
        print(f"Reason: {result['reason']}")
        print(f"\nEngine availability:")
        for eng, ok in available.items():
            status = "OK" if ok else "UNAVAILABLE"
            print(f"  {eng}: {status}")
        # Also output JSON for machine consumption
        print(f"\n{json.dumps(result)}")


if __name__ == "__main__":
    main()
