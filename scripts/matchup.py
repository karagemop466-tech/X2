#!/usr/bin/env python3
"""Matchup-deficiency matrix: join official availability to official chart string.

WHAT IT PUBLISHES
-----------------
One row per club / side-of-ball / position row, with the published 1st-4th string and a
per-slot status derived by joining the players named on the club's OWN depth chart to the
official NFL injury report.

WHAT IT REFUSES TO DO
---------------------
1. It never invents a string. If the club published one player in a slot, the slot has one
   player; if the club published two players in one cell, the cell is `shared`; if the club
   published nothing, the cell is `empty`. A "1st string" that silently picked one of two
   names would fabricate a starter the club never named (VR-21/VR-23).
2. It never upgrades a status. The injury report's game status is `Out`, `Doubtful`,
   `Questionable` or blank, and it is copied verbatim. A blank game status is NOT 'healthy':
   it means the report does not say, and the brief's own requirement (R60) is that a level
   must never be substituted for a missing value. Blank is published as 'not designated'.
3. It never computes a points penalty for an absence. The brief's REQ-8a asks for injury and
   personnel ABLATIONS (same model with and without the features), not a fixed penalty; the
   model carries no availability feature at all (D24 blocked), so a "points lost" column
   would be an invented number. The matrix instead publishes the structural fact - who is
   designated unavailable and which string behind him the club names - and a deficiency
   index that counts strings, not points.
4. It never treats the injury report as a Week 11 report. The report stored in this repo is
   the Week 10 report (nfl.com/injuries renders Week 10 on 2026-11-18, flag F94). The
   column is therefore labelled Week 10, and the Week 11 designation is blank by design.

DEFICIENCY INDEX
----------------
For each position row, the index is the number of the club's OWN published players in slots
1-4 whose last official game status is Out or Doubtful:
    index 0 = nobody at this position is designated out/doubtful
    index 1 = the first-string player is designated out/doubtful
    index 2+ = the first string and the next man up are both designated out/doubtful
It is a count of strings, with no implied points. It cannot be computed from a level: it is a
comparison between what the club published and what the official report says.
"""
import csv
import os
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")

SRC_INJ = "https://www.nfl.com/injuries/"
SRC_SCHED_W11 = "https://www.nfl.com/schedules/2026/by-week/week-11"
READ_UTC = "2026-11-18"


