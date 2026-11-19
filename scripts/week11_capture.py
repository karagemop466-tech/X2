#!/usr/bin/env python3
"""T129 · Week 11 official injury-report capture: private raw rows, published derived summary.

Source: https://www.nfl.com/injuries/ (page heading "Injuries - WEEK 11", read 2026-11-19 UTC).

Raw row-level data (player names, injuries, practice and game status) lives ONLY in
private/injury_week11_2026-11-19.psv. The private/ folder is gitignored and is never
published. The NFL terms question (flag F16) is unresolved, and the brief asks that raw
row-level data stay private until the terms are read.

This script reads that file, checks it against pinned counts and vocabularies, and
writes only derived output:
  data/injury_week11_2026-11-19_by_club.csv      one row per club: counts, no names
  data/captures/injury_week11_2026-11-19.meta.json  capture record: read window, hashes, flags

It fails loudly (exit 1) on any structural violation, so a bad transcription cannot
publish quietly. Pins below were set when the transcription was checked against the
page's own game list and bye list.
"""
import csv
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PRIVATE = os.path.join(ROOT, "private", "injury_week11_2026-11-19.psv")
SCHEDULE = os.path.join(ROOT, "data", "schedule_week11_2026.csv")
OUT_CSV = os.path.join(ROOT, "data", "injury_week11_2026-11-19_by_club.csv")
OUT_META = os.path.join(ROOT, "data", "captures", "injury_week11_2026-11-19.meta.json")

SOURCE_URL = "https://www.nfl.com/injuries/"
SCHEDULE_URL = "https://www.nfl.com/schedules/2026/by-week/week-11"
READ_CLOCK_CHECK_UTC = "2026-11-19T06:53:35Z"  # session clock read AFTER chunk 0 and BEFORE chunks 1-6; chunk 0 time is not recorded

# Pins (set from the page itself, 2026-11-19)
PIN_ROWS = 253
PIN_CLUBS_WITH_SECTION = 26     # 24 clubs with player rows + 2 clubs with "No Injuries Reported"
PIN_GAMES = 13
PIN_NO_INJURY_CLUBS = ["CIN", "WAS"]
PIN_BYE_CLUBS = ["ATL", "CLE", "GB", "LA", "NE", "SEA"]
PIN_PRACTICE = {"DNP", "LP", "FP"}
PIN_GAME_STATUS = {"", "Out", "Questionable", "Doubtful"}

errors = []


def fail(msg):
    errors.append(msg)


