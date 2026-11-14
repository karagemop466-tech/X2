# X2 — NFL Research & Lines Dashboard

Source-linked NFL research: injury tracking, depth exposure, strategy framework
(single bet / parlay / player props), validation gates, correlation, a strategy
leaderboard, open questions, requirements, a dedicated Suggestions area, and a
Flagged-for-Review register. Originate NFL lines and rank strategies on skill
(Closing Line Value), not luck.

**Live site:** https://karagemop466-tech.github.io/X2/

## What is here

This repository contains **two complementary build systems**, both source-linked:

| Path | Purpose |
|------|---------|
| `data/*.csv` | Source of truth (session e98c7ba0). Every verified value is a CSV row with an official link. |
| `data/*.json` | Structured data for the Node dashboard tables (session 09d7cc77). |
| `scripts/build.py` | Standard-library Python. Validates the CSV data, writes `docs/*.html` and `docs/data/*.json`, checks links. |
| `src/` | Node static-site generator (`build.mjs`), verifier (`verify.mjs`), and dashboard stylesheet. |
| `docs/` | The **live** GitHub Pages site (served from `main` / `docs` via a root `index.html` forward). |
| `COORDINATION.md` | Shared task board: claims, sources, verification notes, irregularities, and merge log for all sessions. |

## Commands

```bash
# Live-site build (Python, outputs to docs/)
python3 scripts/build.py

# Node dashboard build + verification (outputs to site/)
npm run build
npm run verify
```

## Rules used for every value

1. Only values confirmed on an official source are shown (NFL.com, NFL Operations,
   e-Gov, Japan Sport Council).
2. Anything that cannot be confirmed is left blank and listed on the
   **Flagged for review** page.
3. No values are inferred or estimated.
4. Each table row carries a link to the source it came from.

## Verification

- **Python build:** validates 345 injury rows, 14 games, every row linked to an
  official domain; all internal links resolve.
- **Node build:** `npm run verify` confirms every `data/*.json` row resolves to a
  known source and every internal link in `site/` resolves.

## Important

This project is research. It is not betting advice. Wagering laws vary by
jurisdiction and require legal review; **no legal conclusion about this product is
established**. See the flagged list (F-07 / F09).
