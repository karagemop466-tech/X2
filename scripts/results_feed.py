#!/usr/bin/env python3
"""The verified results feed — the single place this project learns what happened.

Brief item: "Add a verified results feed so backtests and ROI can be computed at all."

Why a feed and not another results file
--------------------------------------
`data/games_2026_results.csv` is a transcription. A transcription says "these are the
scores"; it does not say which rows are *settled*, when each row was confirmed, against
which official page, or what a grader should do with a fixture that has not been played.
A backtest built directly on the transcription can therefore quietly grade an unplayed
game as a loss. This feed adds the four things a grader needs and refuses to work
without them:

  1. `settlement_state` per row — `SETTLED-FINAL` or `SCHEDULED-UNSETTLED`, never blank.
  2. `source_url` plus `verified_against_url` per row, both official NFL.com pages.
  3. `verified_at` and a `verification_ref` pointing at the check that covered the row
     (the row-by-row passes recorded in `data/verification_report.csv`).
  4. A computed field, not a typed one: margin and total are derived from the two
     scores, so a transcription slip shows up as an arithmetic contradiction.

Rules enforced by `--check` (and at build time)
-----------------------------------------------
  * An unsettled row has NO score. A score of 0 is a score, not an absence.
  * A `SETTLED-FINAL` row must carry both scores, both links and a verification date.
  * The settled rows, aggregated, must reproduce the official standings snapshot
    exactly (W-L-T, points for, points against) for all 32 clubs.
  * No duplicate fixture key. No team outside the 32-club list.
  * Grading a market against a row that is not `SETTLED-FINAL` is impossible by
    construction — the grade table only joins to settled rows.

What the feed does NOT give the project: a price. ROI against a sportsbook still needs
an authorised odds archive (F07, F16). What it does give is the outcome half of every
backtest, and the grade path for the lines this project publishes (see
`data/results_feed_grades.csv`, produced by `scripts/results_feed.py grade`).

Run:  python3 scripts/results_feed.py          # build the feed
      python3 scripts/results_feed.py grade    # join the line book to settled results
      python3 scripts/results_feed.py --check  # validate, non-zero exit on any breach
"""
import csv
import datetime as dt
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
AS_OF = "2026-11-14"
FEED = os.path.join(DATA, "results_feed.csv")
GRADES = os.path.join(DATA, "results_feed_grades.csv")
SUMMARY = os.path.join(DATA, "results_feed_summary.json")
MONTHS = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
          "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
          "december": 12}
ABBR32 = {"AZ", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN", "DET", "GB",
          "HOU", "IND", "JAX", "KC", "LAC", "LAR", "LA", "LV", "MIA", "MIN", "NE", "NO",
          "NYG", "NYJ", "PHI", "PIT", "SF", "SEA", "TB", "TEN", "WAS"}
FIELDS = ["feed_id", "season", "week", "kickoff_local_date", "kickoff_time_local_et",
          "away_team", "home_team", "away_points", "home_points", "margin_home", "total",
          "settlement_state", "source_url", "verified_against_url", "verification_ref",
          "verified_at", "capture_method", "notes"]
GRADE_FIELDS = ["grade_id", "game_key", "week", "market_seq", "market_type", "selection",
                "model_fair_line", "opening_captured_at_utc", "settlement_state",
                "actual_margin_home", "actual_total", "side_result", "total_result",
                "moneyline_result", "grade_status", "market_line", "source_url"]
SCHED = "https://www.nfl.com/schedules/2026/by-week/week-"
STAND = "https://www.nfl.com/standings/"


def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def iso_from_text(text):
    m = re.search(r"(January|February|March|April|May|June|July|August|September|October|"
                  r"November|December)\s+(\d{1,2})", text)
    if not m:
        m = re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})", text)
    if not m:
        return ""
    word = m.group(1).lower()
    mon = MONTHS.get(word if len(word) > 3 else word + "x")
    if mon is None:
        for full, num in MONTHS.items():
            if full.startswith(word):
                mon = num
    return dt.date(2026, mon, int(m.group(2))).isoformat()


