#!/usr/bin/env python3
"""Parallel v2 research corpus (decision P09 = option B), session 60c8c865 (T111).

Decision P09 asked whether to adopt the 13 settled Week 10 games and the nine
neutral-site flags into the published corpus. Option B - the console's own
recommendation, recorded on 2026-11-18 - is: publish a PARALLEL v2 research
register and keep v1 (137 games) frozen as the published record. This script
implements exactly that and nothing else:

  * v1 files (data/games_2026_results.csv, model_*.csv, model_summary.json,
    results_feed_2026.csv, strategy_*.csv) are OPENED READ-ONLY. Their
    sha256 is taken before and after the run and the script fails if any
    changed. No published metric is recomputed over v1 here.
  * v2 = the 137 published rows PLUS the 13 official Week 10 finals already
    transcribed in data/games_week10_backfill_2026.csv (source:
    https://www.nfl.com/schedules/2026/by-week/week-10, read 2026-11-18),
    with neutral_site = Y on the settled international games matched from
    data/international_games_2026.csv (source: NFL Football Operations).
    Nothing is inferred: flags come from the official international slate,
    scores from the two official transcriptions.

SELF-CHECK BEFORE ANY OUTPUT. The walk-forward and rating code below is copied
from scripts/model.py. Before a single v2 file is written, the same code is run
on the v1 corpus and must reproduce the PUBLISHED v1 numbers:

  - data/model_backtest.csv     (89 rows, 1dp)          tolerance 0.055
  - data/model_ratings.csv      (32 rows, 2dp)          tolerance 0.006
  - data/model_summary.json     MAE and slope           tolerance per field

If any reproduction check fails the script exits non-zero and writes nothing:
a v2 built by code that cannot reproduce v1 is not fit to publish.

Outputs (all new files; v1 untouched):
  data/games_2026_results_v2.csv      150 rows, neutral flags applied
  data/corpus_v2_selfcheck.csv        the v1 reproduction checks, published
  data/corpus_v2_backtest.csv         v2 walk-forward (102 OOS rows, weeks 4-10)
  data/corpus_v2_ratings.csv          v1 vs v2 ratings per club
  data/corpus_v2_metrics.csv          headline v1 vs v2 metrics, side by side
  data/corpus_v2_pick_diffs.csv       per common game: pick, gate, flip
  data/corpus_v2_week11_lines.csv     Week 11 lines under v2 (side, total, ML)

Run:  python3 scripts/corpus_v2.py
"""
import csv
import hashlib
import json
import math
import os
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")

EVAL_FROM_WEEK = 4          # as model.py
BET_DELTA = 3.0             # as model.py
HFA_REF = 2.5               # as model.py
TOL_BACKTEST = 0.055        # published at 1dp
TOL_RATING = 0.006          # published at 2dp
TOL_SUMMARY = 0.006         # published at 2dp
TOL_SLOPE = 0.001           # published at 3dp
SRC_SCHED10 = "https://www.nfl.com/schedules/2026/by-week/week-10"
SRC_STAND = "https://www.nfl.com/standings/"
SRC_INTL = ("https://operations.nfl.com/programs-initiatives/international-growth/"
            "nfl-international-games")

# v1 files that must not change (sha256 before/after).
V1_IMMUTABLE = [
    "games_2026_results.csv", "model_backtest.csv", "model_ratings.csv",
    "model_lines_week11.csv", "model_summary.json", "results_feed_2026.csv",
    "strategy_leaderboard.csv", "model_bets.csv",
]


def fail(msg):
    raise SystemExit("CORPUS V2 FAILED: " + msg)


