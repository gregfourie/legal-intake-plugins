# legal-intake-plugins

A Claude plugin marketplace with one plugin, **legal-matter-intake**: matter intake for litigators and arbitration practitioners in any jurisdiction. See [the plugin README](plugins/legal-matter-intake/README.md) for what it does.

## Install

**Claude Code**

```
/plugin marketplace add gregfourie/legal-intake-plugins
/plugin install legal-matter-intake@legal-intake-plugins
```

**Claude app (claude.ai or desktop)**

Download `legal-matter-intake.plugin` from the latest release, then go to **Customize > Plugins > Add > Upload plugin**.

After install, connect your matters folder and say **"set up intake"**.

## Contributing a jurisdiction profile

1. Copy `plugins/legal-matter-intake/skills/intake-setup/references/profiles/template.json` to `<code>.json` (e.g. `ew.json`, `au.json`).
2. Fill in court names as they appear on headings, case-number regexes and judgment markers. Test each regex on real examples.
3. Add a short `<code>.md` with jurisdiction notes (courts, professional split, citation style, email boilerplate).
4. If you have verified a case-law source's URL pattern, add it to `skills/caselaw-fetch/references/sources.md`.
5. Open a pull request.

## Disclaimer

These skills are aids. They do not give legal advice. Check every output before relying on it.

## Licence

MIT. See [LICENSE](LICENSE).
