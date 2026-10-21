#!/usr/bin/env python3
"""
Multi-engine PDF to Markdown extraction.
Runs a single engine (pdfplumber, docling, or tesseract) per invocation.
Call once per engine as separate shell commands, then run build_manifest.py.

The tesseract engine is new — uses pytesseract + pdf2image for OCR,
providing a fast fallback when Docling is unavailable.
"""

import os
os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import argparse
import json
import re
import sys
import time
import traceback


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


def run_docling(pdf_path: str, output_dir: str, force_ocr: bool) -> dict:
    """Run Docling extraction via Python API."""
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions

    pipeline_options = PdfPipelineOptions(do_ocr=True, do_table_structure=True)
    if force_ocr:
        pipeline_options.ocr_options.force_full_page_ocr = True

    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
    )

    start = time.time()
    result = converter.convert(pdf_path)
    elapsed = time.time() - start

    md_content = result.document.export_to_markdown()
    out_path = os.path.join(output_dir, "docling_output.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    return {
        "engine": "docling",
        "output_path": out_path,
        "elapsed_seconds": round(elapsed, 1),
        "success": True,
        "error": None,
    }


def run_pdfplumber(pdf_path: str, output_dir: str) -> dict:
    """Run pdfplumber extraction — fast text-layer + table extraction."""
    import pdfplumber

    start = time.time()
    page_outputs = []
    scanned_count = 0
    text_count = 0

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text(x_tolerance=3, y_tolerance=3)

            # Check for tables
            tables = page.find_tables()
            table_mds = []
            for table in tables:
                extracted = table.extract()
                if extracted and len(extracted) >= 2:
                    rows = []
                    for row in extracted:
                        cleaned = [str(c).strip().replace("|", "\\|").replace("\n", " ")
                                   if c else "" for c in row]
                        rows.append(cleaned)
                    max_cols = max(len(r) for r in rows)
                    for r in rows:
                        while len(r) < max_cols:
                            r.append("")
                    lines = []
                    lines.append("| " + " | ".join(rows[0]) + " |")
                    lines.append("| " + " | ".join(["---"] * max_cols) + " |")
                    for row in rows[1:]:
                        lines.append("| " + " | ".join(row) + " |")
                    table_mds.append("\n".join(lines))

            if text and text.strip():
                text_count += 1
                page_md = text
                if table_mds:
                    page_md += "\n\n" + "\n\n".join(table_mds)
                page_outputs.append(page_md)
            elif table_mds:
                text_count += 1
                page_outputs.append("\n\n".join(table_mds))
            else:
                scanned_count += 1
                page_outputs.append(f"<!-- Page {i + 1}: no extractable text (scanned?) -->")

    elapsed = time.time() - start
    md_content = "\n\n---\n\n".join(page_outputs)

    out_path = os.path.join(output_dir, "pdfplumber_output.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    return {
        "engine": "pdfplumber",
        "output_path": out_path,
        "elapsed_seconds": round(elapsed, 1),
        "success": True,
        "error": None,
    }


def _text_quality_score(text: str) -> float:
    """
    Score text readability by checking for common English words/patterns.
    Mirrored or garbled text will score low because real words won't match.
    """
    # Common English words and legal/financial terms likely in documents
    common_words = {
        'the', 'and', 'for', 'that', 'with', 'this', 'from', 'have', 'are',
        'not', 'but', 'was', 'will', 'can', 'all', 'has', 'may', 'should',
        'must', 'shall', 'any', 'been', 'each', 'which', 'their', 'such',
        'fund', 'risk', 'investment', 'return', 'capital', 'review', 'decision',
        'record', 'flow', 'chart', 'section', 'gate', 'start', 'stop',
        'yes', 'date', 'initial', 'amount', 'client', 'policy', 'fiduciary',
        'optimization', 'preservation', 'growth', 'aligned', 'objectives',
        'excluded', 'included', 'adjusted', 'evaluate', 'identified',
        'structure', 'suitable', 'suitability', 'investor', 'mandate',
        'primary', 'final', 'analysis', 'parameters', 'deal', 'new',
        'element', 'key', 'risks', 'negotiate', 'better', 'terms',
        'execution', 'order', 'document', 'page', 'report', 'court',
    }
    words = re.findall(r'[A-Za-z]{3,}', text.lower())
    if not words:
        return 0.0
    matches = sum(1 for w in words if w in common_words)
    return matches / len(words)


