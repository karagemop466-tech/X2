#!/usr/bin/env python3
"""Origination contract: the side first, then the total, then a moneyline derived from them.

Brief items: "Originate the side first, then the total, then the moneyline" and
"Publish the model's fair line, the market line, and the difference as separate columns."

What this adds over the existing line file
------------------------------------------
`data/model_lines_week11.csv` publishes all three numbers side by side, which makes the
order look like a presentation choice. It is not one, and the difference matters:

  * stage 1 (side) and stage 2 (total) are produced by the same fitted ratings system,
    so they are two READINGS of one model, not two independent forecasts. This script
    says so out loud instead of letting the column order imply independence — and that
    sharing is precisely why same-game legs are correlated (see the correlation register).
  * stage 3 (moneyline) is DERIVED from stage 1 through the fitted residual spread. If
    the published win probability does not reproduce from the published side line, the
    three numbers are not one book and the game's publication is marked inconsistent.

Every market row carries three separate columns: `model_fair_line` (ours),
`market_line` (the price a book offered — blank, no authorised archive: F07/F16) and
`fair_minus_market` (the difference — therefore blank too). A fourth column,
`fair_minus_reference`, is populated because the reference line IS a project number and
the difference between two project numbers is computable. The reference line is not a
market price and is never described as one (F32).

Run:  python3 scripts/originate.py
"""
import csv
import datetime as dt
import json
import math
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
AS_OF = "2026-11-14"
MONTHS = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
          "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
          "december": 12}
NO_PRICE = "blank — no authorised odds archive (F07, F16)"
OUT_FIELDS = ["row_id", "week", "game_key", "kickoff_local_date", "market_seq", "market_name",
              "model_fair_line", "market_line", "fair_minus_market", "reference_line",
              "fair_minus_reference", "derivation", "inputs_used", "fit_window",
              "consistency_check", "status", "source_url"]


def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def verdict_of(sum_gap, tot_gap, prob_gap):
    if abs(sum_gap) <= 0.105 and abs(tot_gap) <= 0.105 and abs(prob_gap) <= 0.01:
        return "consistent within the rounding tolerance on all three checks"
    return "review — a gap exceeds the rounding tolerance (the number is not published until cleared)"


