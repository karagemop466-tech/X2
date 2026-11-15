#!/usr/bin/env python3
"""Control baselines for the out-of-sample side (straight-up winner) record.

Standard library only. Run:  python3 scripts/controls.py

Reads the 89 walk-forward out-of-sample games in data/model_backtest.csv (weeks 4-10
of 2026, every margin taken from the official NFL game pages linked in that file) and
grades three rules on the decided games (the one tied game is excluded):

  C1  Random picks      - each game is a fair coin flip (seeded, 10,000 draws).
  C2  Favourite only    - pick the team the NAIVE REFERENCE LINE favours. No betting
                          market exists in this repository, so "favourite" means the
                          reference line's favourite, not a market favourite (Flag F32).
  C3  Model M1          - pick the team the M1 model favours (for comparison).

Writes:
  data/control_baselines.csv        one row per control
  data/control_baselines_games.csv  one row per game: C2 and C3 picks and whether each was right
                                    (C1 is a distribution over draws, so it has no per-game row)

Sign convention used by the source file: margin = home points - away points, so a
positive reference or model margin favours the HOME team. The column names
'reference_spread_home' and 'm1_spread_home' hold these margins (not market spreads).
"""
import csv
import math
import os
import random

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "data", "model_backtest.csv")
OUT = os.path.join(ROOT, "data", "control_baselines.csv")
OUT_GAMES = os.path.join(ROOT, "data", "control_baselines_games.csv")
SEED = 20261115          # fixed seed, recorded so the random-pick result can be replayed
DRAWS = 10000
SCHEDULE_URL = "https://www.nfl.com/schedules/2026/by-week/week-4"


def wilson(k, n, z=1.959964):
    if n == 0:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def binom_two_sided_p(k, n):
    """Exact two-sided binomial test against p = 0.5."""
    if n == 0:
        return None
    probs = [math.comb(n, i) * 0.5 ** n for i in range(n + 1)]
    pk = probs[k]
    return min(1.0, sum(p for p in probs if p <= pk + 1e-12))


def main():
    with open(SRC, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    games = []
    for r in rows:
        away, home = [s.strip() for s in r["matchup"].split(" at ")]
        margin = int(float(r["actual_margin"]))
        ref = float(r["reference_spread_home"])
        m1 = float(r["m1_spread_home"])
        games.append({
            "week": r["week"], "matchup": r["matchup"], "home": home, "away": away,
            "actual_margin": margin, "ref_margin": ref, "m1_margin": m1,
            "game_url": r["game_url"], "source_url": r["source_url"],
            "decided": margin != 0,
            "home_won": margin > 0,
        })

    decided = [g for g in games if g["decided"]]
    n = len(decided)

    def pick_fav(g):
        if g["ref_margin"] == 0:
            return None
        return "home" if g["ref_margin"] > 0 else "away"

    def pick_m1(g):
        if g["m1_margin"] == 0:
            return None
        return "home" if g["m1_margin"] > 0 else "away"

    def correct(g, pick):
        if pick is None:
            return None
        return (pick == "home") == g["home_won"]

    # C2 and C3 are deterministic
    for g in games:
        g["c2_pick"] = pick_fav(g)
        g["c3_pick"] = pick_m1(g)

    rng = random.Random(SEED)
    draws = []
    random_correct_per_game = {id(g): 0 for g in decided}
    for _ in range(DRAWS):
        k = 0
        for g in decided:
            pick = "home" if rng.random() < 0.5 else "away"
            if correct(g, pick):
                k += 1
                random_correct_per_game[id(g)] += 1
        draws.append(k)
    draws.sort()
    mean_random = sum(draws) / DRAWS
    lo_random = draws[int(0.025 * DRAWS)]
    hi_random = draws[int(0.975 * DRAWS) - 1]

    def summarise(control_id, name, rule, k, nn, basis, lo=None, hi=None):
        acc = k / nn if nn else None
        if lo is None:
            ci = wilson(k, nn)
            lo, hi = ci
        p = binom_two_sided_p(round(k), nn) if nn else None
        return {
            "control_id": control_id,
            "control": name,
            "rule": rule,
            "decided_games_n": nn,
            "correct": round(k, 2) if isinstance(k, float) else k,
            "accuracy": f"{acc:.3f}" if acc is not None else "",
            "ci95_low": f"{lo:.3f}" if lo is not None else "",
            "ci95_high": f"{hi:.3f}" if hi is not None else "",
            "p_vs_coin_two_sided": f"{p:.4f}" if p is not None else "",
            "basis": basis,
            "source_url": SCHEDULE_URL,
        }

    fav_k = sum(1 for g in decided if correct(g, g["c2_pick"]))
    m1_k = sum(1 for g in decided if correct(g, g["c3_pick"]))
    summary = [
        summarise("C1", "Random picks (seeded coin flip)",
                  "Each decided game: home or away with probability 0.5; seed %d; %d draws" % (SEED, DRAWS),
                  mean_random, n,
                  "Mean correct over %d draws. The ci95 columns hold the 2.5th-97.5th percentile range of the random draws (NOT a confidence interval on a model). Range %d-%d of %d."
                  % (DRAWS, lo_random, hi_random, n),
                  lo=lo_random / n, hi=hi_random / n),
        summarise("C2", "Favourite only (reference line)",
                  "Pick the team the naive reference line favours (home if reference margin > 0)",
                  fav_k, n,
                  "Reference line = season point differential + fixed 2.5-point home field; no market price used (Flag F32)."),
        summarise("C3", "Model M1 (straight-up winner)",
                  "Pick the team M1 favours (home if M1 margin > 0)",
                  m1_k, n,
                  "Same 89 games; M1 ridge attack/defence model, walk-forward."),
    ]

    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        w.writeheader()
        w.writerows(summary)

    game_fields = ["week", "matchup", "actual_margin", "c2_pick", "c2_correct", "c3_pick", "c3_correct",
                   "game_url", "source_url"]
    with open(OUT_GAMES, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=game_fields)
        w.writeheader()
        for g in games:
            if not g["decided"]:
                c2 = c3 = ""
            else:
                c2 = "" if correct(g, g["c2_pick"]) is None else ("yes" if correct(g, g["c2_pick"]) else "no")
                c3 = "" if correct(g, g["c3_pick"]) is None else ("yes" if correct(g, g["c3_pick"]) else "no")
            w.writerow({
                "week": g["week"], "matchup": g["matchup"], "actual_margin": g["actual_margin"],
                "c2_pick": (g["home"] if g["c2_pick"] == "home" else g["away"]) if g["c2_pick"] else "",
                "c2_correct": c2,
                "c3_pick": (g["home"] if g["c3_pick"] == "home" else g["away"]) if g["c3_pick"] else "",
                "c3_correct": c3,
                "game_url": g["game_url"], "source_url": g["source_url"],
            })

    print("decided games:", n, "of", len(games))
    for s in summary:
        print(s["control_id"], s["control"], s["correct"], "/", s["decided_games_n"], s["accuracy"],
              "CI", s["ci95_low"], s["ci95_high"], "p", s["p_vs_coin_two_sided"])


if __name__ == "__main__":
    main()
