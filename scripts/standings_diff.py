#!/usr/bin/env python3
"""Dated 'what changed' diff between two official standings reads (T103, D37).

Inputs (both transcriptions of https://www.nfl.com/standings/):
  data/standings_2026_official_read_20261114.csv   prior read, 2026-11-14
  data/captures/standings_2026-11-18.csv           current read, 2026-11-18

Output: data/standings_diff_2026-11-14_to_2026-11-18.csv, one row per club.
Rank = position when the 32 clubs are sorted by net points (points for minus
points against), descending; ties share a rank ("min" method). Rank change is
prior rank minus current rank, so a positive value means the club moved up.
Nothing is estimated: every value is read from the two files.
"""
import csv
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PRIOR = os.path.join(ROOT, "data", "standings_2026_official_read_20261114.csv")
CURRENT = os.path.join(ROOT, "data", "captures", "standings_2026-11-18.csv")
OUT = os.path.join(ROOT, "data", "standings_diff_2026-11-14_to_2026-11-18.csv")


def load(path):
    with open(path, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    out = {}
    for r in rows:
        out[r["team_abbr"]] = {
            "name": r["team_name"],
            "w": int(r["wins"]), "l": int(r["losses"]), "t": int(r["ties"]),
            "pf": int(r["points_for"]), "pa": int(r["points_against"]),
        }
        out[r["team_abbr"]]["net"] = out[r["team_abbr"]]["pf"] - out[r["team_abbr"]]["pa"]
    return out


def ranks(d):
    """Competition rank by net points: 1 + number of clubs with strictly more net points."""
    return {k: 1 + sum(1 for j in d if d[j]["net"] > d[k]["net"]) for k in d}


def main():
    prior, cur = load(PRIOR), load(CURRENT)
    if set(prior) != set(cur) or len(cur) != 32:
        sys.exit(f"club sets differ or are not 32: {set(prior) ^ set(cur)}")
    rp, rc = ranks(prior), ranks(cur)
    fields = ["team_abbr", "team_name", "record_prior", "record_current", "games_added",
              "wins_change", "losses_change", "ties_change", "pf_change", "pa_change",
              "net_prior", "net_current", "net_change", "net_rank_prior", "net_rank_current",
              "rank_change_up_is_positive", "changed", "source_prior", "source_current"]
    out_rows = []
    for k in sorted(cur):
        p, c = prior[k], cur[k]
        games_added = (c["w"] + c["l"] + c["t"]) - (p["w"] + p["l"] + p["t"])
        rec = lambda x: f'{x["w"]}-{x["l"]}' + (f'-{x["t"]}' if x["t"] else "")
        changed = "Y" if (p["w"], p["l"], p["t"], p["pf"], p["pa"]) != (c["w"], c["l"], c["t"], c["pf"], c["pa"]) else "N"
        out_rows.append({
            "team_abbr": k, "team_name": c["name"], "record_prior": rec(p), "record_current": rec(c),
            "games_added": games_added, "wins_change": c["w"] - p["w"], "losses_change": c["l"] - p["l"],
            "ties_change": c["t"] - p["t"], "pf_change": c["pf"] - p["pf"], "pa_change": c["pa"] - p["pa"],
            "net_prior": p["net"], "net_current": c["net"], "net_change": c["net"] - p["net"],
            "net_rank_prior": rp[k], "net_rank_current": rc[k],
            "rank_change_up_is_positive": rp[k] - rc[k], "changed": changed,
            "source_prior": "https://www.nfl.com/standings/ (read 2026-11-14)",
            "source_current": "https://www.nfl.com/standings/ (read 2026-11-18)",
        })
    with open(OUT, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(out_rows)
    changed = sum(1 for r in out_rows if r["changed"] == "Y")
    print(f"wrote {os.path.relpath(OUT, ROOT)}: {len(out_rows)} clubs, {changed} with a changed record")
    print(f"games added across the league: {sum(r['games_added'] for r in out_rows) // 2}")


if __name__ == "__main__":
    main()
