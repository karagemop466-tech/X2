#!/usr/bin/env python3
"""Staking ledger — the staking half of the leaderboard, kept away from the ranking.

Brief item: "Separate 'signal' from 'staking' in the leaderboard so a lucky staking run
cannot mask a bad signal."

`data/strategy_signal_staking.csv` (session c125b2f7) defines the split; its staking
columns are deliberately empty because no price exists. This script fills the staking
half with what CAN be computed from verified data, and states exactly what it is:

  * every bet in `data/model_bets.csv` is graded against the project's naive REFERENCE
    line at a DECLARED flat payout of 1 unit won / 1 unit lost. It is not a sportsbook
    return: there is no price in this project (F07), and a win here is not a win against
    a bookmaker (F32). The payout assumption is printed in every row, not in a footnote.
  * signal metrics come from the graded forecast series and are the ONLY thing that
    produces a rank.
  * staking metrics (units, drawdown, streaks, run probability) are reported beside the
    rank and cannot move it. The divergence between the two orders is published as a
    canary, and the size of a typical lucky run is quantified so "+36-14" can be read
    against what chance alone produces across seven strategies.

Run:  python3 scripts/staking_book.py
"""
import csv
import json
import math
import os
import random
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
SEED = 20261114
DRAWS = 5000
PAYOUT = "flat 1 unit won / 1 unit lost, graded against the project reference line (not a market price)"
FIELDS = ["strategy_id", "strategy", "market", "n_bets", "wins", "losses", "push", "win_rate",
          "se_win_rate", "binom_p_one_sided_vs_coin", "units_even_money", "roi_units_pct",
          "units_boot_ci_low", "units_boot_ci_high", "max_drawdown_units", "longest_win_streak",
          "longest_loss_streak", "mean_edge_points", "bet_coverage_of_eligible_games",
          "signal_rank", "signal_skill_points", "signal_ci_low", "signal_ci_high", "signal_q_bh",
          "staking_rank_by_units", "rank_divergence", "canary", "interpretation",
          "payout_assumption", "source_url"]


def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def one_sided_binom(wins, n):
    """P(X >= wins) for X ~ Binomial(n, 0.5), computed exactly."""
    if wins <= 0:
        return 1.0
    tot = 0
    for k in range(wins, n + 1):
        tot += math.comb(n, k)
    return tot / (2.0 ** n)


def pct(sorted_vals, q):
    if not sorted_vals:
        return float("nan")
    i = min(len(sorted_vals) - 1, max(0, int(round(q * (len(sorted_vals) - 1)))))
    return sorted_vals[i]


