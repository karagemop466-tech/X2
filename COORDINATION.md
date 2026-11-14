# COORDINATION.md — Shared Task Board

> This is the shared task board for the **X2 NFL Lines** project. Multiple agent
> sessions may work in this repository at the same time. **Read this file before
> starting any task.** It lists every task, its status, the owning session, and
> the files it touches. Keep scopes non-overlapping.

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
| `session-09d7cc77` | `arena/09d7cc77-x2` | Only session observed in this repository. Acts as the integration session as well. |

## Tasks

| ID | Task | Status | Owner | File scope | Sources / verification | Notes |
|---|---|---|---|---|---|---|
| T1 | Scaffold repo, coordination board, static-site build system, Pages workflow | `done` | `session-09d7cc77` | `COORDINATION.md`, `package.json`, `.gitignore`, `.github/**`, `src/**`, `README.md` | Build verified: `npm run build` emits 12 pages to `site/`; `npm run verify` passes. | Foundation complete. |
| T2 | Requirements, executive summary, questions & answers, suggestions | `done` | `session-09d7cc77` | `docs/00-*.md`, `docs/01-*.md`, `docs/02-*.md`, `docs/03-*.md`, `data/requirements.json`, `data/questions.json`, `data/suggestions.json` | Requirements grounded in user goals + official NFL sources; questions/answers flagged where no official source exists. | 28 requirements, 14 questions, 13 suggestions. |
| T3 | Strategy research, validation gates, correlation values, leaderboard | `done` | `session-09d7cc77` | `docs/04-*.md`, `docs/05-*.md`, `docs/06-*.md`, `docs/07-*.md`, `data/strategies.json`, `data/validation-gates.json`, `data/correlations.json`, `data/leaderboard.json` | Methodology grounded in cited CLV/market-efficiency sources. Correlation values intentionally blank + flagged (no official pre-computed values). | 9 strategies, 7 gates, 6 correlation pairs, 5 leaderboard entries. |
| T4 | Injury tracking & depth-chart deficiency system | `done` | `session-09d7cc77` | `docs/08-*.md`, `data/injuries.json`, `data/depth-deficiencies.json` | Injuries verified against NFL.com Week 10 injury report (fetched 2026-11-14); depth from Ourlads (fetched 2026-11-14). | 19 verified injury rows; 6 depth-deficiency rows (offense + defense). |
| T5 | Data sources & verification methodology, flagged-for-review register | `done` | `session-09d7cc77` | `docs/09-*.md`, `docs/10-*.md`, `data/sources.json`, `data/flagged.json` | All source URLs resolved/verified 2026-11-14 (official NFL.com, NFL Operations; third-party ESPN/Ourlads; aggregators; methodology refs). | 16 sources, 6 flagged items. |
| T6 | Build the GitHub Pages site (landing + category subpages, dashboard UI) | `done` | `session-09d7cc77` | `src/**`, `site/**` (generated) | `npm run verify`: 196 internal links checked, all resolve; every data row source resolves. | Clean dashboard; tables with per-row source links. |
| T7 | Integration, line-by-line re-verification, Pages deploy, PR + merge | `in progress` | `session-09d7cc77` | `main` (merge), `COORDINATION.md` | Re-verify combined data; confirm build + deploy. | Final integration session. |

## Requests between sessions

_No cross-session file requests logged. Only one session is active._

## Merge / conflict log

_No merge conflicts encountered._

## Handoff log

_No handoffs._

## Completion record

- **Build:** `npm run build` → 12 HTML pages written to `site/`.
- **Verify:** `npm run verify` → all 104 data-table rows resolve to a known source;
  196 internal links across 12 HTML files all resolve. **ALL CHECKS PASSED.**
- **Data verified from official/reputable sources (2026-11-14):** NFL.com standings,
  NFL.com injury report (Week 10, 2026), NFL.com team stats (offense/defense),
  NFL.com transactions (reserve list), NFL Operations rulebook, ESPN depth charts,
  Ourlads depth charts (DET/NE), VegasInsider/Covers/FOX Sports odds (aggregators),
  and CLV/market-efficiency methodology references.
- **Irregularities flagged (do not block merge):** F-01 Ben Brown position
  discrepancy (C vs RG); F-02 correlation values unverified (blank); F-03 live line
  values unverified (blank); F-04 live performance values unverified (blank);
  F-05 depth charts are third-party, not official; F-06 player-stats feed not
  confirmed. All published on the Flagged for Review page with source links.