def norm_cdf(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def iso(text):
    m = re.search(r"(January|February|March|April|May|June|July|August|September|October|"
                  r"November|December)\s+(\d{1,2})", text or "")
    if not m:
        return ""
    return dt.date(2026, MONTHS[m.group(1).lower()], int(m.group(2))).isoformat()


def main():
    lines = read("model_lines_week11.csv")
    sched = {s["game_no"]: s for s in read("schedule_week11_2026.csv")}
    with open(os.path.join(DATA, "model_summary.json"), encoding="utf-8") as f:
        ms = json.load(f)
    sd = float(ms["sd_margin_residual"])
    rows, audit = [], []
    for g in lines:
        no = int(g["game_no"])
        away, home = [t.strip() for t in g["matchup"].split(" at ")]
        game_key = f"W11-{no:02d} {away} at {home}"
        kdate = iso(g.get("kickoff_et", "") or sched.get(str(no), {}).get("kickoff_day", ""))
        margin = float(g["model_spread_home"])
        total = float(g["model_total"])
        hp, ap = float(g["model_home_points"]), float(g["model_away_points"])
        pub_p = float(g["home_win_prob"])
        ref_margin = float(g["reference_spread_home"])
        ref_total = float(g["reference_total"])
        fit = f"ratings fitted on {ms['games_transcribed']} settled games, " \
              f"weeks {min(ms['weeks'])}-{max(ms['weeks'])} (Thursday) only — see F36"
        # ---- stage 1: side
        rows.append({
            "row_id": f"OR-{no:02d}-1", "week": "11", "game_key": game_key,
            "kickoff_local_date": kdate, "market_seq": 1, "market_name": "Side (home margin, points)",
            "model_fair_line": f"{margin:+.2f}", "market_line": "", "fair_minus_market": "",
            "reference_line": f"{ref_margin:+.2f}", "fair_minus_reference": f"{margin - ref_margin:+.2f}",
            "derivation": "estimated directly: home attack+defence rating minus away attack+defence "
                          "rating, plus the fitted home term",
            "inputs_used": "settled 2026 scores only (ridge attack/defence system)",
            "fit_window": fit, "consistency_check": "", "status": NO_PRICE,
            "source_url": g["game_url"],
        })
        # ---- stage 2: total
        rows.append({
            "row_id": f"OR-{no:02d}-2", "week": "11", "game_key": game_key,
            "kickoff_local_date": kdate, "market_seq": 2, "market_name": "Total (combined points)",
            "model_fair_line": f"{total:.2f}", "market_line": "", "fair_minus_market": "",
            "reference_line": f"{ref_total:.2f}", "fair_minus_reference": f"{total - ref_total:+.2f}",
            "derivation": "estimated from the SAME fitted system, not from the side line: "
                          "2*mu + attack(home)+attack(away) - defence(home) - defence(away) + home term",
            "inputs_used": "settled 2026 scores only (same system as stage 1 — not an independent forecast)",
            "fit_window": fit, "consistency_check": "", "status": NO_PRICE,
            "source_url": g["game_url"],
        })
        # ---- stage 3: moneyline, derived
        derived_p = norm_cdf(margin / sd)
        gap = derived_p - pub_p
        verdict = ("consistent" if abs(gap) <= 0.01 else "INCONSISTENT — the published probability "
                   "does not reproduce from the published side line")
        rows.append({
            "row_id": f"OR-{no:02d}-3", "week": "11", "game_key": game_key,
            "kickoff_local_date": kdate, "market_seq": 3, "market_name": "Moneyline (home win probability)",
            "model_fair_line": f"{pub_p:.3f}", "market_line": "", "fair_minus_market": "",
            "reference_line": f"{norm_cdf(ref_margin / sd):.3f}",
            "fair_minus_reference": f"{pub_p - norm_cdf(ref_margin / sd):+.3f}",
            "derivation": f"DERIVED from stage 1, not separately fitted: norm_cdf(margin / residual SD) "
                          f"= norm_cdf({margin:+.2f} / {sd:.2f}) = {derived_p:.3f}",
            "inputs_used": "stage-1 side line and the published residual spread; the total is not used",
            "fit_window": fit, "consistency_check": f"{verdict} (gap {gap:+.3f})",
            "status": NO_PRICE + "; tie probability is not modelled (1 tie in the 2026 ledger)",
            "source_url": g["game_url"],
        })
        # ---- internal consistency of the published triple
        sum_gap = (hp - ap) - margin
        tot_gap = (hp + ap) - total
        audit.append({
            "game_key": game_key, "week": "11",
            "score_grid_reconstructs_margin": f"{hp:.1f} - {ap:.1f} = {hp - ap:.1f} vs published "
                                               f"margin {margin:+.2f} (gap {sum_gap:+.2f})",
            "score_grid_reconstructs_total": f"{hp:.1f} + {ap:.1f} = {hp + ap:.1f} vs published "
                                              f"total {total:.2f} (gap {tot_gap:+.2f})",
            "moneyline_reproduces_from_side": f"published {pub_p:.3f} vs derived {derived_p:.3f} "
                                               f"(gap {gap:+.3f})",
            "verdict": verdict_of(sum_gap, tot_gap, gap),
            "tolerance_applied": "score grid 0.105 (each published score is rounded to 0.1, so a "
                                 "difference or a sum can move by at most 0.1); probability 0.01",
            "source_url": g["game_url"],
        })
    tmp = os.path.join(DATA, "originated_markets_week11.csv") + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUT_FIELDS, lineterminator="\r\n")
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, os.path.join(DATA, "originated_markets_week11.csv"))
    af = ["game_key", "week", "score_grid_reconstructs_margin", "score_grid_reconstructs_total",
          "moneyline_reproduces_from_side", "tolerance_applied", "verdict", "source_url"]
    tmp2 = os.path.join(DATA, "origination_audit.csv") + ".tmp"
    with open(tmp2, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=af, lineterminator="\r\n")
        w.writeheader()
        w.writerows(audit)
    os.replace(tmp2, os.path.join(DATA, "origination_audit.csv"))

    contract = [
        {"stage": "1", "market": "Side (home margin)",
         "must_be_produced_from": "the fitted attack/defence ratings and the home term only",
         "must_not_use": "the total, the moneyline, any market price",
         "published_columns": "model_fair_line / market_line / fair_minus_market",
         "if_a_market_line_is_missing": "publish the fair line and leave the difference blank — never infer a price",
         "blocking_condition": "no settled results feed, or a ratings fit that used the game being predicted",
         "source_url": "https://www.nfl.com/schedules/2026/by-week/week-11"},
        {"stage": "2", "market": "Total (combined points)",
         "must_be_produced_from": "the same fitted system, but as a separate reading (2*mu + attacks - defences + home)",
         "must_not_use": "the side line; the two are not independent and are not claimed to be",
         "published_columns": "model_fair_line / market_line / fair_minus_market",
         "if_a_market_line_is_missing": "as stage 1",
         "blocking_condition": "any parlay or combo priced as if side and total were independent draws",
         "source_url": "https://www.itl.nist.gov/div898/handbook/glossary.htm"},
        {"stage": "3", "market": "Moneyline (win probability)",
         "must_be_produced_from": "stage 1 only: norm_cdf(side / residual spread)",
         "must_not_use": "a separately fitted probability, and never a market price back-out",
         "published_columns": "model_fair_line / market_line / fair_minus_market",
         "if_a_market_line_is_missing": "as stage 1",
         "blocking_condition": "the derived probability differs from the published one by more than 0.01, "
                               "or the score grid fails to reproduce the margin or the total",
         "source_url": "https://www.itl.nist.gov/div898/handbook/eda/section3/eda352.htm"},
    ]
    cf = ["stage", "market", "must_be_produced_from", "must_not_use", "published_columns",
          "if_a_market_line_is_missing", "blocking_condition", "source_url"]
    tmp3 = os.path.join(DATA, "origination_contract.csv") + ".tmp"
    with open(tmp3, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cf, lineterminator="\r\n")
        w.writeheader()
        w.writerows(contract)
    os.replace(tmp3, os.path.join(DATA, "origination_contract.csv"))

    bad = [a for a in audit if not a["verdict"].startswith("consistent")]
    print(f"Originated {len(rows)} market rows ({len(lines)} games x 3 stages) in publication order; "
          f"{len(lines) - len(bad)} games pass all three internal consistency checks, {len(bad)} do not.")
    for a in bad:
        print("  review:", a["game_key"], "-", a["verdict"])
    return rows, audit


if __name__ == "__main__":
    main()
