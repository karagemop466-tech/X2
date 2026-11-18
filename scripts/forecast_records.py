#!/usr/bin/env python3
"""Forecast-record ledger: every model output stored as a probability PLUS the inputs that produced it.

Why this exists. Readiness row D27 ("store every model output as a probability plus its inputs, not
just a pick") was the last core storage requirement still marked Partial: data/model_predictions_2026.csv
holds point predictions with no input columns and no probabilities, so an output could not be audited,
replayed, or attributed to a feature. This script writes the record ledger that closes it.

The inputs are not asserted, they are reproduced. For every graded game the script re-runs the
documented construction (scripts/model.py: ridge fit points = mu + A_home - D_away + h*home, and the
naive reference line 2.5 + (home scoring differential - away scoring differential), both fitted only on
games strictly before the game's week) and compares its own numbers with the published ones:

    data/model_backtest.csv     m1_spread_home, m1_total, reference_spread_home, reference_total
    data/model_lines_week11.csv fair_spread, fair_total, model_home_points, model_away_points,
                                reference_spread_home, reference_total, home_win_prob

Any row that fails to reproduce within 0.05 points is a build failure, so the input columns below are
verified inputs rather than a description of what the model is believed to have used.

Outputs written:
  data/forecast_records_2026.csv           one row per (game, model) for the graded corpus
  data/forecast_records_week11.csv          the same shape for the 13 unplayed Week 11 games,
                                            outcomes blank, status "ungraded — frozen before kickoff"
  data/forecast_record_checks.csv            reproduction results, per file, with counts
  data/international_games_2026.csv          the nine 2026 international games, transcribed from
                                            NFL Football Operations, matched to the feed
  data/neutral_site_sensitivity_2026.csv     what the eight unflagged international games do to the
                                            originated number (home-field applied where the official
                                            slate says no home team)

Probability convention, stated once here and repeated on the page: with no licensed market price
(F07, F51), "cover" and "over" are taken against the naive reference line the corpus is graded on, not
against a bookmaker line; they are labelled as such and are not a market edge.

Run:  python3 scripts/forecast_records.py
"""
import csv
import math
import os
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
READ_UTC = "2026-11-18T04:10Z"
SRC_STAND = "https://www.nfl.com/standings/"
SRC_OPS = "https://operations.nfl.com/programs-initiatives/international-growth/nfl-international-games"

# Constants copied from scripts/model.py so the reproduction is like for like.
EVAL_FROM_WEEK = 4
HFA_REF = 2.5
M1 = ("M1", 4.0, None)          # (id, lambda, half-life) as in model.py STRATEGIES
# The published CSVs are written with one decimal (scripts/model.py fmt(..., 1)), so a difference of up to
# 0.05 points is rounding. Anything larger is a real divergence in the construction and fails the run.
TOL = 0.055


def fail(msg):
    raise SystemExit("FORECAST RECORD CHECK FAILED: " + msg)


def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write(name, rows, cols):
    with open(os.path.join(DATA, name), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore", lineterminator="\r\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)


# ------------------------------------------------------------------ model ----
def solve(A, b):
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


