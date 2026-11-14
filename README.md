# X2 — NFL Research & Lines Dashboard

Source-linked NFL research covering the Week 10 injury snapshot, offense/defense availability exposure, independent-line hypotheses, parlays and player props, validation gates, correlation methods, a leaderboard empty state, questions, suggestions, and flagged items.

**Published GitHub Pages site:** https://karagemop466-tech.github.io/X2/

## Project layout and build systems

- `data/*.csv` — inputs for the Python dashboard and source/review registers.
- `scripts/build.py` — standard-library builder for the current GitHub Pages content in `docs/` and `docs/data/`.
- `docs/` — current static site. GitHub Pages is configured from the repository root; root `index.html` forwards to `docs/index.html`.
- `src/` — Node static-site generator and verifier. `npm run build` writes a separate `site/` output; it is not the current Pages source.
- `data/*.json` and `docs/*.md` — structured data and documentation used by the Node dashboard work.
- `COORDINATION.md` — shared task board, source register pointers, verification notes, irregularities, and merge log.

The source register includes official NFL, Japanese government, and NIST references. First-party GitHub repository/Pages links support only project implementation or deployment claims; they are not evidence for NFL statistics or legal facts.

## Build and verification

```bash
python3 scripts/build.py
npm run build
npm run verify
```

The Python build rejects missing or non-allow-listed source URLs, broken internal links, and any generated table row without an approved HTTPS source link. The Node verifier checks its own JSON-backed site data and internal links.

Unconfirmed prices, forecast values, player-depth ranks, replacement impacts, performance metrics, correlation coefficients, sample sizes, and confidence intervals remain blank or marked unverified. No strategy result is represented as tested. Football variance cannot be removed or used to guarantee a result.

## Data snapshot and rights gate

- Snapshot source: [NFL Week 10 injury report](https://www.nfl.com/injuries/), read 14 November 2026 (UTC); the repository contains 345 manually transcribed rows across 28 teams and 14 listed games. Manual spot-check remains flagged.
- The [official NFL Week 10 schedule](https://www.nfl.com/schedules/2026/by-week/week-10) confirms CHI, DEN, PHI and TB were on bye; this is not inferred from injury-report absence.
- No licensed odds archive, historical forecast/outcome ledger, confirmed depth chart, player-level participation feed, computed parlay correlation, or tested strategy is available in the Python dashboard.
- [NFL.com terms](https://support.nfl.com/hc/en-us/articles/35869743904916-NFL-com-Terms-and-Conditions) prohibit systematic retrieval to compile a collection/database absent express prior written consent. No written permission is recorded here for the published injury snapshot; see **F16** on Flagged for Review. Do not expand or automate that data use without written authorization or qualified review.

## Important

This is a research-only project, not betting advice. Official Japan-specific guidance says online sports betting accessed from Japan is prohibited. That guidance does not determine the legality of a particular skill contest/reward or the rules in any other jurisdiction; see **F09** and keep wagering, referrals, and rewards disabled pending qualified review.
