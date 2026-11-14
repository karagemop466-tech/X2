# Strategy Research

Research and development of signal-generation strategies for generating useful,
skill-based NFL signals. Strategies cover single bets, parlays, and player-prop
combos. **Every strategy must pass the validation gates** on the
[Validation Gates](../validation-gates/) page before it is accepted or ranked.

## Strategy catalog

{{TABLE: strategies}}

## Signal-generation principles

1. **Originate own lines.** Each strategy generates its own projection (projected
   spread, total, win probability, or player total) and compares it to the market
   line — it does not copy the market.
2. **Skill over luck.** Strategies are evaluated on **Closing Line Value (CLV)** —
   whether the price taken was better than the price at kickoff — not on short-term
   win rate. CLV is the established proxy for betting skill because it measures
   price-finding rather than outcome variance. Source:
   [Squawka — NFL Betting Strategy](https://www.squawka.com/us/nfl/strategy/).
3. **Selectivity.** Strategies take fewer, higher-conviction bets rather than betting
   every game. Selectivity reduces variance and focuses edge.
4. **Correlation-aware combos.** Parlay and prop-combo strategies combine legs only
   where computed correlation is bounded, so combined edge is not distorted by
   correlated outcomes. See [Correlation Values](../correlation/).

## Market types

- **Single bet** — point spread (side), over/under (total), and moneyline. The
  baseline building block and the cleanest place to measure skill.
- **Parlay** — multi-leg combinations. Require correlation handling (gates G-04,
  G-05) so legs are not double-counting the same risk.
- **Player prop** — player-specific totals (passing, rushing, receiving yards, etc.)
  and prop combos. Require a confirmed prop-line feed.

## Inputs used by the strategies

- Official team stats and standings (baseline performance).
- Official injury reports and reserve-list transactions (availability).
- Depth charts (which backup is replacing a starter — see
  [Injuries & Depth](../injuries-and-depth/)).
- Market lines (opening and closing) for CLV.

## Status note

All strategies are **designed** and documented. None is ranked on live performance
yet, because no live odds feed is connected and no live performance data exists.
Live performance values are left blank and flagged on the
[Strategy Leaderboard](../leaderboard/) page rather than inferred.
