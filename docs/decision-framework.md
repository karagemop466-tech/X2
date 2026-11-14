# Decision Framework — Questions, Information, and Answers Required Before Any Decision

**Purpose:** No line-origination, strategy, or site change is implemented until the questions below are answered. This is the single place where open decisions are logged, reviewed, and closed.
**Review path:** suggestions are submitted in the Suggestions section (pages/suggestions.html), reviewed here, and only then approved for implementation.

## How to read this document

| Column | Meaning |
|--------|---------|
| Decision area | What decision is being considered |
| Question | Specific question that must be answered before deciding |
| Information we have | What is already known, with official source |
| Information we do NOT have | Missing information needed to answer |
| Answer (preliminary) | Current best answer; flagged if unverified |
| Suggestion to discover missing info | How to obtain the missing information |

---

## Decision area A — Originating our own NFL lines

| # | Question | Information we have | Information we do NOT have | Answer (preliminary) | Suggestion to discover missing info |
|---|----------|---------------------|----------------------------|----------------------|-------------------------------------|
| A1 | What inputs should drive our opening line? | 2026 team standings (W/L/T, PF/PA, net points, home/road/div/conf splits) — official NFL standings (nfl.com/standings, verified 2026-11-14). Official injury report Week 10 (nfl.com/injuries/league/2026/REG10, verified). | Offensive/defensive DVOA or EPA by team; strength of schedule; venue/weather; rest/travel; official depth charts (1st–4th string) not available from official NFL source. | Baseline line = team rating difference + home-field advantage; rating built from PF/PA differential and win rate. Injury adjustment TBD. | Compute team ratings from PF/PA and standings; pull EPA/DVOA from a secondary stats source and flag it; scrape official NFL team roster pages for starter/backup info. |
| A2 | How do injuries adjust the line? | Per-player injury + game status (Out/Questionable/Doubtful) from official NFL injury report. | Player replacement value (2nd/3rd/4th string); snap-count impact of each injured starter; positional importance weights. | Out starter = negative adjustment; magnitude TBD by position and replacement quality. | Build depth-chart table from official team pages; assign positional weights (QB highest, etc.); validate against line movement history. |
| A3 | Where do we publish opening lines for review? | Suggestions section + decision framework exist on the site. | None. | Publish proposed lines in pages/strategies.html with validation-gate status before any use. | N/A |

---

## Decision area B — Single bets

| # | Question | Information we have | Information we do NOT have | Answer (preliminary) | Suggestion to discover missing info |
|---|----------|---------------------|----------------------------|----------------------|-------------------------------------|
| B1 | Which single bet types are in scope? | Moneyline, spread, total (over/under), first-half, player props — standard bet types. | Market odds from a sportsbook to compare against our originated lines (NFL does not publish official odds). | Start with moneyline + spread + total using our originated lines vs. market odds (market odds to be added as third-party data, flagged). | Record closing lines from one reference sportsbook; flag as non-official. |
| B2 | What is the minimum edge to bet a single? | None defined yet. | Bankroll, Kelly fraction, historical win rate of our signals. | No bets until edge threshold and bankroll rules are set (suggestion: 3%+ edge, 1/4 Kelly). | Back-test signal history once 4+ weeks of signals are logged. |

---

## Decision area C — Parlays

| # | Question | Information we have | Information we do NOT have | Answer (preliminary) | Suggestion to discover missing info |
|---|----------|---------------------|----------------------------|----------------------|-------------------------------------|
| C1 | How many legs max per parlay? | None defined. | Correlation data between legs; sportsbook parlay payout rules. | Suggestion: max 3 legs; require correlation < 0.30 between any two legs. | Compute leg correlation from historical results; flag until 4 weeks of data. |
| C2 | Are correlated parlays allowed? | Correlation framework documented in docs/strategies.md (not yet computed). | Actual correlation values. | No — correlated legs (e.g., same-game QB pass yards + team over) blocked by gate. | Build correlation matrix from game logs. |

---

## Decision area D — Player-prop combinations

| # | Question | Information we have | Information we do NOT have | Answer (preliminary) | Suggestion to discover missing info |
|---|----------|---------------------|----------------------------|----------------------|-------------------------------------|
| D1 | Which player props in scope? | None defined. | Prop markets (pass/rush/receive yards, TDs), player usage/snap counts, injury replacements. | Suggestion: QB pass yards, RB rush yards, WR receive yards only; starter must be active (not Out). | Collect prop lines from reference sportsbook; tie to official injury status. |
| D2 | How do backup QBs affect prop combos? | Injury report lists QB status and practice participation. | Backup QB depth and historical performance as starter. | Exclude prop combos involving a team whose starter QB is Out. | Depth chart from official team pages (flagged unverified). |

---

## Decision area E — Strategy validation gates

| # | Question | Information we have | Information we do NOT have | Answer (preliminary) | Suggestion to discover missing info |
|---|----------|---------------------|----------------------------|----------------------|-------------------------------------|
| E1 | What gates must every strategy pass? | Gate definitions proposed in docs/strategies.md (line origin, correlation check, skill vs. luck, back-test minimum). | Pass/fail thresholds; out-of-sample performance. | Gates defined; thresholds TBD until 4 weeks of signal history exist. | Run paper-trading back-test; record results on strategy leaderboard. |
| E2 | How is "luck" removed? | Correlation controls + selective bet sizing + validation gates. | Statistical luck model (variance decomposition). | Skill-based subset only: strategies must show edge > noise on paper results. | Track luck-adjusted metrics; review monthly. |

---

## Decision area F — Site & process changes

| # | Question | Information we have | Information we do NOT have | Answer (preliminary) | Suggestion to discover missing info |
|---|----------|---------------------|----------------------------|----------------------|-------------------------------------|
| F1 | Who reviews suggestions before implementation? | Suggestions section exists (pages/suggestions.html); reviewer not assigned. | Reviewer role & schedule. | Suggestion: repository owner reviews weekly; log decision in COORDINATION.md. | Assign reviewer; add review log table. |
| F2 | How often is data refreshed? | Weekly NFL cycle (injuries every week, standings after each game week). | None. | Refresh standings + injuries every Tuesday/Wednesday after NFL week completes. | Set calendar reminder; log refresh date in data files. |

---

## Open suggestions to discover missing information

1. Depth charts: fetch official NFL team roster pages (nfl.com/teams/{team}) and record starter/2nd/3rd/4th string by position; flag any values still missing.
2. Market odds: record reference sportsbook closing lines weekly for moneyline/spread/total; flag as non-official third-party data.
3. Correlation matrix: compute leg-by-leg correlation from 4+ weeks of logged results; update docs/strategies.md.
4. Back-test: paper-trash all signals for 4 weeks before any real-money allocation; publish results on the strategy leaderboard.
5. Reviewer assignment: name a suggestions reviewer and set a weekly review cadence.
