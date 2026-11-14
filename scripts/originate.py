#!/usr/bin/env python3
"""Originate our own NFL lines: side first, then total, then moneyline (T43).

The brief asks for the markets to be originated in a fixed order — side, then
total, then moneyline — because each step consumes the previous one:

  step 1  side       attack/defence ratings give a home margin.
  step 2  total      the same ratings give expected points for each team;
                     their sum is the total. It is conditioned on step 1, not
                     fitted separately.
  step 3  moneyline  the margin from step 1 plus the walk-forward residual
                     spread of the margin gives a win probability, and the
                     probability gives a price.

This script also writes the price-snapshot rows for our *own* numbers: an
opening value (the number the model would have published after Week 9, fitted
on the 136 games played up to then) and a current value (fitted on all 137 games
in the repository, i.e. through the Week 10 Thursday game). A true closing value
is the last number before kickoff, so that column is reserved and left blank
until the games are played.

The market columns are blank. There is no licensed odds feed in this
repository, and nothing here invents one: every market, price and difference
cell stays empty and is marked unverified (F07).

The ridge fit is the same estimator as scripts/model.py. Before writing
anything this script re-fits on the full ledger and checks that it reproduces
scripts/model.py's published Week 11 numbers; if it does not, it exits with an
error rather than publishing a second, different set of lines.

Run:  python3 scripts/originate.py
"""

import csv
import json
import math
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
AS_OF = "2026-11-14"
SEED = 20261114
LAMBDA = 4.0                      # M1 ridge penalty, as pre-registered in model.py
BLANK = ("UNVERIFIED - no licensed odds feed in this project; market columns "
         "intentionally blank (F07)")


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


def american(prob):
    """Zero-vig American price for a probability strictly between 0 and 1."""
    if not 0.0 < prob < 1.0:
        return ""
    if prob >= 0.5:
        return "%d" % round(-100.0 * prob / (1.0 - prob))
    return "+%d" % round(100.0 * (1.0 - prob) / prob)


def f(x, nd=1):
    return "" if x is None else f"{x:.{nd}f}"


# ----------------------------------------------------------------- data ----
results = read("games_2026_results.csv")
week11 = read("schedule_week11_2026.csv")
with open(os.path.join(DATA, "model_summary.json"), encoding="utf-8") as fh:
    summary = json.load(fh)
SD_MARGIN = summary["sd_margin_residual"]
SD_TOTAL = summary["sd_total_residual"]

for r in results:
    r["week"] = int(r["week"])
    r["away_points"] = int(r["away_points"])
    r["home_points"] = int(r["home_points"])
    r["margin"] = r["home_points"] - r["away_points"]

TEAMS = sorted({r["away_team"] for r in results} | {r["home_team"] for r in results})
IDX = {t: i for i, t in enumerate(TEAMS)}
NT = len(TEAMS)
P = 1 + NT + NT + 1                     # mu, attack, defence, home field