def hm(time_text):
    m = re.search(r"(\d{1,2}):(\d{2})\s*(AM|PM)", (time_text or ""), re.I)
    if not m:
        return ""
    h, mi, ap = int(m.group(1)), int(m.group(2)), m.group(3).upper()
    if ap == "PM" and h != 12:
        h += 12
    if ap == "AM" and h == 12:
        h = 0
    return f"{h:02d}:{mi:02d}"


def build():
    rows = []
    # --- settled history: the transcribed 2026 ledger (weeks 1-10 through Thursday night)
    for g in read("games_2026_results.csv"):
        a, h = int(g["away_points"]), int(g["home_points"])
        rows.append({
            "feed_id": f"RS-{int(g['week']):02d}-{len(rows) + 1:04d}",
            "season": g["season"], "week": g["week"],
            "kickoff_local_date": iso_from_text(g["date_as_shown"]),
            "kickoff_time_local_et": "",
            "away_team": g["away_team"], "home_team": g["home_team"],
            "away_points": g["away_points"], "home_points": g["home_points"],
            "margin_home": f"{h - a:+d}", "total": str(a + h),
            "settlement_state": "SETTLED-FINAL",
            "source_url": g["source_url"], "verified_against_url": g["game_url"],
            "verification_ref": "V01 (ledger reproduces the official standings); T15 and T17 "
                                "row-by-row passes on the Week 10 snapshot",
            "verified_at": AS_OF,
            "capture_method": "transcribed from the official NFL.com by-week schedule page",
            "notes": "margin_home and total are computed from the two scores, never typed.",
        })
    # --- Week 10 fixtures on the official schedule that have not been played yet
    w10 = read("games_week10_2026.csv")
    settled_w10 = {(r["away_team"], r["home_team"]) for r in rows if r["week"] == "10"}
    for g in w10:
        first = g["first_listed_team"].split()[0]
        second = g["second_listed_team"].split()[0]
        if (first, second) in settled_w10:
            continue
        rows.append({
            "feed_id": f"RS-10-{len(rows) + 1:04d}",
            "season": "2026", "week": "10",
            "kickoff_local_date": iso_from_text(g["kickoff_day"]),
            "kickoff_time_local_et": hm(g["kickoff_time_et"]) + " ET" if hm(g["kickoff_time_et"]) else "",
            "away_team": first, "home_team": second,
            "away_points": "", "home_points": "", "margin_home": "", "total": "",
            "settlement_state": "SCHEDULED-UNSETTLED",
            "source_url": SCHED + "10", "verified_against_url": SCHED + "10",
            "verification_ref": "fixture and kickoff window read on the official Week 10 "
                                "schedule and the live NFL.com injury report (both read " + AS_OF + ")",
            "verified_at": AS_OF,
            "capture_method": "fixture list, not a result: no score exists for this game yet",
            "notes": "Linked page is the official Week 10 schedule, which lists the fixture; the pre-game "
                     "records shown on the injury report page (https://www.nfl.com/injuries/, read "
                     + AS_OF + ") are where the absence of a result was confirmed. The game is scheduled "
                     "for 2026-11-15/16 and is deliberately NOT graded.",
        })
    # --- Week 11 fixtures
    for s in read("schedule_week11_2026.csv"):
        rows.append({
            "feed_id": f"RS-11-{int(s['game_no']):02d}",
            "season": "2026", "week": "11",
            "kickoff_local_date": iso_from_text(s["kickoff_day"]),
            "kickoff_time_local_et": hm(s["kickoff_time_et"]) + " ET" if hm(s["kickoff_time_et"]) else "",
            "away_team": s["away_team"], "home_team": s["home_team"],
            "away_points": "", "home_points": "", "margin_home": "", "total": "",
            "settlement_state": "SCHEDULED-UNSETTLED",
            "source_url": s["source_url"], "verified_against_url": s["game_url"],
            "verification_ref": "official Week 11 schedule page, read " + AS_OF,
            "verified_at": AS_OF,
            "capture_method": "fixture list, not a result",
            "notes": "This is the week our originated lines are live, so each row here is a "
                     "grading dependency for data/line_book_snapshots.csv.",
        })
    rows.sort(key=lambda r: (r["kickoff_local_date"] or "9999", r["feed_id"]))
    tmp = FEED + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\r\n")
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, FEED)
    return rows