def run_tesseract(pdf_path: str, output_dir: str) -> dict:
    """
    Run pytesseract OCR extraction.
    Converts each PDF page to an image via pdf2image, then runs Tesseract OCR.
    This is the fast OCR fallback when Docling is unavailable.

    Handles tricky PDFs by trying multiple orientations AND horizontal flips,
    since some scanned PDFs store images mirrored or rotated.
    """
    from pdf2image import convert_from_path
    from PIL import ImageOps
    import pytesseract

    start = time.time()
    page_outputs = []

    # Convert PDF pages to images
    images = convert_from_path(pdf_path, dpi=300)

    for i, image in enumerate(images):
        best_text = ""
        best_score = -1

        # Try all orientations × flip combinations
        # Orientations: 0°, 90° CW, 90° CCW, 180°
        # Flips: none, horizontal mirror
        transforms = [
            ("normal", lambda img: img),
            ("rot-90cw", lambda img: img.rotate(-90, expand=True)),
            ("rot-90ccw", lambda img: img.rotate(90, expand=True)),
            ("rot-180", lambda img: img.rotate(180, expand=True)),
            ("flip-h", lambda img: ImageOps.mirror(img)),
            ("flip-h-rot-90cw", lambda img: ImageOps.mirror(img).rotate(-90, expand=True)),
            ("flip-h-rot-90ccw", lambda img: ImageOps.mirror(img).rotate(90, expand=True)),
            ("flip-h-rot-180", lambda img: ImageOps.mirror(img).rotate(180, expand=True)),
        ]

        for name, transform in transforms:
            try:
                transformed = transform(image)
                text = pytesseract.image_to_string(transformed)
                if not text.strip():
                    continue

                # Score based on text length AND readability
                length_score = len(text.strip())
                quality = _text_quality_score(text)
                score = length_score * quality

                if score > best_score:
                    best_score = score
                    best_text = text.strip()

                # If we got high-quality text, no need to try more transforms
                if quality > 0.6 and length_score > 200:
                    break
            except Exception:
                continue

        if best_text:
            page_outputs.append(best_text)
        else:
            page_outputs.append(f"<!-- Page {i + 1}: no text detected by Tesseract -->")

    elapsed = time.time() - start
    md_content = "\n\n---\n\n".join(page_outputs)

    out_path = os.path.join(output_dir, "tesseract_output.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    return {
        "engine": "tesseract",
        "output_path": out_path,
        "elapsed_seconds": round(elapsed, 1),
        "success": True,
        "error": None,
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


def load_or_create_manifest(pdf_path: str, engine_dir: str) -> dict:
    """Load existing manifest or create a new one."""
    manifest_path = os.path.join(engine_dir, "manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "pdf_path": pdf_path,
        "page_info": None,
        "engine_dir": engine_dir,
        "results": [],
    }


def save_manifest(manifest: dict, engine_dir: str):
    """Save manifest to disk."""
    manifest_path = os.path.join(engine_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def run_easyocr(pdf_path: str, output_dir: str) -> dict:
    """
    Run EasyOCR extraction — best engine for dark-background slides, inverted
    contrast, and presentation graphics that defeat Tesseract.

    EasyOCR uses a neural network trained on diverse visual layouts, making it
    significantly more robust than Tesseract for non-standard document images
    (white text on dark backgrounds, branded slide decks, watermarked pages).

    Requires easyocr to be installed. If installed to a non-standard --target
    path (e.g. due to disk constraints), set EASYOCR_PATH env var to that
    directory so it gets added to sys.path automatically.

    Models are stored in EASYOCR_MODELS env var path, or ~/.EasyOCR by default.
    First run downloads ~100 MB of models.
    """
    import gc

    # Support non-standard install path (e.g. installed with pip --target)
    easyocr_path = os.environ.get("EASYOCR_PATH", "")
    if easyocr_path and easyocr_path not in sys.path:
        sys.path.insert(0, easyocr_path)

    import easyocr as easyocr_lib
    import numpy as np
    from pdf2image import convert_from_path

    model_dir = os.environ.get(
        "EASYOCR_MODELS", os.path.expanduser("~/.EasyOCR")
    )
    os.makedirs(model_dir, exist_ok=True)

    start = time.time()

    # Initialise reader once (loads neural net models into memory)
    reader = easyocr_lib.Reader(
        ["en"],
        gpu=False,
        model_storage_directory=model_dir,
        verbose=False,
    )

    page_outputs = []
    # 150 DPI keeps memory footprint manageable on CPU
    images = convert_from_path(pdf_path, dpi=150)

    for i, image in enumerate(images):
        img_np = np.array(image)
        del image
        gc.collect()

        try:
            results = reader.readtext(img_np, detail=1, paragraph=False)
            del img_np
            gc.collect()

            # Sort detections top-to-bottom by bounding box y-coordinate
            results_sorted = sorted(results, key=lambda r: r[0][0][1])
            lines = [text for _bbox, text, conf in results_sorted if conf > 0.25]

            if lines:
                page_outputs.append("\n".join(lines))
            else:
                page_outputs.append(
                    f"<!-- Page {i + 1}: no text detected by EasyOCR -->"
                )
        except Exception as e:
            page_outputs.append(f"<!-- Page {i + 1}: EasyOCR error: {e} -->")

    elapsed = time.time() - start
    md_content = "\n\n---\n\n".join(page_outputs)

    out_path = os.path.join(output_dir, "easyocr_output.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    return {
        "engine": "easyocr",
        "output_path": out_path,
        "elapsed_seconds": round(elapsed, 1),
        "success": True,
        "error": None,
    }


def main():
    parser = argparse.ArgumentParser(description="Single-engine PDF extraction")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("--output-dir", "-o", help="Output directory (default: same as PDF)")
    parser.add_argument("--engine", "-e", required=True,
                        choices=["docling", "pdfplumber", "tesseract", "easyocr"],
                        help="Which engine to run (liteparse runs via shell script)")
    args = parser.parse_args()

    pdf_path = os.path.abspath(args.pdf_path)
    if not os.path.exists(pdf_path):
        print(f"ERROR: PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    output_dir = args.output_dir or os.path.dirname(pdf_path)
    stem = os.path.splitext(os.path.basename(pdf_path))[0]
    engine_dir = os.path.join(output_dir, f"{stem}_extraction")
    os.makedirs(engine_dir, exist_ok=True)

    manifest = load_or_create_manifest(pdf_path, engine_dir)

    if not manifest["page_info"]:
        print(f"Analyzing: {pdf_path}")
        manifest["page_info"] = detect_scanned_pages(pdf_path)

    page_info = manifest["page_info"]
    print(f"Pages: {page_info['total']} (text: {page_info['text_pages']}, "
          f"scanned: {page_info['scanned_pages']})")
    force_ocr = page_info["scanned_pages"] > 0

    engine_name = args.engine
    print(f"\n--- Running {engine_name} ---")
    try:
        if engine_name == "docling":
            result = run_docling(pdf_path, engine_dir, force_ocr)
        elif engine_name == "pdfplumber":
            result = run_pdfplumber(pdf_path, engine_dir)
        elif engine_name == "tesseract":
            result = run_tesseract(pdf_path, engine_dir)
        elif engine_name == "easyocr":
            result = run_easyocr(pdf_path, engine_dir)

        with open(result["output_path"], "r", encoding="utf-8") as f:
            md_text = f.read()
        result["metrics"] = quality_metrics(md_text, page_info["total"])
        print(f"  Done in {result['elapsed_seconds']}s, "
              f"{result['metrics']['total_chars']} chars, "
              f"alnum ratio: {result['metrics']['alnum_ratio']:.1%}")
    except Exception as e:
        result = {
            "engine": engine_name,
            "output_path": None,
            "elapsed_seconds": 0,
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "metrics": None,
        }
        print(f"  FAILED: {e}")

    existing = [i for i, r in enumerate(manifest["results"]) if r["engine"] == engine_name]
    if existing:
        manifest["results"][existing[0]] = result
    else:
        manifest["results"].append(result)

    save_manifest(manifest, engine_dir)
    manifest_path = os.path.join(engine_dir, "manifest.json")
    print(f"\nManifest: {manifest_path}")

    print("\n=== QUALITY COMPARISON ===")
    print(f"{'Engine':<12} {'Chars':>8} {'Alnum%':>8} {'Ch/pg':>8} "
          f"{'Headings':>8} {'Tables':>8} {'Markers':>8} {'Time':>8}")
    print("-" * 80)
    for r in manifest["results"]:
        if r["success"] and r["metrics"]:
            m = r["metrics"]
            print(f"{r['engine']:<12} {m['total_chars']:>8} "
                  f"{m['alnum_ratio']:>7.1%} {m['chars_per_page']:>8.0f} "
                  f"{m['heading_count']:>8} {m['table_count']:>8} "
                  f"{m['structural_markers']:>8} {r['elapsed_seconds']:>7.1f}s")
        else:
            print(f"{r['engine']:<12} {'FAILED':>8}")


if __name__ == "__main__":
    main()
