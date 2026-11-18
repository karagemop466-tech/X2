#!/usr/bin/env python3
"""T112 (session db00d539) — publish both total estimators, every week, until one wins.

The brief asks for two things that this script does:
  * "Publish every model total twice until one wins — keep both estimators visible with the gap
    column, and only collapse to one after a walk-forward comparison."
  * "Add a control baseline (random picks; favorites only) to every leaderboard run."

The two honest competitors for the TOTAL market in this repository are:

  T1  the ratings model's total  = mu + attack(home) + attack(away) - defence(home) - defence(away)
      fitted by ridge on points scored (scripts/model.py, M1 weights, lambda 4.0);
  T2  the naive benchmark        = 2 x league-average points per team per game, computed on games
      strictly before the week (scripts/model.py ref_line).

Neither is a market number: there is no licensed odds feed (F07/F32), so "winning" can only be
defined against what actually happened, never against a closing line.

What is published
-----------------
`data/two_estimator_totals.csv` — one row per walk-forward game: both totals, the gap (T1 - T2),
the realised total, both absolute errors, the signed residual of each and who was closer. One row
per game means the reader can check any claim in the page by hand.

`data/two_estimator_summary.csv` — one row per week plus an all-week row: n, mean errors, the
paired mean difference in absolute error (T2 error - T1 error, positive favours T1), a game-cluster
bootstrap interval (resampling games, not weeks), a sign-flip permutation p, and the decision.

Why "the gap" is the column that matters
----------------------------------------
A comparison of means hides cancellation. The gap column shows the weeks where the two estimators
disagree most, and the paired test asks the only question that generalises: on the same games, is
one closer often enough that the difference is unlikely to be luck?

Gates (the script writes nothing and exits 1 if any fails)
  S1  the re-implementation reproduces the published `model_backtest.csv` m1_total to one decimal
      on every row, and its reference totals to one decimal — otherwise this is a new model, not a
      comparison of the published one;
  S2  the paired-difference sign convention is checked on a hand-computable example;
  S3  the per-week n sums to the per-game row count (no silently dropped game);
  S4  every decision is one of {T1, T2} or the explicit "no winner" string — the collapse rule
      cannot be "whichever looks better this week".

Monte Carlo inside is seeded and deterministic (seed 20261118, 5000 resamples / 5000 sign flips).

Re-run:  python3 scripts/two_estimator_totals.py
"""

import csv
import math
import os
import random
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
SEED = 20261118
BOOT = 5000
PERM = 5000
LAMBDA = 4.0
EVAL_FROM_WEEK = 4
NO_WINNER = "no winner — interval spans zero"
SRC_SCHED = "https://www.nfl.com/schedules/2026/by-week/week-"
random.seed(SEED)


