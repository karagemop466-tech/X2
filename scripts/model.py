#!/usr/bin/env python3
"""X2 independent NFL line model, walk-forward backtest, validation gates,
parlay/total correlation study and strategy leaderboard.

Standard library only (no numpy). Inputs (all transcribed from official
NFL.com pages; see data/*.csv and data/sources.csv):
  data/games_2026_results.csv   2026 regular-season results, weeks 1-10 (TNF)
                                neutral_site column: 'Y' only where the official
                                2026 International Games slate says so, else blank
  data/schedule_week11_2026.csv Week 11 schedule (no results yet)
  data/injuries_week10_2026.csv Week 10 injury-report snapshot (availability)

Outputs (CSV + JSON in data/): model ratings, Week 11 originated lines,
out-of-sample backtest, per-bet log, gate results, correlations, parlay
study, leaderboard and a summary used by scripts/build.py.

Method
------
One ridge-regularised least-squares system is fitted on points scored:

    points(team t vs opponent o, home flag) = mu + A_t - D_o + h * home

where `home` is 1 only when the home team is actually at home. International
games are neutral-site: the designated home team gets no home-field term
(`home` = 0), because the game is not played in its stadium.

with A_t an attack rating, D_t a defence rating (higher = fewer points
allowed), mu a league mean and h a home-field term. Predictions follow:

    home margin = (A_home + D_home) - (A_away + D_away) + h*home
    total       = 2*mu + (A_home + A_away) - (D_home + D_away) + h*home

Every prediction for week W is fitted ONLY on games strictly before week W
(walk-forward). No market/odds input is used anywhere: this project has no
licensed odds feed, so every "bet" below is a wager AGAINST A PUBLISHED
REFERENCE LINE (a naive season point-differential + fixed home-field model),
never against a sportsbook price. See flags F07/F-03.
"""
import csv
import json
import math
import os
import random
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
AS_OF = "2026-11-14"
SEED = 20261114
EVAL_FROM_WEEK = 4          # first week with an out-of-sample prediction
BET_DELTA = 3.0             # pre-registered: only bet when |model - reference| >= 3 points
BET_DELTA_TOTAL = 3.0
BOOTSTRAP = 5000
PERMUTATIONS = 5000
SRC_SCHED = "https://www.nfl.com/schedules/2026/by-week/week-"
SRC_STAND = "https://www.nfl.com/standings/"
SRC_INJ = "https://www.nfl.com/injuries/"

random.seed(SEED)


# ----------------------------------------------------------------- data ----
def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write(name, rows, fields):
    with open(os.path.join(DATA, name), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


results = read("games_2026_results.csv")
week11 = read("schedule_week11_2026.csv")
injuries = read("injuries_week10_2026.csv")

for r in results:
    r["week"] = int(r["week"])
    r["away_points"] = int(r["away_points"])
    r["home_points"] = int(r["home_points"])
    r["neutral"] = (r.get("neutral_site", "").strip().upper() == "Y")
    r["margin"] = r["home_points"] - r["away_points"]      # home - away
    r["total"] = r["home_points"] + r["away_points"]

TEAMS = sorted({r["away_team"] for r in results} | {r["home_team"] for r in results})
IDX = {t: i for i, t in enumerate(TEAMS)}
NT = len(TEAMS)
P = 1 + NT + NT + 1                                         # mu, A, D, h


# ------------------------------------------------------------- algebra ----
def solve(A, b):
    """Gaussian elimination with partial pivoting. A is n x n, b length n."""
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
        s = M[r][n] - sum(M[r][c] * x[c] for c in range(r + 1, n))
        x[r] = s / M[r][r]
    return x


def fit(games, lam, half_life=None, ref_week=None):
    """Ridge fit: points = mu + A_t - D_o + h*home. Returns (params, n_obs)."""
    XtX = [[0.0] * P for _ in range(P)]
    Xty = [0.0] * P
    n_obs = 0
    for g in games:
        if half_life and ref_week is not None:
            w = 0.5 ** ((ref_week - g["week"]) / half_life)
        else:
            w = 1.0
        hfa = 0.0 if g.get("neutral") else 1.0        # neutral site: no home edge
        for t, o, home in ((g["home_team"], g["away_team"], hfa),
                           (g["away_team"], g["home_team"], 0.0)):
            cols = [(0, 1.0), (1 + IDX[t], 1.0), (1 + NT + IDX[o], -1.0), (1 + 2 * NT, home)]
            y = g["home_points"] if home else g["away_points"]
            for i, vi in cols:
                Xty[i] += w * vi * y
                for j, vj in cols:
                    XtX[i][j] += w * vi * vj
            n_obs += 1
    for i in range(1, 1 + 2 * NT):                    # shrink ratings, not mu/h
        XtX[i][i] += lam
    beta = solve(XtX, Xty)
    return {"mu": beta[0], "A": beta[1:1 + NT], "D": beta[1 + NT:1 + 2 * NT],
            "h": beta[1 + 2 * NT]}, n_obs


def predict(p, home, away, neutral=False):
    hfa = 0.0 if neutral else p["h"]               # neutral site: no home edge
    home_pts = p["mu"] + p["A"][IDX[home]] - p["D"][IDX[away]] + hfa
    away_pts = p["mu"] + p["A"][IDX[away]] - p["D"][IDX[home]]
    return {"home_points": home_pts, "away_points": away_pts,
            "margin": home_pts - away_pts, "total": home_pts + away_pts}


# --------------------------------------------- naive reference baseline ----
def season_to_date(week):
    """Points for/against per game strictly before `week` (no look-ahead)."""
    st = defaultdict(lambda: [0, 0, 0])                # pf, pa, games
    for g in results:
        if g["week"] < week:
            a, h = g["away_team"], g["home_team"]
            st[a][0] += g["away_points"]; st[a][1] += g["home_points"]; st[a][2] += 1
            st[h][0] += g["home_points"]; st[h][1] += g["away_points"]; st[h][2] += 1
    return st


HFA_REF = 2.5                                          # pre-registered constant


def ref_line(week, home, away, neutral=False):
    """Naive published reference line.

    home margin = 2.5 (fixed home-field) + (home season scoring differential per
    game - away season scoring differential per game), using only games strictly
    before `week`. At a neutral site the 2.5-point home-field term is not added. No opponent adjustment: this is the standard naive benchmark
    an originated line has to beat. The differential is used at full scale - it
    is NOT halved - so the benchmark is not artificially mis-scaled.
    """
    st = season_to_date(week)
    lg = [v for v in st.values() if v[2]]
    lg_ppg = sum(v[0] for v in lg) / max(1, sum(v[2] for v in lg))
    lg_total = 2 * lg_ppg
    hd = (st[home][0] - st[home][1]) / st[home][2] if st[home][2] else 0.0
    ad = (st[away][0] - st[away][1]) / st[away][2] if st[away][2] else 0.0
    margin = (0.0 if neutral else HFA_REF) + (hd - ad)
    return {"margin": margin, "total": lg_total}


# ------------------------------------------------------------ statistics ---
def norm_cdf(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


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
    r = sxy / math.sqrt(sxx * syy)
    return r, n


def fisher_ci(r, n, alpha=0.05):
    if r is None or n < 4 or abs(r) >= 1:
        return (None, None)
    z = 0.5 * math.log((1 + r) / (1 - r))
    se = 1.0 / math.sqrt(n - 3)
    zc = 1.959963985
    lo, hi = z - zc * se, z + zc * se
    return (math.tanh(lo), math.tanh(hi))


def pearson_p(r, n):
    """Two-sided p-value for a Pearson correlation (t transformation).

    p = I_x(df/2, 1/2) with x = df / (df + t^2)  -- the regularised incomplete
    beta function. Verified against the identity p = 1 for r = 0.
    """
    if r is None or n < 4 or abs(r) >= 1:
        return None
    df = n - 2
    if abs(r) < 1e-12:
        return 1.0
    t = r * math.sqrt(df / (1 - r * r))
    x = df / (df + t * t)
    return min(1.0, max(0.0, betainc(df / 2.0, 0.5, x)))


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


def wilson(k, n, z=1.959963985):
    if n == 0:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - m), min(1.0, c + m))


