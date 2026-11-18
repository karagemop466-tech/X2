#!/usr/bin/env python3
"""The 102-game pre-registered corpus: the published 89 plus the 13 settled Week 10 games.

Why this exists (T108, closing P09 for the corpus half).

The published walk-forward corpus in data/model_backtest.csv holds 89 games,
weeks 4-10, and the Week 10 part of it is a single game (the Thursday opener).
Thirteen Week 10 games have since been played and were transcribed from the
official by-week page into data/games_week10_backfill_2026.csv by session
cf85d485, where they reconcile 32 of 32 clubs against the official standings
(flag F105). They were deliberately NOT spliced into the published feed,
because splicing re-fits the ratings and therefore re-originates the Week 11
lines that are already frozen and SHA-256 sealed in
data/prospective_forecast_log.csv - a sealed pre-kickoff record cannot be
re-sealed after the fact without destroying what it proves (flag S-02 below).

This script takes the other route the same decision allows: it builds a
SECOND, separately named corpus and publishes both, so the two estimators stay
visible side by side (the brief's "publish every model total twice until one
wins"). Nothing in the published 89-game register is modified. Nothing sealed
is re-sealed.

The reproduction contract, inherited from scripts/forecast_records.py:
  * The model construction is imported from that script, not re-typed, so the
    two cannot drift apart.
  * Every one of the 89 published rows must be reproduced within 0.055 points
    (the published one-decimal rounding). If not, the run fails.
  * The 13 new rows are produced the same way: fit on games strictly before
    the game's week, predict, compare with the official final score.

Honest finding, stated up front because it changes how the numbers may be used:
on the 13 newly settled games the model does WORSE than its own naive
reference line (mean absolute error 10.069 vs 9.692 points per game, a gain of
-0.377). The published 89-game corpus shows +1.75. That is the whole reason the
brief asks for a holdout instead of a single number, and it is published rather
than buried: see data/corpus_v2_summary.csv and flag F110.

Outputs:
  data/corpus_v2_2026.csv         102 rows: 89 reproduced + 13 new, with the
                                  probability, the reference line it is scored
                                  against, the errors and the fit inputs
  data/corpus_v2_summary.csv      the side-by-side estimator comparison
                                  (89-game corpus, 13-game holdout, 102-game
                                  pooled) for M1 and the reference line

Run:  python3 scripts/corpus_v2.py
"""
import csv
import importlib.util
import math
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
READ_UTC = "2026-11-18T05:20Z"
SRC_W10 = "https://www.nfl.com/schedules/2026/by-week/week-10"
SRC_STAND = "https://www.nfl.com/standings/"

# The published construction, imported rather than copied. forecast_records.py
# holds the verified ridge fit, the reference line and the phi/z helpers.
_spec = importlib.util.spec_from_file_location(
    "forecast_records", os.path.join(ROOT, "scripts", "forecast_records.py"))
_fr = importlib.util.module_from_spec(_spec)
# Import for its definitions only: its main() is guarded, so this has no side effects.
_spec.loader.exec_module(_fr)


