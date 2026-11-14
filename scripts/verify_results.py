#!/usr/bin/env python3
"""Verify the transcribed results against the official standings, line by line.

Reads data/games_2026_results.csv (transcribed from the official NFL.com
by-week schedule pages) and data/standings_2026_snapshot.csv (transcribed from
the official NFL.com standings page), recomputes every team's record and points
from the games, and reports any mismatch.

Run:  python3 scripts/verify_results.py
Exit code 0 means every team reconciles exactly.
"""
import csv
import os
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")


def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


games = read("games_2026_results.csv")
standings = {r["team_abbr"]: r for r in read("standings_2026_snapshot.csv")}

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

print(f"Games checked: {len(games)}")
print("Games per week:", ", ".join(f"wk {w}: {n}" for w, n in sorted(per_week.items())))
print(f"Teams compared: {len(rec)}")
if problems:
    print("MISMATCHES:")
    for p in problems:
        print("  -", p)
    sys.exit(1)
print("All teams reconcile exactly with the official standings "
      "(W, L, T, points for, points against).")