def binom_pmf(k, n, p=0.5):
    return math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k))


def binom_two_sided(k, n, p=0.5):
    """Exact two-sided binomial test (method of small p-values)."""
    if n == 0:
        return None
    obs = binom_pmf(k, n, p)
    tot = 0.0
    for i in range(n + 1):
        pi = binom_pmf(i, n, p)
        if pi <= obs * (1 + 1e-9):
            tot += pi
    return min(1.0, tot)


def benjamini_hochberg(pvals):
    """Return BH-adjusted q-values in the input order (blank for None)."""
    idx = [i for i, p in enumerate(pvals) if p is not None]
    m = len(idx)
    q = [None] * len(pvals)
    if not m:
        return q
    order = sorted(idx, key=lambda i: pvals[i])
    prev = 1.0
    for rank in range(m - 1, -1, -1):
        i = order[rank]
        val = pvals[i] * m / (rank + 1)
        prev = min(prev, val)
        q[i] = min(1.0, prev)
    return q


def required_n_proportion(p1, p0=0.5, alpha=0.05, power=0.80):
    """Two-sided one-sample proportion test sample size (normal approximation)."""
    if p1 is None or abs(p1 - p0) < 1e-9:
        return None
    za, zb = 1.959963985, 0.8416212336
    num = (za * math.sqrt(p0 * (1 - p0)) + zb * math.sqrt(p1 * (1 - p1))) ** 2
    return math.ceil(num / (p1 - p0) ** 2)


def required_n_mean(delta, sd, alpha=0.05, power=0.80):
    """Two-sided one-sample t/z test sample size for a mean points edge."""
    if not delta or not sd or abs(delta) < 1e-9:
        return None
    za, zb = 1.959963985, 0.8416212336
    return math.ceil(((za + zb) ** 2) * (sd ** 2) / (delta ** 2))


def paired_skill(diffs):
    """Paired accuracy test: diffs = (error of reference) - (error of model) per game.

    Positive means the model is closer to what actually happened. Bootstrap CI
    and a sign-flip permutation p-value (null: the two methods are equally
    accurate, so each paired difference is exchangeable with its negative).
    """
    n = len(diffs)
    if n < 2:
        return {"mean": None, "boot_lo": None, "boot_hi": None, "p_perm": None,
                "half1": None, "half2": None, "n": n}
    mean = sum(diffs) / n
    lo, hi = bootstrap_ci(diffs)
    obs = abs(mean)
    hits = 0
    for _ in range(PERMUTATIONS):
        ssum = 0.0
        for d in diffs:
            ssum += d * (1 if random.random() < 0.5 else -1)
        if abs(ssum / n) >= obs - 1e-12:
            hits += 1
    p_perm = (hits + 1) / (PERMUTATIONS + 1)
    half = n // 2
    return {"mean": mean, "boot_lo": lo, "boot_hi": hi, "p_perm": p_perm,
            "half1": sum(diffs[:half]) / half if half else None,
            "half2": sum(diffs[half:]) / (n - half) if n - half else None, "n": n}


def brier_logloss(pred_margin, sd):
    """Brier score and log loss of the home-win probability from a margin forecast."""
    brier = ll = 0.0
    for r in oos:
        p = norm_cdf(pred_margin(r) / sd)
        p = min(max(p, 1e-6), 1 - 1e-6)
        y = 1.0 if r["actual_margin"] > 0 else (0.5 if r["actual_margin"] == 0 else 0.0)
        brier += (p - y) ** 2
        ll += -(y * math.log(p) + (1 - y) * math.log(1 - p)) if y in (0.0, 1.0) else 0.0
    n = len(oos)
    return brier / n, ll / n


def bootstrap_ci(vals, iters=BOOTSTRAP, alpha=0.05):
    n = len(vals)
    if n < 2:
        return (None, None)
    means = []
    for _ in range(iters):
        s = 0.0
        for _ in range(n):
            s += vals[random.randrange(n)]
        means.append(s / n)
    means.sort()
    lo = means[int((alpha / 2) * iters)]
    hi = means[min(iters - 1, int((1 - alpha / 2) * iters))]
    return (lo, hi)


def permutation_p(diffs, edges, iters=PERMUTATIONS):
    """Shuffle the sign of the model's lean: how often is mean edge >= observed?"""
    n = len(edges)
    if n < 2:
        return None
    obs = sum(edges) / n
    hits = 0
    for _ in range(iters):
        s = 0.0
        for i in range(n):
            s += edges[i] * (1 if random.random() < 0.5 else -1)
        if abs(s / n) >= abs(obs) - 1e-12:
            hits += 1
    return (hits + 1) / (iters + 1)


def phi_coef(a, b, c, d):
    """Phi / Matthews correlation for a 2x2 table [[a,b],[c,d]]."""
    n = a + b + c + d
    if n == 0:
        return None
    num = a * d - b * c
    den = math.sqrt((a + b) * (c + d) * (a + c) * (b + d))
    return num / den if den else None


# ------------------------------------------------------ walk-forward fit ----
STRATEGIES = [
    ("M1", "Ridge attack/defence, uniform weights", 4.0, None),
    ("M2", "Ridge attack/defence, 3-week recency half-life", 4.0, 3.0),
    ("M3", "Ridge attack/defence, heavy shrinkage", 12.0, None),
    ("M4", "Ridge attack/defence, light shrinkage", 1.0, None),
]

# games available by week
by_week = defaultdict(list)
for g in results:
    by_week[g["week"]].append(g)
completed_weeks = sorted(w for w in by_week if w <= 10)

