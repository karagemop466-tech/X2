#!/usr/bin/env python3
"""Publish every model total twice, with the gap, until a walk-forward comparison
says which one wins — including "neither" as a permitted answer.

The brief: "Publish every model total twice until one wins. Keep both estimators
visible with the gap column, and only collapse to one after a walk-forward comparison."

What the two estimators are, and why they are genuinely different constructions
--------------------------------------------------------------------------------
The repository already publishes one total per game (M1's ridge attack/defence total).
The failure mode this requirement guards against is *premature collapse*: choosing one
construction because it looked better in sample, then publishing only it. So the second
estimator is not a re-parameterisation of the first. It is built from a different
quantity:

  ESTIMATOR A — "structure": the published ridge attack/defence total.
      total_A = 2*mu + (A_home + A_away) - (D_home + D_away) + h*home
      It asserts that a team's scoring and conceding propensities are separable and that
      a game total is the sum of four fitted terms. No game-level information enters
      beyond the ratings.

  ESTIMATOR B — "matchup pace": a two-team, no-rating, experience-only total.
      total_B = (home team's points-for per game + home team's points-against per game
                 + away team's points-for per game + away team's points-against per game) / 2
      computed strictly from games BEFORE the reference week. This is the classic
      "these two teams' games average N points" number. It shares no fitted parameter
      with A: A shrinks toward the league mean with a ridge penalty and splits offence
      from defence; B shrinks toward nothing and cannot separate a good offence from a
      bad defence.

  ESTIMATOR C — the naive league reference total already published (a constant per week).
      Included so the comparison has a floor: an estimator that cannot beat a constant is
      not an estimator.

The three are compared on the SAME walk-forward protocol the rest of the repository uses
(train strictly before the week, predict the week, never re-fit with future games), on
absolute error against the settled total, with a paired bootstrap interval on the
difference (A - B) and a paired sign test. The decision rule is pre-registered below and
is checked before any number is looked at, in the code's order, not after.

The published Week 11 rows carry all three totals and both gap columns. Nothing is
collapsed: the collapse condition is left as a named gate whose status the evidence at
this sample size cannot satisfy.

Run:  python3 scripts/two_estimators.py
"""

import csv
import math
import os
import random
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
GAMES = os.path.join(DATA, "games_2026_results.csv")
SCHED = os.path.join(DATA, "schedule_week11_2026.csv")
WEEK11 = os.path.join(DATA, "model_lines_week11.csv")

OUT = os.path.join(DATA, "model_totals_two_estimators_week11.csv")
OUT_WF = os.path.join(DATA, "estimator_walkforward_2026.csv")
OUT_DEC = os.path.join(DATA, "estimator_collapse_decision.csv")

SEED = 20261118
BOOTSTRAP = 4000
EVAL_FROM_WEEK = 4          # same start the repository's walk-forward uses

# ---------------------------------------------------------------- pre-registration
# Written before the comparison was run. The order of the rules matters: rule 1 can
# block rules 2-4, and "neither" is reachable by rule 4.
PREREG = [
    ("E1", "The comparison window is every settled game from Week 4 onward, predicted "
           "walk-forward (fit strictly before the game's week).", "fixed before running"),
    ("E2", "The metric is mean absolute error of the total, in points. Lower is better.",
     "fixed before running"),
    ("E3", "A difference between two estimators counts only if the paired bootstrap 95% "
           "interval on (error_finalist - error_other) excludes zero.", "fixed before running"),
    ("E4", "If no estimator's interval excludes zero against the best other, the answer is "
           "'neither — keep publishing both'.", "fixed before running"),
    ("E5", "If an estimator wins but its advantage over the naive league-constant total is "
           "not itself established, the answer is 'winner not yet separable from a "
           "constant — keep publishing both'.", "fixed before running"),
]

REF_TOTAL_FALLBACK = 45.9   # the published naive constant; recomputed below, not trusted


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def sd(xs):
    n = len(xs)
    if n < 2:
        return float("nan")
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


def paired_bootstrap(diffs, iters=BOOTSTRAP, seed=SEED):
    """95% percentile interval for the MEAN paired difference."""
    if len(diffs) < 3:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(diffs)
    means = []
    for _ in range(iters):
        s = 0.0
        for _ in range(n):
            s += diffs[rng.randrange(n)]
        means.append(s / n)
    means.sort()
    lo = means[int(0.025 * iters)]
    hi = means[int(0.975 * iters) - 1]
    return (lo, hi)


def sign_test(diffs):
    """Two-sided sign test on non-zero paired differences."""
    pos = sum(1 for d in diffs if d > 1e-12)
    neg = sum(1 for d in diffs if d < -1e-12)
    n = pos + neg
    if n == 0:
        return (float("nan"), 0)
    k = min(pos, neg)
    # exact two-sided binomial p
    p_one = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return (min(1.0, 2 * p_one), n)


