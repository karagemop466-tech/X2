# Strategy Leaderboard

A leaderboard competition designed to reward top-performing strategies. Once
eligible, strategies would be ranked by their out-of-sample **Closing Line Value
(CLV)** — the skill metric that reduces luck — and rewarded according to their
rank. A strategy appears with a rank only after it has passed all applicable
[validation gates](../validation-gates/). **No strategy is currently ranked or
rewarded**: no strategy has passed the gates, so the rank column is blank and the
reward column is disabled (see D10 and F-03/F-04).

## Ranking and rewards

{{TABLE: leaderboard}}

## Rules

1. **Ranking metric.** Strategies are ranked by mean out-of-sample CLV, not by win
   rate. Win rate is a variance-dominated secondary metric and is not the ranking
   basis.
2. **Eligibility.** A strategy is ranked only after passing gates G-01 (CLV), G-02
   (sample size), and G-03 (out-of-sample), plus any market-specific gates (G-04,
   G-05 for multi-leg; G-07 for selectivity). Until then its rank is blank.
3. **Rewards.** The intended design gives top-ranked strategies an allocation tier;
   the specific reward is a project decision recorded through the
   [Suggestions](../suggestions/) review and is **not approved or enabled** — legal,
   jurisdiction and data-rights gates (D01, D02, D09, D10) are open. It is not an
   official fact.
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

## Signal vs staking (kept apart)

Ranking uses **signal only** — forecast skill with its uncertainty interval and
multiplicity-adjusted q-value. The bet record (wins, hit rate, edge, ROI when
prices exist) is a **staking** record: it is displayed for transparency and can
never raise or lower a rank, so a lucky staking run cannot mask a bad signal.
Separately, the Python Pages dashboard publishes a measured signal/staking split
for the seven graded paper strategies and the proposed demotion gate; no reward
tier is offered anywhere until the qualification disagreement (F42) is resolved
and the owner decides on the tier labels (R36, F43). Nothing is paid.