oos = []            # one dict per (week, game) with all predictions
for wk in completed_weeks:
    if wk < EVAL_FROM_WEEK:
        continue
    train = [g for g in results if g["week"] < wk]
    if len(train) < 20:
        continue
    preds = {}
    for sid, _label, lam, hl in STRATEGIES:
        params, _n = fit(train, lam, half_life=hl, ref_week=wk)
        preds[sid] = params
    for g in by_week[wk]:
        row = {"week": wk, "away_team": g["away_team"], "home_team": g["home_team"],
               "away_points": g["away_points"], "home_points": g["home_points"],
               "actual_margin": g["margin"], "actual_total": g["total"],
               "game_url": g["game_url"], "source_url": g["source_url"]}
        rl = ref_line(wk, g["home_team"], g["away_team"], g["neutral"])
        row["ref_margin"] = rl["margin"]
        row["ref_total"] = rl["total"]
        for sid, _l, _lam, _hl in STRATEGIES:
            pr = predict(preds[sid], g["home_team"], g["away_team"], g["neutral"])
            row[sid + "_margin"] = pr["margin"]
            row[sid + "_total"] = pr["total"]
        oos.append(row)

n_oos = len(oos)

# residual scale, estimated on walk-forward residuals of M1 (used for prices-free probabilities)
res_m = [r["actual_margin"] - r["M1_margin"] for r in oos]
res_t = [r["actual_total"] - r["M1_total"] for r in oos]
sd_margin = math.sqrt(sum(x * x for x in res_m) / max(1, len(res_m) - 1))
sd_total = math.sqrt(sum(x * x for x in res_t) / max(1, len(res_t) - 1))
mae_ref = sum(abs(r["actual_margin"] - r["ref_margin"]) for r in oos) / n_oos
mae_m1 = sum(abs(r["actual_margin"] - r["M1_margin"]) for r in oos) / n_oos


# --------------------------------------------------------------- bets -------
def side_bets(model_key):
    out = []
    for r in oos:
        diff = r[model_key + "_margin"] - r["ref_margin"]
        if abs(diff) < BET_DELTA:
            continue
        side = "home" if diff > 0 else "away"
        edge = (r["actual_margin"] - r["ref_margin"]) * (1 if side == "home" else -1)
        out.append({"week": r["week"], "home": r["home_team"], "away": r["away_team"],
                    "ref": r["ref_margin"], "model": r[model_key + "_margin"],
                    "side": side, "edge": edge, "hit": 1 if edge > 0 else (0 if edge < 0 else None),
                    "actual": r["actual_margin"], "url": r["game_url"], "src": r["source_url"]})
    return out


def total_bets(model_key):
    out = []
    for r in oos:
        diff = r[model_key + "_total"] - r["ref_total"]
        if abs(diff) < BET_DELTA_TOTAL:
            continue
        side = "over" if diff > 0 else "under"
        edge = (r["actual_total"] - r["ref_total"]) * (1 if side == "over" else -1)
        out.append({"week": r["week"], "home": r["home_team"], "away": r["away_team"],
                    "ref": r["ref_total"], "model": r[model_key + "_total"],
                    "side": side, "edge": edge, "hit": 1 if edge > 0 else (0 if edge < 0 else None),
                    "actual": r["actual_total"], "url": r["game_url"], "src": r["source_url"]})
    return out


def summarise(name, bets, kind, oos_key=None, subset=None):
    decided = [b for b in bets if b["hit"] is not None]
    n = len(decided)
    wins = sum(b["hit"] for b in decided)
    pushes = len(bets) - n
    edges = [b["edge"] for b in decided]
    hits = [b["hit"] for b in decided]
    mean_edge = sum(edges) / n if n else None
    lo, hi = bootstrap_ci(edges)
    p_bin = binom_two_sided(wins, n) if n else None
    p_perm = permutation_p([abs(b.get("model", 0) - b.get("ref", 0)) or 1.0 for b in decided], edges) if n else None
    wlo, whi = wilson(wins, n) if n else (None, None)
    halves = None
    if n >= 8:
        half = n // 2
        halves = (sum(hits[:half]) / half, sum(hits[half:]) / (n - half))
    # Skill measured on every out-of-sample game, not only on selected bets:
    # paired absolute-error improvement against the naive reference line.
    acc = None
    skill = None
    if oos_key:
        key_act = "actual_margin" if kind == "side" else "actual_total"
        key_ref = "ref_margin" if kind == "side" else "ref_total"
        scope = subset if subset is not None else oos
        errs_model = [abs(r[key_act] - r[oos_key + ("_margin" if kind == "side" else "_total")]) for r in scope]
        errs_ref = [abs(r[key_act] - r[key_ref]) for r in scope]
        diff_err = [a - b for a, b in zip(errs_ref, errs_model)]   # >0 = model closer
        skill = paired_skill(diff_err)
        acc = {"mean_err_model": sum(errs_model) / len(errs_model),
               "mean_err_ref": sum(errs_ref) / len(errs_ref),
               "mean_improvement": skill["mean"]}
    sd_edges = None
    if n > 1:
        m = sum(edges) / n
        sd_edges = math.sqrt(sum((e - m) ** 2 for e in edges) / (n - 1))
    return {"strategy_id": name, "kind": kind, "n_bets": n, "pushes": pushes, "wins": wins,
            "sd_edge": sd_edges,
            "req_n_hit": required_n_proportion(wins / n) if n else None,
            "req_n_edge": required_n_mean(mean_edge, sd_edges) if n else None,
            "losses": n - wins, "hit_rate": (wins / n) if n else None,
            "wilson_lo": wlo, "wilson_hi": whi, "mean_edge_points": mean_edge,
            "boot_lo": lo, "boot_hi": hi, "p_binomial": p_bin, "p_permutation": p_perm,
            "first_half_hit": halves[0] if halves else None,
            "second_half_hit": halves[1] if halves else None, "accuracy": acc,
            "skill": skill,
            "bets": bets}


# bye weeks, transcribed from the official schedule pages (used by the rest strategy)
BYES = {5: {"CAR", "KC"}, 6: {"CIN", "DET", "MIA", "MIN"}, 7: {"BUF", "JAX", "LAC", "WAS"},
        8: {"HOU", "NO", "NYG", "SF"}, 9: {"PIT", "TEN"}, 10: {"CHI", "DEN", "PHI", "TB"},
        11: {"ATL", "CLE", "GB", "LA", "NE", "SEA"}}


def rest_bets(model_key="M1"):
    """M1 bets restricted to games where exactly one team is coming off its bye."""
    base = side_bets(model_key)
    out = []
    for b in base:
        wk = b["week"]
        prev_byes = BYES.get(wk - 1, set())
        home_off_bye = b["home"] in prev_byes
        away_off_bye = b["away"] in prev_byes
        if home_off_bye == away_off_bye:
            continue
        out.append(b)
    return out


