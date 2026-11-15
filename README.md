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

0. **Review console** (`docs/review.html`) — the section where a path is actually *chosen*: eight decisions, three
   options each, a recommendation, the file each would change, and what stays blocked until it is decided. It ships
   with **zero decisions recorded**, because no human has recorded one.

0. **Review path** (`docs/review.html`) — one ordered route through the open decisions, so a reviewer can choose a direction before anything is built.
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

### Also new (session 6ee4d13e): per-team view, controls for every run

- **Per-team view** (`docs/team-view.html`, built from `data/team_view_week10_2026.csv` by `python3 scripts/team_view.py`): one row per club for Week 10, with the official injury counts, the net injury count, starters Out on a club chart and the replacements named there. Bye clubs are shown blank, never as injury-free. Starter order is available for six clubs only. The injury row count is still open (F83; see F89).
- **Leaderboard: controls for every run** (`data/leaderboard_control_runs.csv`, computed by `scripts/baselines.py` from `scripts/model.py`): M1-M4, T1, R1 and P1 against seeded random picks and the reference-line favourite, on the exact bets each run made. Every run must reproduce its published bet count and mean edge, or the build stops. The favourite control is weak on these games (F91).

### Also new (session b03f4ba1): controls, two-sided triggers, readiness table

- **Landing page: removal-of-luck panel and decision-readiness table.** The panel shows each strategy's skill, its
  interval, weeks positive and halves agreement. The luck index is a heuristic built inside the model (flag F85).
  The readiness table has one row per requirement from the brief, with its status, the gate that blocks it and
  the number that would clear it (45 rows, sourced to the official page or first-party file in each row).
- **Leaderboard: control baselines** (`data/control_baselines.csv`, reproduced by `python3 scripts/controls.py`):
  random picks (seeded), the naive reference line's favourite, and M1, graded on the same 88 decided out-of-sample games.
  No betting-market favourite is measured (flag F32).
- **Leaderboard: two-sided "what would change our mind"** for M1-M4, T1, R1 and P1 (`data/strategy_change_rules.csv`).
  No strategy is pre-registered (flag F87).
- New flags F83-F88: Week 10 injury row count not reconciled (F83), three conflicting gate numberings (F84), the
  heuristic luck index (F85), margin columns named "spread" (F86), pre-registration not demonstrable (F87), and the
  brief's 136-game count against 137 games in the repo (F88).

### Also new: market sheet, props, event risk

- **Market sheet** (`docs/market-sheet.html`) — every Week 11 market in origination order (side, total, moneyline)
  with the **fair line, the market line and the difference in three separate columns**, a fair American price, and a
  SHA-256-sealed pre-kickoff forecast log (`data/prospective_forecast_log.sha256`). The market columns are blank.
- **Player props** (`docs/props.html`) — six prop families with their official outcome source, the same-game
  correlation matrix carrying `n` on every value, and prop-combo dependence published as a blank rather than a guess.
- **Event risk** (`docs/event-risk.html`) — 65 named Week 11 risks tied to a player, an official status word and the
  specific markets each can invalidate. Of those, **58 have no official source establishing the player's role**, and
  that number is published instead of the shortfall being hidden.
- **Skill versus luck** (`docs/leaderboard.html`) — every strategy now carries luck share, skill share, half-split
  agreement and a per-week sign test. The finding is negative and published anyway: M1 is positive in 5 of 7 weeks
  (p = 0.45), so its rank describes 89 games rather than predicting the next one.

### Also new: settlement, replacement depth, correlation provenance, audit

Five pages added by session `d0d9d19f`, each covering a requirement the earlier passes left open:

- **Originated lines** (`docs/originated-lines.html`) — side → total → moneyline with our own opening and current
  number per market held in the snapshot store. `scripts/originate.py` re-fits the ratings independently and refuses
  to publish if any spread or total disagrees with `scripts/model.py` by more than 0.05 points.
- **Results feed** (`docs/results-feed.html`) — the settlement view: the official final score for all 137 games plus
  how the side, the total and the moneyline we originated actually settled.
