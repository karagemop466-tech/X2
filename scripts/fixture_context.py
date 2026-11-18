#!/usr/bin/env python3
"""Fixture-context features built only from published schedule facts (T104, D25).

Reads ONLY schedule facts: season, week, date, away team, home team, and the
official game/schedule URL. No score, result, injury or market field is read.

Sources (all published by NFL.com):
  data/season_games_2026.csv          weeks 1-10 game dates and teams (game_url per row)
  data/games_week10_2026.csv          Week 10 kickoff day and listed teams (schedule of the injury page)
  data/schedule_week11_2026.csv       Week 11 kickoff day and teams (schedule page)

Output: data/fixture_context_2026.csv, one row per scheduled game (weeks 1-11).

Per game and per side (home, away), using only earlier games in the same schedule:
  days_since_last_game   calendar days from the team's previous scheduled game
  prev_week              week of that previous game
  bye_before_game        1 when the previous game was 2+ weeks earlier (a bye week fell in between)
  games_before           number of earlier scheduled games in this file for that team
Per game: rest_diff_home_minus_away (blank when either side has no previous game),
thursday_game (1 when kickoff falls on a Thursday).
Blank means "no earlier scheduled game in this file" (for example Week 1), never zero.
"""
import csv
import datetime as dt
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(DATA, "fixture_context_2026.csv")
MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July",
                                      "August", "September", "October", "November", "December"], 1)}
MONTHS_ABBR = {m[:3]: i for m, i in MONTHS.items()}


def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def load_games():
    games = []
    for r in read("season_games_2026.csv"):
        games.append(dict(season=int(r["season"]), week=int(r["week"]),
                          date=dt.date.fromisoformat(r["game_date"]),
                          away=r["away_team"], home=r["home_team"],
                          source=r["game_url"], basis="season_games_2026.csv (game_url per row)"))
    for r in read("games_week10_2026.csv"):
        m = re.match(r"(\w{3}) (\w{3}) (\d{1,2})$", r["kickoff_day"])
        if not m:
            sys.exit(f"unparsed Week 10 kickoff: {r['kickoff_day']!r}")
        date = dt.date(2026, MONTHS_ABBR[m.group(2)], int(m.group(3)))
        if date.strftime("%a") != m.group(1):
            sys.exit(f"weekday mismatch for Week 10 game {r['game_no']}: {r['kickoff_day']} is {date:%a}")
        away = r["first_listed_team"].split()[0]
        home = r["second_listed_team"].split()[0]
        same = [g for g in games if g["week"] == 10 and {g["away"], g["home"]} == {away, home}]
        if same:  # already in season_games_2026.csv (the Week 10 Thursday game); the teams must agree
            if (same[0]["away"], same[0]["home"], same[0]["date"]) != (away, home, date):
                sys.exit(f"Week 10 game {r['game_no']} disagrees with season_games_2026.csv")
            continue
        games.append(dict(season=2026, week=10, date=date, away=away, home=home,
                          source="https://www.nfl.com/schedules/2026/by-week/week-10",
                          basis="games_week10_2026.csv (away = first listed team, verified against game titles)"))
    for r in read("schedule_week11_2026.csv"):
        m = re.match(r"(\w+) (\w+) (\d{1,2})(st|nd|rd|th)$", r["kickoff_day"])
        if not m:
            sys.exit(f"unparsed Week 11 kickoff: {r['kickoff_day']!r}")
        date = dt.date(2026, MONTHS[m.group(2)], int(m.group(3)))
        if date.strftime("%A") != m.group(1):
            sys.exit(f"weekday mismatch for Week 11 game {r['game_no']}: {r['kickoff_day']} is {date:%A}")
        games.append(dict(season=2026, week=11, date=date, away=r["away_team"], home=r["home_team"],
                          source=r["source_url"], basis="schedule_week11_2026.csv (schedule page)"))
    return games


def main():
    games = load_games()
    # sanity: one game per team per week
    seen = {}
    for g in games:
        for t in (g["home"], g["away"]):
            if (t, g["week"]) in seen:
                sys.exit(f"{t} has two games in week {g['week']}")
            seen[(t, g["week"])] = g
    games.sort(key=lambda g: (g["week"], g["date"], g["home"]))
    history = {}  # team -> list of (date, week)
    rows = []
    for i, g in enumerate(games, 1):
        feats = {}
        for side in ("away", "home"):
            t = g[side]
            prior = sorted(history.get(t, []))
            if prior:
                pd, pw = prior[-1]
                days = (g["date"] - pd).days
                feats[side] = dict(days=days, prev_week=pw, bye=1 if pw < g["week"] - 1 else 0, n=len(prior))
            else:
                feats[side] = dict(days=None, prev_week=None, bye=None, n=0)
        for side in ("away", "home"):
            history.setdefault(g[side], []).append((g["date"], g["week"]))
        ad, hd = feats["away"]["days"], feats["home"]["days"]
        rows.append({
            "fixture_id": f"FC-{g['season']}-W{g['week']:02d}-{g['away']}-{g['home']}",
            "season": g["season"], "week": g["week"], "game_date": g["date"].isoformat(),
            "weekday": g["date"].strftime("%a"),
            "away_team": g["away"], "home_team": g["home"],
            "away_days_since_last_game": "" if ad is None else ad,
            "home_days_since_last_game": "" if hd is None else hd,
            "away_prev_week": "" if feats["away"]["prev_week"] is None else feats["away"]["prev_week"],
            "home_prev_week": "" if feats["home"]["prev_week"] is None else feats["home"]["prev_week"],
            "away_bye_before_game": "" if feats["away"]["bye"] is None else feats["away"]["bye"],
            "home_bye_before_game": "" if feats["home"]["bye"] is None else feats["home"]["bye"],
            "away_games_before": feats["away"]["n"], "home_games_before": feats["home"]["n"],
            "rest_diff_home_minus_away": "" if (ad is None or hd is None) else hd - ad,
            "thursday_game": 1 if g["date"].strftime("%a") == "Thu" else 0,
            "source_url": g["source"], "basis": g["basis"],
        })
    fields = list(rows[0].keys())
    with open(OUT, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {os.path.relpath(OUT, ROOT)}: {len(rows)} scheduled games (weeks 1-11), "
          f"{sum(1 for r in rows if r['away_days_since_last_game'] == '' )} first-appearance sides blank")


if __name__ == "__main__":
    main()