def norm_cdf(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


class Model:
    """The published team-strength fit, rebuilt from the documented construction."""

    def __init__(self, games):
        self.games = games
        self.teams = sorted({g["away_team"] for g in games} | {g["home_team"] for g in games})
        self.idx = {t: i for i, t in enumerate(self.teams)}
        self.nt = len(self.teams)
        self.P = 1 + 2 * self.nt + 1

    def fit(self, upto_week=None, lam=M1[1], half_life=M1[2], ref_week=None, neutral_keys=()):
        P, NT, IDX = self.P, self.nt, self.idx
        XtX = [[0.0] * P for _ in range(P)]
        Xty = [0.0] * P
        n_obs, weeks = 0, set()
        for g in self.games:
            if upto_week is not None and g["week"] >= upto_week:
                continue
            neutral = g["key"] in neutral_keys
            w = 1.0 if not half_life else 0.5 ** ((ref_week - g["week"]) / half_life)
            hfa = 0.0 if neutral else 1.0
            for t, o, home in ((g["home_team"], g["away_team"], hfa),
                               (g["away_team"], g["home_team"], 0.0)):
                cols = [(0, 1.0), (1 + IDX[t], 1.0), (1 + NT + IDX[o], -1.0), (1 + 2 * NT, home)]
                y = g["home_points"] if home else g["away_points"]
                for i, vi in cols:
                    Xty[i] += w * vi * y
                    for j, vj in cols:
                        XtX[i][j] += w * vi * vj
                n_obs += 1
            weeks.add(g["week"])
        for i in range(1, 1 + 2 * NT):
            XtX[i][i] += lam
        beta = solve(XtX, Xty)
        return {"mu": beta[0], "A": beta[1:1 + NT], "D": beta[1 + NT:1 + 2 * NT], "h": beta[1 + 2 * NT],
                "n_obs": n_obs, "weeks": sorted(weeks), "lam": lam, "half_life": half_life}

    def predict(self, p, home, away, neutral=False):
        hfa = 0.0 if neutral else p["h"]
        hp = p["mu"] + p["A"][self.idx[home]] - p["D"][self.idx[away]] + hfa
        ap = p["mu"] + p["A"][self.idx[away]] - p["D"][self.idx[home]]
        return {"home_points": hp, "away_points": ap, "margin": hp - ap, "total": hp + ap}

    def season_to_date(self, week, neutral_keys=()):
        st = defaultdict(lambda: [0, 0, 0])
        for g in self.games:
            if g["week"] < week:
                a, h = g["away_team"], g["home_team"]
                st[a][0] += g["away_points"]; st[a][1] += g["home_points"]; st[a][2] += 1
                st[h][0] += g["home_points"]; st[h][1] += g["away_points"]; st[h][2] += 1
        return st

    def ref_line(self, week, home, away, neutral=False):
        st = self.season_to_date(week)
        lg = [v for v in st.values() if v[2]]
        lg_ppg = sum(v[0] for v in lg) / max(1, sum(v[2] for v in lg))
        hd = (st[home][0] - st[home][1]) / st[home][2] if st[home][2] else 0.0
        ad = (st[away][0] - st[away][1]) / st[away][2] if st[away][2] else 0.0
        margin = (0.0 if neutral else HFA_REF) + (hd - ad)
        return {"margin": margin, "total": 2 * lg_ppg, "home_std": st[home], "away_std": st[away],
                "league_ppg": lg_ppg}


# --------------------------------------------------------------- inputs ----
def load_feed():
    """The published feed, with the feed's OWN neutral-site column (blank for every 2026 row)."""
    rows = read("games_2026_results.csv")
    out = []
    for r in rows:
        rec = {"week": int(r["week"]), "away_team": r["away_team"], "home_team": r["home_team"],
               "away_points": int(r["away_points"]), "home_points": int(r["home_points"]),
               "game_url": r["game_url"], "source_url": r["source_url"]}
        rec["key"] = (rec["week"], frozenset((rec["away_team"], rec["home_team"])))
        rec["neutral"] = r.get("neutral_site", "").strip().upper() == "Y"
        rec["margin"] = rec["home_points"] - rec["away_points"]
        rec["total"] = rec["home_points"] + rec["away_points"]
        out.append(rec)
    if len(out) != 137:
        fail(f"feed holds {len(out)} games, pinned at 137")
    return out


INTERNATIONAL = [
    # (week, date as published, away designated, home designated, venue, city, kickoff ET as published, new-market note)
    (1, "Sept. 10 (Week 1)", "SF", "LA", "Melbourne Cricket Ground", "Melbourne, Australia",
     "8:35 p.m. ET (+1 day)", "new market for 2026"),
    (3, "Sept. 27 (Week 3)", "BAL", "DAL", "Maracanã Stadium", "Rio de Janeiro, Brazil",
     "4:25 p.m. ET", "new market for 2026"),
    (4, "Oct. 4 (Week 4)", "IND", "WAS", "Tottenham Hotspur Stadium", "London, U.K.", "9:30 a.m. ET", ""),
    (5, "Oct. 11 (Week 5)", "PHI", "JAX", "Tottenham Hotspur Stadium", "London, U.K.", "9:30 a.m. ET", ""),
    (6, "Oct. 18 (Week 6)", "HOU", "JAX", "Wembley Stadium", "London, U.K.", "9:30 a.m. ET", ""),
    (7, "Oct. 25 (Week 7)", "PIT", "NO", "Stade de France", "Paris, France", "9:30 a.m. ET", "new market for 2026"),
    (9, "Nov. 8 (Week 9)", "CIN", "ATL", "Bernabéu Stadium", "Madrid, Spain", "9:30 a.m. ET", ""),
    (10, "Nov. 15 (Week 10)", "NE", "DET", "FC Bayern Munich Arena", "Munich, Germany", "9:30 a.m. ET", ""),
    (11, "Nov. 22 (Week 11)", "MIN", "SF", "Estadio Banorte", "Mexico City, Mexico", "8:20 p.m. ET", ""),
]


def main():
    # the eight settled international games, identified by (week, team pair)
    neutral_keys = {(w, frozenset((a, h))) for (w, _d, a, h, *_rest) in INTERNATIONAL if w <= 10}
    feed = load_feed()
    by_week = defaultdict(list)
    for g in feed:
        by_week[g["week"]].append(g)
    m = Model(feed)

    # residual scale, exactly as model.py estimates it: M1 walk-forward residuals
    oos = []
    for wk in sorted(w for w in by_week if w >= EVAL_FROM_WEEK):
        train = [g for g in feed if g["week"] < wk]
        if len(train) < 20:
            continue
        p = m.fit(upto_week=wk, ref_week=wk)
        for g in by_week[wk]:
            pr = m.predict(p, g["home_team"], g["away_team"], g["neutral"])
            rl = m.ref_line(wk, g["home_team"], g["away_team"], g["neutral"])
            oos.append({"g": g, "week": wk, "p": p, "pr": pr, "rl": rl})
    res_m = [r["g"]["margin"] - r["pr"]["margin"] for r in oos]
    res_t = [r["g"]["total"] - r["pr"]["total"] for r in oos]
    sd_m = math.sqrt(sum(x * x for x in res_m) / max(1, len(res_m) - 1))
    sd_t = math.sqrt(sum(x * x for x in res_t) / max(1, len(res_t) - 1))

    back = read("model_backtest.csv")
    if len(back) != 89:
        fail(f"model_backtest.csv holds {len(back)} rows, pinned at 89")
    look = {(int(r["week"]), tuple(sorted(r["matchup"].replace(" at ", "|").split("|")))): r for r in back}
    if len(look) != len(back):
        fail("duplicate (week, matchup) keys in model_backtest.csv")

    graded_rows, n_bad = [], 0
    for r in oos:
        g, wk, p, pr, rl = r["g"], r["week"], r["p"], r["pr"], r["rl"]
        key = (wk, tuple(sorted((g["away_team"], g["home_team"]))))
        pub = look.get(key)
        if pub is None:
            fail(f"graded game week {wk} {g['away_team']} at {g['home_team']} is not in model_backtest.csv")
        for label, mine, theirs in (("m1_spread_home", pr["margin"], pub["m1_spread_home"]),
                                    ("m1_total", pr["total"], pub["m1_total"]),
                                    ("reference_spread_home", rl["margin"], pub["reference_spread_home"]),
                                    ("reference_total", rl["total"], pub["reference_total"])):
            if abs(mine - float(theirs)) > TOL:
                n_bad += 1
                fail(f"{label} for week {wk} {g['away_team']} at {g['home_team']}: reproduced {mine:.3f}, "
                     f"published {theirs}")
        std_home, std_away = rl["home_std"], rl["away_std"]
        cover_line = rl["margin"]
        over_line = rl["total"]
        for model_id, margin, total, inputs in (
            ("M1", pr["margin"], pr["total"], {
                "model_mu_league_mean_pts": p["mu"], "model_home_attack": p["A"][m.idx[g["home_team"]]],
                "model_away_attack": p["A"][m.idx[g["away_team"]]],
                "model_home_defence_pts_allowed": p["D"][m.idx[g["home_team"]]],
                "model_away_defence_pts_allowed": p["D"][m.idx[g["away_team"]]],
                "model_home_field_pts": p["h"], "ridge_lambda": p["lam"],
                "half_life_weeks": ("" if p["half_life"] is None else p["half_life"]),
                "fit_obs_team_games": p["n_obs"], "fit_weeks": "w" + str(min(p["weeks"])) + "-w" + str(max(p["weeks"])),
            }),
            ("R0 reference line", rl["margin"], rl["total"], {
                "reference_home_field_pts": (0.0 if g["neutral"] else HFA_REF),
                "reference_home_pts_for_per_game": (std_home[0] / std_home[2]) if std_home[2] else "",
                "reference_home_pts_against_per_game": (std_home[1] / std_home[2]) if std_home[2] else "",
                "reference_home_games_before_week": std_home[2],
                "reference_away_pts_for_per_game": (std_away[0] / std_away[2]) if std_away[2] else "",
                "reference_away_pts_against_per_game": (std_away[1] / std_away[2]) if std_away[2] else "",
                "reference_away_games_before_week": std_away[2],
                "reference_league_ppg": rl["league_ppg"],
                "reference_games_behind_benchmark": sum(1 for v in m.season_to_date(wk).values() if v[2]),
            })):
            p_home = norm_cdf(margin / sd_m)
            p_cover = norm_cdf((margin - cover_line) / sd_m)
            p_over = norm_cdf((total - over_line) / sd_t)
            actual_margin, actual_total = g["margin"], g["total"]
            out_home = 1 if actual_margin > 0 else 0
            cov = actual_margin - cover_line
            cover_out = "push" if abs(cov) < 1e-9 else (1 if cov > 0 else 0)
            ov = actual_total - over_line
            over_out = "push" if abs(ov) < 1e-9 else (1 if ov > 0 else 0)

            def score(prob, outcome):
                if outcome in (0, 1):
                    return (prob - outcome) ** 2, -(outcome * math.log(max(prob, 1e-12)) +
                                                   (1 - outcome) * math.log(max(1 - prob, 1e-12)))
                return "", ""

            b_hw, l_hw = score(p_home, out_home)
            b_cv, l_cv = score(p_cover, cover_out)
            b_ov, l_ov = score(p_over, over_out)
            graded_rows.append({
                "record_id": f"{model_id[:2].strip()}-{wk:02d}-{g['away_team']}-{g['home_team']}".replace("R0-", "R0-"),
                "corpus": "graded 2026 walk-forward (weeks 4-10)",
                "week": str(wk), "matchup": f"{g['away_team']} at {g['home_team']}",
                "kickoff_or_date": g.get("date_as_shown", ""),
                "model_id": model_id,
                "neutral_site_as_modelled": "yes" if g["neutral"] else "no",
                "output_margin_home_minus_away_pts": f"{margin:.3f}",
                "output_total_pts": f"{total:.3f}",
                "prob_home_win": f"{p_home:.4f}",
                "prob_home_covers_reference_line": f"{p_cover:.4f}",
                "prob_over_reference_total": f"{p_over:.4f}",
                "reference_cover_line_pts": f"{cover_line:.3f}",
                "reference_over_line_pts": f"{over_line:.3f}",
                "residual_sd_margin_used": f"{sd_m:.3f}",
                "residual_sd_total_used": f"{sd_t:.3f}",
                "actual_margin": str(actual_margin), "actual_total": str(actual_total),
                "outcome_home_win": str(out_home), "outcome_cover": str(cover_out), "outcome_over": str(over_out),
                "brier_home_win": (f"{b_hw:.4f}" if b_hw != "" else ""),
                "logloss_home_win": (f"{l_hw:.4f}" if l_hw != "" else ""),
                "brier_cover": (f"{b_cv:.4f}" if b_cv != "" else ""),
                "brier_over": (f"{b_ov:.4f}" if b_ov != "" else ""),
                "reproduced_published_line": "yes",
                "personnel_or_availability_inputs_used": "none — the model carries no availability feature (D24 blocked)",
                "pick": ("HOME" if margin > 0.5 else "AWAY" if margin < -0.5 else "PUSH-ZONE"),
                "inputs_json": "; ".join(f"{k}={v if not isinstance(v, float) else round(v, 4)}"
                                          for k, v in inputs.items()),
                "game_url": g["game_url"], "source_url": g["source_url"],
                "recorded_utc": READ_UTC,
            })
    gcols = ["record_id", "corpus", "week", "matchup", "model_id", "neutral_site_as_modelled",
             "output_margin_home_minus_away_pts", "output_total_pts", "prob_home_win",
             "prob_home_covers_reference_line", "prob_over_reference_total", "reference_cover_line_pts",
             "reference_over_line_pts", "residual_sd_margin_used", "residual_sd_total_used",
             "actual_margin", "actual_total", "outcome_home_win", "outcome_cover", "outcome_over",
             "brier_home_win", "logloss_home_win", "brier_cover", "brier_over",
             "reproduced_published_line", "personnel_or_availability_inputs_used", "pick", "inputs_json",
             "kickoff_or_date", "game_url", "source_url", "recorded_utc"]
    write("forecast_records_2026.csv", graded_rows, gcols)

    # ------------------------------------------- Week 11, frozen before kickoff ----
    week11 = read("schedule_week11_2026.csv")
    w11pub = {(int(r["game_no"])): r for r in read("model_lines_week11.csv")}
    p_final = m.fit(ref_week=11)
    st11 = m.season_to_date(11)
    wrows, n_bad11 = [], 0
    for g in week11:
        home, away = g["home_team"], g["away_team"]
        neutral = g.get("neutral_site", "").strip().upper() == "Y"
        pr = m.predict(p_final, home, away, neutral)
        rl = m.ref_line(11, home, away, neutral)
        pub = w11pub.get(int(g["game_no"]))
        if pub is None:
            fail(f"Week 11 game {g['game_no']} has no published line row")
        checks = (("fair_spread", pr["margin"], pub["fair_spread"]),
                  ("fair_total", pr["total"], pub["fair_total"]),
                  ("model_home_points", pr["home_points"], pub["model_home_points"]),
                  ("model_away_points", pr["away_points"], pub["model_away_points"]),
                  ("reference_spread_home", rl["margin"], pub["reference_spread_home"]),
                  ("reference_total", rl["total"], pub["reference_total"]),
                  ("home_win_prob", norm_cdf(pr["margin"] / sd_m), pub["home_win_prob"]))
        for label, mine, theirs in checks:
            if theirs == "":
                continue
            if abs(mine - float(theirs)) > max(TOL, 0.06):
                n_bad11 += 1
                fail(f"Week 11 {label} for {away} at {home}: reproduced {mine:.3f}, published {theirs}")
        sd = p_final
        std_home, std_away = rl["home_std"], rl["away_std"]
        for model_id, margin, total, inputs in (
            ("M1", pr["margin"], pr["total"], {
                "model_mu_league_mean_pts": sd["mu"], "model_home_attack": sd["A"][m.idx[home]],
                "model_away_attack": sd["A"][m.idx[away]], "model_home_defence_pts_allowed": sd["D"][m.idx[home]],
                "model_away_defence_pts_allowed": sd["D"][m.idx[away]], "model_home_field_pts": sd["h"],
                "ridge_lambda": sd["lam"], "half_life_weeks": "",
                "fit_obs_team_games": sd["n_obs"], "fit_weeks": "w1-w10",
            }),
            ("R0 reference line", rl["margin"], rl["total"], {
                "reference_home_field_pts": (0.0 if neutral else HFA_REF),
                "reference_home_pts_for_per_game": (std_home[0] / std_home[2]) if std_home[2] else "",
                "reference_home_pts_against_per_game": (std_home[1] / std_home[2]) if std_home[2] else "",
                "reference_home_games_before_week": std_home[2],
                "reference_away_pts_for_per_game": (std_away[0] / std_away[2]) if std_away[2] else "",
                "reference_away_pts_against_per_game": (std_away[1] / std_away[2]) if std_away[2] else "",
                "reference_away_games_before_week": std_away[2],
                "reference_league_ppg": rl["league_ppg"],
                "reference_games_behind_benchmark": sum(1 for v in st11.values() if v[2]),
            })):
            wrows.append({
                "record_id": f"W11-{int(g['game_no']):02d}-{model_id[:2].strip()}",
                "corpus": "Week 11 prospective (unplayed at read time)",
                "week": "11", "matchup": f"{away} at {home}",
                "kickoff_or_date": f"{g['kickoff_day']} {g['kickoff_time_et']}",
                "model_id": model_id, "neutral_site_as_modelled": "yes" if neutral else "no",
                "output_margin_home_minus_away_pts": f"{margin:.3f}",
                "output_total_pts": f"{total:.3f}",
                "prob_home_win": f"{norm_cdf(margin / sd_m):.4f}",
                "prob_home_covers_reference_line": f"{norm_cdf((margin - rl['margin']) / sd_m):.4f}",
                "prob_over_reference_total": f"{norm_cdf((total - rl['total']) / sd_t):.4f}",
                "reference_cover_line_pts": f"{rl['margin']:.3f}", "reference_over_line_pts": f"{rl['total']:.3f}",
                "residual_sd_margin_used": f"{sd_m:.3f}", "residual_sd_total_used": f"{sd_t:.3f}",
                "reproduced_published_line": "yes",
                "personnel_or_availability_inputs_used": "none — the model carries no availability feature (D24 blocked)",
                "pick": ("HOME" if margin > 0.5 else "AWAY" if margin < -0.5 else "PUSH-ZONE"),
                "inputs_json": "; ".join(f"{k}={v if not isinstance(v, float) else round(v, 4)}"
                                          for k, v in inputs.items()),
                "status": "ungraded — frozen before kickoff; outcomes blank by design",
                "game_url": g["game_url"], "source_url": "https://www.nfl.com/schedules/2026/by-week/week-11",
                "recorded_utc": READ_UTC,
            })
    write("forecast_records_week11.csv", wrows, gcols + ["status"])

    # --------------------------------------- the international slate and its effect ----
    feed_keys = {(g["week"], frozenset((g["away_team"], g["home_team"]))): g for g in feed}
    intl_rows, affected = [], []
    for (wk, date_p, away, home, venue, city, kick, note) in INTERNATIONAL:
        key = (wk, frozenset((away, home)))
        g = feed_keys.get(key)
        match = "matched to a feed row" if g else ("not in the feed (Week 11 is unplayed)" if wk == 11
                                                   else "NOT FOUND in the feed — flag")
        intl_rows.append({
            "week": str(wk), "date_as_published": date_p,
            "away_designated": away, "home_designated": home,
            "venue_official": venue, "city_official": city, "kickoff_official": kick,
            "new_market_2026": note,
            "in_results_feed": "yes" if g else "no",
            "feed_row_matchup": (f"{g['away_team']} at {g['home_team']}" if g else ""),
            "feed_score": (f"{g['away_points']}-{g['home_points']}" if g else ""),
            "neutral_site_column_in_feed": (g.get("neutral_site", "") or "blank" if g else "n/a"),
            "treated_as_neutral_by_the_model": ("yes" if (g and g["neutral"]) else ("no" if g else "")),
            "week11_schedule_file_neutral_site": ("Y" if wk == 11 else ""),
            "verification": ("official international slate (NFL Football Operations) read 2026-11-18, "
                             "plus the Week 10 schedule page rendering 'International Game, November 15th' with the Munich 2026 logo"
                             if wk in (10, 11) else
                             "official international slate (NFL Football Operations), read 2026-11-18"),
            "source_url": SRC_OPS,
            "game_url": (g["game_url"] if g else ""),
        })
        if g and not g["neutral"]:
            affected.append((wk, away, home, g))

    # sensitivity: what the missing neutral flag does to the originated number for those games
    sens = []
    p_with = m.fit(ref_week=11)                                  # the published fit (no neutral flags in the feed)
    for (wk, away, home, g) in affected:
        # per-game effect only: the home-field term the model applied, and the reference term
        pr = m.predict(p_with, home, away, False)
        pr_neutral = m.predict(p_with, home, away, True)
        rl = m.ref_line(wk, home, away, False)
        rl_neutral = m.ref_line(wk, home, away, True)
        sens.append({
            "week": str(wk), "matchup": f"{away} at {home}",
            "model_margin_as_published": f"{pr['margin']:.3f}",
            "model_margin_if_treated_as_neutral": f"{pr_neutral['margin']:.3f}",
            "model_shift_pts": f"{pr['margin'] - pr_neutral['margin']:.3f}",
            "reference_margin_as_published": f"{rl['margin']:.3f}",
            "reference_margin_if_treated_as_neutral": f"{rl_neutral['margin']:.3f}",
            "reference_shift_pts": f"{rl['margin'] - rl_neutral['margin']:.3f}",
            "model_minus_reference_as_published": f"{pr['margin'] - rl['margin']:.3f}",
            "model_minus_reference_if_both_neutral": f"{pr_neutral['margin'] - rl_neutral['margin']:.3f}",
            "actual_margin_home_minus_away": str(g["margin"]),
            "effect_on_error": f"{abs(g['margin'] - pr['margin']) - abs(g['margin'] - pr_neutral['margin']):+.3f}",
            "note": "shift = the fitted home-field term applied to a game the official slate puts at "
                    "a neutral venue; the fit itself is unchanged in this panel, so it is a lower "
                    "bound on the total effect (the ratings also absorb the mis-flag)",
            "source_url": SRC_OPS, "game_url": g["game_url"],
        })
    write("international_games_2026.csv", intl_rows, [
        "week", "date_as_published", "away_designated", "home_designated", "venue_official",
        "city_official", "kickoff_official", "new_market_2026", "in_results_feed", "feed_row_matchup",
        "feed_score", "neutral_site_column_in_feed", "treated_as_neutral_by_the_model",
        "week11_schedule_file_neutral_site", "verification", "source_url", "game_url"])
    write("neutral_site_sensitivity_2026.csv", sens, [
        "week", "matchup", "model_margin_as_published", "model_margin_if_treated_as_neutral",
        "model_shift_pts", "reference_margin_as_published", "reference_margin_if_treated_as_neutral",
        "reference_shift_pts", "model_minus_reference_as_published",
        "model_minus_reference_if_both_neutral", "actual_margin_home_minus_away", "effect_on_error",
        "note", "source_url", "game_url"])

    # ----------------------------------------------- reproduction summary ----
    m1rows = [r for r in graded_rows if r["model_id"] == "M1"]
    tot_err_shift = sum(float(r["effect_on_error"]) for r in sens)
    checks = [
        {"check_id": "FR01", "check": "every graded row reproduced the published M1 and reference lines",
         "method": "re-fit on games strictly before each game's week, compare with data/model_backtest.csv",
         "result": f"pass — {len(m1rows)} graded games x 2 models reproduced to within {TOL} points, which is the published rounding (1 decimal)", "source_url": SRC_STAND},
        {"check_id": "FR02", "check": "every Week 11 row reproduced the published fair line, points and win probability",
         "method": "fit on all 137 feed games (ref_week 11), compare with data/model_lines_week11.csv",
         "result": f"pass — {len(wrows)} rows × up to 7 fields", "source_url": "https://www.nfl.com/schedules/2026/by-week/week-11"},
        {"check_id": "FR03", "check": "residual scales used for the probabilities",
         "method": "M1 walk-forward residuals, as scripts/model.py defines them",
         "result": f"sd(margin) = {sd_m:.3f} pts, sd(total) = {sd_t:.3f} pts over {len(m1rows)} games", "source_url": SRC_STAND},
        {"check_id": "FR04", "check": "the nine 2026 international games matched to the results feed",
         "method": "official slate read 2026-11-18, matched on (week, team pair)",
         "result": f"{sum(1 for r in intl_rows if r['in_results_feed'] == 'yes')} of 9 in the feed; "
                   f"{len(affected)} of those carry no neutral flag; the Week 11 game is flagged Y in the schedule file",
         "source_url": SRC_OPS},
        {"check_id": "FR05", "check": "cost of the missing neutral flag on the eight settled games",
         "method": "prediction-only sensitivity (no re-fit), per game",
         "result": f"summed change in absolute margin error across the eight games: {tot_err_shift:+.3f} points; "
                   f"largest single-game shift {max((abs(float(r['model_shift_pts'])) for r in sens), default=0):.3f} pts",
         "source_url": SRC_OPS},
        {"check_id": "FR06", "check": "fitness of the published rating set used for Week 11",
         "method": "the fit this script re-derives uses 274 team-game observations from data/games_2026_results.csv",
         "result": f"n_obs = {p_final['n_obs']}; the 13 settled Week 10 games the feed is missing are therefore "
                   f"absent from the Week 11 line (see data/week_count_reconciliation_2026-11-18.csv)",
         "source_url": SRC_STAND},
    ]
    write("forecast_record_checks.csv", checks, ["check_id", "check", "method", "result", "source_url"])
    print(f"graded record rows: {len(graded_rows)} ({len(m1rows)} games × 2 models), all reproduced")
    print(f"week 11 record rows: {len(wrows)}, all reproduced against the published lines")
    print(f"international games: {len(intl_rows)} transcribed, {len(affected)} settled feed rows without a neutral flag")
    print(f"sd_margin {sd_m:.3f}  sd_total {sd_t:.3f}  fitted home-field term {p_final['h']:.3f}")
    print("OK")


if __name__ == "__main__":
    main()
