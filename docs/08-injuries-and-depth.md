# Injuries & Depth Charts

The system tracks injuries and detects deficiencies created when 2nd, 3rd, or
4th-string backups must replace starters — on **both** defense and offense. It
cross-references the official NFL injury report with depth charts to name the
specific backup elevating to starter, so a status becomes an actionable, verifiable
signal rather than a guess.

## How it works

1. **Injury status** is taken from the official NFL.com injury report (questionable,
   doubtful, out, plus practice participation).
2. **Depth ordering** is taken from the club-published depth charts on the official
   club websites — [detroitlions.com](https://www.detroitlions.com/team/depth-chart)
   and [patriots.com](https://www.patriots.com/team/depth-chart) — which are linked
   from the NFL.com team roster pages. No league-level official depth chart exists
   (the NFL.com team depth-chart URLs checked return 404), and the club pages
   self-label their charts "unofficial"; that caveat is flagged (F-05).
3. **Deficiency** is detected when a starter is out/doubtful/questionable and the
   next-string backup is named as the replacement.
4. The deficiency is flagged for review if the position cannot be reconciled across
   sources (see the position-discrepancy case below).

## Current verified injuries (NFL.com, Week 10, 2026)

Sample of the official injury report, with the source link on every row. Rows with
a blank injury or game-status field are shown blank because the official report did
not list a value for that field.

{{TABLE: injuries}}

## Injury entries with club-chart depth ordering (backups replacing starters)

Each row carries the official NFL.com injury status plus depth ordering verified
against the club-published depth charts (fetched 2026-11-14). Fields no club chart
confirms stay blank and marked unverified. Third-party charts (ESPN, Ourlads) are
not used as evidence. Both offense and defense positions are listed.

{{TABLE: depthDeficiencies}}

## Notes and caveats

- **Depth charts: club official pages, self-labeled "unofficial" (F-05).** The
  NFL.com team depth-chart URLs checked return 404, but the clubs publish weekly
  charts on their official sites —
  [detroitlions.com](https://www.detroitlions.com/team/depth-chart) ("2026
  Unofficial Depth Chart Compiled by Lions Football Communications") and
  [patriots.com](https://www.patriots.com/team/depth-chart) ("unofficial and is
  published by the writers of Patriots.com", reflecting writer opinion). Both are
  linked from the NFL.com team roster pages. Ordering values are filled only where
  a club chart confirms them, and the self-labeled "unofficial" caveat applies to
  every such row. ESPN and Ourlads are third-party; they were consulted only as
  leads and are not used as evidence.
- **Backup identity corrected against the official club chart (F-08).** A former
  third-party value named Khalil Dorsey "2nd string" behind D.J. Reed. The Lions
  club chart lists **Rock Ya-Sin 2nd** and Khalil Dorsey 3rd behind Reed, and the
  row now carries the club-chart value.
- **Position discrepancy.** Ben Brown is listed as **C** in the official injury
  report. The club chart lists him **1st-string LG and 2nd-string C**; the former
  third-party **RG** value is unsupported by the club chart and not used. See
  [F-01](../flagged-for-review/) on the [Flagged for Review](../flagged-for-review/)
  page.
- **Severity scoring.** The system defines a documented method to convert
  (position + string depth + injury status) into a line-impact score. No numeric
  severity is assumed or invented; values are computed from the linked official
  data once the feed is connected.
