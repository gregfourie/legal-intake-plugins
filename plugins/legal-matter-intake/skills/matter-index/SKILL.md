---
name: matter-index
description: "Build or refresh a matter's _index/ from a folder of legal documents (PDF, DOCX, XLSX, MSG, EML, TXT, MD) so later sessions get the lay of the matter cheaply. Triggers: index this matter, re-index, what documents are in here, inventory the documents, get to grips with the bundle. Run last in every intake."
---

# Matter index

## Purpose

Turn a matter folder into a persistent markdown index that Claude reads first in later sessions.

- `_index/index.md` — one structured entry per document (type, date, parties, case number, pages, each with a confidence flag).
- `_index/docs/NNNN_*.md` — full extracted text per document, with a metadata header.
- `_index/_illegible.md` — scanned, failed or password-protected files.
- `## Probable versions` at the foot of `index.md` — pairs that look like the same document in another file or format (docx/pdf, two scans of one judgment, draft v signed). A reading list, never a fact.
- `_index/_state.json` — SHA-256 cache. Re-runs process only new or changed files. Exact duplicates are recorded once.

## What this skill does NOT do

- No AI summaries. All metadata is heuristic, with a confidence flag.
- No OCR. Scanned PDFs (under about 200 characters a page) go to `_illegible.md`. Route them to pdf-intake.
- Never deletes, moves or edits source files. Never trims extracted text.

## Scope

The engine skips any file or folder whose name starts with `_` or `.` (`_inbox`, `_intake`, `_quarantine`, `_index`, `.git`), the folders `01 Hopper`, `05 Archive`, `06 Audits`, `Bookmarked PDFs`, `legibility-review`, `Previous Drafts`, `eml`, `needs adobe ocr`, and the control files `_matter.md`, `MATTER.md`, `LESSONS.md`, `AGENTS.md`, `START HERE.md`, `Index.md`. Add `--exclude-dir NAME` or `--exclude-file NAME` for more (e.g. a record bundle of hundreds of MB). State the scope in the report.

## Mirror mode (optional)

If the matter has `.ai/mirror-index.json` and `.ai/mirrors/` (from an intake pipeline that writes verified text mirrors), the engine reads text from the mirrors instead of re-extracting, flags STALE mirrors, and runs a gate: it ends with `GATE: PASS` or `GATE: FAIL` (exit 2) when a mirror is text-poor. On FAIL, report the list and let the user choose: OCR and re-run, or proceed with `--no-gate` and carry each gap by name. Without those files the engine runs in normal mode and this section does not apply.

## Steps

### 1. Confirm inputs

Find `_intake-config.md` in the matter folder or the nearest parent folder and use its settings. If there is none, run intake-setup first. The engine reads `_intake-profile.json` from the same place for court names and case-number patterns (`--profile` overrides).

MATTER_PATH; OUTPUT_PATH (default `MATTER_PATH/_index/`); recursive (default yes); force re-extract (default no). If the user already said "re-index" or picked the option from a menu, run without re-asking.

### 2. Dependencies

```bash
python3 -c "import pdfplumber, docx, openpyxl, extract_msg" 2>/dev/null || \
  pip install pdfplumber python-docx openpyxl extract-msg --break-system-packages --quiet
```

If install fails, show the error and stop.

### 3. Run the engine where the files are

`SKILL_DIR` is this skill's install folder.

```bash
python3 "$SKILL_DIR/scripts/build_index.py" "<MATTER_PATH>" "<MATTER_PATH>/_index"
```

Options: `--no-recursive`, `--force`, `--exclude-dir NAME`, `--exclude-file NAME`, `--mirror-index PATH`, `--gate` / `--no-gate`, `--no-versions`, `--profile PATH`. Exit codes: 0 pass, 2 gate failed (index written), 3 refused.

If the shell call has a time limit, run in the foreground with `timeout`, not in the background. `_state.json` is written only at the end, so a killed run keeps nothing. For a large matter, index subfolders in separate calls (`--no-recursive` per folder into the same OUTPUT_PATH).

### 4. Reconcile and report

Report: files indexed / skipped / problems; path to `index.md`; type counts (`grep '^- \*\*Type:' index.md | sort | uniq -c`); anomalies (zero-byte, password-protected, odd extensions); the scope excluded. Offer pdf-intake for files in `_illegible.md`. Do not run OCR without the user's go-ahead.

Tell the user once: the index is at `_index/index.md`; future sessions read it first and open a reading copy only when detail is needed.

### 5. Matter context file

If `_matter.md` does not exist, hand over to the new-matter skill (retrofit mode). If it exists, do not overwrite it; offer to fill open `[TO CONFIRM]` items and apply only what the user confirms.

## Known limits

- Heuristic metadata is fallible. Treat `low`/`medium` fields as starting points; open the source if a field matters. Type detection misclassifies hybrids; date detection may pick a referenced deadline instead of the document date; parties, court and case number need a standard heading and work best with a jurisdiction profile.
- Exact duplicates are found by hash. The probable-versions pass is heuristic: two versions with unlike titles and different opening pages are missed.
- DOCX text carrying `<!-- PARA n -->` markers is counted and cited as (docx, para n).
- XLSX: structure and first rows only. `.msg`/`.eml`: header and body; attachments listed, not extracted.
- Index order is processing order, not chronological.

## Not for

- A single document — read it directly.
- Chronologies or substantive analysis — use a chronology or analysis skill.
- Email-chain reconstruction — email-chain-extraction.
- High-accuracy extraction of one PDF — pdf-intake.

## Verification

Never cite from the index alone. Anything going into a pleading, opinion, letter or memo is checked in the reading copy and, where wording matters, in the source file.
