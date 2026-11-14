# Data Sources & Verification

## Source registry

All sources used on this site, with their type and how each was verified.

| Source | Type | URL | Verified |
| --- | --- | --- | --- |
| NFL.com — Standings | Official | https://www.nfl.com/standings/ | search-confirmed 2026-11-14 |
| NFL.com — Injury Report | Official | https://www.nfl.com/injuries/ | fetched 2026-11-14 |
| NFL.com — Team Stats, Offense | Official | https://www.nfl.com/stats/team-stats/ | search-confirmed 2026-11-14 |
| NFL.com — Team Stats, Defense | Official | https://www.nfl.com/stats/team-stats/defense/passing/2026/reg/all | search-confirmed 2026-11-14 |
| NFL.com — Transactions, Reserve List | Official | https://www.nfl.com/transactions/league/reserve-list/2026/11 | search-confirmed 2026-11-14 |
| NFL Operations — 2026 Rulebook | Official | https://operations.nfl.com/rules-officiating/2026-nfl-rulebook | search-confirmed 2026-11-14 |
| ESPN — NFL Depth Charts | Reputable third-party | https://www.espn.com/nfl/depthcharts | fetched 2026-11-14 |
| Ourlads — NFL Depth Charts | Reputable third-party | https://www.ourlads.com/nfldepthcharts/depthcharts.aspx | fetched 2026-11-14 |
| VegasInsider — NFL Odds | Odds aggregator | https://www.vegasinsider.com/nfl/ | fetched 2026-11-14 |
| Covers — NFL Odds | Odds aggregator | https://www.covers.com/nfl/ | fetched 2026-11-14 |
| FOX Sports — NFL Odds | Odds aggregator | https://www.foxsports.com/nfl/odds | fetched 2026-11-14 |
| Squawka — NFL Betting Strategy (CLV) | Methodology reference | https://www.squawka.com/us/nfl/strategy/ | search-confirmed 2026-11-14 |
| OddsIndex — Closing Line Value | Methodology reference | https://oddsindex.com/guides/closing-line-value-guide | search-confirmed 2026-11-14 |
| NFL Betting Math — Vig & CLV | Methodology reference | https://nflsportsbettingstats.com/articles/nfl-betting-math-vig-clv/ | search-confirmed 2026-11-14 |

## Source classification

- **Official** — NFL.com and NFL Operations. These are the primary sources for
  standings, injuries, team stats, transactions, and the rulebook.
- **Reputable third-party** — ESPN and Ourlads. Consulted only as leads; their values
  are never published in the tables. No league-level official depth chart exists
  (the NFL.com team depth-chart URLs return 404), and the depth ordering shown on
  the Node pages comes from the clubs' official websites' weekly charts
  (detroitlions.com, patriots.com), which self-label "unofficial" (Node flag F-05).
  Labeled as non-official.
- **Odds aggregator** — VegasInsider, Covers, FOX Sports. These aggregate odds set
  by individual regulated sportsbooks. **There is no single official odds source.**
  They are used as references only; live line values are left blank and flagged
  until a specific sportsbook feed is connected.
- **Methodology reference** — Squawka, OddsIndex, NFL Betting Math. Used to ground
  the CLV, market-efficiency, and validation methodology. These are not official
  NFL sources and are labeled as methodology.

## Verification method

1. **Every table row carries a source link.** The table renderer enforces a Source
   column on every data table.
2. **Unverified values are blank and flagged.** If a value cannot be confirmed from
   an official source, the cell is left empty (shown as —) and the item is listed
   on the [Flagged for Review](../flagged-for-review/) page. Values are never
   inferred or filled in.
3. **Official-source preference.** Facts that exist as official NFL data (standings,
   injuries, team stats, transactions) cite the official NFL.com / NFL Operations
   pages. Facts that are methodology cite methodology references and are labeled.
4. **No fabricated numbers.** Correlation values, live line values, and live
   performance values are all left blank where no official/computable source is
   connected, and are flagged.

## Automated check

The build includes a verification step (`npm run verify`) that scans the generated
site for internal links and confirms every data row resolves to a known source.
