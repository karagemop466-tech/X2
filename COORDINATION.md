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
| `e98c7ba0` | `arena/e98c7ba0-x2` | Built the **live** `docs/` site (Python `scripts/build.py`), 345 injury rows. PRs #1–#3 merged to `main`. |
| `d80442c2` | `arena/d80442c2-x2` | Supplemental post-merge source/compliance audit and handoff (T11). PRs #5–#6 merged to `main`. Touches `COORDINATION.md` only. |
| `session-09d7cc77` | `arena/09d7cc77-x2` | Parallel Node dashboard (`src/`), docs, JSON data. PR #4 merged into `main`; Node output remains separate from the root-forwarded Python Pages site. |
| `7678436e` | `arena/7678436e-x2` | Source-link/validation follow-up to the live Python dashboard; rebased onto the latest `main`, PR pending. F16 terms/data-rights, F17 numeric-cutoff, and F18 Node third-party-depth review flags remain explicit. |
| `25d6114f` | `arena/25d6114f-x2` | Session 4. Owns the live Python Pages pipeline (`scripts/build.py`, `data/*.csv`, `docs/`). Tasks T14–T20: line-by-line re-verification of the committed snapshot against nfl.com, original-line signal research, leaderboard + anti-luck statistics, depth-chart deficiency model, decision-gate Q&A register, suggestion/option registry, and site build. Does **not** edit Node-owned files (`src/**`, `data/*.json`, `docs/*.md`). |

## Task board (combined — all sessions)