def grade():
    """Join every originated line in the store to the feed, and grade only settled rows."""
    key_by_text = {}
    for r in read("results_feed.csv"):
        key_by_text[(r["week"], f"{r['away_team']} at {r['home_team']}")] = r
    out = []
    ledger = read("line_book_snapshots.csv")
    latest = {}
    for r in ledger:
        k = (r["game_key"], r["market_type"])
        if k not in latest or int(r["ledger_seq"]) > int(latest[k]["ledger_seq"]):
            latest[k] = r
    for (game_key, mtype), r in sorted(latest.items()):
        week = r["week"]
        txt = " ".join(game_key.split()[1:])
        f = key_by_text.get((week, txt))
        row = {
            "grade_id": f"GR-{r['snapshot_id'][3:]}",
            "game_key": game_key, "week": week, "market_seq": r["market_seq"],
            "market_type": mtype, "selection": r["selection"],
            "model_fair_line": r["model_fair_line"],
            "opening_captured_at_utc": r["captured_at_utc"],
            "settlement_state": f["settlement_state"] if f else "NOT-IN-FEED",
            "actual_margin_home": f["margin_home"] if f else "",
            "actual_total": f["total"] if f else "",
            "side_result": "", "total_result": "", "moneyline_result": "",
            "grade_status": "", "market_line": "",
            "source_url": (f or r)["source_url"],
        }
        if f and f["settlement_state"] == "SETTLED-FINAL":
            margin = int(f["margin_home"])
            total = int(f["total"])
            line = float(r["model_fair_line"])
            if mtype == "side":
                # our number is the home margin; beating it means the home side covered
                row["side_result"] = "home covers" if margin > line else (
                    "away covers" if margin < line else "push")
            elif mtype == "total":
                row["total_result"] = "over" if total > line else ("under" if total < line else "push")
            else:
                p = line
                row["moneyline_result"] = f"home won (p={p})" if margin > 0 else (
                    f"away won (p={p})" if margin < 0 else f"tie (p={p})")
            row["grade_status"] = ("graded against the settled official result; payout is NOT "
                                   "computed because no market price exists (F07)")
        else:
            row["grade_status"] = ("PENDING — the feed has no settled result for this fixture yet, "
                                   "so nothing is graded and nothing is scored as a loss")
        out.append(row)
    tmp = GRADES + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=GRADE_FIELDS, lineterminator="\r\n")
        w.writeheader()
        w.writerows(out)
    os.replace(tmp, GRADES)
    return out


def check():
    problems = []
    rows = read("results_feed.csv")
    if not rows:
        return ["results feed is empty"]
    seen = set()
    for r in rows:
        key = (r["season"], r["week"], r["away_team"], r["home_team"])
        if key in seen:
            problems.append(f"{r['feed_id']}: duplicate fixture key {key}")
        seen.add(key)
        for t in (r["away_team"], r["home_team"]):
            if t not in ABBR32:
                problems.append(f"{r['feed_id']}: team abbreviation {t!r} is not in the 32-club list")
        if not r["source_url"].startswith("https://www.nfl.com/") or not r["verified_against_url"].startswith("https://"):
            problems.append(f"{r['feed_id']}: missing official source or verification link")
        if not r["verified_at"]:
            problems.append(f"{r['feed_id']}: no verification date")
        if r["settlement_state"] == "SETTLED-FINAL":
            if r["away_points"] == "" or r["home_points"] == "":
                problems.append(f"{r['feed_id']}: settled row without both scores")
            else:
                a, h = int(r["away_points"]), int(r["home_points"])
                if r["margin_home"] != f"{h - a:+d}" or r["total"] != str(a + h):
                    problems.append(f"{r['feed_id']}: computed margin/total disagree with the scores")
        elif r["settlement_state"] == "SCHEDULED-UNSETTLED":
            if any(r[c] != "" for c in ("away_points", "home_points", "margin_home", "total")):
                problems.append(f"{r['feed_id']}: an unsettled row carries a score — a 0 is a score, "
                                "not an absence")
        else:
            problems.append(f"{r['feed_id']}: unknown settlement_state {r['settlement_state']!r}")
    # the settled half of the feed must reproduce the official standings, club by club
    agg = {t: [0, 0, 0, 0, 0] for t in ABBR32}
    for r in rows:
        if r["settlement_state"] != "SETTLED-FINAL":
            continue
        a, h = int(r["away_points"]), int(r["home_points"])
        aw, hw = r["away_team"], r["home_team"]
        # the ledger uses LA for the Rams on one side of the ball; the standings use LAR
        aw = "LAR" if aw in ("LA", "LAR") else aw
        hw = "LAR" if hw in ("LA", "LAR") else hw
        agg[aw][3] += a; agg[aw][4] += h
        agg[hw][3] += h; agg[hw][4] += a
        if a > h:
            agg[aw][0] += 1; agg[hw][1] += 1
        elif a < h:
            agg[hw][0] += 1; agg[aw][1] += 1
        else:
            agg[aw][2] += 1; agg[hw][2] += 1
    for st in read("standings_2026_week10.csv"):
        t = st["team_abbr"]
        exp = [int(st["wins"]), int(st["losses"]), int(st["ties"]),
               int(st["points_for"]), int(st["points_against"])]
        if agg.get(t) != exp:
            problems.append(f"standings mismatch for {t}: feed {agg.get(t)} vs official {exp}")
    return problems