def main():
    if not os.path.exists(PRIVATE):
        print(f"week11_capture: private transcription missing: {PRIVATE} (gitignored; cannot rebuild)")
        return 1

    with open(PRIVATE, encoding="utf-8", newline="") as fh:
        lines = fh.read().splitlines()
    header = lines[0].split("|")
    if header != ["game", "team", "player", "position", "injury", "practice", "game_status"]:
        fail(f"unexpected header {header}")

    rows = []
    for n, line in enumerate(lines[1:], start=2):
        parts = line.split("|")
        if len(parts) != 7:
            fail(f"line {n}: {len(parts)} fields, expected 7")
            continue
        r = dict(zip(header, parts))
        rows.append(r)

    if len(rows) != PIN_ROWS:
        fail(f"row count {len(rows)} != pinned {PIN_ROWS}")
    for r in rows:
        if not r["player"].strip() or not r["position"].strip():
            fail(f"blank player/position: {r}")
        if r["practice"] not in PIN_PRACTICE:
            fail(f"practice vocabulary: {r['player']} = {r['practice']!r}")
        if r["game_status"] not in PIN_GAME_STATUS:
            fail(f"game_status vocabulary: {r['player']} = {r['game_status']!r}")
    dupes = [k for k, v in Counter((r["team"], r["player"]) for r in rows).items() if v > 1]
    if dupes:
        fail(f"duplicate player within club: {dupes}")

    # Schedule cross-check: the page's game list must equal the repo's Week 11 schedule register.
    with open(SCHEDULE, encoding="utf-8", newline="") as fh:
        sched = list(csv.DictReader(fh))
    sched_games = {f"{r['away_team']}@{r['home_team']}": r for r in sched}
    if len(sched_games) != PIN_GAMES:
        fail(f"schedule register has {len(sched_games)} games, pinned {PIN_GAMES}")

    game_of_team = {}
    games_seen = defaultdict(set)
    for r in rows:
        label = r["game"]
        matchup = label.split(" ", 1)[1]
        away, home = matchup.split("@")
        if r["team"] not in (away, home):
            fail(f"team {r['team']} not in game {matchup}")
        if matchup not in sched_games:
            fail(f"game {matchup} not on the Week 11 schedule register")
        game_of_team[r["team"]] = matchup
        games_seen[matchup].add(r["team"])

    clubs_with_rows = set(game_of_team)
    all_clubs = set()
    for m in sched_games:
        a, h = m.split("@")
        all_clubs.update([a, h])
    no_injury = [c for c in PIN_NO_INJURY_CLUBS]
    clubs_section = clubs_with_rows | set(no_injury)
    if len(clubs_section) != PIN_CLUBS_WITH_SECTION:
        fail(f"clubs with a section = {len(clubs_section)}, pinned {PIN_CLUBS_WITH_SECTION}")
    # Bye clubs cannot be derived from the schedule (they have no game); they are pinned from the
    # official Week 11 bye list (data/verification_inputs/week11_byes_2026-11-18.tsv). Check they are
    # disjoint from the playing clubs and that playing + bye = 32 clubs.
    byes = sorted(PIN_BYE_CLUBS)
    if all_clubs & set(byes):
        fail(f"bye clubs overlap scheduled clubs: {sorted(all_clubs & set(byes))}")
    if len(all_clubs | set(byes)) != 32:
        fail(f"playing + bye clubs = {len(all_clubs | set(byes))}, expected 32")
    for c in no_injury:
        if c in clubs_with_rows:
            fail(f"{c} is pinned as 'No Injuries Reported' but has player rows")

    if errors:
        for e in errors:
            print("FAIL", e)
        print(f"week11_capture: {len(errors)} check(s) failed; nothing written.")
        return 1

    # Derived per-club summary: counts only, no player names.
    per = defaultdict(Counter)
    for r in rows:
        per[r["team"]]["rows"] += 1
        per[r["team"]][f"status_{r['game_status'] or 'blank'}"] += 1
        per[r["team"]][f"practice_{r['practice']}"] += 1

    read_end = datetime.fromtimestamp(os.path.getmtime(PRIVATE), tz=timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    window = (f"chunks 1-6 read after {READ_CLOCK_CHECK_UTC}; chunk 0 read earlier in the same session (its time was "
              f"not recorded); transcription file written by {read_end} (session clock; the fetch tool returns no "
              f"per-request time)")

    out_rows = []
    for m in sorted(sched_games, key=lambda k: int(sched_games[k]["game_no"])):
        a, h = m.split("@")
        for club in (a, h):
            c = per.get(club, Counter())
            is_none = club in no_injury
            out_rows.append({
                "club": club,
                "game": m,
                "kickoff": f"{sched_games[m]['kickoff_day']} {sched_games[m]['kickoff_time_et']}",
                "rows": c["rows"],
                "game_status_out": c["status_Out"],
                "game_status_questionable": c["status_Questionable"],
                "game_status_doubtful": c["status_Doubtful"],
                "game_status_blank": c["status_blank"],
                "practice_dnp": c["practice_DNP"],
                "practice_lp": c["practice_LP"],
                "practice_fp": c["practice_FP"],
                "page_says_no_injuries": "Y" if is_none else "N",
                "source_url": SOURCE_URL,
                "read_window_utc": window,
            })
    assert len(out_rows) == 2 * PIN_GAMES

    with open(OUT_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)

    with open(PRIVATE, "rb") as fh:
        psv_sha = hashlib.sha256(fh.read()).hexdigest()
    status_totals = Counter(r["game_status"] or "blank" for r in rows)
    practice_totals = Counter(r["practice"] for r in rows)
    meta = {
        "capture_id": "INJ-W11-2026-11-19",
        "source_url": SOURCE_URL,
        "page_heading": "Injuries - WEEK 11",
        "page_title": "Official Latest NFL Injury Report for Players - Week 11 of the 2026 Season | NFL.com",
        "schedule_source_url": SCHEDULE_URL,
        "read_window_utc": window,
        "read_clock_check_utc": READ_CLOCK_CHECK_UTC,
        "method": "fetch_page tool, chunks 0-6 (totalChunks=7, hasMore=false on chunk 6) read in full; every "
                  "player row transcribed by hand into the private PSV; checked by scripts/week11_capture.py "
                  "against the page's own game list and bye list, and against data/schedule_week11_2026.csv",
        "raw_bytes_retained": False,
        "raw_bytes_note": "The fetch tool returns processed markdown, not the HTTP body, so no hash of the server's "
                          "raw bytes exists. The sha256 below covers the private transcription only.",
        "private_transcription": "private/injury_week11_2026-11-19.psv (gitignored; not published)",
        "private_transcription_sha256": psv_sha,
        "rows_transcribed": len(rows),
        "clubs_with_section": PIN_CLUBS_WITH_SECTION,
        "clubs_with_player_rows": len(clubs_with_rows),
        "games": len(sched_games),
        "games_with_player_rows": len(games_seen),
        "no_injuries_reported_clubs": no_injury,
        "bye_clubs_without_section": byes,
        "practice_totals": dict(practice_totals),
        "game_status_totals": dict(status_totals),
        "delta": "none: first read of the Week 11 report. The delta series starts with the next read (T129 "
                 "follow-up). A delta is only meaningful between reads of the same week.",
        "published_layer": "derived counts per club only (data/injury_week11_2026-11-19_by_club.csv)",
        "raw_rows_published": False,
        "verification_status": "single transcription read, not yet independently re-read (flag F129)",
        "flags": ["F129", "F126", "F16"],
    }
    with open(OUT_META, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print(f"week11_capture: {len(rows)} rows, {len(clubs_section)} club sections, {len(sched_games)} games, "
          f"byes {byes}. Wrote {os.path.relpath(OUT_CSV, ROOT)} and {os.path.relpath(OUT_META, ROOT)}.")
    print(f"private sha256 {psv_sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
