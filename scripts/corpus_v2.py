#!/usr/bin/env python3
"""T108 (session db00d539) — the dated corpus tranche: v1 frozen, v2 published beside it.

Why this script exists
----------------------
`data/games_2026_results.csv` is the pre-registered backtest corpus. It holds 137 games
(weeks 1-9 = 136 games, plus the Week 10 Thursday game). Thirteen Week 10 games played on
Sunday 15 and Monday 16 November 2026 are settled and transcribed
(`data/games_week10_backfill_2026.csv`, flag F105) but are NOT in the corpus, because
editing a pre-registered corpus in place would silently change every published metric.

This script therefore never touches v1. It publishes a *parallel* corpus:

    data/corpus_v2_2026.csv   150 games = 137 (v1, byte-identical rows) + 13 Week 10 rows
    data/corpus_v2_diff.csv   one row per game: which version holds it, and why

and it refuses to publish if any of the following fails, so the tranche cannot drift:

  C1  the 137 v1 rows in v2 are identical to v1 on every compared field
  C2  the 13 added rows are exactly the rows of the transcribed backfill, no others
  C3  v2 reproduces the official standings read of 2026-11-18 for all 32 clubs
      (W-L-T, points for, points against) and v1 does not (26 of 32 short)
  C4  the official standings reconcile to 150 games arithmetically (W+L+T team-games / 2)
  C5  every row carries an official NFL.com URL

Nothing here is inferred. A value that the official pages do not publish stays blank.

Re-run:  python3 scripts/corpus_v2.py
"""

import csv
import os
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")

V1 = "games_2026_results.csv"
BACKFILL = "games_week10_backfill_2026.csv"
STAND_CURRENT = os.path.join("captures", "standings_2026-11-18.csv")
V2 = "corpus_v2_2026.csv"
DIFF = "corpus_v2_diff.csv"

STAD = "https://www.nfl.com/standings/"
SCHED10 = "https://www.nfl.com/schedules/2026/by-week/week-10"
READ = "2026-11-18"
CMP = ["season", "week", "date_as_shown", "away_team", "away_points", "home_team",
       "home_points", "game_url", "source_url", "neutral_site"]


