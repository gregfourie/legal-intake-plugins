---
name: caselaw-fetch
description: Fetch judgments from the open legal sources the user named in setup (e.g. SAFLII, BAILII, AustLII, CanLII, CourtListener) into a matter's research folder, with identity checked against the citation and a provenance log. Use whenever cited authorities need to be obtained or kept on file — "fetch these cases", "get the judgments", "download the authorities", "add [case] to the research folder", "find the missing authorities" — or when drafting needs a judgment that is not yet on file. Reports unobtainable authorities for manual sourcing rather than guessing.
allowed-tools: Bash, Read, Write, Edit, WebSearch, WebFetch
user-invocable: true
---

# Case-law fetch

## Why this skill exists

Get authorities on file with verified identity, so that nothing is cited unless a copy sits in the matter's research folder.

## Step 0 — Read the configuration

Find `_intake-config.md` in the matter folder or the nearest parent folder. Use its **Case-law sources** list (in order of preference), **Research folder** name (default `research/`) and **Citation style**. If there is no config, run the intake-setup skill first, or ask the user which free legal source to use for this matter.

Use only the sources the user listed. Never fetch from a source the user did not approve. Subscription services are out of scope: list those authorities for manual sourcing.

## Step 1 — Check what is already on file

List the research folder and its `_sources.md`. Never re-fetch an authority already on file; report it as present.

## Step 2 — Resolve each authority

For each case (name + citation as cited):

- **Neutral citation:** if the source's entry in the config gives a URL pattern for neutral citations, build the URL from it. Do not trust the built URL — verify (Step 3).
- **Report-series citation or no URL pattern:** search the source by party names and year (the source's own search page, or a web search restricted to its domain), then verify.
- If a page comes back empty (client-rendered page), try the PDF or print version, or a domain-restricted web search, before concluding the case is unavailable.

## Step 3 — Verify identity before saving (mandatory)

Open the fetched judgment and confirm the first page matches the citation: party names, court, case number and/or neutral citation, and year.

- Same-name traps are real (two judgments between the same parties in different years or courts). If year or court differs from the citation, do NOT save it as that authority — report the discrepancy.
- A judgment that cannot be verified is not delivered as verified. No exceptions.

## Step 4 — File with provenance

- Filename: `Case Name v Other Party [Year] Citation.pdf` (descriptive, filesystem-safe). Prefer the source's PDF; if only HTML exists, save the HTML page as PDF or .html and say which.
- Append one row per fetch to `<research folder>/_sources.md`:

  | Case | Citation | Source URL | Fetched | Verified |
  |------|----------|------------|---------|----------|

- Never modify the judgment file (no cover sheets, no stamps).

## Step 5 — Report

One line per authority: fetched-and-verified / already on file / UNOBTAINABLE with reason. Typical unobtainable classes: subscription-only reports, unreported judgments, very old decisions not on free sources. List these for the user to source manually. Never substitute a similar case, never fabricate, never cite an unobtained authority.

## Source notes

Known patterns for some sources are in `references/sources.md`. Treat them as a starting point and verify each fetch; sites change.
