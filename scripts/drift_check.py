#!/usr/bin/env python3
"""Drift alarm for every register (T105, D38).

Reads data/drift_pins.csv. For each pinned register it checks, and fails loudly:
  * the file exists;
  * its row count equals expected_rows;
  * every required_nonblank_columns column exists and is non-blank in every row;
  * unique_key (one or more columns) has no duplicates;
  * allowed_values (col=v1|v2;col2=...) contains only listed values.

A pin changes only by editing data/drift_pins.csv in the same commit as the data
change, with a reason in the note column. The script never rewrites pins.
Exit status is 1 when any check fails; scripts/build.py calls it first and stops.
"""
import csv
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
PINS = os.path.join(DATA, "drift_pins.csv")


def check(pin):
    problems = []
    path = os.path.join(DATA, pin["register"])
    if not os.path.exists(path):
        return [f"missing file {pin['register']}"]
    with open(path, encoding="utf-8", newline="") as fh:
        rd = csv.DictReader(fh)
        header = rd.fieldnames or []
        rows = list(rd)
    expected = int(pin["expected_rows"])
    if len(rows) != expected:
        problems.append(f"row count {len(rows)} != pinned {expected}")
    for col in [c for c in pin["required_nonblank_columns"].split(";") if c]:
        if col not in header:
            problems.append(f"required column missing: {col}")
            continue
        blanks = [i + 2 for i, r in enumerate(rows) if not (r.get(col) or "").strip()]
        if blanks:
            problems.append(f"blank {col} on file line(s) {blanks[:8]}{' ...' if len(blanks) > 8 else ''}")
    key = [c for c in (pin["unique_key"] or "").split(";") if c]
    if key:
        if any(c not in header for c in key):
            problems.append(f"unique_key column missing: {key}")
        else:
            seen, dups = set(), []
            for r in rows:
                k = tuple(r[c] for c in key)
                if k in seen:
                    dups.append(k)
                seen.add(k)
            if dups:
                problems.append(f"duplicate key {key}: {dups[:3]}")
    for spec in [s for s in (pin["allowed_values"] or "").split(";") if s]:
        col, _, values = spec.partition("=")
        if col not in header:
            problems.append(f"allowed-values column missing: {col}")
            continue
        allowed = set(values.split("|"))
        bad = sorted({r[col] for r in rows if r[col] not in allowed})
        if bad:
            problems.append(f"{col} has unexpected values {bad[:5]}")
    return problems


def main():
    with open(PINS, encoding="utf-8", newline="") as fh:
        pins = list(csv.DictReader(fh))
    failures = 0
    for pin in pins:
        probs = check(pin)
        status = "PASS" if not probs else "FAIL"
        print(f"  drift {status}: {pin['register']} ({pin['expected_rows']} rows)")
        for p in probs:
            print(f"      - {p}")
        failures += bool(probs)
    if failures:
        print(f"DRIFT ALARM: {failures} register(s) failed their pinned checks; the build stops.")
        return 1
    print(f"drift check: all {len(pins)} registers match their pins.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
