#!/usr/bin/env python3
"""Week 11 injury report: independent second read vs first read (T406, session cb679d0e).

Reads:
  data/injury_week11_2026-11-19_by_club.csv              -- first read (T129, session 1745bf18)
  data/injury_week11_read2_2026-11-19_cb679d0e.csv       -- second read (this session)

Writes:
  data/injury_week11_series_2026-11-19_cb679d0e.csv      -- one row per club-section
      comparison, one row per whole-report total, and three item-check rows.

A difference between two dated reads of a live page is a FINDING, not a script
failure: differing rows are published with verdict DIFFERS and the real delta.
The script exits non-zero only on structural problems (club sets that do not
match, a club whose status counts do not sum to its row count, non-official
source URLs, blank required cells), so the register can never silently
disagree with its own inputs.

Cross-reference: session 0a0deaaf's independent second read (T211, flag F133 on
main, read 2026-11-19T22:10Z) reported the same IND discrepancy this script
surfaces; b94f5221's third dated read (T316) is recorded on main as well.
"""
import csv
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")

READ1 = os.path.join(DATA, "injury_week11_2026-11-19_by_club.csv")
READ2 = os.path.join(DATA, "injury_week11_read2_2026-11-19_cb679d0e.csv")
OUT = os.path.join(DATA, "injury_week11_series_2026-11-19_cb679d0e.csv")

SRC = "https://www.nfl.com/injuries/"
CLOCK1 = "2026-11-19T06:53:35Z (chunks 1-6; chunk 0 time not recorded)"
CLOCK2 = "2026-11-19T22:12Z-2026-11-19T22:22Z (session clock)"

COUNT_COLS = [
    "rows",
    "game_status_out",
    "game_status_questionable",
    "game_status_doubtful",
    "game_status_blank",
    "practice_dnp",
    "practice_lp",
    "practice_fp",
]
PRACTICE = ["practice_dnp", "practice_lp", "practice_fp"]
STATUS = ["game_status_out", "game_status_questionable", "game_status_doubtful", "game_status_blank"]

# Whole-report totals of the first read, taken from its capture record
# data/captures/injury_week11_2026-11-19.meta.json (not re-typed from memory).
READ1_TOTALS = {
    "club_sections": 26,
    "total_rows": 253,
    "practice_dnp": 83,
    "practice_lp": 87,
    "practice_fp": 83,
    "game_status_out": 9,
    "game_status_questionable": 7,
    "game_status_doubtful": 0,
    "game_status_blank": 237,
    "no_injury_clubs": 2,
    "games_listed": 13,
}

IND_NOTE = (
    "First read published IND Questionable=4 / blank=2; this second read shows 3 / 3 "
    "(Questionable = Gardner, Gould, Rhodes; blank = Carlies, Heck, Tucker, counted from this "
    "session's own chunk-0 fetch). Session 0a0deaaf's independent second read at 22:10Z (flag F133 "
    "on main) found the same 3 / 3. Whether the page changed after 06:53Z or the first read "
    "miscounted cannot be told from here: the first read's raw rows are gitignored and absent from "
    "clones (flag F143). Do not use the IND Questionable count as settled until resolved (F133/F142)."
)

ITEM_CHECKS = [
    {
        "check_id": "R2-ITEM-ALFORD",
        "metric": "F129 item (a): Dee Alford (BUF) player-link slug",
        "read1_value": "flagged: hub displays Dee Alford with slug deaundre-ford (F129)",
        "read2_value": (
            "resolved as correct: /players/deaundre-ford/ renders 'Dee Alford Stats, News and Video - CB', "
            "CB #23, Buffalo Bills, active; the alternate /players/dee-alford/ exists but renders an empty "
            "template (title 'player.DisplayName')"
        ),
        "delta": "resolved",
        "verdict": "RESOLVED",
        "source_url": "https://www.nfl.com/players/deaundre-ford/",
        "note": "Both URLs read live 2026-11-19. The hub link is the player's canonical official page; the duplicate dee-alford URL is an official-site template defect, not a report error.",
    },
    {
        "check_id": "R2-ITEM-WADDLE",
        "metric": "F129 item (b): Jaylen Waddle listed under DEN",
        "read1_value": "listed under DEN, not checked against Denver roster (F129)",
        "read2_value": (
            "still listed under DEN; official player page states Denver Broncos, WR #17, status active"
        ),
        "delta": "resolved",
        "verdict": "RESOLVED",
        "source_url": "https://www.nfl.com/players/jaylen-waddle/",
        "note": "Verified on the official NFL.com player page (team line 'Denver Broncos') on 2026-11-19; the hub's DEN placement is correct. Main's SRC-120 separately checked all nine DEN names against the Broncos roster page.",
    },
    {
        "check_id": "R2-ITEM-MURRAY",
        "metric": "Spot check raised by the second read: Kyler Murray listed under MIN",
        "read1_value": "not assessed in the first read",
        "read2_value": (
            "listed under MIN in the hub; official player page states Minnesota Vikings, QB #1, status active"
        ),
        "delta": "new observation, confirmed",
        "verdict": "CONFIRMED",
        "source_url": "https://www.nfl.com/players/kyler-murray/",
        "note": "Raised by session cb679d0e during the second read because Murray is not listed under AZ; verified on his official player page 2026-11-19.",
    },
]


