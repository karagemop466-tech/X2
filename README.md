# X2 — NFL Research Dashboard

Source-linked NFL research: injury tracking, depth exposure, strategy framework, open questions, suggestions, and flagged items.

**Live site (after merge):** https://karagemop466-tech.github.io/X2/

## What is here

| Path | Purpose |
|------|---------|
| `data/*.csv` | Source of truth. Every verified value is in a CSV row with an official link. |
| `scripts/build.py` | Standard-library Python. Validates data, writes `docs/*.html` and `docs/data/*.json`, checks links. |
| `docs/` | The GitHub Pages site (served from `main` / `docs`). |
| `COORDINATION.md` | Shared task board, claims, sources, verification notes, irregularities, and log. |

## Rules used for every value

1. Only values confirmed on an official source are shown (NFL.com, e-Gov, Japan Sport Council).
2. Anything that cannot be confirmed is left blank and listed on the **Flagged for review** page.
3. No values are inferred or estimated.
4. Each table row carries a link to the source it came from.

## Rebuild

```bash
python3 scripts/build.py
```

The build exits non-zero if a data row lacks an official link, a link is broken, or an external link is not on the allow-list.

## Data snapshot

- Injury report: NFL.com Week 10, 2026 season, read 2026-11-14 (UTC). 345 rows, 28 teams, 14 games.
- No odds, historical results, or official depth charts have been collected yet. See the flagged list.

## Important

This project is research. It is not betting advice. Wagering on NFL games is restricted in Japan under Penal Code Arts. 185–187. Get legal advice before any real-money activity (Flag F09).
