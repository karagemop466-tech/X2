# COORDINATION — shared task board

Session ID used in this file: **e98c7ba0** (branch `arena/e98c7ba0-x2`).

## Branch rule for this session

The brief asks for `session-<id>/<task>` branches. This session is bound to one branch, `arena/e98c7ba0-x2`. All tasks below are done on that branch, so no other branch was created or pushed (Flag F03). Other sessions that work in parallel should pick a different scope and log it here before starting.

## Task board

Status values: `unclaimed`, `in progress`, `done`, `needs review`.
Files listed are the ones each task touches. Shared outputs (`docs/`, `scripts/build.py`, `COORDINATION.md`) belong to the integration task T10.

| ID | Task | Status | Owner | Files touched | Sources | Notes |
|----|------|--------|-------|---------------|---------|-------|
| T01 | Repo review (line by line) | done | e98c7ba0 | README.md, .gitignore, COORDINATION.md | github.com/karagemop466-tech/X2 | Flags F01, F02, F03 |
| T02 | Injury tracking: Week 10, 2026 snapshot | done | e98c7ba0 | data/injuries_week10_2026.csv, data/games_week10_2026.csv, data/news_week10_2026.csv | S01 (NFL.com/injuries) | 345 rows, 28 teams, 14 games. Flags F05, F10, F12, F13 |
| T03 | Depth exposure (starter / backup) | done, with blanks | e98c7ba0 | scripts/build.py (depth section) | S01, S02 | Starter order UNVERIFIED (F06). Only Out/Doubtful exposure by unit is verified |
| T04 | Questions and requirements | done | e98c7ba0 | data/questions.csv, data/requirements.csv | S01, S02 | Q01–Q18 |
| T05 | Suggestions (choose before change) | needs review (awaiting user choice) | e98c7ba0 | data/suggestions.csv | — | S01–S10. No changes implemented |
| T06 | Strategy lab: gates, hypotheses, leaderboard framework | done (framework); validation blocked | e98c7ba0 | data/strategy_gates.csv, data/strategy_hypotheses.csv | — | No odds or results from official source (F07, F08). No strategy has passed |
| T07 | Legal check: wagering from Japan | needs review | e98c7ba0 | data/flags.csv (F09) | S03, S04 | Official Penal Code text and JSC page checked. Legal opinion still needed |
| T08 | Executive summary | done | e98c7ba0 | scripts/build.py (exec summary) | S01, S03, S04 | Numbers computed by build script |
| T09 | Site: landing, category subpages, Flagged for Review | done | e98c7ba0 | docs/, scripts/build.py | all | Static HTML, no external dependencies |
| T10 | Integration: validate, build, PR, merge, Pages | done (merge + Pages step recorded in log) | e98c7ba0 | COORDINATION.md, PR | all | PR #1: https://github.com/karagemop466-tech/X2/pull/1 |

## Source registry

See `data/sources.csv` (also published at `docs/sources.html`). Every verified value links to one of these official pages:

- S01 NFL.com injury report: https://www.nfl.com/injuries/
- S02 NFL.com Buffalo Bills roster: https://www.nfl.com/teams/buffalo-bills/roster
- S03 e-Gov Penal Code: https://laws.e-gov.go.jp/law/140AC0000000045
- S04 Japan Sport Council: https://www.jpnsport.go.jp/sportspromotion/index.html

## Verification performed

- Injury report read in full (8 chunks) on 2026-11-14. Transcribed into `data/injuries_week10_2026.csv`.
- Checks run by `scripts/build.py`: 345 injury rows, 14 games (each injury row maps to a game number), every row carries an https link on the official-domain allow-list, all internal links in `docs/` resolve, no non-official external link.
- Per-team row counts were compared with the team sections of the NFL.com page (28 teams).
- Manual transcription: spot-check recommended (Flag F10).

## Irregularities

See `data/flags.csv` (F01–F14), also published at `docs/flagged.html` under "Flagged for review". Key items:

- F05: CHI, DEN, PHI, TB are not on the Week 10 report (bye not confirmed).
- F06: starter / backup order not verifiable from the sources checked.
- F07 / F08: no odds or historical results collected.
- F09: Japan wagering law needs legal advice.
- F11: NFL.com roster link slug for "Dee Alford" does not match the name.
- F12: two different official headlines for the Lamar Jackson timeline.

## Log

- 2026-11-14 · e98c7ba0 · Claimed T01–T10 on branch `arena/e98c7ba0-x2`. Work done on this branch only.
- 2026-11-14 · e98c7ba0 · T01 (repo review), T02 (injury data), T04, T06, T08 completed in this branch. T03, T09 built with `scripts/build.py`.
- 2026-11-14 · e98c7ba0 · Data-file repair: four CSV files had unquoted commas (questions, suggestions, news, flags). Rewritten or repaired. Nothing else affected.
- 2026-11-14 · e98c7ba0 · Integration check: `python3 scripts/build.py` passes (345 injury rows, 14 games, 11 pages, all links resolve, all row links official).
- 2026-11-14 · e98c7ba0 · Pull request opened: https://github.com/karagemop466-tech/X2/pull/1 (base `main`, head `arena/e98c7ba0-x2`). Merge with `--merge` next, without waiting for approval, per the brief.
- No merge conflicts. No other session has touched these files.
