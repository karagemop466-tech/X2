# X2 — NFL Lines: Executive Summary

**Project:** X2 — NFL line generation, strategy validation, and decision support.
**Repository:** https://github.com/karagemop466-tech/X2
**Site (GitHub Pages):** https://karagemop466-tech.github.io/X2/ (served from `main` / root; pages under `/docs/`)
**Branch of this session:** `arena/22ae094b-x2`, based on `main` @ `38629cad2d5daf388367a682f65de41b0fdc1bb6` (PR #86 merged).

## Objective

Collect, organize, and analyze NFL lines using a complete list of requirements; originate original NFL lines; research and develop signal-generation strategies for single bets, parlays, and player-prop combos; run a leaderboard that rewards top-performing strategies; track injuries and the deficiencies created when 2nd/3rd/4th-string backups replace starters on offense and defense; and present everything on a clean GitHub Pages dashboard. No manual input is required from the owner.

## What has been built (all requirements R01–R65 addressed)

| Area | What exists | State |
|---|---|---|
| Requirements register | `data/requirements.csv` — 65 requirements (R01–R65), each with status, blocker, and source | Complete |
| Decision-readiness table | `data/decision_readiness.csv` — 65 rows, one per requirement, on the landing page, each with its blocking gate and the number that would clear it | Complete (65 of 65) |
| Verified results feed | `data/games_2026_results.csv` — 137 settled games (weeks 1–9 + Week 10 Thursday), each linked to the official NFL schedule/game page and reconciled 32/32 vs the official standings | Published (historical corpus) |
| Parallel v2 results feed | `data/results_feed_v2_2026.csv` — 150 games (adds the 13 transcribed Week 10 games + 8 international neutral-site flags), 15 machine checks, double-read against an independent build | Published in parallel; corpus choice (P09) left to the owner |
| Price-snapshot store | `data/price_snapshots_extended.csv` — 306 rows (13 Week 11 games × side/total/moneyline, in origination order), opening/closing schema in place | Structure complete; prices blank + flagged (no licensed feed, F07/F51) |
| Originated lines | `data/model_lines_week11.csv` / `data/originated_lines_week11.csv` — side first, then total, then moneyline; fair line, market line, difference as separate columns | Fair lines published; market columns blank + flagged (F07) |
| Residual vs market | Model/home/away points, win probability, and edge vs the naive reference line published per game | Published; no market residual computable without prices |
| Signal vs staking | `data/strategy_leaderboard.csv` + `data/strategy_signal_staking.csv` — prospective-only; signal and staking blocks separate; no ranks, scores, hit rates, or ROI published | Unranked; nothing paid |
| Backtest firewall | Historical walk-forward results live on `data/strategy_backtest_scores.csv` and the Backtest page only — never on the competition leaderboard | Enforced in build |
| Validation gates | `data/gate_results.csv` — G1–G9 (incl. look-ahead, sample, significance, multiplicity, CI-excludes-zero, stability, luck, beats-reference) | All proposed, none owner-approved (F17) |
| Demotion gate | `data/demotion_gate.csv` — D1–D7 returns a live strategy to paper | Proposed; inert (no live strategy) |
| Correlations | `data/correlations_computed.csv` — 9 coefficients from official results, each with CI, p-value, and sample `n` | Computed; prop/parlay correlations blank (F31) |
| Injury tracking | `data/injuries_week10_2026.csv` — 347 Week 10 rows (re-read 2026-11-18), per-row official source links | Verified; two dated reads + delta published |
| Availability graph / depth | `data/team_view_week10_2026.csv`, `data/depth_replacement.csv`, `data/replacement_depth_week10_2026.csv` — per-team view, officially named replacements, replacement depth where a club chart verifies | Partial (6 of 32 clubs have a dated club chart; string rank blank where unverified, F06) |
| Depth parsing | `scripts/depth_parse.py` — jersey-number prefixes stripped with raw string retained; slots modelled as groups; empty cells preserved; Texans image refused, not transcribed by eye | 1 club (Green Bay) worked; 11 build-enforced tests |
| Roster / IR sweep | `data/roster_ir_sweep_2026-11-18.csv` — official reserve-list feed (94 Reserve/Injured transactions, 31 of 32 clubs) joined to rosters | Done; Baltimore/Willis examples confirmed |
| Fixture context | `data/fixture_context_2026.csv` — 163 scheduled games from schedule facts only (rest, bye, Thursday) | Built; not yet consumed by the model |
| Venue | `data/venues_2026.csv` — venue transcribed from the official game-centre block | 1 of 163 fixtures (F99); rest blank, never inferred |
| Model outputs as probability + inputs | `data/forecast_records_2026.csv` (178 graded rows) + `data/forecast_records_week11.csv` (26 prospective rows) — probability plus `inputs_json`, reproduced before publishing | Done for the ledger; personnel ablation blocked (no availability input) |
| Removal-of-luck panel | Landing page — historical skill, uncertainty, week consistency, heuristic luck index (flagged F85) | Published; labelled research-only, not a leaderboard |
| Change-our-mind field | `data/strategy_change_rules.csv` — two-sided toward/away-from-trust conditions for each of 7 candidate rules | Design field present; not pre-registered (F87) |
| Two-estimator totals | `data/model_totals_two_estimators_week11.csv` — three totals per game with both gap columns; walk-forward comparison says neither wins (E4); collapse gate left OPEN | Published with negative finding |
| Drift alarm | `scripts/drift_check.py` — 54 registers pinned (row counts, required fields, uniqueness); build stops on failure | Active |
| Suggestions section | `docs/suggestions.html` + `data/suggestions_register.csv` — review proposals with a recommended path and blocking gate before implementation | Complete (review-only) |
| Questions & answers | `docs/questions.html` + `data/decision_questions.csv` — what is known, what is not, and how to find missing information | Complete |
| Sources register | `data/sources.csv` — every official source used, with what it supports | Complete |

## Key findings

1. **No strategy is ranked or rewarded.** The leaderboard is prospective-only and unranked. Historical backtest scores are explicitly excluded. No reward is offered or paid pending legal, jurisdictional (Japan F09, Netherlands F19), and data-rights (F16) review, plus approved gate cut-offs (F17).
2. **No market price is connected.** NFL.com terms (§1.3) prohibit systematic retrieval to compile a database absent express prior written consent, and no permission is recorded (F16 — critical). No licensed odds feed exists, so opening/closing prices, ROI, CLV, vig-free comparison, and market residuals are all blank by design — never inferred or filled in.
3. **The published feed is 13 Week 10 games behind the current standings.** The 137-game feed reconciles 32/32 vs the 2026-11-14 standings read but only 6/32 vs the 2026-11-18 read. A source-linked 13-game backfill reconciles 32/32 vs the current read and is published as a parallel v2 register (F96/F105). Which corpus the metrics grade on is owner decision P09; nothing was recomputed.
4. **Skill signal is modest and not yet established.** Best walk-forward rule gains ~1.74 pts MAE vs the naive reference on the published corpus and ~1.38 pts on the 150-game v2 corpus; the gain does not clearly survive the holdout, and no reward tier is offered (F42 qualification disagreement).
5. **Every table row carries a source link.** Values not confirmable from an official source are left blank and flagged — never inferred.

## What remains blocked (owner decisions, not agent decisions)

- **P09:** choose which results corpus (137 published / 150 v2) the published metrics grade on.
- **F16:** written NFL data-use consent / terms review before any automated or expanded capture.
- **F07/F51:** connect a licensed, timestamped odds archive before any price, ROI, or CLV can be measured.
- **F17:** owner-approve the numeric validation cut-offs and reward tiers.
- **F87:** create an immutable pre-registration commit (rule text, sample window, gates) before a new evaluation window opens.
- **F09/F19:** legal review for Japan and the Netherlands before any wagering, referral, or reward mechanic.
- **D8/D20/D21/D45:** archived prior-season data for train/validation/holdout split and designation calibration.
- **D13/D16:** official inactive lists and snap counts (not captured anywhere in the repo).

## Verification status (this session, 2026-11-19)

All checks green: `scripts/build.py` (55 pages, row-source + link checks), `verify_results.py` (137 games), `verify_live.py` (75/75 units), `verify_snapshot.py` (103 pass / 0 fail / 1 review — Ben Brown position, left flagged), `check_links.py` (3,055 internal / 7,016 external, none broken), `drift_check.py` (54/54 registers pinned), `repo_audit.py` (22 checks, 0 failing), `npm run build && npm run verify` (ALL CHECKS PASSED), `git diff --check` clean.

**Limitation:** this sandbox's outbound network is restricted to github.com / npm / pypi, so nfl.com and other official pages could not be re-fetched live in this session. All NFL values stand as committed and previously verified by prior sessions; nothing was inferred or filled in.
