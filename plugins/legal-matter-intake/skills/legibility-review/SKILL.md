---
name: "legibility-review"
description: "Methodical legibility review and full-text transcription of one document or a folder of documents (PDFs, scanned images, DOCX), with structured uncertainty resolution before any text is committed. Use whenever the user wants to transcribe a document, check whether a scan is legible, produce a clean text version of a bundle, verify handwritten passages, resolve unclear stamps/signatures/dates, or prepare a reliable transcript of correspondence, pleadings, affidavits, contracts, financial notes, or any mixed bundle. Trigger on phrases like \"legibility review\", \"transcribe this\", \"transcribe the bundle\", \"check the legibility\", \"is this readable\", \"clean transcription\", \"/legibility_review\", \"/legibility-review\", or any request to turn a hard-to-read source into a reliable text record. Prefer this skill over a one-shot OCR dump whenever accuracy matters and the source contains handwriting, stamps, faint print, mixed scans, or sensitive identifiers (names, dates, case numbers, statutory refs, amounts)."
---

# legibility-review

A structured workflow for producing a **reliable full-text transcription** of one or more source documents, with uncertainties resolved through targeted questions to the user before any text is committed to the final transcript.

The skill is designed for legal/professional use where accuracy on identifiers (names, dates, case numbers, statutory references, amounts, contact details) matters more than speed. Conservative phrasing beats confident phrasing that turns out to be wrong. Where the source is illegible and cannot be resolved by cross-reference, the skill asks rather than guesses.

The skill works on:

- a single file (PDF, scanned image, DOCX), or
- a folder of files — processed **sequentially per document**, but with a **pre-built cross-reference index** so cleaner copies of the same content elsewhere in the bundle can silently resolve uncertainties in any other document.

---

## Step 0 — Locate the source material and determine mode

Before doing anything else:

1. Identify where the source lives. In order of preference:
   - A folder path the user has named (e.g. "the `incoming/` folder", "this Drive folder").
   - Files attached to the current chat (look in `/mnt/user-data/uploads/` if running on Claude.ai).
   - Files in the project workspace.
2. List the source. Note for each file:
   - Filename, file type, size.
   - Page count (for PDFs) or a sense of length (for DOCX/images).
   - Whether it is native-text or scanned (relevant for PDF extraction strategy).
3. State the **mode** in one line, then proceed:
   - **Single-file mode** — one source document.
   - **Folder mode** — multiple source documents; sequential processing with cross-reference index.

If anything is ambiguous about scope (e.g. the folder contains both source documents and unrelated material), ask once, then proceed.

### Working folder for persistent artefacts

Create a `legibility-review/` subfolder in the working directory. All persistent artefacts live there:

- `index.md` — cross-reference index across all source docs (folder mode only).
- `transcripts/<docname>.md` — one transcript per source document.
- `queue/<docname>.md` — running verification log per document (questions asked, answers received, items resolved by cross-reference).
- `final-note.md` — final legibility note (written in Step 4).

If artefacts already exist from a prior run, ask the user whether to resume, overwrite, or start fresh in a different folder.

---

## Step 0.5 — Extract text from every source file (folder mode: build the index)

Before triage, extract text from every source file. This is what makes silent cross-reference resolution possible later.

**File-type-specific extraction strategy** (use the best available tool):

