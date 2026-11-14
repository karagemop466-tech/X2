# Signal & Strategy Research — Originating NFL Lines

**Status:** Analysis work product — NOT official NFL data.
**Source note:** All team-level inputs use verified official NFL data (nfl.com/standings, nfl.com/injuries). Lines, signals, correlations, gates, and leaderboard rules are original analysis and must be validated before use.

## Goal

Originate our own NFL lines and generate useful, selectively skill-based betting signals across single bets, parlays, and player-prop combinations, run as a leaderboard competition with rewards for top-performing strategies. Luck is removed by construction: correlation gates, skill-vs-luck filters, and validation gates must all pass before a strategy is admitted.

## 1. Line origination method (proposal)

Inputs (official, verified):
- Team win rate (W/(W+L+T)) from standings
- Points differential (PF − PA) per game
- Home/road splits, division/conference splits
- Injury adjustments: starter Out/Questionable at high-impact positions (QB, OT, edge rusher, CB) shifts team rating

Opening line = (away rating − home rating) + home-field advantage (~2.5 points, to be calibrated).
Our line vs. market line = edge. Bet when edge exceeds threshold (gate G1).

## 2. Signal types in scope

| Signal type | Description | Legs | Correlation gate applies? |
|-------------|-------------|------|---------------------------|
| Single bet — moneyline | Pick winner | 1 | No (single leg) |
| Single bet — spread | Cover the spread | 1 | No |
| Single bet — total | Over/under points | 1 | No |
| Parlay | 2–3 single bets combined | 2–3 | Yes — every leg pair |
| Player-prop combination | QB pass / RB rush / WR receive yards props | 1–3 | Yes — cross-player correlation |

## 3. Correlation values (to be computed — placeholder)

Correlation between legs must be estimated from historical results. Current values are placeholders and are flagged unverified until computed from a 4-week game log.

| Leg pair | Estimated correlation | Status | Action |
|----------|----------------------|--------|--------|
| Team moneyline + team spread (same game) | high (~0.85) | placeholder | Exclude from same parlay |
| Team total + game total (same game) | high (~0.70) | placeholder | Exclude from same parlay |
| QB pass yards + team pass yards (same team) | medium-high (~0.60) | placeholder | Restrict (max one of pair per parlay) |
| WR receive yards + QB pass yards (same team) | medium (~0.50) | placeholder | Restrict |
| RB rush yards + team rush attempts | medium (~0.45) | placeholder | Restrict |
| Two different games | ~0.00 | placeholder | Allowed |

Rule: no parlay may contain a leg pair with correlation ≥ 0.30. This removes correlated (luck-driven) stacks and keeps parlays skill-based.

## 4. Validation gates (every strategy must pass all gates)

| Gate | Rule | Pass condition |
|------|------|----------------|
| G1 Line origin | Line derived from verified official inputs only | All inputs sourced & linked |
| G2 Correlation | No leg pair ≥ 0.30 correlation | Correlation matrix checked |
| G3 Injury filter | No bet on team with starter Out at key position | Official injury status = active |
| G4 Sample size | Strategy back-tested on ≥ 4 weeks of paper results | ≥ 20 signals logged |
| G5 Edge threshold | Originated edge vs. market ≥ threshold (TBD) | Edge ≥ threshold on every leg |
| G6 Skill vs. luck | Win rate exceeds break-even + variance margin | Paper win rate > break-even by margin |

A strategy failing any gate is rejected or revised before admission to the leaderboard.

## 5. Leaderboard competition & rewards

- Each admitted strategy is scored weekly on paper results: units won, win rate, ROI, edge accuracy.
- Leaderboard published on pages/strategies.html; updated weekly after NFL results are official.
- Rewards (proposal): top 3 strategies each month receive recognition + increased paper allocation; no real money until G4–G6 pass for 8 consecutive weeks.

## 6. Removing luck — design principles

1. Single bets first; parlays only after singles show skill.
2. Correlation caps prevent lucky stacks.
3. Injury filter removes bets damaged by backup replacements (2nd/3rd/4th string).
4. Paper-only for 4–8 weeks; real allocation only after gate passage.
5. Weekly review: strategies decaying below edge threshold are removed.

## 7. Open items (flagged)

- Market odds source not yet defined (non-official, to be flagged).
- Correlation values not yet computed from real results (placeholder, flagged unverified).
- Edge threshold and bankroll rules TBD (see decision framework F1–F2).
- Reviewer assignment TBD.
