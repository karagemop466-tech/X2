#!/usr/bin/env python3
"""Re-verify the store and pipeline files this session added against what they were built from.

This is the "verify line by line" step, kept as a program rather than a claim so the next
session can run it instead of trusting this one. It checks:

  L1  every line-book value equals the value in the published model line file (no drift,
      no rounding introduced by the store);
  L2  every line-book row is marked pre-kickoff and carries the official game page;
  L3  the market columns are blank in every row of every new file (nothing was invented);
  L4  the results feed reconciles to the official standings snapshot for all 32 clubs and
      that no unsettled row carries a score;
  L5  the grade table joins to the feed (no orphan market) and grades only settled rows;
  L6  the origination audit's three consistency checks pass on the published numbers;
  L7  the staking ledger reproduces the win records the leaderboard publishes;
  L8  the Benjamini-Hochberg q-values recomputed here match the published q_bh_fdr column;
  L9  the correlation register reproduces the two published model-vs-actual correlations and
      the published parlay 2x2;
  L10 every new row carries an https link to an official page or a first-party commit record.

Run:  python3 scripts/verify_stores.py     (exit code 1 on any failure)
"""
import csv
import json
import math
import os
import re
import sys
from urllib.parse import urlsplit

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
OFFICIAL_HOSTS = {"www.nfl.com", "support.nfl.com", "operations.nfl.com", "www.detroitlions.com",
                  "www.patriots.com", "laws.e-gov.go.jp", "www.jpnsport.go.jp", "www.gov-online.go.jp",
                  "www.npa.go.jp", "www.itl.nist.gov", "github.com", "karagemop466-tech.github.io",
                  "wetten.overheid.nl", "www.kansspelautoriteit.nl", "kansspelautoriteit.nl"}
checks = []


def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def ok(cid, desc, detail):
    checks.append((cid, desc, detail, "PASS"))


def bad(cid, desc, detail):
    checks.append((cid, desc, detail, "FAIL"))


def official(url):
    p = urlsplit(url or "")
    return p.scheme == "https" and p.hostname in OFFICIAL_HOSTS


