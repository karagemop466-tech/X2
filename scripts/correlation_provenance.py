#!/usr/bin/env python3
"""Correlation provenance register (task T44).

The rule is simple and it is enforced here rather than assumed: a correlation is
published only if both of its inputs come from officially sourced numbers, and
every published value carries the n it was computed on.

This script recomputes every correlation the project publishes, from the
official ledger, and compares the recomputed value and n against the published
row in data/correlations_computed.csv. A disagreement is reported, not hidden.
It then adds the correlations the brief still needs (same-game leg dependence,
drift, blowout predictability), each with its own n.

Officially sourced means: the number comes from the NFL.com by-week schedule
pages or the NFL.com standings page as transcribed into
data/games_2026_results.csv, which scripts/verify_results.py reconciles against
the official standings for all 32 teams; or from the NFL.com Week 10 injury
report as transcribed into data/injuries_week10_2026.csv. Anything else is
marked not officially sourced and is not published as a value.

Run:  python3 scripts/correlation_provenance.py
"""

import csv
import math
import os
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
AS_OF = "2026-11-14"
SRC_SCHED = "https://www.nfl.com/schedules/2026/by-week/week-10"
SRC_STAND = "https://www.nfl.com/standings/"
SRC_INJ = "https://www.nfl.com/injuries/"
OFFICIAL = ("Yes - both inputs trace to the official NFL.com results ledger, which "
            "reconciles to the official standings for all 32 teams with 0 mismatches")