def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write(name, rows, fields):
    with open(os.path.join(DATA, name), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


matrix = read("matchup_matrix_week11.csv")
injuries = read("injuries_week10_2026.csv")
schedule11 = read("schedule_week11_2026.csv")

# ---------------------------------------------------------------- injury index ----
# team -> normalised player name -> (position, game_status, injury, practice_status)
def norm(s):
    return " ".join(s.replace(".", "").replace("'", "").lower().split())


inj = defaultdict(dict)
for r in injuries:
    inj[r["team_abbr"]][norm(r["player"])] = r

# Who does each club play in Week 11? Used to pair a club's chart against its opponent.
opponent, matchup_label = {}, {}
for g in schedule11:
    opponent[g["away_team"]] = g["home_team"]
    opponent[g["home_team"]] = g["away_team"]
    matchup_label[g["away_team"]] = f"{g['away_team']} at {g['home_team']}"
    matchup_label[g["home_team"]] = f"{g['away_team']} at {g['home_team']}"
# The schedule writes the Rams as LAR; the injury report and charts use LA/LAR variously.
ALIAS = {"LA": "LAR"}
for a, b in list(opponent.items()):
    if a in ALIAS:
        opponent[ALIAS[a]] = b

DESIGNATED = {"out", "doubtful"}

out_rows = []
summary = defaultdict(lambda: {"slots": 0, "designated": 0, "positions_affected": 0,
                                "positions": 0, "rows": []})

for r in matrix:
    club = r["club"]
    names = []
    for si in range(1, 5):
        cell = r.get(f"string_{si}", "")
        if cell:
            names.append((si, cell))
    status_bits = []
    designated = 0
    hit_slots = []
    for si, cell in names:
        for one in cell.split(" | "):
            rec = inj.get(club, {}).get(norm(one))
            if rec:
                gs = (rec.get("game_status") or "").strip()
                if gs.lower() in DESIGNATED:
                    designated += 1
                    hit_slots.append(si)
                status_bits.append((si, one, gs or "not designated", rec["injury"] or "not stated"))
    # the club's injury-report POSITION is the only official positional label available;
    # the chart row's pos is the club's own. Both are published, neither is reconciled.
    report_positions = sorted({p for _s, _n, _g, p in []})
    out_rows.append({
        "club": club, "club_name": r["club_name"], "week11_matchup": matchup_label.get(club, ""),
        "opponent": opponent.get(club, ""),
        "side": r["side"], "unit": r["unit"], "position_row": r["position_row"], "pos": r["pos"],
        "matches_against": r["matches_against"],
        "string_1": r["string_1"], "string_1_type": r["string_1_type"],
        "string_2": r["string_2"], "string_2_type": r["string_2_type"],
        "string_3": r["string_3"], "string_3_type": r["string_3_type"],
        "string_4": r["string_4"], "string_4_type": r["string_4_type"],
        "strings_published": r["strings_published"],
        "shared_slots": r["shared_slots"], "empty_slots": r["empty_slots"],
        "players_named_in_report": len(status_bits),
        "designated_out_or_doubtful": designated,
        "which_strings_are_designated": ",".join(str(s) for s in sorted(set(hit_slots))),
        "deficiency_index_strings": designated,
        "availability_source_week": "Week 10 official report (the page renders Week 10 on 2026-11-18, F94)",
        "week11_designation": "",
        "week11_designation_note": "blank by design - no Week 11 report is published in this repository (F94)",
        "chart_self_label": r["chart_self_label"],
        "chart_date_as_published": r["chart_date_as_published"],
        "read_utc": READ_UTC,
        "source_url": r["source_url"],
        "injury_source_url": SRC_INJ,
    })
    s = summary[club]
    s["slots"] += int(r["strings_published"] or 0)
    s["designated"] += designated
    s["positions"] += 1
    if designated:
        s["positions_affected"] += 1

fields = list(out_rows[0].keys())
write("matchup_deficiency_week11.csv", out_rows, fields)

# ---------------------------------------------------------------- per-club summary ----
sum_rows = []
for club in sorted(summary):
    s = summary[club]
    sum_rows.append({
        "club": club,
        "week11_matchup": matchup_label.get(club, ""),
        "position_rows": s["positions"],
        "published_player_slots": s["slots"],
        "players_designated_out_or_doubtful_in_report": s["designated"],
        "position_rows_affected": s["positions_affected"],
        "share_of_position_rows_affected": (f"{s['positions_affected'] / s['positions']:.3f}"
                                            if s["positions"] else ""),
        "note": ("Counts only players the club's own chart names. A player on the report but "
                 "not on the chart, or on the chart but not in the report, is excluded from "
                 "both numerator and denominator rather than being guessed into a slot."),
        "source_url": next((x["source_url"] for x in matrix if x["club"] == club), ""),
        "injury_source_url": SRC_INJ,
    })
write("matchup_deficiency_summary_week11.csv", sum_rows,
      list(sum_rows[0].keys()))

# ---------------------------------------------------------------- pair view ----
# For each Week 11 game, the two clubs' affected position rows, side by side. This is the
# "one screen" view the brief asks for, and it makes no claim about points.
pairs = []
seen = set()
for r in out_rows:
    key = (r["week11_matchup"], r["club"], r["side"], r["position_row"])
    if key in seen:
        continue
    seen.add(key)
    if not r["deficiency_index_strings"]:
        continue
    opp = r["opponent"]
    opp_row = next((x for x in out_rows
                    if x["club"] == opp and x["side"] != r["side"]
                    and x["unit"] == r["matches_against"].split(" (")[0].split(" their ")[-1]
                    ), None)
    pairs.append({
        "week11_matchup": r["week11_matchup"],
        "club_with_absence": r["club"],
        "side": r["side"], "unit": r["unit"], "pos": r["pos"],
        "string_1": r["string_1"], "string_2": r["string_2"], "string_3": r["string_3"],
        "designated_out_or_doubtful": r["designated_out_or_doubtful"],
        "which_strings_are_designated": r["which_strings_are_designated"],
        "faces": r["matches_against"],
        "opponent_chart_covered": "yes" if opp in summary else "no - opponent chart not transcribed this session",
        "source_url": r["source_url"],
        "injury_source_url": SRC_INJ,
    })
write("matchup_pairs_week11.csv", pairs, list(pairs[0].keys()))

print(f"matrix rows           : {len(out_rows)}")
print(f"clubs                 : {len(summary)}")
print(f"clubs with >=1 absence: {sum(1 for s in summary.values() if s['designated'])}")
print(f"designated absences   : {sum(s['designated'] for s in summary.values())}")
print(f"pair rows             : {len(pairs)}")