def read(name):
    path = name if os.path.isabs(name) else os.path.join(DATA, name)
    if not os.path.exists(path):
        fail(f"missing input {name}")
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write(name, rows, fields):
    with open(os.path.join(DATA, name), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def sha(name):
    with open(os.path.join(DATA, name), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def fmt(x, nd=3):
    return "" if x is None else f"{x:.{nd}f}"


# ------------------------------------------------------- model.py copy ----
# Copied verbatim (behaviourally) from scripts/model.py so the self-check
# compares like with like. Sums iterate in corpus order, exactly as model.py.
def solve(A, b):
    n = len(A)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[piv][col]) < 1e-12:
            fail("singular matrix in ridge fit")
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


def prep(rows, apply_flags):
    """Copy rows into model shape. apply_flags=False reproduces published v1
    (every neutral_site blank -> not neutral). apply_flags=True builds v2."""
    out = []
    for r in rows:
        g = dict(r)
        g["week"] = int(g["week"])
        g["away_points"] = int(g["away_points"])
        g["home_points"] = int(g["home_points"])
        flag = (g.get("neutral_site", "") or "").strip().upper() == "Y"
        g["neutral"] = bool(flag and apply_flags)
        g["margin"] = g["home_points"] - g["away_points"]
        g["total"] = g["home_points"] + g["away_points"]
        out.append(g)
    return out


def teams_index(games):
    teams = sorted({g["away_team"] for g in games} | {g["home_team"] for g in games})
    return teams, {t: i for i, t in enumerate(teams)}


def fit(games, idx, lam, half_life=None, ref_week=None):
    nt = len(idx)
    p = 1 + nt + nt + 1
    xtX = [[0.0] * p for _ in range(p)]
    xty = [0.0] * p
    n_obs = 0
    for g in games:
        if half_life and ref_week is not None:
            w = 0.5 ** ((ref_week - g["week"]) / half_life)
        else:
            w = 1.0
        hfa = 0.0 if g.get("neutral") else 1.0
        for t, o, home in ((g["home_team"], g["away_team"], hfa),
                           (g["away_team"], g["home_team"], 0.0)):
            cols = [(0, 1.0), (1 + idx[t], 1.0), (1 + nt + idx[o], -1.0), (1 + 2 * nt, home)]
            y = g["home_points"] if home else g["away_points"]
            for i, vi in cols:
                xty[i] += w * vi * y
                for j, vj in cols:
                    xtX[i][j] += w * vi * vj
            n_obs += 1
    for i in range(1, 1 + 2 * nt):
        xtX[i][i] += lam
    beta = solve(xtX, xty)
    return {"mu": beta[0], "A": beta[1:1 + nt], "D": beta[1 + nt:1 + 2 * nt],
            "h": beta[1 + 2 * nt]}, n_obs


def predict(p, idx, home, away, neutral=False):
    hfa = 0.0 if neutral else p["h"]
    home_pts = p["mu"] + p["A"][idx[home]] - p["D"][idx[away]] + hfa
    away_pts = p["mu"] + p["A"][idx[away]] - p["D"][idx[home]]
    return {"home_points": home_pts, "away_points": away_pts,
            "margin": home_pts - away_pts, "total": home_pts + away_pts}


def season_to_date(games, week):
    st = defaultdict(lambda: [0, 0, 0])
    for g in games:
        if g["week"] < week:
            a, h = g["away_team"], g["home_team"]
            st[a][0] += g["away_points"]; st[a][1] += g["home_points"]; st[a][2] += 1
            st[h][0] += g["home_points"]; st[h][1] += g["away_points"]; st[h][2] += 1
    return st


def ref_line(games, week, home, away, neutral=False):
    st = season_to_date(games, week)
    lg = [v for v in st.values() if v[2]]
    lg_ppg = sum(v[0] for v in lg) / max(1, sum(v[2] for v in lg))
    hd = (st[home][0] - st[home][1]) / st[home][2] if st[home][2] else 0.0
    ad = (st[away][0] - st[away][1]) / st[away][2] if st[away][2] else 0.0
    margin = (0.0 if neutral else HFA_REF) + (hd - ad)
    return {"margin": margin, "total": 2 * lg_ppg}


def norm_cdf(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def american_ml(p):
    if p is None or p <= 0.0 or p >= 1.0:
        return None
    if p >= 0.5:
        return -round(100.0 * p / (1.0 - p))
    return round(100.0 * (1.0 - p) / p)


STRATEGIES = [
    ("M1", 4.0, None),
    ("M2", 4.0, 3.0),
    ("M3", 12.0, None),
    ("M4", 1.0, None),
]


def walk_forward(games):
    idx_map = dict(teams_index(games)[1])
    by_week = defaultdict(list)
    for g in games:
        by_week[g["week"]].append(g)
    oos = []
    for wk in sorted(w for w in by_week if w <= 10):
        if wk < EVAL_FROM_WEEK:
            continue
        train = [g for g in games if g["week"] < wk]
        if len(train) < 20:
            continue
        params = {sid: fit(train, idx_map, lam, half_life=hl, ref_week=wk)[0]
                  for sid, lam, hl in STRATEGIES}
        for g in by_week[wk]:
            row = {"week": wk, "away_team": g["away_team"], "home_team": g["home_team"],
                   "actual_margin": g["margin"], "actual_total": g["total"],
                   "neutral": g["neutral"],
                   "game_url": g["game_url"], "source_url": g["source_url"]}
            rl = ref_line(games, wk, g["home_team"], g["away_team"], g["neutral"])
            row["ref_margin"] = rl["margin"]
            row["ref_total"] = rl["total"]
            for sid, _lam, _hl in STRATEGIES:
                pr = predict(params[sid], idx_map, g["home_team"], g["away_team"], g["neutral"])
                row[sid + "_margin"] = pr["margin"]
                row[sid + "_total"] = pr["total"]
            # no-look-ahead assertion: every training week strictly earlier
            train_weeks = {t["week"] for t in train}
            if train_weeks and max(train_weeks) >= wk:
                fail(f"look-ahead: training contains week {max(train_weeks)} for week {wk}")
            oos.append(row)
    return oos


def headline(oos):
    n = len(oos)
    mae_ref = sum(abs(r["actual_margin"] - r["ref_margin"]) for r in oos) / n
    mae_m1 = sum(abs(r["actual_margin"] - r["M1_margin"]) for r in oos) / n
    xs = [r["M1_margin"] for r in oos]
    ys = [r["actual_margin"] for r in oos]
    mx = sum(xs) / n; my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    intercept = my - slope * mx
    resid = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
    se_slope = math.sqrt(sum(e * e for e in resid) / (n - 2) / sxx)
    res_m = [r["actual_margin"] - r["M1_margin"] for r in oos]
    res_t = [r["actual_total"] - r["M1_total"] for r in oos]
    sd_m = math.sqrt(sum(x * x for x in res_m) / max(1, n - 1))
    sd_t = math.sqrt(sum(x * x for x in res_t) / max(1, n - 1))
    return {"n_oos": n, "mae_reference": mae_ref, "mae_m1": mae_m1,
            "mae_improvement": mae_ref - mae_m1, "calibration_slope": slope,
            "calibration_slope_se": se_slope, "sd_margin_residual": sd_m,
            "sd_total_residual": sd_t}


# ------------------------------------------------------------- inputs -----
before = {f: sha(f) for f in V1_IMMUTABLE}

v1_rows = read("games_2026_results.csv")
backfill = read("games_week10_backfill_2026.csv")
intl = read("international_games_2026.csv")
week11 = read("schedule_week11_2026.csv")

# International flags for v2: (week, away, home) of every settled international
# game that lands in the 150-game corpus. Week 11 MIN at SF is unplayed and is
# not part of the results corpus (it already carries neutral_site in the
# schedule file the model reads).
intl_pairs = set()
for r in intl:
    if r["in_results_feed"] == "yes" or any(
            b["week"] == r["week"] and b["away_team"] == r["away_designated"]
            and b["home_team"] == r["home_designated"] for b in backfill):
        intl_pairs.add((int(r["week"]), r["away_designated"], r["home_designated"]))

v2_rows = []
for r in v1_rows:
    g = dict(r)
    if (int(g["week"]), g["away_team"], g["home_team"]) in intl_pairs:
        g["neutral_site"] = "Y"
    v2_rows.append(g)
for b in backfill:
    g = {"season": "2026", "week": b["week"], "date_as_shown": b["date_as_shown"],
         "away_team": b["away_team"], "away_points": b["away_points"],
         "home_team": b["home_team"], "home_points": b["home_points"],
         "game_url": b["game_url"], "source_url": b["source_url"], "neutral_site": ""}
    if (int(g["week"]), g["away_team"], g["home_team"]) in intl_pairs:
        g["neutral_site"] = "Y"
    v2_rows.append(g)

if len(v1_rows) != 137:
    fail(f"v1 corpus is {len(v1_rows)} rows, expected 137")
if len(v2_rows) != 150:
    fail(f"v2 corpus is {len(v2_rows)} rows, expected 150")
v2_flagged = [g for g in v2_rows if g["neutral_site"] == "Y"]
if len(v2_flagged) != 8:
    fail(f"v2 carries {len(v2_flagged)} neutral flags, expected 8 settled international games")
if len({(g['week'], g['away_team'], g['home_team']) for g in v2_rows}) != 150:
    fail("v2 corpus has duplicate fixtures")

# ------------------------------------------------- self-check on v1 -------
v1 = prep(v1_rows, apply_flags=False)          # exactly what model.py sees
oos_v1 = walk_forward(v1)
summary_pub = json.load(open(os.path.join(DATA, "model_summary.json"), encoding="utf-8"))
bt_pub = read("model_backtest.csv")
ratings_pub = read("model_ratings.csv")

checks = []


def check(cid, what, ok, detail, src):
    checks.append({"check_id": cid, "what_was_checked": what,
                   "result": "pass" if ok else "FAIL", "detail": detail,
                   "source_url": src})
    if not ok:
        fail(f"{cid}: {detail}")


# SC1: walk-forward reproduces every published backtest row.
pub_by = {(int(r["week"]), r["matchup"]): r for r in bt_pub}
worst = 0.0
mismatch = []
for r in oos_v1:
    key = (r["week"], f"{r['away_team']} at {r['home_team']}")
    p = pub_by.get(key)
    if p is None:
        mismatch.append(f"missing in published: {key}")
        continue
    for col, val in (("m1_spread_home", r["M1_margin"]), ("m1_total", r["M1_total"]),
                     ("m2_spread_home", r["M2_margin"]), ("m3_spread_home", r["M3_margin"]),
                     ("m4_spread_home", r["M4_margin"]),
                     ("reference_spread_home", r["ref_margin"]),
                     ("reference_total", r["ref_total"])):
        d = abs(float(p[col]) - val)
        worst = max(worst, d)
        if d > TOL_BACKTEST:
            mismatch.append(f"{key} {col}: published {p[col]} vs {val:.3f}")
check("SC1", "v1 walk-forward reproduces data/model_backtest.csv (89 rows, 7 numeric columns, 1dp)",
      not mismatch and len(oos_v1) == len(bt_pub) == 89,
      (f"89 rows; largest absolute difference {worst:.4f} pts (tolerance {TOL_BACKTEST}); "
       + ("no mismatches" if not mismatch else "; ".join(mismatch[:5]))),
      "https://github.com/karagemop466-tech/X2/blob/main/data/model_backtest.csv")

# SC2: final v1 fit reproduces the published ratings.
teams_v1, idx_v1 = teams_index(v1)
main_v1, _ = fit(v1, idx_v1, 4.0)
worst_r = 0.0
mismatch_r = []
for p in ratings_pub:
    t = p["team"]
    for col, val in (("attack_rating", main_v1["A"][idx_v1[t]]),
                     ("defence_rating", main_v1["D"][idx_v1[t]]),
                     ("net_rating", main_v1["A"][idx_v1[t]] + main_v1["D"][idx_v1[t]])):
        d = abs(float(p[col]) - val)
        worst_r = max(worst_r, d)
        if d > TOL_RATING:
            mismatch_r.append(f"{t} {col}: published {p[col]} vs {val:.4f}")
check("SC2", "v1 final ridge fit reproduces data/model_ratings.csv (32 clubs, 2dp)",
      not mismatch_r and len(ratings_pub) == 32,
      (f"32 clubs; largest absolute difference {worst_r:.5f} pts (tolerance {TOL_RATING}); "
       + ("no mismatches" if not mismatch_r else "; ".join(mismatch_r[:5]))),
      "https://github.com/karagemop466-tech/X2/blob/main/data/model_ratings.csv")

# SC3: headline v1 metrics reproduce model_summary.json.
h_v1 = headline(oos_v1)
m3_ok = (abs(h_v1["mae_reference"] - summary_pub["mae_reference"]) <= TOL_SUMMARY
         and abs(h_v1["mae_m1"] - summary_pub["mae_m1"]) <= TOL_SUMMARY
         and abs(h_v1["mae_improvement"] - summary_pub["mae_improvement"]) <= TOL_SUMMARY
         and abs(h_v1["calibration_slope"] - summary_pub["calibration_slope"]) <= TOL_SLOPE
         and abs(h_v1["sd_margin_residual"] - summary_pub["sd_margin_residual"]) <= TOL_SUMMARY)
check("SC3", "v1 headline metrics reproduce data/model_summary.json (MAE, improvement, slope, residual sd)",
      m3_ok,
      (f"MAE ref {h_v1['mae_reference']:.3f} vs {summary_pub['mae_reference']}; "
       f"MAE M1 {h_v1['mae_m1']:.3f} vs {summary_pub['mae_m1']}; "
       f"slope {h_v1['calibration_slope']:.4f} vs {summary_pub['calibration_slope']}; "
       f"sd {h_v1['sd_margin_residual']:.3f} vs {summary_pub['sd_margin_residual']}"),
      "https://github.com/karagemop466-tech/X2/blob/main/data/model_summary.json")

# SC4: the v2 corpus is built only from the two official transcriptions.
src_ok = all(r["source_url"].startswith("https://www.nfl.com/") for r in v2_rows)
check("SC4", "every one of the 150 v2 rows carries an official nfl.com source link",
      src_ok and len(v2_rows) == 150,
      f"{sum(1 for r in v2_rows if r['source_url'].startswith('https://www.nfl.com/'))} of 150 rows source-linked",
      SRC_SCHED10)

# SC5: neutral flags come from the official international slate only.
flag_src_ok = all(
    (int(r["week"]), r["away_team"], r["home_team"]) in intl_pairs
    for r in v2_rows if r["neutral_site"] == "Y")
check("SC5", "each of the 8 v2 neutral flags matches a settled game on the official international slate",
      flag_src_ok and len(v2_flagged) == 8,
      f"{len(v2_flagged)} flagged games, all present in data/international_games_2026.csv",
      SRC_INTL)

# ------------------------------------------------------------ v2 run ------
oos_v2 = walk_forward(prep(v2_rows, apply_flags=True))
teams_v2, idx_v2 = teams_index(prep(v2_rows, apply_flags=True))
v2_prepped = prep(v2_rows, apply_flags=True)
main_v2, _ = fit(v2_prepped, idx_v2, 4.0)
h_v2 = headline(oos_v2)

check("SC6", "v2 walk-forward covers weeks 4-10 with the 14-game Week 10 slate",
      len(oos_v2) == 102 and sum(1 for r in oos_v2 if r["week"] == 10) == 14,
      f"{len(oos_v2)} out-of-sample rows (v1: 89); Week 10 rows: "
      f"{sum(1 for r in oos_v2 if r['week'] == 10)} (v1: 1)",
      SRC_SCHED10)

# SC7: no look-ahead in v2 (walk_forward already fails hard; record the audit).
check("SC7", "every v2 prediction for week W is fitted only on games strictly before week W",
      True, "training weeks asserted strictly earlier inside walk_forward for all 7 evaluated weeks",
      "https://www.itl.nist.gov/div898/handbook/pmd/section4/pmd44.htm")

# ------------------------------------------------------------- outputs ----
# 1. the v2 corpus itself
write("games_2026_results_v2.csv", v2_rows,
      ["season", "week", "date_as_shown", "away_team", "away_points", "home_team",
       "home_points", "game_url", "source_url", "neutral_site"])

# 2. self-check register
write("corpus_v2_selfcheck.csv", checks,
      ["check_id", "what_was_checked", "result", "detail", "source_url"])

# 3. v2 backtest, same shape as model_backtest plus corpus membership
bt_rows = []
for r in sorted(oos_v2, key=lambda r: (r["week"], r["home_team"])):
    bt_rows.append({
        "week": r["week"], "matchup": f"{r['away_team']} at {r['home_team']}",
        "actual_margin": r["actual_margin"], "actual_total": r["actual_total"],
        "neutral_site": "Y" if r["neutral"] else "",
        "reference_spread_home": fmt(r["ref_margin"], 1),
        "reference_total": fmt(r["ref_total"], 1),
        "m1_spread_home": fmt(r["M1_margin"], 1), "m1_total": fmt(r["M1_total"], 1),
        "m2_spread_home": fmt(r["M2_margin"], 1),
        "m3_spread_home": fmt(r["M3_margin"], 1),
        "m4_spread_home": fmt(r["M4_margin"], 1),
        "m1_error": fmt(abs(r["actual_margin"] - r["M1_margin"]), 1),
        "reference_error": fmt(abs(r["actual_margin"] - r["ref_margin"]), 1),
        "in_v1_published_corpus": "yes" if r["week"] < 10 or (
            r["week"] == 10 and r["away_team"] == "WAS" and r["home_team"] == "NYG") else "no",
        "game_url": r["game_url"], "source_url": r["source_url"]})
write("corpus_v2_backtest.csv", bt_rows,
      ["week", "matchup", "actual_margin", "actual_total", "neutral_site",
       "reference_spread_home", "reference_total", "m1_spread_home", "m1_total",
       "m2_spread_home", "m3_spread_home", "m4_spread_home", "m1_error",
       "reference_error", "in_v1_published_corpus", "game_url", "source_url"])

# 4. ratings v1 vs v2
gp = defaultdict(int)
for g in v2_prepped:
    gp[g["away_team"]] += 1
    gp[g["home_team"]] += 1
rating_rows = []
for t in teams_v1:
    a1, d1 = main_v1["A"][idx_v1[t]], main_v1["D"][idx_v1[t]]
    a2, d2 = main_v2["A"][idx_v2[t]], main_v2["D"][idx_v2[t]]
    rating_rows.append({
        "team": t,
        "v1_attack": fmt(a1, 2), "v2_attack": fmt(a2, 2), "delta_attack": fmt(a2 - a1, 2),
        "v1_defence": fmt(d1, 2), "v2_defence": fmt(d2, 2), "delta_defence": fmt(d2 - d1, 2),
        "v1_net": fmt(a1 + d1, 2), "v2_net": fmt(a2 + d2, 2), "delta_net": fmt((a2 + d2) - (a1 + d1), 2),
        "v2_games_played": gp[t],
        "notes": "v1 = published 137-game fit; v2 = 150-game fit with neutral flags (P09=B)",
        "source_url": SRC_STAND})
rating_rows.sort(key=lambda r: -float(r["v2_net"]))
write("corpus_v2_ratings.csv", rating_rows,
      ["team", "v1_attack", "v2_attack", "delta_attack", "v1_defence", "v2_defence",
       "delta_defence", "v1_net", "v2_net", "delta_net", "v2_games_played", "notes",
       "source_url"])

# 5. headline metrics side by side
v1_by = {(r["week"], r["away_team"], r["home_team"]): r for r in oos_v1}
common = [r for r in oos_v2
          if (r["week"], r["away_team"], r["home_team"]) in v1_by]
h_c1 = headline([v1_by[(r["week"], r["away_team"], r["home_team"])] for r in common])
h_c2 = headline(common)
# reference total for week 11 under each corpus
rt_v1 = ref_line(v1, 11, "KC", "PHI")["total"]
rt_v2 = ref_line(v2_prepped, 11, "KC", "PHI")["total"]
metric_rows = []


def mrow(metric, v1v, v2v, note, src=SRC_STAND, nd=3):
    delta = ""
    try:
        delta = fmt(float(v2v) - float(v1v), nd)
    except (TypeError, ValueError):
        delta = ""
    metric_rows.append({"metric": metric, "v1_published_137": fmt(v1v, nd) if isinstance(v1v, float) else v1v,
                        "v2_research_150": fmt(v2v, nd) if isinstance(v2v, float) else v2v,
                        "delta_v2_minus_v1": delta, "note": note, "source_url": src})


mrow("corpus_games", 137, 150, "v1 is the frozen published record; v2 adds the 13 official Week 10 finals (P09=B)", SRC_SCHED10, 0)
mrow("neutral_flagged_games", 0, len(v2_flagged), "v1 publishes blank neutral_site on every row; v2 flags the settled international games from the official slate", SRC_INTL, 0)
mrow("out_of_sample_games_weeks_4_10", h_v1["n_oos"], h_v2["n_oos"], "v2 adds 13 Week 10 games to the walk-forward", SRC_SCHED10, 0)
mrow("mae_reference_common_89", h_c1["mae_reference"], h_c2["mae_reference"], "same 89 games under both corpora: isolates the neutral-flag + refit effect", SRC_STAND)
mrow("mae_m1_common_89", h_c1["mae_m1"], h_c2["mae_m1"], "same 89 games under both corpora", SRC_STAND)
mrow("mae_improvement_common_89", h_c1["mae_improvement"], h_c2["mae_improvement"], "model minus reference, positive = model closer", SRC_STAND)
mrow("mae_reference_v2_full_102", h_v1["mae_reference"], h_v2["mae_reference"], "v1 column is its own 89-game value; v2 covers 102 games - not like for like", SRC_SCHED10)
mrow("mae_m1_v2_full_102", h_v1["mae_m1"], h_v2["mae_m1"], "v1 column is its own 89-game value; v2 covers 102 games - not like for like", SRC_SCHED10)
mrow("calibration_slope_common_89", h_c1["calibration_slope"], h_c2["calibration_slope"], "OLS slope of actual on predicted margin, same 89 games", SRC_STAND)
mrow("sd_margin_residual_common_89", h_c1["sd_margin_residual"], h_c2["sd_margin_residual"], "residual scale used for prices-free probabilities", SRC_STAND)
mrow("fitted_home_field_term", main_v1["h"], main_v2["h"], "ridge estimate of the home-field term; v2 zeroes it on 8 flagged games", SRC_STAND)
mrow("reference_total_week11", rt_v1, rt_v2, "2 x league avg points/team/game over games strictly before Week 11 (F44)", SRC_SCHED10, 1)
write("corpus_v2_metrics.csv", metric_rows,
      ["metric", "v1_published_137", "v2_research_150", "delta_v2_minus_v1", "note", "source_url"])

# 6. per-game pick and gate diffs on the 89 common games
def side_pick(model, ref):
    d = model - ref
    if abs(d) < 1e-12:
        return "none"
    return "home" if d > 0 else "away"


diff_rows = []
flips = crossings = 0
for r in common:
    k = (r["week"], r["away_team"], r["home_team"])
    a = v1_by[k]
    pick1, pick2 = side_pick(a["M1_margin"], a["ref_margin"]), side_pick(r["M1_margin"], r["ref_margin"])
    gate1 = abs(a["M1_margin"] - a["ref_margin"]) >= BET_DELTA
    gate2 = abs(r["M1_margin"] - r["ref_margin"]) >= BET_DELTA
    flip = pick1 != pick2
    cross = gate1 != gate2
    flips += flip
    crossings += cross
    diff_rows.append({
        "week": r["week"], "matchup": f"{r['away_team']} at {r['home_team']}",
        "v1_m1_spread": fmt(a["M1_margin"], 1), "v2_m1_spread": fmt(r["M1_margin"], 1),
        "delta_m1_spread": fmt(r["M1_margin"] - a["M1_margin"], 1),
        "v1_reference_spread": fmt(a["ref_margin"], 1), "v2_reference_spread": fmt(r["ref_margin"], 1),
        "v1_side_pick": pick1, "v2_side_pick": pick2,
        "side_pick_flipped": "yes" if flip else "no",
        "v1_at_bet_gate": "yes" if gate1 else "no", "v2_at_bet_gate": "yes" if gate2 else "no",
        "bet_gate_crossed": "yes" if cross else "no",
        "actual_margin": r["actual_margin"],
        "note": "gate = |model - reference| >= 3 pts (pre-registered BET_DELTA); research comparison only",
        "source_url": r["source_url"]})
diff_rows.sort(key=lambda r: (r["week"], r["matchup"]))
write("corpus_v2_pick_diffs.csv", diff_rows,
      ["week", "matchup", "v1_m1_spread", "v2_m1_spread", "delta_m1_spread",
       "v1_reference_spread", "v2_reference_spread", "v1_side_pick", "v2_side_pick",
       "side_pick_flipped", "v1_at_bet_gate", "v2_at_bet_gate", "bet_gate_crossed",
       "actual_margin", "note", "source_url"])

# 7. Week 11 lines under v2 (side -> total -> moneyline), for comparison only
w11_rows = []
sd_v2 = h_v2["sd_margin_residual"]
for g in week11:
    home, away = g["home_team"], g["away_team"]
    neutral = (g.get("neutral_site", "") or "").strip().upper() == "Y"
    pr2 = predict(main_v2, idx_v2, home, away, neutral)
    pr1 = predict(main_v1, idx_v1, home, away, neutral)
    rl2 = ref_line(v2_prepped, 11, home, away, neutral)
    rl1 = ref_line(v1, 11, home, away, neutral)
    p_home2 = norm_cdf(pr2["margin"] / sd_v2)
    ml2_h = american_ml(p_home2)
    ml2_a = american_ml(1.0 - p_home2)
    w11_rows.append({
        "game_no": g["game_no"], "matchup": f"{away} at {home}",
        "neutral_site": "Y" if neutral else "",
        "v1_fair_spread": fmt(pr1["margin"], 1), "v2_fair_spread": fmt(pr2["margin"], 1),
        "delta_spread": fmt(pr2["margin"] - pr1["margin"], 1),
        "v1_fair_total": fmt(pr1["total"], 1), "v2_fair_total": fmt(pr2["total"], 1),
        "delta_total": fmt(pr2["total"] - pr1["total"], 1),
        "v1_reference_spread": fmt(rl1["margin"], 1), "v2_reference_spread": fmt(rl2["margin"], 1),
        "v2_moneyline_home": str(ml2_h) if ml2_h is not None else "",
        "v2_moneyline_away": str(ml2_a) if ml2_a is not None else "",
        "note": ("v2 research line under P09=B; the published record remains data/model_lines_week11.csv. "
                 "Moneyline implied by the v2 residual scale, no market price (F07)."),
        "game_url": g["game_url"], "source_url": g["source_url"]})
w11_rows.sort(key=lambda r: int(r["game_no"]))
write("corpus_v2_week11_lines.csv", w11_rows,
      ["game_no", "matchup", "neutral_site", "v1_fair_spread", "v2_fair_spread",
       "delta_spread", "v1_fair_total", "v2_fair_total", "delta_total",
       "v1_reference_spread", "v2_reference_spread", "v2_moneyline_home",
       "v2_moneyline_away", "note", "game_url", "source_url"])

# --------------------------------------------------- immutability proof ---
after = {f: sha(f) for f in V1_IMMUTABLE}
changed = [f for f in V1_IMMUTABLE if before[f] != after[f]]
if changed:
    fail(f"v1 files were modified: {changed}")

print(f"SELF-CHECK: {len(checks)} checks, all pass (v1 reproduced before any v2 write).")
print(f"v1 OOS {h_v1['n_oos']} games, MAE ref {h_v1['mae_reference']:.2f}, MAE M1 {h_v1['mae_m1']:.2f}")
print(f"v2 OOS {h_v2['n_oos']} games, MAE ref {h_v2['mae_reference']:.2f}, MAE M1 {h_v2['mae_m1']:.2f}")
print(f"common-89 side picks flipped: {flips}; bet-gate crossings: {crossings}")
print(f"v1 immutable files unchanged: {len(V1_IMMUTABLE)} of {len(V1_IMMUTABLE)}")
print("corpus v2 outputs written: games_2026_results_v2.csv, corpus_v2_selfcheck.csv, "
      "corpus_v2_backtest.csv, corpus_v2_ratings.csv, corpus_v2_metrics.csv, "
      "corpus_v2_pick_diffs.csv, corpus_v2_week11_lines.csv")
