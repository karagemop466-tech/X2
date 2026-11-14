# Injuries & Depth Charts

The system tracks injuries and detects deficiencies created when 2nd, 3rd, or
4th-string backups must replace starters — on **both** defense and offense. It
cross-references the official NFL injury report with depth charts to name the
specific backup elevating to starter, so a status becomes an actionable, verifiable
signal rather than a guess.

## How it works

1. **Injury status** is taken from the official NFL.com injury report (questionable,
   doubtful, out, plus practice participation).
2. **Depth ordering** is taken from depth charts, which list the starter and the
   2nd/3rd/4th-string players at each position.
3. **Deficiency** is detected when a starter is out/doubtful/questionable and the
   next-string backup is named as the replacement.
4. The deficiency is flagged for review if the position cannot be reconciled across
   sources (see the position-discrepancy case below).

## Current verified injuries (NFL.com, Week 10, 2026)

Sample of the official injury report, with the source link on every row. Rows with
a blank injury or game-status field are shown blank because the official report did
not list a value for that field.

{{TABLE: injuries}}

## Verified depth deficiencies (backups replacing starters)

Cross-reference of the official injury report with depth charts. Each row names the
starter, the elevating backup, and the resulting deficiency. Both offense and
defense are covered.

{{TABLE: depthDeficiencies}}

## Notes and caveats

- **Depth charts are third-party.** The NFL does not publish an official depth
  chart. ESPN and Ourlads are reputable third-party sources and are labeled as such
  on the [Data Sources](../data-sources/) page. This is flagged on the
  [Flagged for Review](../flagged-for-review/) page.
- **Position discrepancy.** Ben Brown is listed as **C** in the official injury
  report but as **RG** on the depth chart. The deficiency is withheld until the
  position is reconciled. See [F-01](../flagged-for-review/) on the
  [Flagged for Review](../flagged-for-review/) page.
- **Severity scoring.** The system defines a documented method to convert
  (position + string depth + injury status) into a line-impact score. No numeric
  severity is assumed or invented; values are computed from the linked official
  data once the feed is connected.
