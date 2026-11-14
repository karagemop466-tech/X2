# Coordination Board — X2 (NFL Betting Analysis Site)

**Branch:** arena/6fac6aa4-x2
**Base commit:** 259c1c2534cf7d1b4f4f6b3ba65ed1ce651dcae1 (main)
**Session ID:** session-x2-01 (single active session; all tasks claimed here unless handoff occurs)

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
| T1 | Repo review — line-by-line audit of existing files | claimed | session-x2-01 | repo root (README.md, COORDINATION.md) | n/a | n/a | none (empty repo) |
| T2 | Research official NFL sources (injuries, standings, roster/depth charts) | in progress | session-x2-01 | docs/sources.md | nfl.com, espn.com | in progress | none yet |
| T3 | Build decision framework: questions, info, answers needed before decisions | unclaimed | — | docs/decision-framework.md | TBD | TBD | TBD |
| T4 | Build signal/strategy research (NFL lines, parlays, player props, correlation, validation gates) | unclaimed | — | docs/strategies.md | TBD | TBD | TBD |
| T5 | Injury & depth-chart tracking model (starters vs backups, offense/defense) | unclaimed | — | docs/injury-depth.md | TBD | TBD | TBD |
| T6 | Executive summary | unclaimed | — | docs/executive-summary.md | TBD | TBD | TBD |
| T7 | Build GitHub Pages site (landing page + category subpages, dashboard tables) | unclaimed | — | index.html, pages/*.html, assets/, _config.yml | TBD | TBD | TBD |
| T8 | Flagged-for-review page (unverified items + irregularities) | unclaimed | — | pages/flagged-review.html | TBD | TBD | TBD |
| T9 | Final integration: merge branches, re-verify line by line, confirm build/no broken links | unclaimed | — | all | TBD | TBD | TBD |
| T10 | PR to main, merge, confirm GitHub Pages deploy, record PR link & result | unclaimed | — | repo | TBD | TBD | TBD |

## Claims Log
- session-x2-01 claims T1 (repo review), T2 (official sources research) — started at 2026-11-14.

## Handoffs
- none yet