def main():
    bets = read("model_bets.csv")
    board = {r["strategy_id"]: r for r in read("strategy_leaderboard.csv")}
    bt = read("model_backtest.csv")
    eligible_by_week = {}
    for r in bt:
        eligible_by_week[r["week"]] = eligible_by_week.get(r["week"], 0) + 1
    total_eligible = len(bt)

    by_strat = {}
    for b in bets:
        by_strat.setdefault(b["strategy_id"], []).append(b)

    rows = []
    units_by_strat = {}
    for idx, (sid, bs) in enumerate(sorted(by_strat.items())):
        outcomes = [1 if b["result"] == "win" else (-1 if b["result"] == "loss" else 0) for b in bs]
        wins = sum(1 for o in outcomes if o == 1)
        losses = sum(1 for o in outcomes if o == -1)
        push = sum(1 for o in outcomes if o == 0)
        n = len(outcomes)
        wr = wins / n if n else 0.0
        se = math.sqrt(wr * (1 - wr) / n) if n else float("nan")
        units = sum(outcomes)
        units_by_strat[sid] = units
        rng = random.Random(SEED + 101 * idx)   # deterministic: never seed from hash(), which is salted per process
        boots = []
        for _ in range(DRAWS):
            s = 0
            for _ in range(n):
                s += outcomes[rng.randrange(n)]
            boots.append(s)
        boots.sort()
        run = max_run = 0
        loss_run = max_loss_run = 0
        for o in outcomes:
            run = run + 1 if o == 1 else 0
            max_run = max(max_run, run)
            loss_run = loss_run + 1 if o == -1 else 0
            max_loss_run = max(max_loss_run, loss_run)
        eq = peak = 0
        dd = 0
        for o in outcomes:
            eq += o
            peak = max(peak, eq)
            dd = min(dd, eq - peak)
        edges = [float(b["edge_points"]) for b in bs if b["edge_points"] not in ("", None)]
        mean_edge = sum(edges) / len(edges) if edges else float("nan")
        sig = board.get(sid, {})
        rows.append({
            "strategy_id": sid, "strategy": sig.get("strategy", ""), "market": sig.get("market", ""),
            "n_bets": n, "wins": wins, "losses": losses, "push": push,
            "win_rate": f"{wr:.3f}", "se_win_rate": f"{se:.3f}",
            "binom_p_one_sided_vs_coin": f"{one_sided_binom(wins, n):.5f}",
            "units_even_money": f"{units:+d}", "roi_units_pct": f"{100.0 * units / n:+.1f}%",
            "units_boot_ci_low": f"{pct(boots, 0.025):+d}", "units_boot_ci_high": f"{pct(boots, 0.975):+d}",
            "max_drawdown_units": f"{dd:+d}", "longest_win_streak": max_run,
            "longest_loss_streak": max_loss_run,
            "mean_edge_points": f"{mean_edge:.2f}" if edges else "",
            "bet_coverage_of_eligible_games": f"{n}/{total_eligible} = {n / total_eligible:.2f}",
            "signal_rank": sig.get("rank", ""), "signal_skill_points": sig.get("skill_score_mae_improvement_pts", ""),
            "signal_ci_low": sig.get("skill_ci_low", ""), "signal_ci_high": sig.get("skill_ci_high", ""),
            "signal_q_bh": sig.get("q_bh_fdr", ""),
            "staking_rank_by_units": "", "rank_divergence": "", "canary": "",
            "interpretation": "", "payout_assumption": PAYOUT,
            "source_url": bs[0]["source_url"],
        })
    # staking order is computed for display only, then compared against the signal order
    for i, r in enumerate(sorted(rows, key=lambda x: int(x["units_even_money"]), reverse=True), start=1):
        r["staking_rank_by_units"] = str(i)
    for r in rows:
        try:
            div = int(r["signal_rank"]) - int(r["staking_rank_by_units"])
        except ValueError:
            div = 0
        r["rank_divergence"] = f"{div:+d}"
        r["canary"] = ("WATCH — one slot of divergence (staking did better or worse than the signal "
                       "rank); the split is working, no action" if abs(div) == 1 else
                       "OK — staking order matches the signal order" if div == 0 else
                       f"DIVERGENT — staking places this strategy {abs(div)} slot(s) away from its signal "
                       "rank; the signal rank stands and the divergence is the thing to investigate")
        q = float(r["signal_q_bh"]) if r["signal_q_bh"] else None
        if q is None:
            r["interpretation"] = "No signal measurement on the board — staking numbers cannot substitute for one."
        elif q <= 0.10:
            r["interpretation"] = (f"Signal clears the proposed FDR cut-off (q={q:.4f}); the staking run "
                                   f"({r['units_even_money']} units over {r['n_bets']} bets) is reported but did not "
                                   "affect the rank.")
        else:
            r["interpretation"] = (f"Signal does NOT clear the proposed FDR cut-off (q={q}); "
                                   f"{'the positive staking run is inside the range chance produces and must not be read as skill' if int(r['units_even_money']) > 0 else 'nothing here supports the strategy'}.")
    rows.sort(key=lambda r: int(r["signal_rank"]) if r["signal_rank"].isdigit() else 99)

    # How large is a lucky run, across this many strategies, on these sample sizes?
    rng = random.Random(SEED)
    ns = [int(r["n_bets"]) for r in rows]
    best = []
    for _ in range(DRAWS):
        best.append(max((2 * rng.getrandbits(n).bit_count() - n) for n in ns))
    best.sort()
    observed_best = max(int(r["units_even_money"]) for r in rows)
    p_at_least = sum(1 for b in best if b >= observed_best) / DRAWS
    canary = {
        "seed": SEED, "draws": DRAWS,
        "strategies_in_the_family": len(rows),
        "expected_best_units_with_no_skill_mean": round(sum(best) / DRAWS, 2),
        "expected_best_units_with_no_skill_p95": pct(best, 0.95),
        "observed_best_units": observed_best,
        "probability_some_strategy_reaches_that_run_by_chance_alone": round(p_at_least, 4),
        "reading": ("A best-of-family run this large is routine under no skill, so the run alone cannot "
                    "establish a strategy; the signal gates must carry the decision."
                    if p_at_least > 0.05 else
                    "A best-of-family run this large is uncommon under no skill, but the signal gates — "
                    "not the run — still decide promotion."),
        "payout_assumption": PAYOUT,
        "note": "Simulated by resampling each strategy's own bet count as coin flips; the strategies "
                "share games, so the true spread of lucky runs is somewhat wider than this independence "
                "assumption implies (recorded, not hidden).",
    }
    tmp = os.path.join(DATA, "staking_book.csv") + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\r\n")
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, os.path.join(DATA, "staking_book.csv"))
    with open(os.path.join(DATA, "staking_canary.json"), "w", encoding="utf-8") as f:
        json.dump(canary, f, indent=1)
        f.write("\n")
    print(f"Staking ledger: {len(rows)} strategies; best observed run {observed_best:+d} units; "
          f"chance alone produces a best-of-{len(rows)} run of at least that in "
          f"{100 * p_at_least:.1f}% of simulations (p95 = {pct(best, 0.95):+d} units).")
    for r in rows:
        print(f"  {r['strategy_id']}: signal rank {r['signal_rank']} | staking {r['units_even_money']} units "
              f"({r['wins']}-{r['losses']}) | {r['canary'][:60]}")


if __name__ == "__main__":
    main()
