# Validation Gates

Every strategy must pass a set of validation gates before it is accepted or ranked
on the leaderboard. Gates are pre-declared so that acceptance is auditable and not
tuned after the fact. The gates are the mechanism for **removing luck** and
ensuring strategies are selectively skill-based.

## Gates

{{TABLE: validationGates}}

## Why these gates remove luck

- **G-01 (CLV)** measures whether the price taken beat the closing price. A
  consistently positive CLV indicates genuine price-finding skill that survives
  short-term losing streaks; a consistently negative CLV means wins are variance.
  Source: [NFL Betting Math — Vig & CLV](https://nflsportsbettingstats.com/articles/nfl-betting-math-vig-clv/).
- **G-02 (sample size)** prevents a lucky short run from being read as skill.
- **G-03 (out-of-sample)** prevents overfitting: edge must hold on data the
  strategy has not been tuned on.
- **G-04 (correlation)** and **G-05 (leg independence)** prevent parlay/prop-combo
  strategies from manufacturing apparent edge from correlated or duplicate legs.
- **G-06 (data integrity)** enforces the no-hallucination rule at the signal level:
  no signal may use an inferred or fabricated input.
- **G-07 (selectivity)** enforces that strategies take fewer, higher-conviction bets.

## Acceptance rule

A strategy is eligible for the leaderboard only when **all** applicable gates pass
over its evaluation window. Flagged or unverified inputs block the signal (G-06);
unverified correlation values block multi-leg strategies (G-04) until computed.

## Demotion gate (live back to paper)

Entry gates decide whether a strategy may go live. A separate **demotion gate**
sends a live strategy back to paper. Rules D1–D7 are defined in
`data/demotion_gate.csv` and rendered on the Python Pages dashboard's
Market tables page (`docs/markets.html`): signal-interval collapse, multiplicity failure,
sample loss, source revision, lost provenance/legal clearance, and a closing-line
value test once a priced archive exists (G-06/G-08 linkages). Staking results can
neither promote nor rescue a strategy. All thresholds are **proposals awaiting
owner approval** (F17) and no strategy is live, so the gate is currently inert.
