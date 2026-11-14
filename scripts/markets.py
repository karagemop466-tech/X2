#!/usr/bin/env python3
"""Derive the market tables (session c125b2f7, tasks T39-T40).

Reads only existing project files:
  data/model_lines_week11.csv   - originated fair lines (model_*), one row per game
  data/strategy_leaderboard.csv - strategy skill rows (source_url per row)

Writes:
  data/price_snapshots.csv        - opening/closing store, one row per originated market
  data/line_comparison_week11.csv - fair line / market line / difference, one block per game
  data/strategy_signal_staking.csv - signal ranking kept separate from staking

No price value is ever written by this script. Market and price cells stay blank
until an official or licensed, timestamped source is recorded (see flag F07 and gate G4).

Run:  python3 scripts/markets.py
"""
import csv
import os

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

NO_PRICE_SOURCE = "UNVERIFIED - no authorised timestamped price source (F07, G4)"


def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write(name, rows, fields):
    with open(os.path.join(DATA, name), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\r\n")
        w.writeheader()
        w.writerows(rows)


def teams(matchup):
    away, home = matchup.split(" at ")
    return away.strip(), home.strip()


games = read("model_lines_week11.csv")
leaderboard = read("strategy_leaderboard.csv")

# ---------- T39a: price-snapshot store (side -> total -> moneyline) ----------
MARKETS = [
    (1, "side", "Spread (home side)"),
    (2, "total", "Game total (over/under)"),
    (3, "moneyline", "Moneyline (home side)"),
]
price_fields = [
    "snapshot_id", "game_no", "matchup", "kickoff_et", "origination_order", "market_type", "market",
    "selection", "model_value", "opening_line", "opening_price", "opening_timestamp_utc", "opening_source",
    "closing_line", "closing_price", "closing_timestamp_utc", "closing_source", "status", "source_url",
]
price_rows = []
for g in games:
    _, home = teams(g["matchup"])
    model_value = {
        "side": g["model_spread_home"],
        "total": g["model_total"],
        "moneyline": g["home_win_prob"],
    }
    for order, mtype, label in MARKETS:
        selection = home if mtype != "total" else "over / under"
        price_rows.append({
            "snapshot_id": f"PS-W11-{int(g['game_no']):02d}-{order}",
            "game_no": g["game_no"],
            "matchup": g["matchup"],
            "kickoff_et": g["kickoff_et"],
            "origination_order": order,
            "market_type": mtype,
            "market": label,
            "selection": selection,
            "model_value": model_value[mtype],
            "opening_line": "", "opening_price": "", "opening_timestamp_utc": "", "opening_source": "",
            "closing_line": "", "closing_price": "", "closing_timestamp_utc": "", "closing_source": "",
            "status": NO_PRICE_SOURCE,
            "source_url": g["game_url"],
        })
write("price_snapshots.csv", price_rows, price_fields)

# ---------- T39b: fair line / market line / difference as separate columns ----------
# Difference convention: market minus fair. It is blank unless a market value exists.
comp_fields = [
    "game_no", "matchup", "kickoff_et",
    "side_fair_home_spread", "side_market_home_spread", "side_difference_market_minus_fair",
    "total_fair", "total_market", "total_difference_market_minus_fair",
    "moneyline_fair_home_win_prob", "moneyline_market_home_win_prob", "moneyline_difference_market_minus_fair",
    "status", "source_url",
]
comp_rows = []
for g in games:
    comp_rows.append({
        "game_no": g["game_no"],
        "matchup": g["matchup"],
        "kickoff_et": g["kickoff_et"],
        "side_fair_home_spread": g["model_spread_home"],
        "side_market_home_spread": "",
        "side_difference_market_minus_fair": "",
        "total_fair": g["model_total"],
        "total_market": "",
        "total_difference_market_minus_fair": "",
        "moneyline_fair_home_win_prob": g["home_win_prob"],
        "moneyline_market_home_win_prob": "",
        "moneyline_difference_market_minus_fair": "",
        "status": "Fair line published; market line blank - " + NO_PRICE_SOURCE,
        "source_url": g["game_url"],
    })
write("line_comparison_week11.csv", comp_rows, comp_fields)

# ---------- T40b: signal and staking kept apart ----------
# Rank is by the signal metric only (skill, points). Staking has no measured value
# because no prices exist, so a staking result can never move a strategy up the signal rank.
sig_fields = [
    "signal_rank", "strategy_id", "strategy", "market",
    "signal_skill_points", "signal_ci_low", "signal_ci_high", "signal_q_bh_fdr", "signal_oos_games",
    "signal_gates_passed", "signal_leaderboard_rank",
    "staking_rule", "staking_roi", "staking_status",
    "ranking_basis", "source_url",
]


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


ranked = sorted(leaderboard, key=lambda r: (num(r["skill_score_mae_improvement_pts"]) is None,
                                             -(num(r["skill_score_mae_improvement_pts"]) or 0)))
sig_rows = []
for i, r in enumerate(ranked, start=1):
    has_skill = num(r["skill_score_mae_improvement_pts"]) is not None
    sig_rows.append({
        "signal_rank": str(i) if has_skill else "unranked (no measured skill)",
        "strategy_id": r["strategy_id"],
        "strategy": r["strategy"],
        "market": r["market"],
        "signal_skill_points": r["skill_score_mae_improvement_pts"],
        "signal_ci_low": r["skill_ci_low"],
        "signal_ci_high": r["skill_ci_high"],
        "signal_q_bh_fdr": r["q_bh_fdr"],
        "signal_oos_games": r["oos_games"],
        "signal_gates_passed": r["gates_passed"],
        "signal_leaderboard_rank": r["rank"],
        "staking_rule": "None defined - flat or Kelly staking not applied; no price exists to stake against",
        "staking_roi": "",
        "staking_status": "UNVERIFIED - no priced bets (F07)",
        "ranking_basis": "Signal only (forecast skill vs reference). Staking cannot raise or lower this rank.",
        "source_url": r["source_url"],
    })
write("strategy_signal_staking.csv", sig_rows, sig_fields)

print(f"price_snapshots: {len(price_rows)} rows; line_comparison: {len(comp_rows)} games; "
      f"signal_staking: {len(sig_rows)} strategies")