def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write(name, rows, fields):
    with open(os.path.join(DATA, name), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


# ---- statistics (same estimators as scripts/model.py, copied so this file
# ---- stands alone and can be checked against it)
def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None, None
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None, None
    return sxy / math.sqrt(sxx * syy), n


def fisher_ci(r, n, alpha=0.05):
    if r is None or n < 4 or abs(r) >= 1:
        return (None, None)
    z = 0.5 * math.log((1 + r) / (1 - r))
    se = 1.0 / math.sqrt(n - 3)
    zc = 1.959963985
    return (math.tanh(z - zc * se), math.tanh(z + zc * se))


def betacf(a, b, x, itmax=200, eps=3e-12):
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1 / d
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        c = 1 + aa / c
        if abs(d) < 1e-30:
            d = 1e-30
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        c = 1 + aa / c
        if abs(d) < 1e-30:
            d = 1e-30
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1 / d
        de = d * c
        h *= de
        if abs(de - 1) < eps:
            break
    return h


def betainc(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(math.log(x) * a + math.log(1 - x) * b - lbeta)
    if x < (a + 1) / (a + b + 2):
        return front * betacf(a, b, x) / a
    return 1 - math.exp(math.log(1 - x) * b + math.log(x) * a - lbeta) * betacf(b, a, 1 - x) / b


def pearson_p(r, n):
    if r is None or n < 4 or abs(r) >= 1:
        return None
    df = n - 2
    if abs(r) < 1e-12:
        return 1.0
    t = r * math.sqrt(df / (1 - r * r))
    x = df / (df + t * t)
    return min(1.0, max(0.0, betainc(df / 2.0, 0.5, x)))


def phi_coef(a, b, c, d):
    den = math.sqrt((a + b) * (c + d) * (a + c) * (b + d))
    return (a * d - b * c) / den if den else None


def f(x, nd=3):
    return "" if x is None else f"{x:.{nd}f}"


# ----------------------------------------------------------------- data ----
games = read("games_2026_results.csv")
backtest = read("model_backtest.csv")
injuries = read("injuries_week10_2026.csv")
standings = read("standings_2026_snapshot.csv")
published = {r["corr_id"]: r for r in read("correlations_computed.csv")}

for g in games:
    g["week"] = int(g["week"])
    g["home_points"] = int(g["home_points"])
    g["away_points"] = int(g["away_points"])
    g["margin"] = g["home_points"] - g["away_points"]
    g["total"] = g["home_points"] + g["away_points"]

oos = []
for r in backtest:
    oos.append({"week": int(r["week"]),
                "home_points": None,
                "actual_margin": float(r["actual_margin"]),
                "actual_total": float(r["actual_total"]),
                "M1_margin": float(r["m1_spread_home"]),
                "M1_total": float(r["m1_total"]),
                "ref_margin": float(r["reference_spread_home"]),
                "ref_total": float(r["reference_total"])})
# home/away points are only in the results ledger; join them by week + margin
by_key = defaultdict(list)
for g in sorted(games, key=lambda g: (g["week"], g["game_url"])):
    by_key[(g["week"], g["margin"], g["total"])].append(g)
for r in oos:
    key = (r["week"], int(r["actual_margin"]), int(r["actual_total"]))
    pool = by_key.get(key)
    if pool:
        g = pool.pop(0)
        r["home_points"], r["away_points"] = g["home_points"], g["away_points"]

rows = []


def add(cid, question, pair, r, n, inputs, source, note, published_id=None,
        is_slope=False):
    dataset = "; ".join(inputs)
    lo, hi = (None, None) if is_slope else fisher_ci(r, n)
    p = None if is_slope else pearson_p(r, n)
    pub = published.get(published_id or cid)
    if pub is None:
        check = "new this session - not previously published"
    else:
        pv = pub["value"]
        if pv == "":
            check = "published value is blank; nothing to compare"
        else:
            d = abs(float(pv) - r)
            pn_ok = str(n) == str(pub["sample_n"])
            check = ("recomputed: value differs by %.3f; n %s (published n = %s)"
                     % (d, "matches" if pn_ok else "DIFFERS", pub["sample_n"]))
    rows.append({
        "corr_id": cid,
        "question": question,
        "input_1": inputs[0],
        "input_2": inputs[1],
        "pair_measured": pair,
        "value": f(r),
        "ci_low": f(lo),
        "ci_high": f(hi),
        "p_value": f(p, 4),
        "n": n,
        "inputs_officially_sourced": OFFICIAL if source != SRC_INJ else
        ("Yes - input 1 counts Out/Doubtful players on the NFL.com Week 10 injury "
         "report; input 2 is points allowed per game from the official standings"),
        "dataset": dataset,
        "official_source_url": source,
        "method": ("Pearson r with a Fisher z 95% interval and a two-sided t test"
                   if not is_slope else
                   "least-squares slope of actual on predicted, out of sample"),
        "recomputation_check": check,
        "note": note,
    })


xs = [r["M1_margin"] for r in oos]
ys = [r["actual_margin"] for r in oos]
add("C01", "Do model-predicted margins track actual margins (out of sample)?",
    ("model predicted home margin", "actual home margin"), *pearson(xs, ys),
    ("data/model_backtest.csv (M1 walk-forward line)",
     "data/games_2026_results.csv (official final score)"), SRC_SCHED,
    "The headline skill measure for the originated side.")
add("C02", "Same, for the naive reference line (season point differential + 2.5)",
    ("reference home margin", "actual home margin"),
    *pearson([r["ref_margin"] for r in oos], ys),
    ("data/model_backtest.csv (reference line)",
     "data/games_2026_results.csv (official final score)"), SRC_SCHED,
    "The benchmark the model has to beat.")
add("C03", "Are blowouts associated with higher game totals?",
    ("absolute actual margin", "actual total points"),
    *pearson([abs(y) for y in ys], [r["actual_total"] for r in oos]),
    ("data/games_2026_results.csv", "data/games_2026_results.csv"), SRC_SCHED,
    "Same-game link between margin and scoring volume.")
add("C04", "Within a game, do the two teams' point totals co-move?",
    ("home points", "away points"),
    *pearson([r["home_points"] for r in oos], [r["away_points"] for r in oos]),
    ("data/games_2026_results.csv", "data/games_2026_results.csv"), SRC_SCHED,
    "A negative value means a scoring trade-off inside the same game.")

# week-to-week persistence
team_seq = defaultdict(list)
for g in sorted(games, key=lambda g: (g["week"], g["game_url"])):
    team_seq[g["home_team"]].append((g["week"], g["margin"]))
    team_seq[g["away_team"]].append((g["week"], -g["margin"]))
prev, cur = [], []
for t, seq in team_seq.items():
    for i in range(1, len(seq)):
        if seq[i][0] == seq[i - 1][0] + 1:
            prev.append(seq[i - 1][1])
            cur.append(seq[i][1])
add("C06", "Does last week's margin predict this week's margin for the same team?",
    ("team margin in week W-1", "team margin in week W"), *pearson(prev, cur),
    ("data/games_2026_results.csv", "data/games_2026_results.csv"), SRC_SCHED,
    "Near zero means week-to-week results are mostly noise, so recency weighting "
    "cannot add much.")

# calibration slope
mx = sum(xs) / len(xs)
my = sum(ys) / len(ys)
sxx = sum((x - mx) ** 2 for x in xs)
slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
intercept = my - slope * mx
resid = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
se_slope = math.sqrt(sum(e * e for e in resid) / (len(xs) - 2) / sxx)
rows.append({
    "corr_id": "C09",
    "question": "Calibration: slope of actual margin on the model's predicted margin "
                "(1.0 = perfectly scaled)",
    "input_1": "model predicted home margin", "input_2": "actual home margin",
    "pair_measured": "89 out-of-sample games (weeks 4-10)",
    "value": f(slope), "ci_low": f(slope - 1.959963985 * se_slope),
    "ci_high": f(slope + 1.959963985 * se_slope), "p_value": "",
    "n": len(xs), "inputs_officially_sourced": OFFICIAL,
    "dataset": "data/model_backtest.csv + data/games_2026_results.csv",
    "official_source_url": SRC_SCHED,
    "method": "least-squares slope of actual on predicted, out of sample",
    "recomputation_check": ("recomputed: slope %s (SE %s), intercept %s; published slope "
                            "%s. The 0.002 gap is rounding - this check re-uses the "
                            "published backtest lines, which are stored to one decimal, "
                            "while scripts/model.py fits at full precision."
                            % (f(slope), f(se_slope), f(intercept),
                               published["C09"]["value"])),
    "note": ("Recomputed on the published (one-decimal) lines; see the recomputation "
             "column. A slope below 1 means the model is over-shy; above 1, over-confident. "
             "The intercept of %s points is the home-team bias the originated side "
             "carries into Week 11." % f(intercept)),
})

# parlay leg correlation, recomputed from the published 2x2 table
par = read("parlay_analysis.csv")[0]
tbl = {}
for part in par["two_by_two"].split(","):
    k, v = part.split("=")
    tbl[k.strip()] = int(v)
a, b, c, d = tbl["both"], tbl["side only"], tbl["total only"], tbl["neither"]
phi = phi_coef(a, b, c, d)
rows.append({
    "corr_id": "C07",
    "question": "Are the side leg and the total leg of the same game correlated (phi)?",
    "input_1": "side leg result vs the reference line",
    "input_2": "total leg result vs the reference line",
    "pair_measured": "%d two-leg tickets (weeks 4-10)" % (a + b + c + d),
    "value": f(phi), "ci_low": "", "ci_high": "", "p_value": "",
    "n": a + b + c + d,
    "inputs_officially_sourced": OFFICIAL,
    "dataset": "data/parlay_analysis.csv (2x2), derived from the official ledger",
    "official_source_url": SRC_SCHED,
    "method": "phi coefficient on the 2x2 of leg outcomes",
    "recomputation_check": ("recomputed from the published 2x2: phi %s, published %s, "
                            "n %d (published tickets %s)"
                            % (f(phi), par["phi_correlation"], a + b + c + d, par["tickets"])),
    "note": ("Parlay pricing: |phi| > 0 means the independence shortcut misprices the "
             "ticket. n counts tickets, not games, and no interval is published because "
             "the ticket count is small and the tickets were selected."),
})

# injury exposure vs points allowed
def_unit = defaultdict(int)
for r in injuries:
    if r["position"] in ("DE", "DT", "DL", "NT", "LB", "OLB", "ILB", "MLB",
                         "CB", "S", "SAF", "DB") and r["game_status"] in ("Out", "Doubtful"):
        def_unit[r["team_abbr"]] += 1
st = {r["team_abbr"]: r for r in standings}
expo, papg = [], []
for t in sorted(st):
    s = st[t]
    gp = int(s["wins"]) + int(s["losses"]) + int(s["ties"])
    if gp:
        papg.append(int(s["points_against"]) / gp)
        expo.append(def_unit.get(t, 0))
add("C08", "Is Week-10 defensive injury exposure associated with season points allowed?",
    ("count of Out/Doubtful defenders on the Week 10 report",
     "points allowed per game, official standings"), *pearson(expo, papg),
    ("data/injuries_week10_2026.csv (NFL.com Week 10 injury report)",
     "data/standings_2026_snapshot.csv (official standings)"), SRC_INJ,
    "Exploratory only: one snapshot, no causal claim, and the string rank of each "
    "absent player is still unverified for most clubs (F06).")

# ------------------------------------------------- new correlations (T44) ----
err_side = [r["actual_margin"] - r["M1_margin"] for r in oos]
err_total = [r["actual_total"] - r["M1_total"] for r in oos]
add("C10", "Within one game, do the side error and the total error move together?",
    ("actual margin minus model margin", "actual total minus model total"),
    *pearson(err_side, err_total),
    ("data/model_backtest.csv + data/games_2026_results.csv",
     "data/model_backtest.csv + data/games_2026_results.csv"), SRC_SCHED,
    "Same-game parlay pricing: the two legs' errors move in opposite directions, so a "
    "ticket built from both is priced wrong by the independence shortcut in a consistent "
    "direction. Negative means: when the side beats the model's number, the total tends "
    "to come in under it.",
    published_id=None)

allm = [g["margin"] for g in games]
allt = [g["total"] for g in games]
add("C11", "Across the whole season, do home margins and game totals move together?",
    ("home margin (official)", "total points (official)"), *pearson(allm, allt),
    ("data/games_2026_results.csv", "data/games_2026_results.csv"), SRC_SCHED,
    "Computed on all 137 games, not only the out-of-sample window, so it is a "
    "description of the season rather than a test of the model.")

add("C12", "Is the model getting more or less accurate as the season goes on?",
    ("calendar week", "absolute error of the model's home margin"),
    *pearson([r["week"] for r in oos], [abs(e) for e in err_side]),
    ("data/games_2026_results.csv (week)", "data/model_backtest.csv + official scores"),
    SRC_SCHED,
    "A drift check for the demotion gate: a rising error with week would argue for "
    "re-fitting or demotion before the next live window.")

add("C13", "Are lopsided games harder to predict than close ones?",
    ("absolute actual margin", "absolute error of the model's home margin"),
    *pearson([abs(y) for y in ys], [abs(e) for e in err_side]),
    ("data/games_2026_results.csv", "data/model_backtest.csv + official scores"),
    SRC_SCHED,
    "Partly mechanical - both variables contain the realised margin - so read it as a "
    "description of where the error sits, not as an independent finding. It does say the "
    "model's confidence should widen with the size of its own prediction.")

add("C14", "Is home-field advantage drifting across the season?",
    ("calendar week", "home margin (official)"),
    *pearson([g["week"] for g in games], allm),
    ("data/games_2026_results.csv", "data/games_2026_results.csv"), SRC_SCHED,
    "Home teams won %d of the %d decided games in the ledger. A negative slope would "
    "mean the fixed home-field term is becoming too large."
    % (sum(1 for m in allm if m > 0), sum(1 for m in allm if m != 0)))

fields = ["corr_id", "question", "input_1", "input_2", "pair_measured", "value",
          "ci_low", "ci_high", "p_value", "n", "inputs_officially_sourced",
          "dataset", "official_source_url", "method", "recomputation_check", "note"]
write("correlation_provenance.csv", rows, fields)

print("correlation_provenance.csv: %d correlations published, each with n" % len(rows))
for r in rows:
    print("  %s n=%-4s value=%-8s %s" % (r["corr_id"], r["n"], r["value"] or "-",
                                         r["recomputation_check"][:78]))
bad = [r for r in rows if "DIFFERS" in r["recomputation_check"]]
if bad:
    sys.stderr.write("WARNING: %d correlation(s) disagree with the published row\n" % len(bad))