| ID | Task | Status | Owner | Files touched | Sources | Notes |
|----|------|--------|-------|---------------|---------|-------|
| T01 | Repo review (line by line) | done | e98c7ba0 | README.md, .gitignore, COORDINATION.md | github.com/karagemop466-tech/X2 | Flags F01, F02, F03 |
| T02 | Injury tracking: Week 10, 2026 snapshot | done (rights/spot-check follow-up open) | e98c7ba0 | data/injuries_week10_2026.csv, data/games_week10_2026.csv, data/news_week10_2026.csv | NFL.com injury report; NFL Week 10 schedule | 345 rows, 28 teams, 14 games. F05 bye list confirmed by T12; transcription spot-check F10 and permission F16 remain open |
| T03 | Depth exposure (starter / backup) | done, with blanks | e98c7ba0 | scripts/build.py (depth section) | S01, S02 | Starter order UNVERIFIED (F06). Only Out/Doubtful exposure by unit is verified |
| T04 | Questions and requirements | done | e98c7ba0 | data/questions.csv, data/requirements.csv | S01, S02 | Q01–Q18 |
| T05 | Suggestions (review before future implementation) | done (review-only; no user choice required to finish this brief) | e98c7ba0 / 7678436e | data/suggestions.csv | NFL terms, official odds/data sources, NIST, Government of Japan | S01–S10 are sourced proposals; no feature is implemented or waiting on user input |
| T06 | Strategy lab: independent lines, gates, hypotheses, correlation and leaderboard framework | done (framework); validation blocked | e98c7ba0 / 7678436e | data/strategy_gates.csv, data/strategy_hypotheses.csv, scripts/build.py | NFL stats/odds context; NIST methods | No lines, prices, performance or correlations calculated; F17 numeric thresholds blank; no strategy has passed |
| T07 | Legal check: wagering from Japan | needs review | e98c7ba0 | data/flags.csv (F09) | S03, S04 | Official Penal Code text and JSC page checked. Legal opinion still needed |
| T08 | Executive summary | done | e98c7ba0 | scripts/build.py (exec summary) | S01, S03, S04 | Numbers computed by build script |
| T09 | Site: landing, category subpages, Flagged for Review | done | e98c7ba0 | docs/, scripts/build.py | all | Static HTML, no external dependencies |
| T10 | Integration: validate, build, PR, merge, Pages | done | e98c7ba0 | COORDINATION.md, PRs | all | PR #1 (0563aab), PR #2 (2c9f374). Live: https://karagemop466-tech.github.io/X2/ |
| T11 | Supplemental post-merge source/compliance audit and handoff | done (audit merged; follow-up recommendations remain) | d80442c2 | COORDINATION.md only; T01–T10-owned `docs/`, `data/*.csv`, and `scripts/build.py` left untouched | T11-S1–T11-S4 | PR #5 (71e65aa), PR #6 (241a142). Findings handed off to the dashboard owner. No duplicate dashboard/data changes published. |
| T12 | Source-link completeness and research-gate remediation for the Python Pages site | in progress | 7678436e | README.md, data/questions.csv, data/requirements.csv, data/suggestions.csv, data/strategy_gates.csv, data/strategy_hypotheses.csv, data/sources.csv, data/flags.csv, scripts/build.py, generated legacy `docs/*.html` and `docs/data/*.json`, COORDINATION.md | NFL, Government of Japan/NPA, NIST; first-party GitHub records for project facts | Repaired 41 source-less table rows; universal builder checks; independent line/correlation plan and leaderboard empty state; F16 terms/data rights, F17 thresholds. F18 requests review of third-party Node depth values without editing session-09d files. PR/deploy pending. |
| T13 | Review third-party depth values in the separate Node dashboard against official-only requirement | unclaimed | — | `data/depth-deficiencies.json`, Node dashboard source/output | Official NFL primary sources; current entries also cite Ourlads (third-party) | Python dashboard flags these as F18; no T12 edits to the completed Node task. Keep them blank/unverified or replace with official evidence before describing as official NFL facts. |
| T14 | Independent re-verification of the committed Week 10 snapshot, line by line, against nfl.com | in progress | 25d6114f | `data/verification_week10_2026.csv` (new), `docs/verification.html`, `docs/data/verification_week10_2026.json`, `scripts/build.py` | nfl.com injury report, schedules, standings | Re-read every committed row against the live official page. No committed value is edited; mismatches are recorded as rows and flagged. |
| T15 | Original-line signal research: strategy families, feature definitions, gate criteria, correlation model, leaderboard and anti-luck statistics | in progress | 25d6114f | `data/strategy_signals.csv` (new), `data/strategy_eval.csv` (new), `data/correlation_matrix.csv` (new), `docs/strategy-lab.html` (rebuild) | no licensed odds/results feed available — all numeric cells that require one stay blank | Signals are defined and gated only; nothing is claimed as tested or profitable. |
| T16 | Depth-chart deficiency model for offense and defense (1st/2nd/3rd/4th string) | in progress | 25d6114f | `data/depth_deficiency.csv` (new), `docs/depth-analysis.html` (rebuild) | NFL.com injury report + rosters; no official public depth chart | String rank stays blank unless an official source states it; only verified absence and unit exposure are published. |
| T17 | Decision-gate register: every question, information gap and answer required before a path can be chosen | in progress | 25d6114f | `data/decision_questions.csv` (new), `docs/decision-gates.html` (new) | official sources per row | Extends Q01–Q18 without editing `data/questions.csv`. |
| T18 | Suggestion and option registry with review workflow (choose a path before implementing) | in progress | 25d6114f | `data/suggestions_register.csv` (new), `docs/suggestions.html` (rebuild) | NFL terms, NIST, GitHub Pages docs | Extends S01–S10 without editing `data/suggestions.csv`; nothing is auto-implemented. |
| T19 | Repo review, line by line, of every owned file, with a source link and a finding per line group | in progress | 25d6114f | `data/repo_review.csv` (new), `docs/repo-review.html` (new) | first-party GitHub records + official sources | Flags every irregularity; no value is changed without a source. |
| T20 | Integration: validate combined data, rebuild, broken-link check, executive summary refresh, PR to `main`, merge, confirm Pages live | in progress | 25d6114f | `COORDINATION.md`, `README.md`, PR, live site | all of the above | Runs only after T14–T19 are `done`; re-verifies the combined data before merge. |
| T1 | Scaffold repo, coordination board, static-site build system | done | session-09d7cc77 | COORDINATION.md, package.json, .gitignore, src/**, README.md | Build verified: `npm run build` emits 12 pages; `npm run verify` passes | Node generator foundation |
| T2 | Requirements, executive summary, questions & answers, suggestions | done | session-09d7cc77 | docs/00-*.md … docs/03-*.md, data/requirements.json, data/questions.json, data/suggestions.json | Official NFL sources + methodology | 28 requirements, 14 questions, 13 suggestions |
| T3 | Strategy research, validation gates, correlation values, leaderboard | done | session-09d7cc77 | docs/04-*.md … docs/07-*.md, data/strategies.json, data/validation-gates.json, data/correlations.json, data/leaderboard.json | CLV/market-efficiency methodology | Correlation values blank + flagged |
| T4 | Injury tracking & depth-chart deficiency system | done | session-09d7cc77 | docs/08-*.md, data/injuries.json, data/depth-deficiencies.json | NFL.com Week 10 injury report; Ourlads depth charts | 19 verified injury rows; 6 depth-deficiency rows |
| T5 | Data sources & verification methodology, flagged register | done | session-09d7cc77 | docs/09-*.md, docs/10-*.md, data/sources.json, data/flagged.json | All source URLs verified 2026-11-14 | 17 sources, 7 flagged items |
| T6 | Build the GitHub Pages site (landing + subpages, dashboard UI) | done | session-09d7cc77 | src/**, site/** (generated) | `npm run verify`: 196 internal links, all resolve | Node dashboard; per-row source links |
| T7 | Integration: merge into main, re-verify, confirm live site | done | session-09d7cc77 | main (merge), COORDINATION.md, README.md | Re-verified combined data; confirmed live Pages | See merge/conflict log below |

## Source registry (combined)

Every verified value links to one of these official pages (full lists also at
`data/sources.csv` and `docs/sources.html`):

**Core (e98c7ba0):**
- **S01** NFL.com injury report: https://www.nfl.com/injuries/
- **S02** NFL.com team roster (e.g. Buffalo Bills): https://www.nfl.com/teams/buffalo-bills/roster
- **S03** e-Gov Penal Code (Japan): https://laws.e-gov.go.jp/law/140AC0000000045
- **S04** Japan Sport Council: https://www.jpnsport.go.jp/sportspromotion/index.html

**Supplemental (d80442c2 — T11 audit; not yet in data/sources.csv):**
- **T11-S1** NFL.com Terms and Conditions (Section 1.3): https://www.nfl.com/legal/terms/ — states systematic retrieval to compile data/content is prohibited absent express prior written consent.
- **T11-S2** NFL API documentation entry point: https://api.nfl.com/docs/global/endpoints/index.html — redirected to NFL sign-on during review; public access/scope unverified.
- **T11-S3** GitHub Pages documentation: https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages
- **T11-S4** NIST/SEMATECH bootstrap and held-out validation references: https://www.itl.nist.gov/div898/handbook/eda/section3/bootplot.htm and https://itl.nist.gov/div898/handbook/pri/section6/pri636.htm (general methods only).

**Additional (session-09d7cc77):**
- NFL.com standings: https://www.nfl.com/standings/
- NFL.com team stats (offense/defense): https://www.nfl.com/stats/team-stats/
- NFL.com transactions (reserve list): https://www.nfl.com/transactions/league/reserve-list/2026/11
- NFL Operations — 2026 Rulebook: https://operations.nfl.com/rules-officiating/2026-nfl-rulebook
- ESPN depth charts: https://www.espn.com/nfl/depthcharts (third-party)
- Ourlads depth charts: https://www.ourlads.com/nfldepthcharts/depthcharts.aspx (third-party)
- Odds aggregators (references, not official): VegasInsider, Covers, FOX Sports
- CLV / market-efficiency methodology: Squawka, OddsIndex, NFL Betting Math

**T12 supplement (7678436e; official references and first-party project records are catalogued in `data/sources.csv` as SRC-01–SRC-24):**
- NFL Week 10 schedule/bye list: https://www.nfl.com/schedules/2026/by-week/week-10
- NFL.com Terms and Conditions: https://support.nfl.com/hc/en-us/articles/35869743904916-NFL-com-Terms-and-Conditions
- NFL Support odds FAQ and NFL data-partner announcement: https://support.nfl.com/hc/en-us/articles/35869698780564-If-I-place-a-bet-on-NFL-com-or-the-NFL-app-am-I-betting-with-the-NFL · https://www.nfl.com/news/nfl-draftkings-fanduel-fanatics-sports-betting-partners
- Government of Japan and National Police Agency online-gambling guidance: https://www.gov-online.go.jp/article/202411/entry-6786.html · https://www.npa.go.jp/bureau/safetylife/hoan/onlinecasino/onlinecasino.html
- NIST/SEMATECH model validation, multiple comparisons, correlation, confidence intervals and bootstrap: https://www.itl.nist.gov/div898/handbook/pmd/section4/pmd44.htm · https://www.itl.nist.gov/div898/handbook/prc/section4/prc47.htm · https://www.itl.nist.gov/div898/handbook/glossary.htm · https://www.itl.nist.gov/div898/handbook/eda/section3/eda352.htm · https://www.itl.nist.gov/div898/handbook/eda/section3/bootplot.htm

## Verification performed

**Session e98c7ba0:**
- Injury report read in full (8 chunks) on 2026-11-14. Transcribed into
  `data/injuries_week10_2026.csv`.
- `python3 scripts/build.py` checks: 345 injury rows, 14 games, every row carries an
  https link on the official-domain allow-list, all internal links in `docs/`
  resolve, no non-official external link.
- Per-team row counts compared with the team sections of the NFL.com page (28 teams).

**Session d80442c2:**
- Independently opened NFL.com Terms and Conditions (Section 1.3) and the NFL API
  documentation entry point; recorded findings as T11-S1/T11-S2. Confirmed GitHub
  Pages serves static files (T11-S3). Did not modify site/data/build files.

**Session 09d7cc77:**
- All source URLs resolved/verified 2026-11-14 (official NFL.com, NFL Operations;
  third-party ESPN/Ourlads; odds aggregators; methodology refs).
- Real verified data: NFL.com Week 10 injury report + DET/NE depth charts
  cross-referenced into 6 depth-deficiency entries.
- `npm run verify`: all `data/*.json` rows resolve to a known source; 196 internal
  links across 12 HTML files resolve. ALL CHECKS PASSED.

**Session 7678436e (T12, Python dashboard follow-up):**
- The original `origin/main` Python build was unpacked to a temporary directory and independently audited. It built successfully but had 41 source-less question, requirement, suggestion, gate and hypothesis rows.
- T12 added evidence URLs and made the Python builder require evidence URLs for every one of those CSV rows; the generated-HTML check now rejects any table row without an allow-listed HTTPS source.
- `python3 -m py_compile scripts/build.py`, `python3 scripts/build.py`, `npm run build`, `npm run verify` and `git diff --check` pass. Python output: 11 pages, 345 injury rows, 28 teams, 14 games and 61 unit exposure rows; Node output: 12 pages, 196 internal links and all JSON rows source-resolved. Node output remains separate from the root-forwarded Python Pages site.
- Independent audit: 63 evidence-bearing CSV rows and 573 generated table rows; zero missing or non-allowlisted source URLs, zero source-less rows. Temporary negative tests confirmed that a blank Q09 link and an `example.com` link are rejected.
- The NFL Week 10 schedule explicitly confirms CHI, DEN, PHI and TB were on bye (F05). Injury values were not changed. Numeric strategy cutoffs remain blank (F17); no odds, forecast, replacement-impact, correlation or performance value was invented.
- F16 records that written permission for systematic NFL injury-data collection/publication is not found in this repo; F17 records unapproved numeric cutoffs. F18 flags separate Node depth rows that cite third-party Ourlads charts; T12 did not edit the Node-owned data. These flags do not establish a legal conclusion.

## Irregularities (combined)

**Session e98c7ba0 flags (F01–F15, published at `docs/flagged.html`):**
- F05: CHI, DEN, PHI, TB are not on the Week 10 report (bye not confirmed).
- F06: starter / backup order not verifiable from the sources checked.
- F07 / F08: no odds or historical results collected.
- F09: Japan wagering law needs legal advice.
- F10: 345 injury rows transcribed manually — spot-check recommended.
- F11: NFL.com roster link slug for "Dee Alford" does not match the name.
- F12: two different official headlines for the Lamar Jackson timeline.
- F15: GitHub Pages source is main / (root), not /docs. Token returned HTTP 403 when
  changing it. Root index.html forwards to docs/index.html.

**Session d80442c2 audit request — F16 terms/compliance (implemented by T12):**
- NFL.com Terms and Conditions Section 1.3 prohibits systematic retrieval to compile
  a collection/database absent express prior written consent (T11-S1). T12 added
  `data/flags.csv` F16 and a prominent homepage warning. No automated NFL.com data
  collection is implemented; permission for the existing published snapshot is not
  recorded, so this remains a critical open rights gate.

**Session 09d7cc77 flags (F-01–F-07, published on the Node Flagged for Review page):**
- F-01: Ben Brown position discrepancy (C in injury report vs RG on depth chart).
- F-02: correlation values unverified (blank — must be computed, not assumed).
- F-03: live line values unverified (blank — no single official odds source;
  repository-scope finding: no sportsbook price feed is connected here).
- F-04: live performance values unverified (blank — no live data).
- F-05: depth charts are third-party, not official.
- F-06: player-stats feed not confirmed.
- F-07: NFL.com Terms Section 1.3 — systematic-retrieval restriction; automated
  collection requires authorization (mirrors F16 in the Python register).

**Python dashboard T12 status:**
- F05: Week 10 bye status is now confirmed from the official schedule, not inferred from injury-report absence.
- F16: written permission for the existing NFL injury snapshot is not recorded; data rights remain unresolved.
- F17: numerical validation cutoffs are blank/unverified; no strategy has passed.
- F18: separate Node depth-deficiency rows cite Ourlads third-party charts; those player/backup values are not official NFL facts. T12 logged a request and did not edit the Node-owned file.
- The Node `data/flagged.json` IDs `F-01`–`F-07` and Python `data/flags.csv` IDs `F01`–`F18` are separate registers; do not conflate their identifiers.

## Requests between sessions

**d80442c2 → dashboard owner (T09/T10 scope — logged, not edited by 09d7cc77):**
These requests target `e98c7ba0`-owned files (`docs/`, `data/*.csv`,
`scripts/build.py`) and are logged here per the coordination rule rather than edited
by session-09d7cc77:
1. **F16 terms/compliance** — add a prominent Flagged for Review item; do not
   implement automated scraping until authorized (T11-S1). *(09d7cc77 mirrored this
   as its own F-07 and added the source.)*
2. **Narrow odds assertions** — replace absolute "NFL does not publish odds" claims
   in `data/flags.csv` F07 and `data/questions.csv` Q08 with the repository-scope
   finding; flag the provider as missing.
3. **Remove unreviewed legal conclusions** from README (Japan wagering) — use neutral
   language. *(09d7cc77 addressed this in its own README; the shared README now uses
   neutral language.)*
4. **Correct post-merge publishing/status documentation** in README to match the
   verified root-forwarder configuration. *(09d7cc77's README reflects this.)*
5. **Enforce per-row source** in `scripts/build.py` — reject blank `evidence_url`
   rows (e.g. H03–H06, G1–G7); correct the S02 source-ID mismatch.
6. **Keep proposed validation thresholds** explicitly unapproved (not in "passed"
   criteria).
7. **Preserve the manual-transcription limitation** (F10).
8. **Reconcile terms review status** in Q18.

**T12 follow-up (7678436e, current branch):** addressed requests 1–8 for the Python dashboard with source-backed wording, a universal CSV/HTML source-link validator, explicit F16/F17 flags, blank unapproved numeric cutoffs, and clearer line/correlation/leaderboard scaffolding. No injury-row values were edited; the source/license question remains open and is not treated as cleared.

**T13 request (unclaimed):** The separate Node `data/depth-deficiencies.json` contains player/backup values sourced partly from Ourlads, a third-party chart provider. The Node docs disclose that limitation, but the user's official-source-only rule means these cannot be described as official NFL facts. T12 added Python Flag F18 with a link to that project file; it did not edit the completed Node task's owned data. A Node dashboard owner should blank/suppress these values or locate an official primary depth-chart source before promoting that output.

## Merge / conflict log

- **2026-11-14 · session-09d7cc77 · merge conflict on PR #4 (session 1 vs 2).**
  While merging `arena/09d7cc77-x2` into `main`, `main` had advanced with session
  e98c7ba0's merged work (PRs #1–#3). Conflict in `.gitignore`, `README.md`, and
  `COORDINATION.md` (add/add + content). **Resolution:** combined both sessions'
  content; neither discarded. The Node `deploy.yml` workflow was removed because the
  Pages source is branch-based (main /) and switching to Actions returns HTTP 403
  (flag F15) — keeping it would create a failing deploy check.
- **2026-11-14 · session-09d7cc77 · merge conflict on PR #4 (session 1+2 vs 3).**
  After the first resolution, `main` advanced again with session d80442c2's audit
  (PRs #5–#6), which edited `COORDINATION.md`. Merging `origin/main` into the branch
  produced a second `COORDINATION.md` conflict. **Resolution:** combined all three
  sessions' task boards, sources, verification, irregularities, and audit requests
  into this single board; no session's records were discarded. The d80442c2 requests
  that target e98c7ba0-owned files are logged under "Requests between sessions" and
  were not edited by 09d7cc77. README legal language was updated to neutral.
- **2026-11-14 · session-09d7cc77 · PR #4 merged.** Pull request
  https://github.com/karagemop466-tech/X2/pull/4 (base `main`, head
  `arena/09d7cc77-x2`) merged with `--merge`; merge commit `2657d4d`. After the
  merge, `main` is an ancestor of the branch (clean fast-forward). Both build
  systems pass: `python3 scripts/build.py` (11 pages, 345 injury rows) and
  `npm run build` + `npm run verify` (12 pages, all checks). GitHub Pages rebuilt
  from `main` and is `built`. **Live site verified:**
  https://karagemop466-tech.github.io/X2/ serves the NFL Research Dashboard
  (executive summary, injuries, games, depth exposure, strategy lab, questions,
  requirements, suggestions, flagged for review, sources).

## Handoff log

_No formal handoffs. Each session completed its work on its own branch; the
integration session (09d7cc77) merged them into `main` and re-verified the combined
data and live site._

- **2026-11-14 · 7678436e · rebase onto latest main.** The first `git pull --rebase` against the session branch failed on the add/add coordination file, so that rebase was aborted. After `origin/main` advanced through PR #4 and the d80442c2 audit, T12 was rebased onto `origin/main` at `9608561`. Conflicts were limited to `README.md` and `COORDINATION.md`; resolution retained the complete latest main records (including the Node dashboard/audit history) and added T12 without changing Node files or discarding prior session notes. The current branch remains `arena/7678436e-x2`; its remote still has the earlier pre-rebase history, so publish with a lease-protected update only after final verification.