def main():
    games = read_csv(GAMES)
    for g in games:
        g["week"] = int(g["week"])
        g["home_points"] = int(g["home_points"])
        g["away_points"] = int(g["away_points"])
        g["total"] = g["home_points"] + g["away_points"]

    by_week = defaultdict(list)
    for g in games:
        by_week[g["week"]].append(g)

    # ---------------------------------------------------------------- estimator B
    def experience_totals(week):
        """Per-team (pf, pa, n) over games strictly before `week`. No ratings."""
        st = defaultdict(lambda: [0, 0, 0])
        for g in games:
            if g["week"] < week:
                for t, pf, pa in ((g["home_team"], g["home_points"], g["away_points"]),
                                  (g["away_team"], g["away_points"], g["home_points"])):
                    st[t][0] += pf
                    st[t][1] += pa
                    st[t][2] += 1
        return st

    def total_b_clean(week, home, away):
        """Estimator B: the mean of the two clubs' own games-total averages.

        Each club's games average ALREADY contains its opponents, so the two averages
        share the same underlying quantity and their MEAN is the matchup expectation —
        the sum would double count. No fitted parameter, no offence/defence split, no
        shrinkage: this is the "these two teams' games average N points" number, which
        is precisely the construction estimator A does not use.
        """
        st = experience_totals(week)
        vals = []
        for t in (home, away):
            pf, pa, n = st[t]
            if n == 0:
                return float("nan")
            vals.append((pf + pa) / n)
        return sum(vals) / 2.0

    # -------------------------------------------------------- load estimator A
    # data/model_lines_week11.csv holds estimator A for the prospective week; the
    # walk-forward rows for A come from data/model_backtest.csv, which is produced by
    # scripts/model.py under the identical split. Using the published file (rather than
    # re-fitting here) keeps ONE definition of estimator A in the repository.
    bt = read_csv(os.path.join(DATA, "model_backtest.csv"))
    for r in bt:
        r["week"] = int(r["week"])

    # Reference total per week, recomputed from settled games strictly before the week.
    def ref_total(week):
        st = experience_totals(week)
        lg = [v for v in st.values() if v[2]]
        if not lg:
            return REF_TOTAL_FALLBACK
        ppg = sum(v[0] for v in lg) / sum(v[2] for v in lg)
        return 2 * ppg

    # ----------------------------------------------------- walk-forward scoring
    wf = []
    for r in bt:
        wk = r["week"]
        if wk < EVAL_FROM_WEEK:
            continue
        matchup = r["matchup"]
        if " at " not in matchup:
            continue
        away, home = [s.strip() for s in matchup.split(" at ")]
        actual = float(r["actual_total"])
        a = float(r["m1_total"]) if r["m1_total"] else float("nan")
        b = total_b_clean(wk, home, away)
        c = ref_total(wk)
        if any(math.isnan(x) for x in (a, b, c)):
            continue
        wf.append({
            "week": wk, "matchup": matchup, "home": home, "away": away,
            "actual_total": actual,
            "total_A_structure": a, "total_B_experience": b, "total_C_league_constant": c,
            "err_A": abs(actual - a), "err_B": abs(actual - b), "err_C": abs(actual - c),
            "gap_A_minus_B": a - b,
            "game_url": r["game_url"], "source_url": r["source_url"],
        })

    n = len(wf)
    if n < 20:
        raise SystemExit(f"BUILD FAILED: only {n} walk-forward games; comparison is not meaningful.")

    errA = [r["err_A"] for r in wf]
    errB = [r["err_B"] for r in wf]
    errC = [r["err_C"] for r in wf]

    e = {"A": errA, "B": errB, "C": errC}
    diffs = {}
    for x, y in (("A", "B"), ("A", "C"), ("B", "C")):
        diffs[f"{x}_minus_{y}"] = [a - b for a, b in zip(e[x], e[y])]

    stats = {}
    for key, d in diffs.items():
        lo, hi = paired_bootstrap(d)
        p, nz = sign_test(d)
        st = {"mean": mean(d), "lo": lo, "hi": hi, "p": p, "n_nonzero": nz,
              "excludes_zero": (lo > 0) or (hi < 0)}
        stats[key] = st
        # mirror the comparison under its reverse name so a lookup never has to guess
        # whether the pair was stored in a particular order.
        x, y = key.split("_minus_")
        stats[f"{y}_minus_{x}"] = {"mean": -st["mean"], "lo": -hi, "hi": -lo, "p": p,
                                   "n_nonzero": nz, "excludes_zero": st["excludes_zero"],
                                   "_mirror": True}

    # --------------------------------------------------------- apply PREREG rules
    mae = {"A": mean(errA), "B": mean(errB), "C": mean(errC)}
    order = sorted(mae, key=lambda k: mae[k])       # best first
    best, second = order[0], order[1]

    key_bs = f"{best}_minus_{second}"
    s_bs = stats[key_bs]
    # Normalise so a positive mean always means "best is WORSE than second".
    best_is_worse = s_bs["mean"] > 0
    rule_fired = None
    decision = None
    detail = ""

    if best_is_worse or not s_bs["excludes_zero"]:
        rule_fired = "E4"
        decision = ("neither — keep publishing both"
                    if not s_bs["excludes_zero"] else
                    "second-best is actually better — keep publishing both")
        detail = (f"The best point estimate ({best}, MAE {mae[best]:.2f}) is separated from "
                  f"({second}, MAE {mae[second]:.2f}) by a paired difference whose 95% "
                  f"interval is {s_bs['lo']:+.2f} to {s_bs['hi']:+.2f}, which "
                  f"{'excludes' if s_bs['excludes_zero'] else 'includes'} zero.")
    else:
        # best is genuinely better than second; now it must beat the constant.
        s_bc = stats[f"{best}_minus_C"]      # mirror-safe: positive => best has larger error
        beat_const = s_bc["excludes_zero"] and s_bc["mean"] < 0
        if not beat_const:
            rule_fired = "E5"
            decision = "winner not yet separable from a constant — keep publishing both"
            detail = (f"{best} beats {second} by an established margin, but its advantage "
                      f"over the naive league-constant total is not established "
                      f"(interval {s_bc['lo']:+.2f} to {s_bc['hi']:+.2f}).")
        else:
            rule_fired = "E3"
            decision = f"{best} wins — collapse is permitted"
            detail = (f"{best} beats {second} (interval {s_bs['lo']:+.2f} to {s_bs['hi']:+.2f}) "
                      f"and beats the naive constant.")

    # ------------------------------------------------- Week 11 two-estimator table
    sched = read_csv(SCHED)
    mlines = {r["matchup"]: r for r in read_csv(WEEK11)}
    wk11 = []
    year_games_before_11 = [g for g in games if g["week"] < 11]
    # A and B for Week 11 use exactly the information available before Week 11.
    for r in sched:
        matchup = f'{r["away_team"]} at {r["home_team"]}'
        ml = mlines.get(matchup, {})
        a = float(ml["fair_total"]) if ml.get("fair_total") else float("nan")
        b = total_b_clean(11, r["home_team"], r["away_team"])
        c = ref_total(11)
        wk11.append({
            "game_no": r["game_no"], "week": 11, "matchup": matchup,
            "kickoff": f'{r["kickoff_day"]} {r["kickoff_time_et"]}',
            "total_A_structure": f"{a:.1f}" if not math.isnan(a) else "",
            "total_B_experience": f"{b:.1f}" if not math.isnan(b) else "",
            "total_C_league_constant": f"{c:.1f}",
            "gap_A_minus_B": f"{a - b:+.1f}" if not math.isnan(a) and not math.isnan(b) else "",
            "gap_A_minus_C": f"{a - c:+.1f}" if not math.isnan(a) else "",
            "collapse_status": "both published — collapse gate " + (
                "CLOSED by the pre-registered rule" if decision and "wins" in decision
                else "OPEN (no estimator has established its advantage)"),
            "decision_rule_fired": rule_fired,
            "game_url": r["game_url"], "source_url": r["source_url"],
        })

    # ------------------------------------------------------------------- write
    def write(path, rows, cols):
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for rr in rows:
                w.writerow({k: rr.get(k, "") for k in cols})

    write(OUT, wk11, list(wk11[0].keys()))

    wf_rows = []
    for r in wf:
        wf_rows.append({
            "week": r["week"], "matchup": r["matchup"], "actual_total": r["actual_total"],
            "total_A_structure": f'{r["total_A_structure"]:.1f}',
            "total_B_experience": f'{r["total_B_experience"]:.1f}',
            "total_C_league_constant": f'{r["total_C_league_constant"]:.1f}',
            "err_A": f'{r["err_A"]:.2f}', "err_B": f'{r["err_B"]:.2f}', "err_C": f'{r["err_C"]:.2f}',
            "gap_A_minus_B": f'{r["gap_A_minus_B"]:+.1f}',
            "game_url": r["game_url"], "source_url": r["source_url"],
        })
    write(OUT_WF, wf_rows, list(wf_rows[0].keys()))

    dec_rows = []
    for k, v in stats.items():
        dec_rows.append({
            "comparison": k.replace("_minus_", " minus "),
            "mean_paired_difference_pts": f'{v["mean"]:+.3f}',
            "ci95_low": f'{v["lo"]:+.3f}', "ci95_high": f'{v["hi"]:+.3f}',
            "interval_excludes_zero": "yes" if v["excludes_zero"] else "no",
            "sign_test_p": f'{v["p"]:.4f}', "n_nonzero_pairs": v["n_nonzero"],
            "reading": ("A positive value means the FIRST estimator has the LARGER error "
                        "(is worse)."),
            "n_games": n, "source_url": "https://www.nfl.com/schedules/2026/by-week/week-11",
        })
    write(OUT_DEC, dec_rows, list(dec_rows[0].keys()))

    print(f"two_estimators: {n} walk-forward games; MAE A={mae['A']:.2f} B={mae['B']:.2f} "
          f"C={mae['C']:.2f}; rule {rule_fired}; decision: {decision}")
    for k, v in stats.items():
        print(f"  {k}: {v['mean']:+.3f} [{v['lo']:+.3f}, {v['hi']:+.3f}] "
              f"p={v['p']:.4f} excludes_zero={v['excludes_zero']}")


if __name__ == "__main__":
    main()
