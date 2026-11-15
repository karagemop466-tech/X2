#!/usr/bin/env python3
"""Control baseline for the strategy leaderboard (T98, session 46d43a42).

Two controls are scored on exactly the same out-of-sample games that the model
leaderboard uses (weeks 4-10 of the 2026 season, every game strictly graded
against the naive reference line from scripts/model.py):

  C0  random picks   - for each game, a side (home or away) drawn with a seeded
                       generator. Expected hit rate 0.5 if there is no skill.
  C1  favourites     - always back the side the reference line favours
                       (home if the reference margin is positive, away if it is
                       negative; a zero margin has no favourite and is excluded).

"Win" means the chosen side beat the reference line (edge > 0). A push (edge
exactly 0) is not a decided bet. The controls exist to show what skill-free
rules score on the same games, so a model leaderboard entry can be read against
them. They are not ranked and are not part of the multiple-testing family.

The reference line is re-derived here from the official results ledger
(data/games_2026_results.csv) with the same formula as scripts/model.py
(season point differential to date + 2.5 home field, no home term at neutral
sites). The script refuses to write output unless its reference line reproduces
data/model_backtest.csv for every out-of-sample game.

Inputs : data/games_2026_results.csv, data/model_backtest.csv
Outputs: data/control_baseline.csv (one row per control)
         data/control_bets.csv     (one row per game, both controls' picks)

Standard library only. Run:  python3 scripts/control_baseline.py
"""
import csv
import math
import os
import random
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")

SEED = 20261115            # fixed, pre-declared seed for the random control (C0)
BOOT_SEED = 20261116       # fixed seed for the bootstrap interval of the mean edge
BOOTSTRAP = 5000
EVAL_FROM_WEEK = 4         # same first out-of-sample week as scripts/model.py
HFA_REF = 2.5              # same fixed home-field constant as scripts/model.py


def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


results = read("games_2026_results.csv")
for r in results:
    r["week"] = int(r["week"])
    r["away_points"] = int(r["away_points"])
    r["home_points"] = int(r["home_points"])
    r["neutral"] = r.get("neutral_site", "").strip().upper() == "Y"
    r["margin"] = r["home_points"] - r["away_points"]


def season_to_date(week):
    st = defaultdict(lambda: [0, 0, 0])            # points for, against, games
    for g in results:
        if g["week"] < week:
            a, h = g["away_team"], g["home_team"]
            st[a][0] += g["away_points"]; st[a][1] += g["home_points"]; st[a][2] += 1
            st[h][0] += g["home_points"]; st[h][1] += g["away_points"]; st[h][2] += 1
    return st


def ref_margin(week, home, away, neutral):
    """Naive reference margin, home minus away (same formula as model.py ref_line)."""
    st = season_to_date(week)
    hd = (st[home][0] - st[home][1]) / st[home][2] if st[home][2] else 0.0
    ad = (st[away][0] - st[away][1]) / st[away][2] if st[away][2] else 0.0
    return (0.0 if neutral else HFA_REF) + (hd - ad)


def ref_total(week):
    st = season_to_date(week)
    lg = [v for v in st.values() if v[2]]
    return 2 * sum(v[0] for v in lg) / max(1, sum(v[2] for v in lg))


# ---- out-of-sample games: same set and order as scripts/model.py ----
oos = []
for g in sorted((r for r in results if r["week"] >= EVAL_FROM_WEEK),
                key=lambda r: (r["week"], r["game_url"])):
    rm = ref_margin(g["week"], g["home_team"], g["away_team"], g["neutral"])
    rt = ref_total(g["week"])
    oos.append({"week": g["week"], "home": g["home_team"], "away": g["away_team"],
                "actual": g["margin"], "ref": rm, "ref_total": rt,
                "game_url": g["game_url"], "source_url": g["source_url"]})

# ---- cross-check against the model's own out-of-sample record ----
backtest = {}
for r in read("model_backtest.csv"):
    backtest[(int(r["week"]), r["matchup"])] = r
mismatch = []
for o in oos:
    key = (o["week"], f'{o["away"]} at {o["home"]}')
    b = backtest.get(key)
    if b is None:
        mismatch.append(f"missing in model_backtest.csv: {key}")
        continue
    if abs(float(b["reference_spread_home"]) - o["ref"]) > 0.05 + 1e-9:
        mismatch.append(f"reference margin {key}: ledger {b['reference_spread_home']} vs {o['ref']:.3f}")
    if abs(float(b["reference_total"]) - o["ref_total"]) > 0.05 + 1e-9:
        mismatch.append(f"reference total {key}: ledger {b['reference_total']} vs {o['ref_total']:.3f}")
if len(oos) != len(backtest):
    mismatch.append(f"game count {len(oos)} vs model_backtest.csv {len(backtest)}")