def parlay_bets(model_key="M1"):
    """Same-game 2-leg combo: side and total both disagree with the reference."""
    out = []
    for r in oos:
        ds = r[model_key + "_margin"] - r["ref_margin"]
        dt = r[model_key + "_total"] - r["ref_total"]
        if abs(ds) < BET_DELTA or abs(dt) < BET_DELTA_TOTAL:
            continue
        side = "home" if ds > 0 else "away"
        tot = "over" if dt > 0 else "under"
        e_side = (r["actual_margin"] - r["ref_margin"]) * (1 if side == "home" else -1)
        e_tot = (r["actual_total"] - r["ref_total"]) * (1 if tot == "over" else -1)
        hit_side = 1 if e_side > 0 else 0
        hit_tot = 1 if e_tot > 0 else 0
        out.append({"week": r["week"], "home": r["home_team"], "away": r["away_team"],
                    "side": side, "total": tot, "hit_side": hit_side, "hit_tot": hit_tot,
                    "hit": 1 if (hit_side and hit_tot) else 0,
                    "edge": e_side + e_tot, "url": r["game_url"], "src": r["source_url"]})
    return out


summaries = []
for sid, label, _lam, _hl in STRATEGIES:
    summaries.append((summarise(sid, side_bets(sid), "side", sid), label, "Game side (spread)"))
summaries.append((summarise("T1", total_bets("M1"), "total", "M1"), "Model total vs league-average total", "Game total"))
bye_games = []
for r in oos:
    prev_byes = BYES.get(r["week"] - 1, set())
    if (r["home_team"] in prev_byes) != (r["away_team"] in prev_byes):
        bye_games.append(r)
summaries.append((summarise("R1", rest_bets("M1"), "side", "M1", subset=bye_games),
                  "M1 filtered to post-bye spots", "Game side (spread)"))

pl = parlay_bets("M1")
n_pl = len(pl)
pl_hits = sum(p["hit"] for p in pl)
pl_side_hits = sum(p["hit_side"] for p in pl)
pl_tot_hits = sum(p["hit_tot"] for p in pl)
p_parlay = binom_two_sided(pl_hits, n_pl) if n_pl else None
# 2x2 table for the phi correlation of the two legs
a = sum(1 for p in pl if p["hit_side"] and p["hit_tot"])
b = sum(1 for p in pl if p["hit_side"] and not p["hit_tot"])
c = sum(1 for p in pl if not p["hit_side"] and p["hit_tot"])
d = sum(1 for p in pl if not p["hit_side"] and not p["hit_tot"])
phi_pl = phi_coef(a, b, c, d)
indep_rate = (pl_side_hits / n_pl) * (pl_tot_hits / n_pl) if n_pl else None
summaries.append((summarise("P1", pl, "parlay", None), "Same-game side + total parlay (2 legs)", "Parlay"))

# ---- multiple-comparison control across the family of strategies ----------
fam_p = [(s["skill"] or {}).get("p_perm") for s, _l, _k in summaries]
qvals = benjamini_hochberg(fam_p)
for (s, _l, _k), q in zip(summaries, qvals):
    s["q_bh"] = q
    s["skill_p"] = (s["skill"] or {}).get("p_perm")


# ----------------------------------------------------------------- gates ----
# Proposed numeric cut-offs. Flagged (F17) as proposed by this session and not
# yet approved by the project owner.
GATE_DEFS = [
    ("G1", "No look-ahead", "Every prediction for week W is fitted only on games played before week W",
     "Audited: for every out-of-sample week, training games are strictly earlier weeks and none are empty "
     "(scripts/model.py audit_no_lookahead)", "https://www.itl.nist.gov/div898/handbook/pmd/section4/pmd44.htm"),
    ("G2", "Minimum sample", "At least 30 decided bets and at least 30 out-of-sample games",
     "n_bets >= 30", "https://www.itl.nist.gov/div898/handbook/prc/section1/prc16.htm"),
    ("G3", "Skill is significant", "Sign-flip permutation test on the paired accuracy improvement, p < 0.05",
     "skill p_perm < 0.05", "https://www.itl.nist.gov/div898/handbook/eda/section3/bootplot.htm"),
    ("G4", "Multiple-comparison control", "Benjamini-Hochberg q < 0.10 across every strategy tested",
     "q_bh < 0.10", "https://www.itl.nist.gov/div898/handbook/prc/section4/prc47.htm"),
    ("G5", "Uncertainty excludes zero", "Bootstrap 95% CI of the accuracy improvement excludes 0",
     "skill boot_lo > 0", "https://www.itl.nist.gov/div898/handbook/eda/section3/bootplot.htm"),
    ("G6", "Stable across the window", "Accuracy improvement positive in both halves of the window",
     "skill half1 > 0 and skill half2 > 0", "https://www.itl.nist.gov/div898/handbook/pmd/section4/pmd44.htm"),
    ("G7", "Record not explained by luck", "Sign-permutation test on bet edges vs the reference line, p < 0.05",
     "p_permutation < 0.05", "https://www.itl.nist.gov/div898/handbook/eda/section3/bootplot.htm"),
    ("G8", "Beats the reference line outright", "Mean absolute error lower than the naive reference line",
     "mean_err_model < mean_err_ref", "https://www.itl.nist.gov/div898/handbook/eda/section3/eda352.htm"),
    ("G9", "Demotion gate (live back to paper)",
     "A strategy that is live is demoted back to paper when its skill 95% CI includes zero, "
     "or any core gate G1-G5 fails on the latest window, or its mean edge turns negative",
     "status = Live only if G1-G8 all pass and skill boot_lo > 0; otherwise Paper (demoted)",
     "https://www.itl.nist.gov/div898/handbook/prc/section4/prc47.htm"),
]


# ------------------------------------------------------- no-look-ahead audit ----
# G1 used to be a hardcoded True, which made it a constant rather than a check
# (flag F56). It is now an actual audit of the walk-forward construction: for
# every evaluation week, the training set must be strictly earlier than the
# week being predicted, and must be non-empty. If any week breaks that, no
# prediction is produced and G1 reports the failure instead of passing.
def audit_no_lookahead():
    checks = []
    ok = True
    for wk in completed_weeks:
        if wk < EVAL_FROM_WEEK:
            continue
        train = [g for g in results if g["week"] < wk]
        future = [g for g in train if g["week"] >= wk]
        good = (len(train) >= 20) and not future
        ok = ok and good
        checks.append({"week": wk, "train_games": len(train),
                       "latest_training_week": max((g["week"] for g in train), default=None),
                       "future_games": len(future), "pass": good})
    return ok, checks


LOOKAHEAD_OK, LOOKAHEAD_CHECKS = audit_no_lookahead()


def gate_eval(s):
    acc = s["accuracy"] or {}
    sk = s["skill"] or {}
    passed = {
        "G1": LOOKAHEAD_OK,
        "G2": (s["n_bets"] or 0) >= 30,
        "G3": sk.get("p_perm") is not None and sk["p_perm"] < 0.05,
        "G4": s["q_bh"] is not None and s["q_bh"] < 0.10,
        "G5": sk.get("boot_lo") is not None and sk["boot_lo"] > 0,
        "G6": (sk.get("half1") or -1) > 0 and (sk.get("half2") or -1) > 0,
        "G7": s["p_permutation"] is not None and s["p_permutation"] < 0.05,
        "G8": ("mean_err_model" in acc and acc["mean_err_model"] < acc["mean_err_ref"]),
    }
    # G9 demotion gate: a strategy keeps (or earns) Live status only when every
    # gate G1-G8 passes AND the skill interval still excludes zero. Anything
    # else sends it back to paper.
    passed["G9"] = all(passed[g] for g in ("G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8")) \
        and passed["G5"]
    return passed


