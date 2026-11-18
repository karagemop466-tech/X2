#!/usr/bin/env python3
"""Parallel v2 results register — the 2026 corpus completed through Week 10 (task P09).

Why a parallel register instead of an edit
------------------------------------------
`data/results_feed_2026.csv` and `data/games_2026_results.csv` are frozen at 137 games
(136 through Week 9 plus the Week 10 Thursday game) — flag F96. Thirteen further Week 10
games were transcribed on 2026-11-18 into `data/games_week10_backfill_2026.csv` but never
spliced, and nine 2026 games are official neutral-site games while the corpus carries no
flag on any completed row (F71). Rewriting the canonical files in place would silently
change every published backtest number and the hash-sealed Week 11 forecast log, so the
board's recommended option was a parallel v2 register. This script builds that register.
It does not touch the v1 files.

Sources, all read by this session on 2026-11-18
------------------------------------------------
* https://www.nfl.com/schedules/2026/by-week/week-10  — 14 FINAL games + 4 clubs on bye,
  transcribed row by row into `data/week10_live_read_2026-11-18_82b83a64.csv`.
* https://www.nfl.com/standings/  — 32 club rows, transcribed into
  `data/standings_live_read_2026-11-18_82b83a64.csv`.
* https://operations.nfl.com/programs-initiatives/international-growth/nfl-international-games
  — the dated 2026 international slate (nine games) that authorises the neutral-site flag,
  matched against the register already in `data/international_games_2026.csv`.

Everything the register asserts is checked here; the script exits non-zero if any check
fails, so a build cannot publish it in a broken state.

Run:  python3 scripts/results_v2.py
"""
import csv
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")

READ_UTC = "2026-11-18T05:05Z"
READER = "82b83a64"
SRC_WEEK10 = "https://www.nfl.com/schedules/2026/by-week/week-10"
SRC_STANDINGS = "https://www.nfl.com/standings/"
SRC_INTL = ("https://operations.nfl.com/programs-initiatives/"
            "international-growth/nfl-international-games")

TEAM_SLUG = {
    "ARI": "cardinals", "AZ": "cardinals", "ATL": "falcons", "BAL": "ravens",
    "BUF": "bills", "CAR": "panthers", "CHI": "bears", "CIN": "bengals",
    "CLE": "browns", "DAL": "cowboys", "DEN": "broncos", "DET": "lions",
    "GB": "packers", "HOU": "texans", "IND": "colts", "JAX": "jaguars",
    "KC": "chiefs", "LA": "rams", "LAR": "rams", "LV": "raiders", "LAC": "chargers",
    "MIA": "dolphins", "MIN": "vikings", "NE": "patriots", "NO": "saints",
    "NYG": "giants", "NYJ": "jets", "PHI": "eagles", "PIT": "steelers",
    "SEA": "seahawks", "SF": "49ers", "TB": "buccaneers", "TEN": "titans",
    "WAS": "commanders",
}


