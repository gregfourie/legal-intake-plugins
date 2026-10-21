---
name: "matter-mail"
description: "Get matter emails out of Outlook or Apple Mail into ONE flat correspondence folder per matter. The user drags selected messages into the matter's correspondence/eml/ drop folder (drag-out creates .eml); this skill turns each .eml into a date-first markdown record, extracts attachments flat and updates an index. Trigger on \"process the emails\", \"get the emails into the matter\", \"file these emails\", a correspondence/eml or _inbox folder with unprocessed .eml files, or loose .eml files in a matter folder."
---

# matter-mail — email into the matter folder, flat

One email = one markdown record + its attachments, all in ONE flat `correspondence/` folder. No per-email subfolders, ever.

## Configuration

Find `_intake-config.md` in the matter folder or the nearest parent folder and use its settings. If there is none, run intake-setup first. Use its correspondence folder name and header labels.

## Target structure (per matter)

```
correspondence/
  index.md                                  # chronological one-line-per-email index
  2026-08-27 - Fw Day 3 transcript - Smith to Jones.md
  ...                                       # one .md per email, date-first
  attachments/                              # FLAT; every file prefixed with its email's date
    2026-08-27 - Day 3 transcript.doc
  eml/                                      # raw .eml originals (evidence; never delete)
    ... also the DROP FOLDER for new mail
```

## Route 1 — drag-and-drop (works everywhere, the default)

1. The user selects the messages in Apple Mail or Outlook and drags them into the matter's `correspondence/eml/` folder (both apps write .eml on drag-out). Loose .eml files found anywhere in the matter are treated the same way.
2. Claude processes every unprocessed .eml with the script below (adapt paths; run via bash; python3 stdlib only — no dependencies).
3. Per email produce `YYYY-MM-DD - <subject, cleaned> - <sender surname> to <recipient surname>.md` containing: From / To / Cc / Date / Subject header block; the plain-text body VERBATIM (fall back to HTML converted to text); an attachments list naming the extracted files. Strip nothing from the body — boilerplate stripping is email-chain-extraction's job when a clean chronology is wanted.
4. Attachments: extract beside the record into `attachments/`, name `YYYY-MM-DD - <original filename>`; on collision append ` (2)`.
5. Deduplicate on Message-ID: keep a `processed:` list of Message-IDs at the bottom of `index.md`; skip any .eml whose Message-ID is already there (log the skip).
6. Append each email to `index.md`: `- YYYY-MM-DD HH:MM — <From> → <To> — <Subject> — [record](<md file>) — attachments: n`. Keep the index sorted chronologically.
7. The .eml stays in `eml/` untouched.

Processing core (adapt, don't retype from memory):

```python
import email, email.policy, re
from pathlib import Path
from email.utils import parsedate_to_datetime

def slug(s, n=60):
    s = re.sub(r"[\\/:*?\"<>|]", "-", (s or "no subject")).strip()
    return re.sub(r"\s+", " ", s)[:n].strip(" -.")

def process(eml_path: Path, corr: Path):
    msg = email.message_from_bytes(eml_path.read_bytes(), policy=email.policy.default)
    mid = (msg["Message-ID"] or eml_path.name).strip()
    try: d = parsedate_to_datetime(msg["Date"])
    except Exception: d = None
    ds = d.strftime("%Y-%m-%d") if d else "undated"
    body = msg.get_body(preferencelist=("plain", "html"))
    text = body.get_content() if body else "[no body found]"
    if body and body.get_content_type() == "text/html":
        text = re.sub(r"<[^>]+>", "", text)
    atts = []
    (corr / "attachments").mkdir(parents=True, exist_ok=True)
    for part in msg.walk():
        if part.get_content_disposition() == "attachment" and part.get_filename():
            data = part.get_payload(decode=True) or b""
            name = f"{ds} - {slug(part.get_filename(), 80)}"
            dest = corr / "attachments" / name
            k = 2
            while dest.exists(): dest = corr / "attachments" / f"{name} ({k})"; k += 1
            dest.write_bytes(data); atts.append(dest.name)
    rec = corr / f"{ds} - {slug(msg['Subject'])}.md"
    k = 2
    while rec.exists(): rec = corr / f"{ds} - {slug(msg['Subject'])} ({k}).md"; k += 1
    rec.write_text(
        f"# {msg['Subject'] or '(no subject)'}\n\n"
        f"- From: {msg['From']}\n- To: {msg['To']}\n- Cc: {msg['Cc'] or '-'}\n"
        f"- Date: {msg['Date']}\n- Message-ID: {mid}\n- Source: eml/{eml_path.name}\n"
        f"- Attachments: {', '.join(atts) if atts else 'none'}\n\n---\n\n{text}\n")
    return mid, rec.name, atts
```

## Route 2 — automated Apple Mail search (Claude Code on a Mac only, optional)

A sandboxed shell cannot reach Apple Mail. In a Claude Code session on the Mac, osascript can search Mail directly:

```bash
osascript -e 'tell application "Mail" to get subject of (messages of inbox whose subject contains "<case number>")'
```

Use AppleScript to save matching messages as .eml/.txt into `correspondence/eml/`, then run Route 1 processing. Always search by matter identifiers from `_matter.md` (case number, party names, attorney addresses). Never delete or move messages inside Mail — export copies only.

## Rules

- Bodies verbatim; never summarise into the record file (summaries live in the index line only).
- Never delete an .eml. Duplicates are skipped, not removed.
- Chronology or boilerplate-stripped bundles for court → hand the records to email-chain-extraction; this skill only ingests and files.
- After a large ingest, offer a matter-index re-run.
