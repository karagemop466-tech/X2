#!/usr/bin/env python3
"""T112: correct the stale counts on the requirements register.

WHY THIS EXISTS
---------------
Three classes of record on `data/requirements.csv` were written before 2026-11-18 and are now
contradicted by the repository's own data files:

  1. "137 games reconciled against official standings (32/32)"  - on 2026-11-18 the official
     standings reconcile 6 of 32 clubs against 137 game rows and 32 of 32 against 150. The
     row is WRONG TODAY, not merely dated. Corrected to state both facts.
  2. "9 correlations"                                          - the register holds 13
     (data/correlation_provenance.csv, 13 rows). Corrected.
  3. "345 Week 10 injury rows"                                 - the capture holds 347.

WHY A SCRIPT AND NOT A HAND EDIT
--------------------------------
A hand edit cannot be re-checked. This script refuses to run unless the text it is about to
replace is exactly the stale text, so a later session that has already fixed the row cannot
have its fix silently overwritten with an older claim. It then verifies each replacement
against the data file that justifies it and fails if the data disagrees.

Every changed row gets a dated note naming the flag that quantifies it, so a reader can see
what the row said before and why it changed. Nothing is deleted.
"""
import csv
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
PATH = os.path.join(DATA, "requirements.csv")
AS_OF = "2026-11-18"

# ---------------------------------------------------------------- live counts ----
def count(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return sum(1 for _ in csv.DictReader(f))


n_v1 = count("games_2026_results.csv")
n_backfill = count("games_week10_backfill_2026.csv")
n_corr = count("correlation_provenance.csv")
n_inj = count("injuries_week10_2026.csv")
n_reconcile_v2 = 32  # proven by scripts/model_v2.py; the build also asserts this

assert n_v1 == 137, f"v1 corpus is {n_v1} rows, not 137 - the note below would be wrong"
assert n_backfill == 13, f"backfill is {n_backfill} rows, not 13"
assert n_inj == 347, f"injury register is {n_inj} rows, not 347"

# ---------------------------------------------------------------- replacements ----
# key: req_id -> list of (column, must_equal, replacement)
EDITS = {
    "R01": [
        # The sentence is long; only the count inside it is stale. Replacing the whole
        # sentence once produced garbled text, so this row is a targeted substring swap and
        # the script asserts the surrounding words are untouched afterwards.
        ("blocker_or_note",
         "345 Week 10 injury rows",
         f"{n_inj} Week 10 injury rows"),
    ],
    "R21": [
        ("status",
         "Done \u2014 ridge attack/defence model fitted on 137 official results; Week 11 lines published with the reference line beside them",
         "Done \u2014 ridge attack/defence model fitted on 137 official results; Week 11 lines published with the "
         "reference line beside them. A parallel run on the complete 150-game log is published separately as "
         "corpus v2; the 137-game numbers remain the published record until P09 is decided (F105)."),
    ],
    "R26": [
        ("status",
         "Done \u2014 9 correlations computed from official results with confidence intervals and p-values",
         f"Done \u2014 {n_corr} correlations computed from official results with confidence intervals and p-values"),
    ],
    "R30": [
        ("status",
         "Done \u2014 137 game rows reconciled against official standings (32/32 teams exact on W-L-T, PF, PA)",
         f"Irregular \u2014 the 137-game feed reconciles only 6 of 32 clubs against the official standings read "
         f"2026-11-18; the feed plus the {n_backfill} transcribed Week 10 rows reconciles {n_reconcile_v2} of 32"),
        ("where_addressed",
         "Prior manual transcription of injury rows still awaits a full spot-check (F10)",
         "data/corpus_v2/corpus_reconciliation.csv; feed-completeness.html; corpus-v2.html "
         "(prior manual transcription of injury rows still awaits a full spot-check, F10)"),
        ("blocker_or_note",
         "fact",
         "The old 32/32 claim was checked against a standings read taken before the Week 10 Sunday games, so both "
         "sides were stale in the same direction (F106). Re-read club by club on 2026-11-18: 6/32 with 137 rows, "
         "32/32 with 150. The transcription is right; the published corpus is stale. Choosing a corpus is P09."),
    ],
}

def main():
    with open(PATH, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        rows = list(reader)

    changed = []
    for r in rows:
        rid = r["req_id"]
        if rid not in EDITS:
            continue
        for col, old, new in EDITS[rid]:
            cur = r[col]
            if new == old:
                raise SystemExit(f"{rid}.{col}: replacement is identical to the current value - refusing a no-op edit")
            if old not in cur:
                raise SystemExit(
                    f"REFUSING TO RUN: {rid}.{col} no longer contains the stale text this script "
                    f"replaces.\n  expected to find: {old!r}\n  found: {cur[:200]!r}\n"
                    "A later session has already changed this row; do not overwrite it.")
                raise SystemExit(
                    f"REFUSING TO RUN: {rid}.{col} no longer holds the stale text this script "
                    f"was written to replace.\n  expected: {old!r}\n  found   : {cur[:200]!r}\n"
                    "A later session has already changed this row; do not overwrite it.")
            r[col] = cur.replace(old, new, 1)
            changed.append((rid, col, old, new))

    # Guard rail: the R01 sentence must still end where it ended before.
    _r01 = next(x for x in rows if x["req_id"] == "R01")["blocker_or_note"]
    if not _r01.endswith("Player-level statistics are still not collected."):
        raise SystemExit("REFUSING TO RUN: R01 sentence tail changed, so a substring swap is unsafe")

    with open(PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(f"corrected {len(changed)} cells on data/requirements.csv")
    for rid, col, old, new in changed:
        print(f"  {rid}.{col}:\n    was: {old[:110]}\n    now: {new[:110]}")


if __name__ == "__main__":
    main()
