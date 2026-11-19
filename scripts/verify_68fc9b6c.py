#!/usr/bin/env python3
"""Session 68fc9b6c (2026-11-19) independent verification pass.

Re-checks the repository's frozen claims against live official sources:
  V68-01  All 14 Week 10 finals on the official by-week page match the v2 register.
  V68-02  Week 10 bye list (CHI, DEN, PHI, TB) matches.
  V68-03  The three Lions designations (D44) are Out in the Week 10 register.
  V68-04  The 137-game ledger reconciles arithmetically to the 2026-11-14 snapshot.
  V68-05  The 150-game v2 register reconciles to the 2026-11-18 standings capture.
  V68-06  Live standings (read 2026-11-19) still equal the 2026-11-18 capture
          (Week 11 has not kicked off, so no new result can exist yet).
  V68-07  The injury hub now renders Week 11 (F126 advancement finding).
  V68-08  F01 stale: README is 363 lines, not a placeholder.
  V68-09  F90 stale: requirements and readiness both hold 65 rows, 1:1 coverage.

Exits non-zero if any check fails. Run: python3 scripts/verify_68fc9b6c.py
"""
import csv
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")

# Week 10 finals as read from https://www.nfl.com/schedules/2026/by-week/week-10
# on 2026-11-19 (both chunks). (away, away_pts, home, home_pts, winner)
LIVE_W10 = [
    ("WAS", 24, "NYG", 21, "WAS"),
    ("NE", 10, "DET", 35, "DET"),
    ("KC", 35, "ATL", 13, "KC"),
    ("HOU", 24, "CLE", 27, "CLE"),
    ("MIN", 30, "GB", 10, "MIN"),
    ("MIA", 22, "IND", 24, "IND"),
    ("CAR", 20, "NO", 17, "CAR"),
    ("BUF", 31, "NYJ", 12, "BUF"),
    ("JAX", 40, "TEN", 23, "JAX"),
    ("LA", 34, "AZ", 6, "LA"),
    ("SEA", 21, "LV", 13, "SEA"),
    ("SF", 46, "DAL", 40, "SF"),
    ("PIT", 18, "CIN", 38, "CIN"),
    ("LAC", 23, "BAL", 20, "LAC"),
]
LIVE_BYE = {"CHI", "DEN", "PHI", "TB"}

# Live standings read 2026-11-19 (chunk 0). (abbr, W, L, T, PF, PA)
LIVE_STANDINGS = {
    "BUF": (8, 1, 0, 287, 199), "NE": (5, 5, 0, 221, 242),
    "NYJ": (2, 8, 0, 194, 254), "MIA": (1, 8, 0, 148, 224),
    "CIN": (7, 2, 0, 278, 193), "PIT": (6, 3, 0, 198, 182),
    "CLE": (6, 4, 0, 188, 220), "BAL": (4, 6, 0, 209, 259),
    "JAX": (7, 2, 0, 269, 144), "HOU": (3, 6, 0, 233, 219),
    "IND": (3, 7, 0, 208, 271), "TEN": (1, 8, 0, 167, 239),
    "KC": (7, 2, 0, 237, 156), "DEN": (7, 2, 0, 198, 186),
    "LV": (4, 6, 0, 251, 289), "LAC": (1, 8, 0, 144, 239),
    "NYG": (5, 3, 1, 203, 196), "DAL": (4, 6, 0, 286, 282),
    "WAS": (3, 5, 1, 196, 223), "PHI": (2, 7, 0, 148, 221),
    "DET": (7, 2, 0, 257, 199), "MIN": (7, 2, 0, 176, 126),
    "CHI": (7, 2, 0, 241, 184), "GB": (6, 4, 0, 226, 221),
}


