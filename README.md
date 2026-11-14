# X2 — NFL Research & Lines Dashboard

Source-linked NFL research covering the Week 10 injury snapshot, offense/defense availability exposure,
**an independent line model that originates its own spreads and totals**, a walk-forward backtest, validation
gates with graded results, computed correlation values, a same-game parlay study, a strategy leaderboard,
independent-line hypotheses, parlays and player props, questions, an ordered decision path, a suggestion review
matrix, a verification record, and flagged items. The market layer adds a **price-snapshot store** (opening and
closing fields for every originated market, side → total → moneyline), **fair line / market line / difference as
separate columns**, a strict **signal-vs-staking split** in the leaderboard, a proposed **demotion gate** that
returns a live strategy to paper, and **replacement-depth tracking** (the 2nd/3rd/4th string of the replacement,
where a source verifies it).

## Read in this order

1. **Decision path** (`docs/decision-path.html`) — the ten ordered gates that block progress, each with the question, the answer required, the owner and the official source.
2. **Executive summary** (`docs/executive-summary.html`) — key findings and what is deliberately blank.
3. **Model & Week 11 lines** (`docs/model-lines.html`) — the originated spreads, totals and moneylines, originated side first then total then moneyline, with the fair line, market line and difference as separate columns, the team ratings, and the method.
4. **Price snapshots** (`docs/price-snapshots.html`) — the price-snapshot store recording opening and closing numbers for every originated market; values blank and flagged because no licensed odds feed exists.
5. **Market tables** (`docs/markets.html`) — the market layer: Week 11 price store (opening/closing per market), fair vs market lines with the difference column, the signal-only ranking, and the proposed demotion gate.
6. **Backtest** (`docs/backtest.html`) — every walk-forward out-of-sample prediction against what actually happened.
7. **Leaderboard** (`docs/leaderboard.html`) — strategies ranked on signal (forecast skill) only, with gates, uncertainty and required sample sizes; staking is displayed separately and never affects rank.
8. **Validation gates** (`docs/validation-gates.html`) — the nine gates, including the demotion gate (G9) that sends a live strategy back to paper.
9. **Verification** (`docs/verification.html`) — what was checked line by line, against which official page, with the result.
10. **Suggestions** (`docs/suggestions.html`) — proposals plus a review matrix naming a recommended path and the gate that blocks each one.
11. **Flagged for review** (`docs/flagged.html`) — irregularities and unverified items, each with a source link.

**Published GitHub Pages site:** https://karagemop466-tech.github.io/X2/

## The model, briefly

`scripts/model.py` fits one ridge-regularised least-squares system on points scored:

```
points(team t vs opponent o, at home) = league mean + attack(t) - defence(o) + home field
```

which yields both a spread, `(attack + defence) difference plus home field`, and a total. Every prediction is
walk-forward: ratings for a week are fitted only on games played strictly before that week. Out-of-sample record
over 89 games (weeks 4-10 of 2026), graded against a naive published reference line (season point differential
plus a fixed 2.5-point home field):

| Measure | Model | Naive reference line |
|---|---|---|
| Mean absolute error, margin | 9.16 points | 10.89 points |
| Improvement | +1.74 points (95% bootstrap CI 0.76 to 2.74) | — |
| Calibration slope (actual on predicted) | 0.885 (SE 0.28) | — |

**There is no market comparison anywhere in this project.** No licensed odds feed is connected, so no closing
line, market price, closing-line value or return on investment can be computed. Leaderboard bets are graded
against the naive reference line and must never be read as market results (flag F32).

**What the newest layer adds.** Markets are originated in a fixed order — side first, then total, then
moneyline — and every market publishes the model's *fair line*, the *market line* and the *difference* as
separate columns (market columns blank, F07). A **price-snapshot store** records the opening and closing number
for every originated market (`data/price_snapshots.csv`, `docs/price-snapshots.html`); with no licensed odds feed
every opening/closing value is blank and flagged rather than inferred (F07, F31, F43). The leaderboard
**separates signal from staking** so a lucky staking run cannot mask a weak signal (F44), and a **demotion gate
(G9)** sends a live strategy back to paper when its edge degrades. No strategy is live today: the qualification
is disputed by the independent cross-check (F42), the gate cut-offs await owner approval (F17), and wagering and
rewards stay disabled (F09, F16, F19).

## Project layout and build systems

- `data/*.csv` — inputs for the Python dashboard and source/review registers.
- `data/games_2026_results.csv`, `data/standings_2026_snapshot.csv`, `data/schedule_week11_2026.csv` — the verified results feed, the standings used to check it, and the Week 11 slate.
- `data/model_*.csv`, `data/strategy_leaderboard.csv`, `data/gate_results.csv`, `data/correlations_computed.csv`, `data/parlay_analysis.csv`, `data/price_snapshots_extended.csv`, `data/model_summary.json` — model outputs, all regenerated by `scripts/model.py`.
- `data/price_snapshots.csv`, `data/line_comparison_week11.csv`, `data/strategy_signal_staking.csv`, `data/demotion_gate.csv` — the market layer (price store, fair/market/difference, signal vs staking, demotion rules), regenerated by `scripts/markets.py`.
- `data/replacement_depth.csv` — depth-of-replacement tracking (RD01–RD07), curated from verified official statements and club depth charts; blank where unverified. `data/replacement_depth_week10_2026.csv` (session 8a0bf37e) is the companion availability register.
- `scripts/model.py` — the line model, backtest, gates, correlations, parlay study and leaderboard (standard library only, fixed random seed).
- `scripts/markets.py` — derives the market-layer tables from the model outputs; never writes a price value.
- `scripts/verify_results.py` — reconciles the transcribed games against the official standings, team by team.
- `scripts/build.py` — standard-library builder for the current GitHub Pages content in `docs/` and `docs/data/`.
- `docs/` — current static site. GitHub Pages is configured from the repository root; root `index.html` forwards to `docs/index.html`.
- `src/` — Node static-site generator and verifier. `npm run build` writes a separate `site/` output; it is not the current Pages source.
- `data/*.json` and `docs/*.md` — structured data and documentation used by the Node dashboard work.
- `COORDINATION.md` — shared task board, source register pointers, verification notes, irregularities, and merge log.

