---
name: pdf-intake
description: "The front door for ANY PDF entering a matter or project: assess quality, route to the right extraction tool, produce a Markdown version, vision-verify it against the rendered pages, and leave page images on file so the content is visually available for all further work. Use this skill whenever a new PDF arrives and its content must become reliably usable — 'read this PDF', 'get this PDF into the matter', 'convert/extract this PDF', 'is this scan usable', 'OCR this', 'make an MD version', or when a prior extraction looks wrong (garbled order, reversed text, broken table headers, bad handwriting OCR). It orchestrates abc-pdf for engine extraction and ADDS the mandatory vision fidelity gate that abc-pdf lacks; prefer pdf-intake over calling abc-pdf directly whenever the output will be relied on. Not for whole-folder intake (matter-index) or bulk substantive reading (map) — but those workflows should call pdf-intake for their problem files."
---

# PDF Intake — assess, route, extract, vision-verify

Statistical legibility checks (chars/page, alnum ratio) tell you text VOLUME is
healthy. They are blind to the failures that actually corrupt meaning: wrong
reading order, rotated text extracted as reversed character soup, table headers
bled into data rows, 0/O–1/I confusables silently normalised, handwriting
mis-OCR'd into plausible garbage, annotations and footers dropped by consensus
merging. Every one of these was observed in testing (August 2026) on outputs
that PASSED the statistical checks.

**Core rule: no extraction is trusted until it has been compared, by eye,
against the rendered page image. Claude's vision is the strongest engine
available — it is the arbiter, and for handwriting it is the primary engine.**

## Outputs (per PDF)

```
{stem}.md            # final Markdown, with a FIDELITY header comment
{stem}_pages/        # page PNGs at 150 dpi — KEEP; downstream work Reads these
{stem}_extraction/   # engine outputs + fidelity.json (audit trail)
```

The `_pages/` folder is a first-class deliverable: it is what makes the
document *visually available* for later queries, citation checks and drafting.
Never delete it after extraction.

## Step 1 — Assess (seconds, always)

Reuse the abc-pdf skill's venv and triage:

```bash
SKILL_DIR=...                                 # this skill's install path
ABC="$SKILL_DIR/../abc-pdf"                   # sibling skill in this plugin
bash "$ABC/scripts/setup.sh"                  # idempotent
VENV_PY="$ABC/.venv/bin/python"

"$VENV_PY" "$ABC/scripts/triage.py" "INPUT.pdf"          # strategy + corruption check
"$VENV_PY" "$SKILL_DIR/scripts/probe_flags.py" "INPUT.pdf"  # per-page risk flags
```

Render pages in the same step (needed later regardless):

```bash
mkdir -p "OUT/{stem}_pages" && pdftoppm -png -r 150 "INPUT.pdf" "OUT/{stem}_pages/page"
```

Triage answers *how much OCR*; probe_flags answers *where vision is
non-negotiable*: `rotated_text`, `tables`, `multi_column_or_panels`,
`image_heavy`, `confusable_identifiers`, `no_text_layer`.

## Step 2 — Route

| Assessment | Route | Rationale |
|---|---|---|
| Native text, no flags | pdfplumber only (abc-pdf fast) | cheap and lossless |
| Native text + any flag | pdfplumber, then vision repair of flagged pages | engines cannot fix order/rotation; vision can |
| Scanned, printed text | tesseract + docling (abc-pdf full), merge | consensus helps on print |
| Scanned, ≤5 pages | engines optional — vision transcription may be faster and better | one Read per page beats 60s of OCR |
| Handwriting suspected (scanned + engines disagree wildly, or cursive visible in the page image) | **vision-first transcription**; OCR only as a cross-check, never as the deliverable | OCR on handwriting produces plausible garbage (observed: "QX-91B" → "QX-91LB") |
| Corrupt text layer (triage `encoding_warning`) | OCR engines + vision; tell the user the text layer was corrupt | per abc-pdf rules |
| Heavy diagonal watermarks on a scan (repeated stamps like COPY / DRAFT / PRIVILEGED visible in the page image, or OCR output laced with watermark fragments) | vision-first for short docs; for long docs, re-render pages with binarisation (`pdftoppm -png -r 300` then threshold, e.g. ImageMagick `-threshold 60%`) and re-OCR the cleaned image — watermarks are printed light and threshold out; expect the consensus merge to pick wrong sections, so read the RECOVERED CONTENT block against the merged body | observed: watermarked forensic report reduced both OCR engines to fragments while the loss-check block held the real prose |