def solve(A, b):
    """Gaussian elimination with partial pivoting (same routine as model.py)."""
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[piv][col]) < 1e-12:
            raise ValueError("singular matrix")
        M[col], M[piv] = M[piv], M[col]
        pv = M[col][col]
        for r in range(col + 1, n):
            fac = M[r][col] / pv
            if fac:
                for c in range(col, n + 1):
                    M[r][c] -= fac * M[col][c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        s = M[r][n] - sum(M[r][c] * x[c] for c in range(r + 1, n))
        x[r] = s / M[r][r]
    return x


def fit(games, lam=LAMBDA):
    XtX = [[0.0] * P for _ in range(P)]
    Xty = [0.0] * P
    for g in games:
        for t, o, home in ((g["home_team"], g["away_team"], 1.0),
                           (g["away_team"], g["home_team"], 0.0)):
            cols = [(0, 1.0), (1 + IDX[t], 1.0), (1 + NT + IDX[o], -1.0),
                    (1 + 2 * NT, home)]
            y = g["home_points"] if home else g["away_points"]
            for i, vi in cols:
                Xty[i] += vi * y
                for j, vj in cols:
                    XtX[i][j] += vi * vj
    for i in range(1, 1 + 2 * NT):
        XtX[i][i] += lam
    beta = solve(XtX, Xty)
    return {"mu": beta[0], "A": beta[1:1 + NT], "D": beta[1 + NT:1 + 2 * NT],
            "h": beta[1 + 2 * NT]}


def season_to_date(games):
    st = {}
    for g in games:
        for team, pf, pa in ((g["away_team"], g["away_points"], g["home_points"]),
                             (g["home_team"], g["home_points"], g["away_points"])):
            cur = st.setdefault(team, [0, 0, 0])
            cur[0] += pf
            cur[1] += pa
            cur[2] += 1
    return st


def predict(p, home, away, neutral=False):
    """Home-field term is dropped at a neutral site, as scripts/model.py does."""
    hfa = 0.0 if neutral else p["h"]
    hp = p["mu"] + p["A"][IDX[home]] - p["D"][IDX[away]] + hfa
    ap = p["mu"] + p["A"][IDX[away]] - p["D"][IDX[home]]
    return {"home_points": hp, "away_points": ap,
            "margin": hp - ap, "total": hp + ap}


def ref_line(games, home, away, neutral=False):
    """Naive published reference line, as defined in scripts/model.py."""
    st = season_to_date(games)
    lg = [v for v in st.values() if v[2]]
    lg_total = 2 * (sum(v[0] for v in lg) / max(1, sum(v[2] for v in lg)))
    hd = (st[home][0] - st[home][1]) / st[home][2] if home in st and st[home][2] else 0.0
    ad = (st[away][0] - st[away][1]) / st[away][2] if away in st and st[away][2] else 0.0
    return (0.0 if neutral else 2.5) + (hd - ad), lg_total


# --------------------------------------------------- reproduce-check gate ----
full = fit(results)
published = {r["game_no"]: r for r in read("model_lines_week11.csv")}
mismatch = []
for g in week11:
    pr = predict(full, g["home_team"], g["away_team"],
                 g.get("neutral_site", "").strip().upper() == "Y")
    pub = published.get(g["game_no"])
    if pub is None:
        mismatch.append("game %s: no published row to compare against" % g["game_no"])
        continue
    if abs(pr["margin"] - float(pub["model_spread_home"])) > 0.051:
        mismatch.append("game %s: spread %.2f vs published %s"
                        % (g["game_no"], pr["margin"], pub["model_spread_home"]))
    if abs(pr["total"] - float(pub["model_total"])) > 0.051:
        mismatch.append("game %s: total %.2f vs published %s"
                        % (g["game_no"], pr["total"], pub["model_total"]))
if mismatch:
    sys.stderr.write("reproduce-check FAILED:\n  " + "\n  ".join(mismatch) + "\n")
    sys.exit(1)
print("reproduce-check: this fit matches scripts/model.py's published Week 11 "
      "lines for all %d games" % len(week11))

# ------------------------------------------------- two publication bases ----
opening_games = [g for g in results if g["week"] <= 9]
current_games = list(results)
params_open = fit(opening_games)
params_now = fit(current_games)

# ------------------------------------------------------------- originate ----
line_rows = []
snap_rows = []
for g in week11:
    home, away = g["home_team"], g["away_team"]
    neutral = g.get("neutral_site", "").strip().upper() == "Y"
    po = predict(params_open, home, away, neutral)
    pn = predict(params_now, home, away, neutral)
    ref_side, ref_total = ref_line(current_games, home, away, neutral)
    p_home = norm_cdf(pn["margin"] / SD_MARGIN)
    p_over_ref = norm_cdf((pn["total"] - ref_total) / SD_TOTAL)
    p_home_cover_ref = norm_cdf((pn["margin"] - ref_side) / SD_MARGIN)
    pref = "home" if (pn["margin"] - ref_side) > 0 else "away"
    p_pref = p_home_cover_ref if pref == "home" else 1.0 - p_home_cover_ref

    line_rows.append({
        "game_no": g["game_no"],
        "matchup": "%s at %s" % (away, home),
        "kickoff_et": "%s %s" % (g["kickoff_day"], g["kickoff_time_et"]),
        "neutral_site": ("Y" if neutral else "N")
                        + ((" - " + g["neutral_site_note"].strip())
                           if neutral and g.get("neutral_site_note", "").strip() else ""),
        "step_1_side_fair_home_line": f(pn["margin"]),
        "step_1_side_fair_price_at_our_own_line": "+100 / +100 (a fair line splits the coin)",
        "step_1_side_reference_line_home": f(ref_side),
        "step_1_side_edge_points_vs_reference": f(pn["margin"] - ref_side),
        "step_1_side_fair_price_at_reference_for_preferred_side": american(p_pref),
        "step_1_side_market_line": "",
        "step_1_side_difference_market_minus_fair": "",
        "step_2_total_fair": f(pn["total"]),
        "step_2_total_fair_price_at_our_own_line": "+100 / +100 (a fair line splits the coin)",
        "step_2_total_reference_line": f(ref_total),
        "step_2_total_fair_prob_over_at_reference": f(p_over_ref, 3),
        "step_2_total_edge_points_vs_reference": f(pn["total"] - ref_total),
        "step_2_total_market_line": "",
        "step_2_total_difference_market_minus_fair": "",
        "step_3_moneyline_fair_home_prob": f(p_home, 3),
        "step_3_moneyline_fair_price_home": american(p_home),
        "step_3_moneyline_fair_price_away": american(1.0 - p_home),
        "step_3_moneyline_market_price": "",
        "step_3_moneyline_difference_market_minus_fair": "",
        "model_home_points": f(pn["home_points"]),
        "model_away_points": f(pn["away_points"]),
        "residual_sd_margin_used": f(SD_MARGIN, 2),
        "residual_sd_total_used": f(SD_TOTAL, 2),
        "market_note": BLANK,
        "game_url": g["game_url"],
        "source_url": g["source_url"],
    })

    for order, market, ov, cv in (
            (1, "side", po["margin"], pn["margin"]),
            (2, "total", po["total"], pn["total"]),
            (3, "moneyline", norm_cdf(po["margin"] / SD_MARGIN), p_home)):
        snap_rows.append({
            "snapshot_id": "OS-W11-%s-%d" % (g["game_no"], order),
            "game_no": g["game_no"],
            "matchup": "%s at %s" % (away, home),
            "origination_order": order,
            "market": market,
            "our_opening_value": f(ov, 3 if market == "moneyline" else 1),
            "our_opening_basis": ("fitted on the %d games of weeks 1-9, i.e. the number the "
                                  "model would have published before the Week 10 Thursday game"
                                  % len(opening_games)),
            "our_current_value": f(cv, 3 if market == "moneyline" else 1),
            "our_current_basis": ("fitted on all %d games in the repository (through the Week 10 "
                                  "Thursday game) - the number currently published"
                                  % len(current_games)),
            "our_move_current_minus_opening": f(cv - ov, 3 if market == "moneyline" else 1),
            "our_closing_value": "",
            "our_closing_basis": "reserved: the closing value is the last number published before kickoff",
            "market_opening_value": "",
            "market_closing_value": "",
            "market_note": BLANK,
            "as_of": AS_OF,
            "game_url": g["game_url"],
            "source_url": g["source_url"],
        })

line_fields = ["game_no", "matchup", "kickoff_et", "neutral_site",
               "step_1_side_fair_home_line",
               "step_1_side_fair_price_at_our_own_line",
               "step_1_side_reference_line_home",
               "step_1_side_edge_points_vs_reference",
               "step_1_side_fair_price_at_reference_for_preferred_side",
               "step_1_side_market_line", "step_1_side_difference_market_minus_fair",
               "step_2_total_fair", "step_2_total_fair_price_at_our_own_line",
               "step_2_total_reference_line",
               "step_2_total_fair_prob_over_at_reference",
               "step_2_total_edge_points_vs_reference",
               "step_2_total_market_line", "step_2_total_difference_market_minus_fair",
               "step_3_moneyline_fair_home_prob", "step_3_moneyline_fair_price_home",
               "step_3_moneyline_fair_price_away",
               "step_3_moneyline_market_price",
               "step_3_moneyline_difference_market_minus_fair",
               "model_home_points", "model_away_points",
               "residual_sd_margin_used", "residual_sd_total_used",
               "market_note", "game_url", "source_url"]
snap_fields = ["snapshot_id", "game_no", "matchup", "origination_order", "market",
               "our_opening_value", "our_opening_basis", "our_current_value",
               "our_current_basis", "our_move_current_minus_opening",
               "our_closing_value", "our_closing_basis", "market_opening_value",
               "market_closing_value", "market_note", "as_of", "game_url",
               "source_url"]
write("originated_lines_week11.csv", line_rows, line_fields)
write("origin_snapshots_week11.csv", snap_rows, snap_fields)

moves = [abs(float(r["our_move_current_minus_opening"]))
         for r in snap_rows if r["market"] == "side"]
print("originated_lines_week11.csv: %d games, three markets originated in order"
      % len(line_rows))
print("origin_snapshots_week11.csv: %d market snapshots (side, total, moneyline)"
      % len(snap_rows))
print("  largest side move between the two bases: %.1f points; mean %.2f"
      % (max(moves), sum(moves) / len(moves)))