if mismatch:
    print("REFUSING TO WRITE: reference line does not reproduce model_backtest.csv")
    for m in mismatch[:20]:
        print("  -", m)
    sys.exit(1)
print(f"Reference line reproduces model_backtest.csv for all {len(oos)} out-of-sample games.")


# ---- controls ----
def edge_for(side, o):
    """Points gained by the chosen side against the reference line (>0 = win)."""
    return (o["actual"] - o["ref"]) * (1 if side == "home" else -1)


rng = random.Random(SEED)
bets = []
for o in oos:
    c0_side = rng.choice(["home", "away"])
    c1_side = None
    if o["ref"] > 0:
        c1_side = "home"
    elif o["ref"] < 0:
        c1_side = "away"
    bets.append({"o": o, "c0": c0_side, "c1": c1_side})


def wilson(k, n, z=1.959963985):
    if n == 0:
        return None, None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def binom_two_sided(k, n):
    """Exact two-sided binomial test against p = 0.5."""
    if n == 0:
        return None
    pmf = [math.comb(n, i) * 0.5 ** n for i in range(n + 1)]
    pk = pmf[k]
    return min(1.0, sum(p for p in pmf if p <= pk * (1 + 1e-12)))


def bootstrap_mean_ci(vals, seed):
    if not vals:
        return None, None
    rnd = random.Random(seed)
    n = len(vals)
    means = sorted(sum(rnd.choice(vals) for _ in range(n)) / n for _ in range(BOOTSTRAP))
    return means[int(0.025 * BOOTSTRAP)], means[int(0.975 * BOOTSTRAP) - 1]


def summarise(cid, name, rule, side_key, seed):
    decided, pushes, edges = [], 0, []
    excluded = 0
    for b in bets:
        side = b[side_key]
        if side is None:
            excluded += 1
            continue
        e = edge_for(side, b["o"])
        if e == 0:
            pushes += 1
            continue
        decided.append(1 if e > 0 else 0)
        edges.append(e)
    n = len(decided)
    wins = sum(decided)
    lo, hi = wilson(wins, n)
    m = sum(edges) / n if n else None
    m_lo, m_hi = bootstrap_mean_ci(edges, seed)
    return {
        "control_id": cid,
        "control": name,
        "rule": rule,
        "games_in_scope": len(bets),
        "excluded_no_favourite": excluded,
        "decided": n,
        "pushes": pushes,
        "wins": wins,
        "losses": n - wins,
        "hit_rate": f"{wins / n:.3f}" if n else "",
        "wilson_95_low": f"{lo:.3f}" if n else "",
        "wilson_95_high": f"{hi:.3f}" if n else "",
        "p_binomial_vs_0_5": f"{binom_two_sided(wins, n):.4f}" if n else "",
        "mean_edge_points": f"{m:.2f}" if n else "",
        "mean_edge_95_low": f"{m_lo:.2f}" if n else "",
        "mean_edge_95_high": f"{m_hi:.2f}" if n else "",
        "random_seed": str(seed) if cid == "C0" else "",
        "ranked": "no - control, not in the ranked family",
        "source_url": "https://www.nfl.com/schedules/2026/by-week/week-10",
    }


controls = [
    summarise("C0", "Random picks",
              f"Each game: home or away drawn with random.Random({SEED}); no information used",
              "c0", SEED),
    summarise("C1", "Favourites only",
              "Each game: back the side the reference line favours (no favourite at a zero margin)",
              "c1", BOOT_SEED),
]

with open(os.path.join(DATA, "control_baseline.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(controls[0].keys()), lineterminator="\r\n")
    w.writeheader()
    w.writerows(controls)

with open(os.path.join(DATA, "control_bets.csv"), "w", encoding="utf-8", newline="") as f:
    fields = ["week", "matchup", "reference_margin_home", "actual_margin_home",
              "c0_side", "c0_result", "c1_side", "c1_result", "game_url", "source_url"]
    w = csv.DictWriter(f, fieldnames=fields, lineterminator="\r\n")
    w.writeheader()
    for b in bets:
        o = b["o"]

        def res(side):
            if side is None:
                return "no favourite"
            e = edge_for(side, o)
            return "push" if e == 0 else ("win" if e > 0 else "loss")
        w.writerow({"week": o["week"], "matchup": f'{o["away"]} at {o["home"]}',
                    "reference_margin_home": f'{o["ref"]:.1f}', "actual_margin_home": o["actual"],
                    "c0_side": b["c0"], "c0_result": res(b["c0"]),
                    "c1_side": b["c1"] or "", "c1_result": res(b["c1"]),
                    "game_url": o["game_url"], "source_url": o["source_url"]})

for c in controls:
    print(c["control_id"], c["control"], "decided", c["decided"], "wins", c["wins"],
          "hit", c["hit_rate"], "CI", c["wilson_95_low"], c["wilson_95_high"],
          "p", c["p_binomial_vs_0_5"], "mean edge", c["mean_edge_points"])
