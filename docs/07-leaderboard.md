# Strategy Leaderboard

A leaderboard competition that rewards top-performing strategies. Strategies are
ranked by their out-of-sample **Closing Line Value (CLV)** — the skill metric that
removes luck — and rewarded according to their rank. A strategy appears on the
leaderboard only after it has passed all applicable [validation gates](../validation-gates/).

## Ranking and rewards

{{TABLE: leaderboard}}

## Rules

1. **Ranking metric.** Strategies are ranked by mean out-of-sample CLV, not by win
   rate. Win rate is a variance-dominated secondary metric and is not the ranking
   basis.
2. **Eligibility.** A strategy is ranked only after passing gates G-01 (CLV), G-02
   (sample size), and G-03 (out-of-sample), plus any market-specific gates (G-04,
   G-05 for multi-leg; G-07 for selectivity).
3. **Rewards.** Top-ranked strategies receive the primary allocation tier; the
   specific reward values are a project decision recorded through the
   [Suggestions](../suggestions/) review, not an official fact.
4. **No live data yet.** Because no live odds feed is connected, all `value` cells
   are left blank and flagged as unverified. No strategy is ranked on performance
   until live data is available and gates pass.

## Why CLV-based ranking removes luck

CLV measures whether the price a strategy took was better than the price at
kickoff. A bettor who consistently beats the closing line will be in profit over a
large enough sample even with a hit rate barely above 50%; a bettor who consistently
takes worse prices than close will lose even with a 55% hit rate. Ranking on CLV
captures the underlying skill of price-finding rather than the variance of game
outcomes. Sources:
[Squawka](https://www.squawka.com/us/nfl/strategy/) and
[NFL Betting Math — Vig & CLV](https://nflsportsbettingstats.com/articles/nfl-betting-math-vig-clv/).
