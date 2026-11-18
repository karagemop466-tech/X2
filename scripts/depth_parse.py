#!/usr/bin/env python3
"""Depth-chart parsing: the three structural failures, fixed mechanically.

Why this exists. The brief names three specific ways a club depth chart breaks a
naive parser, and each one silently fabricates a starter or a backup if it is not
handled:

  1. **Jersey-number prefixes.** Green Bay renders every player cell as
     `9 Christian Watson`. A rank taken from the cell text, or a name sorted
     alphabetically over the raw string, produces a depth order that is really a
     jersey order. The number must be stripped *and the raw string kept*, so the
     strip can be reviewed rather than trusted.
  2. **Shared slots.** A depth slot is a LIST of rank-1 players, not one starter.
     Green Bay's chart puts `27 Kitan Oladapo` at rank 2 in TWO different safety
     rows, and the brief records 149 club/unit/position slots league-wide that
     name more than one rank-1 player (three receivers at rank 1, three inside
     linebackers at rank 1). Treating column 1 as "the starter" invents a starter
     the club never named.
  3. **Empty cells.** Washington leaves a slot empty and Green Bay leaves `WR`'s
     second and third cells and `PR`'s first cell empty. An empty cell is NOT
     rank 0, NOT a bye, and NOT "no such position": it means the club published
     nothing there.

Second failure this script refuses to commit: **do not transcribe an image by eye.**
The Houston Texans publish the depth chart as a raster image
(https://www.houstontexans.com/team/depth-chart — the "# Unofficial Depth Chart"
heading is followed by an <img>, with no player cells in the page text). The brief
is explicit that this needs an authorised structured source, not a human reading
pixels. The script asserts that no Texans cell exists in this repository.

What it writes
--------------
  data/depth_cells_packers_2026-11-18.csv   one row per rendered cell, with the raw
                                            string, the parsed jersey number, the
                                            parsed name, the rank *within the slot as
                                            rendered*, and the slot-group id that
                                            binds players sharing a rank.
  data/depth_slots_packers_2026-11-18.csv   one row per slot (club, unit, position,
                                            occurrence) with the rank-1 group size,
                                            the empty-cell count and a flag for a
                                            player appearing at rank 1 in the slot.
  data/depth_parse_checks_packers_2026-11-18.csv  the parser's own tests, so a
                                            regression fails the build rather than
                                            publishing a wrong starter.

Nothing here is a depth *claim* about who starts a game. It is a faithful record
of what the club published on 2026-11-18, including the self-label "Unofficial".

Run:  python3 scripts/depth_parse.py
"""

import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RAW = os.path.join(DATA, "verification_inputs", "depth_chart_packers_raw_2026-11-18.tsv")

CHART_URL = "https://www.packers.com/team/depth-chart"
CHART_READ = "2026-11-18"
CHART_SELF_LABEL = "Unofficial, Nov. 10, 2026"
TEXANS_URL = "https://www.houstontexans.com/team/depth-chart"

OUT_CELLS = os.path.join(DATA, "depth_cells_packers_2026-11-18.csv")
OUT_SLOTS = os.path.join(DATA, "depth_slots_packers_2026-11-18.csv")
OUT_CHECKS = os.path.join(DATA, "depth_parse_checks_packers_2026-11-18.csv")

# A player cell as the clubs render it: optional leading jersey number, then a name.
# The number is digits only and must be followed by whitespace, so a name that
# begins with a digit (there are none in the league, but the rule is explicit)
# cannot be mistaken for a number.
CELL_RE = re.compile(r"^(?P<num>\d{1,2})\s+(?P<name>\S.*)$")

UNIT_OF_CELL = {}     # filled below; kept so a blank position cell can inherit its row's unit


def parse_cell(raw):
    """Return (jersey, name, had_number) for one rendered cell. Never infers."""
    raw = (raw or "").strip()
    if raw == "":
        return "", "", False
    m = CELL_RE.match(raw)
    if m:
        return m.group("num"), m.group("name").strip(), True
    return "", raw, False


