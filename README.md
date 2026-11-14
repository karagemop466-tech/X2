# X2 — NFL Lines

Collect, organize, and analyze NFL lines with a complete set of requirements.
Originate original NFL lines, research signal-generation strategies for single
bets, parlays, and player-prop combos, run a leaderboard that rewards top-performing
strategies, and track injuries and the deficiencies created when backups replace
starters on both offense and defense.

## What's in this repo

- **`COORDINATION.md`** — the shared task board for parallel sessions.
- **`docs/`** — narrative documentation (executive summary, requirements,
  questions & answers, suggestions, strategy research, validation gates,
  correlation, leaderboard, injuries & depth, data sources & verification,
  flagged for review).
- **`data/`** — structured data for every table (requirements, questions,
  suggestions, strategies, validation gates, correlations, leaderboard, injuries,
  depth deficiencies, flagged items, sources).
- **`src/`** — the static-site generator (`build.mjs`), the verifier
  (`verify.mjs`), and the dashboard stylesheet.
- **`.github/workflows/deploy.yml`** — builds and publishes the site to GitHub
  Pages on every push to `main`.

## Commands

```bash
npm run build    # build the static site into site/
npm run verify   # verify every table row's source + every internal link
```

## Verification rule

Every table row links to a source. Values that cannot be confirmed from an official
source are left blank and flagged on the **Flagged for Review** page — never
inferred or filled in. See `docs/09-data-sources-and-verification.md`.

## Site

The live dashboard is published to GitHub Pages. Navigation is organized by
category: Overview, Planning, Strategy, and Data.
