# X2 — NFL Research & Lines Dashboard

Source-linked NFL research covering the Week 10 injury snapshot, offense/defense availability exposure, independent-line hypotheses, parlays and player props, validation gates, correlation methods, a leaderboard empty state, questions, suggestions, and flagged items.

**Published GitHub Pages site:** https://karagemop466-tech.github.io/X2/

## Project layout and build systems

- `data/*.csv` — inputs for the Python dashboard and source/review registers.
- `data/verification/official_batch1.txt`, `official_batch2.txt` — a complete independent transcription of the
  official Week 10 injury page (every row, every field). Input to the verification ledger.
- `scripts/build.py` — standard-library builder for the current GitHub Pages content in `docs/` and `docs/data/`.
- `scripts/verify_snapshot.py` — reproducible line-by-line verification. Compares the transcription above with the
  committed snapshot and writes `data/verification_week10_2026.csv`.
- `docs/` — current static site. GitHub Pages is configured from the repository root; root `index.html` forwards to `docs/index.html`.
- `src/` — Node static-site generator and verifier. `npm run build` writes a separate `site/` output; it is not the current Pages source.
- `data/*.json` and `docs/*.md` — structured data and documentation used by the Node dashboard work.
- `COORDINATION.md` — shared task board, source register pointers, verification notes, irregularities, and merge log.

The source register includes official NFL, Japanese government, and NIST references. First-party GitHub repository/Pages links support only project implementation or deployment claims; they are not evidence for NFL statistics or legal facts.

## Build and verification

```bash
python3 scripts/verify_snapshot.py   # reproducible line-by-line re-check of the snapshot
python3 scripts/build.py             # validate, write docs/, check every link and every row source
npm run build
npm run verify
```

The Python build rejects missing or non-allow-listed source URLs, broken internal links, and any generated table row without an approved HTTPS source link. The Node verifier checks its own JSON-backed site data and internal links.

Unconfirmed prices, forecast values, player-depth ranks, replacement impacts, performance metrics, correlation coefficients, sample sizes, and confidence intervals remain blank or marked unverified. No strategy result is represented as tested. Football variance cannot be removed or used to guarantee a result.

## Data snapshot and rights gate

- Snapshot source: [NFL Week 10 injury report](https://www.nfl.com/injuries/), read 14 November 2026 (UTC); the
  repository contains 345 manually transcribed rows across 28 teams and 14 listed games.
- **Verification result:** 345 of 345 rows match a fresh transcription on position, injury, practice status and game
  status (1380 field comparisons, 0 mismatches), plus 14 games, 4 bye teams, 10 news links and all 345 player links.
  Reproduce with `python3 scripts/verify_snapshot.py`; see `docs/verification.html`. The one recorded conflict is a
  source disagreement (Ben Brown is listed at C on the injury report and G on his official player page, Flag F19).
- **Independence limitation:** the verification transcription was produced in the same session as the snapshot, so a
  shared misreading would not be detected (Flag F22). An independent second transcriber is recommended (suggestion
  SR-13).
- The [official NFL Week 10 schedule](https://www.nfl.com/schedules/2026/by-week/week-10) confirms CHI, DEN, PHI and TB were on bye; this is not inferred from injury-report absence.
- **Starter identity is officially verifiable after the game.** The NFL publishes no pregame depth chart and the
  official roster page has no depth column, so a "1st/2nd/3rd/4th string" rank cannot be sourced. The official NFL
  gamebook, however, publishes the starting lineup by slot, the substitutions, the Did Not Play list and the Not
  Active list. Nineteen such rows from the Week 10 Commanders at Giants gamebook are recorded in
  `data/starters_gamebook_2026_reg_10.csv` and on `docs/starters.html`. This corrects Flag F06 and is logged as F20.
  The gamebook carries its own use restriction (Flag F21).
- No licensed odds archive, historical forecast/outcome ledger, pregame depth chart, player-level participation feed,
  computed parlay correlation, or tested strategy is available in the Python dashboard. A separate Node research data file cites third-party Ourlads depth charts; those entries are flagged as non-official and must not be presented as official NFL facts (F18).
- [NFL.com terms](https://support.nfl.com/hc/en-us/articles/35869743904916-NFL-com-Terms-and-Conditions) prohibit systematic retrieval to compile a collection/database absent express prior written consent. No written permission is recorded here for the published injury snapshot; see **F16** on Flagged for Review. Do not expand or automate that data use without written authorization or qualified review.

## Important

This is a research-only project, not betting advice. Official Japan-specific guidance says online sports betting accessed from Japan is prohibited. That guidance does not determine the legality of a particular skill contest/reward or the rules in any other jurisdiction; see **F09** and keep wagering, referrals, and rewards disabled pending qualified review.

## Research registers added in this session

| Register | File | Rows | What it holds |
|---|---|---|---|
| Verification ledger | `data/verification_week10_2026.csv` | 90 | Every check, its committed value, the official value, the result and a source link |
| Starter identity | `data/starters_gamebook_2026_reg_10.csv` | 19 | Official gamebook lineup status for the Week 10 Thursday game |
| Depth deficiency | `data/depth_deficiency.csv` | 97 | Availability exposure per team and unit, with string rank and impact deliberately blank |
| Line signals | `data/line_signals.csv` | 20 | Signal definitions for single bets, totals, props and combos, each with its leakage risk |
| Skill engine | `data/skill_engine_gates.csv` | 18 | Gates EG0–EG17 with checkable pass rules and no invented thresholds |
| Anti-luck tests | `data/luck_tests.csv` | 10 | Bootstrap intervals, multiplicity control, held-out blocks, clustered uncertainty |
| Correlation plan | `data/correlation_framework.csv` | 10 | Dependent leg pairs with the estimator and sample each one needs; every value blank |
| Leaderboard rules | `data/leaderboard_rules.csv` | 12 | Pre-declared ranking rules; no entry is eligible and no reward is enabled |
| Decision gates | `data/decision_questions.csv` | 20 | Questions to answer before any route is chosen, with the choice the user faces |
| Suggestions register | `data/suggestions_register.csv` | 18 | Recommendations with options, effort, risk and the gate each depends on |
| Repo review | `data/repo_review.csv` | 27 | Line-by-line findings with a source per row |

No line, price, probability, correlation coefficient, performance score or reward value is published anywhere in this
repository, because none could be confirmed from an official source. Where a value is missing it is blank and flagged,
never inferred.
