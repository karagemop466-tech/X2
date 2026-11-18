#!/usr/bin/env python3
"""Verify the transcribed results against the official standings, line by line.

Reads data/games_2026_results.csv (transcribed from the official NFL.com
by-week schedule pages) and data/standings_2026_snapshot.csv (transcribed from
the official NFL.com standings page, read 2026-11-14), recomputes every team's
record and points from the games, and reports any mismatch.

Read provenance (flag F106, added 2026-11-18, session 60c8c865). The original
script printed only "All teams reconcile exactly with the official standings",
which hid two facts a reader needs:

  1. the read date of the checked data (the feed: verified 2026-11-14,
     newest game Thursday 2026-11-12) and of the checking source (the
     standings snapshot: read 2026-11-14, taken before the Week 10 Sunday
     games), and
  2. that a newer official standings read exists in this repository
     (data/captures/standings_2026-11-18.csv, read 2026-11-18) against
     which the frozen feed does NOT reconcile: 26 of 32 clubs differ,
     because the feed holds 137 games and the newer read implies 150
     (the 13 settled Week 10 games the feed does not carry, F96).

So the script now runs three checks and prints every read date:

  A. primary   - feed vs the frozen official read of 2026-11-14 (the
                 reconciliation the site has always published);
  B. currency  - feed vs the newer official read of 2026-11-18 (expected
                 to differ for 26 clubs; this is the F106 warning, not an
                 arithmetic failure);
  C. explained - feed plus data/games_week10_backfill_2026.csv (the 13
                 official Week 10 finals, transcribed from the by-week
                 page) vs the 2026-11-18 read. This must be 32 of 32: it
                 proves the currency gap is exactly the missing tranche
                 and nothing else.

Exit code 0 means check A passed AND check C passed (the gap is fully
explained by the official tranche). Exit 1 means the arithmetic is broken
or the gap is NOT explained by the backfill - a real data problem.

Run:  python3 scripts/verify_results.py
"""
import csv
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")

MONTHS = {"January": 1, "February": 2, "March": 3, "April": 4, "May": 5,
          "June": 6, "July": 7, "August": 8, "September": 9, "October": 10,
          "November": 11, "December": 12}

FROZEN_READ_FILE = "standings_2026_official_read_20261114.csv"  # date in name
NEWER_READ_FILE = os.path.join("captures", "standings_2026-11-18.csv")
BACKFILL_FILE = "games_week10_backfill_2026.csv"
FEED_VERIFIED_FILE = "results_feed.csv"  # carries verified_on per game row


def read(name):
    path = name if os.path.isabs(name) else os.path.join(DATA, name)
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def record(games):
    rec = defaultdict(lambda: {"W": 0, "L": 0, "T": 0, "PF": 0, "PA": 0})
    for g in games:
        a, h = int(g["away_points"]), int(g["home_points"])
        for team, pf, pa in ((g["away_team"], a, h), (g["home_team"], h, a)):
            rec[team]["PF"] += pf
            rec[team]["PA"] += pa
            if pf > pa:
                rec[team]["W"] += 1
            elif pf < pa:
                rec[team]["L"] += 1
            else:
                rec[team]["T"] += 1
    return rec


def compare(rec, standings):
    """Return (matched, problems) comparing recomputed records to a standings dict."""
    matched, problems = 0, []
    for team, r in sorted(rec.items()):
        s = standings.get(team)
        if s is None:
            problems.append(f"{team}: no official standings row to compare against")
            continue
        exp = (int(s["wins"]), int(s["losses"]), int(s["ties"]),
               int(s["points_for"]), int(s["points_against"]))
        got = (r["W"], r["L"], r["T"], r["PF"], r["PA"])
        if exp == got:
            matched += 1
        else:
            problems.append(
                f"{team}: computed {got} but official standings say {exp}")
    for team in sorted(standings):
        if team not in rec:
            problems.append(f"{team}: appears in the official standings but has no game rows")
    return matched, problems


def newest_game_date(games):
    """Newest date_as_shown in the feed, as a date (e.g. 'Thursday November 12th')."""
    from datetime import date
    best = None
    for g in games:
        m = re.search(r"([A-Za-z]+) (\d{1,2})(?:st|nd|rd|th)?\b", g.get("date_as_shown", ""))
        if not m or m.group(1) not in MONTHS:
            continue
        cand = date(int(g.get("season") or 2026), MONTHS[m.group(1)], int(m.group(2)))
        if best is None or cand > best:
            best = cand
    return best


games = read("games_2026_results.csv")
standings = {r["team_abbr"]: r for r in read("standings_2026_snapshot.csv")}

# ---- provenance: read dates of the checked data and of the checking source ----
# The snapshot is byte-identical to the dated read file; only then does the
# date embedded in that file's name describe the snapshot.
frozen_read = read(FROZEN_READ_FILE)
same = (len(frozen_read) == len(standings)
        and all(standings[r["team_abbr"]] == r for r in frozen_read))
m_frozen = re.search(r"(\d{8})", FROZEN_READ_FILE)
frozen_read_date = (frozen_read[0]["read_date"] if frozen_read and "read_date" in frozen_read[0]
                    else (f"{m_frozen.group(1)[0:4]}-{m_frozen.group(1)[4:6]}-{m_frozen.group(1)[6:8]}"
                          if m_frozen else "unknown"))