Efficiency rules learned in testing:
- Do not run liteparse by default (observed to fail silently, producing nothing); use it only if tesseract AND docling both fail.
- Per-page OCR: honour `pages_needing_ocr` from triage — never OCR a full native-text record for a few scanned pages.
- For single-page or few-page difficult documents, skip multi-engine ceremony entirely and transcribe from the page image; note this in the FIDELITY header.

## Step 3 — Extract

Run the routed abc-pdf engines exactly as the abc-pdf SKILL.md specifies (one
Bash call per engine, manifest, merge for standard/full). For vision-first
routes, skip to Step 4.

## Step 4 — Vision fidelity gate (MANDATORY — this is the step abc-pdf lacks)

Read the page PNGs and compare against the draft Markdown:

- **≤10 pages:** every page.
- **>10 pages:** every page flagged by probe_flags or triage, plus a random
  sample of ~20% of the rest (minimum 3). If any sampled page fails, widen the
  sample.

Per page, check specifically (the failure modes engines cannot see):
1. **Reading order** — does the MD sequence match the visual reading order? Re-sequence if not; layout cues (boxes, rules, arrows, "read X before Y") govern.
2. **Rotated/vertical text** — margin notes, vertical table headers, side labels. Transcribe from the image; label position and orientation, e.g. `## MARGIN NOTE (rotated 90°, right edge)`.
3. **Tables** — headers correct (not reversed, not bled into row 1)? Row-to-remark alignment preserved? Verify identifier cells character-by-character.
4. **Confusable identifiers** (0/O, 1/I/l, 5/S, 8/B, 2/Z) — verify each flagged code visually. Where genuinely undecidable at 150 dpi, re-render that page at 300 dpi; if still undecidable, mark `[?]` — never silently normalise.
5. **Handwriting, annotations, stamps and redactions** — marginalia, strikethroughs, checkbox states, signatures, arrows, ink colour; court stamps (RECEIVED/FILED with dates) kept distinct from body text OCR fuses them into; redaction bars represented explicitly as `[REDACTED — black bar in supplied copy]`, never as blank cells or dropped words; watermark fragments removed from body text but the watermark's existence noted in the FIDELITY header (a COPY / NOT FOR FILING mark is itself material information about the document).
6. **Completeness** — headers, footers, filed-by lines, page labels. Consensus merges drop content one engine caught; restore from the image.

Repair the MD from the image wherever it disagrees — **the image wins, always**.
Rate each checked page GREEN (matches), AMBER (repaired minor), RED (rewritten
from image). Record in `{stem}_extraction/fidelity.json`:
`{page, rating, checks_failed, repairs}`.

## Step 5 — Deliver

Prepend a FIDELITY header comment to the final MD:

```markdown
<!-- FIDELITY: vision-verified | engines: <list or 'vision-only'> | pages vision-checked: <n>/<total>
     Repairs: <one line per material repair, esp. identifiers and dropped content>
     Unresolved: <[?] items needing the physical document, or 'none'> -->
```

Report to the user: route taken, per-page ratings, every repaired identifier,
and anything still `[?]`. In legal matters the `[?]` list is a *to-confirm*
list — a gap is better than a fabrication.

Then per house rules: the MD from a scanned or handwritten source is a working
transcript, not a citable source; quotes for deliverables still go through
citation-verifier against the source PDF.

## Escalation

If the vision gate RED-rates pages and vision itself cannot read them (truly
illegible scan): stop, deliver what is legible with explicit gaps, and offer
the legibility-review skill (structured uncertainty resolution) or
handwriting-narration (guided intake with the user) rather than guessing.
