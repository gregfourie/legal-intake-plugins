---
name: hopper-intake
description: "Process new files dropped into a matter's _inbox/ folder: scan every file, decide which skill handles each one, show a routing table for approval, then run the approved skills in one pass and write an intake report. Use whenever the user says 'process the inbox', 'intake [matter]', 'run intake', 'what's in the inbox', 'deal with the new documents', or when files are found in a matter's _inbox folder. This is the router for NEW arrivals only; it calls new-matter, pdf-intake, matter-mail, email-chain-extraction, legibility-review, caselaw-fetch and matter-index, and flags work for other skills if installed. Not for tidying an existing folder."
---

# Hopper intake — route new matter files to the right skill

The inbox is `<matter>/_inbox/`. The matter is the parent folder. If the user
has not said where their matters live, ask once.
This skill decides; the other skills do the work. It never does their work
itself.

## Rules that apply throughout

- **Approval gate.** Nothing runs until the user approves the routing table.
- **Never delete. Never overwrite.** Copy first. Move a file out of `_inbox/`
  only after its step is verified. Junk and duplicates go to `_quarantine/`
  with a deletion list for sign-off.
- **Failures do not stop the run.** A failed step is marked FAILED; its files
  stay in `_inbox/`.
- **No legal conclusions.** Classification is about document type, not merits.
  If a file's type is unclear, say so in the table — do not guess.
- **PDFs go to pdf-intake, never abc-pdf directly.** pdf-intake calls abc-pdf
  and adds the vision check.

## Step 0 — Read the configuration

Find `_intake-config.md` in the matter folder or the nearest parent folder and use its settings (folder names, role, contact block, jurisdiction, sources). If there is none, run intake-setup first. The scan script reads `_intake-profile.json` from the same place.

## Step 1 — Check the matter

Read `<matter>/_matter.md`. If it is missing, route **new-matter** first and
stop until it exists (party names and case numbers are needed for step 3).

## Step 2 — Scan (script)

```bash
python3 "$SKILL_DIR/scripts/scan_inbox.py" "<matter>/_inbox" --out "<matter>/_intake/scan.json"
```

For each file the script records: type, size, hash, duplicates, PDF pages,
text-layer density, bookmark outline, email-chain and judgment signals,
docx author, and draft-version clusters. It adds a `suggested_route`. The user's Word author names come from the profile
(`own_authors`), so drafts by others get a redline flag. `--own-author` and
`--profile` override. The
suggestion is a hint only — confirm it in step 3.

## Step 3 — Classify and route

Read `references/routing_table.md`. Group A routes marked *(outside this
plugin)* run only if that skill is installed; if it is not, list the file as
FLAG with the note "skill not installed". For each file, confirm or correct the
suggested route by looking at the file (first pages of PDFs via their text or
page image; opening lines of Office files). Use `_matter.md` to spot the
parties, the opponent's documents and the user's own drafts.

Each file gets one of three statuses:
- **RUN** — skill in group A of the routing table.
- **FLAG** — skill in group B; listed in the report, not run.
- **QUARANTINE** — duplicate or junk.

A file can have one RUN and several FLAGs (e.g. a 400-page PDF record: RUN
pdf-intake, RUN pdf-bookmarks if installed and no outline, FLAG large-record analysis).

## Step 4 — Approval gate

Show one table in chat, then ask with multiple-choice options
(Approve all / Change routes / Stop):

| # | File | Type found | Route | Status | Note |
|---|---|---|---|---|---|

Keep notes to a few words. Mark anything uncertain `[TO CONFIRM]`.

## Step 5 — Run

Run all approved RUN steps in one pass, in this order (earlier outputs feed
later ones):

1. new-matter (if needed)
2. matter-mail / email-chain-extraction
3. pdf-intake (then legibility-review, or handwriting-narration if installed, where routed)
4. caselaw-fetch (judgments: verify identity, file in the research folder, log
   in its `_sources.md`)
5. draft-version-control, if installed
6. pdf-bookmarks, if installed (writes a new copy; original kept)
7. docx / xlsx / pptx reads, file-reading for odd types
8. matter-index — always last

Heavy jobs (large-record analysis, very large legibility runs) are never run here. They are
flagged for a fresh session: they need their own context.

Verify each step's output exists and opens before moving its source out of
`_inbox/` into the matter's standard folder.

## Step 6 — Report

Write `<matter>/_intake/intake-report.md`:

```markdown
# Intake report — <matter> — <date>

| # | File | Route | Status | Output / reason |
|---|---|---|---|---|

## Flagged for later
- <skill> — <file> — <why>

## Left in _inbox
- <file> — <reason>

## Quarantined
- <file> — <reason>
```

Status is one of OK / FAILED / FLAGGED / QUARANTINED / SKIPPED (not approved).

Then offer, as multiple choice, to update `_matter.md` (new documents
received, new parties or case numbers found).
