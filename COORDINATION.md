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
| T10 | Integration: validate, build, PR, merge, Pages | done | e98c7ba0 | COORDINATION.md, PR | all | PR #1 (merged 0563aab): https://github.com/karagemop466-tech/X2/pull/1 · PR #2 (merged 2c9f374): https://github.com/karagemop466-tech/X2/pull/2 · Live: https://karagemop466-tech.github.io/X2/ |
| T11 | Supplemental post-merge source/compliance audit and handoff | done (audit merged; follow-up recommendations remain) | d80442c2 | COORDINATION.md only; T01–T10-owned `docs/`, `data/*.csv`, and `scripts/build.py` left untouched | T11-S1–T11-S4 below | PR #5 merged (71e65aac); findings are handed off to the dashboard owner. No duplicate dashboard/data changes were published from this branch. |

## Source registry

See `data/sources.csv` (also published at `docs/sources.html`). Every verified value links to one of these official pages:

- S01 NFL.com injury report: https://www.nfl.com/injuries/
- S02 NFL.com Buffalo Bills roster: https://www.nfl.com/teams/buffalo-bills/roster
- S03 e-Gov Penal Code: https://laws.e-gov.go.jp/law/140AC0000000045
- S04 Japan Sport Council: https://www.jpnsport.go.jp/sportspromotion/index.html
Supplemental references for T11 only (not yet added to `data/sources.csv` or the published source page):

- T11-S1 NFL.com Terms and Conditions (Section 1.3): https://www.nfl.com/legal/terms/ — opened 2026-11-14; states systematic retrieval to compile data/content is prohibited absent express prior written consent.
- T11-S2 NFL API documentation entry point: https://api.nfl.com/docs/global/endpoints/index.html — direct access redirected to NFL sign-on during review; public access, scope and reuse rights are unverified.
- T11-S3 GitHub Pages static-hosting documentation: https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages — confirms Pages serves static files.
- T11-S4 NIST/SEMATECH bootstrap and held-out validation references: https://www.itl.nist.gov/div898/handbook/eda/section3/bootplot.htm and https://itl.nist.gov/div898/handbook/pri/section6/pri636.htm — general methods only, not NFL-specific evidence.

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
- F15: GitHub Pages source is main / (root), not /docs. The token returned HTTP 403 when changing it. Root index.html forwards to docs/index.html.

## Log

- 2026-11-14 · e98c7ba0 · Claimed T01–T10 on branch `arena/e98c7ba0-x2`. Work done on this branch only.
- 2026-11-14 · e98c7ba0 · T01 (repo review), T02 (injury data), T04, T06, T08 completed in this branch. T03, T09 built with `scripts/build.py`.
- 2026-11-14 · e98c7ba0 · Data-file repair: four CSV files had unquoted commas (questions, suggestions, news, flags). Rewritten or repaired. Nothing else affected.
- 2026-11-14 · e98c7ba0 · Integration check: `python3 scripts/build.py` passes (345 injury rows, 14 games, 11 pages, all links resolve, all row links official).
- 2026-11-14 · e98c7ba0 · Pull request opened: https://github.com/karagemop466-tech/X2/pull/1 (base `main`, head `arena/e98c7ba0-x2`). Merge with `--merge` next, without waiting for approval, per the brief.
- 2026-11-14 · e98c7ba0 · PR #1 merged into main (merge commit 0563aab). Enabling Pages from main /docs returned HTTP 403, and the existing Pages config is main /. Workaround in PR #2: root index.html forwards to docs/ (Flag F15).
- 2026-11-14 · e98c7ba0 · PR #1 merged to main (`--merge`, merge commit 0563aab, 02:45:30Z).
- 2026-11-14 · e98c7ba0 · Pages source change to /docs refused (HTTP 403). PR #2 merged to main (merge commit 2c9f374, 02:46:10Z) with a root index.html that forwards to docs/ (F15).
- 2026-11-14 · e98c7ba0 · GitHub Pages build for commit 2c9f374: status `built`. Live check: https://karagemop466-tech.github.io/X2/ forwards to docs/index.html and shows 345 players, 28 teams, 66 Out, 10 Doubtful, 84 Questionable. Flagged page live at https://karagemop466-tech.github.io/X2/docs/flagged.html.
- No merge conflicts. No other session had touched these files as of this log entry.

## Supplemental audit and handoff — session d80442c2

