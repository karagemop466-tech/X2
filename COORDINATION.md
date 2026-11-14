# COORDINATION.md — Shared Task Board

> This is the shared task board for the **X2 NFL lines** project. Multiple agent
> sessions work in this repository in parallel. **Read this file before starting any
> task.** It lists every task, its status, the owning session, and the files it
> touches. Keep scopes non-overlapping.

## How to use this board

1. Pick a task whose status is `unclaimed`.
2. Claim it by writing your **session ID** and the **file scope** you will edit.
3. Commit and push the claim immediately.
4. Work only inside your claimed file scope. If a task needs a file owned by
   another session, **log the request here** instead of editing it.
5. Make small, frequent commits. Run `git pull --rebase` before every push.
6. On a merge conflict: stop, resolve it without discarding the other session's
   work, and log what happened here.
7. When a task is done, record its **sources**, the **verification performed**,
   and any **irregularities** here, then mark it `done`.
8. **Never mark anything verified without checking it against an official
   source — link that source.**
9. If a session crashes or its claim is more than **60 minutes** old with no
   commits, any other session may take over and note the handoff here.

**Status values:** `unclaimed` · `in progress` · `needs review` · `done`
(`needs review` items are published on the Flagged for Review page and do not
block anything).

**Rule on shared outputs:** the site's table data, `index` and navigation are
changed **only by the final integration session**, once all other tasks are done.
That session merges branches, re-verifies the combined data line by line,
confirms the site builds with no broken links, and publishes to GitHub Pages.

## Sessions

| Session ID | Branch | Notes |
|---|---|---|
| `e98c7ba0` | `arena/e98c7ba0-x2` | Built the **live** `docs/` site (Python `scripts/build.py`), 345 injury rows, PRs #1–#3 merged to `main`. |
| `session-09d7cc77` | `arena/09d7cc77-x2` | Built a parallel Node dashboard (`src/`), docs, and JSON data. Now performing the integration merge into `main`. |

