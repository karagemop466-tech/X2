# Executive Summary

**Project:** X2 — NFL line generation, strategy validation, and decision support.

**Objective.** Collect, organize, and analyze NFL lines using a complete list of
requirements; originate original NFL lines; research and develop signal-generation
strategies for single bets, parlays, and player-prop combos; run a leaderboard that
rewards top-performing strategies; track injuries and the deficiencies created when
2nd/3rd/4th-string backups replace starters on both offense and defense; and present
everything on a clean GitHub Pages dashboard. No manual input is required.

## What has been built

- A **requirements register** capturing every requirement the system must satisfy,
  grouped by category (data collection, strategy, validation, injuries/depth,
  presentation, governance). See the [Requirements](../requirements/) page.
- A **decision framework** of open questions with the information needed and the
  current answer, plus a dedicated **Suggestions** area for review before any
  change is implemented. See [Questions & Answers](../questions-and-answers/) and
  [Suggestions](../suggestions/).
- A **strategy catalog** for single bets, parlays, and player props, each required
  to pass **validation gates**, with **correlation** handling and a **leaderboard**
  reward structure. See [Strategy Research](../strategy-research/),
  [Validation Gates](../validation-gates/), [Correlation Values](../correlation/),
  and [Strategy Leaderboard](../leaderboard/).
- An **injury & depth system** that records the official NFL.com injury status for
  every listed player and verifies starter/backup ordering against the clubs'
  official depth-chart pages where available (detroitlions.com, patriots.com —
  which self-label their charts "unofficial", flag F-05). Fields no official
  source confirms stay blank and flagged. See [Injuries & Depth](../injuries-and-depth/).
- A **source registry and verification method**, and a **Flagged for Review**
  register for irregularities and unverified items. See
  [Data Sources & Verification](../data-sources/) and
  [Flagged for Review](../flagged-for-review/).

## Key findings

1. **Skill is measured with Closing Line Value (CLV).** CLV — the difference between
   the price taken and the price at kickoff — is a widely used proxy for
   price-finding skill and is the basis for removing luck from the ranking; it is
   proposed by methodology references, not by the NFL. Win rate is treated as a
   secondary, variance-dominated metric. No method removes football variance or
   guarantees a result. Methodology references:
   [Squawka — NFL Betting Strategy](https://www.squawka.com/us/nfl/strategy/).
2. **Correlation must be computed, not assumed.** Multi-leg parlay and prop-combo
   strategies are only valid where leg correlations are bounded; correlation values
   are **not yet computed** and are therefore left blank and flagged, never inferred.
3. **Injuries are verified; depth replacements are partially sourced.** The official
   NFL.com Week 10 injury report verifies the availability statuses (for example,
   the Lions' center Cade Mays and cornerback D.J. Reed are ruled out; the Patriots
   list Rhamondre Stevenson Questionable and TreVeyon Henderson Out). Starter/
   backup ordering for those rows is verified against the clubs' official
   depth-chart pages, which self-label their charts "unofficial" (flag F-05);
   where no official chart confirms a value, the field stays blank and flagged.
   Any effect on a game (for example a third-string back becoming the primary
   carry) is a conditional scenario drawn from those charts, not a verified
   outcome. All rows carry per-row source links.
4. **No official odds feed is connected to this repository.** The NFL's own odds
   widgets use bookmaker-partner odds (NFL Support FAQ); no licensed feed or
   historical price archive is available here. Odds aggregators (VegasInsider,
   Covers, FOX Sports) are references but are not official; live line values are
   therefore left blank and flagged until a specific feed is connected.

## Verification status

Every table row on this site carries a link to its source. Values that cannot be
confirmed from an official source are **left blank and flagged as unverified** —
never inferred or filled in. Official sources used include NFL.com (standings,
injury report, team stats, transactions) and NFL Operations (rulebook). Third-party
depth charts (ESPN, Ourlads) and odds aggregators are labeled as such. On
2026-11-14 (task T13) third-party depth values were removed from the depth-table
data: backup names, string ranks, and the third-party LG label for Walter Rouse are
no longer published; official injury-report facts were retained and spot-checked.
The
current flagged items are listed on the [Flagged for Review](../flagged-for-review/)
page.

## Bottom line

The framework, methodology, and data model are complete and grounded in verified
sources. The remaining work before live decision-making is to connect the missing
data feeds (primary odds feed for CLV, confirmed player-stats endpoint, and a
depth-chart update monitor) — these are captured as suggestions and open questions
for review. No strategy is ranked on live performance until those feeds are in place
and every strategy has passed its validation gates.

## Market layer (published on the Python Pages dashboard)

The GitHub Pages site (`docs/` in this repository) now carries the market layer the
brief requires: a **price-snapshot store** with opening and closing fields for every
originated Week 11 market (side first, then total, then moneyline), **fair line /
market line / difference as separate columns**, a strict **signal-vs-staking split**
in the leaderboard, a proposed **demotion gate** (D1–D7) that returns a live
strategy to paper, and **replacement-depth tracking** to the 2nd/3rd/4th string
where an official-domain chart verifies it. Every price cell is blank and flagged:
no authorised, timestamped price source is connected (F07), so no ROI, CLV or
market return is computed anywhere.
