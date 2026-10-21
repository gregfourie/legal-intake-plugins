---
name: intake-setup
description: One-time setup for the legal-matter-intake plugin. Asks where the user keeps matters, their jurisdiction, which free case-law sources to use, their role and contact block, citation style and spelling, then writes _intake-config.md and _intake-profile.json into the matters folder for the other intake skills to read. Use on "set up intake", "configure the intake plugin", "change my case-law source", "update my intake settings", or whenever another intake skill finds no _intake-config.md.
---

# Intake setup

Other skills in this plugin look for `_intake-config.md` (and `_intake-profile.json`) in the matter folder or the nearest parent. This skill writes both, once, into the user's matters folder.

## Rules

- Ask, don't guess. Never invent an email address, court name or URL pattern.
- Ask in one or two batches of multiple-choice questions where the answer set is guessable; free text otherwise.
- If a config already exists, read it, show the current values, and change only what the user asks.
- Never delete or overwrite other files in the matters folder.

## Step 1 — Ask

Batch 1:
1. **Matters folder** — the folder that holds one sub-folder per matter. If the session cannot see it yet, ask the user to connect it.
2. **Jurisdiction** — offer the profiles in `references/profiles/` (currently: South Africa) plus "Other". For "Other", ask for the country / court system and build a profile from `references/profiles/template.json` with the user (Step 2).
3. **Role** — e.g. advocate / barrister, attorney / solicitor, in-house counsel, paralegal, other. Also the other side of the professional split, if any (e.g. "instructing attorney", "instructing solicitor", none).
4. **Case-law sources** — free sources in order of preference. Offer the ones for their jurisdiction from `caselaw-fetch/references/sources.md` (sibling skill); allow "none — I will supply judgments myself".

Batch 2:
5. **Contact block** for `_matter.md` — name, email, chambers / firm, city. Free text.
6. **Word author names** — how the user's name appears as author in Word files (used to flag other people's drafts for redline).
7. **Citation style** — e.g. jurisdiction default, OSCOLA, Bluebook, AGLC, McGill, other.
8. **Spelling** — British or US English.
9. **Folder names** — keep the defaults (`_inbox/`, `research/`, `pleadings/`, `correspondence/`, `drafts/`, `working docs/`, `record/`) or rename.

## Step 2 — Build the profile

Start from the chosen file in `references/profiles/`. Add the user's Word author names under `own_authors`. For a new jurisdiction, fill `template.json` with the user: court and tribunal names as they appear on document headings, case-number patterns (regular expressions; test each on a real example the user gives), and markers that identify a judgment (e.g. a source name printed on downloads, a neutral-citation pattern). Leave a field empty rather than guess.

Test each regex before saving:

```bash
python3 -c "import re,sys; print(bool(re.search(sys.argv[1], sys.argv[2], re.I)))" '<regex>' '<example>'
```

## Step 3 — Write the files

Write into the matters folder:

- `_intake-profile.json` — the profile from Step 2 (valid JSON; check with `python3 -m json.tool`).
- `_intake-config.md` — from `references/config-template.md`, filled with the answers. Copy in the matching jurisdiction notes from `references/profiles/<code>.md` if one exists.

Show the user the config before writing it. Write only confirmed content; unknowns are `[TO CONFIRM]`.

## Step 4 — Report

Say where the two files are and that the other skills now read them. Offer, as multiple choice: (a) set up a first matter (new-matter); (b) process an inbox (hopper-intake); (c) done.