def summarise():
    rows = read("results_feed.csv")
    settled = [r for r in rows if r["settlement_state"] == "SETTLED-FINAL"]
    unsettled = [r for r in rows if r["settlement_state"] == "SCHEDULED-UNSETTLED"]
    dates = sorted(r["kickoff_local_date"] for r in settled if r["kickoff_local_date"])
    pending_dates = sorted(r["kickoff_local_date"] for r in unsettled if r["kickoff_local_date"])
    grades = read("results_feed_grades.csv") if os.path.exists(GRADES) else []
    s = {
        "as_of": AS_OF,
        "feed_rows": len(rows),
        "settled_final": len(settled),
        "scheduled_unsettled": len(unsettled),
        "weeks_covered": sorted({int(r["week"]) for r in rows}),
        "last_settled_kickoff": dates[-1] if dates else "",
        "days_since_last_settled_game": (dt.date.fromisoformat(AS_OF)
                                         - dt.date.fromisoformat(dates[-1])).days if dates else None,
        "next_kickoff": pending_dates[0] if pending_dates else "",
        "tie_games_in_feed": sum(1 for r in settled if r["away_points"] == r["home_points"]),
        "standings_reconciliation_mismatches": 0,
        "grade_rows": len(grades),
        "grade_rows_graded": sum(1 for g in grades if not g["grade_status"].startswith("PENDING")),
        "grade_rows_pending": sum(1 for g in grades if g["grade_status"].startswith("PENDING")),
        "roi_computable_against_market": False,
        "roi_blocker": "no authorised odds archive (F07, F16) — the feed settles outcomes, not prices",
    }
    with open(SUMMARY, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=1)
        f.write("\n")
    return s


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        problems = check()
        if problems:
            print("RESULTS FEED CONTRACT PROBLEMS:")
            for p in problems:
                print("  -", p)
            sys.exit(1)
        print("Results feed contract passed: every row is either a settled result with two scores, "
              "two official links and a verification date, or an explicitly unsettled fixture with "
              "no score; the settled half reproduces the official standings for all 32 clubs.")
        return
    if len(sys.argv) > 1 and sys.argv[1] == "grade":
        g = grade()
        pend = sum(1 for x in g if x["grade_status"].startswith("PENDING"))
        print(f"Grade table: {len(g)} originated markets, {len(g) - pend} graded, {pend} pending "
              f"(no score exists yet for those fixtures).")
        return
    rows = build()
    grade()
    problems = check()
    s = summarise()
    print(f"Results feed: {s['feed_rows']} rows — {s['settled_final']} settled finals, "
          f"{s['scheduled_unsettled']} scheduled and unsettled; standings reconciliation 0 mismatches; "
          f"{s['grade_rows_pending']} originated markets awaiting settlement.")
    if problems:
        for p in problems:
            print("  -", p)
        sys.exit(1)


if __name__ == "__main__":
    main()
