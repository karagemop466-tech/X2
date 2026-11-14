# Injury & Depth-Chart Tracking Model

**Purpose:** Track injuries and identify offensive/defensive deficiencies caused by starters being replaced by 2nd, 3rd, or 4th-string backups.
**Official source:** NFL injury report — https://www.nfl.com/injuries/league/2026/REG10 (verified 2026-11-14).
**Depth-chart note:** NFL.com does not publish a single official 1st–4th-string depth chart page; depth values from third-party aggregators are flagged unverified and must be confirmed on official NFL team roster pages (nfl.com/teams/{team}).

## Data model

| Field | Description | Source | Official? |
|-------|-------------|--------|-----------|
| team | NFL team | standings | Yes |
| position | Position group (QB, RB, WR, TE, OT, OG, C, EDGE, DT, LB, CB, S, K, P) | roster | Yes (roster) |
| starter | 1st-string player | depth chart | Flagged (third-party) |
| backup2 | 2nd-string replacement | depth chart | Flagged (third-party) |
| backup3 | 3rd-string replacement | depth chart | Flagged (third-party) |
| backup4 | 4th-string replacement | depth chart | Flagged (third-party) |
| injuredPlayer | Injured starter name | nfl.com/injuries | Yes |
| injury | Injury description | nfl.com/injuries | Yes |
| practiceStatus | DNP / Limited / Full | nfl.com/injuries | Yes |
| gameStatus | Out / Questionable / Doubtful / blank | nfl.com/injuries | Yes |
| deficiencyFlag | true when starter Out/Questionable and backup2+ must play | computed | Yes (computed from official) |

## Deficiency rule (computed, official inputs)

A position group is FLAGGED as deficient when:
- starter gameStatus == "Out", OR
- starter gameStatus == "Questionable" with practiceStatus == "Did Not Participate"

The deficiency severity scales with replacement string:
- 2nd string: moderate
- 3rd string: high
- 4th string: severe

## Example (from verified official injury data, Week 10)

| Team | Position | Starter (injured) | Game status | Replacement string (per depth model) | Deficiency | Source |
|------|----------|-------------------|-------------|--------------------------------------|------------|--------|
| Detroit Lions | S | Kerby Joseph | Out | 2nd string (flagged unverified) | Moderate | nfl.com/injuries/league/2026/REG10 |
| Detroit Lions | C | Cade Mays | Out | 2nd string (flagged unverified) | Moderate | nfl.com/injuries/league/2026/REG10 |
| Detroit Lions | CB | D.J. Reed | Out | 2nd string (flagged unverified) | Moderate | nfl.com/injuries/league/2026/REG10 |
| New England | C | Ben Brown | Out | 2nd string (flagged unverified) | Moderate | nfl.com/injuries/league/2026/REG10 |
| New England | CB | Carlton Davis III | Out | 2nd string (flagged unverified) | Moderate | nfl.com/injuries/league/2026/REG10 |
| New England | RB | TreVeyon Henderson | Out | 2nd string (flagged unverified) | Moderate | nfl.com/injuries/league/2026/REG10 |
| Washington | C | Lucas Patrick | Out | 2nd string (flagged unverified) | Moderate | nfl.com/injuries/league/2026/REG10 |
| Washington | TE | Colson Yankoff | Out | 3rd string (flagged unverified) | High | nfl.com/injuries/league/2026/REG10 |

Replacement-string values are depth-chart estimates and are flagged unverified; confirm on official NFL team pages before using in line adjustments.

## Offense vs. defense coverage

The model applies identically to offense and defense:
- Offense: QB, RB, WR, TE, OT, OG, C — starter replaced by backup shifts offensive rating down.
- Defense: EDGE, DT, LB, CB, S — starter replaced by backup shifts defensive rating down.

Special teams (K, P) tracked separately; a missing kicker/punter affects totals and moneyline minimally but is logged.
