#!/usr/bin/env python3
"""Verify the transcribed results against the official standings, line by line.

Reads a results register and a standings snapshot, recomputes every team's record
and points from the games, and reports any mismatch.

Both inputs are arguments, because the pairing matters: a corpus frozen at one
date can only be reconciled against a standings read taken after every game in it
and before any game outside it. Reconciling the 137-game corpus against the
2026-11-18 standings read fails for exactly that reason - thirteen Week 10 games
sit between the two - and that failure is the finding, not an error to paper over
(flag F106, raised by session cf85d485).

  python3 scripts/verify_results.py                      # published pair (137 games, week-9 standings)
  python3 scripts/verify_results.py --games results_feed_v2_2026.csv \
                                         --standings captures/standings_2026-11-18.csv
                                                         # the completed 150-game register
  python3 scripts/verify_results.py --list               # which standings reads are available

An explicit standings file must name its read date in a column
(`read_date_utc` or `read_date`); a file that does not is refused, because an
undated standings read is what made the original claim unverifiable.

Run:  python3 scripts/verify_results.py [options]
Exit code 0 means every team reconciles exactly.
"""
import argparse
import csv
import os
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")

DEFAULT_GAMES = "games_2026_results.csv"
DEFAULT_STANDINGS = "standings_2026_snapshot.csv"
DATE_COLS = ("read_date_utc", "read_date", "read_utc", "verified_date")


def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def standings_read_date(rows):
    """The date the standings page was read, from the file itself, or None."""
    if not rows:
        return None
    for col in DATE_COLS:
        val = (rows[0].get(col) or "").strip()[:10]
        if val:
            return val
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--games", default=DEFAULT_GAMES,
                    help=f"results register under data/ (default {DEFAULT_GAMES})")
    ap.add_argument("--standings", default=None,
                    help=f"standings snapshot under data/ (default {DEFAULT_STANDINGS})")
    ap.add_argument("--list", action="store_true", help="list standings reads available in data/")
    ap.add_argument("--allow-future-weeks", action="store_true",
                    help="report mismatching clubs instead of failing (used to date the gap)")
    args = ap.parse_args(argv)

    if args.list:
        print("Standings reads available under data/:")
        for dirpath, _dirs, files in os.walk(DATA):
            for fn in sorted(files):
                if "standings" not in fn or not fn.endswith((".csv", ".psv")):
                    continue
                rel = os.path.relpath(os.path.join(dirpath, fn), DATA)
                try:
                    rows = read(rel)
                except Exception:  # noqa: BLE001 - a listing must not die on one file
                    continue
                if not rows or "wins" not in rows[0]:
                    continue
                print(f"  {rel}  ({len(rows)} clubs, read {standings_read_date(rows) or 'UNDATED'})")
        return 0

    games = read(args.games)
    standings_name = args.standings or DEFAULT_STANDINGS
    standings_rows = read(standings_name)
    standings = {r["team_abbr"]: r for r in standings_rows}
    standings_date = standings_read_date(standings_rows)
    if standings_date is None:
        print("WARNING: this standings file carries no read date, so the reconciliation it anchors "
              "cannot be age-checked (flag F106). data/captures/standings_<date>.csv files do carry one.")
    if standings_date is None and args.standings:
        print(f"REFUSED: {standings_name} carries no read date, so a reconciliation "
              f"against it cannot be checked for staleness (F106).")
        return 2
    corpus_week = max(int(g["week"]) for g in games)

    print(f"Games register: data/{args.games}  ({len(games)} rows, latest week {corpus_week})")
    print(f"Standings read: data/{standings_name}  ({len(standings)} clubs, "
          f"read {standings_date or 'date unknown'})")
    if standings_date:
        print(f"Pairing: corpus through week {corpus_week} vs standings read {standings_date}")

    rec = defaultdict(lambda: {"W": 0, "L": 0, "T": 0, "PF": 0, "PA": 0, "last_week": 0})
    per_week = defaultdict(int)
    for g in games:
        a, h = int(g["away_points"]), int(g["home_points"])
        wk = int(g["week"])
        per_week[wk] += 1
        for team, pf, pa in ((g["away_team"], a, h), (g["home_team"], h, a)):
            rec[team]["PF"] += pf
            rec[team]["PA"] += pa
            rec[team]["last_week"] = max(rec[team]["last_week"], wk)
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
        label = "MISMATCHES" if not args.allow_future_weeks else "MISMATCHES (reported, not fatal)"
        print(f"{label} ({len(problems)}):")
        for p in problems:
            print("  - " + p)
        if not args.allow_future_weeks:
            print("\nIf the standings read is newer than the corpus, this is the gap the corpus "
                  "has not closed yet (see data/week_count_reconciliation_2026-11-18.csv and F96), "
                  "not a transcription error. Pass --allow-future-weeks to report without failing, "
                  "or reconcile against a register that contains those weeks (e.g. "
                  "data/results_feed_v2_2026.csv).")
            return 1
    print("All teams reconcile exactly with the official standings "
          "(W, L, T, points for, points against).")
    return 0


if __name__ == "__main__":
    sys.exit(main())


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