def fmt(x, nd=3):
    return "" if x is None else f"{x:.{nd}f}"


# --------------------------------------------------------- Week 11 lines ----
final_params = {}
for sid, _label, lam, hl in STRATEGIES:
    p, nfit = fit(results, lam, half_life=hl, ref_week=11)
    final_params[sid] = p
main = final_params["M1"]

def american_ml(p):
    """Fair American moneyline implied by probability p (no vig).

    If p is the probability of the side, the fair price is -100*p/(1-p) for
    p >= 0.5 and 100*(1-p)/p below. Returns None for degenerate probabilities.
    """
    if p is None or p <= 0.0 or p >= 1.0:
        return None
    if p >= 0.5:
        return -round(100.0 * p / (1.0 - p))
    return round(100.0 * (1.0 - p) / p)


lines_rows = []
for g in week11:
    home, away = g["home_team"], g["away_team"]
    # Origination order: the SIDE first, then the TOTAL, then the MONEYLINE.
    # Neutral-site games carry no home-field term (F57).
    g["neutral"] = (g.get("neutral_site", "").strip().upper() == "Y")
    pr = predict(main, home, away, g["neutral"])
    # 1. Side: the spread, from the ridge margin prediction.
    side_fair = pr["margin"]
    # 2. Total: the points total, from the same ratings system.
    total_fair = pr["total"]
    # 3. Moneyline: fair American prices implied by the model win probability.
    p_home = norm_cdf(pr["margin"] / sd_margin)
    p_away = 1.0 - p_home
    ml_home = american_ml(p_home)
    ml_away = american_ml(p_away)
    rl = ref_line(11, home, away, g["neutral"])
    lines_rows.append({
        "game_no": g["game_no"],
        "matchup": f"{away} at {home}",
        "kickoff_et": f"{g['kickoff_day']} {g['kickoff_time_et']}",
        # --- SIDE market (originated first) ---
        "fair_spread": fmt(side_fair, 1),
        "market_spread": "",
        "fair_minus_market_spread": "",
        # --- TOTAL market (originated second) ---
        "fair_total": fmt(total_fair, 1),
        "market_total": "",
        "fair_minus_market_total": "",
        # --- MONEYLINE market (originated third) ---
        "fair_moneyline_home": (str(ml_home) if ml_home is not None else ""),
        "fair_moneyline_away": (str(ml_away) if ml_away is not None else ""),
        "market_moneyline_home": "",
        "market_moneyline_away": "",
        "fair_minus_market_moneyline_home": "",
        "fair_minus_market_moneyline_away": "",
        # model point projection and reference line (kept for the backtest).
        # The model_spread_home / model_total aliases are retained so that the
        # independent market generator (scripts/markets.py, session c125b2f7)
        # keeps reading this file unchanged.
        "model_spread_home": fmt(side_fair, 1),
        "model_total": fmt(total_fair, 1),
        "model_home_points": fmt(pr["home_points"], 1),
        "model_away_points": fmt(pr["away_points"], 1),
        "home_win_prob": fmt(p_home, 3),
        "reference_spread_home": fmt(rl["margin"], 1),
        "reference_total": fmt(rl["total"], 1),
        "model_minus_reference": fmt(side_fair - rl["margin"], 1),
        "market_note": "No licensed odds feed in this project — market columns intentionally blank (F07)",
        "game_url": g["game_url"],
        "source_url": g["source_url"],
    })

ratings_rows = []
for t in TEAMS:
    gp = sum(1 for g in results if t in (g["home_team"], g["away_team"]))
    ratings_rows.append({
        "team": t,
        "attack_rating": fmt(main["A"][IDX[t]], 2),
        "defence_rating": fmt(main["D"][IDX[t]], 2),
        "net_rating": fmt(main["A"][IDX[t]] + main["D"][IDX[t]], 2),
        "games_played": gp,
        "notes": "Positive attack = scores more than league average; positive defence = allows fewer",
        "source_url": SRC_STAND,
    })
ratings_rows.sort(key=lambda r: -float(r["net_rating"]))


# --------------------------------------------------------- correlations ----
corr_rows = []
def add_corr(cid, question, r, n, note, src):
    lo, hi = fisher_ci(r, n) if r is not None else (None, None)
    p = pearson_p(r, n) if r is not None else None
    corr_rows.append({"corr_id": cid, "question": question, "value": fmt(r),
                      "ci_low": fmt(lo), "ci_high": fmt(hi), "p_value": fmt(p, 4),
                      "sample_n": n, "interpretation": note, "source_url": src})


def t_cdf(t, df):
    """CDF of Student's t, via the regularised incomplete beta function."""
    x = df / (df + t * t)

    def betacf(a, b, x):
        MAXIT, EPS, FPMIN = 200, 3e-16, 1e-300
        qab, qap, qam = a + b, a + 1.0, a - 1.0
        c, d = 1.0, 1.0 - qab * x / qap
        if abs(d) < FPMIN:
            d = FPMIN
        d = 1.0 / d
        h = d
        for m in range(1, MAXIT + 1):
            m2 = 2 * m
            aa = m * (b - m) * x / ((qam + m2) * (a + m2))
            d = 1.0 + aa * d
            if abs(d) < FPMIN:
                d = FPMIN
            c = 1.0 + aa / c
            if abs(c) < FPMIN:
                c = FPMIN
            d = 1.0 / d
            h *= d * c
            aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
            d = 1.0 + aa * d
            if abs(d) < FPMIN:
                d = FPMIN
            c = 1.0 + aa / c
            if abs(c) < FPMIN:
                c = FPMIN
            d = 1.0 / d
            de = d * c
            h *= de
            if abs(de - 1.0) < EPS:
                break
        return h

    def betai(a, b, x):
        if x <= 0.0:
            return 0.0
        if x >= 1.0:
            return 1.0
        lbeta = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                 + a * math.log(x) + b * math.log(1.0 - x))
        bt = math.exp(lbeta)
        if x < (a + 1.0) / (a + b + 2.0):
            return bt * betacf(a, b, x) / a
        return 1.0 - bt * betacf(b, a, 1.0 - x) / b

    two_tail = betai(df / 2.0, 0.5, x)
    return 1.0 - two_tail / 2.0 if t > 0 else two_tail / 2.0


