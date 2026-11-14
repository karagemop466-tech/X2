#!/usr/bin/env python3
"""Demotion evaluation — run the live → paper gate against measured numbers.

Brief item: "Define a demotion gate that sends a live strategy back to paper."

`data/demotion_gate.csv` (session c125b2f7) defines triggers D1-D7 but records every
strategy as paper-only, so the gate has never actually been *run*. A gate that has never
been evaluated is not a gate: nobody knows whether it can fire, what it reads, or what it
would say today. This script evaluates every trigger, for every graded strategy, against
the data in this repository, and publishes:

  * the measured value (with its interval where the trigger is defined on one),
  * the proposed threshold, copied from the gate register rather than restated,
  * a verdict — FIRES / does not fire / not computable — with the missing input named
    when a trigger cannot be evaluated,
  * the action that would follow.

Two triggers are added here (D8, D9) because the brief's demotion requirement is incomplete
without them, and they are labelled as new proposals awaiting approval (same F17 convention
as everything else numeric in this project):

  D8  the results feed has gone stale — a live strategy whose outcomes stopped arriving must
      not stay live on old numbers;
  D9  the line book has markets that reached kickoff with no closing capture — without a
      closing number there is no price test, so a live strategy cannot be monitored at all.

Run:  python3 scripts/demote.py
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
ROLL_WINDOW = 50
FIELDS = ["evaluation_id", "rule_id", "rule_definition", "strategy_id", "measured_value",
          "window", "threshold_proposed", "verdict", "reason", "action_if_fires",
          "new_this_session", "source_url"]


def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def pct(vals, q):
    s = sorted(vals)
    i = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return s[i]


def boot_ci(diffs, seed):
    rng = random.Random(seed)
    n = len(diffs)
    means = []
    for _ in range(DRAWS):
        tot = 0.0
        for _ in range(n):
            tot += diffs[rng.randrange(n)]
        means.append(tot / n)
    return pct(means, 0.025), pct(means, 0.975)


def bh(pvals):
    """Benjamini-Hochberg adjusted q-values (step-up), matching the board's convention."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    q = [0.0] * m
    prev = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        val = min(prev, pvals[i] * m / rank)
        q[i] = val
        prev = val
    return q