def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write(name, rows, cols):
    with open(os.path.join(DATA, name), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore", lineterminator="\r\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def load_published():
    rows = read("games_2026_results.csv")
    out = []
    for r in rows:
        out.append({
            "week": int(r["week"]), "away_team": r["away_team"], "home_team": r["home_team"],
            "away_points": int(r["away_points"]), "home_points": int(r["home_points"]),
            "game_url": r["game_url"], "source_url": r["source_url"], "provenance": "published feed",
        })
    return out


def load_backfill():
    """The 13 settled Week 10 games, transcribed from the official by-week page."""
    out = []
    for r in read("games_week10_backfill_2026.csv"):
        out.append({
            "week": int(r["week"]), "away_team": r["away_team"], "home_team": r["home_team"],
            "away_points": int(r["away_points"]), "home_points": int(r["home_points"]),
            "game_url": r["game_url"], "source_url": r["source_url"],
            "provenance": "official Week 10 by-week page, transcribed 2026-11-18 (F105)",
        })
    if len(out) != 13:
        raise SystemExit(f"CORPUS FAILED: backfill holds {len(out)} games, pinned at 13")
    return out


def normalise(games):
    for g in games:
        g["key"] = (g["week"], frozenset((g["away_team"], g["home_team"])))
        g["neutral"] = False          # the published feed's own column is blank for 2026 (F71)
        g["margin"] = g["home_points"] - g["away_points"]
        g["total"] = g["home_points"] + g["away_points"]
    return games


def main():
    published = normalise(load_published())
    backfill = normalise(load_backfill())
    if len(published) != 137:
        raise SystemExit(f"CORPUS FAILED: published feed holds {len(published)} games, pinned at 137")

    # One pool, but a provenance tag per row so a reader can always tell which
    # rows are the published corpus and which are the new ones.
    pool = published + backfill
    model = _fr.Model(pool)

    # --- 1. reproduce the published 89 rows, or stop -----------------------
    back = read("model_backtest.csv")
    if len(back) != 89:
        raise SystemExit(f"CORPUS FAILED: model_backtest.csv holds {len(back)} rows, pinned at 89")
    pub_index = {(int(r["week"]), frozenset((r["away_team"], r["home_team"]))): r for r in published}

    reproduced, worst = 0, 0.0
    for row in back:
        wk = int(row["week"])
        # model_backtest.csv writes "AWAY at HOME", so the first token is the away team.
        away, home = [t.strip() for t in row["matchup"].split(" at ")]
        g = pub_index[(wk, frozenset((home, away)))]
        p = model.fit(upto_week=wk, ref_week=wk)
        pr = model.predict(p, home, away, False)
        rl = model.ref_line(wk, home, away, False)
        for got, want in ((round(pr["home_points"], 1), round(pr["home_points"], 1)),
                          (pr["margin"], float(row["m1_spread_home"])),
                          (pr["total"], float(row["m1_total"])),
                          (rl["margin"], float(row["reference_spread_home"])),
                          (rl["total"], float(row["reference_total"]))):
            pass
        checks = ((pr["margin"], float(row["m1_spread_home"])),
                  (pr["total"], float(row["m1_total"])),
                  (rl["margin"], float(row["reference_spread_home"])),
                  (rl["total"], float(row["reference_total"])))
        delta = max(abs(a - b) for a, b in checks)
        worst = max(worst, delta)
        if delta > _fr.TOL:
            raise SystemExit(f"CORPUS FAILED: week {wk} {row['matchup']} diverges from the "
                             f"published row by {delta:.3f} points (tolerance {_fr.TOL})")
        reproduced += 1
    print(f"Reproduced {reproduced} of {len(back)} published rows; worst divergence {worst:.4f} points.")

    # --- 2. score the 13 new games out of sample ---------------------------
    rows = []

    def add_row(g, corpus, fit_n, fit_weeks, pr, rl, sd_m, sd_t, sd_src):
        cover_line = rl["margin"]
        over_line = rl["total"]
        p_home = _fr.norm_cdf(pr["margin"] / sd_m)
        p_cover = _fr.norm_cdf((pr["margin"] - cover_line) / sd_m)
        p_over = 1.0 - _fr.norm_cdf((over_line - pr["total"]) / sd_t)
        actual_cover = 1 if g["margin"] > cover_line else 0
        actual_over = 1 if g["total"] > over_line else 0
        rows.append({
            "record_id": f"M1-{g['week']:02d}-{g['away_team']}-{g['home_team']}",
            "corpus": corpus, "week": g["week"],
            "matchup": f"{g['away_team']} at {g['home_team']}",
            "model_id": "M1",
            "output_margin_home_minus_away_pts": round(pr["margin"], 3),
            "output_total_pts": round(pr["total"], 3),
            "prob_home_win": round(p_home, 4),
            "prob_home_covers_reference_line": round(p_cover, 4),
            "prob_over_reference_total": round(p_over, 4),
            "reference_cover_line_pts": round(cover_line, 3),
            "reference_over_line_pts": round(over_line, 3),
            "residual_sd_margin": round(sd_m, 3),
            "residual_sd_total": round(sd_t, 3),
            "residual_sd_source": sd_src,
            "actual_margin": g["margin"], "actual_total": g["total"],
            "outcome_home_win": 1 if g["margin"] > 0 else 0,
            "outcome_cover": actual_cover, "outcome_over": actual_over,
            "abs_error_model_margin": round(abs(pr["margin"] - g["margin"]), 3),
            "abs_error_reference_margin": round(abs(cover_line - g["margin"]), 3),
            "abs_error_model_total": round(abs(pr["total"] - g["total"]), 3),
            "abs_error_reference_total": round(abs(over_line - g["total"]), 3),
            "personnel_or_availability_inputs_used": "none - the model carries no availability feature (D24 blocked)",
            "fit_team_games": fit_n, "fit_weeks": fit_weeks,
            "provenance": g["provenance"],
            "game_url": g["game_url"], "source_url": g["source_url"],
            "recorded_utc": READ_UTC,
        })

    # Residual scale: estimated only on games strictly before the scored week,
    # so the 13 new rows are not calibrated with their own outcomes.
    def residual_scale(upto_week):
        res_m, res_t = [], []
        for wk in sorted({g["week"] for g in pool if g["week"] >= _fr.EVAL_FROM_WEEK and g["week"] < upto_week}):
            train = [g for g in pool if g["week"] < wk]
            if len(train) < 20:
                continue
            p = model.fit(upto_week=wk, ref_week=wk)
            for g in [x for x in pool if x["week"] == wk]:
                pr = model.predict(p, g["home_team"], g["away_team"], False)
                res_m.append(g["margin"] - pr["margin"])
                res_t.append(g["total"] - pr["total"])
        if len(res_m) >= 2:
            sd_m = math.sqrt(sum(x * x for x in res_m) / (len(res_m) - 1))
            sd_t = math.sqrt(sum(x * x for x in res_t) / (len(res_t) - 1))
            return sd_m, sd_t, "out-of-sample residuals, weeks before %d (n=%d)" % (upto_week, len(res_m))
        # Week 4 is the first scored week, so there is no earlier out-of-sample
        # residual to measure. Fall back to the IN-SAMPLE residual of the fit
        # itself, which uses no information from the scored week or later, and
        # say so in the row rather than silently borrowing a future number.
        p = model.fit(upto_week=upto_week, ref_week=upto_week)
        rm, rt = [], []
        for g in [x for x in pool if x["week"] < upto_week]:
            pr = model.predict(p, g["home_team"], g["away_team"], False)
            rm.append(g["margin"] - pr["margin"])
            rt.append(g["total"] - pr["total"])
        sd_m = math.sqrt(sum(x * x for x in rm) / (len(rm) - 1))
        sd_t = math.sqrt(sum(x * x for x in rt) / (len(rt) - 1))
        return sd_m, sd_t, "in-sample residuals of the training fit (no earlier scored week, n=%d)" % len(rm)

    for g in published:
        if g["week"] >= _fr.EVAL_FROM_WEEK:
            wk = g["week"]
            p = model.fit(upto_week=wk, ref_week=wk)
            pr = model.predict(p, g["home_team"], g["away_team"], False)
            rl = model.ref_line(wk, g["home_team"], g["away_team"], False)
            sd_m, sd_t, sd_src = residual_scale(wk)
            add_row(g, "published 89-game corpus (weeks 4-10)", p["n_obs"],
                    f"w{p['weeks'][0]}-w{p['weeks'][-1]}", pr, rl, sd_m, sd_t, sd_src)

    for g in backfill:
        wk = g["week"]
        p = model.fit(upto_week=wk, ref_week=wk)
        pr = model.predict(p, g["home_team"], g["away_team"], False)
        rl = model.ref_line(wk, g["home_team"], g["away_team"], False)
        sd_m, sd_t, sd_src = residual_scale(wk)
        add_row(g, "week 10 holdout (13 games, settled 2026-11-15/16)", p["n_obs"],
                f"w{p['weeks'][0]}-w{p['weeks'][-1]}", pr, rl, sd_m, sd_t, sd_src)

    rows.sort(key=lambda r: (r["week"], r["matchup"]))
    if len(rows) != 102:
        raise SystemExit(f"CORPUS FAILED: wrote {len(rows)} rows, expected 89 + 13 = 102")

    # --- 3. the side-by-side comparison -----------------------------------
    def summarise(sel, label):
        n = len(sel)
        mae_m = sum(r["abs_error_model_margin"] for r in sel) / n
        mae_r = sum(r["abs_error_reference_margin"] for r in sel) / n
        tot_m = sum(r["abs_error_model_total"] for r in sel) / n
        tot_r = sum(r["abs_error_reference_total"] for r in sel) / n
        wins = sum(1 for r in sel if r["abs_error_model_margin"] < r["abs_error_reference_margin"])
        losses = sum(1 for r in sel if r["abs_error_model_margin"] > r["abs_error_reference_margin"])
        ties = n - wins - losses
        return {
            "subset": label, "games": n,
            "mae_model_margin": round(mae_m, 3), "mae_reference_margin": round(mae_r, 3),
            "gain_margin_pts": round(mae_r - mae_m, 3),
            "mae_model_total": round(tot_m, 3), "mae_reference_total": round(tot_r, 3),
            "gain_total_pts": round(tot_r - tot_m, 3),
            "games_model_closer": wins, "games_reference_closer": losses, "ties": ties,
            "source_url": SRC_W10,
            "reading": ("model ahead of its own reference line" if mae_r > mae_m
                        else "model BEHIND its own reference line on this subset"),
        }

    pub = [r for r in rows if r["provenance"] == "published feed"]
    new = [r for r in rows if r["provenance"] != "published feed"]
    summary = [summarise(pub, "A. published 89-game corpus (weeks 4-10)"),
               summarise(new, "B. Week 10 holdout (13 games, never scored before)"),
               summarise(rows, "C. pooled 102-game corpus (A + B)")]

    write("corpus_v2_2026.csv", rows, list(rows[0].keys()))
    write("corpus_v2_summary.csv", summary,
          ["subset", "games", "mae_model_margin", "mae_reference_margin", "gain_margin_pts",
           "mae_model_total", "mae_reference_total", "gain_total_pts",
           "games_model_closer", "games_reference_closer", "ties", "reading", "source_url"])

    print(f"corpus_v2_2026.csv: {len(rows)} rows (89 published + 13 new)")
    for s in summary:
        print(f"  {s['subset']}: n={s['games']} model MAE {s['mae_model_margin']} vs reference "
              f"{s['mae_reference_margin']} → gain {s['gain_margin_pts']:+.3f} pts")


if __name__ == "__main__":
    main()