- **Depth of replacement** (`docs/depth-replacement.html`) — 2nd/3rd/4th-string ordinals read from official club depth
  charts for DET, NE, DAL, GB, TEN and NO; 33 rows, 19 with a named replacement, 14 blank and flagged.
- **Correlation provenance** (`docs/correlation-provenance.html`) — inputs, official source and `n` for every
  published correlation, with each previously published value recomputed from the ledger.
- **Repository audit** (`docs/repo-audit.html`) — 22 checks against live official pages and recomputations, 0 failing.

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
| Calibration slope (actual on predicted) | 0.885 (SE 0.28), 95% CI 0.33 to 1.44 | — |

The calibration slope carries its **own t interval**, not a correlation interval: the slope is not
distinguishable from 1.0 (p = 0.68 against a null of 1.0), so the data show neither miscalibration nor
demonstrated calibration. An earlier build published a Pearson-r interval and p = 0.0000 here, which
applied a correlation formula to a regression coefficient (flag F72).

**Neutral sites are modelled.** Nine 2026 games are international
([NFL Football Operations](https://operations.nfl.com/programs-initiatives/international-growth/nfl-international-games)).
The model adds no home-field term to the designated home team in those games. The Week 11 Mexico City game
(MIN at SF) is corrected; the 137 historical rows carry a **blank** `neutral_site` value because every stadium
was not re-confirmed, so nothing was inferred (flag F71).

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
- `data/results_feed_2026.csv` — the canonical verified results feed (session f25d6b55): every official 2026 result with a per-row verification status; all grading consumes exactly these rows.
- `data/model_*.csv`, `data/strategy_leaderboard.csv`, `data/gate_results.csv`, `data/correlations_computed.csv`, `data/parlay_analysis.csv`, `data/price_snapshots_extended.csv`, `data/model_summary.json` — model outputs, all regenerated by `scripts/model.py`. Origination order is fixed (side, then total, then moneyline; the moneyline derives from the originated side and total only). The correlation register publishes input A, input B and the owner-rule classification per row, and C09 uses the slope's own standard error (F48, REQ-8a-1).
- `data/price_snapshots.csv`, `data/line_comparison_week11.csv`, `data/strategy_signal_staking.csv`, `data/demotion_gate.csv` — the market layer (Week 11 price store, fair/market/difference, signal vs staking, demotion rules), regenerated by `scripts/markets.py`; never writes a price value.
- `data/replacement_depth.csv` — depth-of-replacement tracking (RD01–RD07), curated from verified official statements and club depth charts; blank where unverified. `data/replacement_depth_week10_2026.csv` (session 8a0bf37e) is the companion availability register.
- `scripts/model.py` — the line model, backtest, gates, correlations, parlay study and leaderboard (standard library only, fixed random seed).
- `scripts/verify_results.py` — reconciles the transcribed games against the official standings, team by team.
- `scripts/verify_snapshot.py` — reproducible line-by-line re-check of the Week 10 snapshot (T88 takeover from session 25d6114f).
- `data/verification/official_batch1.txt`, `data/verification/official_batch2.txt` — a complete independent transcription of the official Week 10 injury page (every row, every field); input to the verification ledger.
- `data/verification_week10_2026.csv`, `data/starters_gamebook_2026_reg_10.csv`, `data/depth_deficiency.csv`, `data/line_signals.csv`, `data/skill_engine_gates.csv`, `data/luck_tests.csv`, `data/correlation_framework.csv`, `data/leaderboard_rules.csv`, `data/decision_questions.csv`, `data/suggestions_register.csv`, `data/repo_review.csv` — research registers taken over from session 25d6114f (T88); row counts and contents are listed under “Research registers” below.
- `scripts/build.py` — standard-library builder for the current GitHub Pages content in `docs/` and `docs/data/`.
- `docs/` — current static site. GitHub Pages is configured from the repository root; root `index.html` forwards to `docs/index.html`.
- `src/` — Node static-site generator and verifier. `npm run build` writes a separate `site/` output; it is not the current Pages source.
- `data/*.json` and `docs/*.md` — structured data and documentation used by the Node dashboard work.
- `COORDINATION.md` — shared task board, source register pointers, verification notes, irregularities, and merge log.

The source register includes official NFL, Japanese government, and NIST references. First-party GitHub repository/Pages links support only project implementation or deployment claims; they are not evidence for NFL statistics or legal facts.

## Build and verification

```bash
python3 scripts/verify_results.py   # reconcile the 137 games against the official standings
python3 scripts/verify_snapshot.py  # reproducible field-by-field re-check of the Week 10 snapshot
python3 scripts/verify_live.py      # compare the registers against a fresh independent transcription
python3 scripts/model.py            # refit ratings, Week 11 lines, backtest, gates, leaderboard,
                                    # results feed, price-snapshot store (fixed seed)
python3 scripts/desk.py             # results-feed, demotion-window and correlation-audit registers
python3 scripts/desk_v2.py          # market sheet, correlation matrix, props, event risk
python3 scripts/markets.py          # regenerate the market tables (price store, fair/market view,
                                    # signal-vs-staking) from the model outputs
python3 scripts/review.py           # decision console (reads data/decision_choices.json)
python3 scripts/results_feed.py     # settled results feed (137 games, all three markets)
python3 scripts/originate.py        # side -> total -> moneyline, our opening/current number per market
python3 scripts/depth_chain.py      # depth of the replacement from official club depth charts
python3 scripts/correlation_provenance.py   # recompute every correlation, publish inputs and n
python3 scripts/repo_audit.py       # line-by-line audit against live official pages
python3 scripts/team_view.py        # per-team view for Week 10 (asserts the 66/10/84 injury totals)
python3 scripts/build.py            # rebuild docs/ and check every row has a source
npm run build && npm run verify     # the separate Node dashboard (12 pages)
```

The Python build rejects missing or non-allow-listed source URLs, broken internal links, any generated table row
without an approved HTTPS source link, and a decision console that disagrees with `data/decision_choices.json`. The Node verifier checks its own JSON-backed site data and internal links.

Now computed from official results and published with intervals: team ratings, originated spreads and totals,
out-of-sample forecast accuracy, correlations with confidence intervals and p-values, and gate results for every
strategy. Still blank by design because no official evidence exists in this repository: every market price,
closing line, player-prop outcome, player-depth string order, replacement impact and legal conclusion.

Football variance cannot be removed. Out-of-sample testing, permutation tests, bootstrap intervals and
multiple-comparison control stop variance from being mistaken for skill; they do not eliminate it and they
guarantee no result. Every leaderboard row publishes the sample size it would need for a decisive test.

## Two independent implementations, compared

Two sessions built overlapping artefacts in parallel. Both are kept, and the comparisons are recorded rather than
reconciled by picking a winner.

| Artefact | This session (`d0d9d19f`) | Parallel session | Comparison |
|---|---|---|---|
| Results feed | `data/results_feed.csv` — 137 games plus the settlement of all three originated markets | `data/results_feed_2026.csv` — 137 games with a per-row verification chain | **137 of 137 scores agree, 0 disagreements.** Different columns; neither carries a price. |
| Replacement depth | `data/depth_replacement.csv` — DET, NE, DAL, GB, TEN, NO; every Out/Doubtful player on those charts | `data/replacement_depth_week10_2026.csv` — SEA, MIA, BAL, CLE, AZ, NYG; quarterback-centred | Different clubs, so **twelve clubs covered in total**. One disagreement: Seattle's chart was retrievable at `www.seahawks.com` but not at the address this session used. |
| Correlation register | `data/correlation_provenance.csv` — inputs, official source, `n`, recomputation | `data/correlation_audit.csv` — same rows plus the owner-rule classification (F49) | The owner rule treats a correlation whose predictor is a model output as a diagnostic, not an officially sourced correlation. The provenance page states which inputs are official, so the rule can be applied row by row. |
| Neutral-site handling | `scripts/originate.py` drops the home-field term where the schedule says `neutral_site = Y` | `scripts/model.py` does the same, and F71 records the defect | Both agree. The open half is unchanged: all 137 completed rows still carry a blank `neutral_site` value. |

## Data snapshot and rights gate

- Results: the verified results feed — all 137 games of 2026 (weeks 1–9 complete, plus the Week 10 Thursday
  game) transcribed from the official
  [NFL by-week schedule pages](https://www.nfl.com/schedules/2026/by-week/week-10) and
  [standings](https://www.nfl.com/standings/), read 14 November 2026 (UTC). Recomputing every team's record and
  points from those games reproduces the official standings exactly for all 32 teams; the check is
  `scripts/verify_results.py`.
- The Week 11 lines were fitted before Week 10's Sunday games were played; re-run `scripts/model.py` afterwards (F36).
- Snapshot source: [NFL Week 10 injury report](https://www.nfl.com/injuries/), read 14 November 2026 (UTC); the repository contains 345 rows across 28 teams and 14 listed games.
- **Snapshot verification ledger (T88 takeover):** `python3 scripts/verify_snapshot.py` re-compares the committed snapshot with a stored field-by-field transcription of the official page: 345 of 345 rows match on position, injury, practice status and game status (1,380 comparisons, 0 mismatches), plus all 14 games, the 4 bye teams and all 345 player links (90 checks: 87 PASS, 1 CONFIRMED, 1 NEW EVIDENCE, 1 REVIEW, 0 FAIL). Residual limitation: that transcription was produced in the same session as the snapshot, so a shared misreading would not be detected — logged as **F80**; two further independent passes against the live page (sessions 30beeb55 and 7c9eb69a) reached the same result. Reproduce with `python3 scripts/verify_snapshot.py`; see `docs/verification.html`.
- **Starter identity is officially verifiable after the game (T88 takeover).** The NFL publishes no pregame depth chart and the official roster page has no depth column, so a “1st/2nd/3rd/4th string” rank cannot be sourced (F06). The official NFL gamebook does publish the starting lineup by slot, the substitutions, the Did Not Play list and the Not Active list. Nineteen such rows from the Week 10 Commanders at Giants gamebook are recorded in `data/starters_gamebook_2026_reg_10.csv` and on `docs/starters.html` — logged as **F78**; the gamebook carries its own use restriction (**F79**). A single gamebook does not establish pregame depth order. Every row and every game header was independently re-verified against the live page on 2026-11-14 with no discrepancies found (Flag F20). A separate session (30beeb55, T15) reached the same result independently; the manual-transcription limitation is retained (F10).
- The [official NFL Week 10 schedule](https://www.nfl.com/schedules/2026/by-week/week-10) confirms CHI, DEN, PHI and TB were on bye; this is not inferred from injury-report absence.
- No licensed odds archive, historical forecast/outcome ledger, league-published depth chart, player-level participation feed, computed parlay correlation, or tested strategy is available in the Python dashboard. The separate Node research data file was resolved in two steps: T13 (session 30beeb55) blanked all third-party Ourlads ordering values, then the integration supplement (session 52ca9f77, 2026-11-14) located the club-published depth charts on the official club websites ([detroitlions.com](https://www.detroitlions.com/team/depth-chart), [patriots.com](https://www.patriots.com/team/depth-chart)) and restored club-chart-confirmed values with per-row citations. One contradicted third-party value was corrected (Node flag F-08); both club charts self-label "unofficial" (Node flag F-05, Python flag F18).
- No league-level official NFL depth chart exists: the conventional team depth-chart URLs return HTTP 404, and roster pages expose position and status only (F06). The official club depth-chart pages are the best available official-domain depth evidence and carry the self-labeled "unofficial" caveat (F-05).
- The Thursday night result is verified on the official schedule (Commanders 24, Giants 21, final) and is published in the games table (F22, resolved by session 324b0cd2).
- [NFL.com terms](https://support.nfl.com/hc/en-us/articles/35869743904916-NFL-com-Terms-and-Conditions) prohibit systematic retrieval to compile a collection/database absent express prior written consent. No written permission is recorded here for the published injury snapshot; see **F16** on Flagged for Review. Do not expand or automate that data use without written authorization or qualified review.

## Verification, this session

A second, independent transcription of the same official pages was made on 2026-11-14 and compared row by row
(`scripts/verify_live.py`, inputs in `data/verification_inputs/`). **75 of 75 units matched with 0 discrepancies:**
all 345 injury rows across 28 teams (injury, practice status and game status identical), all 32 standings lines on
W-L-T-PF-PA, all 13 Week 11 games on day, kickoff time and network, and the 6-team bye list. Results in
`data/live_reverification_2026-11-14.csv`; flag F69.

Gate G1 is no longer a constant `True` (that was flag F50). It now runs ten checks in `scripts/model.py` —
strictly-earlier training weeks, a from-scratch refit that reproduces archived predictions exactly, and an
early-window fit that provably differs from a full-sample fit — and passes all of them (flag F63).

## Important

This is a research-only project, not betting advice, and no reward has monetary value or is paid. Official
Japan-specific guidance says online sports betting accessed from Japan is prohibited. That guidance does not
determine the legality of a particular skill contest/reward or the rules in any other jurisdiction; see **F09**
and keep wagering, referrals, and rewards disabled pending qualified review. The project owner is located in the
Netherlands; Dutch law (Wet op de kansspelen, Kansspelautoriteit) is flagged as **F19** and has not been reviewed.
See `research/nl-legal-review.md`.

## Research registers (T88 takeover from session 25d6114f)

| Register | File | Rows | What it holds |
|---|---|---|---|
| Verification ledger | `data/verification_week10_2026.csv` | 92 | Every check, its committed value, the official value, the result and a source link |
| Starter identity | `data/starters_gamebook_2026_reg_10.csv` | 19 | Official gamebook lineup status for the Week 10 Thursday game |
| Depth deficiency | `data/depth_deficiency.csv` | 97 | Availability exposure per team and unit, with string rank and impact deliberately blank |
| Line signals | `data/line_signals.csv` | 20 | Signal definitions for single bets, totals, props and combos, each with its leakage risk |
| Skill engine | `data/skill_engine_gates.csv` | 18 | Gates EG0–EG17 with checkable pass rules and no invented thresholds |
| Anti-luck tests | `data/luck_tests.csv` | 10 | Bootstrap intervals, multiplicity control, held-out blocks, clustered uncertainty |
| Correlation plan | `data/correlation_framework.csv` | 10 | Dependent leg pairs with the estimator and sample each one needs; every value blank |
| Leaderboard rules | `data/leaderboard_rules.csv` | 12 | Pre-declared ranking rules; no entry is eligible and no reward is enabled |
| Decision gates | `data/decision_questions.csv` | 20 | Questions to answer before any route is chosen, with the choice the owner faces |
| Suggestions register | `data/suggestions_register.csv` | 18 | Recommendations with options, effort, risk and the gate each depends on |
| Repo review | `data/repo_review.csv` | 27 | Line-by-line findings with a source per row |

No market price, closing line, player-prop outcome, string order, replacement impact, ROI or legal conclusion is
published anywhere in this repository, because none could be confirmed from an official source. Where a value is
missing it is blank and flagged, never inferred. The model's fair lines are first-party computed values and are
labelled as such; they are not market prices.

The leaderboard's three reward tiers are a proposal for review, not an implemented mechanic. Strategies compete
inside this repository; nobody is entered, nothing is staked and nothing is paid out. Read the
[leaderboard](docs/leaderboard.html) on the skill column, and read the flags
[F32](docs/flagged.html) (beating the naive reference line is not beating a sportsbook) and
[F33](docs/flagged.html) (89 games is not yet a decisive sample) before relying on any ranking.
