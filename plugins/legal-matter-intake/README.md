# legal-matter-intake

Matter intake skills for Claude, for litigators and arbitration practitioners in any jurisdiction.

## Skills

| Skill | What it does |
|---|---|
| intake-setup | Run once. Asks where your matters live, your jurisdiction, role, contact block, citation style and free case-law sources. Writes `_intake-config.md` and `_intake-profile.json` into your matters folder. |
| hopper-intake | Scans a matter's `_inbox/`, proposes a route per file, waits for your approval, runs the routes, writes an intake report. |
| new-matter | Creates a matter folder and its `_matter.md` context file, or adds `_matter.md` to an existing folder. |
| pdf-intake | Front door for PDFs: assess, extract to Markdown (OCR for scans), check the pages visually before the text is trusted. |
| abc-pdf | Extraction engine behind pdf-intake (pdfplumber, Docling, EasyOCR, Tesseract, consensus merge). |
| legibility-review | Careful transcription of scans, handwriting and stamps, with uncertainties resolved before text is committed. |
| matter-mail | Turns `.eml` files dragged out of your mail app into dated markdown records, flat attachments and an index. |
| email-chain-extraction | Rebuilds email chains from PDFs or `.msg` files into clean chronological order. |
| caselaw-fetch | Fetches judgments from the free sources you chose, checks identity against the citation, logs provenance. |
| matter-index | Builds `_index/` (one entry per document, full text, list of illegible files) so later sessions start fast. |

## Install

```
/plugin marketplace add gregfourie/legal-intake-plugins
/plugin install legal-matter-intake@legal-intake-plugins
```

In the Claude app: download `legal-matter-intake.plugin` from the latest release at https://github.com/gregfourie/legal-intake-plugins/releases, then **Customize > Plugins > Add > Upload plugin**.

## Start

1. Connect your matters folder to Claude.
2. Say **"set up intake"**.
3. Then **"new matter"**, or drop files into `<matter>/_inbox/` and say **"process the inbox"**.
4. Approve the routing table. Nothing runs before you approve.

## Jurisdictions

A jurisdiction profile tells the scripts your court names, case-number patterns and how to recognise a judgment. Included: **South Africa** (`za`). For anywhere else, setup builds a profile with you from a template; until then the generic defaults apply.

Free case-law sources listed in setup: SAFLII, BAILII, AustLII, NZLII, CanLII, CourtListener, EUR-Lex, HUDOC. Only SAFLII's URL pattern is documented; for the others the skill searches the site and verifies each judgment.

## Ground rules built in

- Never deletes or overwrites. Duplicates and junk go to `_quarantine/` for your sign-off.
- No guessed party names, case numbers, dates or citations: unknowns are marked `[TO CONFIRM]`.
- A judgment is filed only after its first page is checked against the citation.
- Never cite from the index or an extraction alone; check the source.

These are aids, not a substitute for professional judgment. Check every output before you rely on it.

## Optional companion skills

hopper-intake routes to these if you have them installed; otherwise it lists the file as flagged: handwriting-narration, draft-version-control, pdf-bookmarks.

## Requirements

Python 3. abc-pdf installs its engines into a local virtual environment on first run (a few minutes). matter-index installs pdfplumber, python-docx, openpyxl and extract-msg on first run. `pdftotext` (poppler) is used by the inbox scan if present.

## Licence

MIT. See LICENSE.
