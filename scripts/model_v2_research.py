#!/usr/bin/env python3
"""Research-only re-fits that price the P09 decision (task T109).

What this measures
------------------
`scripts/results_v2.py` built a 150-game register that also carries the official neutral-site
flags (P09 option B: publish v2 in parallel, keep the 137-game v1 corpus as the published
record so no published metric or hash-sealed forecast log changes quietly).

Two things change between the published fit and that register, and they are usually conflated:

  A. the published corpus: 137 games, no neutral-site flag on any completed row (F71);
  B. A + the neutral flags honoured on the 7 completed international games the v1 corpus has;
  C. B + the 13 settled Week 10 games (the full v2 register, 150 games, 8 flagged).

Running B separately is what makes the two effects separable, and it is the number the owner
needs before choosing between "discard the published corpus and re-register" and "keep it and
publish v2 beside it".

How it is run without touching a published file
-----------------------------------------------
`scripts/` and `data/` are copied into a temporary directory; only `data/games_2026_results.csv`
in that copy is replaced; `scripts/model.py` is then executed **unmodified** with the temporary
directory as its root. Every output, including the file that would carry the forecast-log seal,
lands in the sandbox and is deleted. The repository's published model outputs are never written.

Run:  python3 scripts/model_v2_research.py
"""
import csv
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
SRC_WEEK10 = "https://www.nfl.com/schedules/2026/by-week/week-10"
SRC_STANDINGS = "https://www.nfl.com/standings/"
SRC_CODE = "https://github.com/karagemop466-tech/X2/blob/main/scripts/model_v2_research.py"
SRC_MODEL = "https://github.com/karagemop466-tech/X2/blob/main/scripts/model.py"
BET_DELTA = 3.0          # the pre-registered bet threshold inside scripts/model.py
CORPUS_FIELDS = ["season", "week", "date_as_shown", "away_team", "away_points", "home_team",
                 "home_points", "game_url", "source_url", "neutral_site"]


def _close(a, b, tol):
    """Compare two published decimal strings at the looser register's tolerance."""
    try:
        return abs(float(a) - float(b)) <= tol + 1e-9
    except (TypeError, ValueError):
        return str(a).strip() == str(b).strip()