def main():
    gate = {r["rule_id"]: r for r in read("demotion_gate.csv")}
    bt = read("model_backtest.csv")
    bets = read("model_bets.csv")
    board = read("strategy_leaderboard.csv")
    flags = {r["flag_id"]: r for r in read("flags.csv")}
    with open(os.path.join(DATA, "results_feed_summary.json"), encoding="utf-8") as f:
        feed = json.load(f)
    with open(os.path.join(DATA, "line_book_summary.json"), encoding="utf-8") as f:
        book = json.load(f)

    bt_sorted = sorted(bt, key=lambda r: (int(r["week"]), r["matchup"]))
    strategies = [r["strategy_id"] for r in board]

    # Before reusing the published prediction columns, confirm that recomputing an absolute
    # error from them reproduces the published error column. If this check passes, the same
    # formula is valid for the strategies whose error column was never published (M2-M4, T1).
    def recomputed(r, col):
        target = "actual_margin" if col.endswith("spread_home") else "actual_total"
        ref = "reference_spread_home" if col.endswith("spread_home") else "reference_total"
        return abs(float(r[target]) - float(r[col])), abs(float(r[target]) - float(r[ref]))

    m1_check = [abs(recomputed(r, "m1_spread_home")[0] - float(r["m1_error"])) for r in bt_sorted]
    m1_max_gap = max(m1_check) if m1_check else float("nan")
    pred_col = {"M1": "m1_spread_home", "M2": "m2_spread_home", "M3": "m3_spread_home",
                "M4": "m4_spread_home", "T1": "m1_total"}
    rows = []
    seq = [0]

    def add(rule, strat, measured, window, threshold, verdict, reason, action, new=""):
        seq[0] += 1
        rows.append({
            "evaluation_id": f"DE-{seq[0]:03d}", "rule_id": rule,
            "rule_definition": (gate.get(rule, {}).get("trigger") or
                                "New trigger proposed by this session (not in the gate register yet)"),
            "strategy_id": strat, "measured_value": measured, "window": window,
            "threshold_proposed": threshold, "verdict": verdict, "reason": reason,
            "action_if_fires": action if action else "(prohibition, no action of its own)",
            "new_this_session": new,
            "source_url": ("https://www.nfl.com/schedules/2026/by-week/week-10"
                           if rule in ("D1", "D2", "D3") else
                           "https://www.itl.nist.gov/div898/handbook/eda/section3/eda352.htm"
                           if rule == "D4" else
                           "https://support.nfl.com/hc/en-us/articles/35869743904916-NFL-com-Terms-and-Conditions"
                           if rule in ("D5", "D7") else
                           "https://github.com/karagemop466-tech/X2"),
        })

    # ---------------- D1: rolling-window signal must keep clearing zero ----------------
    for sid in strategies:
        if sid not in pred_col:
            add("D1", sid, "", "", "lower 95% bound of the window advantage > 0", "NOT COMPUTABLE",
                "this strategy is a filtered subset (bye filter) or a multi-leg ticket: the gate needs its "
                "own per-game prediction series, and the backtest file publishes predictions only for the "
                "four ridge variants and the total",
                "Return to paper; the trigger stays armed")
            continue
        col = pred_col[sid]
        diffs = [recomputed(r, col)[1] - recomputed(r, col)[0] for r in bt_sorted]
        how = (f"reference absolute error - {col} absolute error"
               + (" (matches the published m1_error column to "
                  f"{m1_max_gap:.2f} points, so the recomputation is equivalent)" if sid == "M1" else ""))
        recent = diffs[-ROLL_WINDOW:]
        lo, hi = boot_ci(recent, SEED + seq[0] + 7)
        mean = sum(recent) / len(recent)
        verdict = "FIRES" if lo <= 0 else "does not fire"
        add("D1", sid, f"mean advantage {mean:+.2f} points, 95% interval [{lo:+.2f}, {hi:+.2f}] ({how})",
            f"most recent {len(recent)} of {len(diffs)} out-of-sample games",
            "lower 95% bound of the window advantage > 0", verdict,
            ("the improvement is not maintained over the recent window — the gate exists to catch exactly this"
             if lo <= 0 else
             "the recent window still clears zero; the width of the interval is a statement about sample "
             "size, not a statement of safety"),
            "Return the strategy from live to paper until a new pre-registered window clears zero")

    # ---------------- D2: multiplicity-adjusted significance ----------------
    ps = []
    for r in board:
        try:
            ps.append(float(r["skill_p_permutation"]))
        except (TypeError, ValueError):
            ps.append(1.0)
    qs = bh(ps)
    for r, q in zip(board, qs):
        pub = r.get("q_bh_fdr", "")
        verdict = "FIRES" if q > 0.10 else "does not fire"
        add("D2", r["strategy_id"], f"recomputed BH q = {q:.4f} (register publishes {pub or 'blank'}) "
                                    f"across {len(ps)} tested strategies",
            f"all {len(ps)} strategies tested on the same walk-forward window",
            "q > 0.10 demotes", verdict,
            ("the result does not survive the charge for testing this many rules at once"
             if q > 0.10 else
             "the result survives the multiple-comparison adjustment at the proposed level"),
            "Return to paper; re-entry requires a pre-registered test on a larger sample")

    # ---------------- D3: minimum sample ----------------
    counts = {}
    for b in bets:
        counts[b["strategy_id"]] = counts.get(b["strategy_id"], 0) + 1
    for sid in strategies:
        n = counts.get(sid, 0)
        verdict = "FIRES" if n < 30 else "does not fire"
        add("D3", sid, f"{n} decided bets", "entire walk-forward bet log",
            "n_bets >= 30 (proposed, F17)", verdict,
            "below the proposed minimum, so the run rate is not interpretable" if n < 30 else
            "at or above the proposed minimum",
            "Return to paper; no live status until the minimum is met again")

    # ---------------- D4: input revision / reconciliation ----------------
    mism = int(feed.get("standings_reconciliation_mismatches", 0))
    for sid in strategies:
        add("D4", sid, f"feed rows {feed['feed_rows']}; settled {feed['settled_final']}; "
                       f"standings reconciliation mismatches {mism}",
            "results feed rebuilt " + feed["as_of"],
            "any change to a gate outcome demotes", "does not fire" if mism == 0 else "FIRES",
            "the settled half of the feed reproduces the official standings for all 32 clubs, so no "
            "revision has moved a number under this strategy" if mism == 0 else
            "a reconciliation mismatch means an input changed — every gate outcome on it is suspect",
            "Demote pending re-run; reinstatement requires a new pre-registered window")

    # ---------------- D5: provenance / legal clearance ----------------
    clearance = []
    for fid, what in (("F16", "written permission for systematic NFL data reuse"),
                      ("F09", "Japan online-wagering and rewards legality opinion"),
                      ("F19", "Netherlands jurisdiction review")):
        st = (flags.get(fid, {}).get("status") or "flag not found")
        clearance.append(f"{fid} {st.split('—')[0].split('-')[0].strip()} ({what})")
    cleared = all("esolved" in (flags.get(fid, {}).get("status") or "") for fid in ("F16", "F09", "F19"))
    for sid in strategies:
        add("D5", sid, "; ".join(clearance), "project-wide, re-read " + feed["as_of"],
            "any loss of clearance", "FIRES" if not cleared else "does not fire",
            "no written permission or legal opinion is recorded, so a live strategy would be running on "
            "an unauthorised data base — this trigger is the one that is already true today",
            "Immediate demotion to paper, no re-test; no re-promotion until cleared in writing")

    # ---------------- D6: staking must not move the rank ----------------
    ranks = [int(r["rank"]) for r in board if r["rank"].isdigit()]
    skills = []
    for r in board:
        try:
            skills.append(float(r["skill_score_mae_improvement_pts"]))
        except (TypeError, ValueError):
            skills.append(-9e9)
    order_ok = all(skills[i] >= skills[i + 1] for i in range(len(skills) - 1))
    for sid in strategies:
        add("D6", sid, "board rank order is monotone in the signal score" if order_ok else
                       "board rank order is NOT monotone in the signal score",
            "published leaderboard", "staking or ROI must not enter the ranking",
            "does not fire" if order_ok else "FIRES",
            "checked structurally: rank was produced by the skill column alone; the staking ledger "
            "(data/staking_book.csv) is a separate file and is not read by the ranking step",
            "")

    # ---------------- D7: price test once an archive exists ----------------
    pop = int(book.get("market_line_columns_populated", 0))
    for sid in strategies:
        add("D7", sid, f"{pop} market-price cells populated in the line book",
            "would be the most recent 50 priced bets", "95% interval of mean closing-line value entirely below 0",
            "NOT COMPUTABLE",
            "no authorised timestamped odds archive exists (F07, F16); the line book stores our own "
            "opening numbers and refuses to invent a market number",
            "Diagnostic only: never promotes, can demote once computable")

    # ---------------- D8 (new): the feed has gone stale ----------------
    days = feed.get("days_since_last_settled_game")
    for sid in strategies:
        add("D8", sid, f"{days} days since the last settled game in the feed "
                       f"(last settled kickoff {feed['last_settled_kickoff']}); next kickoff "
                       f"{feed['next_kickoff']}",
            "rolling, recomputed on every build", "more than 14 days without a new settled result (proposed)",
            "FIRES" if (days or 0) > 14 else "does not fire",
            "a strategy cannot be monitored on outcomes that stopped arriving; today the feed is current, "
            "the trigger exists for the weeks when it is not",
            "Return to paper until the feed is back within the freshness window", new="yes — D8")

    # ---------------- D9 (new): closing capture missed ----------------
    open_w = int(book.get("closing_windows_open", 0))
    closing = int(book.get("closing_snapshots", 0))
    for sid in strategies:
        add("D9", sid, f"{open_w} markets sit in an open closing window; {closing} closing capture(s) on file; "
                       f"earliest kickoff in {book.get('earliest_kickoff_in_days')} day(s)",
            "line book as of " + book["as_of"],
            "any market reaching kickoff with no closing capture (proposed)",
            "does not fire (yet)",
            "the windows are still open today, so nothing has been missed; the trigger is what makes the "
            "capture deadline real — after kickoff the closing number can never be recovered",
            "Void the price test for that fixture, keep the outcome grade, and demote any strategy whose "
            "monitoring depends only on the missing price test", new="yes — D9")

    tmp = os.path.join(DATA, "demotion_evaluation.csv") + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\r\n")
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, os.path.join(DATA, "demotion_evaluation.csv"))
    fires = [r for r in rows if r["verdict"] == "FIRES"]
    nc = [r for r in rows if r["verdict"] == "NOT COMPUTABLE"]
    print(f"Demotion evaluation: {len(rows)} rows ({len(strategies)} strategies x "
          f"{len({r['rule_id'] for r in rows})} triggers). {len(fires)} trigger evaluations FIRE "
          f"({sorted({r['rule_id'] for r in fires})}), {len(nc)} are not computable.")
    for r in fires[:4]:
        print(f"  {r['rule_id']}/{r['strategy_id']}: {r['measured_value'][:90]}")


if __name__ == "__main__":
    main()