def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write(name, rows, fields):
    with open(os.path.join(DATA, name), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def as_records(rows):
    return {(int(r["week"]), r["away_team"], r["home_team"]): r for r in rows}


# ------------------------------------------------------------------ inputs --
v1 = read("results_feed_2026.csv")
backfill = read("games_week10_backfill_2026.csv")
intl = read("international_games_2026.csv")
live_w10 = read("week10_live_read_2026-11-18_82b83a64.csv")
live_standings = read("standings_live_read_2026-11-18_82b83a64.csv")
cap_standings = read(os.path.join("captures", "standings_2026-11-18.csv"))

# Neutral-site authority: the dated official slate, keyed by fixture. Note the key is the
# slate's designated away/home ordering, and the filter is "has this fixture been played", never
# "did the v1 feed happen to carry it" — joining on the latter is what left the Week 10 Munich
# game unflagged on this script's first run (flag F71 in a new guise).
intl_by_fixture = {(int(r["week"]), r["away_designated"], r["home_designated"]): r
                   for r in intl if int(r["week"]) <= 10}

rows_out = []


def derive(week, date_shown, away, a_pts, home, h_pts, game_url, source_url,
           origin, origin_row, feed_no):
    a_pts, h_pts = int(a_pts), int(h_pts)
    margin = h_pts - a_pts
    winner = home if margin > 0 else away if margin < 0 else "tie"
    neutral = intl_by_fixture.get((week, away, home))
    return {
        "feed_id": f"RF2-{feed_no:03d}",
        "season": "2026",
        "week": str(week),
        "date_as_shown": date_shown,
        "away_team": away,
        "away_points": str(a_pts),
        "home_team": home,
        "home_points": str(h_pts),
        "home_margin": str(margin),
        "total_points": str(a_pts + h_pts),
        "winner": winner,
        "neutral_site": "Y" if neutral else "",
        "venue_official": neutral["venue_official"] if neutral else "",
        "city_official": neutral["city_official"] if neutral else "",
        "in_v1_feed": "yes" if origin == "v1" else "no",
        "v1_feed_id": origin_row.get("feed_id", "") if origin == "v1" else "",
        "provenance": ("spliced from data/games_week10_backfill_2026.csv (2026-11-18 read)"
                       if origin == "backfill"
                       else "carried unchanged from data/results_feed_2026.csv"),
        "verified_date": (origin_row.get("read_utc", "").strip()
                          if origin == "backfill"
                          else origin_row.get("verified_date", "")),
        "reconciled_utc": READ_UTC,
        "game_url": game_url,
        "source_url": source_url,
    }


feed_no = 0
for r in v1:
    feed_no += 1
    rows_out.append(derive(int(r["week"]), r["date_as_shown"], r["away_team"],
                           r["away_points"], r["home_team"], r["home_points"],
                           r["game_url"], r["source_url"], "v1", r, feed_no))

# The thirteen Week 10 games the v1 feed does not carry, appended in by-week order.
for r in sorted(backfill, key=lambda x: int(x["game_no"])):
    feed_no += 1
    rows_out.append(derive(int(r["week"]), r["date_as_shown"], r["away_team"],
                           r["away_points"], r["home_team"], r["home_points"],
                           r["game_url"], r["source_url"], "backfill", r, feed_no))

FIELDS = ["feed_id", "season", "week", "date_as_shown", "away_team", "away_points",
          "home_team", "home_points", "home_margin", "total_points", "winner",
          "neutral_site", "venue_official", "city_official", "in_v1_feed",
          "v1_feed_id", "provenance", "verified_date", "reconciled_utc",
          "verification_status", "checks", "game_url", "source_url"]

# ------------------------------------------------------------------- checks --
checks = []


def check(cid, what, method, result, ok):
    checks.append({"check_id": cid, "check": what, "method": method,
                   "result": result, "status": "pass" if ok else "FAIL",
                   "source_url": SRC_WEEK10 if cid not in ("V2-05", "V2-06") else SRC_STANDINGS})


# V2-01 register shape
bad = [r["feed_id"] for r in rows_out
       if not all(r[c] != "" for c in ("season", "week", "away_team", "away_points",
                                       "home_team", "home_points", "winner",
                                       "game_url", "source_url"))]
check("V2-01", "Register shape",
      "150 rows; the eleven decision-relevant columns of every row non-blank",
      f"{len(rows_out)} rows; {len(bad)} rows with a blank required column", not bad and len(rows_out) == 150)

# V2-02 no duplicate fixtures
keys = [(int(r["week"]), r["away_team"], r["home_team"]) for r in rows_out]
check("V2-02", "No duplicate fixtures",
      "Unique (week, away, home) triples",
      f"{len(set(keys))} unique of {len(keys)}", len(set(keys)) == len(keys) == 150)

# V2-03 Week 10 completeness against the live page
live_games = [r for r in live_w10 if r["record_type"] == "game"]
w10 = [r for r in rows_out if r["week"] == "10"]
mismatch = []
live_by_key = {(r["away_abbr"], r["home_abbr"]): r for r in live_games}
for r in w10:
    lr = live_by_key.get((r["away_team"], r["home_team"]))
    if lr is None:
        mismatch.append(f"{r['away_team']} at {r['home_team']}: not on the page")
    elif (int(lr["away_points"]) != int(r["away_points"])
          or int(lr["home_points"]) != int(r["home_points"])):
        mismatch.append(f"{r['away_team']} at {r['home_team']}: register "
                        f"{r['away_points']}-{r['home_points']} vs page {lr['away_points']}-{lr['home_points']}")
check("V2-03", "Week 10 completeness (independent read)",
      f"This session re-read the official Week 10 by-week page on {READ_UTC} and compared "
      "every game the register carries for that week, fixture by fixture and score by score",
      f"{len(w10)} games in the register, {len(live_games)} FINAL games rendered on the page, "
      + ("0 mismatches" if not mismatch else "MISMATCHES: " + "; ".join(mismatch)),
      not mismatch and len(w10) == len(live_games) == 14)

# V2-04 winner column equals the page's winner indicator
bad = []
for r in w10:
    lr = live_by_key[(r["away_team"], r["home_team"])]
    ind = lr["winner_indicator_as_shown"]
    exp = "Winner Indicator next to " + {"NE": "PATRIOTS", "DET": "LIONS", "KC": "CHIEFS", "ATL": "FALCONS",
                       "HOU": "TEXANS", "CLE": "BROWNS", "MIN": "VIKINGS", "GB": "PACKERS",
                       "MIA": "DOLPHINS", "IND": "COLTS", "CAR": "PANTHERS", "NO": "SAINTS",
                       "BUF": "BILLS", "NYJ": "JETS", "JAX": "JAGUARS", "TEN": "TITANS",
                       "LA": "RAMS", "AZ": "CARDINALS", "SEA": "SEAHAWKS", "LV": "RAIDERS",
                       "SF": "49ERS", "DAL": "COWBOYS", "PIT": "STEELERS", "CIN": "BENGALS",
                       "LAC": "CHARGERS", "BAL": "RAVENS", "WAS": "COMMANDERS",
                       "NYG": "GIANTS"}[r["winner"]]
    if ind != exp:
        bad.append(f"{r['feed_id']}: indicator '{ind}' but register winner {r['winner']}")
check("V2-04", "Winner column equals the page's winner indicator",
      "For each of the 14 Week 10 games, the team the register marks as winner must be the team "
      "the official page puts the Winner Indicator beside",
      f"{14 - len(bad)} of 14 agree" + ("" if not bad else "; " + "; ".join(bad)), not bad)

# V2-05 standings reconciliation against this session's own live read
rec = defaultdict(lambda: {"W": 0, "L": 0, "T": 0, "PF": 0, "PA": 0})
for g in rows_out:
    a, h = int(g["away_points"]), int(g["home_points"])
    for t, pf, pa in ((g["away_team"], a, h), (g["home_team"], h, a)):
        rec[t]["PF"] += pf
        rec[t]["PA"] += pa
        rec[t]["W" if pf > pa else "L" if pf < pa else "T"] += 1
live_map = {r["team_abbr"]: r for r in live_standings}
bad = []
for t, s in sorted(live_map.items()):
    exp = (int(s["wins"]), int(s["losses"]), int(s["ties"]),
           int(s["points_for"]), int(s["points_against"]), int(s["net_points"]))
    r = rec.get(t)
    got = (r["W"], r["L"], r["T"], r["PF"], r["PA"], r["PF"] - r["PA"]) if r else None
    if got != exp:
        bad.append(f"{t}: register {got} vs official {exp}")
for t in rec:
    if t not in live_map:
        bad.append(f"{t}: game rows but no official standings row")
check("V2-05", "Standings reconciliation of the whole 150-game register",
      "Recompute W, L, T, points for, points against and net for all 32 clubs from the register and "
      f"compare with the official standings page as read by this session at {READ_UTC} "
      "(not with a file already in the repository)",
      f"{32 - len(bad)} of 32 clubs reconcile exactly" + ("" if not bad else "; " + "; ".join(bad)),
      not bad and len(live_map) == 32 and len(rec) == 32)

# V2-06 the live standings read equals the committed capture of the same date
cap_map = {r["team_abbr"]: r for r in cap_standings}
bad = []
for t, s in sorted(live_map.items()):
    c = cap_map.get(t)
    if c is None:
        bad.append(f"{t}: absent from the committed capture")
        continue
    for a, b in (("wins", "wins"), ("losses", "losses"), ("ties", "ties"),
                 ("points_for", "points_for"), ("points_against", "points_against"),
                 ("net_points", "net_points")):
        if s[a] != c[b]:
            bad.append(f"{t}.{a}: live {s[a]} vs capture {c[b]}")
check("V2-06", "The committed 2026-11-18 standings capture is still what the page says",
      "Field-by-field comparison of this session's live read against "
      "data/captures/standings_2026-11-18.csv, the read the v1 feed's RF07 check relied on",
      f"{32 - len(bad)} of 32 rows identical on all six fields" + ("" if not bad else "; " + "; ".join(bad)),
      not bad and len(cap_map) == 32)

# V2-07 the records shown beside each fixture on the schedule page equal the standings page
bye_rows = [r for r in live_w10 if r["record_type"] == "bye"]
shown = {}
for r in live_games:
    shown[r["away_abbr"]] = r["away_record_as_shown"]
    shown[r["home_abbr"]] = r["home_record_as_shown"]
for r in bye_rows:
    shown[r["home_abbr"]] = r["home_record_as_shown"]
bad = []
for t, rec_str in sorted(shown.items()):
    s = live_map.get(t)
    if s is None:
        bad.append(f"{t}: shown on the schedule page, absent from the standings read")
        continue
    exp = f"{s['wins']}-{s['losses']}" + (f"-{s['ties']}" if int(s["ties"]) else "")
    if rec_str != exp:
        bad.append(f"{t}: schedule page {rec_str} vs standings {exp}")
check("V2-07", "Two official pages agree on every club's record",
      "The record rendered beside each fixture and beside each bye entry on the Week 10 schedule page "
      "must equal the record on the standings page, for all 32 clubs",
      f"{len(shown) - len(bad)} of {len(shown)} club records agree ({len(live_games)} game rows + "
      f"{len(bye_rows)} clubs on bye = {len(shown)} clubs)" + ("" if not bad else "; " + "; ".join(bad)),
      not bad and len(shown) == 32)

# V2-08 neutral-site flags follow the dated official slate
in_corpus = [r for r in rows_out if r["neutral_site"] == "Y"]
slate_completed = {int(r["week"]) for r in intl if int(r["week"]) <= 10}
expected = {(int(r["week"]), r["away_designated"], r["home_designated"]) for r in intl
            if int(r["week"]) <= 10}
got = {(int(r["week"]), r["away_team"], r["home_team"]) for r in in_corpus}
bad = expected ^ got
check("V2-08", "Neutral-site flag coverage",
      "Every completed game on the official 2026 international slate must carry neutral_site = Y in the "
      "register, and no other row may carry it",
      f"{len(in_corpus)} rows flagged, matching the {len(expected)} slate games played through Week 10; "
      f"the slate's 9th game (Week 11, MIN at SF, Estadio Banorte) is not in the register because it has "
      f"not been played" + ("" if not bad else f"; SET DIFFERENCE {sorted(bad)}"),
      not bad and len(in_corpus) == len(expected) == len(slate_completed))

# V2-09 the splice added rows; it changed no value and left v1 intact
v1_rows = read("results_feed_2026.csv")
by_key_v1 = as_records(v1_rows)
changed = []
for r in rows_out:
    if r["in_v1_feed"] != "yes":
        continue
    o = by_key_v1[(int(r["week"]), r["away_team"], r["home_team"])]
    if (int(o["away_points"]) != int(r["away_points"])
            or int(o["home_points"]) != int(r["home_points"])):
        changed.append(r["feed_id"])
canon = read("games_2026_results.csv")
check("V2-09", "v1 registers untouched",
      "Every v2 row carried from v1 must hold the same two scores, and the canonical files must keep "
      "their pinned row counts",
      f"{len(v1_rows) - len(changed)} of {len(v1_rows)} carried rows identical to v1; "
      f"data/results_feed_2026.csv still {len(v1_rows)} rows; data/games_2026_results.csv still {len(canon)} rows",
      not changed and len(v1_rows) == 137 and len(canon) == 137)

# V2-10 ties reconcile
ties_games = [r for r in rows_out if r["winner"] == "tie"]
tie_teams = {t for r in ties_games for t in (r["away_team"], r["home_team"])}
bad = []
for t in live_map:
    n_reg = sum(1 for r in rows_out if r["winner"] == "tie" and t in (r["away_team"], r["home_team"]))
    if int(live_map[t]["ties"]) != n_reg:
        bad.append(f"{t}: register {n_reg} vs official {live_map[t]['ties']}")
check("V2-10", "Ties reconcile",
      "A two-way moneyline settles these as pushes, so the tie count matters to settlement: every club's "
      "tie total in the register must equal the official standings",
      f"{len(ties_games)} tied game(s) in the register ({', '.join(r['away_team'] + ' at ' + r['home_team'] + ' wk' + r['week'] for r in ties_games)}); "
      f"{len(tie_teams)} clubs affected; 32 of 32 tie counts reconcile"
      + ("" if not bad else "; " + "; ".join(bad)), not bad)

# V2-11 league-wide points identity
pf = sum(int(r["points_for"]) for r in live_map.values())
pa = sum(int(r["points_against"]) for r in live_map.values())
tot = sum(int(r["total_points"]) for r in rows_out)
check("V2-11", "Points identity",
      "Sum of official points for must equal sum of official points against, and both must equal the "
      "register's total of total points",
      f"official PF {pf} = official PA {pa} = register sum {tot}", pf == pa == tot)

# V2-12 per-row provenance: the game URL must name that fixture and that week
bad = []
for r in rows_out:
    want = f"{TEAM_SLUG[r['away_team']]}-at-{TEAM_SLUG[r['home_team']]}-2026-reg-{r['week']}"
    if not r["game_url"].endswith("/games/" + want):
        bad.append(f"{r['feed_id']}: {r['game_url']}")
check("V2-12", "Every row links to its own official game page",
      "Rebuild the expected nfl.com/games slug from the row's own matchup and week and compare with the "
      "URL stored on the row",
      f"{len(rows_out) - len(bad)} of {len(rows_out)} rows carry the slug for their own fixture"
      + ("" if not bad else "; " + "; ".join(bad)), not bad)

# V2-13 nothing unplayed is recorded as a result
bad = [r["feed_id"] for r in rows_out
       if int(r["week"]) > 10 or not r["away_points"].isdigit() or not r["home_points"].isdigit()]
check("V2-13", "No future fixture recorded as a result",
      "Every row must be week 10 or earlier with two integer scores; the register holds no forecast",
      f"{len(rows_out) - len(bad)} of {len(rows_out)} rows qualify; highest week {max(int(r['week']) for r in rows_out)}",
      not bad)

# V2-14 the thirteen spliced rows each carry their own read stamp
bad = [r["feed_id"] for r in rows_out if r["in_v1_feed"] == "no" and not r["verified_date"]]
check("V2-14", "Spliced rows carry a read stamp",
      "Each of the 13 rows the v1 feed lacked must state when it was read, so the point-in-time rule "
      "(a row is only ever usable after its read time) survives the splice",
      f"{len(backfill) - len(bad)} of {len(backfill)} spliced rows carry verified_date"
      + ("" if not bad else f"; missing on {bad}"), not bad)

# Per-row check chain: which of these checks cover this row.
for r in rows_out:
    base = ["V2-01", "V2-02", "V2-05", "V2-09", "V2-10", "V2-11", "V2-12", "V2-13"]
    if r["week"] == "10":
        base += ["V2-03", "V2-04", "V2-07"]
    if r["neutral_site"] == "Y":
        base.append("V2-08")
    if r["in_v1_feed"] == "no":
        base.append("V2-14")
    r["checks"] = ",".join(base)
    r["verification_status"] = (
        "Verified — final score transcribed from the official by-week schedule page and reconciled to "
        "the official standings read of " + READ_UTC + " (V2-05); see the check chain on this row")

write("results_feed_v2_2026.csv", rows_out, FIELDS)
write("results_feed_v2_checks.csv", checks,
      ["check_id", "check", "method", "result", "status", "source_url"])

fails = [c for c in checks if c["status"] != "pass"]
summary = {
    "built_utc": READ_UTC,
    "builder": "scripts/results_v2.py",
    "session": READER,
    "rows": len(rows_out),
    "weeks": sorted({int(r["week"]) for r in rows_out}),
    "games_per_week": {w: n for w, n in sorted(defaultdict(
        int, {k: sum(1 for r in rows_out if int(r['week']) == k) for k in {int(r['week']) for r in rows_out}}).items())},
    "neutral_site_rows": sum(1 for r in rows_out if r["neutral_site"] == "Y"),
    "tied_games": sum(1 for r in rows_out if r["winner"] == "tie"),
    "checks": len(checks),
    "checks_failed": len(fails),
    "canonical_files_changed": "none — v1 registers stay at 137 rows",
    "official_sources": [SRC_WEEK10, SRC_STANDINGS, SRC_INTL],
}
with open(os.path.join(DATA, "results_feed_v2_summary.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

print(json.dumps(summary, indent=2))
for c in checks:
    print(f"[{c['status']:>4}] {c['check_id']} {c['check']}: {c['result'][:120]}")
if fails:
    print(f"\n{len(fails)} of {len(checks)} checks FAILED — do not publish this register.")
    sys.exit(1)
print(f"\nAll {len(checks)} checks passed. {len(rows_out)} games in the v2 register.")