## Task board (combined)

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
| T10 | Integration: validate, build, PR, merge, Pages | done | e98c7ba0 | COORDINATION.md, PRs | all | PR #1 (0563aab), PR #2 (2c9f374). Live: https://karagemop466-tech.github.io/X2/ |
| T1 | Scaffold repo, coordination board, static-site build system | done | session-09d7cc77 | COORDINATION.md, package.json, .gitignore, src/**, README.md | Build verified: `npm run build` emits 12 pages to `site/`; `npm run verify` passes | Node generator foundation |
| T2 | Requirements, executive summary, questions & answers, suggestions | done | session-09d7cc77 | docs/00-*.md … docs/03-*.md, data/requirements.json, data/questions.json, data/suggestions.json | Official NFL sources + methodology | 28 requirements, 14 questions, 13 suggestions |
| T3 | Strategy research, validation gates, correlation values, leaderboard | done | session-09d7cc77 | docs/04-*.md … docs/07-*.md, data/strategies.json, data/validation-gates.json, data/correlations.json, data/leaderboard.json | CLV/market-efficiency methodology | Correlation values blank + flagged |
| T4 | Injury tracking & depth-chart deficiency system | done | session-09d7cc77 | docs/08-*.md, data/injuries.json, data/depth-deficiencies.json | NFL.com Week 10 injury report; Ourlads depth charts | 19 verified injury rows; 6 depth-deficiency rows |
| T5 | Data sources & verification methodology, flagged register | done | session-09d7cc77 | docs/09-*.md, docs/10-*.md, data/sources.json, data/flagged.json | All source URLs verified 2026-11-14 | 16 sources, 6 flagged items |
| T6 | Build the GitHub Pages site (landing + subpages, dashboard UI) | done | session-09d7cc77 | src/**, site/** (generated) | `npm run verify`: 196 internal links, all resolve | Node dashboard; per-row source links |
| T7 | Integration: merge into main, re-verify, confirm live site | done | session-09d7cc77 | main (merge), COORDINATION.md | Re-verified combined data; confirmed live Pages | See merge/conflict log below |

## Source registry (combined)

Every verified value links to one of these official pages (full lists also at
`data/sources.csv` and `docs/sources.html`):

- **S01** NFL.com injury report: https://www.nfl.com/injuries/
- **S02** NFL.com team roster (e.g. Buffalo Bills): https://www.nfl.com/teams/buffalo-bills/roster
- **S03** e-Gov Penal Code (Japan): https://laws.e-gov.go.jp/law/140AC0000000045
- **S04** Japan Sport Council: https://www.jpnsport.go.jp/sportspromotion/index.html
- NFL.com standings: https://www.nfl.com/standings/
- NFL.com team stats (offense/defense): https://www.nfl.com/stats/team-stats/
- NFL.com transactions (reserve list): https://www.nfl.com/transactions/league/reserve-list/2026/11
- NFL Operations — 2026 Rulebook: https://operations.nfl.com/rules-officiating/2026-nfl-rulebook
- ESPN depth charts: https://www.espn.com/nfl/depthcharts (third-party)
- Ourlads depth charts: https://www.ourlads.com/nfldepthcharts/depthcharts.aspx (third-party)
- Odds aggregators (references, not official): VegasInsider, Covers, FOX Sports
- CLV / market-efficiency methodology: Squawka, OddsIndex, NFL Betting Math

## Verification performed

**Session e98c7ba0:**
- Injury report read in full (8 chunks) on 2026-11-14. Transcribed into
  `data/injuries_week10_2026.csv`.
- `python3 scripts/build.py` checks: 345 injury rows, 14 games, every row carries an
  https link on the official-domain allow-list, all internal links in `docs/`
  resolve, no non-official external link.
- Per-team row counts compared with the team sections of the NFL.com page (28 teams).

**Session 09d7cc77:**
- All source URLs resolved/verified 2026-11-14 (official NFL.com, NFL Operations;
  third-party ESPN/Ourlads; odds aggregators; methodology refs).
- Real verified data: NFL.com Week 10 injury report + DET/NE depth charts
  cross-referenced into 6 depth-deficiency entries.
- `npm run verify`: all 104 `data/*.json` rows resolve to a known source; 196
  internal links across 12 HTML files resolve. ALL CHECKS PASSED.

## Irregularities (combined)

Session e98c7ba0 flags (F01–F15, published at `docs/flagged.html`):
- F05: CHI, DEN, PHI, TB are not on the Week 10 report (bye not confirmed).
- F06: starter / backup order not verifiable from the sources checked.
- F07 / F08: no odds or historical results collected.
- F09: Japan wagering law needs legal advice.
- F11: NFL.com roster link slug for "Dee Alford" does not match the name.
- F12: two different official headlines for the Lamar Jackson timeline.
- F15: GitHub Pages source is main / (root), not /docs. The token returned HTTP 403
  when changing it. Root index.html forwards to docs/index.html.

Session 09d7cc77 flags (F-01–F-06, published at `docs/10-flagged-for-review.md` /
Node site):
- F-01: Ben Brown position discrepancy (C in injury report vs RG on depth chart).
- F-02: correlation values unverified (blank — must be computed, not assumed).
- F-03: live line values unverified (blank — no single official odds source).
- F-04: live performance values unverified (blank — no live data).
- F-05: depth charts are third-party, not official.
- F-06: player-stats feed not confirmed.

## Requests between sessions

_No cross-session file requests logged._

## Merge / conflict log

- **2026-11-14 · session-09d7cc77 · merge conflict on PR #4.** While merging
  `arena/09d7cc77-x2` into `main`, `main` had already advanced with session
  e98c7ba0's merged work (PRs #1–#3). Conflict in `.gitignore`, `README.md`, and
  `COORDINATION.md` (add/add + content). **Resolution:** combined both sessions'
  content in all three files — neither session's work was discarded. The merged
  `COORDINATION.md` above now records both task boards, sources, verification, and
  irregularities. The live Pages site remains the `docs/` build (session e98c7ba0);
  the Node `src/` generator is retained as a complementary build tool. The Node
  `deploy.yml` workflow was **removed** because the Pages source is branch-based
  (main /) and switching to Actions returns HTTP 403 (flag F15) — keeping it would
  create a failing deploy check. No other conflicts; all other files merged cleanly.

## Handoff log

_No handoffs. Both sessions completed their work on their own branches._