if not same:
    print("PROVENANCE FAILURE: data/standings_2026_snapshot.csv is not identical to "
          f"data/{FROZEN_READ_FILE}; the frozen read date cannot be claimed.")
    sys.exit(1)

feed_verified = read(FEED_VERIFIED_FILE)
feed_read_dates = sorted({r.get("verified_on", "").strip() for r in feed_verified
                          if r.get("verified_on", "").strip()})
feed_read_date = feed_read_dates[-1] if feed_read_dates else "not recorded"
if len(feed_read_dates) > 1:
    feed_read_date = ", ".join(feed_read_dates)

newest = newest_game_date(games)
newest_str = newest.isoformat() if newest else "unknown"

newer_read_path = os.path.join(DATA, NEWER_READ_FILE)
newer_read_date, newer = None, None
if os.path.exists(newer_read_path):
    newer_rows = read(newer_read_path)
    newer = {r["team_abbr"]: r for r in newer_rows}
    dates = sorted({r.get("read_date_utc", "").strip() for r in newer_rows
                    if r.get("read_date_utc", "").strip()})
    newer_read_date = dates[-1] if dates else "unknown"

# ---- check A: primary reconciliation against the frozen read ------------------
rec = record(games)
per_week = defaultdict(int)
for g in games:
    per_week[int(g["week"])] += 1

problems_a = []
matched_a, problems_a = compare(rec, standings)

print(f"Games checked: {len(games)}")
print("Games per week: " + ", ".join(f"wk {w}: {n}" for w, n in sorted(per_week.items())))
print(f"Teams compared: {len(rec)}")
print("Read provenance (flag F106):")
print(f"  - checked data: data/games_2026_results.csv, verified_on {feed_read_date} "
      f"(data/{FEED_VERIFIED_FILE}); newest game in the feed {newest_str}")
print(f"  - checking source (primary): data/standings_2026_snapshot.csv = "
      f"official standings read {frozen_read_date} (identical to data/{FROZEN_READ_FILE})")
if newer_read_date:
    print(f"  - newer official read on file: data/{NEWER_READ_FILE} "
          f"(read {newer_read_date}, https://www.nfl.com/standings/)")
if newest and frozen_read_date != "unknown":
    if frozen_read_date < newest_str:
        print(f"  WARNING (F106 rule): the primary source read ({frozen_read_date}) is OLDER "
              f"than the newest game in the data ({newest_str}).")
    else:
        print(f"  F106 rule: primary source read ({frozen_read_date}) is not older than the "
              f"newest game in the data ({newest_str}) - no warning on that rule alone.")

# ---- check C: feed + official Week 10 tranche vs the newer read --------------
backfill = read(BACKFILL_FILE)
combined = games + [{"season": "2026", "week": b["week"],
                     "date_as_shown": b["date_as_shown"],
                     "away_team": b["away_team"], "away_points": b["away_points"],
                     "home_team": b["home_team"], "home_points": b["home_points"]}
                    for b in backfill]
problems_c, matched_c = [], None
if newer is not None:
    rec_combined = record(combined)
    matched_c, problems_c = compare(rec_combined, newer)

# ---- check B: feed vs the newer read (the F106 currency warning) -------------
matched_b, problems_b = ([], None) if newer is None else compare(rec, newer)

if problems_a:
    print("MISMATCHES (primary, frozen read):")
    for p in problems_a:
        print(f"  - {p}")

ok_a = not problems_a
ok_c = (newer is None) or (matched_c == len(newer) and not problems_c)

if newer is None:
    print("Currency check skipped: no newer official standings read is committed.")
else:
    print(f"Currency check (feed vs official read {newer_read_date}): "
          f"{matched_b} of {len(newer)} clubs match, {len(newer) - matched_b} differ.")
    print(f"  WARNING (F106): the frozen feed does not reconcile against the newer official "
          f"read for {len(newer) - matched_b} of {len(newer)} clubs. Cause on file: the feed holds "
          f"{len(games)} games; the newer read implies 150 through Week 10 - the "
          f"{len(backfill)}-game official tranche in data/{BACKFILL_FILE} is not spliced in "
          f"(owner decision P09, flag F96).")
    print(f"  Explained-gap check (feed + {len(backfill)} official Week 10 finals vs the "
          f"{newer_read_date} read): {matched_c} of {len(newer)} clubs match.")
    if not ok_c:
        print("  MISMATCHES (feed + official tranche):")
        for p in problems_c:
            print(f"  - {p}")
        print("  FAIL: the currency gap is NOT fully explained by the official Week 10 tranche.")

print(f"Teams compared: {len(rec)}")
if ok_a and ok_c:
    tail = (f"All teams reconcile exactly with the official standings read of "
            f"{frozen_read_date} (W, L, T, points for, points against).")
    if newer_read_date and matched_b is not None and matched_b != len(newer):
        tail += (f" CURRENCY WARNING (F106): {len(newer) - matched_b} of {len(newer)} clubs differ "
                 f"against the newer official read of {newer_read_date}; the gap is fully explained "
                 f"by the {len(backfill)} official Week 10 finals not yet spliced in (P09/F96).")
    print(tail)
    sys.exit(0)

if not ok_a:
    print("Primary reconciliation FAILED against the frozen official read.")
else:
    print("Primary reconciliation passed, but the explained-gap check FAILED.")
sys.exit(1)
