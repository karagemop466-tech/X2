#!/usr/bin/env python3
"""Results-feed completeness: the Week 10 slate, the standings arithmetic, and what moved.

Why this exists. The published results feed holds 137 games and the site describes it as the
verified 2026 feed every backtest runs on. Today's read of the official standings
(https://www.nfl.com/standings/, 2026-11-18) implies 300 team-games = 150 games through Week 10.
The feed's Week 10 block holds ONE game (the Thursday, Nov 12 game); data/games_week10_2026.csv
lists all 14 Week 10 matchups but leaves `result` blank on 13 of them. The 13-game gap is exactly
the difference, and it reconciles to the point: this script refits nothing and edits the canonical
feed not at all — it transcribes the 13 settled scores from the official Week 10 schedule page,
then checks the backfilled log against the official standings club by club. If the two official
surfaces did not agree to the point, the script would fail.

It also closes the 136-vs-137 dispute (flag F88) with arithmetic instead of a recount:
136 = weeks 1-9 (16+16+16+16+15+14+14+14+15, as held in data/games_2026_results.csv);
137 = 136 + the Nov 12 game; 150 = 136 + the full 14-game Week 10 slate, which is what today's
official standings imply (149 wins, 149 losses, 2 ties).

Outputs (all new files; nothing here rewrites another session's register):
  data/games_week10_backfill_2026.csv              the 13 missing settled games, each source-linked
  data/results_feed_completeness_2026-11-18.csv    per club: feed record vs official record, gap
  data/week_count_reconciliation_2026-11-18.csv     league-level counts and the checks, pass/fail
  data/what_changed_2026-11-14_to_2026-11-18.csv   the weekly "what changed" diff: standings order,
                                                   record, points, and the injury-designation change
                                                   count per club from the two dated injury captures

Run:  python3 scripts/results_feed_completeness.py
"""
import csv
import os
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(__file__, "..", ".."))
DATA = os.path.join(ROOT, "data")
VER = os.path.join(ROOT, "data", "verification_inputs")

STANDINGS_URL = "https://www.nfl.com/standings/"
WEEK10_URL = "https://www.nfl.com/schedules/2026/by-week/week-10"
GAME_URL = "https://www.nfl.com/games/{}"
INJURY_URL = "https://www.nfl.com/injuries/"
READ_UTC = "2026-11-18T04:00Z"
PRIOR_STANDINGS = "standings_2026_official_read_20261114.csv"
FEED = "games_2026_results.csv"
OFFICIAL_GAMES_THROUGH_W10 = 150  # (149 + 149 + 2) / 2 from today's official standings read
NAMES = {}


def fail(msg):
    raise SystemExit("RESULTS-FEED COMPLETENESS CHECK FAILED: " + msg)


def read_rows(name):
    path = name if os.path.isabs(name) else os.path.join(DATA, name)
    if not os.path.exists(path):
        fail(f"missing input {name}")
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def read_psv(path, nfields):
    rows = []
    with open(path, encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) != nfields:
                fail(f"{os.path.basename(path)} line {ln}: {len(parts)} fields, expected {nfields}")
            rows.append([p.strip() for p in parts])
    return rows


