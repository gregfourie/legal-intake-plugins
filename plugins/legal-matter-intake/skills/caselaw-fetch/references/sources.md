# Source notes

Patterns below are a starting point. Verify every fetch (SKILL.md, Step 3).
Only SAFLII's pattern has been used in practice by the author. For the other
sources, only the home page is listed: work out the pattern on first use,
check it, then add it to your `_intake-config.md`.

## SAFLII — South Africa (saflii.org)

- Neutral citation to URL: `[2007] ZACC 22` → `https://www.saflii.org/za/cases/ZACC/2007/22.html` (a `.pdf` is sometimes available at the same path).
- Report-series citations (SA, BCLR, ILJ and others) have no direct URL: search SAFLII by party names and year.
- Not on SAFLII: many unreported judgments, subscription reports (Juta, LexisNexis), older decisions.

## Other free sources (home pages only — pattern not documented here)

| Source | Coverage | Home page |
|---|---|---|
| BAILII | UK and Ireland | https://www.bailii.org |
| AustLII | Australia | https://www.austlii.edu.au |
| NZLII | New Zealand | https://www.nzlii.org |
| CanLII | Canada | https://www.canlii.org |
| CourtListener | United States | https://www.courtlistener.com |
| EUR-Lex | European Union | https://eur-lex.europa.eu |
| HUDOC | European Court of Human Rights | https://hudoc.echr.coe.int |

Some sites limit automated access or have terms of use. Respect them; if a site blocks fetching, tell the user and ask them to download the judgment themselves.

## Adding a source

Add a line under **Case-law sources** in `_intake-config.md`:

```
- <Name> — <home page> — neutral-citation URL pattern: <pattern or "search only">
```

Contributions of verified patterns are welcome (see the repository README).