def load(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return {r["club"]: r for r in csv.DictReader(fh)}


def main():
    r1 = load(READ1)
    r2 = load(READ2)
    problems = []

    if set(r1) != set(r2):
        problems.append(
            f"club sections differ: only-read1={sorted(set(r1) - set(r2))} "
            f"only-read2={sorted(set(r2) - set(r1))}")

    for club, r in sorted(r2.items()):
        if not r["source_url"].startswith("https://www.nfl.com/"):
            problems.append(f"{club}: read2 source_url not official")
        try:
            rows = int(r["rows"])
            p_sum = sum(int(r[c]) for c in PRACTICE)
            s_sum = sum(int(r[c]) for c in STATUS)
        except ValueError:
            problems.append(f"{club}: non-integer count in read2")
            continue
        if p_sum != rows:
            problems.append(f"{club}: practice counts sum to {p_sum}, rows {rows}")
        if s_sum != rows:
            problems.append(f"{club}: game-status counts sum to {s_sum}, rows {rows}")

    rows_out = []
    n_match = n_diff = 0
    for club in sorted(set(r1) & set(r2)):
        a, b = r1[club], r2[club]
        mismatches = [c for c in COUNT_COLS if a[c].strip() != b[c].strip()]
        if a["page_says_no_injuries"].strip() != b["page_says_no_injuries"].strip():
            mismatches.append("page_says_no_injuries")
        if a["game"].strip() != b["game"].strip():
            mismatches.append("game")
        delta = int(b["rows"]) - int(a["rows"])
        if mismatches:
            verdict = "DIFFERS"
            n_diff += 1
            note = "mismatched cells: " + ",".join(mismatches)
            if club == "IND":
                note += " | " + IND_NOTE
        else:
            verdict = "MATCH"
            n_match += 1
            note = "all counted cells match: " + ",".join(COUNT_COLS) + ",game,page_says_no_injuries"
        rows_out.append({
            "check_id": f"R2-CLUB-{club}",
            "scope": "club section",
            "metric": "player rows (verdict covers every counted cell of the section)",
            "read1_value": a["rows"],
            "read1_clock": CLOCK1,
            "read2_value": b["rows"],
            "read2_clock": CLOCK2,
            "delta": delta,
            "verdict": verdict,
            "source_url": SRC,
            "note": note,
        })

    def total(metric, v1, v2, note_extra=""):
        delta = int(v2) - int(v1)
        verdict = "MATCH" if delta == 0 else "DIFFERS"
        note = ("read1 value from data/captures/injury_week11_2026-11-19.meta.json; "
                "read2 summed from data/injury_week11_read2_2026-11-19_cb679d0e.csv")
        if note_extra:
            note += " | " + note_extra
        rows_out.append({
            "check_id": "R2-TOTAL-" + metric.upper(),
            "scope": "whole report",
            "metric": metric,
            "read1_value": v1,
            "read1_clock": CLOCK1,
            "read2_value": v2,
            "read2_clock": CLOCK2,
            "delta": delta,
            "verdict": verdict,
            "source_url": SRC,
            "note": note,
        })
        return verdict

    total("club_sections", READ1_TOTALS["club_sections"], len(r2))
    total("total_rows", READ1_TOTALS["total_rows"], sum(int(r["rows"]) for r in r2.values()))
    for col in PRACTICE + STATUS:
        extra = ""
        if col == "game_status_questionable":
            extra = "delta is the IND discrepancy (F133 on main; F142 here)"
        if col == "game_status_blank":
            extra = "delta is the IND discrepancy (F133 on main; F142 here)"
        total(col, READ1_TOTALS[col], sum(int(r[col]) for r in r2.values()), extra)
    total("no_injury_clubs", READ1_TOTALS["no_injury_clubs"],
          sum(1 for r in r2.values() if r["page_says_no_injuries"].strip() == "Y"))
    total("games_listed", READ1_TOTALS["games_listed"], len({r["game"] for r in r2.values()}))

    for item in ITEM_CHECKS:
        if not item["source_url"].startswith("https://www.nfl.com/"):
            problems.append(f"{item['check_id']}: source_url not official")
        for k in ("read1_value", "read2_value", "delta", "verdict", "note"):
            if not item[k].strip():
                problems.append(f"{item['check_id']}: blank {k}")
        rows_out.append({
            "check_id": item["check_id"],
            "scope": "item check",
            "metric": item["metric"],
            "read1_value": item["read1_value"],
            "read1_clock": CLOCK1,
            "read2_value": item["read2_value"],
            "read2_clock": CLOCK2,
            "delta": item["delta"],
            "verdict": item["verdict"],
            "source_url": item["source_url"],
            "note": item["note"],
        })

    if problems:
        print("WEEK11 READ2 STRUCTURAL CHECK FAILED:")
        for p in problems:
            print("  -", p)
        sys.exit(1)

    fields = ["check_id", "scope", "metric", "read1_value", "read1_clock",
              "read2_value", "read2_clock", "delta", "verdict", "source_url", "note"]
    with open(OUT, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows_out)
    print(f"WEEK11 READ2 PASS: {len(r2)} club sections, "
          f"{sum(int(r['rows']) for r in r2.values())} rows; comparisons: {n_match} MATCH, "
          f"{n_diff} DIFFERS ({', '.join(sorted(r['check_id'].replace('R2-CLUB-', '') for r in rows_out if r['verdict'] == 'DIFFERS' and r['scope'] == 'club section')) or 'none'}); "
          f"3 item checks; {len(rows_out)} rows written to {os.path.basename(OUT)}.")


if __name__ == "__main__":
    main()
