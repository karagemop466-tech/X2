#!/usr/bin/env python3
"""Diff the repository's stored Week-10 depth-chart transcription against today's live read.

WHY
---
`data/depth_charts_2026_week10.json` was transcribed on 2026-11-14 for DET, NE, DAL, GB,
TEN and NO. This session re-read five of those six club pages live on 2026-11-18 and
transcribed them independently in `data/depth_chart_strings_2026.csv`.

Two different things can make them disagree, and they must not be confused:

  DRIFT    the club changed its chart between 2026-11-14 and 2026-11-18 (expected; a chart
           is a live document and the brief requires a dated register, not a durable one)
  DEFECT   the stored row was never right for the page it cites (a transcription error)

Only a difference in a cell the club has NOT plausibly changed can be called a defect, and
even then it can only be called one when the value cannot be a between-dates change. This
script therefore reports every difference and labels each one by whether the stored value
is *absent* or *different*, with the live value quoted, and it never silently overwrites
the stored file. The judgement of drift-vs-defect is recorded per row in `assessment`.
"""
import csv
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")

AS_OF_STORED = "2026-11-14"
AS_OF_LIVE = "2026-11-18"

with open(os.path.join(DATA, "depth_charts_2026_week10.json"), encoding="utf-8") as f:
    stored = json.load(f)

live = {}
with open(os.path.join(DATA, "depth_chart_strings_2026.csv"), encoding="utf-8", newline="") as f:
    for r in csv.DictReader(f):
        live.setdefault(r["club"], {"offense": [], "defense": []})
        live[r["club"]][r["side"]].append(r)


def live_matrix(club):
    """club -> {side: [ (pos, [col1, col2, col3, col4]) ]} rebuilt from the flat register."""
    out = {}
    for side in ("offense", "defense"):
        rows = live.get(club, {}).get(side, [])
        by_row = {}
        for r in rows:
            by_row.setdefault(int(r["position_row"]), {"pos": r["pos"], "cols": ["", "", "", ""]})
            idx = int(r["string"]) - 1
            if 0 <= idx < 4:
                by_row[int(r["position_row"])]["cols"][idx] = r["players_in_slot"]
        out[side] = [(v["pos"], v["cols"]) for _k, v in sorted(by_row.items())]
    return out


def stored_matrix(club):
    """The JSON stores players as one list per row; column index == published column."""
    out = {}
    for side in ("offense", "defense"):
        rows = []
        for row in stored["charts"][club].get(side, []):
            cols = ["", "", "", ""]
            for i, name in enumerate(row["players"][:4]):
                cols[i] = name.replace("|", " | ")
            rows.append((row["pos"], cols))
        out[side] = rows
    return out


rows = []
overlap = []
for club in stored["charts"]:
    if club in live:
        overlap.append(club)

for club in overlap:
    s, l = stored_matrix(club), live_matrix(club)
    for side in ("offense", "defense"):
        s_rows, l_rows = s[side], l[side]
        if len(s_rows) != len(l_rows):
            rows.append({
                "club": club, "side": side, "position_row": "", "pos": "",
                "stored_as_of": AS_OF_STORED, "live_as_of": AS_OF_LIVE,
                "stored_value": f"{len(s_rows)} position rows",
                "live_value": f"{len(l_rows)} position rows",
                "difference": "row_count", "assessment": "", "note": "",
                "stored_source_url": stored["charts"][club]["url"],
                "live_source_url": stored["charts"][club]["url"],
            })
        for i in range(min(len(s_rows), len(l_rows))):
            s_pos, s_cols = s_rows[i]
            l_pos, l_cols = l_rows[i]
            if s_pos != l_pos:
                rows.append({
                    "club": club, "side": side, "position_row": i + 1, "pos": s_pos,
                    "stored_as_of": AS_OF_STORED, "live_as_of": AS_OF_LIVE,
                    "stored_value": s_pos, "live_value": l_pos,
                    "difference": "position label", "assessment": "drift", "note": "",
                    "stored_source_url": stored["charts"][club]["url"],
                    "live_source_url": stored["charts"][club]["url"],
                })
            for c in range(4):
                sv, lv = s_cols[c], l_cols[c]
                if sv == lv:
                    continue
                # The stored transcription embeds an editorial annotation INSIDE the value
                # ("... (listed together in the first column)"). That is a data-hygiene
                # defect, not drift: the annotation is not a player name, and a reader that
                # compares names cannot tell a shared slot from a ranked one.
                ANNOT = " (listed together in the"
                if ANNOT in sv and sv.split(ANNOT)[0].strip() == lv.strip():
                    kind = "annotation artefact - same players, stored value polluted by a note"
                elif sv and not lv:
                    kind = "stored-only player (not on the live chart)"
                elif lv and not sv:
                    kind = "live-only player (absent from the stored row)"
                elif sv.strip().lower() == lv.strip().lower():
                    kind = "spelling/accent difference - same player"
                else:
                    kind = "different player"
                rows.append({
                    "club": club, "side": side, "position_row": i + 1, "pos": l_pos,
                    "stored_as_of": AS_OF_STORED, "live_as_of": AS_OF_LIVE,
                    "stored_value": sv, "live_value": lv,
                    "difference": kind,
                    "assessment": ("defect - note embedded in the data value" if kind.startswith("annotation")
                                   else "drift or transcription difference - not separable from a four-day change"),
                    "note": ("The stored cell carries an editorial note inside the player-name "
                             "value, so shared and ranked slots are indistinguishable in the "
                             "stored file (the brief's shared-slot requirement, VR-21/VR-23)."
                             if kind.startswith("annotation") else
                             "A chart can legitimately change in four days, so this is recorded "
                             "as a dated difference. It is a transcription defect only if the "
                             "stored value was never on the page the stored row cites, which "
                             "cannot be settled from today's read alone."),
                    "stored_source_url": stored["charts"][club]["url"],
                    "live_source_url": stored["charts"][club]["url"],
                })

out = os.path.join(DATA, "depth_chart_diff_2026-11-14_vs_2026-11-18.csv")
with open(out, "w", encoding="utf-8", newline="") as f:
    fields = ["club", "side", "position_row", "pos", "stored_as_of", "live_as_of",
              "stored_value", "live_value", "difference", "assessment", "note",
              "stored_source_url", "live_source_url"]
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for r in rows:
        w.writerow(r)

print(f"clubs compared : {', '.join(overlap)} ({len(overlap)} of the {len(stored['charts'])} stored)")
print(f"differences    : {len(rows)}")
for r in rows:
    print(f"  {r['club']} {r['side']:7} row {r['position_row']:>2} {r['pos']:<5} "
          f"stored={r['stored_value']!r:34} live={r['live_value']!r:34} [{r['difference']}]")
