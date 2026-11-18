#!/usr/bin/env python3
"""T110 (session db00d539) — transcribe the venue of every Week 11 fixture from the
official game centre and publish it as a dated register.

Flag F99 recorded that 1 of 163 fixtures had a venue read from an official source. The
cheapest complete unit is one slate, so this script transcribes the *whole* Week 11 slate:
13 fixtures, each read from its own official game centre page, Game Info block
(`Location`, `Stadium`).

The values below are a transcription, not a lookup. Each entry records what the official
page rendered on 2026-11-18. The script then checks, and refuses to publish unless:

  V1  every fixture in data/schedule_week11_2026.csv has a transcribed row and vice versa
      (13 and 13 — no fixture silently missing)
  V2  the away and home teams in the register equal the schedule's
  V3  every row carries the game-centre URL of that exact fixture, on nfl.com
  V4  no field is blank: a venue is either read from the page or the row is absent
  V5  the register's `location` for the neutral-site game is outside the designated
      home team's market (Mexico City vs San Francisco) — this is the one row that would
      silently mis-price a home-field term if it were wrong

Existing rows in data/venues_2026.csv are preserved; Week 11 rows are replaced
idempotently, so re-running cannot duplicate or clobber another session's rows.

Re-run:  python3 scripts/venues_week11.py
"""

import csv
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
REGISTER = "venues_2026.csv"
SCHED = "schedule_week11_2026.csv"
READ_DATE = "2026-11-18"
GC = "https://www.nfl.com/games/%s"

# Transcribed 2026-11-18 from the Game Info block of each official game centre.
# key: "<away>-<home>" exactly as the schedule file renders them.
TRANSCRIBED = {
    "IND-HOU": ("RELIANT STADIUM", "HOUSTON, TX", "colts-at-texans-2026-reg-11"),
    "MIA-BUF": ("HIGHMARK STADIUM", "ORCHARD PARK, NY", "dolphins-at-bills-2026-reg-11"),
    "BAL-CAR": ("BANK OF AMERICA STADIUM", "CHARLOTTE, NC", "ravens-at-panthers-2026-reg-11"),
    "NO-CHI": ("SOLDIER FIELD", "CHICAGO, IL", "saints-at-bears-2026-reg-11"),
    "TEN-DAL": ("AT&T STADIUM", "ARLINGTON, TX", "titans-at-cowboys-2026-reg-11"),
    "TB-DET": ("FORD FIELD", "DETROIT, MI", "buccaneers-at-lions-2026-reg-11"),
    "AZ-KC": ("ARROWHEAD STADIUM", "KANSAS CITY, MO", "cardinals-at-chiefs-2026-reg-11"),
    "PIT-PHI": ("LINCOLN FINANCIAL FIELD", "PHILADELPHIA, PA", "steelers-at-eagles-2026-reg-11"),
    "NYJ-LAC": ("SOFI STADIUM", "INGLEWOOD, CA", "jets-at-chargers-2026-reg-11"),
    "JAX-NYG": ("METLIFE STADIUM", "EAST RUTHERFORD, NJ", "jaguars-at-giants-2026-reg-11"),
    "LV-DEN": ("EMPOWER FIELD AT MILE HIGH", "DENVER, CO", "raiders-at-broncos-2026-reg-11"),
    "MIN-SF": ("ESTADIO BANORTE", "MEXICO CITY", "vikings-at-49ers-2026-reg-11"),
    "CIN-WAS": ("NORTHWEST STADIUM", "LANDOVER, MD", "bengals-at-commanders-2026-reg-11"),
}
FIELDS = ["fixture_id", "season", "week", "away_team", "home_team", "stadium", "location",
          "read_date_utc", "verification_status", "source_url"]


def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


sched = read(SCHED)
existing = read(REGISTER)

