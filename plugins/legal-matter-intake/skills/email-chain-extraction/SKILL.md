---
name: email-chain-extraction
description: Extract, clean, and reorganise email chains from PDFs, MSG files, or document bundles into structured chronological format. Use this skill whenever the user wants to extract emails from a PDF, clean up an email thread, reorganise email correspondence chronologically, strip signatures and boilerplate from emails, parse MSG files, or prepare email evidence for litigation. Also triggers on requests to extract correspondence, clean up email trails, organise email chains, or prepare email bundles for court/arbitration. Handles common legal email boilerplate (data-protection notices, regulatory disclaimers, confidentiality notices), with extra patterns from the user's jurisdiction profile, and common corporate email signatures.
---

# Email Chain Extraction Skill

Extract, clean, and reorganise email chains from PDFs or MSG files into structured chronological documents suitable for litigation use.

## When to Use

This skill applies when you need to take a messy email chain (typically a PDF printout of a forwarded thread, or a set of MSG files) and produce a clean, chronologically ordered document with boilerplate stripped out.

Common scenarios:
- A discovery PDF contains a long email thread printed in reverse chronological order (newest first)
- Multiple MSG files need to be consolidated into one chronological document
- Email evidence needs to be cleaned up for inclusion in a trial bundle or working note
- An email chain needs to be analysed and the key communications extracted

## Extraction Workflow

### Step 1: Identify the Source Format

- **PDF email chain**: Emails printed/saved as PDF, typically in reverse chronological order (newest at top). Use pdfplumber or abc-pdf skill to extract text.
- **MSG files**: Outlook message files. Parse with Python `extract-msg` or `msg-extractor` library.
- **EML files**: Standard email format. Parse with Python `email` standard library.
- **DOCX containing emails**: Extract text with pandoc or python-docx.

### Step 2: Parse Individual Emails

For each email in the chain, extract:
- **Date/Time**: Full timestamp including timezone where available
- **From**: Sender name and email address
- **To**: Recipient(s) name and email address
- **CC**: Carbon copy recipients (if any)
- **Subject**: Email subject line
- **Body**: The substantive content only

**Parsing heuristics for PDF email chains:**
- Look for header patterns: `From:`, `Sent:`, `Date:`, `To:`, `Cc:`, `Subject:`
- Also match variations: `Van:`, `Aan:`, `Onderwerp:` (Afrikaans equivalents)
- A new email starts when you encounter a `From:` line followed by `Sent:`/`Date:` and `To:`
- Watch for forwarded messages indicated by `-----Original Message-----` or `---------- Forwarded message ----------`

### Step 3: Strip Boilerplate

Remove the following from each email body (preserve the substantive content only):

**Signatures to strip:**
- Name/title/phone/address blocks at the end of emails
- Company logos and image placeholders (`[image]`, `[cid:...]`)
- Social media links and icons
- "Sent from my iPhone/Android" tags

**Legal disclaimers to strip:**
- Data-protection / privacy notices (e.g. GDPR, POPIA, CCPA wording)
- Regulatory disclaimers (e.g. "this email does not constitute financial advice…")
- Confidentiality and privilege notices ("This email and any attachments are confidential and intended solely for...")
- Tax disclaimers
- Electronic communications disclaimers
- Patterns listed under "Email boilerplate" in the user's `_intake-config.md`, if present
- Any multi-paragraph boilerplate that appears identically or near-identically across multiple emails in the chain

**How to identify boilerplate:**
- Text that appears verbatim (or near-verbatim) in multiple emails
- Text that begins with standard disclaimer phrases ("This email is...", "The information contained...", "Please consider the environment...")
- Text blocks separated from the body by a line of dashes, equals signs, or similar dividers
- Text after "Regards" / "Kind regards" / "Best regards" that isn't the sender's name

**What NOT to strip:**
- Inline replies and comments (even if they're short)
- Forwarded message content (this is substantive)
- Quoted text that the sender is responding to (keep for context)
- Any text that contains substantive discussion, even if it appears at the end of the email

### Step 4: Reorder Chronologically

- Sort emails by date/time, **oldest first**
- If exact times aren't available, preserve the relative ordering indicated by reply/forward references
- Number emails sequentially: Email 1, Email 2, etc.

### Step 5: Format Output

Produce a clean document with this structure for each email:

```
EMAIL [N]
Date:    [full date and time]
From:    [sender name] <[email address]>
To:      [recipient(s)]
CC:      [if any]
Subject: [subject line]

[Body text — substantive content only]

---
```

### Step 6: Flag Non-Extractable Content

Some content in email chains can't be extracted as text:
- **Embedded images**: Tables, screenshots, charts that were pasted into the email body
- **Inline attachments**: Files referenced but not extractable from the PDF

Flag these with bracketed notes:
```
[EMBEDDED IMAGE: Appears to be a table showing shareholder commitments — not extractable as text. See original PDF page X.]
```

## Output Formats

- **DOCX**: For formal use in litigation — use the `docx` skill for proper formatting (Arial 12pt, appropriate spacing)
- **PDF**: Convert from DOCX via LibreOffice if PDF output is requested
- **Markdown**: For working notes and quick reference

## Edge Cases

### Garbled/Reversed PDFs
Some PDFs store text in reversed order (characters reversed, lines reversed). If extracted text looks like gibberish:
1. Try reversing each line's characters
2. Try reversing line order
3. Try both
4. If still garbled, fall back to OCR (abc-pdf skill with OCR engine)

### Nested Forwards
When an email contains a forwarded chain within a forwarded chain:
- Maintain the full nesting structure
- Number at the outermost level only
- Indent forwarded-within-forwarded content or clearly label the nesting level

### Non-English Headers
Email clients localise header labels. Parse them identically to their English
equivalents. Use the "Email header labels" list in the user's
`_intake-config.md` if present. Example (Afrikaans):
- `Van:` = From
- `Aan:` = To
- `Onderwerp:` = Subject
- `Gestuur:` / `Datum:` = Sent / Date

If a label is not recognised, say so rather than guessing its meaning.

### Partial Chains
If the PDF only contains part of a thread (e.g., a forward that includes only some of the original chain), note this:
```
[NOTE: This email chain appears to begin mid-thread. Earlier correspondence is not included in this document.]
```

## Verification

After extraction, verify:
- Total email count matches what's visible in the source
- Date ordering is correct
- No substantive content has been accidentally stripped
- All sender/recipient information is preserved
- Any embedded images or missing attachments are flagged