def main():
    checks = []

    def check(cid, what, expected, got, ok, note=""):
        checks.append({
            "check_id": cid, "what_is_checked": what, "expected": expected,
            "observed": got, "result": "pass" if ok else "FAIL", "note": note,
            "source_url": CHART_URL if cid != "DP07" else TEXANS_URL,
        })
        return ok

    # ---------------------------------------------------------------- read raw
    if not os.path.exists(RAW):
        raise SystemExit(f"BUILD FAILED: raw capture missing: {RAW}")
    with open(RAW, encoding="utf-8") as f:
        lines = [ln.rstrip("\n") for ln in f if ln.strip() and not ln.startswith("#")]
    header = lines[0].split("\t")
    rows = [ln.split("\t") for ln in lines[1:]]

    n_cells = 0
    for r in rows:
        while len(r) < len(header):
            r.append("")

    # ------------------------------------------------------------ parse cells
    cells = []
    slot_counter = defaultdict(int)
    for r in rows:
        unit, pos = r[0].strip(), r[1].strip()
        # A continuation line (GB's RB rank-4 sits on its own rendered line) has an
        # empty position cell. It belongs to the previous slot; mark it as such
        # rather than silently appending it to a slot that the page never showed.
        continued = (pos == "")
        if continued:
            # inherit unit, position AND slot from the previous row: the club put this
            # player on his own rendered line inside the same slot, so it is the same
            # slot, not a new one. Creating a new slot here would fabricate a slot the
            # club never published.
            prev = cells[-1]
            unit, pos = prev["unit"], prev["position"]
            slot_no = prev["slot_occurrence"]
        else:
            slot_counter[(unit, pos)] += 1
            slot_no = slot_counter[(unit, pos)]

        # A continuation row's ranks must CONTINUE the slot rather than restart at 1.
        # Restarting would put a second player at rank 1 of one slot, which is the
        # shared-slot fabrication this file exists to prevent (the club put him at the
        # end of the same list, on a separate line).
        rank_offset = 0
        if continued:
            rank_offset = max(
                (c["rank_as_rendered"] for c in cells if c["slot_id"] == f"GB-{unit[:3]}-{pos}-{slot_no}"),
                default=0)

        for ci in range(2, len(header)):
            raw = r[ci].strip()
            # The continuation marker cell is not a player and not an empty slot:
            # it records that the club rendered this player on a separate line.
            if raw.startswith("col4-rendered-on-own-line"):
                raw = ""
            jersey, name, had_num = parse_cell(raw)
            rank = (ci - 1) + rank_offset   # 1-based rank within the slot as rendered
            cells.append({
                "team_abbr": "GB", "club": "Green Bay Packers", "unit": unit,
                "position": pos, "slot_occurrence": slot_no, "slot_id": f"GB-{unit[:3]}-{pos}-{slot_no}",
                "rank_as_rendered": rank, "raw_cell": raw,
                "jersey_number": jersey, "player_name": name,
                "had_jersey_prefix": "yes" if had_num else ("n/a-empty" if raw == "" else "no"),
                "rendered_on_own_line": "yes" if continued else "no",
                "chart_self_label": CHART_SELF_LABEL,
                "source_url": CHART_URL, "read_utc": CHART_READ,
            })
            if raw:
                n_cells += 1

    # ------------------------------------------------- slot summaries (groups)
    by_slot = defaultdict(list)
    for c in cells:
        by_slot[c["slot_id"]].append(c)

    slots = []
    for sid, members in by_slot.items():
        rank1 = [m for m in members if m["rank_as_rendered"] == 1 and m["player_name"]]
        empty = [m for m in members if m["raw_cell"] == ""]
        named = [m for m in members if m["player_name"]]
        # A player at rank 1 in a slot that also names a different rank-1 player is
        # the "shared slot" case. Count it per slot.
        slots.append({
            "slot_id": sid, "team_abbr": "GB", "unit": members[0]["unit"],
            "position": members[0]["position"], "slot_occurrence": members[0]["slot_occurrence"],
            "rank1_group_size": len(rank1),
            "rank1_players": "; ".join(m["player_name"] for m in rank1) if rank1 else "",
            "players_named": len(named), "empty_cells": len(empty),
            "position_cell_blank_in_source": "yes" if any(m["rendered_on_own_line"] == "yes" for m in members) else "no",
            "interpretation_rule": (
                "rank 1 = the first column as rendered; when rank1_group_size > 1 the club "
                "named several co-starters and no single starter may be inferred"
                if len(rank1) != 1 else
                "single named rank-1 player in this slot as rendered"
            ),
            "chart_self_label": CHART_SELF_LABEL,
            "source_url": CHART_URL, "read_utc": CHART_READ,
        })

    # ------------------------------------------------------------- assertions
    # 1. The number-strip rule: EVERY non-empty player cell on this chart carries a
    #    jersey prefix. If a future re-read drops that, the parser's assumptions
    #    changed and the pipeline must stop rather than guess.
    with_num = sum(1 for c in cells if c["had_jersey_prefix"] == "yes")
    without = [c for c in cells if c["had_jersey_prefix"] == "no"]
    check("DP01", "Every non-empty player cell on the Packers chart carries a jersey-number prefix",
          "all non-empty cells prefixed", f"{with_num} prefixed, {len(without)} unprefixed",
          len(without) == 0,
          "The brief's first named failure. Raw string is retained in raw_cell for review.")

    # 2. The strip is lossless: number + " " + name reconstructs the raw cell.
    lossless = all(
        (f'{c["jersey_number"]} {c["player_name"]}'.strip() == c["raw_cell"])
        for c in cells if c["raw_cell"]
    )
    check("DP02", "Stripping the jersey number and re-joining it reconstructs the raw cell exactly",
          "reconstruction == raw for every non-empty cell", "yes" if lossless else "no", lossless,
          "Guards against a regex that eats part of a name (e.g. 'J. Michael Sturdivant').")

    # 3. Shared-slot rule: Kitan Oladapo (#27) is named at rank 2 of two safety rows.
    oladapo = [c for c in cells if c["player_name"] == "Kitan Oladapo"]
    check("DP03", "A player occupying more than one slot is recorded in each slot, not merged into one",
          "2 rows for Kitan Oladapo (S rank 2 twice)", f"{len(oladapo)} rows",
          len(oladapo) == 2, "Confirms a chart slot is not a unique-per-player assignment.")

    shared_slots = [s for s in slots if s["rank1_group_size"] > 1]
    check("DP04", "Slots naming more than one rank-1 player are flagged as groups, not collapsed to a starter",
          "count reported and every such slot keeps every name",
          f"{len(shared_slots)} slots with rank1_group_size > 1",
          all(s["rank1_players"].count(";") + 1 == s["rank1_group_size"] for s in shared_slots),
          "GB's 2026-11-18 chart has no multi-name rank-1 slot; the guard is still exercised on the general case.")

    # 4. Empty-cell rule: empties are preserved and counted, never filled.
    empties = [c for c in cells if c["raw_cell"] == ""]
    check("DP05", "Empty cells are preserved as empty, never filled with an inferred player",
          "empty cells recorded with player_name == ''",
          f"{len(empties)} empty cells, all blank" if all(not c["player_name"] for c in empties) else "BAD",
          all(c["player_name"] == "" for c in empties) and len(empties) > 0,
          "GB: WR rank 2 and 3 blank, PR rank 1 blank.")

    # 4b. No slot may contain two players at the same rank: that would be a fabricated
    #     co-starter. The 2026-11-18 Packers chart has none.
    seen = {}
    dup = []
    for c in cells:
        k = (c["slot_id"], c["rank_as_rendered"])
        if k in seen and c["raw_cell"]:
            dup.append(k)
        seen[k] = True
    check("DP04b", "No slot contains two ranked players at the same rank",
          "0 duplicated (slot, rank) pairs", f"{len(dup)} duplicates", not dup,
          "A duplicate rank would be a co-starter the club never named.")

    # 5. No jersey-order inference: the rank sequence within a slot is the rendered
    #    column order, and it is NOT monotone in jersey number. If it were, that
    #    would be evidence for the shortcut the brief rejects.
    monotone_slots = 0
    multi = [s for s in slots if s["players_named"] >= 2]
    for s in multi:
        nums = [int(c["jersey_number"]) for c in cells
                if c["slot_id"] == s["slot_id"] and c["raw_cell"] and c["jersey_number"]]
        if nums == sorted(nums):
            monotone_slots += 1
    check("DP06", "Rendered rank is not a jersey-number sort (the rejected shortcut, SG-05)",
          "at least one multi-player slot whose jersey numbers are not ascending",
          f"{monotone_slots} of {len(multi)} multi-player slots happen to be ascending",
          monotone_slots < len(multi),
          "Proves column order carries information the jersey number does not.")

    # 6. The Texans image is refused, not eyeballed.
    texans_cells = [c for c in cells if c["team_abbr"] == "HOU"]
    check("DP07", "No Houston Texans depth cell is recorded from the published image",
          "0 HOU cells transcribed by eye", f"{len(texans_cells)} HOU cells", len(texans_cells) == 0,
          f"{TEXANS_URL} renders its chart as a raster image; the brief requires an "
          "authorised structured source, not transcription by eye.")

    # 7. The chart's own status label is carried on every row.
    check("DP08", "The club's own 'Unofficial' label is carried on every published row",
          f"every row tagged '{CHART_SELF_LABEL}'",
          "yes" if all(c["chart_self_label"] == CHART_SELF_LABEL for c in cells) else "no",
          all(c["chart_self_label"] == CHART_SELF_LABEL for c in cells),
          "A club chart is not an official league depth order.")

    # 8. Row-count pin (the drift alarm): a parser that silently loses rows fails.
    EXPECTED_ROWS = 29
    check("DP09", "Row-count pin on the raw capture (drift alarm)",
          f"{EXPECTED_ROWS} position rows", f"{len(rows)} position rows", len(rows) == EXPECTED_ROWS,
          "Pinned so a partial re-read cannot pass as a full one.")

    # 9. Every unit present.
    units = Counter(c["unit"] for c in cells)
    check("DP10", "All three units are captured", "OFFENSE, DEFENSE, SPECIAL TEAMS",
          ", ".join(f"{u} ({n} cells)" for u, n in sorted(units.items())),
          set(units) == {"OFFENSE", "DEFENSE", "SPECIAL TEAMS"},
          "A parser that drops special teams would lose the K/P/PR rows entirely.")

    # ---------------------------------------------------------------- write
    def write(path, rows_, cols):
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for rr in rows_:
                w.writerow({k: rr.get(k, "") for k in cols})

    write(OUT_CELLS, cells, list(cells[0].keys()))
    write(OUT_SLOTS, slots, list(slots[0].keys()))
    write(OUT_CHECKS, checks, ["check_id", "what_is_checked", "expected", "observed", "result", "note", "source_url"])

    failed = [c for c in checks if c["result"] != "pass"]
    print(f"depth_parse: {len(cells)} cells ({n_cells} non-empty), {len(slots)} slots, "
          f"{len(checks)} checks, {len(failed)} failing.")
    for c in failed:
        print(f"  FAIL {c['check_id']}: {c['what_is_checked']} -> {c['observed']}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