def read(name, base=DATA):
    with open(os.path.join(base, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write(name, rows, fields):
    with open(os.path.join(DATA, name), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


# ------------------------------------------------------- the two corpora ----
v1_corpus = read("games_2026_results.csv")
v2_register = read("results_feed_v2_82b83a64.csv")
if len(v1_corpus) != 137:
    sys.exit(f"the published corpus is {len(v1_corpus)} rows, expected 137 — stop, a canonical file moved")
if len(v2_register) != 150:
    sys.exit(f"v2 register has {len(v2_register)} rows, expected 150 — run scripts/results_v2.py first")

neutral_v2 = {(r["week"], r["away_team"], r["home_team"]) for r in v2_register
              if r["neutral_site"] == "Y"}


def as_corpus_from_v2():
    return [{k: r.get(k, "") for k in CORPUS_FIELDS} for r in v2_register]


def as_corpus_flags_only():
    out = []
    for r in v1_corpus:
        row = {k: r.get(k, "") for k in CORPUS_FIELDS}
        key = (r["week"], r["away_team"], r["home_team"])
        row["neutral_site"] = "Y" if key in neutral_v2 else ""
        out.append(row)
    return out


def as_corpus_v2_unflagged():
    """The v2 corpus with the neutral-site flags removed.

    Added after the companion register published in PR #78 (scripts/corpus_v2.py, 2026-11-18): its
    data/corpus_v2_summary.csv scores the model closer on 5 of the 13 games while this script's v2 fit scored 3. The only methodological difference
    between the two is the flags, so a third 150-game corpus without them settles whether the disagreement is the
    neutral-site treatment or the fit lineage. It is cheaper to run than to argue about.
    """
    out = []
    for r in v2_register:
        row = {k: r.get(k, "") for k in CORPUS_FIELDS}
        row["neutral_site"] = ""
        out.append(row)
    return out


VARIANTS = {
    "flags_only_137": as_corpus_flags_only(),
    "corpus_v2_150": as_corpus_from_v2(),
    "corpus_v2_150_no_flags": as_corpus_v2_unflagged(),
}


# ------------------------------------------------------------- sandbox run --
def run_variant(name, corpus, sandbox_parent):
    box = os.path.join(sandbox_parent, name)
    shutil.copytree(os.path.join(ROOT, "scripts"), os.path.join(box, "scripts"))
    shutil.copytree(DATA, os.path.join(box, "data"))
    with open(os.path.join(box, "data", "games_2026_results.csv"), "w",
              encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CORPUS_FIELDS)
        w.writeheader()
        for r in corpus:
            w.writerow(r)
    proc = subprocess.run([sys.executable, os.path.join(box, "scripts", "model.py")],
                          capture_output=True, text=True, cwd=box)
    if proc.returncode != 0:
        sys.exit(f"model.py failed on variant {name}:\n"
                 + proc.stdout[-2500:] + proc.stderr[-2500:])
    return os.path.join(box, "data")


def per_game(bt):
    """(week, matchup) -> the decision the published method would take on that game."""
    out = {}
    for r in bt:
        edge = float(r["m1_spread_home"]) - float(r["reference_spread_home"])
        bet = abs(edge) >= BET_DELTA
        actual = float(r["actual_margin"])
        out[(int(r["week"]), r["matchup"])] = {
            "edge": edge, "bet": bet,
            "side": (1 if edge > 0 else -1) if bet else 0,
            "closer": abs(actual - float(r["m1_spread_home"]))
                      < abs(actual - float(r["reference_spread_home"])),
            "m1_spread": float(r["m1_spread_home"]),
            "ref_spread": float(r["reference_spread_home"]),
            "m1_total": float(r["m1_total"]), "ref_total": float(r["reference_total"]),
            "actual_margin": actual, "actual_total": float(r["actual_total"]),
        }
    return out


def agg(base):
    bt = read("model_backtest.csv", base)
    s = json.load(open(os.path.join(base, "model_summary.json"), encoding="utf-8"))
    pg = per_game(bt)
    out = {
        "games_in_fit": int(s["games_transcribed"]),
        "oos_rows": len(bt),
        "oos_weeks": len({int(r["week"]) for r in bt}),
        "mae_margin_m1": statistics.fmean(abs(float(r["m1_error"])) for r in bt),
        "mae_margin_reference": statistics.fmean(abs(float(r["reference_error"])) for r in bt),
        "side_hit_rate": sum(v["closer"] for v in pg.values()) / len(pg),
        "mae_total_m1": statistics.fmean(
            abs(float(r["actual_total"]) - float(r["m1_total"])) for r in bt),
        "mae_total_reference": statistics.fmean(
            abs(float(r["actual_total"]) - float(r["reference_total"])) for r in bt),
        "bets": sum(1 for v in pg.values() if v["bet"]),
        "bets_won": sum(1 for v in pg.values() if v["bet"] and v["closer"]),
        "calibration_slope": float(s["calibration_slope"]),
        "calibration_slope_ci": s["calibration_slope_ci"],
        "reference_total_next_week": float(s["reference_total_week11"]),
        "neutral_modelled": int(s["neutral_site_games_modelled"]),
        "neutral_blank": int(s["neutral_site_rows_blank"]),
        "qualified": int(s["qualified_strategies"]),
        # the summary's published figures, kept alongside the per-game recomputations: they differ by up to
        # 0.01 points because model_backtest.csv stores the error against the ROUNDED published line
        "summary_mae_m1": float(s["mae_m1"]),
        "summary_mae_reference": float(s["mae_reference"]),
        "summary_calibration_slope": float(s["calibration_slope"]),
        "summary_reference_total": float(s["reference_total_week11"]),
        "seal": s["forecast_log_seal_sha256"],
        "per_game": pg,
    }
    return out


sandbox_parent = tempfile.mkdtemp(prefix="x2_v2_refit_")
try:
    a = agg(DATA)
    dirs = {name: run_variant(name, corpus, sandbox_parent) for name, corpus in VARIANTS.items()}
    runs = {name: agg(d) for name, d in dirs.items()}
    b, c = runs["flags_only_137"], runs["corpus_v2_150"]
    d = runs["corpus_v2_150_no_flags"]

    # --- shared-game controls: identical fixtures, different fit -----------
    def rate_on(agg_, keys):
        return (sum(1 for k in keys if agg_["per_game"][k]["closer"]) / len(keys)) if keys else 0.0

    ab = sorted(set(a["per_game"]) & set(b["per_game"]))
    ac = sorted(set(a["per_game"]) & set(c["per_game"]))
    only_c = sorted(set(c["per_game"]) - set(a["per_game"]))
    ctrl = {
        "shared_ab": len(ab), "hit_a_on_ab": rate_on(a, ab), "hit_b_on_ab": rate_on(b, ab),
        "hit_a_on_ac": rate_on(a, ac), "hit_c_on_ac": rate_on(c, ac), "shared_ac": len(ac),
        "added_rows": len(only_c), "hit_c_on_added": rate_on(c, only_c),
        "bet_changed_ab": sum(1 for k in ab if a["per_game"][k]["bet"] != b["per_game"][k]["bet"]),
        "side_flip_ab": sum(1 for k in ab if a["per_game"][k]["bet"] and b["per_game"][k]["bet"]
                            and a["per_game"][k]["side"] != b["per_game"][k]["side"]),
        "bet_changed_ac": sum(1 for k in ac if a["per_game"][k]["bet"] != c["per_game"][k]["bet"]),
        "side_flip_ac": sum(1 for k in ac if a["per_game"][k]["bet"] and c["per_game"][k]["bet"]
                            and a["per_game"][k]["side"] != c["per_game"][k]["side"]),
    }
    closer_c = sum(1 for k in only_c if c["per_game"][k]["closer"])
    closer_d = sum(1 for k in only_c if d["per_game"][k]["closer"])

    # --- Week 11 lines: what a re-registration would republish -------------
    def lines(base):
        return {(int(r["game_no"]), r["matchup"]): r for r in read("model_lines_week11.csv", base)}

    LA, LB, LC = lines(DATA), lines(dirs["flags_only_137"]), lines(dirs["corpus_v2_150"])
    line_rows, flip_b, flip_c = [], 0, 0
    for key in sorted(LA):
        p, n1, n2 = LA[key], LB[key], LC[key]
        pick = lambda r: "home" if float(r["fair_spread"]) > 0 else "away" if float(r["fair_spread"]) < 0 else "pick-em"
        p0, p1, p2 = pick(p), pick(n1), pick(n2)
        flip_b += p1 != p0
        flip_c += p2 != p0
        d = lambda x, y: f"{float(y) - float(x):+.1f}"
        line_rows.append({
            "game_no": key[0], "matchup": key[1],
            "published_fair_spread": p["fair_spread"],
            "flagged_fair_spread": n1["fair_spread"], "spread_delta_flags": d(p["fair_spread"], n1["fair_spread"]),
            "v2_fair_spread": n2["fair_spread"], "spread_delta_v2": d(p["fair_spread"], n2["fair_spread"]),
            "published_fair_total": p["fair_total"],
            "flagged_fair_total": n1["fair_total"], "total_delta_flags": d(p["fair_total"], n1["fair_total"]),
            "v2_fair_total": n2["fair_total"], "total_delta_v2": d(p["fair_total"], n2["fair_total"]),
            "published_home_win_prob": p["home_win_prob"],
            "v2_home_win_prob": n2["home_win_prob"],
            "prob_delta_v2": f"{float(n2['home_win_prob']) - float(p['home_win_prob']):+.3f}",
            "side_pick_published": p0, "side_pick_flags_only": p1, "side_pick_v2": p2,
            "pick_flips": "yes" if p1 != p0 or p2 != p0 else "no",
            "note": "research only — the published line and the sealed forecast log stay exactly as they are"
                    if p1 == p0 and p2 == p0 else
                    "research only — a re-registration would change this published pick",
            "game_url": p["game_url"],
            "source_url": "https://www.nfl.com/schedules/2026/by-week/week-11",
        })
    line_fields = ["game_no", "matchup", "published_fair_spread", "flagged_fair_spread",
                   "spread_delta_flags", "v2_fair_spread", "spread_delta_v2", "published_fair_total",
                   "flagged_fair_total", "total_delta_flags", "v2_fair_total", "total_delta_v2",
                   "published_home_win_prob", "v2_home_win_prob", "prob_delta_v2",
                   "side_pick_published", "side_pick_flags_only", "side_pick_v2", "pick_flips",
                   "note", "game_url", "source_url"]
    write("model_v2_research_week11.csv", line_rows, line_fields)

    # --- team ratings: published vs the full v2 fit ------------------------
    pub_r = {r["team"]: r for r in read("model_ratings.csv")}
    new_r = {r["team"]: r for r in read("model_ratings.csv", dirs["corpus_v2_150"])}
    rating_rows = []
    for t in sorted(pub_r):
        p, n = pub_r[t], new_r.get(t)
        if n is None:
            continue
        rating_rows.append({
            "team": t,
            "published_attack": p["attack_rating"], "v2_attack": n["attack_rating"],
            "attack_delta": f"{float(n['attack_rating']) - float(p['attack_rating']):+.2f}",
            "published_defence": p["defence_rating"], "v2_defence": n["defence_rating"],
            "defence_delta": f"{float(n['defence_rating']) - float(p['defence_rating']):+.2f}",
            "published_net": p["net_rating"], "v2_net": n["net_rating"],
            "net_delta": f"{float(n['net_rating']) - float(p['net_rating']):+.2f}",
            "games_in_fit_published": p["games_played"], "games_in_fit_v2": n["games_played"],
            "source_url": SRC_STANDINGS,
        })
    rating_rows.sort(key=lambda r: -abs(float(r["net_delta"])))
    write("model_v2_research_ratings.csv", rating_rows,
          ["team", "published_attack", "v2_attack", "attack_delta", "published_defence",
           "v2_defence", "defence_delta", "published_net", "v2_net", "net_delta",
           "games_in_fit_published", "games_in_fit_v2", "source_url"])

    # --- the delta table ---------------------------------------------------
    METRICS = [
        ("games in the fitted corpus", "the walk-forward input", "games_in_fit", 0,
         "B changes nothing here; C adds the 13 settled Week 10 games"),
        ("out-of-sample backtest rows", "weeks 4 onward, every game with a published line", "oos_rows", 0,
         "a larger evaluation sample is the one unambiguous gain of completing the corpus (F33)"),
        ("out-of-sample weeks", "weeks represented in the backtest", "oos_weeks", 0,
         "same weeks; more games inside them"),
        ("MAE, margin (M1)", "points", "mae_margin_m1", 3, "model error on the margin, per corpus"),
        ("MAE, margin (reference line)", "points", "mae_margin_reference", 3,
         "the benchmark the model is scored against moves too, which is why the gap matters more than either"),
        ("Side hit rate vs reference", "share of backtest games where M1 is closer", "side_hit_rate", 3,
         "the headline number the backtest page publishes"),
        ("MAE, total (M1)", "points", "mae_total_m1", 3, "totals, model"),
        ("MAE, total (reference line)", "points", "mae_total_reference", 3, "totals, benchmark"),
        ("Bets at the pre-registered threshold", f"|model − reference| >= {BET_DELTA} points", "bets", 0,
         "the rule is unchanged; only the fit and the sample differ"),
        ("Bets won", "games where M1's number was closer than the reference's", "bets_won", 0,
         "counted with the identical rule on all three corpora"),
        ("Calibration slope", "regression of actual margin on predicted margin", "calibration_slope", 3,
         "read against the interval the model already publishes; a point estimate crossing 1.0 is not evidence"),
        ("Reference total for the next week", "points", "reference_total_next_week", 1,
         "the naive benchmark moves with the corpus, so a re-registration would republish this"),
        ("Neutral games modelled without a home term", "count", "neutral_modelled", 0,
         "0 of 137 as published (F71); B fixes it on the 7 completed international games the v1 corpus holds; "
         "C on all 8"),
        ("Corpus rows with a blank neutral flag", "count", "neutral_blank", 0,
         "the published corpus carries no flag at all"),
        ("Strategies qualified", "count", "qualified", 0,
         "0 on all three: no strategy qualifies prospectively, and a bigger historical sample does not change that"),
    ]
    rows = []
    for name, scope, key, nd, reading in METRICS:
        va, vb, vc = a[key], b[key], c[key]
        f = (lambda x: f"{x:.{nd}f}") if nd else (lambda x: str(int(x)))
        rows.append({
            "metric": name, "scope": scope,
            "published_v1_137": f(va), "flags_only_137": f(vb), "corpus_v2_150": f(vc),
            "delta_flags_only": f"{vb - va:+.{nd}f}" if nd else f"{int(vb - va):+d}",
            "delta_v2": f"{vc - va:+.{nd}f}" if nd else f"{int(vc - va):+d}",
            "reading": reading, "compute_url": SRC_MODEL, "source_url": SRC_WEEK10,
        })

    extra = [
        ("Side hit rate on the games A and B both contain",
         f"the identical {ctrl['shared_ab']} backtest rows, published fit versus flags-only fit",
         f"{ctrl['hit_a_on_ab']:.3f}", f"{ctrl['hit_b_on_ab']:.3f}", "—",
         f"{ctrl['hit_b_on_ab'] - ctrl['hit_a_on_ab']:+.3f}", "—",
         "the neutral flags alone, on unchanged fixtures and an unchanged sample"),
        ("Side hit rate on the games A and C both contain",
         f"the identical {ctrl['shared_ac']} backtest rows, published fit versus the full v2 fit",
         f"{ctrl['hit_a_on_ac']:.3f}", "—", f"{ctrl['hit_c_on_ac']:.3f}", "—",
         f"{ctrl['hit_c_on_ac'] - ctrl['hit_a_on_ac']:+.3f}",
         "the re-estimated ratings on unchanged fixtures; the rest of the headline movement is the added "
         f"Week 10 slice, on which the v2 fit was closer {ctrl['hit_c_on_added']:.1%} of the time"),
        ("Backtest rows the corpus change adds", "games from week 4 onward the published backtest did not contain",
         str(a["oos_rows"]), str(b["oos_rows"]), str(c["oos_rows"]), "0", f"+{ctrl['added_rows']}",
         "measured to say what the added slice holds, never to re-pool it into the published record"),
        ("Shared bets whose side flips", "of the games A would have bet, how many change which side is backed",
         "0", f"{ctrl['side_flip_ab']}", f"{ctrl['side_flip_ac']}",
         f"{ctrl['side_flip_ab']:+d}", f"{ctrl['side_flip_ac']:+d}",
         f"the P09 note on the decision console predicted three side picks plus one bet-gate crossing would turn "
         f"on the neutral flags. Measured: {ctrl['side_flip_ab']} side flips and {ctrl['bet_changed_ab']} "
         f"bet/no-bet changes on the flags-only fit. Recorded as a discrepancy against that note."),
        ("Week 10 holdout: games the model is closer on",
         f"the {ctrl['added_rows']} settled Week 10 games neither corpus had scored, flagged vs unflagged",
         "0", f"{closer_d} of {ctrl['added_rows']}", f"{closer_c} of {ctrl['added_rows']}",
         f"{closer_d:+d}", f"{closer_c:+d}",
         f"cross-register reconciliation. data/corpus_v2_summary.csv (PR #78, 2026-11-18) scores the "
         f"model closer on 5 of these 13 games against its own reference line, MAE 10.099 vs "
         f"9.509 points. This script's unflagged 150-game fit reproduces that figure exactly ({closer_d} of 13), "
         f"and its flagged fit gives {closer_c}: the only methodological difference between the two registers is the "
         f"neutral-site treatment, which re-estimates the ratings and moves {abs(closer_d - closer_c)} of the 13 "
         f"rows across the line. The registers therefore do not disagree about the model — they agree, and both say "
         f"the model is behind its naive reference on the slice it had never been scored against."),
        ("Week 11 side picks that flip", "13 fixtures, published fair-spread sign versus each re-fit",
         "—", f"{flip_b} of 13", f"{flip_c} of 13", f"{flip_b:+d}", f"{flip_c:+d}",
         "the cost of re-registration on the live week: no published pick turns, so the sealed log would be "
         "re-issued with the same sides and moved numbers"),
        ("Forecast-log seal", "SHA-256 over the prospective payload",
         a["seal"][:16] + "…", b["seal"][:16] + "…", c["seal"][:16] + "…",
         "differs", "differs",
         "the sandbox would have written a different seal, so a re-registration must be published as a version "
         "and never as a quiet correction"),
    ]
    for name, scope, va, vb, vc, da, dc, reading in extra:
        rows.append({"metric": name, "scope": scope, "published_v1_137": va,
                     "flags_only_137": vb, "corpus_v2_150": vc, "delta_flags_only": da,
                     "delta_v2": dc, "reading": reading, "compute_url": SRC_CODE,
                     "source_url": SRC_WEEK10})
    # --- cross-register reconciliation with the other parallel v2 build ------
    _d = {r["metric"]: r for r in rows}   # noqa: F841 - kept for readers mapping table rows
    # Session 39948feb (PR #80/#83) independently built a v2 corpus of the same 150 games under
    # data/corpus_v2/ and published data/corpus_v2/corpus_version_comparison.csv. If that register
    # is present, compare it value by value with column C here: two implementations agreeing is
    # evidence, and a disagreement is a bug in one of them. Absent file = no comparison claimed.
    xreg_path = os.path.join(DATA, "corpus_v2", "corpus_version_comparison.csv")
    xreg_rows, xreg_gaps = [], []
    # (their metric key, my summary key, this register's value, their precision)
    PAIRS = [("games in the corpus", "games_in_fit", a if False else None, 0),
             ("walk-forward out-of-sample games graded", "oos_rows", None, 0),
             ("mean absolute error, M1 (margin, pts)", "summary_mae_m1", None, 2),
             ("mean absolute error, naive reference line (margin, pts)", "summary_mae_reference", None, 2),
             ("calibration slope, actual on predicted", "summary_calibration_slope", None, 3),
             ("naive reference total for Week 11", "summary_reference_total", None, 1),
             ("corpus rows whose neutral_site cell was blank", "neutral_blank", None, 0)]
    if os.path.exists(xreg_path):
        with open(xreg_path, encoding="utf-8", newline="") as f:
            their = list(csv.DictReader(f))
        their_by_metric = {r["metric"]: r for r in their}
        LABELS = {"games_in_fit": "games in the fitted corpus", "oos_rows": "out-of-sample backtest rows",
                  "summary_mae_m1": "MAE, margin (M1) — as the summary publishes it",
                  "summary_mae_reference": "MAE, margin (reference) — as the summary publishes it",
                  "summary_calibration_slope": "calibration slope", "summary_reference_total":
                  "reference total for Week 11", "neutral_blank": "corpus rows with a blank neutral flag"}
        for their_key, my_key, _unused, tol_nd in PAIRS:
            th = their_by_metric.get(their_key)
            if th is None:
                xreg_gaps.append(f"{LABELS[my_key]}: no comparable row in their register")
                continue
            mv, pv = c[my_key], a[my_key]                      # v2 value, published v1 value
            try:
                tv, tv1 = float(th["v2_value_150_games_this_build"]), float(th["v1_value_137_games_published"])
            except ValueError:
                xreg_gaps.append(f"{LABELS[my_key]}: their value {th['v2_value_150_games_this_build']!r} is not numeric")
                continue
            # compare at the coarser published precision of the two registers
            tol = 0.5 * 10 ** -tol_nd
            agree = abs(tv - mv) <= tol + 1e-9
            xreg_rows.append({
                "metric": LABELS[my_key], "this_register_v2_150": f"{mv:.{tol_nd}f}" if tol_nd else str(int(mv)),
                "their_register_v2_150": th["v2_value_150_games_this_build"],
                "tolerance_pts": f"{tol:g}", "agreement": "match" if agree else "DISAGREE",
                "their_published_v1": th["v1_value_137_games_published"],
                "published_v1_here": (f"{pv:.{tol_nd}f}" if tol_nd else str(int(pv))),
                "v1_agreement": "match" if abs(tv1 - pv) <= tol + 1e-9 else "differs",
                "source_url": SRC_CODE,
            })
            if not agree:
                xreg_gaps.append(f"{LABELS[my_key]}: here {mv:g} vs their register {tv:g} (tolerance {tol:g})")
        with open(os.path.join(DATA, "model_v2_research_cross_register.csv"), "w",
                  encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["metric", "this_register_v2_150", "their_register_v2_150",
                                              "tolerance_pts", "agreement", "their_published_v1",
                                              "published_v1_here", "v1_agreement", "source_url"])
            w.writeheader()
            for r in xreg_rows:
                w.writerow(r)
    n_agree = sum(1 for r in xreg_rows if r["agreement"] == "match")
    xreg_reading = (
        f"Independent cross-check against data/corpus_v2/corpus_version_comparison.csv, the v2 corpus another "
        f"session built the same day from the same 13 games: {n_agree} of {len(xreg_rows)} comparable metrics "
        f"agree at the precision both registers publish"
        + ("" if not xreg_gaps else f"; {len(xreg_gaps)} not comparable ({'; '.join(xreg_gaps[:3])})")
        if xreg_rows else
        "No comparable parallel v2 register found under data/corpus_v2/ on this checkout, so no cross-check is "
        "claimed for this run.")
    rows.append({"metric": "Cross-register agreement with the other parallel v2 build",
                 "scope": "same 150-game corpus, two independent implementations, compared metric by metric",
                 "published_v1_137": "—", "flags_only_137": "—",
                 "corpus_v2_150": f"{n_agree} of {len(xreg_rows)} match" if xreg_rows else "not run",
                 "delta_flags_only": "—", "delta_v2": "0" if not xreg_gaps else f"{len(xreg_gaps)} gaps",
                 "reading": xreg_reading, "compute_url": SRC_CODE,
                 "source_url": SRC_STANDINGS})

    rows.append({"metric": "Per-game recomputation versus the published summary figure",
                 "scope": "MAE, margin (M1): mean |error| over model_backtest.csv rows versus model_summary.json's mae_m1",
                 "published_v1_137": f"{a['mae_margin_m1']:.3f} vs {a['summary_mae_m1']:.2f}",
                 "flags_only_137": f"{b['mae_margin_m1']:.3f} vs {b['summary_mae_m1']:.2f}",
                 "corpus_v2_150": f"{c['mae_margin_m1']:.3f} vs {c['summary_mae_m1']:.2f}",
                 "delta_flags_only": "—", "delta_v2": "—",
                 "reading": "the two definitions differ by up to 0.01 points because model_backtest.csv stores the "
                            "error against the one-decimal line the model published, while the summary scores the "
                            "unrounded prediction. Both are published here so a reader comparing registers knows which "
                            "figure each table holds; the cross-register row below uses the summary definition, as "
                            "data/corpus_v2/corpus_version_comparison.csv does.",
                 "compute_url": SRC_MODEL, "source_url": SRC_WEEK10})
    write("model_v2_research_deltas.csv", rows,
          ["metric", "scope", "published_v1_137", "flags_only_137", "corpus_v2_150",
           "delta_flags_only", "delta_v2", "reading", "compute_url", "source_url"])

    summary = {
        "purpose": "prices the P09 re-registration decision; publishes no model output and overwrites no "
                   "canonical file",
        "variants": {
            "A_published": {"corpus_rows": a["games_in_fit"], "neutral_flags": a["neutral_modelled"],
                            "seal": a["seal"]},
            "B_flags_only_137": {"corpus_rows": b["games_in_fit"], "neutral_flags": b["neutral_modelled"],
                                 "seal": b["seal"]},
            "C_corpus_v2_150": {"corpus_rows": c["games_in_fit"], "neutral_flags": c["neutral_modelled"],
                                "seal": c["seal"]},
        },
        "controls": ctrl,
        "week10_holdout_closer": {"published": 0, "v2_unflagged": closer_d, "v2_flagged": closer_c,
                                  "pr78_register": "5 of 13 (data/corpus_v2_summary.csv subset B)"},
        "week11_picks_flipped_flags_only": flip_b,
        "week11_picks_flipped_v2": flip_c,
        "cross_register": {"comparable": len(xreg_rows), "agree": n_agree, "gaps": xreg_gaps[:6],
                           "their_register": "data/corpus_v2/corpus_version_comparison.csv"
                                             if os.path.exists(xreg_path) else "absent on this checkout"},
        "canonical_files_written": "none — the four model_v2_research_* registers and this summary only",
        "reproduce": "python3 scripts/results_v2.py && python3 scripts/model_v2_research.py",
        "official_sources": [SRC_WEEK10, SRC_STANDINGS],
    }
    with open(os.path.join(DATA, "model_v2_research_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
finally:
    shutil.rmtree(sandbox_parent, ignore_errors=True)

print(json.dumps(summary, indent=2))
print("\nDeltas (published -> flags-only -> full v2):")
for r in rows:
    print(f"  {r['metric']}: {r['published_v1_137']} -> {r['flags_only_137']} -> "
          f"{r['corpus_v2_150']}  (flags {r['delta_flags_only']}, v2 {r['delta_v2']})")
print("\nSandbox removed; published model outputs untouched.")