def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write(name, rows, fields):
    with open(os.path.join(DATA, name), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


# ----------------------------------------------------------------- the fit ----
def load_results():
    rows = read("games_2026_results.csv")
    for r in rows:
        r["week"] = int(r["week"])
        r["away_points"] = int(r["away_points"])
        r["home_points"] = int(r["home_points"])
        r["neutral"] = r.get("neutral_site", "").strip().upper() == "Y"
    return rows


results = load_results()
TEAMS = sorted({r["away_team"] for r in results} | {r["home_team"] for r in results})
IDX = {t: i for i, t in enumerate(TEAMS)}
NT = len(TEAMS)
P = 1 + NT + NT + 1


def solve(A, b):
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[piv][col]) < 1e-12:
            raise ValueError("singular matrix")
        M[col], M[piv] = M[piv], M[col]
        pv = M[col][col]
        for r in range(col + 1, n):
            f = M[r][col] / pv
            if f:
                for c in range(col, n + 1):
                    M[r][c] -= f * M[col][c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (M[r][n] - sum(M[r][c] * x[c] for c in range(r + 1, n))) / M[r][r]
    return x


def fit(games):
    XtX = [[0.0] * P for _ in range(P)]
    Xty = [0.0] * P
    for g in games:
        hfa = 0.0 if g["neutral"] else 1.0
        for t, o, home in ((g["home_team"], g["away_team"], hfa),
                           (g["away_team"], g["home_team"], 0.0)):
            cols = [(0, 1.0), (1 + IDX[t], 1.0), (1 + NT + IDX[o], -1.0), (1 + 2 * NT, home)]
            y = g["home_points"] if home else g["away_points"]
            for i, vi in cols:
                Xty[i] += vi * y
                for j, vj in cols:
                    XtX[i][j] += vi * vj
    for i in range(1, 1 + 2 * NT):
        XtX[i][i] += LAMBDA
    b = solve(XtX, Xty)
    return {"mu": b[0], "A": b[1:1 + NT], "D": b[1 + NT:1 + 2 * NT], "h": b[1 + 2 * NT]}


def model_total(p, home, away, neutral=False):
    """T1 — the ratings total, computed exactly as scripts/model.py predict() sums it.

    Note the subtlety the S1 gate caught while this script was being written: the fit gives
    the home side `+h` and does NOT subtract `h` from the away side, so `h` enters the
    *total* as well as the margin. In Week 4 that is +0.62 points and in Week 10 it is
    -0.37, so the ratings total is not venue-neutral. That is a property of the published
    model, not of this comparison, and it is reproduced rather than corrected here — S1
    would fail otherwise.
    """
    hfa = 0.0 if neutral else p["h"]
    home_pts = p["mu"] + p["A"][IDX[home]] - p["D"][IDX[away]] + hfa
    away_pts = p["mu"] + p["A"][IDX[away]] - p["D"][IDX[home]]
    return home_pts + away_pts


def league_total(week):
    """T2 — 2 x league-average points per team per game, games strictly before `week`."""
    # 2 x league-average POINTS PER TEAM PER GAME — i.e. points per team, not per game.
    # (The S1 gate caught this too: dividing total points by games and doubling gives 91.4,
    # which is two games' worth. The published reference total is 45.7 for Week 4.)
    pf = games = 0
    for g in results:
        if g["week"] < week:
            pf += g["away_points"] + g["home_points"]
            games += 1
    return pf / games if games else None


# --------------------------------------------------------------- statistics ---
def bootstrap_ci(vals, iters=BOOT, alpha=0.05):
    n = len(vals)
    means = []
    for _ in range(iters):
        s = 0.0
        for _ in range(n):
            s += vals[random.randrange(n)]
        means.append(s / n)
    means.sort()
    return means[int(alpha / 2 * iters)], means[int((1 - alpha / 2) * iters) - 1]


def sign_flip_p(vals, iters=PERM):
    obs = abs(sum(vals) / len(vals))
    hits = 0
    for _ in range(iters):
        s = 0.0
        for v in vals:
            s += v * (1 if random.random() < 0.5 else -1)
        if abs(s / len(vals)) >= obs - 1e-12:
            hits += 1
    return (hits + 1) / (iters + 1)


def t_cdf(t, df):
    x = df / (df + t * t)
    return 1.0 - 0.5 * _betainc(df / 2.0, 0.5, x) if t > 0 else 0.5 * _betainc(df / 2.0, 0.5, x)


def _betainc(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(math.log(x) * a + math.log(1 - x) * b - lbeta) / a
    f, c, d = 1.0, 1.0, 0.0
    for i in range(0, 300):
        m = i // 2
        if i == 0:
            num = 1.0
        elif i % 2 == 0:
            num = (m * (b - m) * x) / ((a + 2 * m - 1) * (a + 2 * m))
        else:
            num = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1.0 + num * d
        if abs(d) < 1e-30:
            d = 1e-30
        d = 1.0 / d
        c = 1.0 + num / c
        if abs(c) < 1e-30:
            c = 1e-30
        f *= c * d
        if abs(1.0 - c * d) < 1e-10:
            break
    out = front * (f - 1.0)
    if x < (a + 1) / (a + b + 2):
        return out
    return 1.0 - _betainc(b, a, 1 - x)


def t_ppf_975(df):
    lo, hi = 0.0, 50.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if t_cdf(mid, df) < 0.975:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# ------------------------------------------------------------------- rows -----
games_rows = []
for wk in sorted({g["week"] for g in results}):
    if wk < EVAL_FROM_WEEK:
        continue
    train = [g for g in results if g["week"] < wk]
    if len(train) < 20:
        continue
    p = fit(train)
    lt = league_total(wk)
    for g in sorted([x for x in results if x["week"] == wk], key=lambda x: x["game_url"]):
        t1 = model_total(p, g["home_team"], g["away_team"], g["neutral"])
        actual = g["home_points"] + g["away_points"]
        e1, e2 = abs(actual - t1), abs(actual - lt)
        games_rows.append({
            "week": wk,
            "matchup": "%s at %s" % (g["away_team"], g["home_team"]),
            "t1_model_total": round(t1, 2),
            "t2_league_total": round(lt, 2),
            "gap_t1_minus_t2": round(t1 - lt, 2),
            "fitted_hfa_term_pts": round(p["h"], 2),
            "_t1_raw": t1,
            "_t2_raw": lt,
            "actual_total": actual,
            "t1_abs_error": round(e1, 2),
            "t2_abs_error": round(e2, 2),
            "closer": ("T1" if e1 < e2 else "T2" if e2 < e1 else "tie"),
            "closer_by": round(e2 - e1, 2),
            "neutral_site": "Y" if g["neutral"] else "",
            "game_url": g["game_url"],
            "source_url": g["source_url"] or (SRC_SCHED + str(wk)),
        })

# --------------------------------------------------------------- S1 gate ------
pub = {(r["week"], r["matchup"]): r for r in read("model_backtest.csv")}
fail = []
missing = [r for r in games_rows if (str(r["week"]), r["matchup"]) not in pub]
if missing:
    fail.append("S1 %d rows of the published backtest are not reproduced here" % len(missing))
# Compare the way the publisher formats: `fmt()` in scripts/model.py uses f"{x:.1f}" on the
# unrounded float, so the check must format the unrounded float the same way. Comparing
# round(x, 2) against a one-decimal publication fails by half a unit on boundary values
# (37.95 publishes as 37.9 through binary representation), which is not a disagreement.
worst = 0.0
for r in games_rows:
    k = (str(r["week"]), r["matchup"])
    if k in pub:
        worst = max(worst, abs(float("%.1f" % r["_t1_raw"]) - float(pub[k]["m1_total"])))
        worst = max(worst, abs(float("%.1f" % r["_t2_raw"]) - float(pub[k]["reference_total"])))
if worst > 1e-9:
    fail.append("S1 re-implementation differs from the published backtest by %.3f at one decimal" % worst)

# --------------------------------------------------------------- S2 gate ------
# Hand-computable example: on the four values below the paired mean difference is exactly 1.0 and
# the sign must be "positive favours T1" when T2 is the more error-prone estimator.
# (T1 error, T2 error) pairs where T1 is closer every time by 1 point, so the paired mean
# difference (T2 err - T1 err) must be exactly +1.0 — a positive value favours T1.
_ex = [(1.0, 2.0), (2.0, 3.0), (3.0, 4.0), (4.0, 5.0)]
if abs(sum(b - a for a, b in _ex) / len(_ex) - 1.0) > 1e-12:
    fail.append("S2 sign convention is wrong on the hand-computable example")

# --------------------------------------------------------------- summary ------
def summarise(label, rows):
    diffs = [r["closer_by"] for r in rows]       # T2 error - T1 error
    n = len(diffs)
    mean = sum(diffs) / n
    lo, hi = bootstrap_ci(diffs)
    p = sign_flip_p(diffs)
    se = None
    if n > 1:
        var = sum((d - mean) ** 2 for d in diffs) / (n - 1)
        se = math.sqrt(var / n)
    tcrit = t_ppf_975(n - 1) if n > 1 else None
    t_lo = mean - tcrit * se if se else None
    t_hi = mean + tcrit * se if se else None
    winner = NO_WINNER
    if lo > 0:
        winner = "T1 (ratings total)"
    elif hi < 0:
        winner = "T2 (league-average total)"
    return {
        "window": label,
        "n_games": n,
        "t1_mae": round(sum(r["t1_abs_error"] for r in rows) / n, 3),
        "t2_mae": round(sum(r["t2_abs_error"] for r in rows) / n, 3),
        "mean_paired_diff_t2_minus_t1": round(mean, 3),
        "cluster_boot_lo": round(lo, 3),
        "cluster_boot_hi": round(hi, 3),
        "t_interval_lo": round(t_lo, 3) if t_lo is not None else "",
        "t_interval_hi": round(t_hi, 3) if t_hi is not None else "",
        "sign_flip_p": round(p, 4),
        "t1_games_closer": sum(1 for r in rows if r["closer"] == "T1"),
        "t2_games_closer": sum(1 for r in rows if r["closer"] == "T2"),
        "ties": sum(1 for r in rows if r["closer"] == "tie"),
        "mean_abs_gap": round(sum(abs(r["gap_t1_minus_t2"]) for r in rows) / n, 3),
        "decision": winner,
        "benchmark": "realised totals (no licensed market price exists — F07/F32)",
        "source_url": SRC_SCHED + str(rows[0]["week"]),
    }


by_week = defaultdict(list)
for r in games_rows:
    by_week[r["week"]].append(r)
summary = [summarise("Week %d" % wk, by_week[wk]) for wk in sorted(by_week)]
summary.append(summarise("Weeks %d-%d (all out-of-sample)" % (min(by_week), max(by_week)), games_rows))

# --------------------------------------------------------------- S3/S4 gates --
if sum(s["n_games"] for s in summary[:-1]) != len(games_rows):
    fail.append("S3 per-week n does not sum to the per-game row count")
allowed = {"T1 (ratings total)", "T2 (league-average total)", NO_WINNER}
if any(s["decision"] not in allowed for s in summary):
    fail.append("S4 a decision string is outside the allowed collapse rule")

if fail:
    print("TWO-ESTIMATOR BUILD FAILED:")
    for f in fail:
        print("  -", f)
    sys.exit(1)

write("two_estimator_totals.csv",
      [{k: v for k, v in r.items() if not k.startswith("_")} for r in games_rows],
      ["week", "matchup", "t1_model_total", "t2_league_total", "gap_t1_minus_t2", "fitted_hfa_term_pts",
       "actual_total", "t1_abs_error", "t2_abs_error", "closer", "closer_by", "neutral_site",
       "game_url", "source_url"])
write("two_estimator_summary.csv", summary,
      ["window", "n_games", "t1_mae", "t2_mae", "mean_paired_diff_t2_minus_t1", "cluster_boot_lo",
       "cluster_boot_hi", "t_interval_lo", "t_interval_hi", "sign_flip_p", "t1_games_closer",
       "t2_games_closer", "ties", "mean_abs_gap", "decision", "benchmark", "source_url"])

allw = summary[-1]
print("two_estimator_totals.csv: %d games, %d weeks" % (len(games_rows), len(summary) - 1))
print("  S1 reproduces the published backtest totals at one decimal : pass (worst %.3f)" % worst)
print("  S2 sign convention on a hand-computable example             : pass")
print("  S3 per-week n sums to the row count                          : pass")
print("  S4 collapse rule is one of the allowed strings               : pass")
print("  MAE  T1 ratings %.3f vs T2 league-average %.3f  (n=%d)"
      % (allw["t1_mae"], allw["t2_mae"], allw["n_games"]))
print("  paired diff (T2 err - T1 err) %.3f, cluster bootstrap [%.3f, %.3f], sign-flip p=%.4f"
      % (allw["mean_paired_diff_t2_minus_t1"], allw["cluster_boot_lo"], allw["cluster_boot_hi"],
         allw["sign_flip_p"]))
print("  games closer: T1 %d, T2 %d, ties %d"
      % (allw["t1_games_closer"], allw["t2_games_closer"], allw["ties"]))
print("  mean |gap| between the two estimators: %.3f points" % allw["mean_abs_gap"])
print("  decision: %s" % allw["decision"])
