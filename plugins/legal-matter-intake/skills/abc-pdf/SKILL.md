---
name: "abc-pdf"
description: "ENGINE ROOM for PDF extraction — multi-engine PDF to Markdown (pdfplumber, Docling, EasyOCR, pytesseract, liteparse) with automatic triage and consensus merging. Do NOT invoke directly for a PDF entering a matter: the pdf-intake skill is the front door — it calls abc-pdf and adds the vision fidelity gate abc-pdf lacks. Invoke abc-pdf directly only when pdf-intake is unavailable, or for scratch extraction whose output will not be relied on (including \"quick read\" / \"fast pdf\" requests). Replaces the retired light-pdf and docling-pdf-convert skills."
---

# Multi-Engine PDF to Markdown Extraction

## Position in the pipeline — read first

This skill is the ENGINE ROOM, not the front door. For any PDF entering a matter or project, or any extraction whose output will be relied on for legal work, use the **pdf-intake** skill: it assesses the PDF, calls this skill for engine extraction, then vision-verifies the output against the rendered pages and leaves page images on file — a fidelity gate this skill does not have. Use abc-pdf directly only when pdf-intake is unavailable, or for scratch/disposable extraction.

Convert any PDF to high-quality Markdown using up to five complementary engines — **pdfplumber** (native text), **Docling** (OCR + layout), **EasyOCR** (neural-net OCR), **pytesseract** (Tesseract OCR), and **liteparse** (Tesseract.js OCR) — with intelligent triage that picks the right combination based on each PDF's characteristics.

Triage is fronted by a fast **pdf-inspector** probe (see Step 2), which catches corrupt text layers that the density heuristic alone scores as healthy.

## Why multiple engines?

| Engine | Speed | OCR | Structure | Best at |
|--------|-------|-----|-----------|---------|
| **pdfplumber** | ~2s | None | Text + tables | Native-text PDFs, table extraction |
| **Docling** | ~15-30s | Yes (EasyOCR) | Markdown with headings/tables/lists | Structured documents, layout understanding |
| **EasyOCR** | ~10-30s | Yes (neural net) | Plain text | Dark backgrounds, white-on-dark slides, inverted contrast, presentation graphics |
| **pytesseract** | ~5-15s | Yes (Tesseract) | Plain text | Fast OCR fallback, widely available |
| **liteparse** | ~10-30s | Yes (Tesseract.js) | Text + bounding boxes | Second OCR perspective, spatial data |

**When to prefer EasyOCR over Tesseract:** EasyOCR handles presentation slides, branded cover pages, and any image where text appears in non-standard contrast (white on dark, light on gradient). Tesseract assumes dark text on a light background and fails silently on inverted images. EasyOCR's neural network has no such assumption.

Consensus merging across engines produces better output than any single engine because different OCR engines catch different errors, and pdfplumber's text-layer extraction is lossless for native-text pages.

## Setup — Runs Automatically on First Use

The skill auto-installs dependencies into a local virtual environment. No manual setup required — the first run takes longer (~2-5 min) while it installs, subsequent runs are fast.

```bash
SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"
bash "$SKILL_DIR/scripts/setup.sh"
```

The setup script creates `.venv/` inside the skill directory. All Python engines run through this venv. The `SKILL_DIR` variable must always resolve to the directory containing this SKILL.md file.

**Determining SKILL_DIR:** When Claude invokes this skill, it knows the skill's install path from the skill metadata. Set `SKILL_DIR` to that path before running any script. For example, if the skill is installed at `/path/to/plugin/skills/abc-pdf/`, then `SKILL_DIR=/path/to/plugin/skills/abc-pdf`.

## Input

The user provides a PDF path. If no path is given, search the current directory for PDFs using Glob and ask which one to convert.

## Workflow

### Step 1: Setup (idempotent — safe to run every time)

```bash
bash "$SKILL_DIR/scripts/setup.sh"
VENV_PY="$SKILL_DIR/.venv/bin/python"
```