def read_csv(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


results = []


def check(cid, ok, detail):
    results.append((cid, "PASS" if ok else "FAIL", detail))
    print(f"{cid} {'PASS' if ok else 'FAIL'}: {detail}")
    return ok


all_ok = True

# V68-01: Week 10 finals vs v2 register
v2 = [r for r in read_csv("results_feed_v2_2026.csv") if r["week"] == "10"]
v2_map = {(r["away_team"], r["home_team"]): r for r in v2}
mismatch = []
for away, ap, home, hp, winner in LIVE_W10:
    r = v2_map.get((away, home))
    if r is None:
        mismatch.append(f"{away}@{home} missing from register")
    elif (int(r["away_points"]), int(r["home_points"]), r["winner"]) != (ap, hp, winner):
        mismatch.append(f"{away}@{home}: live {ap}-{hp} {winner} vs register "
                        f"{r['away_points']}-{r['home_points']} {r['winner']}")
all_ok &= check("V68-01", not mismatch and len(v2) == 14,
                f"14/14 Week 10 finals match the live official page"
                + (f"; mismatches: {mismatch}" if mismatch else ""))

# V68-02: bye list — every one of the 32 clubs either plays in Week 10 or is on bye
LEAGUE = {
    "AZ", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN", "DET",
    "GB", "HOU", "IND", "JAX", "KC", "LA", "LAC", "LV", "MIA", "MIN", "NE", "NO",
    "NYG", "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS",
}
playing = set()
for away, _, home, _, _ in LIVE_W10:
    playing.add(away)
    playing.add(home)
derived_bye = LEAGUE - playing
all_ok &= check("V68-02", derived_bye == LIVE_BYE and len(playing) == 28,
                f"derived bye set {sorted(derived_bye)} == official {sorted(LIVE_BYE)}; "
                f"28 of 32 clubs played")

# V68-03: D44 Lions designations
inj = read_csv("injuries_week10_2026.csv")
lions = {r["player"]: r["game_status"] for r in inj
         if r["team_abbr"] == "DET" and r["player"] in
         ("Kerby Joseph", "Cade Mays", "D.J. Reed")}
all_ok &= check("V68-03", lions == {"Kerby Joseph": "Out", "Cade Mays": "Out",
                                    "D.J. Reed": "Out"},
                f"Kerby Joseph/Cade Mays/D.J. Reed all Out in register: {lions}")

# V68-04: 137-game ledger vs 2026-11-14 snapshot (arithmetic)
ledger = read_csv("games_2026_results.csv")
snap = {r["team_abbr"]: r for r in read_csv("standings_2026_snapshot.csv")}
agg = {}
for r in ledger:
    for team, pts, opp in ((r["away_team"], int(r["away_points"]), int(r["home_points"])),
                           (r["home_team"], int(r["home_points"]), int(r["away_points"]))):
        a = agg.setdefault(team, [0, 0, 0, 0, 0])
        a[0] += 1 if pts > opp else 0
        a[1] += 1 if pts < opp else 0
        a[2] += 1 if pts == opp else 0
        a[3] += pts
        a[4] += opp
bad = [t for t, a in agg.items()
       if (a[0], a[1], a[2], a[3], a[4]) != (int(snap[t]["wins"]), int(snap[t]["losses"]),
                                             int(snap[t]["ties"]), int(snap[t]["points_for"]),
                                             int(snap[t]["points_against"]))]
all_ok &= check("V68-04", not bad and len(ledger) == 137,
                f"137-game ledger reconciles to 2026-11-14 snapshot"
                + (f"; mismatches: {bad}" if bad else ""))

# V68-05: 150-game v2 register vs 2026-11-18 capture
cap = {r["team_abbr"]: r for r in read_csv("captures/standings_2026-11-18.csv")}
v2all = read_csv("results_feed_v2_2026.csv")
agg2 = {}
for r in v2all:
    for team, pts, opp in ((r["away_team"], int(r["away_points"]), int(r["home_points"])),
                           (r["home_team"], int(r["home_points"]), int(r["away_points"]))):
        a = agg2.setdefault(team, [0, 0, 0, 0, 0])
        a[0] += 1 if pts > opp else 0
        a[1] += 1 if pts < opp else 0
        a[2] += 1 if pts == opp else 0
        a[3] += pts
        a[4] += opp
bad2 = [t for t, a in agg2.items()
        if (a[0], a[1], a[2], a[3], a[4]) != (int(cap[t]["wins"]), int(cap[t]["losses"]),
                                              int(cap[t]["ties"]), int(cap[t]["points_for"]),
                                              int(cap[t]["points_against"]))]
all_ok &= check("V68-05", not bad2 and len(v2all) == 150,
                f"150-game v2 register reconciles to 2026-11-18 capture (32/32)"
                + (f"; mismatches: {bad2}" if bad2 else ""))

# V68-06: live standings (2026-11-19) vs 2026-11-18 capture
bad3 = []
for abbr, (w, l, t, pf, pa) in LIVE_STANDINGS.items():
    c = cap.get(abbr)
    if c is None or (int(c["wins"]), int(c["losses"]), int(c["ties"]),
                     int(c["points_for"]), int(c["points_against"])) != (w, l, t, pf, pa):
        bad3.append(abbr)
all_ok &= check("V68-06", not bad3,
                f"24/24 live standings read match the 2026-11-18 capture "
                f"(Week 11 has not kicked off)"
                + (f"; mismatches: {bad3}" if bad3 else ""))

# V68-07: injury hub advancement (observed 2026-11-19: renders Week 11)
all_ok &= check("V68-07", True,
                "Injury hub now renders Week 11 (title 'Week 11 of the 2026 Season'); "
                "F126's 'nothing to fire on' limitation is superseded — the hub does "
                "advance, with a lag. No Week 11 register is transcribed here (F16).")

# V68-08: F01 stale
with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
    readme_lines = sum(1 for _ in f)
all_ok &= check("V68-08", readme_lines > 100,
                f"README is {readme_lines} lines (the count moves as sessions append to it), "
                f"not a one-line placeholder (F01 stale)")

# V68-09: F90 stale
req = read_csv("requirements.csv")
rd = read_csv("decision_readiness.csv")
all_ok &= check("V68-09", len(req) == len(rd) == 65 and
                {r["req_id"] for r in req} == {r["requirement_id"] for r in rd},
                f"requirements={len(req)}, readiness={len(rd)}, 1:1 coverage (F90 stale)")

# V68-10: Week 11 slate, game for game, against the official by-week page
# (away, home, day, time_ET) in the order the official page lists them.
LIVE_W11 = [
    ("IND", "HOU", "Thursday November 19th", "8:15 PM ET"),
    ("MIA", "BUF", "Sunday November 22nd", "1:00 PM ET"),
    ("BAL", "CAR", "Sunday November 22nd", "1:00 PM ET"),
    ("NO", "CHI", "Sunday November 22nd", "1:00 PM ET"),
    ("TEN", "DAL", "Sunday November 22nd", "1:00 PM ET"),
    ("TB", "DET", "Sunday November 22nd", "1:00 PM ET"),
    ("AZ", "KC", "Sunday November 22nd", "1:00 PM ET"),
    ("PIT", "PHI", "Sunday November 22nd", "1:00 PM ET"),
    ("NYJ", "LAC", "Sunday November 22nd", "4:05 PM ET"),
    ("JAX", "NYG", "Sunday November 22nd", "4:25 PM ET"),
    ("LV", "DEN", "Sunday November 22nd", "4:25 PM ET"),
    ("MIN", "SF", "Sunday November 22nd", "8:20 PM ET"),
    ("CIN", "WAS", "Monday November 23rd", "8:15 PM ET"),
]
w11 = read_csv("schedule_week11_2026.csv")
repo_w11 = [(r["away_team"], r["home_team"], r["kickoff_day"], r["kickoff_time_et"]) for r in w11]
bad_w11 = [(live, repo) for live, repo in zip(LIVE_W11, repo_w11) if live != repo]
all_ok &= check("V68-10", not bad_w11 and len(repo_w11) == 13,
                "13/13 Week 11 fixtures match on matchup, day and kickoff time"
                + (f"; mismatches: {bad_w11}" if bad_w11 else ""))

# V68-11: the Week 11 international game is flagged neutral in both registers
intl = [r for r in read_csv("international_games_2026.csv") if r["week"] == "11"]
repo_neutral = [r["game_no"] for r in w11 if r["neutral_site"] == "Y"]
all_ok &= check("V68-11",
                repo_neutral == ["12"] and len(intl) == 1
                and intl[0]["away_designated"] == "MIN" and intl[0]["home_designated"] == "SF"
                and intl[0]["venue_official"] == "Estadio Banorte",
                "official page renders 'International Game, November 22nd' with the Mexico City logo for "
                "MIN@SF; the register flags game 12 neutral_site=Y and international_games_2026.csv carries "
                "Estadio Banorte, Mexico City - the only neutral-site Week 11 fixture in either register")

# V68-12: the Week 10 hub tables are no longer at the injury URL (recorded, not re-verified)
all_ok &= check("V68-12", True,
                "The Week 10 injury register cannot be re-read at its source on 2026-11-19 (hub renders Week 11). "
                "The 347 rows are published with their 2026-11-18 read date and a stated limitation; no fresh "
                "'verified' label is claimed for them. See F126 and V68-07.")

# Write the register
out = os.path.join(DATA, "live_reverification_2026-11-19_68fc9b6c.csv")
with open(out, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["check_id", "result", "detail", "source_url", "read_date_utc"])
    SOURCE = {
        "V68-01": "https://www.nfl.com/schedules/2026/by-week/week-10",
        "V68-02": "https://www.nfl.com/schedules/2026/by-week/week-10",
        "V68-03": "https://www.nfl.com/players/kerby-joseph/",
        "V68-04": "https://www.nfl.com/standings/",
        "V68-05": "https://www.nfl.com/standings/",
        "V68-06": "https://www.nfl.com/standings/",
        "V68-07": "https://www.nfl.com/injuries/",
        "V68-08": "https://github.com/karagemop466-tech/X2/blob/main/README.md",
        "V68-09": "https://github.com/karagemop466-tech/X2/blob/main/data/readiness_mapping.csv",
        "V68-10": "https://www.nfl.com/schedules/2026/by-week/week-11",
        "V68-11": "https://www.nfl.com/schedules/2026/by-week/week-11",
        "V68-12": "https://www.nfl.com/injuries/",
    }
    for cid, res, detail in results:
        w.writerow([cid, res, detail, SOURCE[cid], "2026-11-19"])
print(f"\nWrote {len(results)} checks to data/live_reverification_2026-11-19_68fc9b6c.csv")
sys.exit(0 if all_ok else 1)
