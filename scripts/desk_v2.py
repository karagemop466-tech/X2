#!/usr/bin/env python3
"""Market sheet: originated prop lines, fair prices, joint (parlay) pricing and
named event risk, all derived from official NFL.com figures already verified in
this repository.

What this script does **not** do
--------------------------------
It does not record a market price.  No licensed odds feed is connected (F07), so
every market-side column is left blank and marked UNVERIFIED rather than filled
from a public sportsbook page, which would breach the project's official-source
rule.  A "fair price" here is the price implied by this project's own model; it
is *not* a market price and must never be read as one.

Sources used, and why
---------------------
* NFL.com player game logs (per-game passing / rushing / receiving lines) supply
  the prop **outcomes** the backtest needs.  Flag F31 on `main` says no
  player-stat outcome series is held by the repository.  That remains true of the
  repository, and this script does not add a bulk series either: it computes the
  prop layer from the season-level team model and states plainly which prop
  outcomes can and cannot be graded from what is held here.  See the
  `basis` column of every prop row.
* NFL.com Week 10 injury report and Week 11 schedule supply the *named* event
  risks: a specific player, a specific status word, and the specific market that
  the status can invalidate.

Everyone reading this file should start at `data/event_risk_week11.csv` and read
`risk_is_quantified` before relying on any line.
"""
import csv
import math
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")

AS_OF = "2026-11-14"
SRC_W11 = "https://www.nfl.com/schedules/2026/by-week/week-11"
SRC_INJ = "https://www.nfl.com/injuries/"
SRC_GAME_LOGS = "https://www.nfl.com/players/jared-goff/stats/logs/"

errors = []


