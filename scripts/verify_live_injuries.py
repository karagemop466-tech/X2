#!/usr/bin/env python3
"""Independent line-by-line verification of data/injuries_week10_2026.csv against
a raw capture of the official NFL.com Week 10 injury report.

Reads the raw markdown chunks saved under data/verification/live_injuries_2026-11-18_chunk*.txt
(captured 2026-11-18), reassembles the page, parses the player tables, and diffs
every field against the stored CSV. Exit 0 only when every row matches.
"""
import csv
import glob
import re
import sys
from collections import defaultdict

CHUNKS = sorted(glob.glob("data/verification/live_injuries_2026-11-18_chunk*.txt"))
if len(CHUNKS) != 8:
    sys.exit(f"expected 8 chunks, found {len(CHUNKS)}")

raw = "".join(open(c, encoding="utf-8").read() for c in CHUNKS)

# --- map team display name -> abbreviation from the game header lines ---
abbr_by_name = {}
for m in re.finditer(r"\b([A-Z]{2,3}) \[([^\]]+)\]\(https://www\.nfl\.com/teams/", raw):
    abbr_by_name[m.group(2)] = m.group(1)

TEAM_NAMES = set(abbr_by_name)

player_re = re.compile(
    r"^\| \[([^\]]+)\]\(https://www\.nfl\.com/players/([^)]+)\) \| ([A-Za-z0-9]+) \| (.*?) \| (.*?) \| (.*?) \|$"
)

live = defaultdict(list)  # team_abbr -> list of row dicts
current = None
for line in raw.splitlines():
    s = line.strip()
    if s in TEAM_NAMES:
        current = abbr_by_name[s]
        continue
    m = player_re.match(s)
    if m and current:
        name, url, pos, injury, practice, game = m.groups()
        live[current].append({
            "player": name, "player_url": url, "position": pos,
            "injury": injury.strip(), "practice_status": practice.strip(),
            "game_status": game.strip(),
        })

with open("data/injuries_week10_2026.csv", newline="", encoding="utf-8-sig") as f:
    stored = list(csv.DictReader(f))
by_team = defaultdict(list)
for r in stored:
    by_team[r["team_abbr"]].append(r)

problems = []
total_live = sum(len(v) for v in live.values())
total_stored = len(stored)
print(f"live rows parsed: {total_live} across {len(live)} teams")
print(f"stored rows: {total_stored} across {len(by_team)} teams")
print(f"teams in live but not stored: {sorted(set(live) - set(by_team))}")
print(f"teams in stored but not live: {sorted(set(by_team) - set(live))}")

for team in sorted(set(live) | set(by_team)):
    lv = live.get(team, [])
    sv = by_team.get(team, [])
    if len(lv) != len(sv):
        problems.append(f"{team}: live {len(lv)} rows vs stored {len(sv)} rows")
    lv_keys = [(r["player"], r["position"], r["injury"], r["practice_status"], r["game_status"]) for r in lv]
    sv_keys = [(r["player"], r["position"], r["injury"], r["practice_status"], r["game_status"]) for r in sv]
    lv_set, sv_set = set(lv_keys), set(sv_keys)
    for k in sorted(lv_set - sv_set):
        problems.append(f"{team}: live row not in stored: {k}")
    for k in sorted(sv_set - lv_set):
        problems.append(f"{team}: stored row not in live: {k}")
    # URL check for players present in both (live page gives the slug; stored holds the full URL)
    lv_urls = {r["player"]: "https://www.nfl.com/players/" + r["player_url"] for r in lv}
    for r in sv:
        if r["player"] in lv_urls and lv_urls[r["player"]] != r["player_url"]:
            problems.append(f"{team}: {r['player']} url live={lv_urls[r['player']]} stored={r['player_url']}")

if problems:
    print(f"\n{len(problems)} DISCREPANCIES:")
    for p in problems:
        print(" -", p)
    sys.exit(1)
print("\nRESULT: all rows and fields match the live official page (independent recount, 2026-11-18).")
