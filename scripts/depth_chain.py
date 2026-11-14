#!/usr/bin/env python3
"""Depth of the replacement, not just the fact of one (task T42).

The NFL's own weekly injury report tells you *that* a player is out. It does not
tell you how far down the roster the replacement comes from. The only official-
domain source that carries that order is the depth chart each club publishes on
its own website. Those charts are self-labelled "unofficial", so every value
here inherits that caveat.

This script:

  1. reads the club depth charts transcribed from the official club sites into
     data/depth_charts_2026_week10.json (position order = string order),
  2. reads the Week 10 NFL.com injury report (data/injuries_week10_2026.csv),
  3. for every player the official report lists as Out or Doubtful on a club
     that publishes a machine-readable chart, records
       - the string the absent player held (1st / 2nd / 3rd / 4th),
       - the player the chart lists next, and the string that player holds,
       - how many players the chart lists behind the replacement,
  4. leaves every field blank and marks the row UNVERIFIED when the club does
     not publish a readable chart or the player is not on it.

Nothing is inferred. A player who is missing from his club's chart produces a
blank, not a guess.

Run:  python3 scripts/depth_chain.py
"""

import csv
import json
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
AS_OF = "2026-11-14"

ORDINAL = {1: "1st string", 2: "2nd string", 3: "3rd string", 4: "4th string",
           5: "5th string", 6: "6th string"}

UNIT_OF_SECTION = {"offense": "Offense", "defense": "Defense",
                   "special_teams": "Special teams"}