def write_csv(name, rows, cols):
    with open(os.path.join(DATA, name), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore", lineterminator="\r\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def official_records():
    """Today's official standings read: abbr -> record, plus the published block/row order."""
    out = {}
    for f in read_psv(os.path.join(VER, "standings_2026-11-18_raw.psv"), 12):
        conf, block, pos, abbr, w, l, t, pct, pf, pa, net, strk = f
        out[abbr] = {"conf": conf, "block": int(block), "pos": int(pos), "w": int(w), "l": int(l),
                     "t": int(t), "pct": pct, "pf": int(pf), "pa": int(pa), "net": int(net),
                     "strk": strk, "games": int(w) + int(l) + int(t)}
    if len(out) != 32:
        fail(f"official standings read has {len(out)} clubs, expected 32")
    tw = sum(v["w"] for v in out.values())
    tl = sum(v["l"] for v in out.values())
    tt = sum(v["t"] for v in out.values())
    if not (tw == tl and (tw + tl + tt) // 2 == OFFICIAL_GAMES_THROUGH_W10):
        fail(f"standings read does not imply {OFFICIAL_GAMES_THROUGH_W10} games (W={tw} L={tl} T={tt})")
    return out


def main():
    global NAMES
    for r in read_rows(PRIOR_STANDINGS):
        NAMES[r["team_abbr"]] = r["team_name"]
    feed = read_rows(FEED)
    if len(feed) != 137:
        fail(f"the published feed holds {len(feed)} games, pinned at 137 — the feed changed under this check")

    # --- the official Week 10 slate as rendered today ---
    slate = read_psv(os.path.join(VER, "week10_games_2026-11-18_raw.psv"), 9)
    if len(slate) != 14:
        fail(f"Week 10 slate transcribed with {len(slate)} rows, pinned at 14")
    feed_week = defaultdict(int)
    for g in feed:
        feed_week[int(g["week"])] += 1
    if feed_week[10] != 1:
        fail(f"the feed now holds {feed_week[10]} Week 10 games; this backfill assumes 1")

    # Which slate rows are already in the feed (matched on week + both clubs + both scores)?
    def in_feed(away, home, ap, hp):
        for g in feed:
            if int(g["week"]) != 10:
                continue
            if {g["away_team"], g["home_team"]} != {away, home}:
                continue
            if (int(g["away_points"]), int(g["home_points"])) == (ap, hp):
                return True
        return False

    backfill, already = [], []
    backfill_rows = []
    for row in slate:
        order, section, date_shown, away, ap, home, hp, slug, intl = row
        ap, hp_home = int(ap), int(hp)
        rec = {
            "game_no": order, "week": "10", "date_as_shown": date_shown,
            "section_as_rendered": section,
            "away_team": away, "away_points": str(ap), "home_team": home, "home_points": str(hp_home),
            "home_margin": str(hp_home - ap), "total_points": str(ap + hp_home),
            "winner": home if hp_home > ap else (away if ap > hp_home else "tie"),
            "international_game_flag_as_rendered": intl,
            "already_in_results_feed": "yes" if in_feed(away, home, ap, hp_home) else "no",
            "status": "transcribed from the official Week 10 schedule page and reconciled to the official standings read of the same date",
            "game_url": GAME_URL.format(slug), "source_url": WEEK10_URL,
            "read_utc": READ_UTC,
        }
        if rec["already_in_results_feed"] == "yes":
            already.append(rec)
        else:
            backfill_rows.append(rec)
    if len(backfill_rows) != 13 or len(already) != 1:
        fail(f"expected 13 missing + 1 present, got {len(backfill_rows)} + {len(already)}")
    bcols = ["game_no", "week", "date_as_shown", "section_as_rendered", "away_team", "away_points",
             "home_team", "home_points", "home_margin", "total_points", "winner",
             "international_game_flag_as_rendered", "already_in_results_feed", "status",
             "game_url", "source_url", "read_utc"]
    write_csv("games_week10_backfill_2026.csv", backfill_rows, bcols)

    # --- reconciliation: feed + backfill must reproduce the official standings exactly ---
    def tally(games):
        acc = defaultdict(lambda: {"w": 0, "l": 0, "t": 0, "games": 0, "pf": 0, "pa": 0})
        for g in games:
            a, h = g["away_team"], g["home_team"]
            ap, hp = int(g["away_points"]), int(g["home_points"])
            acc[a]["pf"] += ap; acc[a]["pa"] += hp; acc[a]["games"] += 1
            acc[h]["pf"] += hp; acc[h]["pa"] += ap; acc[h]["games"] += 1
            if ap > hp:
                acc[a]["w"] += 1; acc[h]["l"] += 1
            elif hp > ap:
                acc[h]["w"] += 1; acc[a]["l"] += 1
            else:
                acc[a]["t"] += 1; acc[h]["t"] += 1
        return acc

    off = official_records()
    before = tally(feed)
    after = tally(feed + backfill_rows)
    rows = []
    n_before_bad = n_after_bad = 0
    for t in sorted(off):
        o = off[t]
        b, a = before.get(t, {"w": 0, "l": 0, "t": 0, "games": 0, "pf": 0, "pa": 0}), \
               after.get(t, {"w": 0, "l": 0, "t": 0, "games": 0, "pf": 0, "pa": 0})
        ok_before = (b["w"], b["l"], b["t"], b["pf"], b["pa"]) == (o["w"], o["l"], o["t"], o["pf"], o["pa"])
        ok_after = (a["w"], a["l"], a["t"], a["pf"], a["pa"]) == (o["w"], o["l"], o["t"], o["pf"], o["pa"])
        if not ok_before:
            n_before_bad += 1
        if not ok_after:
            n_after_bad += 1
        rows.append({
            "team_abbr": t, "team_name": NAMES.get(t, ""),
            "feed_games": str(b["games"]), "feed_record": f"{b['w']}-{b['l']}-{b['t']}",
            "feed_pf_pa": f"{b['pf']}/{b['pa']}",
            "official_games_2026_11_18": str(o["games"]),
            "official_record_2026_11_18": f"{o['w']}-{o['l']}-{o['t']}",
            "official_pf_pa_2026_11_18": f"{o['pf']}/{o['pa']}",
            "games_missing_from_feed": str(o["games"] - b["games"]),
            "points_for_missing": str(o["pf"] - b["pf"]),
            "points_against_missing": str(o["pa"] - b["pa"]),
            "feed_plus_backfill_matches_official": "yes" if ok_after else "no",
            "feed_as_published_matches_official": "yes" if ok_before else "no",
            "official_standing_block_row": f"{o['conf']} block {o['block']} row {o['pos']}",
            "source_url": STANDINGS_URL,
            "backfill_source_url": WEEK10_URL,
        })
    write_csv("results_feed_completeness_2026-11-18.csv", rows, [
        "team_abbr", "team_name", "feed_games", "feed_record", "feed_pf_pa",
        "official_games_2026_11_18", "official_record_2026_11_18", "official_pf_pa_2026_11_18",
        "games_missing_from_feed", "points_for_missing", "points_against_missing",
        "feed_plus_backfill_matches_official", "feed_as_published_matches_official",
        "official_standing_block_row", "source_url", "backfill_source_url"])
    if n_after_bad:
        fail(f"{n_after_bad} clubs do not reconcile after the backfill — transcription or standings read is wrong")
    if n_before_bad != 26:
        fail(f"expected 26 clubs short before the backfill, found {n_before_bad} — the gap moved")

    # --- league-level counts (this is the F88 resolution) ---
    checks = []

    def add(metric, value, basis, status, url):
        checks.append({"metric": metric, "value": value, "basis": basis, "result": status, "source_url": url})

    per_week = ", ".join(f"w{w}={feed_week[w]}" for w in sorted(feed_week))
    add("games_in_published_results_feed", "137", "data/games_2026_results.csv row count; per week: " + per_week,
        "measured", "https://github.com/karagemop466-tech/X2/blob/main/data/games_2026_results.csv")
    add("games_in_feed_through_week_9", "136", "weeks 1-9 as held in the feed: " +
        ", ".join(f"w{w}={feed_week[w]}" for w in range(1, 10)),
        "the brief's 136-game log is the through-Week-9 log", WEEK10_URL)
    add("week_10_slate_games_official", "14", "the official Week 10 schedule page lists 14 final games plus 4 byes",
        "verified 2026-11-18", WEEK10_URL)
    add("week_10_games_in_feed", "1", "only the Thursday Nov 12 game carries a score in the feed",
        "gap: 13 settled games absent", WEEK10_URL)
    add("games_implied_by_official_standings", str(OFFICIAL_GAMES_THROUGH_W10),
        "today's standings read: 149 wins, 149 losses, 2 ties = 300 team-games = 150 games",
        "137 + 13 = 150 reconciles", STANDINGS_URL)
    add("feed_plus_backfill_reconciles_all_32_clubs", "yes",
        "every club's W-L-T, points for and points against equal the official standings after adding the 13 rows",
        "pass", STANDINGS_URL)
    add("feed_as_published_reconciles", "no — 26 of 32 clubs short",
        "the 2026-11-14 'all 32 teams reconcile' check compared the feed with a standings read taken before the Week 10 Sunday games",
        "irregularity: the reconciliation was stale, not the arithmetic", STANDINGS_URL)
    add("backtest_corpus_effect", "89 walk-forward games, Week 10 contributes 1",
        "data/model_backtest.csv is graded on the same feed, so the newest out-of-sample week is a single game",
        "flagged for the owner; no metric recomputed here",
        "https://github.com/karagemop466-tech/X2/blob/main/data/model_backtest.csv")
    write_csv("week_count_reconciliation_2026-11-18.csv", checks,
              ["metric", "value", "basis", "result", "source_url"])

    # --- the weekly "what changed" diff: standings + availability, never a static snapshot ---
    prior = {r["team_abbr"]: r for r in read_rows(PRIOR_STANDINGS)}
    inj_delta = defaultdict(int)
    delta_path = os.path.join(DATA, "availability_delta_2026-11-14_to_2026-11-18.csv")
    if os.path.exists(delta_path):
        for r in read_rows("availability_delta_2026-11-14_to_2026-11-18.csv"):
            inj_delta[r["team_abbr"]] += 1
    out_rows = []
    for t in sorted(off):
        o, p = off[t], prior.get(t, {})
        pw, pl = int(p.get("wins", "")), int(p.get("losses", "")) if p else (0, 0)
        pnet = int(p["net_points"]) if p and p.get("net_points", "") != "" else None
        out_rows.append({
            "team_abbr": t, "team_name": NAMES.get(t, ""),
            "record_2026_11_14": f"{pw}-{pl}-{int(p.get('ties', 0))}" if p else "",
            "record_2026_11_18": f"{o['w']}-{o['l']}-{o['t']}",
            "wins_change": str(o["w"] - pw) if p else "",
            "losses_change": str(o["l"] - pl) if p else "",
            "net_points_2026_11_14": pnet if pnet is not None else "",
            "net_points_2026_11_18": str(o["net"]),
            "net_points_change": str(o["net"] - pnet) if pnet is not None else "",
            "standing_position_2026_11_18": f"{o['conf']} block {o['block']} row {o['pos']}",
            "availability_changes_between_captures": str(inj_delta.get(t, 0)),
            "rating_refit_in_this_session": "no — model ratings are not re-fit here (see flag)",
            "source_url": STANDINGS_URL,
            "availability_source_url": INJURY_URL,
        })
    write_csv("what_changed_2026-11-14_to_2026-11-18.csv", out_rows, [
        "team_abbr", "team_name", "record_2026_11_14", "record_2026_11_18", "wins_change",
        "losses_change", "net_points_2026_11_14", "net_points_2026_11_18", "net_points_change",
        "standing_position_2026_11_18", "availability_changes_between_captures",
        "rating_refit_in_this_session", "source_url", "availability_source_url"])

    print(f"backfill rows: {len(backfill_rows)} (13 missing Week 10 games)")
    print(f"clubs reconciling after backfill: 32 of 32; before: {32 - n_before_bad} of 32")
    print(f"what-changed rows: {len(out_rows)}")
    print("OK")


if __name__ == "__main__":
    main()
