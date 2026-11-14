# Coordination Board — X2 (NFL Betting Analysis Site)

**Branch:** arena/6fac6aa4-x2
**Base commit:** 259c1c2534cf7d1b4f4f6b3ba65ed1ce651dcae1 (main)
**Sessions:** session-x2-01 (this branch), e98c7ba0-x2 (already merged to main via PR #1)
**Live site:** https://karagemop466-tech.github.io/X2/ (GitHub Pages, source = branch main, path "/")

## Merge resolution log (2026-11-14)

- Session e98c7ba0-x2 completed T01–T10 on branch arena/e98c7ba0-x2, opened PR #1, merged to main (main now at 0563aab). Their output lives under `data/`, `docs/`, `scripts/` plus `COORDINATION.md` and a rebuilt README.md.
- This session (arena/6fac6aa4-x2) built a root-level dashboard site (`index.html`, `pages/`, `assets/`, `data/*.json`) because GitHub Pages serves from the root "/" of main and main previously had no root `index.html`.
- `git merge origin/main` into this branch produced one conflict: `COORDINATION.md` (add/add, both sessions added it). Resolved by writing this unified board — neither session's work was discarded. Their board content is preserved below in the task table and claims log.
- Next: open PR #2 from this branch to main, merge, confirm GitHub Pages deploys the root site, record PR link + result here.

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

## Unified task list (both sessions)

| ID | Task | Status | Owner(s) | File Scope | Sources | Verification | Irregularities / flags |
|----|------|--------|----------|------------|---------|--------------|------------------------|
| T1 / T01 | Repo review — line-by-line audit | done | both | README.md, repo root | github.com/karagemop466-tech/X2 | repo was only README.md ("# X2"), one commit | none |
| T2 / T02 | Official NFL sources: injuries, standings | done | both | data/*.json, data/*.csv, docs/sources.md | nfl.com/injuries, nfl.com/standings | verified live 2026-11-14; standings 32/32 rows matched; injury Week-10 sample matched | theirs F05: CHI/DEN/PHI/TB not on Week-10 report (bye unconfirmed) |
| T3 / T04 | Decision framework: questions, info, answers | done | both | docs/decision-framework.md, pages/decisions.html, data/questions.csv | nfl.com | questions mapped to verified standings/injuries | gaps flagged (mine F-001..F-006) |
| T4 / T06 | Strategy lab: gates, hypotheses, leaderboard | done (framework); validation blocked | both | docs/strategies.md, pages/strategies.html, data/strategy_gates.csv, data/strategy_hypotheses.csv | nfl.com (inputs only) | lines/correlations/gates are original analysis, labeled "not official" | theirs F07/F08: no odds or historical results from official source |
| T5 | Injury & depth-chart model (starters vs 2nd/3rd/4th string) | done | both | docs/injury-depth.md, pages/injuries.html, data/injuries_*.* | nfl.com/injuries | injury rows verified line by line; replacement strings flagged unverified | theirs F06: starter/backup order not verifiable; mine F-002: coverage is a sample |
| T6 / T08 | Executive summary | done | both | docs/executive-summary.md, pages/executive-summary.html | nfl.com | figures cross-checked to official pages | none |
| T7 / T09 | Site build: landing + category subpages, dashboard tables | done | both | index.html, pages/, assets/ (this session); docs/, scripts/ (theirs) | nfl.com | all 9 root pages HTTP 200; 0 broken internal links; theirs: build.py passes, 345 rows, 14 games | none |
| T8 / T05 | Flagged-for-review + suggestions section | done / needs review | both | pages/flagged-review.html, pages/suggestions.html, data/suggestions.csv, data/flags.csv | nfl.com | F-001..F-006, IRR-001..IRR-003 listed; theirs F01–F14 listed | theirs F09: Japan wagering law needs legal advice; F11 roster slug; F12 Lamar timeline |
| T9 / T10-part | Integration verification: re-verify, build, no broken links | done | both | all | nfl.com | link checker 0 broken / 217 links; theirs: all row links official-domain, internal links resolve | captured above |
| T10 | PR #2 to main, merge, confirm Pages deploy, record result | in progress | session-x2-01 | repo | n/a | pending Pages deploy | none |

## Claims log
- e98c7ba0-x2: claimed T01–T10 on arena/e98c7ba0-x2; PR #1 merged to main; log entries 2026-11-14 (repo review, injury data, questions, strategy gates, exec summary, site build, integration check, PR #1 https://github.com/karagemop466-tech/X2/pull/1).
- session-x2-01: claimed T1–T10 on arena/6fac6aa4-x2; built root dashboard site; merged origin/main into this branch; resolved COORDINATION.md conflict without discarding either session's work.

## Handoffs
- none yet

## Verification record (T9, 2026-11-14)
- Standings: all 32 team rows matched https://www.nfl.com/standings/ (division, conference, league views) fetched 2026-11-14. Source linked on every row.
- Injuries: Week 10 sample matched https://www.nfl.com/injuries/league/2026/REG10 fetched 2026-11-14. Source linked on every row. Their session independently transcribed 345 injury rows / 28 teams / 14 games.
- Build: static HTML/CSS/JS. All 9 root pages HTTP 200 under local server. Internal link checker: 0 broken of 217 links (97 external). Fix applied: index.html asset paths corrected from ../assets/ to assets/.
- Their session: `python3 scripts/build.py` passes (345 injury rows, 14 games, 11 pages, all links resolve, all row links official-domain allow-list).

## Irregularities published for review (union)
See pages/flagged-review.html (this session) and docs/flagged.html (their session) — full list with source links. Key: depth charts not an official single NFL page (use nfl.com/teams/{team}); NFL publishes no official odds (all lines/signals original analysis); Japan wagering law needs legal advice (theirs F09); correlation values are placeholders pending 4+ weeks of results.
