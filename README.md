# X2 — NFL Research & Lines Dashboard

Source-linked NFL research covering the Week 10 injury snapshot, offense/defense availability exposure, independent-line hypotheses, parlays and player props, validation gates, correlation methods, a leaderboard empty state, questions, an ordered decision path, a suggestion review matrix, a verification record, and flagged items.

## Read in this order

1. **Decision path** (`docs/decision-path.html`) — the ten ordered gates that block progress, each with the question, the answer required, the owner and the official source.
2. **Executive summary** (`docs/executive-summary.html`) — key findings and what is deliberately blank.
3. **Verification** (`docs/verification.html`) — what was checked line by line, against which official page, with the result.
4. **Suggestions** (`docs/suggestions.html`) — proposals plus a review matrix naming a recommended path and the gate that blocks each one.
5. **Flagged for review** (`docs/flagged.html`) — irregularities and unverified items, each with a source link.

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

- Snapshot source: [NFL Week 10 injury report](https://www.nfl.com/injuries/), read 14 November 2026 (UTC); the repository contains 345 rows across 28 teams and 14 listed games. Every row and every game header was independently re-verified against the live page on 2026-11-14 with no discrepancies found (Flag F20). A separate session (30beeb55, T15) reached the same result independently; the manual-transcription limitation is retained (F10).
- The [official NFL Week 10 schedule](https://www.nfl.com/schedules/2026/by-week/week-10) confirms CHI, DEN, PHI and TB were on bye; this is not inferred from injury-report absence.
- No licensed odds archive, historical forecast/outcome ledger, league-published depth chart, player-level participation feed, computed parlay correlation, or tested strategy is available in the Python dashboard. The separate Node research data file was resolved in two steps: T13 (session 30beeb55) blanked all third-party Ourlads ordering values, then the integration supplement (session 52ca9f77, 2026-11-14) located the club-published depth charts on the official club websites ([detroitlions.com](https://www.detroitlions.com/team/depth-chart), [patriots.com](https://www.patriots.com/team/depth-chart)) and restored club-chart-confirmed values with per-row citations. One contradicted third-party value was corrected (Node flag F-08); both club charts self-label "unofficial" (Node flag F-05, Python flag F18).
- No league-level official NFL depth chart exists: the conventional team depth-chart URLs return HTTP 404, and roster pages expose position and status only (F06). The official club depth-chart pages are the best available official-domain depth evidence and carry the self-labeled "unofficial" caveat (F-05).
- The Thursday night result is verified on the official schedule (Commanders 24, Giants 21, final) but is not published, because the games table has no result column (F22).
- [NFL.com terms](https://support.nfl.com/hc/en-us/articles/35869743904916-NFL-com-Terms-and-Conditions) prohibit systematic retrieval to compile a collection/database absent express prior written consent. No written permission is recorded here for the published injury snapshot; see **F16** on Flagged for Review. Do not expand or automate that data use without written authorization or qualified review.

## Important

This is a research-only project, not betting advice. Official Japan-specific guidance says online sports betting accessed from Japan is prohibited. That guidance does not determine the legality of a particular skill contest/reward or the rules in any other jurisdiction; see **F09** and keep wagering, referrals, and rewards disabled pending qualified review. The project owner is located in the Netherlands; Dutch law (Wet op de kansspelen, Kansspelautoriteit) is flagged as **F19** and has not been reviewed. See `research/nl-legal-review.md`.
