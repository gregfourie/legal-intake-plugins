#!/usr/bin/env python3
"""probe_flags.py — per-page risk flags that text statistics miss.

Runs AFTER (or alongside) abc-pdf triage. Detects, per page:
  - rotated / non-upright text (vertical headers, margin notes)
  - suspicious reading order (large horizontal gaps between text clusters -> multi-column / panels)
  - table presence
  - image coverage (scanned or image-heavy pages)
  - identifier confusables (0/O, 1/I/l, 5/S, 8/B adjacent inside alphanumeric codes)

Output: JSON to stdout. Every flagged page MUST be vision-checked before the
extraction is treated as reliable.

Usage: python probe_flags.py INPUT.pdf
Requires pdfplumber (use the abc-pdf skill's .venv).
"""
import json
import re
import sys


def main(path: str) -> None:
    import pdfplumber

    confusable = re.compile(r"\b(?=[A-Z0-9-]{4,})[A-Z0-9]*[-]?[A-Z0-9]*(?:0O|O0|1I|I1|l1|5S|S5|8B|B8|2Z|Z2)[A-Z0-9-]*\b")
    out = {"pdf": path, "pages": []}
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            chars = page.chars
            n = len(chars)
            non_upright = sum(1 for c in chars if not c.get("upright", True))
            tables = page.find_tables()
            img_area = sum(
                max(0, (im["x1"] - im["x0"])) * max(0, (im["bottom"] - im["top"]))
                for im in page.images
            )
            page_area = float(page.width * page.height) or 1.0
            text = page.extract_text() or ""
            codes = confusable.findall(text)

            # crude multi-column / panel detection: bimodal x-distribution of chars
            multi_col = False
            if n > 50:
                xs = sorted(c["x0"] for c in chars)
                gaps = [(xs[j + 1] - xs[j]) for j in range(len(xs) - 1)]
                if gaps and max(gaps) > page.width * 0.18:
                    multi_col = True

            flags = []
            # Ratio OR absolute count: a vertical table header or rotated margin
            # label is ~10-40 chars on a dense page and never clears a pure
            # percentage threshold (observed misses: privilege-log vertical
            # headers at 1.6%, transcript margin label at 1.3%).
            if n and (non_upright / n > 0.02 or non_upright >= 8):
                flags.append("rotated_text")
            if tables:
                flags.append("tables")
            if img_area / page_area > 0.5:
                flags.append("image_heavy")
            if multi_col:
                flags.append("multi_column_or_panels")
            if codes:
                flags.append("confusable_identifiers")
            if n == 0:
                flags.append("no_text_layer")

            out["pages"].append(
                {
                    "page": i,
                    "chars": n,
                    "non_upright_chars": non_upright,
                    "table_count": len(tables),
                    "image_area_ratio": round(img_area / page_area, 3),
                    "confusable_codes_sample": codes[:10],
                    "flags": flags,
                }
            )
    out["pages_needing_vision"] = [p["page"] for p in out["pages"] if p["flags"]]
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: probe_flags.py INPUT.pdf")
    main(sys.argv[1])
