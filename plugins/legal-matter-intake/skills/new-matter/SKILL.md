---
name: new-matter
description: "Scaffold a new litigation or arbitration matter folder with a standard structure and a _matter.md context file, or retrofit _matter.md into an existing matter folder that lacks one. Use whenever the user starts a new matter or brief ('new matter', 'set up a matter folder', 'I've been briefed in…', 'open a file for…', 'new instructions received'), points at a case folder without _matter.md, or asks to standardise a matter folder. Also offer this skill at the start of substantive work on any matter whose folder has no _matter.md."
---

# New matter scaffold

## Why this exists

`_matter.md` is the canonical per-matter context file: every session on a
matter reads it first, and it carries the canonical party citations,
abbreviations, case numbers, lawyers' details and record-reference conventions
that stop sessions re-asking or guessing. This skill makes each new matter
start that way instead of accreting structure ad hoc.

## Step 0 — Read the configuration

Find `_intake-config.md` in the matter folder or the nearest parent folder and use its settings (folder names, role, contact block, jurisdiction, sources). If there is none, run intake-setup first.

## Intake (ask, don't guess)

Ask with multiple-choice blocks where the answer set is guessable; free text otherwise. Gather:

1. Matter short name — becomes the folder name in the matters folder
   (lower case, short, e.g. "smith v jones")
2. Parties — full citation for each, the abbreviation to use in drafting,
   and which party the user acts for
3. Forum and case number(s) — offer the courts and tribunals listed in the
   config, plus arbitration and "other"; note the governing rules
4. The user's professional counterpart (from the config, e.g. instructing
   attorneys or solicitors) — firm, contact person, ref, email; the other
   side's lawyers if known
5. Key dates already known — filing deadlines, hearing dates
6. Record-reference convention, if a record already exists
   (e.g. cite as "Vol X, pp Y–Z")

Anything not known yet gets a **[TO CONFIRM]** marker in the file. Never
invent a case number, party citation or date.

## Folder structure

Create inside `<matters folder>/<matter name>/`, using the folder names in the config. Never overwrite or rename
anything that already exists — add only what is missing.

```
_matter.md
_inbox/              ← drop folder for new documents (hopper-intake)
research/            ← authorities PDFs only; cite only what is on file here
                       (provenance logged in research/_sources.md)
pleadings/
correspondence/
drafts/
  Latest Draft/
  Previous Drafts/
working docs/        ← process notes, build reports, verification memos
record/              ← create only once a record exists
```

## Writing _matter.md

Copy `references/matter-template.md` and fill it from intake. Conventions
that matter:

- Contact block: from the config. Never guess an email address.
- Posture log: most recent first, one dated entry per event, lead phrase in
  bold. This is the matter's memory between sessions — write entries so a
  fresh session can act on them without re-reading the whole folder.
- Discrepancies are recorded, not silently resolved: where two documents
  conflict (a case number, a party's citation), note both readings and which
  source controls.
- End any future session that changes the matter's posture by offering to
  update `_matter.md` (standing preference; note it in the file's header).

## Retrofit mode (existing folder, no _matter.md)

Read what is on file first — run matter-index if the folder is large or
mixed — then fill the template from the documents themselves. Mark every
field you could not verify **[TO CONFIRM — not found on file]**. Present the
draft to the user for review before saving it into the matter folder.

## After scaffolding

Offer, as multiple-choice options: (a) a matter-index run if documents
already exist; (b) a scheduled-task reminder if a deadline was captured;
(c) fetching any authorities already identified in the brief into the
research folder with caselaw-fetch.
