#!/usr/bin/env python3
"""Second read of the official NFL Week 11 injury hub, compared with the
published single-read register (T211 / T212, session 0a0deaaf).

Inputs
  private/week11_second_read_2026-11-19.psv   row-level transcription of the
      second read (player names). PRIVATE: gitignored, never published.
      Columns: club|player|practice|game_status
      practice in {DNP, LP, FP}; game_status in {Out, Q, D, -}
  data/injury_week11_2026-11-19_by_club.csv    published single-read counts
  data/captures/injury_week11_2026-11-19.meta.json  published totals

Outputs
  data/week11_second_read_2026-11-19.csv      per-club COUNTS ONLY (no names)
  stdout                                      per-club and page-wide comparison

The script never edits the published single-read register. A mismatch is
reported and must be flagged (F133); it is not silently overwritten.
Exit code is 0 when the comparison ran, 2 when an input is missing or malformed.
"""
import csv
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRIVATE = os.path.join(ROOT, "private", "week11_second_read_2026-11-19.psv")
PUBLISHED = os.path.join(ROOT, "data", "injury_week11_2026-11-19_by_club.csv")
META = os.path.join(ROOT, "data", "captures", "injury_week11_2026-11-19.meta.json")
OUT = os.path.join(ROOT, "data", "week11_second_read_2026-11-19.csv")
SOURCE = "https://www.nfl.com/injuries/"
READ_NOTE = ("Second read via fetch_page, chunks 0-6 (totalChunks=7, hasMore=false on chunk 6), "
             "completed 2026-11-19T22:10Z (sandbox clock). Row-level values held in private/ (gitignored).")

PRACTICE = {"DNP", "LP", "FP"}
STATUS = {"Out", "Q", "D", "-"}


def read_private():
    rows = defaultdict(list)
    if not os.path.exists(PRIVATE):
        sys.exit(f"missing private transcription: {PRIVATE}")
    with open(PRIVATE, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("|")
            if len(parts) != 4:
                sys.exit(f"{PRIVATE}:{n} expected 4 fields, got {len(parts)}")
            club, player, practice, status = parts
            if practice not in PRACTICE or status not in STATUS:
                sys.exit(f"{PRIVATE}:{n} closed-vocabulary violation: {practice!r} {status!r}")
            rows[club].append((player, practice, status))
    return rows


def counts(lst):
    c = Counter()
    for _, p, s in lst:
        c["rows"] += 1
        c[p] += 1
        c["Out" if s == "Out" else "Q" if s == "Q" else "D" if s == "D" else "blank"] += 1
    return c


def main():
    live = read_private()
    with open(PUBLISHED, encoding="utf-8", newline="") as fh:
        pub_rows = list(csv.DictReader(fh))
    meta = json.load(open(META, encoding="utf-8"))

    out_rows = []
    mismatch_clubs = []
    page_live = Counter()
    page_pub = Counter()
    for r in pub_rows:
        club = r["club"]
        lc = counts(live.get(club, []))
        page_live.update(lc)
        pc = {
            "rows": int(r["rows"]),
            "DNP": int(r["practice_dnp"]), "LP": int(r["practice_lp"]), "FP": int(r["practice_fp"]),
            "Out": int(r["game_status_out"]), "Q": int(r["game_status_questionable"]),
            "D": int(r["game_status_doubtful"]), "blank": int(r["game_status_blank"]),
        }
        page_pub.update(pc)
        lv = {"rows": lc["rows"], "DNP": lc["DNP"], "LP": lc["LP"], "FP": lc["FP"],
              "Out": lc["Out"], "Q": lc["Q"], "D": lc["D"], "blank": lc["blank"]}
        diff = [k for k in pc if pc[k] != lv[k]]
        if diff:
            mismatch_clubs.append((club, diff))
        out_rows.append({
            "club": club,
            "game": r["game"],
            "published_rows": pc["rows"], "second_read_rows": lv["rows"],
            "published_dnp": pc["DNP"], "second_read_dnp": lv["DNP"],
            "published_lp": pc["LP"], "second_read_lp": lv["LP"],
            "published_fp": pc["FP"], "second_read_fp": lv["FP"],
            "published_out": pc["Out"], "second_read_out": lv["Out"],
            "published_questionable": pc["Q"], "second_read_questionable": lv["Q"],
            "published_doubtful": pc["D"], "second_read_doubtful": lv["D"],
            "published_blank_status": pc["blank"], "second_read_blank_status": lv["blank"],
            "match": "YES" if not diff else "NO",
            "mismatched_fields": ";".join(diff),
            "source_url": SOURCE,
            "read_note": READ_NOTE,
        })

    with open(OUT, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)

    tot = meta["practice_totals"]
    gst = meta["game_status_totals"]
    print(f"clubs compared: {len(out_rows)}; clubs matching: {len(out_rows) - len(mismatch_clubs)}")
    print(f"second read rows: {page_live['rows']} (published meta: {meta['rows_transcribed']})")
    print(f"practice  second read DNP/LP/FP = {page_live['DNP']}/{page_live['LP']}/{page_live['FP']}"
          f"  published meta = {tot['DNP']}/{tot['LP']}/{tot['FP']}")
    print(f"status    second read Out/Q/D/blank = {page_live['Out']}/{page_live['Q']}/{page_live['D']}/{page_live['blank']}"
          f"  published meta = {gst['Out']}/{gst['Questionable']}/0/{gst['blank']}")
    for club, diff in mismatch_clubs:
        print(f"MISMATCH {club}: {', '.join(diff)}")
    print(f"wrote {os.path.relpath(OUT, ROOT)} (counts only, no player names)")


if __name__ == "__main__":
    main()