If setup fails for some engines, it still succeeds for the basics (pdfplumber + pytesseract). Check the output to see which engines are available.

### Step 2: Triage

```bash
"$VENV_PY" "$SKILL_DIR/scripts/triage.py" "INPUT_PATH"
```

This classifies the PDF and recommends a strategy:

| Strategy | When | Engines | Time |
|----------|------|---------|------|
| **fast** | 100% native text, high density (>800 ch/pg) | pdfplumber only | ~2-5s |
| **standard** | Mixed text/scanned, or low density | pdfplumber + best available OCR | ~15-30s |
| **full** | Mostly scanned, corrupt text layer, or user wants best quality | All available engines | ~30-60s |

If the user asks for "best quality" or "thorough", override to `full`.

#### Text-quality check — judge the text, not its volume

`assess_text_quality()` runs on pdfplumber's own output on every triage,
**with or without pdf-inspector**. It exists because the chars-per-page
heuristic is blind to corruption: a PDF with a broken CID or ToUnicode map
makes pdfplumber return literal `(cid:4)(cid:1)(cid:30)` garbage, and because
those sequences are long they *inflate* the character count. One test fixture
scores **13,338 chars/page of pure `(cid:NNN)` noise** and, on the old
heuristic, was routed to `fast` — pdfplumber-only, no merge, garbage delivered
as the text of a judgment.

The check flags text where the unmapped-glyph ratio exceeds 5%, replacement
characters exceed 5%, or the alphanumeric ratio falls below 60%. On a hit,
strategy is forced to `full`, a warning is printed, and `--force-strategy fast`
is **refused**.

#### The pdf-inspector pre-probe

Before the pdfplumber page walk, triage runs `scripts/pdfi_probe.py` in a
sandboxed child process. It is **advisory only** and contributes:

1. **Speed.** Classification takes milliseconds. On documents over 50 pages,
   triage samples rather than walking every page — 6.3 s instead of 32.9 s on a
   269-page document.
2. **Per-page OCR routing.** `pages_needing_ocr` (1-indexed) tells you which
   pages actually need OCR, so a mostly-native record does not get OCR'd end
   to end.
3. **A second opinion on font decoding**, cross-checked against the text
   quality above.

**On engine disagreement.** pdf-inspector's `has_encoding_issues` reports
whether *pdf-inspector* could decode the fonts — which is not the same question
as whether pdfplumber could. It flags some documents (notably CJK Identity-H)
that pdfplumber reads perfectly. So the probe alone never escalates:

| pdf-inspector | pdfplumber text quality | Result |
|---|---|---|
| encoding broken | fails quality check | `full` + hard warning — corruption confirmed by both |
| encoding broken | passes quality check | `standard` + "engines disagree" note — verify against OCR, never `fast` |
| clean | fails quality check | `full` + hard warning — quality check stands alone |
| clean | passes quality check | normal density-based strategy |

**Hard rule: pdf-inspector never supplies extracted text.** It is not in the
engine list and must not be added to it. Its Markdown silently corrupts legal
prose in two ways — it wraps hanging-indent sub-paragraphs in Markdown table
pipes (splitting `(iv) Statement. If the application…` into
`|(iv)|Statement|. If the application…`), and it inlines superscript footnote
markers into the running text, including inside case names. Extraction stays
with pdfplumber, Docling and the OCR engines.

If pdf-inspector is not installed, or the probe fails, times out, or hits its
2 GB memory cap, triage falls back to the original pdfplumber-only behaviour
with no change in output. Pass `--no-pdfi` to skip the probe deliberately.

**When the probe reports `encoding_broken`, tell the user.** Text from that
document is unverified until checked against the source, and must not be
quoted in a deliverable on the strength of this extraction alone.

### Step 3: Run Engines

Create the extraction directory and run engines recommended by triage. Each engine runs as a **separate Bash command** (important for stability).

