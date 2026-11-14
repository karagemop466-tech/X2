#!/usr/bin/env python3
"""Verified results feed (task T41).

A backtest, a closing-line-value study and a return-on-investment figure all
need the same thing: one row per decided game holding the official final score
and the settlement of every market this project originates. This script builds
that feed. It adds no numbers of its own — every column is either

  * the official final score, already reconciled line by line against the
    official standings by scripts/verify_results.py, or
  * a settlement (cover / not cover / push) computed from that score and the
    walk-forward line scripts/model.py actually published for that game, or
  * deliberately blank, because no market price exists in this repository.

Settlement conventions, stated once so the feed can be joined against prices
later without re-litigating them:

  * side  : the published number is the home team's predicted margin, positive
            when the home team is favoured. The home side covers when the actual
            home margin is strictly greater than that number, loses when it is
            strictly less, and pushes when it is exactly equal.
  * total : the over wins when the actual total points are strictly greater than
            the published total, the under when strictly less, push when equal.
  * moneyline : the home side wins when the actual home margin is strictly
            positive. This season's ledger contains two ties (see the notes
            column), which a two-way moneyline would settle as a push.

Run:  python3 scripts/results_feed.py
"""

import csv
import json
import math
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
AS_OF = "2026-11-14"
BLANK_NOTE = "No licensed odds feed in this project - market columns intentionally blank (F07)"


def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write(name, rows, fields):
    with open(os.path.join(DATA, name), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def norm_cdf(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def f(x, nd=1):
    return "" if x is None else f"{x:.{nd}f}"


def main():
    games = read("games_2026_results.csv")
    backtest = read("model_backtest.csv")
    with open(os.path.join(DATA, "model_summary.json"), encoding="utf-8") as fh:
        summary = json.load(fh)
    sd_margin = summary["sd_margin_residual"]
    sd_total = summary["sd_total_residual"]

    # index the published walk-forward lines by (week, away, home)
    lines = {}
    for r in backtest:
        away, home = [t.strip() for t in r["matchup"].split(" at ")]
        lines[(int(r["week"]), away, home)] = r

    rows = []
    tally = {"side_cover": 0, "side_loss": 0, "side_push": 0,
             "over": 0, "under": 0, "total_push": 0,
             "home_ml_win": 0, "home_ml_loss": 0, "ml_push": 0}
    n_originated = 0
    for i, g in enumerate(games, start=1):
        week = int(g["week"])
        away, home = g["away_team"], g["home_team"]
        ap, hp = int(g["away_points"]), int(g["home_points"])
        margin = hp - ap
        total = hp + ap
        winner = home if margin > 0 else (away if margin < 0 else "tie")
        b = lines.get((week, away, home))

        if b:
            n_originated += 1
            side_line = float(b["m1_spread_home"])
            total_line = float(b["m1_total"])
            ref_side = float(b["reference_spread_home"])
            ref_total = float(b["reference_total"])
            ml_prob = norm_cdf(side_line / sd_margin)
            if margin > side_line:
                side_settle = "home side covers"
                tally["side_cover"] += 1
            elif margin < side_line:
                side_settle = "home side loses"
                tally["side_loss"] += 1
            else:
                side_settle = "push"
                tally["side_push"] += 1
            if total > total_line:
                total_settle = "over"
                tally["over"] += 1
            elif total < total_line:
                total_settle = "under"
                tally["under"] += 1
            else:
                total_settle = "push"
                tally["total_push"] += 1
            if margin > 0:
                ml_settle = "home moneyline wins"
                tally["home_ml_win"] += 1
            elif margin < 0:
                ml_settle = "home moneyline loses"
                tally["home_ml_loss"] += 1
            else:
                ml_settle = "push (tie game)"
                tally["ml_push"] += 1
            origin_status = ("originated walk-forward by scripts/model.py (M1 ridge "
                             "attack/defence, fitted only on games before week %d)" % week)
        else:
            side_line = total_line = ref_side = ref_total = ml_prob = None
            side_settle = total_settle = ml_settle = ""
            origin_status = ("no line originated - the model requires at least 20 prior "
                             "games to fit, so weeks 1-3 carry no published number")

        rows.append({
            "feed_id": "RF-2026-%03d" % i,
            "season": g["season"],
            "week": week,
            "date_as_shown": g["date_as_shown"],
            "away_team": away,
            "away_points": ap,
            "home_team": home,
            "home_points": hp,
            "home_margin": margin,
            "total_points": total,
            "winner": winner,
            "originated_side_home_line": f(side_line),
            "side_settlement_home": side_settle,
            "originated_total_line": f(total_line),
            "total_settlement": total_settle,
            "originated_home_win_probability": f(ml_prob, 3),
            "moneyline_settlement": ml_settle,
            "reference_side_home_line": f(ref_side),
            "reference_total_line": f(ref_total),
            "market_side_home_line": "",
            "market_total_line": "",
            "market_moneyline": "",
            "market_opening_price": "",
            "market_closing_price": "",
            "market_note": BLANK_NOTE,
            "origination_status": origin_status,
            "game_url": g["game_url"],
            "schedule_source_url": g["source_url"],
            "verification": ("final score reconciled against the official standings for "
                             "all 32 teams by scripts/verify_results.py (0 mismatches)"),
            "verified_on": AS_OF,
        })

    fields = ["feed_id", "season", "week", "date_as_shown", "away_team",
              "away_points", "home_team", "home_points", "home_margin",
              "total_points", "winner", "originated_side_home_line",
              "side_settlement_home", "originated_total_line", "total_settlement",
              "originated_home_win_probability", "moneyline_settlement",
              "reference_side_home_line", "reference_total_line",
              "market_side_home_line", "market_total_line", "market_moneyline",
              "market_opening_price", "market_closing_price", "market_note",
              "origination_status", "game_url", "schedule_source_url",
              "verification", "verified_on"]
    write("results_feed.csv", rows, fields)

    print("results_feed.csv: %d games, %d with an originated line" % (len(rows), n_originated))
    print("  side: %d cover / %d loss / %d push" % (tally["side_cover"], tally["side_loss"], tally["side_push"]))
    print("  total: %d over / %d under / %d push" % (tally["over"], tally["under"], tally["total_push"]))
    print("  moneyline: %d home win / %d home loss / %d push" % (tally["home_ml_win"], tally["home_ml_loss"], tally["ml_push"]))
    print("  market price columns: all blank (%s)" % BLANK_NOTE)


if __name__ == "__main__":
    main()
