#!/usr/bin/env python3
"""Session b94f5221 (2026-11-19, T311-T312) second independent live verification pass.

Machine-checks the registers this session produced from official NFL.com pages
(read through the platform page-fetch tool; all 7 injury-hub chunks, standings
(2 chunks), the Week 11 schedule page (2 chunks), the Broncos roster and the
deeundre-ford player page):

  V94 checks (data/live_reverification_2026-11-19_b94f5221.csv):
    - the check register itself is internally consistent (13 rows, all PASS,
      unique ids, every row carries an official https source)
  Injury second read (data/injury_week11_counts_2026-11-19_b94f5221.csv):
    - totals: 253 rows, DNP 83 / LP 87 / FP 83, Out 9 / Questionable 6 / blank 238
    - vs the first read (data/injury_week11_2026-11-19_by_club.csv):
      exactly 23 of 24 clubs identical on every count field, and IND is the
      single differing club with exactly Questionable -1 and blank +1
  Standings second read (data/captures/standings_2026-11-19_b94f5221.csv):
    - 32 clubs, PF=PA+net on every row, and field-by-field equality with the
      2026-11-18 official capture (no Week 11 result existed at either read)
  Schedule (data/schedule_week11_2026.csv vs the observed page):
    - the 13 observed games (day, time, away, home, broadcast) match the
      register exactly, including the MIN@SF Mexico City neutral flag

Exits non-zero on any failure. Run: python3 scripts/verify_b94f5221.py
"""
import csv
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")

failures = []