The source register includes official NFL, Japanese government, and NIST references. First-party GitHub repository/Pages links support only project implementation or deployment claims; they are not evidence for NFL statistics or legal facts.

## Build and verification

```bash
python3 scripts/verify_results.py   # reconcile the 137 games against the official standings
python3 scripts/model.py            # refit ratings, Week 11 lines, backtest, gates, leaderboard
python3 scripts/markets.py          # derive the price store, fair/market/difference, signal/staking, demotion tables
python3 scripts/build.py            # rebuild docs/ (23 pages) and check every row has a source
npm run build && npm run verify     # the separate Node dashboard (12 pages)
```

The Python build rejects missing or non-allow-listed source URLs, broken internal links, and any generated table row without an approved HTTPS source link. The Node verifier checks its own JSON-backed site data and internal links.

Now computed from official results and published with intervals: team ratings, originated spreads and totals,
out-of-sample forecast accuracy, correlations with confidence intervals and p-values, and gate results for every
strategy. Still blank by design because no official evidence exists in this repository: every market price,
closing line, player-prop outcome, player-depth string order, replacement impact and legal conclusion.

Football variance cannot be removed. Out-of-sample testing, permutation tests, bootstrap intervals and
multiple-comparison control stop variance from being mistaken for skill; they do not eliminate it and they
guarantee no result. Every leaderboard row publishes the sample size it would need for a decisive test.

## Data snapshot and rights gate

- Results: the verified results feed — all 137 games of 2026 (weeks 1–9 complete, plus the Week 10 Thursday
  game) transcribed from the official
  [NFL by-week schedule pages](https://www.nfl.com/schedules/2026/by-week/week-10) and
  [standings](https://www.nfl.com/standings/), read 14 November 2026 (UTC). Recomputing every team's record and
  points from those games reproduces the official standings exactly for all 32 teams; the check is
  `scripts/verify_results.py`.
- The Week 11 lines were fitted before Week 10's Sunday games were played; re-run `scripts/model.py` afterwards (F36).
- Snapshot source: [NFL Week 10 injury report](https://www.nfl.com/injuries/), read 14 November 2026 (UTC); the repository contains 345 rows across 28 teams and 14 listed games. Every row and every game header was independently re-verified against the live page on 2026-11-14 with no discrepancies found (Flag F20). A separate session (30beeb55, T15) reached the same result independently; the manual-transcription limitation is retained (F10).
- The [official NFL Week 10 schedule](https://www.nfl.com/schedules/2026/by-week/week-10) confirms CHI, DEN, PHI and TB were on bye; this is not inferred from injury-report absence.
- No licensed odds archive, historical forecast/outcome ledger, league-published depth chart, player-level participation feed, computed parlay correlation, or tested strategy is available in the Python dashboard. The separate Node research data file was resolved in two steps: T13 (session 30beeb55) blanked all third-party Ourlads ordering values, then the integration supplement (session 52ca9f77, 2026-11-14) located the club-published depth charts on the official club websites ([detroitlions.com](https://www.detroitlions.com/team/depth-chart), [patriots.com](https://www.patriots.com/team/depth-chart)) and restored club-chart-confirmed values with per-row citations. One contradicted third-party value was corrected (Node flag F-08); both club charts self-label "unofficial" (Node flag F-05, Python flag F18).
- No league-level official NFL depth chart exists: the conventional team depth-chart URLs return HTTP 404, and roster pages expose position and status only (F06). The official club depth-chart pages are the best available official-domain depth evidence and carry the self-labeled "unofficial" caveat (F-05).
- The Thursday night result is verified on the official schedule (Commanders 24, Giants 21, final) and is published in the games table (F22, resolved by session 324b0cd2).
- [NFL.com terms](https://support.nfl.com/hc/en-us/articles/35869743904916-NFL-com-Terms-and-Conditions) prohibit systematic retrieval to compile a collection/database absent express prior written consent. No written permission is recorded here for the published injury snapshot; see **F16** on Flagged for Review. Do not expand or automate that data use without written authorization or qualified review.

## Important

This is a research-only project, not betting advice, and no reward has monetary value or is paid. Official
Japan-specific guidance says online sports betting accessed from Japan is prohibited. That guidance does not
determine the legality of a particular skill contest/reward or the rules in any other jurisdiction; see **F09**
and keep wagering, referrals, and rewards disabled pending qualified review. The project owner is located in the
Netherlands; Dutch law (Wet op de kansspelen, Kansspelautoriteit) is flagged as **F19** and has not been reviewed.
See `research/nl-legal-review.md`.

The leaderboard's three reward tiers are a proposal for review, not an implemented mechanic. Strategies compete
inside this repository; nobody is entered, nothing is staked and nothing is paid out. Read the
[leaderboard](docs/leaderboard.html) on the skill column, and read the flags
[F32](docs/flagged.html) (beating the naive reference line is not beating a sportsbook) and
[F33](docs/flagged.html) (89 games is not yet a decisive sample) before relying on any ranking.