- **Native-text PDF** (digitally generated — pleadings, judgments, modern correspondence): extract with pdfplumber (the `abc-pdf` skill's fast path), otherwise plain text extraction.
- **Scanned PDF, complex layout, or mixed-quality PDF**: use the `pdf-intake` skill — the front door that routes to `abc-pdf` multi-engine OCR with consensus and vision-verifies the result. If `pdf-intake` is unavailable, call `abc-pdf` directly.
- **Image (JPG/PNG/TIFF)**: rasterise if needed, then OCR with the best available tool (tesseract via pytesseract, or read directly with vision if the model supports it).
- **DOCX**: extract directly using python-docx or the `docx` skill.

If a file cannot be extracted at all (e.g. encrypted PDF, corrupted file), record it as illegible and tell the user before proceeding.

**Folder mode only** — write `index.md` containing:

```
# Cross-reference index

## Files
- doc1.pdf — [type, pages, extraction quality: clean / partial / OCR-needed]
- doc2.pdf — ...

## Likely duplicate or overlapping content
- doc1.pdf pp.3–5 appears to duplicate doc4.pdf pp.1–3 (cleaner copy in doc4)
- doc2.pdf §§14–20 reproduced as exhibit in doc7.pdf pp.12–18

## Identifiers seen across multiple docs
- Case number "JR 1234/24" — appears in doc1, doc3, doc6
- "Mr T. Khumalo" — appears in doc1, doc2 (signature block), doc5
- Date "14 March 2024" — appears in doc1 §3, doc4 cover page

## Structural issues / gaps
- Bates jump between doc3 and doc4 (last Bates of doc3 is 0078, first of doc4 is 0085)
- doc6 appears truncated (ends mid-sentence on p.4 of a 4-page scan)
```

This index is the cross-reference map. When an uncertainty arises later, consult this index first to find a cleaner copy of the same content.

---

## Step 1 — Quick triage (per document)

For each source document, in order, produce a **short triage note** — no more than ~150 words — covering:

- Page count and what kind of document it is (single document, several stitched together, exhibit bundle, etc.).
- Any structural issues specific to this document: Bates number gaps, internal pagination jumps, trimmed sections, duplicate pages.
- The approximate number of uncertainties identified that will need user confirmation.

Nothing else at this stage. No page-by-page report. No preamble.

Then move straight to Step 2 for that document.

---

## Step 2 — Verification queue (the main work)

Work through uncertainties in the current document **one at a time**.

### Before raising any uncertainty with the user

Try to resolve it silently by cross-referencing other copies of the same content:

- In single-file mode: look elsewhere in the same document (e.g. a clearer copy of the same letter further on, a typed version of a handwritten note, a recital in a later document that repeats the unclear passage).
- In folder mode: also consult `index.md` and the other extracted source files. If a cleaner copy exists elsewhere in the bundle, use it.

If resolved by cross-reference, **do not ask the user**. Log it in `queue/<docname>.md`:

```
## Resolved by cross-reference
- Page 3, handwritten date in "Date" field — confirmed as "14 March 2024" by cross-reference to doc4.pdf p.1 where the same date appears in typed form.
```

### When to ask the user

Only bring an uncertainty to the user if **all** of the following are true:

- It cannot be resolved by cross-reference.
- It could materially affect transcription accuracy, legal substance, or an identifier (name, date, case number, statutory reference, contact detail, amount).
- Confidence is medium or lower.

Do not ask about minor imperfections that don't affect meaning or identifiers.

### Format of each question

Ask **one question at a time**. Wait for the answer. Log it. Move on.

For each question, give the user:

1. Document name (folder mode) and page number.
2. Bates/page reference if visible on the page.
3. Exact location on the page (e.g. "handwritten Tel field", "sub-paragraph 3.1.2", "bottom-right stamp").
4. The text you think it says.
5. Your confidence level: high / medium / low.
6. Why it matters in one short sentence.
7. The specific point you need confirmed.
8. **A cropped image of the relevant area, made visible to the user in the chat.**

### How to produce the cropped image

The crop is essential — the user must be able to see the same image you are looking at, not just read your description.

Process:

1. Rasterise the relevant PDF page at **200 DPI or higher** (use `pdf2image` or `pypdfium2`).
2. Identify the area in question. If you have a layout-aware extraction (e.g. via docling or PyMuPDF), use the bounding box of the relevant element. Otherwise, crop a generous rectangle around where you saw the unclear text.
3. Crop the rasterised page to that area using PIL.
4. Save the crop as a JPG (or PNG) at a sensible resolution.
5. **Present the crop inline.**
   - If the `present_files` tool is available, call it on the crop file so it renders inline in the chat.
   - If `present_files` is not available, **say so explicitly** — for example: "I cannot present the cropped image inline in this environment. The crop is saved at `<path>`. Please open it before answering, or tell me to proceed without a visible crop." Do not silently proceed without the crop.

Log every question and answer in `queue/<docname>.md`:

```
## Question 1 — page 3, handwritten Tel field
- Crop: queue/<docname>-q1.jpg
- Asked: "I read this as '011 234 5678' but the third digit is smudged. Confidence: medium. Could you confirm?"
- Answered: "011 234 5678 — confirmed."

## Question 2 — ...
```

### Working rules

- Do not guess silently. If uncertain and cannot resolve by cross-reference, ask.
- Do not fill in missing words or silently correct apparent typos in the source. Flag them so the user can decide whether to mark them `[sic]` or correct them.
- Do not raise minor imperfections that don't affect meaning or identifiers.
- If the user says stop, pause, or change approach, do so immediately.

---

## Step 3 — Full transcription

Once the verification queue for the current document is complete (or once the user tells you to stop verifying), produce a full text transcription.

Write it to `transcripts/<docname>.md`.

### Rules for the transcript

- **Preserve the structure of the original**: paragraph numbering, headings, sub-clauses, indentation.
- **Page and Bates markers**: include them as section markers — e.g. `[Page 2 — Bates 02-34]`. If there are no Bates numbers, use page markers only — e.g. `[Page 2]`.
- **Document boundaries within a bundle**: insert a clear separator and label — e.g. `--- DOCUMENT 2: Service Level Agreement ---`. In folder mode each source file gets its own transcript file, so this only applies where a single source file contains multiple documents stitched together.
- **Handwritten content**: render in italics and prefix with `[handwritten]`. Example: `[handwritten] *14 March 2024*`.
- **Uncertainties the user confirmed**: transcribe the confirmed text without annotation.
- **Uncertainties resolved by cross-reference**: transcribe the cross-referenced text and add a brief footnote at the end of the transcript noting the cross-reference.
- **Unresolved uncertainties**: insert `[unclear: best guess "X"]` inline.
- **Apparent typos in the source**: transcribe verbatim and mark `[sic]`.
- **Fully illegible passages**: insert `[unreadable]`.

If the transcript is very long, the file is already on disk — use `present_files` (if available) to surface it as a downloadable file rather than dumping it inline. Otherwise tell the user where the file is saved.

---

## Step 4 — Final legibility note

After all documents are transcribed, write `final-note.md` containing:

- **Per document** — which uncertainties were resolved by user confirmation and which by cross-reference; any uncertainties that remained unresolved; an overall reliability rating (high / medium / low) with one sentence of reasoning.
- **Across the bundle** (folder mode) — any structural issues worth carrying forward (Bates gaps, missing pages, document boundaries, suspected truncation).
- **Outstanding work** — anything the user asked to defer, anything that remained illegible, anything that warrants re-scanning.

Keep this short and structured. No padding.

---

## Cross-document resolution — concrete examples (folder mode)

The point of `index.md` is that uncertainties in one document can be silently resolved by a cleaner copy of the same content in another. Examples:

- A handwritten case number on a stamped cover page is unclear, but the same case number appears typed in the founding affidavit's heading. **Resolve silently** — log the cross-reference, do not ask.
- A scanned letter has a faint signature, but the same person's typed name appears in the signature block of three other letters in the bundle. **Resolve silently** if the typed name is unambiguous.
- A handwritten amount in a payment receipt is unclear, but the same amount is itemised in a typed schedule elsewhere. **Resolve silently** if the schedule unambiguously matches.

But — **do not over-resolve**. If the cross-reference is itself uncertain, or if the two copies disagree, ask the user. A disagreement between two sources is itself a substantive finding and must be surfaced.

---

## Tone

Precise, methodical, conservative. Treat the work as preparation for legal use. Accuracy matters more than speed. Do not pad the output with explanation the user didn't ask for. Skip preamble. Do not produce a long comprehensive overview before starting work.

---

## Constraints (apply throughout all steps)

- **No silent guessing.** If uncertain and cannot resolve by cross-reference, ask.
- **No silent corrections of typos.** Flag with `[sic]` and let the user decide.
- **No fabricated text.** If a passage is unreadable, mark `[unreadable]` — do not invent plausible text.
- **No invisible cropping.** Either present the crop inline via `present_files`, or tell the user the crop cannot be presented in this environment and let them decide whether to proceed.
- **One question at a time.** Do not batch.
- **Where uncertain, say so.** Conservative phrasing beats confident phrasing that turns out to be wrong.
- **Per-document reliability rating.** Every transcript ends with an honest rating — high / medium / low — not a default "high".

---

## When subagents are available

In Cowork or Claude Code, where subagents exist, use them to parallelise the text-extraction step (Step 0.5) — one subagent per file or per logical group. Each subagent's job is to extract text and return a short structured summary that the main agent folds into `index.md`. The triage and verification queue (Steps 1–3) should remain sequential and main-agent-driven, because they involve real-time interaction with the user.