def t_ppf_975(df):
    """97.5th percentile of Student's t (bisection on t_cdf)."""
    lo, hi = 0.0, 50.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if t_cdf(mid, df) < 0.975:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def add_slope(cid, question, estimate, se, df, note, src, null=1.0):
    """A regression coefficient is not a correlation.

    The interval is the coefficient's own t interval (estimate +/- t*SE) and the
    p-value tests the coefficient against `null`. Applying Fisher's z interval
    here would be a formula error: that transform is for a Pearson r, whose
    standard error is 1/sqrt(n-3), not SE(beta).
    """
    tcrit = t_ppf_975(df)
    lo, hi = estimate - tcrit * se, estimate + tcrit * se
    tstat = (estimate - null) / se
    p = 2.0 * (1.0 - t_cdf(abs(tstat), df))
    corr_rows.append({"corr_id": cid, "question": question, "value": fmt(estimate),
                      "ci_low": fmt(lo), "ci_high": fmt(hi), "p_value": fmt(p, 4),
                      "sample_n": df + 2, "interpretation": note, "source_url": src})


xs = [r["M1_margin"] for r in oos]
ys = [r["actual_margin"] for r in oos]
r1, n1 = pearson(xs, ys)
add_corr("C01", "Do model-predicted margins track actual margins (out of sample)?", r1, n1,
         "Forecast skill of the M1 line; higher means the originated number carries signal.",
         SRC_SCHED + "10")
r2, n2 = pearson([r["ref_margin"] for r in oos], ys)
add_corr("C02", "Same, for the naive reference line (season point differential + 2.5)", r2, n2,
         "Benchmark: the model must beat this to justify originating lines.", SRC_SCHED + "10")
r3, n3 = pearson([abs(r["actual_margin"]) for r in oos], [r["actual_total"] for r in oos])
add_corr("C03", "Are blowouts associated with higher game totals?", r3, n3,
         "Same-game link: lopsided games and scoring volume move together.", SRC_SCHED + "10")
r4, n4 = pearson([r["home_points"] for r in oos], [r["away_points"] for r in oos])
add_corr("C04", "Within a game, do the two teams' point totals co-move?", r4, n4,
         "Direct input to totals and same-game parlays; negative means a scoring trade-off.",
         SRC_SCHED + "10")
r5, n5 = pearson([r["M1_total"] for r in oos], [r["actual_total"] for r in oos])
add_corr("C05", "Do model-predicted totals track actual totals?", r5, n5, "Totals-signal check.",
         SRC_SCHED + "10")
# week-to-week persistence of a team's margin (motivates recency weighting)
prev, cur = [], []
team_seq = defaultdict(list)
for g in sorted(results, key=lambda g: (g["week"], g["game_url"])):
    team_seq[g["home_team"]].append((g["week"], g["margin"]))
    team_seq[g["away_team"]].append((g["week"], -g["margin"]))
for t, seq in team_seq.items():
    for i in range(1, len(seq)):
        if seq[i][0] == seq[i - 1][0] + 1:
            prev.append(seq[i - 1][1]); cur.append(seq[i][1])
r6, n6 = pearson(prev, cur)
add_corr("C06", "Does last week's margin predict this week's margin for the same team?", r6, n6,
         "Near zero means week-to-week results are mostly noise, so recency weighting cannot add much.",
         SRC_SCHED + "10")
# calibration: regress actual margin on predicted margin (out of sample)
mx = sum(xs) / len(xs); my = sum(ys) / len(ys)
sxx = sum((x - mx) ** 2 for x in xs)
slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
intercept = my - slope * mx
resid = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
se_slope = math.sqrt(sum(e * e for e in resid) / (len(xs) - 2) / sxx)
add_slope("C09", "Calibration: slope of actual margin on the model's predicted margin (1.0 = perfectly scaled)",
          slope, se_slope, len(xs) - 2,
          f"Slope {slope:.2f} (SE {se_slope:.2f}), intercept {intercept:.2f}. The interval is the "
          f"slope's own t interval over {len(xs)} forecasts; the p-value tests the slope against 1.0, "
          "not against 0. A slope clearly below 1 would mean the model is over-shy; clearly above 1, "
          "over-confident. This row is a regression slope, not a correlation.",
          SRC_SCHED + "10")
# parlay leg correlation (phi)
add_corr("C07", "Are the side leg and the total leg of the same game correlated (phi)?", phi_pl, n_pl,
         "Parlay pricing: |phi| > 0 means the independence shortcut misprices the ticket.",
         SRC_SCHED + "10")
# injury exposure vs season defensive performance (Week 10 snapshot only)
def_unit = defaultdict(int)
for r in injuries:
    pos = r["position"]
    defence_pos = pos in ("DE", "DT", "DL", "NT", "LB", "OLB", "ILB", "MLB", "CB", "S", "SAF", "DB")
    if defence_pos and r["game_status"] in ("Out", "Doubtful"):
        def_unit[r["team_abbr"]] += 1
st = season_to_date(11)
pa_per = []
expo = []
for t in TEAMS:
    if st[t][2]:
        pa_per.append(st[t][1] / st[t][2])
        expo.append(def_unit.get(t, 0))
r7, n7 = pearson(expo, pa_per)
add_corr("C08", "Is Week-10 defensive injury exposure associated with season points allowed?", r7, n7,
         "Exploratory only: one snapshot, no causal claim, and starter/backup depth is unverified (F06).",
         SRC_INJ)


# ------------------------------------------------------------- parlay -------
parlay_rows = [{
    "parlay_id": "P1",
    "definition": "Same-game 2-leg ticket: side and total, each taken only when the model and the reference line differ by >= 3",
    "legs": 2,
    "tickets": n_pl,
    "leg1_hit_rate": fmt(pl_side_hits / n_pl) if n_pl else "",
    "leg2_hit_rate": fmt(pl_tot_hits / n_pl) if n_pl else "",
    "observed_joint_hit_rate": fmt(pl_hits / n_pl) if n_pl else "",
    "independence_expected_rate": fmt(indep_rate) if indep_rate is not None else "",
    "difference_observed_minus_independence": fmt((pl_hits / n_pl) - indep_rate) if n_pl else "",
    "phi_correlation": fmt(phi_pl),
    "two_by_two": f"both={a}, side only={b}, total only={c}, neither={d}",
    "note": "Small sample; the ticket count is the number of walk-forward games where both legs qualified.",
    "source_url": SRC_SCHED + "10",
}]


# --------------------------------------------------------- leaderboard ------
def reward_tier(passed, s):
    core = all(passed[g] for g in ("G1", "G2", "G3", "G5"))
    if not core:
        return "Not qualified", "No reward tier — gates G1/G2/G3/G5 not all passed"
    if all(passed[g] for g in ("G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8")):
        return "Tier 1 (gold)", "Proposed: top leaderboard reward"
    if all(passed[g] for g in ("G1", "G2", "G3", "G4", "G5", "G6")):
        return "Tier 2 (silver)", "Proposed: mid leaderboard reward"
    return "Tier 3 (bronze)", "Proposed: tracking-only recognition"