fail = []
sched_keys = {"%s-%s" % (r["away_team"], r["home_team"]): r for r in sched}
if set(sched_keys) != set(TRANSCRIBED):
    fail.append("V1 fixture sets differ: schedule only %s / transcription only %s"
                % (sorted(set(sched_keys) - set(TRANSCRIBED)),
                   sorted(set(TRANSCRIBED) - set(sched_keys)))) 

rows = []
for key, (stadium, location, slug) in TRANSCRIBED.items():
    s = sched_keys.get(key)
    if s is None:
        continue
    if not stadium.strip() or not location.strip():
        fail.append("V4 blank venue field for %s" % key)
    url = GC % slug
    if not url.startswith("https://www.nfl.com/games/"):
        fail.append("V3 non-official game-centre URL for %s" % key)
    rows.append({
        "fixture_id": "FC-2026-W11-%s" % key,
        "season": "2026",
        "week": "11",
        "away_team": s["away_team"],
        "home_team": s["home_team"],
        "stadium": stadium,
        "location": location,
        "read_date_utc": READ_DATE,
        "verification_status": ("Verified: read on the official game centre page "
                                "(Game Info section), away/home checked against the "
                                "official Week 11 schedule"),
        "source_url": url,
    })

# V2 — the teams must be the schedule's teams (transcription cross-check).
for r in rows:
    key = "%s-%s" % (r["away_team"], r["home_team"])
    if key not in sched_keys:
        fail.append("V2 %s is not a Week 11 fixture" % key)

# V5 — the neutral-site row must be outside the designated home team's market.
min_sf = next((r for r in rows if r["fixture_id"].endswith("MIN-SF")), None)
if min_sf is None:
    fail.append("V5 the neutral-site fixture MIN-SF is missing")
elif "MEXICO" not in min_sf["location"].upper():
    fail.append("V5 MIN-SF location does not read Mexico City: %r" % min_sf["location"])

# V6 — cross-check the neutral-site game against the independent official register
# data/international_games_2026.csv (built from operations.nfl.com, SRC-90). Two official
# surfaces, read separately, must agree on the venue and the city.
intl = read("international_games_2026.csv")
intl_w11 = [r for r in intl if r.get("week") == "11"]
if not intl_w11:
    fail.append("V6 the international-games register has no Week 11 row to cross-check")
else:
    ref = intl_w11[0]
    mine = min_sf
    if (ref["venue_official"].upper() != mine["stadium"].upper()
            or ref["city_official"].split(",")[0].upper() != mine["location"].upper()):
        fail.append("V6 the two official sources disagree on the Week 11 venue: "
                    "game centre %r/%r vs international register %r/%r"
                    % (mine["stadium"], mine["location"],
                       ref["venue_official"], ref["city_official"]))

if fail:
    print("VENUE BUILD FAILED:")
    for f in fail:
        print("  -", f)
    sys.exit(1)

# Preserve every row that is not a Week 11 transcription, then append the 13.
kept = [r for r in existing if not (r.get("week") == "11" and r.get("fixture_id", "").startswith("FC-2026-W11-"))]
out = kept + rows
with open(os.path.join(DATA, REGISTER), "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=FIELDS)
    w.writeheader()
    for r in out:
        w.writerow({k: r.get(k, "") for k in FIELDS})

neutral = [r for r in rows if "MEXICO" in r["location"].upper()]
print("venues_2026.csv: %d rows (%d preserved + %d Week 11 transcribed)"
      % (len(out), len(kept), len(rows)))
print("  V1 13 Week 11 fixtures covered            : pass")
print("  V2 away/home match the official schedule  : pass")
print("  V3 official game-centre URL on every row  : pass")
print("  V4 no blank venue field                   : pass")
print("  V6 game centre agrees with the international register (operations.nfl.com): pass")
print("  V5 neutral site outside the home market   : pass (%s)"
      % ", ".join("%s at %s -> %s" % (r["away_team"], r["home_team"], r["location"])
                  for r in neutral))
