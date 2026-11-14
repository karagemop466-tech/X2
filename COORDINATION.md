# Coordination Board — X2 (NFL Betting Analysis Site)

**Branch:** arena/6fac6aa4-x2
**Base commit:** 259c1c2534cf7d1b4f4f6b3ba65ed1ce651dcae1 (main)
**Session ID:** session-x2-01 (single active session; all tasks claimed here)

## Rules
- Each task is claimed by writing the session ID and file scope; commit and push the claim immediately.
- Each session works on its own branch/worktree named `session-<id>/<task>` and edits only files in its claimed scope.
- If a task requires changing a file owned by another session, log the request here instead of editing it.
- Small, frequent commits; run `git pull --rebase` before every push.
- On merge conflict: stop, resolve without discarding other session's work, log what happened.
- When finished: record sources, verification performed, irregularities here; mark done.
- Never mark verified without checking against an official source; link that source.
- Shared outputs (table data, index, navigation) changed only by the final integration session once all other tasks are done.
- If a session crashes or its claim is >60 minutes old with no commits, any session may take over and note the handoff.

## Task List

| ID | Task | Status | Owner | File Scope | Sources | Verification | Irregularities |
|----|------|--------|-------|------------|---------|--------------|----------------|
| T1 | Repo review — line-by-line audit of existing files | done | session-x2-01 | repo root (README.md) | n/a | verified: repo contained only README.md ("# X2"), one commit | none |
| T2 | Research official NFL sources (injuries, standings, rosters/depth charts) | done | session-x2-01 | docs/sources.md | nfl.com/injuries, nfl.com/standings, nfl.com/teams | verified live 2026-11-14: nfl.com/injuries/league/2026/REG10 and nfl.com/standings/ return 2026 Week 10 data; all 32 team rows matched | Depth charts not published as a single official league page; team roster pages at nfl.com/teams/{team} used as official source; third-party depth charts flagged |
| T3 | Decision framework: questions, info, answers needed before decisions | done | session-x2-01 | docs/decision-framework.md, pages/decisions.md | nfl.com | verified against official standings/injuries where cited | gaps flagged (F-001..F-006) |
| T4 | Signal/strategy research (NFL lines, parlays, player props, correlation, validation gates) | done | session-x2-01 | docs/strategies.md, pages/strategies.html | nfl.com (inputs only) | inputs verified; lines/correlations/gates are original analysis, labeled "analysis — not official source" | correlation values placeholders (F-003) |
| T5 | Injury & depth-chart tracking model (starters vs backups, offense/defense) | done | session-x2-01 | docs/injury-depth.md, pages/injuries.html | nfl.com/injuries/league/2026/REG10 | injury rows verified line by line; replacement strings flagged unverified | incomplete coverage sample (F-002) |
| T6 | Executive summary | done | session-x2-01 | docs/executive-summary.md, pages/executive-summary.html | nfl.com | standings/injury figures cross-checked to official pages | none |
| T7 | Build GitHub Pages site (landing page + category subpages, dashboard tables) | done | session-x2-01 | index.html, pages/*.html, assets/, data/ | nfl.com | all 9 pages HTTP 200; 0 broken internal links; every table row carries official source link | none |
| T8 | Flagged-for-review page (unverified items + irregularities) | done | session-x2-01 | pages/flagged-review.html | nfl.com | F-001..F-006, IRR-001..IRR-003 listed with source links | listed by design |
| T9 | Final integration: merge branches, re-verify line by line, confirm build/no broken links | done | session-x2-01 | all | nfl.com | re-verified: standings 32/32 rows vs nfl.com/standings; injuries vs nfl.com/injuries/league/2026/REG10; link check 0 broken; site builds (static HTML) | captured in T8 |
| T10 | PR to main, merge, confirm GitHub Pages deploy, record PR link & result | in progress | session-x2-01 | repo | n/a | pending Pages deploy | none |

## Claims Log
- session-x2-01 claims T1–T10 — started 2026-11-14; single session performing integration as well.

## Handoffs
- none yet

## Verification record (T9, 2026-11-14)
- Standings: all 32 team rows matched https://www.nfl.com/standings/ (division, conference, league views) fetched 2026-11-14. Source linked on every row.
- Injuries: Week 10 sample matched https://www.nfl.com/injuries/league/2026/REG10 fetched 2026-11-14. Source linked on every row.
- Build: static HTML/CSS/JS; all 9 pages HTTP 200 under local server; internal link checker: 0 broken of 217 links (97 external).
- Fix applied during verification: index.html asset paths corrected from ../assets/ to assets/.