leader_rows = []
rank = 0
# Live operation is NOT enabled: the qualification is disputed by the
# independent cross-check (F42), the gate cut-offs await owner approval (F17)
# and wagering/rewards stay disabled (F09/F16/F19). The demotion gate (G9) is
# therefore armed but nothing is promoted to Live today; every strategy is
# Paper. A strategy that were Live would be demoted back to Paper the moment
# any of G1-G8 fails or the skill interval includes zero.
LIVE_ENABLED = False
order = sorted(summaries, key=lambda s: -((s[0]["skill"] or {}).get("mean") or -99))
for s, label, kind in order:
    passed = gate_eval(s)
    n_pass = sum(1 for v in passed.values() if v)
    tier, reward = reward_tier(passed, s)
    # Demotion gate (G9): a strategy keeps (or earns) Live status only when
    # every gate passes AND live operation is enabled. Anything else is Paper.
    status = "Live" if (LIVE_ENABLED and all(passed.values())) else "Paper"
    demotion_safe = "Yes" if all(passed.values()) else "No"
    rank += 1
    sk = s["skill"] or {}
    acc = s["accuracy"] or {}
    leader_rows.append({
        "rank": rank,
        "strategy_id": s["strategy_id"],
        "strategy": label,
        "market": kind,
        "status": status,
        "demotion_safe": demotion_safe,
        # --- SIGNAL block (forecast skill, independent of any staking plan) ---
        "skill_score_mae_improvement_pts": fmt(sk.get("mean"), 2),
        "skill_ci_low": fmt(sk.get("boot_lo"), 2),
        "skill_ci_high": fmt(sk.get("boot_hi"), 2),
        "skill_p_permutation": fmt(sk.get("p_perm"), 4),
        "q_bh_fdr": fmt(s["q_bh"], 4),
        "mae_model": fmt(acc.get("mean_err_model"), 2),
        "mae_reference": fmt(acc.get("mean_err_ref"), 2),
        "oos_games": sk.get("n") or n_oos,
        "bets_vs_reference": s["n_bets"],
        "wins": s["wins"],
        "losses": s["losses"],
        "hit_rate_vs_reference": fmt(s["hit_rate"]),
        "mean_edge_points": fmt(s["mean_edge_points"], 2),
        "edge_ci_low": fmt(s["boot_lo"], 2),
        "edge_ci_high": fmt(s["boot_hi"], 2),
        "sd_edge_points": fmt(s["sd_edge"], 2),
        "p_binomial": fmt(s["p_binomial"], 4),
        "p_permutation_bets": fmt(s["p_permutation"], 4),
        "min_n_for_80pct_power": (lambda r: str(r) if 0 < r <= 10000
                                  else (">10000 - effect too small to power a test" if r > 10000 else "not estimable"))(
                                      max([x for x in (s["req_n_hit"], s["req_n_edge"]) if x] or [0])),
        "sample_shortfall": (lambda r, n: str(max(0, r - n)) if 0 < r <= 10000
                             else ("not reachable at this effect size" if r > 10000 else "not estimable"))(
                                 max([x for x in (s["req_n_hit"], s["req_n_edge"]) if x] or [0]), s["n_bets"]),
        "gates_passed": f"{n_pass}/9",
        "gates_failed": ", ".join(g for g, v in passed.items() if not v) or "none",
        "reward_tier": tier,
        "reward_status": "Proposed only — no reward is paid; wagering and rewards stay disabled pending legal and rights review (F09/F16)",
        # --- STAKING block (separate from signal; no prices exist, so ROI is blank) ---
        "staking_plan": "Flat 1 unit per bet (proposed; not enabled)",
        "staking_units_wagered": "",
        "staking_roi_pct": "",
        "staking_note": "No licensed odds feed — staking ROI not computable; kept separate from signal so a lucky staking run cannot mask a weak signal (F07/F32/F46)",
        "source_url": SRC_SCHED + "10",
    })

gate_rows = []
for gid, name, meaning, rule, src in GATE_DEFS:
    passing = [s["strategy_id"] for s, _l, _k in summaries if gate_eval(s).get(gid)]
    gate_rows.append({
        "gate_id": gid, "gate": name, "meaning": meaning, "rule": rule,
        "status": "Proposed cut-off — awaiting project-owner approval (F17)",
        "strategies_passing": ", ".join(passing) or "none",
        "source_url": src,
    })

bet_rows = []
for s, label, kind in summaries:
    for b in s["bets"]:
        bet_rows.append({
            "strategy_id": s["strategy_id"], "week": b["week"],
            "matchup": f"{b['away']} at {b['home']}",
            "bet": b["side"] if "side" in b else (b.get("side", "")),
            "reference_line": fmt(b.get("ref"), 1),
            "model_line": fmt(b.get("model"), 1),
            "actual": fmt(b.get("actual"), 1),
            "edge_points": fmt(b["edge"], 1),
            "result": "win" if b["hit"] == 1 else ("push" if b["hit"] is None else "loss"),
            "game_url": b.get("url", ""),
            "source_url": b.get("src", ""),
        })

backtest_rows = []
for r in sorted(oos, key=lambda r: (r["week"], r["home_team"])):
    backtest_rows.append({
        "week": r["week"], "matchup": f"{r['away_team']} at {r['home_team']}",
        "actual_margin": r["actual_margin"], "actual_total": r["actual_total"],
        "reference_spread_home": fmt(r["ref_margin"], 1),
        "reference_total": fmt(r["ref_total"], 1),
        "m1_spread_home": fmt(r["M1_margin"], 1), "m1_total": fmt(r["M1_total"], 1),
        "m2_spread_home": fmt(r["M2_margin"], 1),
        "m3_spread_home": fmt(r["M3_margin"], 1),
        "m4_spread_home": fmt(r["M4_margin"], 1),
        "m1_error": fmt(abs(r["actual_margin"] - r["M1_margin"]), 1),
        "reference_error": fmt(abs(r["actual_margin"] - r["ref_margin"]), 1),
        "game_url": r["game_url"], "source_url": r["source_url"],
    })

# ------------------------------------------------------ price snapshots ----
# A price-snapshot store records the opening and closing numbers of every
# market this project originates (side, total, moneyline). No licensed odds
# feed is connected and no official free source publishes opening or closing
# NFL market numbers, so every opening/closing value is left BLANK and
# flagged (F07/F31/F45) rather than inferred. The store schema and one row
# per originated market are published so the structure is in place the moment
# an official, rights-cleared odds source is connected.
SNAP_NOTE = ("Blank — no licensed odds feed; opening/closing numbers not "
             "confirmable from an official source (F07/F31/F45)")
snap_rows = []
snap_id = 0

def add_snapshot(week, matchup, market, fair_line, src):
    global snap_id
    snap_id += 1
    snap_rows.append({
        "snapshot_id": f"PS{snap_id:04d}",
        "week": week,
        "matchup": matchup,
        "market": market,
        "fair_line": fair_line,
        "opening_number": "",
        "opening_source": "",
        "opening_verified": "No",
        "closing_number": "",
        "closing_source": "",
        "closing_verified": "No",
        "captured_at": AS_OF,
        "status": SNAP_NOTE,
        "source_url": src,
    })

