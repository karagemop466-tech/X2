#!/usr/bin/env python3
"""Verify the transcribed results against the official standings, line by line.

Reads data/games_2026_results.csv (transcribed from the official NFL.com
by-week schedule pages) and a dated official standings read, recomputes every
team's record and points from the games, and reports any mismatch.

Why the read date is a first-class argument (F106, T109). An earlier version of
this script compared the ledger with data/standings_2026_snapshot.csv, a read
taken on 2026-11-14 before the Week 10 Sunday games, and then printed
"All teams reconcile exactly with the official standings" with no date on it.
On 2026-11-18 that sentence is misleading: 26 of 32 clubs differ from the
fresher official read because 13 settled games were not in the ledger. A
reconciliation between two surfaces read on the same day proves arithmetic; a
reconciliation against an older read proves neither arithmetic nor currency.
So this script takes the standings read to compare against as an argument,
prints both read dates, refuses to present an old read as currency, and exits
non-zero when the ledger is behind the read it is measured against.

Run:
  python3 scripts/verify_results.py                    # both reads, explicit verdicts
  python3 scripts/verify_results.py --target capture   # current read only

Exit code 0 = the ledger reconciles with the current official read.
"""
import argparse
import csv
import os
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")

# The stands read each comparison target was transcribed from. Printed beside
# every verdict, because the verdict is only true of that read (F106).
TARGETS = {
    "snapshot": ("standings_2026_snapshot.csv", "2026-11-14",
                 "before the Week 10 Sunday games were played"),
    "capture": (os.path.join("captures", "standings_2026-11-18.csv"), "2026-11-18",
                "after the completed Week 10 slate"),
}


def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def tally(games):
    rec = defaultdict(lambda: {"W": 0, "L": 0, "T": 0, "PF": 0, "PA": 0})
    per_week = defaultdict(int)
    for g in games:
        a, h = int(g["away_points"]), int(g["home_points"])
        per_week[int(g["week"])] += 1
        for team, pf, pa in ((g["away_team"], a, h), (g["home_team"], h, a)):
            rec[team]["PF"] += pf
            rec[team]["PA"] += pa
            if pf > pa:
                rec[team]["W"] += 1
            elif pf < pa:
                rec[team]["L"] += 1
            else:
                rec[team]["T"] += 1
    return rec, per_week


def games_in(standings):
    """Completed games implied by a standings read: one per club per game."""
    return sum(int(s["wins"]) + int(s["losses"]) + int(s["ties"])
               for s in standings.values()) / 2


def compare(rec, standings):
    problems = []
    for team, r in sorted(rec.items()):
        s = standings.get(team)
        if s is None:
            problems.append(f"{team}: no official standings row to compare against")
            continue
        exp = (int(s["wins"]), int(s["losses"]), int(s["ties"]),
               int(s["points_for"]), int(s["points_against"]))
        got = (r["W"], r["L"], r["T"], r["PF"], r["PA"])
        if exp != got:
            problems.append(f"{team}: computed {got} but official standings say {exp}")
    for team in sorted(standings):
        if team not in rec:
            problems.append(f"{team}: appears in the official standings but has no game rows")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description="Reconcile the results ledger with a dated official standings read.")
    ap.add_argument("--target", choices=sorted(TARGETS) + ["both"], default="both",
                    help="which dated official standings read to compare against")
    args = ap.parse_args(argv)

    games = read("games_2026_results.csv")
    rec, per_week = tally(games)

    print(f"Ledger: data/games_2026_results.csv - {len(games)} games")
    print("Games per week:", ", ".join(f"wk {w}: {n}" for w, n in sorted(per_week.items())))
    print(f"Teams compared: {len(rec)}")

    targets = ["snapshot", "capture"] if args.target == "both" else [args.target]
    behind_current = False
    # How many settled games a fresher read holds that an older one cannot. Used
    # only to word the snapshot verdict honestly; never to change a number.
    _cap = {r["team_abbr"]: r for r in read(TARGETS["capture"][0])}
    _snap = {r["team_abbr"]: r for r in read(TARGETS["snapshot"][0])}
    newer_games = int(games_in(_cap) - games_in(_snap))

    for key in targets:
        name, read_date, note = TARGETS[key]
        standings = {r["team_abbr"]: r for r in read(name)}
        implied = games_in(standings)
        problems = compare(rec, standings)
        print()
        print(f"--- comparison target: {key} ---")
        print(f"Official standings read: {read_date} ({note})")
        print(f"  file: data/{name}")
        print(f"  completed games implied by that read: {implied:g}; games in the ledger: {len(games)}")
        if problems:
            print(f"  MISMATCHES ({len(problems)} of {len(rec)} clubs):")
            for p in problems[:5]:
                print("   -", p)
            if len(problems) > 5:
                print(f"   - ... and {len(problems) - 5} more (same pattern)")
        else:
            print("  0 mismatches on W, L, T, points for and points against.")

        if key == "snapshot":
            if problems:
                print("  VERDICT: the ledger does not reconcile with the 2026-11-14 read.")
            else:
                print("  VERDICT: internal arithmetic PASSES against the 2026-11-14 read.")
                print("  Arithmetic only. NOT a statement of currency: the 2026-11-18 read "
                      f"holds {newer_games} more settled games than this one does.")
        else:
            if problems:
                behind_current = True
                print(f"  VERDICT: FAIL - the ledger is {implied - len(games):g} games behind the current")
                print(f"  official read, so {len(problems)} of {len(rec)} clubs do not reconcile with it.")
                print("  See Flag F106 and the Feed completeness page.")
            else:
                print("  VERDICT: PASS - the ledger reconciles with the current official read on")
                print("  W, L, T, points for and points against.")

    return 1 if behind_current else 0


if __name__ == "__main__":
    sys.exit(main())