```bash
STEM="$(basename 'INPUT_PATH' .pdf)"
EXTRACT_DIR="OUTPUT_DIR/${STEM}_extraction"
mkdir -p "$EXTRACT_DIR"
```

**pdfplumber** (always runs):
```bash
"$VENV_PY" "$SKILL_DIR/scripts/run_engines.py" "INPUT_PATH" --engine pdfplumber --output-dir "OUTPUT_DIR"
```

**Docling** (standard + full, if available):
```bash
"$VENV_PY" "$SKILL_DIR/scripts/run_engines.py" "INPUT_PATH" --engine docling --output-dir "OUTPUT_DIR"
```

**EasyOCR** (standard + full, preferred over Tesseract for image-heavy pages):
```bash
EASYOCR_PATH="/path/to/easyocr/packages" \
EASYOCR_MODELS="/path/to/easyocr/models" \
"$VENV_PY" "$SKILL_DIR/scripts/run_engines.py" "INPUT_PATH" --engine easyocr --output-dir "OUTPUT_DIR"
```
Install: `pip install easyocr`. If disk space is limited, install to a custom path:
`pip install easyocr --target /your/spacious/disk/easyocr_packages`
then set `EASYOCR_PATH` to that directory.

**pytesseract** (standard + full, fallback if EasyOCR and Docling unavailable):
```bash
"$VENV_PY" "$SKILL_DIR/scripts/run_engines.py" "INPUT_PATH" --engine tesseract --output-dir "OUTPUT_DIR"
```

**liteparse** (full only, if available):
```bash
bash "$SKILL_DIR/scripts/run_liteparse.sh" "INPUT_PATH" "$EXTRACT_DIR"
```
The script now fails loudly (non-zero exit, stderr shown) if liteparse errors
or produces an empty output file — previously it failed silently and the
pipeline believed the engine had run. Check its exit status; on failure,
continue with the other engines and say so in the report. Known failure mode:
liteparse downloads tessdata at first OCR run and fails offline or when the
download is blocked (HTTP 403).

After all engines, build the manifest:
```bash
"$VENV_PY" "$SKILL_DIR/scripts/build_manifest.py" "INPUT_PATH" "$EXTRACT_DIR"
```

If an engine fails, continue with the rest. At least one must succeed.

### Step 4: Merge

For **fast** strategy (pdfplumber only), skip merge — use pdfplumber output directly.

For **standard** and **full**:
```bash
"$VENV_PY" "$SKILL_DIR/scripts/merge_consensus.py" "$EXTRACT_DIR/manifest.json"
```

The merger scores each engine and picks the best content per-section, per-page, or overall.

The merge then runs a **content loss-check**: substantive lines captured by any
engine but absent from the merged text (e.g. a footer only one engine caught)
are appended under a `RECOVERED CONTENT` marker and listed in
`merge_report.json` under `recovered_content`. If the marker is present, verify
the recovered lines' placement against the page image before delivery — never
deliver the file with the marker still unreviewed.

### Step 5: Legibility Verification

Run the legibility checks on the final output. Use the inline Python verification described in the triage output, or check:
- Content density (≥500 chars/page)
- Character quality (≥70% alphanumeric)
- Page coverage (≥3 lines/page)

| Rating | Action |
|--------|--------|
| **GREEN** | All checks pass. Copy as final `.md`. |
| **AMBER** | 1-2 checks fail. Proceed with warning. |
| **RED** | 3+ fail or char quality <60%. Auto-escalate to next strategy. |

### Step 6: Deliver

1. Copy final markdown to same directory as input PDF, same name with `.md` extension
2. Report: strategy used, legibility rating, which engines contributed, processing time, character count
3. If triage raised `encoding_warning`, say so explicitly in the report — the
   source text layer was corrupt and the output came from OCR
4. Per-engine outputs remain in `{stem}_extraction/` for reference
5. If this run was invoked by pdf-intake, hand the merged output and the
   extraction directory back to pdf-intake for its vision fidelity gate — the
   pipeline is not finished until that gate has run.