def read_csv(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(name, rows, fields):
    with open(os.path.join(DATA, name), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def norm(name):
    """Normalise a player name for matching: case, punctuation and suffixes."""
    s = name.split("(")[0]
    s = s.lower()
    s = re.sub(r"[^a-z0-9 ]+", "", s)
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", s)
    return " ".join(s.split())


def report_status(injuries, team, player):
    """The replacement's own official game status, if the report lists him."""
    if not player:
        return ""
    key = norm(player)
    for r in injuries:
        if r["team_abbr"] == team and norm(r["player"]) == key and r["game_status"]:
            return "%s (%s)" % (r["game_status"], r["injury"] or "injury not stated")
    return "not listed on the Week 10 injury report"


def co_listed(cell, player):
    """Other names the club chart puts at the same string as this player."""
    parts = [c.strip() for c in cell.split("|")]
    others = [c for c in parts if c and norm(c) != norm(player)]
    return "; ".join(others)


def main():
    with open(os.path.join(DATA, "depth_charts_2026_week10.json"), encoding="utf-8") as f:
        charts = json.load(f)
    injuries = read_csv("injuries_week10_2026.csv")

    rows = []
    n = 0
    for team, chart in charts["charts"].items():
        club_url = chart["url"]
        as_of = chart.get("as_of_as_published") or "not stated on the page"
        for section in ("offense", "defense", "special_teams"):
            for line in chart.get(section, []):
                pos = line["pos"]
                players = line["players"]
                # players[i] holds the (i+1)-th string; a cell may hold two
                # players listed together, which the club chart shows as tied.
                for i, cell in enumerate(players):
                    string_no = i + 1
                    for person in cell.split("|"):
                        pname = person.strip()
                        if not pname:
                            continue
                        key = norm(pname)
                        hits = [r for r in injuries
                                if r["team_abbr"] == team
                                and r["game_status"] in ("Out", "Doubtful")
                                and norm(r["player"]) == key]
                        if not hits:
                            continue
                        for r in hits:
                            n += 1
                            listed = len(players)
                            nxt = players[i + 1] if i + 1 < len(players) else ""
                            behind = listed - (i + 2)
                            if nxt:
                                repl = nxt.split("|")[0].strip()
                                repl_string = ORDINAL.get(i + 2, "%dth string" % (i + 2))
                                depth_behind = max(0, behind)
                                if depth_behind == 0:
                                    tail = ("no further player listed at this "
                                            "spot on the club chart")
                                else:
                                    tail = ("%d further player(s) listed behind "
                                            "him at this spot" % depth_behind)
                                summary = ("%s replaced by %s (%s); %s"
                                           % (ORDINAL.get(string_no, "%dth string" % string_no),
                                              repl, repl_string, tail))
                                status = "Verified against the official club depth chart"
                            else:
                                repl, repl_string, depth_behind = "", "", ""
                                summary = ("%s is the last player the club chart lists at "
                                           "this spot; no replacement is named"
                                           % ORDINAL.get(string_no, "%dth string" % string_no))
                                status = ("UNVERIFIED - the club chart names no replacement; "
                                          "left blank rather than inferred")
                            rows.append({
                                "depth_id": "DR-%s-%02d" % (team, n),
                                "team_abbr": team,
                                "club": chart["club"],
                                "side_of_ball": UNIT_OF_SECTION[section],
                                "chart_position": pos,
                                "player_out": r["player"],
                                "injury_report_position": r["position"],
                                "official_game_status": r["game_status"],
                                "injury_as_reported": r["injury"],
                                "string_of_absent_player": ORDINAL.get(
                                    string_no, "%dth string" % string_no),
                                "players_listed_at_this_spot": listed,
                                "named_replacement": repl,
                                "replacement_string": repl_string,
                                "players_behind_replacement": depth_behind,
                                "replacement_also_on_injury_report": report_status(
                                    injuries, team, repl),
                                "co_listed_at_same_string": co_listed(cell, pname),
                                "depth_of_replacement_summary": summary,
                                "chart_as_of": as_of,
                                "chart_url": club_url,
                                "injury_source_url": r["source_url"],
                                "verification_status": status,
                            })

    # ---- players who are Out/Doubtful on a covered club but absent from its chart
    covered = set(charts["charts"])
    listed_names = {}
    for team, chart in charts["charts"].items():
        s = set()
        for section in ("offense", "defense", "special_teams"):
            for line in chart.get(section, []):
                for cell in line["players"]:
                    for person in cell.split("|"):
                        if person.strip():
                            s.add(norm(person))
        listed_names[team] = s

    missing = []
    for r in injuries:
        if r["game_status"] not in ("Out", "Doubtful"):
            continue
        if r["team_abbr"] not in covered:
            continue
        if norm(r["player"]) in listed_names[r["team_abbr"]]:
            continue
        n += 1
        chart = charts["charts"][r["team_abbr"]]
        missing.append({
            "depth_id": "DR-%s-%02d" % (r["team_abbr"], n),
            "team_abbr": r["team_abbr"],
            "club": chart["club"],
            "side_of_ball": "",
            "chart_position": "",
            "player_out": r["player"],
            "injury_report_position": r["position"],
            "official_game_status": r["game_status"],
            "injury_as_reported": r["injury"],
            "string_of_absent_player": "",
            "players_listed_at_this_spot": "",
            "named_replacement": "",
            "replacement_string": "",
            "players_behind_replacement": "",
                            "replacement_also_on_injury_report": "",
                            "co_listed_at_same_string": "",
            "depth_of_replacement_summary": ("The official report lists him %s, but the club's "
                                             "own depth chart does not list him at any position, "
                                             "so no string and no replacement can be read from "
                                             "an official source"
                                             % r["game_status"].lower()),
            "chart_as_of": chart.get("as_of_as_published") or "not stated on the page",
            "chart_url": chart["url"],
            "injury_source_url": r["source_url"],
            "verification_status": ("UNVERIFIED - absent from the club depth chart; left blank "
                                    "rather than inferred"),
        })

    rows.extend(missing)
    rows.sort(key=lambda r: (r["team_abbr"], r["depth_id"]))

    fields = ["depth_id", "team_abbr", "club", "side_of_ball", "chart_position",
              "player_out", "injury_report_position", "official_game_status",
              "injury_as_reported", "string_of_absent_player",
              "players_listed_at_this_spot", "named_replacement",
              "replacement_string", "players_behind_replacement",
              "replacement_also_on_injury_report", "co_listed_at_same_string",
              "depth_of_replacement_summary", "chart_as_of", "chart_url",
              "injury_source_url", "verification_status"]
    write_csv("depth_replacement.csv", rows, fields)

    named = sum(1 for r in rows if r["named_replacement"])
    print("depth_replacement.csv: %d rows (%d with an officially named replacement, "
          "%d blank and flagged)" % (len(rows), named, len(rows) - named))
    print("clubs with a machine-readable chart: %s" % ", ".join(sorted(charts["charts"])))
    for t, note in sorted(charts["coverage_notes"]["club_chart_retrieved_but_not_machine_readable"].items()):
        print("  %s: %s" % (t, note))
    for t, note in sorted(charts["coverage_notes"]["club_chart_not_retrieved_this_session"].items()):
        print("  %s: %s" % (t, note))


if __name__ == "__main__":
    main()
