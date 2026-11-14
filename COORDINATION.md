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
| `7678436e` | `arena/7678436e-x2` | Source-link/validation follow-up to the live Python dashboard; merged to `main` as PR #7 (cf2d454). F16 terms/data-rights, F17 numeric-cutoff, and F18 Node third-party-depth review flags remain explicit. |
| `30beeb55` | `arena/30beeb55-x2` | Session 30beeb55: claimed T13, T14, T15 on 2026-11-14. Branch from `main` @ `cf2d454`. Merged to `main` via PR #8 (merge commit e33a7f5). |
| `7c9eb69a` | `arena/7c9eb69a-x2` | **Current session.** Independent row-by-row re-verification of the Week 10 snapshot, plus the Decision path, Verification record and suggestion review matrix (T17). Merged `origin/main` (PR #8) and resolved flag/task ID collisions without discarding 30beeb55's work. Performs the final integration step. |
| `45a0ec8c` | `arena/45a0ec8c-x2` | Session 45a0ec8c. Claimed T18 on 2026-11-14 after finding T13–T15 already done on `main` (30beeb55, PR #8). Adds evidence and new flags F23–F29 only; does not redo T13–T15. |

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
| T12 | Source-link completeness and research-gate remediation for the Python Pages site | done (merged: PR #7, merge commit cf2d454) | 7678436e | README.md, data/questions.csv, data/requirements.csv, data/suggestions.csv, data/strategy_gates.csv, data/strategy_hypotheses.csv, data/sources.csv, data/flags.csv, scripts/build.py, generated legacy `docs/*.html` and `docs/data/*.json`, COORDINATION.md | NFL, Government of Japan/NPA, NIST; first-party GitHub records for project facts | Repaired 41 source-less table rows; universal builder checks; F16 terms/data rights, F17 thresholds, F18 review request. |
| T13 | Review third-party depth values in the separate Node dashboard against official-only requirement | done (30beeb55) | 30beeb55 | `data/depth-deficiencies.json`, `data/flagged.json` (F-01, F-05), `docs/08-injuries-and-depth.md` (Node source) | NFL.com Week 10 injury report (official); NFL.com depth-chart URL checked (404) | Rows limited to official NFL.com injury status; Ourlads/ESPN ordering, backup names and deficiency text removed from the table (unverified). Python F18 updated by the integration step. Needs reviewer confirmation of the blank-field approach (F-05). |
| T14 | Jurisdiction gap: user location is the Netherlands (NL); repo flags only Japan (F09) | needs review | 30beeb55 | `research/nl-legal-review.md` (new); `data/flags.csv` F19 (integration); `README.md` note | Wet op de kansspelen art. 1 (wetten.overheid.nl/BWBR0002469/2025-02-12); Kamerstuk 33996 nr. 3; Kansspelautoriteit Kansspelwijzer | Flag only. No legal conclusion stated. Dutch-law review needed before any wagering, referral, reward or leaderboard use by a person in NL. Published as F19 on Flagged for Review. |
| T15 | Spot-check Week 10 injury CSV rows against the NFL.com official injury report (F10) | done | 30beeb55 | Read-only check; F10 status updated in `data/flags.csv` (integration) | NFL.com Week 10 injury report (https://www.nfl.com/injuries/) | All 345 CSV rows compared with all 14 games: no discrepancies. Manual read, not an automated diff. Snapshot is point-in-time. |
| T16 | Integration: merge 30beeb55 branch into main, rebuild both sites, verify, PR, merge, confirm Pages | done | 30beeb55 | `COORDINATION.md`, `data/flags.csv` (F10, F18, F19), `README.md`, `scripts/build.py` (allow-list: wetten.overheid.nl, www.kansspelautoriteit.nl), generated `docs/` | Sources as listed for T13, T14, T15 | PR #8 merged to `main` (merge commit e33a7f5). |
| T17 | Independent second-pass re-verification of the Week 10 snapshot; Decision path, Verification record and suggestion review matrix | done | 7c9eb69a | data/decision-chain.csv, data/suggestion_review.csv, data/flags.csv (F20–F22), data/requirements.csv, scripts/build.py, generated `docs/*.html` and `docs/data/*.json`, COORDINATION.md | NFL.com injury report, Week 10 schedule, game center, standings, team roster page (404 depth-chart test); NIST and Government of Japan sources via suggestion_review evidence | **Second independent pass**: all 345 injury rows and all 14 game headers matched the live page on 2026-11-14, performed separately from 30beeb55's T15 check. Flags F20 (verification pass), F21 (news snapshot drift), F22 (verified Thursday score not published). Python build 13 pages; Node build/verify passing. |
| T18 | Designation and identity cross-check against NFL.com official status article and roundups (F04/F11/F12 evidence; new F23–F29) | done (evidence); status changes requested to integration | 45a0ec8c | data/flags.csv (F23–F29 appended), data/sources.csv (SRC-25–SRC-29 appended), generated docs/flagged.html, docs/data/flags.json, docs/sources.html, docs/data/sources.json | NFL.com injury report and status article (SRC-27), roundups (SRC-28, SRC-29), policy release (SRC-25), player page (SRC-26) | 157 of 160 designations match. Four conflicts (Walker, Mallory, Freiermuth, Key) logged as F26; Jackson absent (F27); blank injuries (F28); label mismatch (F29). Table values NOT changed. F04/F11/F12 status changes requested to integration. |
| T19 | Integration: PR from arena/45a0ec8c-x2 to main for T18 additive outputs; merge; confirm Pages | in progress | 45a0ec8c | COORDINATION.md, data/flags.csv, data/sources.csv, docs/ (generated) | — | Merge result and PR link to be recorded here after merge |

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

**Session 30beeb55 (T13, T14, T15, T16):**
- T15 (F10): Read the NFL.com Week 10 injury report (`https://www.nfl.com/injuries/`, 8 chunks, read 2026-11-14) and compared the 345 rows of `data/injuries_week10_2026.csv` with it, game by game (all 14 games). Fields: player, position, injury, practice status, game status, plus per-game row counts (they sum to 345). No discrepancies found. This was a manual read, not an automated diff. Programmatic checks: one source URL (`https://www.nfl.com/injuries/`) on all 345 rows, no duplicate game/player pairs, all player URLs well-formed. The Hummel link slug (`jake-hummel`) is the one NFL.com itself uses.
- T13: Checked the NFL.com Detroit Lions depth-chart URL (`https://www.nfl.com/teams/detroit-lions/depth-chart`): returned a 404 page on 2026-11-14. Official injury statuses for the seven Node rows were confirmed on the NFL.com report (Mays C Out; D.J. Reed CB Out; St. Brown WR Questionable; Stevenson RB Questionable; Henderson RB Out; Walter Rouse T Questionable; Ben Brown C Out). Depth ordering and backup names could not be verified and were removed from the table. `npm run build` and `npm run verify` pass (194 internal links).
- T14: Read the current consolidated Wok at `https://wetten.overheid.nl/BWBR0002469/2025-02-12` (geldend 12-02-2025 t/m heden, retrieved 2026-11-14), art. 1 lid 1 a–d. Read Kamerstuk 33996 nr. 3 (`https://zoek.officielebekendmakingen.nl/kst-33996-3.html`), section I.1. Read the Kansspelautoriteit pages `https://kansspelautoriteit.nl/` and `https://www.kansspelautoriteit.nl/kansspelwijzer`. Secondary-site claims about tax and enforcement were NOT used.
- Board reconciliation: T12 status changed from "in progress" to done because PR #7 (`cf2d454`) is merged on `main`.

**Session 7c9eb69a (T17) — independent second pass:**
- Re-read the official NFL Week 10 injury report in full (8 chunks, https://www.nfl.com/injuries/) on 2026-11-14 and recounted players per team section independently of `data/injuries_week10_2026.csv`. Independent recount: 345 rows across 28 teams, equal to the stored row count.
- Compared every player name, position, injury text, practice status and game status for all 28 team sections against the stored CSV. **No discrepancies found** (F20). This was performed separately from 30beeb55's T15 check and is therefore a genuine second independent reviewer pass, which is the strongest control the manual-transcription limitation (F10) allows.
- Compared all 14 game headers (day, kickoff time, broadcaster, both listed records) with `data/games_week10_2026.csv`. All matched.
- Read the official Week 10 schedule: confirmed the bye teams CHI/DEN/PHI/TB, the 14 game titles, and that **the injury report lists the away team first in every game**.
- Confirmed the Thursday result Commanders 24 - Giants 21 final on the official schedule and game center (F22); it is not published because the games table has no result column.
- Tested the conventional official depth-chart URL `https://www.nfl.com/teams/buffalo-bills/depth-chart`: returns **HTTP 404**. This corroborates 30beeb55's Detroit check and independently supports F06; starter/backup order stays blank.
- Compared the stored news list with the live page news section: two stored headlines are no longer shown (F21, snapshot drift). Injury rows unaffected.
- Cross-checked Week 10 listed records against the official standings page; matches for the teams checked.
- Added `data/decision-chain.csv` (D01-D10 ordered gates with owner and required answer), `data/suggestion_review.csv` (per-suggestion recommended path, trade-off and blocking gate), and new site pages `decision-path.html` and `verification.html`.
- `python3 scripts/build.py` passes: 13 pages, 345 injury rows, 28 teams, 61 depth rows, link and row-source checks passed. `npm run build` and `npm run verify` pass.

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

**Session 30beeb55 flags (integration: published as F-rows in `data/flags.csv`):**
- F19 (new): Netherlands jurisdiction not reviewed. The project owner is located in NL; the register flagged only Japan. Dutch-law review needed before any wagering, referral, reward or leaderboard use. Not a legal conclusion. See `research/nl-legal-review.md`.
- F10 (updated): all 345 injury rows checked against the NFL.com Week 10 page on 2026-11-14; no discrepancies found (manual read).
- F18 (updated): Node depth-deficiency rows were reduced to the official injury status; Ourlads ordering is removed (T13).
- Node F-01 / F-05 updated: F-01 now cites only the official C position; F-05 records the NFL.com depth-chart 404.
- Official depth chart still not found (the NFL.com depth-chart URL is a 404). Starter/backup ordering stays blank across all sessions until an official source is identified.
- The live Pages site is built from `docs/` by the Python builder. The Node output in `site/` is gitignored and is not published.

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

**T13 request — resolved (30beeb55).** Node depth rows now carry only official NFL.com injury status. F18 was updated by the integration step to say so.

**T14 request (30beeb55 → integration):** added F19 (Netherlands) to `data/flags.csv`; added `wetten.overheid.nl` and `www.kansspelautoriteit.nl` to the builder's official-host allow-list; added a README note.

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
- **2026-11-14 · 30beeb55 · claims and integration.** Claimed T13, T14 and T15 (and added T16 integration) on `arena/30beeb55-x2` from `main` @ `cf2d454`. No handoff from another session. Results are in the Verification and Irregularities sections above. The integration session (30beeb55) updated only F10, F18 and F19 in `data/flags.csv`, the allow-list in `scripts/build.py`, the README note, and regenerated `docs/`.

## Merge / conflict log — session 7c9eb69a

- **2026-11-14 · session 7c9eb69a · merge conflict on PR #9.** While merging `origin/main` into `arena/7c9eb69a-x2`, `main` had advanced with session 30beeb55's work (PR #8, merge commit `e33a7f5`). Conflicts in `COORDINATION.md`, `data/flags.csv`, `docs/data/flags.json` and `docs/flagged.html`.
  **Root cause:** both sessions independently claimed the task ID **T14** and the flag ID **F19**.
  **Resolution (nothing discarded):**
  - 30beeb55 keeps **T14** (Netherlands jurisdiction review) and **F19** (NL jurisdiction gap), since their work was merged to `main` first.
  - 7c9eb69a's task is recorded as **T17**, and its three new flags were renumbered **F20** (verification pass), **F21** (news snapshot drift) and **F22** (verified Thursday score not published). All references in `data/flags.csv`, `scripts/build.py`, generated `docs/` and `README.md` were updated to match.
  - `scripts/build.py` merged automatically: 30beeb55's Netherlands allow-list hosts (`wetten.overheid.nl`, `www.kansspelautoriteit.nl`) are retained alongside 7c9eb69a's `decision-chain` and `suggestion_review` inputs and the `decision-path.html` and `verification.html` pages.
  - F10 was updated to record **two independent manual verification passes** (30beeb55 T15 and 7c9eb69a T17), both finding no discrepancies.
  - `data/flags.csv` was rewritten with LF endings to clear a `git diff --check` trailing-whitespace warning.
  - Generated HTML/JSON files were regenerated by `scripts/build.py` rather than hand-merged.
- **Post-merge verification:** `python3 scripts/build.py` (13 pages, 345 injury rows, 28 teams, 61 depth rows), `npm run build` (12 pages), `npm run verify` (194 internal links, all JSON rows resolve), `python3 -m py_compile`, and `git diff --check` all pass. Independent audit of generated HTML: 611 table rows, 0 without an allow-listed official source, 0 broken internal links, 0 non-allow-listed external links.

## PR and deployment record — session 7c9eb69a

| Item | Result |
|---|---|
| PR #9 | https://github.com/karagemop466-tech/X2/pull/9 — **MERGED** (merge commit `e8ac780`, 2026-11-14T18:09:30Z). T17 verification pass, Decision path, Verification record, suggestion review matrix, flags F20–F22. Included resolution of the T14/F19 ID collision with session 30beeb55. |
| PR #10 | https://github.com/karagemop466-tech/X2/pull/10 — **MERGED** (merge commit `2140bce`). Wording follow-up aligning the Verification page with the two-pass F10 result. |
| GitHub Pages | Deployed from `main` / (root). `gh api repos/karagemop466-tech/X2/pages` reported `status: built` after both merges; the build for `e8ac780` completed at 2026-11-14T18:09:32Z and the build for `2140bce` also reached `built`. |
| Live site check | `https://karagemop466-tech.github.io/X2/docs/decision-path.html` and `/docs/verification.html` served the new pages with the renumbered flags **F20/F21/F22** and the correct two-pass F10 wording. `F19` on the live Flagged page is session 30beeb55's Netherlands jurisdiction item, preserved. |
| Checks at merge time | `python3 scripts/build.py` 13 pages / 345 injury rows / 61 depth rows / link + row-source checks passed · `npm run build` 12 pages · `npm run verify` all checks passed · `python3 -m py_compile` clean · `git diff --check` clean · independent audit 611 table rows with 0 missing allow-listed sources, 0 broken internal links, 0 non-allow-listed external links. |

**Open items handed to the next session:** F01–F09, F11–F22 remain in the register. The blocking gates are D01 (data rights), D02 (odds feed), D03 (history), D04 (official depth source) and D09 (Netherlands legal review, F19). No value in this repository is an estimate, and no strategy has passed validation.

## Session 45a0ec8c — collision record and cross-scope requests (2026-11-14)

- **Collision.** This session originally claimed T13, T14 and T15 from base `cf2d454`. `main` had already completed T13, T14 and T15 under session 30beeb55 (PR #8, merge e33a7f5). The claim was pushed to the branch and then rebased. The rebase conflicted with `main`. Our T13/T14/T15 work was dropped, and our duplicate injury-row file was not kept. Main's versions of `data/depth-deficiencies.json`, `data/flagged.json`, `docs/08-injuries-and-depth.md`, `COORDINATION.md`, `scripts/build.py` and the generated pages were kept.
- **Kept from this session (T18).** Evidence for F04, F11 and F12 (SRC-25 to SRC-29); new flags F23–F29. F26 records four designation conflicts between the injury table and NFL.com's Week 10 status article/roundups.
- **Cross-scope requests (not edited by 45a0ec8c).**
  1. `docs/09-data-sources-and-verification.md` (shared site doc) still lists "ESPN and Ourlads" as "Reputable third-party … used for depth charts". The Node depth table no longer uses Ourlads values (T13, 30beeb55). Request: integration to reword that bullet to say third-party sources are not published as values.
  2. `data/flags.csv` F04, F11, F12: integration to change status using F23, F24 and F25 evidence (SRC-25, SRC-26, SRC-28). This session did not change those rows.
  3. `data/injuries_week10_2026.csv`: request to confirm or correct Walker, Mallory, Freiermuth and Key designations (F26), add or record absence for Lamar Jackson (F27), and fill or keep blank the four Injury fields (F28). Only official confirmed values may be entered.
- **Not done.** The live Pages check remains unverified: the sandbox curl to `karagemop466-tech.github.io/X2/` failed with SSL_ERROR_SYSCALL. Retry after integration.
- **Integration (T19).** Claimed by 45a0ec8c on 2026-11-14 because no integration claim was open. It covers only the T18 additive changes to shared outputs (`data/flags.csv`, `data/sources.csv`, generated `docs/` pages). Integration is limited to these files; nothing in T13 or T17 is edited.