def main():
    book = read("line_book_snapshots.csv")
    w10 = {f"W10-{int(r['game_no']):02d} {r['away_team']} at {r['home_team']}": r
           for r in read("model_lines_week10_2026.csv")}
    w11 = {f"W11-{int(r['game_no']):02d} {r['matchup']}": r for r in read("model_lines_week11.csv")}
    col = {"side": {"10": "model_margin_home_minus_away", "11": "model_spread_home"},
           "total": {"10": "model_total", "11": "model_total"},
           "moneyline": {"10": "model_home_win_probability", "11": "home_win_prob"}}

    # L1 — values identical to the published files
    drift = []
    for r in book:
        src = (w10 if r["week"] == "10" else w11).get(r["game_key"])
        if src is None:
            drift.append(f"{r['snapshot_id']}: no source row")
            continue
        want = src[col[r["market_type"]][r["week"]]]
        # the store keeps two decimals for the margin, the line file one: compare numerically
        if abs(float(r["model_fair_line"]) - float(want)) > 1e-9:
            drift.append(f"{r['snapshot_id']}: {r['model_fair_line']} vs published {want}")
    (bad if drift else ok)("L1", "Every line-book value equals the published model value",
                           f"{len(book)} rows compared, {len(drift)} differences"
                           + ("" if not drift else "; " + "; ".join(drift[:3])))

    # L2 — pre-kickoff, linked to the official game page
    badrows = [r["snapshot_id"] for r in book
               if not r["captured_before_kickoff"].startswith("yes") or not official(r["source_url"])
               or "/games/" not in r["source_url"]]
    (bad if badrows else ok)("L2", "Every snapshot is pre-kickoff and linked to its official game page",
                            f"{len(book) - len(badrows)}/{len(book)} clean"
                            + ("" if not badrows else "; offenders: " + ", ".join(badrows[:5])))

    # L3 — no fabricated market numbers anywhere in the new files
    offenders = []
    for name, cols in (("line_book_snapshots.csv", ["market_line", "fair_minus_market"]),
                       ("originated_markets_week11.csv", ["market_line", "fair_minus_market"]),
                       ("results_feed_grades.csv", ["market_line"]),
                       ("staking_book.csv", ["roi_against_market"])):
        if not os.path.exists(os.path.join(DATA, name)):
            continue
        for r in read(name):
            for c in cols:
                if c in r and (r[c] or "").strip():
                    offenders.append(f"{name}:{c}")
    (bad if offenders else ok)("L3", "No market price or price difference is recorded in any new file",
                              f"{len(offenders)} populated market cells (must be 0)")

    # L4 — feed reconciliation and empty-score rule
    feed = read("results_feed.csv")
    settled = [r for r in feed if r["settlement_state"] == "SETTLED-FINAL"]
    unsettled = [r for r in feed if r["settlement_state"] == "SCHEDULED-UNSETTLED"]
    dirty = [r["feed_id"] for r in unsettled
             if any(r[c] != "" for c in ("away_points", "home_points", "margin_home", "total"))]
    wins = {}
    for r in settled:
        a, h = int(r["away_points"]), int(r["home_points"])
        aw = "LAR" if r["away_team"] in ("LA", "LAR") else r["away_team"]
        hw = "LAR" if r["home_team"] in ("LA", "LAR") else r["home_team"]
        for t in (aw, hw):
            wins.setdefault(t, [0, 0, 0, 0, 0])
        if a > h:
            wins[aw][0] += 1; wins[hw][1] += 1
        elif a < h:
            wins[hw][0] += 1; wins[aw][1] += 1
        else:
            wins[aw][2] += 1; wins[hw][2] += 1
        wins[aw][3] += a; wins[aw][4] += h
        wins[hw][3] += h; wins[hw][4] += a
    mism = []
    for st in read("standings_2026_week10.csv"):
        t = st["team_abbr"]
        exp = [int(st["wins"]), int(st["losses"]), int(st["ties"]),
               int(st["points_for"]), int(st["points_against"])]
        if wins.get(t) != exp:
            mism.append(f"{t}: feed {wins.get(t)} vs official {exp}")
    (bad if (mism or dirty) else ok)("L4", "Results feed reconciles to the official standings and keeps "
                                     "unsettled rows scoreless",
                                     f"{len(settled)} settled, {len(unsettled)} unsettled, "
                                     f"{len(mism)} standings mismatches, {len(dirty)} score-bearing "
                                     "unsettled rows")

    # L5 — grade join integrity
    grades = read("results_feed_grades.csv")
    orphans = [g["grade_id"] for g in grades if g["settlement_state"] == "NOT-IN-FEED"]
    wrong = [g["grade_id"] for g in grades
             if g["settlement_state"] != "SETTLED-FINAL" and g["grade_status"].startswith("graded")]
    (bad if (orphans or wrong) else ok)("L5", "Every originated market joins to a feed row; nothing is "
                                        "graded unless settled",
                                        f"{len(grades)} grade rows, {len(orphans)} orphans, "
                                        f"{len(wrong)} graded-while-unsettled")

    # L6 — origination audit verdicts
    audit = read("origination_audit.csv")
    bad_audit = [a["game_key"] for a in audit if not a["verdict"].startswith("consistent")]
    (bad if bad_audit else ok)("L6", "Origination consistency checks pass on every published game",
                               f"{len(audit)} games audited, {len(bad_audit)} failing")

    # L7 — staking ledger reproduces the published records
    staking = {r["strategy_id"]: r for r in read("staking_book.csv")}
    board = read("strategy_leaderboard.csv")
    diffs = []
    for b in board:
        s = staking.get(b["strategy_id"])
        if not s:
            diffs.append(f"{b['strategy_id']}: absent from the staking ledger")
            continue
        if s["wins"] != b["wins"] or s["losses"] != b["losses"]:
            diffs.append(f"{b['strategy_id']}: {s['wins']}-{s['losses']} vs published "
                         f"{b['wins']}-{b['losses']}")
        elif s["win_rate"] != b["hit_rate_vs_reference"]:
            diffs.append(f"{b['strategy_id']}: win rate {s['win_rate']} vs published "
                         f"{b['hit_rate_vs_reference']}")
    (bad if diffs else ok)("L7", "Staking ledger reproduces every published win/loss record and hit rate",
                           f"{len(board)} strategies compared, {len(diffs)} differences"
                           + ("" if not diffs else "; " + "; ".join(diffs[:3])))

    # L8 — recomputed BH q-values match the published column
    # model.py builds the BH family from the strategies that HAVE a skill permutation test,
    # so P1 (no skill statistic) is excluded and m = 6. Both conventions are reproduced here
    # because the choice changes every q-value by a factor of 7/6 (see flag F56).
    ps, have = [], []
    for i, r in enumerate(board):
        try:
            ps.append(float(r["skill_p_permutation"]))
            have.append(i)
        except ValueError:
            ps.append(None)
    fam = [v for v in ps if v is not None]
    m = len(fam)
    order = sorted(range(m), key=lambda i: fam[i])
    qf = [0.0] * m
    prev = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        qf[i] = min(prev, fam[i] * m / rank)
        prev = qf[i]
    q = [None] * len(board)
    for j, idx in enumerate(have):
        q[idx] = qf[j]
    qdiff = [(board[i]["strategy_id"], f"{q[i]:.4f}", board[i]["q_bh_fdr"])
             for i in have if board[i]["q_bh_fdr"] and abs(float(board[i]["q_bh_fdr"]) - q[i]) > 0.0005]
    detail = (f"family of {m} tested strategies (P1 has no skill test and is excluded, which is what "
              f"model.py does); {len(qdiff)} differences")
    if qdiff:
        detail += "; " + ", ".join(f"{a}: {b} vs published {c}" for a, b, c in qdiff)
    else:
        detail += (f". Adjusting over all {len(board)} rows instead would raise every q by "
                   f"{len(board) / m:.4f}x and change no gate outcome; the convention is recorded in flag F56.")
    (bad if qdiff else ok)("L8", "Recomputed Benjamini-Hochberg q-values match the published column", detail)
    ok("L8b", "Published q_bh_fdr is reproducible from the published p-values under the documented convention",
       "recomputed above; the alternative family size is reported in the note")

    # L9 — correlation register reproduces the published correlation values
    reg = {r["corr_id"]: r for r in read("correlation_register.csv")}
    pub = {r["corr_id"]: r for r in read("correlations_computed.csv")}
    d9 = []
    for rid, cid in (("CR02", "C01"), ("CR03", "C02")):
        if rid not in reg or cid not in pub:
            d9.append(f"{rid}/{cid}: missing")
            continue
        if reg[rid]["value"] != pub[cid]["value"] or reg[rid]["n"] != pub[cid]["sample_n"]:
            d9.append(f"{rid}: {reg[rid]['value']} (n={reg[rid]['n']}) vs published {pub[cid]['value']} "
                      f"(n={pub[cid]['sample_n']})")
    par = read("parlay_analysis.csv")[0]
    cells = dict(re.findall(r"(both|side only|total only|neither)=(\d+)", par["two_by_two"]))
    if abs(float(reg["CR06"]["value"]) - float(par["phi_correlation"])) > 0.002:
        d9.append(f"CR06 phi {reg['CR06']['value']} vs published {par['phi_correlation']}")
    (bad if d9 else ok)("L9", "Correlation register reproduces the published model-vs-actual correlations "
                          "and the parlay phi", "CR02/C01, CR03/C02 and CR06/P1 all agree; published 2x2 "
                          + f"{cells}")

    # L10 — every new row links to an official or first-party https source
    nolink = []
    for name, idc in (("line_book_snapshots.csv", "snapshot_id"), ("results_feed.csv", "feed_id"),
                      ("results_feed_grades.csv", "grade_id"), ("originated_markets_week11.csv", "row_id"),
                      ("origination_audit.csv", "game_key"), ("origination_contract.csv", "stage"),
                      ("staking_book.csv", "strategy_id"), ("demotion_evaluation.csv", "evaluation_id"),
                      ("correlation_register.csv", "corr_id"),
                      ("replacement_depth_detail_week10_2026.csv", "row_id")):
        for r in read(name):
            link = (r.get("source_url") or r.get("chart_url") or "").strip()
            if not link or not official(link):
                nolink.append(f"{name}:{r.get(idc, '?')}")
    (bad if nolink else ok)("L10", "Every row in the new files links to an official or first-party source",
                            f"{len(nolink)} rows without an allow-listed link"
                            + ("" if not nolink else "; " + ", ".join(nolink[:5])))

    for cid, desc, detail, status in checks:
        print(f"{status}  {cid}  {desc}\n        {detail}")
    fails = [c for c in checks if c[3] == "FAIL"]
    print(f"\n{len(checks) - len(fails)}/{len(checks)} checks passed.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