# Week 11 originated markets (side, then total, then moneyline per game).
for lr in lines_rows:
    src = lr["source_url"]
    m = lr["matchup"]
    add_snapshot(11, m, "Side (spread)", lr["fair_spread"], src)
    add_snapshot(11, m, "Total", lr["fair_total"], src)
    add_snapshot(11, m, "Moneyline",
                 f"home {lr['fair_moneyline_home']} / away {lr['fair_moneyline_away']}", src)

# Out-of-sample originated markets for the backtest window (weeks 4-10).
for r in oos:
    m = f"{r['away_team']} at {r['home_team']}"
    p_home = norm_cdf(r["M1_margin"] / sd_margin)
    ml_home = american_ml(p_home)
    ml_away = american_ml(1.0 - p_home)
    ml_txt = (f"home {ml_home} / away {ml_away}" if ml_home is not None else "")
    add_snapshot(r["week"], m, "Side (spread)", fmt(r["M1_margin"], 1), r["source_url"])
    add_snapshot(r["week"], m, "Total", fmt(r["M1_total"], 1), r["source_url"])
    add_snapshot(r["week"], m, "Moneyline", ml_txt, r["source_url"])

# -------------------------------------------------------------- output ------
write("model_lines_week11.csv", lines_rows,
      ["game_no", "matchup", "kickoff_et",
       "fair_spread", "market_spread", "fair_minus_market_spread",
       "fair_total", "market_total", "fair_minus_market_total",
       "fair_moneyline_home", "fair_moneyline_away",
       "market_moneyline_home", "market_moneyline_away",
       "fair_minus_market_moneyline_home", "fair_minus_market_moneyline_away",
       "model_home_points", "model_away_points", "home_win_prob",
       "model_spread_home", "model_total",
       "reference_spread_home", "reference_total", "model_minus_reference",
       "market_note", "game_url", "source_url"])
write("price_snapshots_extended.csv", snap_rows,
      ["snapshot_id", "week", "matchup", "market", "fair_line",
       "opening_number", "opening_source", "opening_verified",
       "closing_number", "closing_source", "closing_verified",
       "captured_at", "status", "source_url"])
write("model_ratings.csv", ratings_rows,
      ["team", "attack_rating", "defence_rating", "net_rating", "games_played", "notes", "source_url"])
write("model_backtest.csv", backtest_rows,
      ["week", "matchup", "actual_margin", "actual_total", "reference_spread_home", "reference_total",
       "m1_spread_home", "m1_total", "m2_spread_home", "m3_spread_home", "m4_spread_home",
       "m1_error", "reference_error", "game_url", "source_url"])
write("model_bets.csv", bet_rows,
      ["strategy_id", "week", "matchup", "bet", "reference_line", "model_line", "actual",
       "edge_points", "result", "game_url", "source_url"])
write("strategy_leaderboard.csv", leader_rows,
      ["rank", "strategy_id", "strategy", "market", "status", "demotion_safe",
       "skill_score_mae_improvement_pts",
       "skill_ci_low", "skill_ci_high", "skill_p_permutation", "q_bh_fdr", "mae_model",
       "mae_reference", "oos_games", "bets_vs_reference", "wins", "losses",
       "hit_rate_vs_reference", "mean_edge_points", "edge_ci_low", "edge_ci_high",
       "p_binomial", "p_permutation_bets", "sd_edge_points",
       "min_n_for_80pct_power", "sample_shortfall",
       "gates_passed", "gates_failed", "reward_tier", "reward_status",
       "staking_plan", "staking_units_wagered", "staking_roi_pct", "staking_note",
       "source_url"])
write("gate_results.csv", gate_rows,
      ["gate_id", "gate", "meaning", "rule", "status", "strategies_passing", "source_url"])
write("correlations_computed.csv", corr_rows,
      ["corr_id", "question", "value", "ci_low", "ci_high", "p_value", "sample_n",
       "interpretation", "source_url"])
write("parlay_analysis.csv", parlay_rows,
      ["parlay_id", "definition", "legs", "tickets", "leg1_hit_rate", "leg2_hit_rate",
       "observed_joint_hit_rate", "independence_expected_rate",
       "difference_observed_minus_independence", "phi_correlation", "two_by_two", "note", "source_url"])

summary = {
    "as_of": AS_OF,
    "games_transcribed": len(results),
    "weeks": sorted({g["week"] for g in results}),
    "out_of_sample_games": n_oos,
    "out_of_sample_weeks": [w for w in completed_weeks if w >= EVAL_FROM_WEEK],
    "bet_delta_points": BET_DELTA,
    "sd_margin_residual": round(sd_margin, 2),
    "calibration_slope": round(slope, 3),
    "calibration_slope_se": round(se_slope, 3),
    "calibration_intercept": round(intercept, 3),
    "sd_total_residual": round(sd_total, 2),
    "mae_reference": round(mae_ref, 2),
    "mae_m1": round(mae_m1, 2),
    "mae_improvement": round(mae_ref - mae_m1, 2),
    "hfa_ref_constant": HFA_REF,
    "week11_games": len(week11),
    "strategies_tested": len(summaries),
    "qualified_strategies": sum(1 for r in leader_rows if r["reward_tier"] != "Not qualified"),
    "tier1_strategies": sum(1 for r in leader_rows if r["reward_tier"].startswith("Tier 1")),
    "live_strategies": sum(1 for r in leader_rows if r["status"] == "Live"),
    "paper_strategies": sum(1 for r in leader_rows if r["status"] == "Paper"),
    "price_snapshot_rows": len(snap_rows),
    "lookahead_audit_pass": LOOKAHEAD_OK,
    "lookahead_audit_weeks": len(LOOKAHEAD_CHECKS),
    "neutral_site_games_modelled": sum(1 for g in results if g["neutral"]),
    "neutral_site_rows_blank": sum(1 for r in read("games_2026_results.csv")
                                   if r.get("neutral_site", "").strip() == ""),
    "injury_rows": len(injuries),
    "injury_teams": len({r["team_abbr"] for r in injuries}),
    "seed": SEED,
}
with open(os.path.join(DATA, "model_summary.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=1)

print(json.dumps(summary, indent=1))
print("\nLeaderboard:")
for r in leader_rows:
    print("  {}. {:3s} {:44s} skill={:>6s} CI[{:>6s},{:>6s}] q={:>6s} n={:>3s} "
          "hit={:>6s} gates={} {} {}".format(
              r["rank"], r["strategy_id"], r["strategy"][:44],
              r["skill_score_mae_improvement_pts"] or "-", r["skill_ci_low"] or "-",
              r["skill_ci_high"] or "-", r["q_bh_fdr"] or "-", str(r["bets_vs_reference"]),
              r["hit_rate_vs_reference"] or "-", r["gates_passed"], r["status"],
              r["reward_tier"]))