def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write(name, rows, fields):
    with open(os.path.join(DATA, name), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


v1 = read(V1)
backfill = read(BACKFILL)
try:
    standings = read(STAND_CURRENT)
except FileNotFoundError:
    sys.exit("FAIL: %s missing — the 2026-11-18 standings read is the C3 control" % STAND_CURRENT)

# ---------------------------------------------------------------- build v2 ----
# The 13 rows the feed does not hold, in the v1 column shape. Every field is copied
# from the transcription; nothing is computed.
have = {(str(r["week"]), r["away_team"], r["home_team"]) for r in v1}
added = []
for b in backfill:
    key = (str(b["week"]), b["away_team"], b["home_team"])
    if key in have:
        continue
    if b.get("already_in_results_feed", "").strip().lower() == "yes":
        continue
    added.append({
        "season": b["week"] and "2026",
        "week": b["week"],
        "date_as_shown": b["date_as_shown"],
        "away_team": b["away_team"],
        "away_points": b["away_points"],
        "home_team": b["home_team"],
        "home_points": b["home_points"],
        "game_url": b["game_url"],
        "source_url": b["source_url"],
        # Munich game (NE at DET) is the one Week 10 fixture the official page renders
        # inside an "International Game" section — see the section_as_rendered column of
        # the transcription. The flag is set only where that section says so. Every
        # other added row stays blank rather than being guessed (F71/F99 discipline).
        "neutral_site": "Y" if "international" in b.get("section_as_rendered", "").lower() else "",
    })

v2 = [{k: r.get(k, "") for k in CMP} for r in v1] + \
     [{k: r.get(k, "") for k in CMP} for r in sorted(added, key=lambda r: (int(r["week"]), r["game_url"]))]

# ---------------------------------------------------------------- checks -----
fail = []

# C1 — the v1 rows survive unchanged.
for a, b in zip(v1, v2):
    diffs = [k for k in CMP if str(a.get(k, "")) != str(b.get(k, ""))]
    if diffs:
        fail.append("C1 row %s at %s changed on %s" % (a["away_team"], a["home_team"], diffs))

# C2 — exactly the transcribed rows are added, and nothing else.
exp_added = {(str(b["week"]), b["away_team"], b["home_team"]) for b in backfill
             if b.get("already_in_results_feed", "").strip().lower() != "yes"}
got_added = {(str(r["week"]), r["away_team"], r["home_team"]) for r in v2[len(v1):]}
if exp_added != got_added:
    fail.append("C2 added rows differ: missing %s / extra %s"
                % (sorted(exp_added - got_added), sorted(got_added - exp_added)))
if len(v2) != 150:
    fail.append("C2 v2 row count is %d, expected 150" % len(v2))

# C3 — reconcile each version to the official standings read.
def agg(rows):
    st = defaultdict(lambda: [0, 0, 0, 0, 0])          # w, l, t, pf, pa
    for r in rows:
        a, h = r["away_team"], r["home_team"]
        ap, hp = int(r["away_points"]), int(r["home_points"])
        for t, pf, pa in ((a, ap, hp), (h, hp, ap)):
            st[t][3] += pf
            st[t][4] += pa
            if pf > pa:
                st[t][0] += 1
            elif pf < pa:
                st[t][1] += 1
            else:
                st[t][2] += 1
    return st


def compare(rows, label):
    st = agg(rows)
    bad = []
    for s in standings:
        t = s["team_abbr"]
        if t not in st:
            bad.append((t, "absent from corpus"))
            continue
        want = (int(s["wins"]), int(s["losses"]), int(s["ties"]),
                int(s["points_for"]), int(s["points_against"]))
        got = tuple(st[t])
        if want != got:
            bad.append((t, "official %s vs corpus %s" % (want, got)))
    return st, bad


st2, bad2 = compare(v2, "v2")
st1, bad1 = compare(v1, "v1")
if bad2:
    fail.append("C3 v2 fails to reproduce the 2026-11-18 standings for %d clubs: %s"
                % (len(bad2), bad2[:5]))
if not bad1:
    fail.append("C3 v1 unexpectedly reconciles too — the tranche's premise is wrong")

# C4 — arithmetic: the standings must imply 150 games.
team_games = sum(int(s["wins"]) + int(s["losses"]) + int(s["ties"]) for s in standings)
implied = team_games / 2
if abs(implied - 150) > 0.001:
    fail.append("C4 standings imply %.1f games, expected 150" % implied)

# C5 — every row carries an official URL pair.
for r in v2:
    for k in ("game_url", "source_url"):
        if not r[k].startswith("https://www.nfl.com/"):
            fail.append("C5 non-official %s in %s at %s" % (k, r["away_team"], r["home_team"]))

if fail:
    print("CORPUS V2 BUILD FAILED:")
    for f in fail:
        print("  -", f)
    sys.exit(1)

# ---------------------------------------------------------------- publish ----
write(V2, v2, CMP)

v1_keys = {(str(r["week"]), r["away_team"], r["home_team"]) for r in v1}
diff_rows = []
for r in v2:
    key = (str(r["week"]), r["away_team"], r["home_team"])
    in_v1 = key in v1_keys
    diff_rows.append({
        "week": r["week"],
        "matchup": "%s at %s" % (r["away_team"], r["home_team"]),
        "in_corpus_v1": "yes" if in_v1 else "no",
        "in_corpus_v2": "yes",
        "tranche": "v1 (pre-registered, frozen)" if in_v1 else "v2 tranche 2026-11-18",
        "reason": ("held in the 137-game pre-registered feed"
                   if in_v1 else
                   "settled Week 10 game, transcribed from the official by-week page on "
                   + READ + " and outside the frozen 137-game feed (F96/F105, P09)"),
        "neutral_site": r["neutral_site"],
        "game_url": r["game_url"],
        "source_url": r["source_url"],
    })
write(DIFF, diff_rows, ["week", "matchup", "in_corpus_v1", "in_corpus_v2", "tranche",
                        "reason", "neutral_site", "game_url", "source_url"])

print("corpus_v2_2026.csv : %d games (v1 %d + tranche %d)" % (len(v2), len(v1), len(added)))
print("  C1 v1 rows unchanged            : pass (%d rows)" % len(v1))
print("  C2 tranche = transcription      : pass (%d rows)" % len(added))
print("  C3 v2 reconciles official read  : pass (32/32 clubs, read %s)" % READ)
print("     v1 against the same read     : %d of 32 clubs disagree (the premise)" % len(bad1))
print("  C4 standings imply 150 games    : pass (%d team-games / 2 = %.0f)" % (team_games, implied))
print("  C5 official URLs on every row   : pass")
neutral_added = ["%s at %s" % (r["away_team"], r["home_team"]) for r in added if r["neutral_site"] == "Y"]
print("  neutral-site flags in the tranche: %s" % (", ".join(neutral_added) or "none"))
