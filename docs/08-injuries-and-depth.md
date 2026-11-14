# Injuries & Depth Charts

The system tracks injuries and detects deficiencies created when 2nd, 3rd, or
4th-string backups must replace starters — on **both** defense and offense. It
cross-references the official NFL injury report with depth charts to name the
specific backup elevating to starter, so a status becomes an actionable, verifiable
signal rather than a guess.

## How it works

1. **Injury status** is taken from the official NFL.com injury report (questionable,
   doubtful, out, plus practice participation).
2. **Depth ordering** would come from an official depth chart. None was found, so
   ordering fields are blank and marked unverified.
3. **Deficiency** is detected when a starter is out/doubtful/questionable and the
   next-string backup is named as the replacement.
4. The deficiency is flagged for review if the position cannot be reconciled across
   sources (see the position-discrepancy case below).

## Current verified injuries (NFL.com, Week 10, 2026)

Sample of the official injury report, with the source link on every row. Rows with
a blank injury or game-status field are shown blank because the official report did
not list a value for that field.

{{TABLE: injuries}}

## Injury entries awaiting official depth ordering (backups replacing starters: unverified)

Each row carries the official NFL.com injury status only. The starter/backup ordering,
the elevating backup and the deficiency text are blank: no official depth chart was
found (see F-05), and third-party charts are not used as evidence. Both offense and
defense positions are listed.

{{TABLE: depthDeficiencies}}

## Notes and caveats

- **No official depth chart found.** The NFL.com depth-chart URL checked for the Detroit
  Lions returned a 404 page on 2026-11-14. ESPN and Ourlads are third-party; they were
  consulted only as leads and are not used as evidence. This is flagged as F-05.
- **Position discrepancy.** Ben Brown is listed as **C** in the official injury
  report. A third-party chart lists **RG**; that value is unverified and not used. See [F-01](../flagged-for-review/) on the
  [Flagged for Review](../flagged-for-review/) page.
- **Severity scoring.** The system defines a documented method to convert
  (position + string depth + injury status) into a line-impact score. No numeric
  severity is assumed or invented; values are computed from the linked official
  data once the feed is connected.