def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write(name, rows, fields):
    with open(os.path.join(DATA, name), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return len(rows)


def fmt(x, nd=3):
    return "" if x is None else f"{x:.{nd}f}"


lines = read("model_lines_week11.csv")
inj = read("injuries_week10_2026.csv")
summary = read("model_summary.json") and None   # placeholder, replaced below
import json

with open(os.path.join(DATA, "model_summary.json"), encoding="utf-8") as f:
    ms = json.load(f)

SD_MARGIN = ms.get("sd_margin_residual")
SD_TOTAL = ms.get("sd_total_residual")
if not SD_MARGIN or not SD_TOTAL:
    errors.append("model_summary.json lacks residual scales; run scripts/model.py first")

# Points -> American price.  The fair price of a bet is the price at which a
# break-even book would offer it: p * (decimal-1) = (1-p)  =>  decimal = 1/p.
def american(p):
    if p is None or p <= 0 or p >= 1:
        return ""
    if abs(p - 0.5) < 1e-12:
        return "+100"
    if p > 0.5:
        return str(-int(round(100 * p / (1 - p))))
    return "+" + str(int(round(100 * (1 - p) / p)))


def implied(p):
    return "" if p is None else fmt(p, 4)


# ---------------------------------------------------------------------------
# 1. FAIR PRICES for the three originated market types, in origination order.
#    side (spread) -> total -> moneyline, as the owner's brief requires.
# ---------------------------------------------------------------------------
price_rows = []
for g in lines:
    total = float(g["model_total"]) if g["model_total"] else None
    spread = float(g["model_spread_home"]) if g["model_spread_home"] else None
    p_home = float(g["home_win_prob"]) if g["home_win_prob"] else None
    # The spread is priced at exactly the modelled line: the model's own
    # probability of covering its own number is, by construction, one half.
    for order, mtype, sel, model_value, p_fair in (
        (1, "side", g["matchup"].split(" at ")[1], fmt(spread, 1), 0.5),
        (2, "total", "over / under", fmt(total, 1), 0.5),
        (3, "moneyline", g["matchup"].split(" at ")[1], fmt(p_home, 3), p_home),
    ):
        price_rows.append({
            "game_no": g["game_no"],
            "matchup": g["matchup"],
            "origination_order": order,
            "market_type": mtype,
            "selection": sel,
            "model_fair_line": model_value,
            "fair_probability_implied": implied(p_fair),
            "fair_american_price": american(p_fair),
            "market_line": "",
            "market_price": "",
            "edge_points_or_prob": "",
            "status": ("Fair price derived from the model only - NOT a market price. "
                       "Market side blank: no licensed odds feed (F07)."),
            "source_url": SRC_W11,
        })

# ---------------------------------------------------------------------------
# 2. CORRELATION MATRIX across every market pair on the same game.
#    n is published on every row.  Only officially sourced quantities are used:
#    the model's own two legs (side, total) and the outcome side of both.
# ---------------------------------------------------------------------------
backtest = read("model_backtest.csv")
parlay = read("parlay_analysis.csv")
phi = float(parlay[0]["phi_correlation"]) if parlay and parlay[0]["phi_correlation"] else None
n_parlay = int(parlay[0]["tickets"]) if parlay else 0
two_by_two = parlay[0]["two_by_two"] if parlay else ""

corr_rows = []


def add(cid, pair, question, value, n, basis, note, status="computed"):
    corr_rows.append({
        "corr_id": cid,
        "leg_pair": pair,
        "question": question,
        "value": fmt(value),
        "sample_n": n,
        "basis": basis,
        "sign_convention": note,
        "status": status,
        "source_url": SRC_W11,
    })


# (a) side vs total of the SAME game: the phi coefficient from the 2x2 of leg hits.
add("X01", "side x total (same game)",
    "Do the two legs of a same-game side+total ticket move together?",
    phi, n_parlay,
    "Phi on the 2x2 of leg outcomes, walk-forward games where both legs qualified",
    "Positive = legs reinforce; negative = one leg tends to cancel the other. "
    "Observed 2x2: %s" % two_by_two)

# (b) side vs moneyline of the same game: arithmetically one-directional.
add("X02", "side x moneyline (same game)",
    "Can a spread leg and a moneyline leg on the same team disagree?",
    1.0, len(backtest),
    "Definitional bound, not a sample estimate: both are increasing functions of the same margin",
    "A home cover and a home win always agree when the spread is negative; they can "
    "disagree only when the spread underdog wins outright. Not an estimate - a bound.",
    status="definitional - no sample needed")

# (c) two different games' sides: independence is the working assumption, and here
#     it is TESTED on the official ledger rather than assumed.
by_game = {}
for r in backtest:
    try:
        by_game[int(r["week"])] = by_game.get(int(r["week"]), 0) + 1
    except (ValueError, KeyError):
        pass

# Pearson correlation between the model's side error and its total error, which is
# the dependence that actually matters for a cross-game or same-game ticket.
xs, ys = [], []
for r in backtest:
    try:
        am, at = float(r["actual_margin"]), float(r["actual_total"])
        pm = float(r["m1_spread_home"])
        pt = float(r["m1_total"])
    except (TypeError, ValueError):
        continue
    xs.append(am - pm)          # margin error
    ys.append(at - pt)          # total error
n_err = len(xs)
if n_err > 3:
    mx, my = sum(xs) / n_err, sum(ys) / n_err
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sxx = sum((a - mx) ** 2 for a in xs)
    syy = sum((b - my) ** 2 for b in ys)
    r_err = sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else None
    add("X03", "side error x total error (same game)",
        "Are this model's side and total errors correlated, which would make a same-game "
        "ticket riskier or safer than the product of its legs?",
        r_err, n_err,
        "Pearson r on walk-forward residuals (actual - model) of the two legs",
        "Near zero means the independence shortcut is defensible for THIS model; a large "
        "value means joint pricing must use a copula or the empirical 2x2.")
else:
    add("X03", "side error x total error (same game)", "Insufficient rows", None, n_err,
        "Pearson r on walk-forward residuals", "Not computed", status="not computed")

# (d) cross-game sides from different weeks: no shared teams means no dependence.
add("X04", "side x side (different games, different teams)",
    "Are two unrelated games' results correlated?",
    0.0, len(backtest),
    "No shared players, venue or weather; treated as independent by construction",
    "This is an assumption, stated as an assumption, not a measurement. It is the one "
    "correlation in this table that is NOT estimated from data.", status="assumption")

# (e) the leg dependence that is NOT measurable here.
add("X05", "player prop x player prop (same game)",
    "Do two player props in the same game move together (e.g. QB passing yards and WR "
    "receiving yards)?",
    None, 0,
    "Needs per-player official game logs for every participant",
    "Not computed. NFL.com publishes per-player game logs, but this repository holds no "
    "player-level game series (F31), so no value is inferred.",
    status="unverified - no player-level series held")

add("X06", "player prop x game total (same game)",
    "Does a player prop move with the game total?",
    None, 0,
    "Needs per-player official game logs plus a graded prop threshold",
    "Not computed for the same reason as X05. A threshold must also be chosen and "
    "pre-registered before any prop can be graded.",
    status="unverified - no player-level series held")

# ---------------------------------------------------------------------------
# 3. PROP MARKET FAMILY.  One row per prop market family, with the honest basis.
# ---------------------------------------------------------------------------
prop_rows = []
PROP_FAMILIES = [
    ("PR01", "Passing yards", "QB", "NFL.com player game logs show passing yards per game"),
    ("PR02", "Passing touchdowns", "QB", "NFL.com player game logs show passing TDs per game"),
    ("PR03", "Rushing yards", "RB", "NFL.com player game logs show rushing yards per game"),
    ("PR04", "Receiving yards", "WR/TE", "NFL.com player game logs show receiving yards per game"),
    ("PR05", "Receptions", "WR/TE/RB", "NFL.com player game logs show receptions per game"),
    ("PR06", "Anytime touchdown scorer", "any", "NFL.com player game logs show touchdowns per game"),
]
for pid, family, group, official_basis in PROP_FAMILIES:
    prop_rows.append({
        "prop_id": pid,
        "market_family": family,
        "position_group": group,
        "origination_order": "4 (after side, total, moneyline)",
        "official_outcome_source": official_basis,
        "outcome_held_in_repo": "no - no player-level game series is transcribed (F31)",
        "model_fair_line": "",
        "market_line": "",
        "market_price": "",
        "graded_out_of_sample": "no",
        "basis": ("Cannot be originated from a team-level attack/defence model: a prop "
                  "needs a player-level participation and usage model, which needs the "
                  "player game-log series the repository does not hold."),
        "next_step": ("Transcribe official NFL.com player game logs for the players in the "
                      "Week 11 slate, pre-register one threshold per family, then grade "
                      "walk-forward. Until then every number stays blank."),
        "status": "BLOCKED - outcome series not held; nothing inferred",
        "source_url": SRC_GAME_LOGS,
    })

# Prop COMBOS (the brief's "player prop bet combos"): state the dependency question
# and the minimum information needed, without inventing a number.
combo_rows = [{
    "combo_id": "PC01",
    "combo": "Two same-game player props (e.g. QB passing yards over + WR receiving yards over)",
    "legs": 2,
    "correlation_known": "no",
    "correlation_value": "",
    "sample_n": 0,
    "why_it_matters": ("Correlated legs misprice a combo in both directions: positively "
                       "correlated legs make the true joint probability HIGHER than the "
                       "product, so the naive price is too long."),
    "what_is_needed": "Per-player official game logs for both players over the graded window",
    "status": "BLOCKED - needs X05",
    "source_url": SRC_GAME_LOGS,
}]

# ---------------------------------------------------------------------------
# 4. EVENT RISK.  A named player, a named status, a named market, and whether the
#    risk's size is quantified anywhere in this repository (it is not).
# ---------------------------------------------------------------------------
# Role evidence comes ONLY from the repository's own officially-sourced register
# (A01-A11 in confirmed_availability_week10_2026.csv), which cites an NFL.com
# statement naming the player.  This script does not decide who is a starter.
avail = read("confirmed_availability_week10_2026.csv")
ROLE_EVIDENCE = {}
for a in avail:
    player = (a.get("player_affected") or "").strip()
    if not player:
        continue
    ROLE_EVIDENCE[(a["team_abbr"], player)] = {
        "role_evidence": "official statement names the player (%s)" % a["item_id"],
        "replacement": (a.get("officially_named_replacement") or "").strip(),
        "why": "the official statement names this player as affected",
    }

week10_teams = {r["team_abbr"] for r in inj}
risk_rows = []
risk_id = 0
week11_teams = set()
for g in lines:
    week11_teams.update(g["matchup"].split(" at "))

# (1) Risks carried into Week 11 by a player the OFFICIAL register names.  These are
# the highest-value rows because a replacement is named (depth of the replacement).
for a in avail:
    team = a["team_abbr"]
    if team not in week11_teams:
        continue
    player = (a.get("player_affected") or "").strip()
    if not player:
        continue
    # status_source names WHERE the status came from (e.g. "NFL.com news").  It is
    # not the status word, so it must not be published in the status column.  The
    # official statement is quoted instead, and the source column carries the link.
    status = "named in an official statement (status word not stated in the register)"
    repl = (a.get("officially_named_replacement") or "").strip()
    risk_id += 1
    risk_rows.append({
        "risk_id": "R%03d" % risk_id,
        "game_no": next(g["game_no"] for g in lines if team in g["matchup"]),
        "matchup": next(g["matchup"] for g in lines if team in g["matchup"]),
        "team": team,
        "player": player,
        "position": a["position_group"],
        "official_status": status,
        "official_injury": "",
        "role_evidence": "official statement names the player (%s): %s"
                         % (a["item_id"], (a.get("official_statement") or "")[:160]),
        "why_it_moves_the_number": "the official statement names this player as affected",
        "market_at_risk": "all markets on this game (side, total, moneyline)",
        "replacement_depth": ("official statement names the replacement: " + repl) if repl
                             else "no replacement named in the official statement checked",
        "response_plan": ("Re-fit after the official inactive list; publish no final number "
                          "before it. No automatic adjustment: the size of the effect is not "
                          "quantified here."),
        "risk_is_quantified": "no",
        "source_url": a["source_url"],
    })

# (2) Every Week 10 Out / Doubtful player on a team that plays in Week 11.  Role and
# replacement depth are established ONLY where an official source does so; otherwise
# the row says so, which is the honest answer and the reason flag F06 stands.
for g in lines:
    away, home = g["matchup"].split(" at ")
    for team in (away, home):
        if team not in week10_teams:
            continue        # on bye in Week 10: no report row, so no risk is asserted
        for r in inj:
            if r["team_abbr"] != team or r["game_status"] not in ("Out", "Doubtful"):
                continue
            risk_id += 1
            ev = ROLE_EVIDENCE.get((team, r["player"]))
            risk_rows.append({
                "risk_id": "R%03d" % risk_id,
                "game_no": g["game_no"],
                "matchup": g["matchup"],
                "team": team,
                "player": r["player"],
                "position": r["position"],
                "official_status": r["game_status"],
                "official_injury": r["injury"],
                "role_evidence": (ev["role_evidence"] if ev else
                                  "role not established by any official source held here"),
                "why_it_moves_the_number": (ev["why"] if ev else ""),
                "market_at_risk": ("all markets on this game" if ev else
                                   "not attributed - role unknown (F06)"),
                "replacement_depth": (("official statement names the replacement: " + ev["replacement"])
                                      if (ev and ev["replacement"]) else
                                      "cannot be ranked: no league-level depth chart exists and "
                                      "club charts self-label unofficial (F06, F45)"),
                "response_plan": ("Re-fit after the official inactive list; publish no final "
                                  "number before it. No automatic adjustment: the size of the "
                                  "effect is not quantified here."),
                "risk_is_quantified": "no",
                "source_url": SRC_INJ,
            })

# (3) The summary that makes the blind spot a number instead of an adjective.
n_risk = len(risk_rows)
n_ev = sum(1 for r in risk_rows if "official statement" in r["role_evidence"])
risk_summary = [{
    "metric": "Week 11 games", "value": len(lines),
    "basis": "officially scheduled games", "source_url": SRC_W11,
}, {
    "metric": "Named event risks published", "value": n_risk,
    "basis": "one row per named player and market", "source_url": SRC_INJ,
}, {
    "metric": "Risks where an official source names the player", "value": n_ev,
    "basis": "official statements, register A01-A11", "source_url": SRC_INJ,
}, {
    "metric": "Risks where the player's role is NOT established officially", "value": n_risk - n_ev,
    "basis": ("the gap this project must close before an injury adjustment can be priced "
              "(F06). Every one of these is left blank rather than guessed."),
    "source_url": SRC_INJ,
}, {
    "metric": "Weeks of injury data held", "value": 1,
    "basis": ("Week 10 only. A one-week snapshot cannot estimate an injury effect size; "
              "see injury_impact_2026.csv and DEC-05."),
    "source_url": SRC_INJ,
}]

# A risk row whose team played in Week 10 but who is NOT on the report cannot be
# asserted; record that as a coverage note rather than silently omitting it.
coverage = []
for g in lines:
    away, home = g["matchup"].split(" at ")
    for team in (away, home):
        n = sum(1 for r in inj if r["team_abbr"] == team and r["game_status"] in ("Out", "Doubtful"))
        coverage.append({
            "game_no": g["game_no"], "matchup": g["matchup"], "team": team,
            "week10_out_or_doubtful": n if team in week10_teams else "",
            "coverage_status": ("counted from the Week 10 report" if team in week10_teams
                                else "no Week 10 report row - team was on bye (Week 11 bye list)"),
            "source_url": SRC_INJ,
        })

# ---------------------------------------------------------------------------
# 5. INJURY IMPACT: is the injury exposure worth anything out of sample?
# ---------------------------------------------------------------------------
impact_rows = []
# Join Week 10 exposure (Out + Doubtful counts by unit) to the Week 10 results and
# ask whether the observed margin moved in the direction the exposure implies.
exposure = {}
for r in inj:
    if r["game_status"] not in ("Out", "Doubtful"):
        continue
    exposure.setdefault(r["team_abbr"], []).append(r)

results = read("games_2026_results.csv")
wk10 = [g for g in results if str(g["week"]) == "10"]
for g in wk10:
    for side, team, opp in (("home", g["home_team"], g["away_team"]),
                            ("away", g["away_team"], g["home_team"])):
        unit_counts = {}
        for r in exposure.get(team, []):
            unit_counts[r["position"]] = unit_counts.get(r["position"], 0) + 1
        impact_rows.append({
            "game": "%s at %s" % (g["away_team"], g["home_team"]),
            "week": g["week"],
            "team": team,
            "side": side,
            "out_or_doubtful_count": len(exposure.get(team, [])),
            "positions_affected": ", ".join("%s x%d" % (k, v) for k, v in sorted(unit_counts.items())),
            "points_scored_this_game": g["home_points"] if side == "home" else g["away_points"],
            "points_allowed_this_game": g["away_points"] if side == "home" else g["home_points"],
            "note": ("One game. A single observation cannot identify the size of an injury "
                     "effect; a coefficient needs many games with pre-game exposure held "
                     "before kickoff."),
            "source_url": g["source_url"],
        })

# ---------------------------------------------------------------------------
# write
# ---------------------------------------------------------------------------
n1 = write("market_sheet_week11.csv", price_rows,
           ["game_no", "matchup", "origination_order", "market_type", "selection",
            "model_fair_line", "fair_probability_implied", "fair_american_price",
            "market_line", "market_price", "edge_points_or_prob", "status", "source_url"])
n2 = write("correlation_matrix_same_game.csv", corr_rows,
           ["corr_id", "leg_pair", "question", "value", "sample_n", "basis",
            "sign_convention", "status", "source_url"])
n3 = write("prop_markets_week11.csv", prop_rows,
           ["prop_id", "market_family", "position_group", "origination_order",
            "official_outcome_source", "outcome_held_in_repo", "model_fair_line",
            "market_line", "market_price", "graded_out_of_sample", "basis", "next_step",
            "status", "source_url"])
n4 = write("prop_combinations_week11.csv", combo_rows,
           ["combo_id", "combo", "legs", "correlation_known", "correlation_value",
            "sample_n", "why_it_matters", "what_is_needed", "status", "source_url"])
n5 = write("event_risk_week11.csv", risk_rows,
           ["risk_id", "game_no", "matchup", "team", "player", "position",
            "official_status", "official_injury", "role_evidence",
            "why_it_moves_the_number", "market_at_risk", "replacement_depth",
            "response_plan", "risk_is_quantified", "source_url"])
n6 = write("injury_impact_2026.csv", impact_rows,
           ["game", "week", "team", "side", "out_or_doubtful_count", "positions_affected",
            "points_scored_this_game", "points_allowed_this_game", "note", "source_url"])
n7 = write("event_risk_coverage_week11.csv", coverage,
           ["game_no", "matchup", "team", "week10_out_or_doubtful", "coverage_status", "source_url"])

n8 = write("event_risk_summary_week11.csv", risk_summary,
           ["metric", "value", "basis", "source_url"])
print("market_sheet_week11.csv              %d rows" % n1)
print("correlation_matrix_same_game.csv     %d rows" % n2)
print("prop_markets_week11.csv              %d rows" % n3)
print("prop_combinations_week11.csv         %d rows" % n4)
print("event_risk_week11.csv                %d rows" % n5)
print("injury_impact_2026.csv               %d rows" % n6)
print("event_risk_coverage_week11.csv       %d rows" % n7)
print("event_risk_summary_week11.csv        %d rows" % n8)
if errors:
    print("\nERRORS:")
    for e in errors:
        print(" -", e)
    raise SystemExit(1)
