#!/usr/bin/env python3
"""Re-capture the official NFL.com Week 10 injury report (2026-11-18) and republish.

Reads the raw markdown capture saved under data/verification/live_injuries_2026-11-18_chunk*.txt
(fetched from https://www.nfl.com/injuries/ on 2026-11-18), parses every player row, and:

  1. updates data/injuries_week10_2026.csv to the live values (existing rows keep
     their game_no, team_name and player_url; new rows are appended to their team
     block with the game_no of that club's Week 10 game);
  2. rewrites data/verification/official_batch1.txt and official_batch2.txt in the
     pipe format consumed by scripts/verify_snapshot.py, so the snapshot verifier
     validates the re-captured file against this capture;
  3. re-captures the news headlines shown on the injury page into
     data/news_week10_2026.csv.

Prints the exact change set (rows added, rows whose fields changed) so the change
can be recorded in the flag register. Exit 0 on success.
"""
import csv
import glob
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
VER = os.path.join(DATA, "verification")

CHUNKS = sorted(glob.glob(os.path.join(VER, "live_injuries_2026-11-18_chunk*.txt")))
if len(CHUNKS) != 8:
    sys.exit(f"expected 8 chunks, found {len(CHUNKS)}")
raw = "".join(open(c, encoding="utf-8").read() for c in CHUNKS)

abbr_by_name = {}
for m in re.finditer(r"\b([A-Z]{2,3}) \[([^\]]+)\]\(https://www\.nfl\.com/teams/", raw):
    abbr_by_name[m.group(2)] = m.group(1)
TEAM_NAMES = set(abbr_by_name)

player_re = re.compile(
    r"^\| \[([^\]]+)\]\(https://www\.nfl\.com/players/([^)]+)\) \| ([A-Za-z0-9]+) \| (.*?) \| (.*?) \| (.*?) \|$"
)
news_re = re.compile(r"\*\*(.+?)\*\*\]\((https://www\.nfl\.com/news/[^)\"]+)")

live = []  # list of dicts in page order
current = None
for line in raw.splitlines():
    s = line.strip()
    if s in TEAM_NAMES:
        current = abbr_by_name[s]
        continue
    m = player_re.match(s)
    if m and current:
        name, slug, pos, injury, practice, game = m.groups()
        live.append({"team_abbr": current, "player": name, "position": pos,
                     "injury": injury.strip(), "practice_status": practice.strip(),
                     "game_status": game.strip(),
                     "player_url": "https://www.nfl.com/players/" + slug})

news = []
seen_news = set()
for m in news_re.finditer(raw):
    headline, url = m.group(1).strip(), m.group(2)
    if url not in seen_news:
        seen_news.add(url)
        news.append({"headline": headline, "url": url, "source_url": "https://www.nfl.com/injuries/"})

# ---- load the committed snapshot ----
inj_path = os.path.join(DATA, "injuries_week10_2026.csv")
with open(inj_path, encoding="utf-8-sig", newline="") as fh:
    reader = csv.DictReader(fh)
    fieldnames = reader.fieldnames
    committed = list(reader)

by_key = {(r["team_abbr"], r["player"]): r for r in committed}
team_name_by_abbr = {r["team_abbr"]: r["team_name"] for r in committed}
game_no_by_abbr = {r["team_abbr"]: r["game_no"] for r in committed}

added, changed = [], []
for lv in live:
    key = (lv["team_abbr"], lv["player"])
    if key in by_key:
        row = by_key[key]
        for col in ("injury", "practice_status", "game_status"):
            if row[col] != lv[col]:
                changed.append((key, col, row[col], lv[col]))
                row[col] = lv[col]
    else:
        added.append(key)
        by_key[key] = {
            "game_no": game_no_by_abbr.get(lv["team_abbr"], ""),
            "team_abbr": lv["team_abbr"], "team_name": team_name_by_abbr.get(lv["team_abbr"], ""),
            "player": lv["player"], "position": lv["position"], "injury": lv["injury"],
            "practice_status": lv["practice_status"], "game_status": lv["game_status"],
            "player_url": lv["player_url"], "source_url": "https://www.nfl.com/injuries/",
        }

# keep existing row order; insert each new row after the last row of its team
order = list(committed)
last_idx_by_team = {}
for i, r in enumerate(order):
    last_idx_by_team[r["team_abbr"]] = i
for key in added:
    team = key[0]
    order.insert(last_idx_by_team[team] + 1, by_key[key])
    last_idx_by_team[team] += 1

with open(inj_path, "w", encoding="utf-8", newline="") as fh:
    writer = csv.DictWriter(fh, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(order)

# ---- pipe-format transcription for verify_snapshot.py ----
CODE = {"Full Participation in Practice": "F",
        "Limited Participation in Practice": "L",
        "Did Not Participate In Practice": "D"}
pipe_lines = []
for r in order:
    code = CODE.get(r["practice_status"], "?")
    if code == "?":
        sys.exit(f"unknown practice status {r['practice_status']!r} for {r['player']}")
    pipe_lines.append("|".join([r["team_abbr"], r["player"], r["position"],
                                r["injury"], code, r["game_status"]]))
half = (len(pipe_lines) + 1) // 2
for name, lines in (("official_batch1.txt", pipe_lines[:half]),
                    ("official_batch2.txt", pipe_lines[half:])):
    with open(os.path.join(VER, name), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

# ---- news re-capture ----
with open(os.path.join(DATA, "news_week10_2026.csv"), "w", encoding="utf-8", newline="") as fh:
    writer = csv.DictWriter(fh, fieldnames=["headline", "url", "source_url"])
    writer.writeheader()
    writer.writerows(news)

print(f"re-captured {len(live)} injury rows (was {len(committed)})")
print(f"added rows ({len(added)}): {added}")
print(f"field changes ({len(changed)}):")
for key, col, old, new in changed:
    print(f"  {key[0]} {key[1]}: {col}: {old!r} -> {new!r}")
print(f"news headlines re-captured: {len(news)}")