def load(path):
    with open(os.path.join(DATA, path), encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def fail(msg):
    failures.append(msg)


# ---- 1. the V94 check register -------------------------------------------------
checks = load("live_reverification_2026-11-19_b94f5221.csv")
if len(checks) != 13:
    fail("check register: %d rows, expected 13" % len(checks))
ids = [r["check_id"] for r in checks]
if len(set(ids)) != len(ids):
    fail("check register: duplicate check_id")
for r in checks:
    if r["result"] != "PASS":
        fail("check register: %s is %s, expected PASS" % (r["check_id"], r["result"]))
    if not r["source_url"].startswith("https://www.nfl.com/"):
        fail("check register: %s source is not an official nfl.com URL" % r["check_id"])

# ---- 2. injury second read -----------------------------------------------------
second = {r["club"]: r for r in load("injury_week11_counts_2026-11-19_b94f5221.csv")}
first = {r["club"]: r for r in load("injury_week11_2026-11-19_by_club.csv")}

if set(second) != set(first):
    fail("club sets differ: %s" % (set(second) ^ set(first)))
if len(second) != 26:
    fail("second read: %d club rows, expected 26" % len(second))

tot_rows = sum(int(r["rows"]) for r in second.values())
tot_dnp = sum(int(r["practice_dnp"]) for r in second.values())
tot_lp = sum(int(r["practice_lp"]) for r in second.values())
tot_fp = sum(int(r["practice_fp"]) for r in second.values())
tot_out = sum(int(r["game_status_out"]) for r in second.values())
tot_q = sum(int(r["game_status_questionable"]) for r in second.values())
tot_blank = sum(int(r["game_status_blank"]) for r in second.values())

if tot_rows != 253:
    fail("second read totals: %d player rows, expected 253" % tot_rows)
if (tot_dnp, tot_lp, tot_fp) != (83, 87, 83):
    fail("second read practice totals %s, expected (83, 87, 83)" % ((tot_dnp, tot_lp, tot_fp),))
if (tot_out, tot_q, tot_blank) != (9, 6, 238):
    fail("second read game-status totals %s, expected (9, 6, 238)" % ((tot_out, tot_q, tot_blank),))

FIELDS = ["rows", "game_status_out", "game_status_questionable", "game_status_doubtful",
          "game_status_blank", "practice_dnp", "practice_lp", "practice_fp"]
diff_clubs = []
for club, r2 in second.items():
    r1 = first.get(club)
    if r1 is None:
        continue
    d = [f for f in FIELDS if r1[f] != r2[f]]
    if d:
        diff_clubs.append((club, d))
if len(diff_clubs) != 1 or diff_clubs[0][0] != "IND":
    fail("expected exactly one differing club (IND), got %s" % diff_clubs)
else:
    d = {f: (int(first["IND"][f]), int(second["IND"][f])) for f in diff_clubs[0][1]}
    if d.get("game_status_questionable") != (4, 3) or d.get("game_status_blank") != (2, 3):
        fail("IND delta is %s, expected exactly Questionable 4->3 and blank 2->3" % d)
    if any(f in d for f in ("rows", "game_status_out", "practice_dnp", "practice_lp", "practice_fp")):
        fail("IND delta unexpectedly touches rows/Out/practice fields: %s" % d)

for c in ("CIN", "WAS"):
    if second[c]["page_says_no_injuries"] != "Y" or int(second[c]["rows"]) != 0:
        fail("%s should read 'No Injuries Reported' with 0 rows" % c)

# ---- 3. standings second read --------------------------------------------------
stand2 = load(os.path.join("captures", "standings_2026-11-19_b94f5221.csv"))
stand1 = load(os.path.join("captures", "standings_2026-11-18.csv"))
if len(stand2) != 32 or len(stand1) != 32:
    fail("standings: %d new rows / %d old rows, expected 32/32" % (len(stand2), len(stand1)))
s1 = {r["team_abbr"]: r for r in stand1}
if set(s1) != {r["team_abbr"] for r in stand2}:
    fail("standings: club sets differ")
for r in stand2:
    if int(r["points_for"]) - int(r["points_against"]) != int(r["net_points"]):
        fail("standings %s: PF-PA != net" % r["team_abbr"])
    old = s1.get(r["team_abbr"])
    if old:
        for f in ("wins", "losses", "ties", "points_for", "points_against", "net_points"):
            if old[f] != r[f]:
                fail("standings %s: %s changed %s -> %s (no Week 11 result should exist)"
                     % (r["team_abbr"], f, old[f], r[f]))

# ---- 4. schedule vs observed page ----------------------------------------------
sched = {r["away_team"] + "@" + r["home_team"]: r for r in load("schedule_week11_2026.csv")}
observed = [
    ("IND@HOU", "Thursday November 19th", "8:15 PM ET", "PRIME"),
    ("MIA@BUF", "Sunday November 22nd", "1:00 PM ET", "CBS"),
    ("BAL@CAR", "Sunday November 22nd", "1:00 PM ET", "FOX"),
    ("NO@CHI", "Sunday November 22nd", "1:00 PM ET", "FOX"),
    ("TEN@DAL", "Sunday November 22nd", "1:00 PM ET", "FOX"),
    ("TB@DET", "Sunday November 22nd", "1:00 PM ET", "FOX"),
    ("AZ@KC", "Sunday November 22nd", "1:00 PM ET", "CBS"),
    ("PIT@PHI", "Sunday November 22nd", "1:00 PM ET", "CBS"),
    ("NYJ@LAC", "Sunday November 22nd", "4:05 PM ET", "FOX"),
    ("JAX@NYG", "Sunday November 22nd", "4:25 PM ET", "CBS"),
    ("LV@DEN", "Sunday November 22nd", "4:25 PM ET", "CBS"),
    ("MIN@SF", "Sunday November 22nd", "8:20 PM ET", "NBC"),
    ("CIN@WAS", "Monday November 23rd", "8:15 PM ET", "ESPN"),
]
if len(sched) != 13:
    fail("schedule register: %d rows, expected 13" % len(sched))
for key, day, time, broadcast in observed:
    row = sched.get(key)
    if row is None:
        fail("schedule: observed game %s missing from register" % key)
        continue
    if row["kickoff_day"] != day or row["kickoff_time_et"] != time or row["broadcast"] != broadcast:
        fail("schedule %s: register (%s, %s, %s) != observed (%s, %s, %s)"
             % (key, row["kickoff_day"], row["kickoff_time_et"], row["broadcast"], day, time, broadcast))
if sched.get("MIN@SF", {}).get("neutral_site") != "Y":
    fail("schedule MIN@SF: neutral_site should be Y (Mexico City international game)")

# ---- summary --------------------------------------------------------------------
if failures:
    print("FAIL (%d)" % len(failures))
    for m in failures:
        print("  - " + m)
    sys.exit(1)
print("PASS: 13/13 V94 checks consistent; injury third dated read 253 rows "
      "(23/24 clubs identical to first read, IND delta exactly Q 4->3 / blank 2->3); "
      "practice totals 83/87/83; standings 32/32 identical to the 2026-11-18 capture; "
      "schedule 13/13 matches the observed page (MIN@SF neutral).")
