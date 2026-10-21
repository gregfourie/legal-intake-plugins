# Routing table

Scan signals come from `scripts/scan_inbox.py`. Confirm each by looking at
the file.

## A. RUN (after approval)

| Skill | Route when | Scan signal |
|---|---|---|
| new-matter | No `_matter.md` in the matter folder | checked in step 1 |
| pdf-intake | Every PDF | `ext == .pdf` |
| legibility-review | Scanned bundle with handwriting, stamps, faint print | `text_layer: none/partial` and several pages |
| handwriting-narration *(outside this plugin)* | Single handwritten form or note | `text_layer: none`, 1–3 pages, handwriting seen in page image |
| matter-mail | Loose .eml files | `ext == .eml` |
| email-chain-extraction | .msg files, or a PDF that is an email chain | `ext == .msg` or `email_chain_signal` |
| caselaw-fetch | A judgment | `judgment_signal` |
| draft-version-control *(outside this plugin)* | Several versions of one draft | `version_cluster` shared by 2+ files |
| file-reading *(built-in)* | Images, zips, unknown types | `ext` not in known list |
| docx / xlsx / pptx *(built-in)* | Reading Office files to classify them | `ext` .docx/.xlsx/.csv/.pptx |
| pdf-bookmarks *(outside this plugin)* | Record or bundle PDF with no outline | `pages >= 50` and `has_outline: false` |
| matter-index | Always, last | — |

## B. FLAG only (listed in report, started later by the user)

Name the task, and the skill if one is installed for it.

| Task | Flag when |
|---|---|
| Large-record analysis | Bundle over about 100 pages needing substantive work |
| Discovery review | Discovery bundle received |
| Chronology | Enough dated material for a timeline |
| Authorities table | Opponent's heads or submissions received |
| Reported version of a judgment | Judgment not on the user's free sources, or reported version needed |
| Redline | Draft by someone else (`docx_author` not the user) |
| Citation check | Incoming draft that cites authorities |

## C. Never called by intake

abc-pdf directly (pdf-intake calls it), folder tidying, bundle building,
drafting, formatting QA, anonymising, admin skills.

## QUARANTINE

- Exact duplicate (`duplicate_of` set) — keep the first copy.
- Zero-byte files, `~$` Office lock files, `.DS_Store`, `Thumbs.db`.