- 2026-11-14 — A pre-existing task board was not present in the initial local checkout. After the initial claim commit/push and before pushing the later site work, `git pull --rebase origin main` fetched PRs #1–#3 from `arena/e98c7ba0-x2`; main already contained completed T01–T10 and the live dashboard. This produced an add/add conflict in `COORDINATION.md`. It was resolved by preserving the complete main-branch board and recording this audit; no T01–T10 `docs/`, `data/*.csv` or `scripts/build.py` file was overwritten. The duplicate dashboard commit from this branch was skipped to avoid replacing the published root forwarder or duplicating T09.
- 2026-11-14 — Independently checked NFL.com Terms and Conditions, Section 1.3: <https://www.nfl.com/legal/terms/>. It states systematic retrieval to compile a collection/database is prohibited absent express prior written consent. The official NFL API documentation URL <https://api.nfl.com/docs/global/endpoints/index.html> redirected to sign-on in this check; public access, API scope and reuse terms remain unverified. **Request:** add a prominent Flagged for Review item (suggested F16), update Suggestion S07 and Question Q18, and do not implement automated scraping until authorized access/terms are documented.
- 2026-11-14 — **Request: narrow unsupported odds assertions.** `data/flags.csv` F07 and `data/questions.csv` Q08 say “The NFL does not publish betting lines / odds,” but cite the NFL injury page. The verified evidence supports only that no sportsbook price/provider is recorded in this repository and that the cited injury page is not an odds feed; it does not establish a league-wide absence. Please replace the absolute claim with the repository-scope finding and flag the provider as missing. The baseline repository commit is <https://github.com/karagemop466-tech/X2/commit/259c1c2534cf7d1b4f4f6b3ba65ed1ce651dcae1>.
- 2026-11-14 — **Request: remove unreviewed legal conclusions.** The main README says “Wagering on NFL games is restricted in Japan under Penal Code Arts. 185–187,” while S03 says full article text has not been reviewed line by line and F09/Q15 acknowledge that application to this product is not established. The e-Gov source is <https://laws.e-gov.go.jp/document?lawid=140AC0000000045>. Please use neutral language (“legal review required; no conclusion about this product”) until qualified counsel reviews the actual activity and jurisdictions. This audit is not legal advice.
- 2026-11-14 — **Request: correct post-merge publishing/status documentation.** GitHub Pages API currently reports `main` / (root), `status=built`, URL <https://karagemop466-tech.github.io/X2/>; the live URL was opened and served the dashboard. The root `index.html` forwards to `docs/index.html`. The README still describes `docs/` as the Pages source and says “Live site (after merge)”; R13 and R17 also retain pre-merge/pending wording. Please align these statements with the verified root-forwarder configuration and merged PRs #1–#3. GitHub's source documentation: <https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages>.
- 2026-11-14 — **Request: enforce the per-row source requirement.** In `scripts/build.py`, the loops for hypotheses, gates, suggestions and requirements call `check_official()` when an `evidence_url` is present but do not reject a blank URL. The CSVs contain blank evidence URLs (for example H03–H06, G1–G7 and several suggestions), so the blanket “every table row” statement is not met for those rows. Also, G1–G7/H03 refer to “S02” for results/player stats, while the current `data/sources.csv` defines S02 as the Buffalo Bills roster page. Please add correctly scoped official references or visibly flag rows without one, and correct the source-ID mismatch before claiming every row is sourced.
- 2026-11-14 — **Request: keep proposed validation thresholds explicitly unapproved.** The gates include values such as 300 bets/3+ seasons, p < 0.05, a 20% profit-share cap and four paper-trading weeks. They are labeled proposed/needs user decision, which is important; they are not NFL-verified facts or evidence-based thresholds in the source pack. Keep them out of “passed” criteria until a documented, predeclared rationale/decision exists.
- 2026-11-14 — **Request: preserve the manual-transcription limitation.** F10 correctly says 345 injury rows were transcribed and need spot-checking. A count/link check does not prove every field on every row was manually compared with the official report. Keep F10 visible and avoid describing every transcribed value as line-by-line verified until the actual row-level comparison is completed.
- 2026-11-14 — **Request: reconcile terms review status.** Q18 currently says NFL.com terms have not been reviewed; T11-S1 above records the Section 1.3 check. Update Q18/related flags to state the exact verified restriction and the unresolved question (authorization for intended reuse), without inferring legal scope beyond the text.
- 2026-11-14 — T11 handoff PR #5 (<https://github.com/karagemop466-tech/X2/pull/5>) was merged with `--merge` at 2026-11-14 02:55:48 UTC (merge commit `71e65aac61d6a3f2407d301a37c01076798648ac`). It changes only this coordination board; it does not change the published site or injury/strategy data. Follow-up correction requests remain with the owner of T09/T10 outputs.
- 2026-11-14 — After PR #5, Pages still reports legacy `main` / root publishing. A Pages deployment for commit `71e65aac` was created at 02:56:13 UTC and was `queued` at 02:56:15 UTC; the site continued to serve the previously built dashboard in the immediate live-page check. Since PR #5 changes no site files, no user-visible site update is expected from that deployment.
- T11 audit and handoff are complete. This session did not edit T09/T10-owned shared site/data/build files. The supplemental findings above are recommendations for the dashboard owner to consider in the existing Flagged for Review page and source register.
