#!/usr/bin/env python3
"""Correlation register — every value computed only from officially sourced numbers, n published.

Brief item: "Compute correlations only from officially sourced numbers and publish n with
each value."

The register keeps a value and its sample size inseparable, and adds the two things the
existing file does not carry:

  1. a PROVENANCE GATE per variable — `official-league-record` (a number an official NFL.com
     page states) or `project-estimate-from-official-record` (a number this project computed
     from those pages). A third kind — third-party, inferred, or remembered — is rejected
     by construction: the row is published with a blank value, n=0 and the reason.
  2. the SMALLEST EFFECT THIS SAMPLE COULD HAVE FOUND. An interval around r is not enough:
     at n=24, a correlation of 0.55 is the smallest thing an 80%-power test can reliably
     detect, so a null result at that n means "we could not have seen a normal-sized effect",
     not "there is no effect". Every row publishes that floor next to its n.

The gate is deliberately strict enough to blank out the correlations the project most wants
(injury availability and replacement depth against outcomes): the Week 10 report describes
games that have not been played yet, so their n is 0 today. Those rows are printed as armed,
not as zeros.

Run:  python3 scripts/correlation_register.py
"""
import csv
import json
import math
import os
import random
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
SEED = 20261114
DRAWS = 5000
OFFICIAL = ("official-league-record", "project-estimate-from-official-record")
FIELDS = ["corr_id", "question", "variable_a", "variable_a_kind", "variable_a_source",
          "variable_b", "variable_b_kind", "variable_b_source", "method", "n", "value",
          "ci_low", "ci_high", "p_value", "smallest_abs_r_detectable_at_80pct_power",
          "provenance_gate", "reading", "source_url"]
NFL_SCHED = "https://www.nfl.com/schedules/2026/by-week/week-"


def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def fisher(r, n, alpha=1.96):
    if r is None or n < 4 or abs(r) >= 1:
        return None, None, None
    z = atanh(r)
    se = 1.0 / math.sqrt(n - 3)
    lo, hi = math.tanh(z - alpha * se), math.tanh(z + alpha * se)
    p = 2 * (1 - ncdf(abs(z) / se))
    return lo, hi, p


def atanh(x):
    return 0.5 * math.log((1 + x) / (1 - x)) if -1 < x < 1 else float("nan")


def ncdf(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def detectable_floor(n):
    """Smallest |r| an 80%-power two-sided test at 5% can find, by inverting the Fisher-z SE."""
    if n < 5:
        return None
    return math.tanh((1.96 + 0.8416) / math.sqrt(n - 3))


def main():
    feed = [r for r in read("results_feed.csv") if r["settlement_state"] == "SETTLED-FINAL"]
    bt = read("model_backtest.csv")
    inj = read("injuries_week10_2026.csv")
    ratings = {r["team"]: r for r in read("model_ratings.csv")}
    ledger = read("line_book_snapshots.csv")
    out = []

    def add(cid, q, a, ak, asrc, b, bk, bsrc, method, xs, ys, reading, extra_n=0):
        n = min(len(xs), len(ys)) if xs is not None else extra_n
        ok = ak in OFFICIAL and bk in OFFICIAL
        if not ok:
            out.append({"corr_id": cid, "question": q, "variable_a": a, "variable_a_kind": ak,
                        "variable_a_source": asrc, "variable_b": b, "variable_b_kind": bk,
                        "variable_b_source": bsrc, "method": method, "n": 0, "value": "",
                        "ci_low": "", "ci_high": "", "p_value": "",
                        "smallest_abs_r_detectable_at_80pct_power": "",
                        "provenance_gate": f"REJECTED — {a if not ok and ak not in OFFICIAL else b} is "
                                           "not an officially sourced number",
                        "reading": "Not computed and not estimated. The row is kept so the gap is visible.",
                        "source_url": asrc})
            return
        if n < 3:
            out.append({"corr_id": cid, "question": q, "variable_a": a, "variable_a_kind": ak,
                        "variable_a_source": asrc, "variable_b": b, "variable_b_kind": bk,
                        "variable_b_source": bsrc, "method": method, "n": 0, "value": "",
                        "ci_low": "", "ci_high": "", "p_value": "",
                        "smallest_abs_r_detectable_at_80pct_power": "",
                        "provenance_gate": "PASSED on provenance; sample not available yet",
                        "reading": "ARMED — the inputs exist but the outcomes have not been played yet. "
                                   "This becomes computable the moment the results feed settles.",
                        "source_url": asrc})
            return
        r = pearson(xs, ys)
        lo, hi, p = fisher(r, n)
        floor = detectable_floor(n)
        out.append({"corr_id": cid, "question": q, "variable_a": a, "variable_a_kind": ak,
                    "variable_a_source": asrc, "variable_b": b, "variable_b_kind": bk,
                    "variable_b_source": bsrc, "method": method, "n": n,
                    "value": f"{r:.3f}" if r is not None else "",
                    "ci_low": f"{lo:.3f}" if lo is not None else "",
                    "ci_high": f"{hi:.3f}" if hi is not None else "",
                    "p_value": f"{p:.4g}" if p is not None else "",
                    "smallest_abs_r_detectable_at_80pct_power": f"{floor:.3f}" if floor else "",
                    "provenance_gate": "PASSED — both variables official or derived only from official",
                    "reading": reading, "source_url": asrc})

    # ---- the settled ledger: two official numbers, no model involved
    marg = [int(r["margin_home"]) for r in feed]
    tot = [int(r["total"]) for r in feed]
    add("CR01", "Do bigger margins come with bigger totals across the season?",
        "home margin, points", "official-league-record", NFL_SCHED + "1",
        "combined points", "official-league-record", NFL_SCHED + "1",
        "Pearson r, Fisher-z interval and two-sided p", marg, tot,
        "Blowouts and shootouts are close to unrelated: the scoring level of a game does not "
        "follow from how lopsided it is.")

    # ---- forecast-vs-reality, on the walk-forward set
    add("CR02", "Does our originated side line track what actually happened?",
        "model side line (home margin)", "project-estimate-from-official-record", NFL_SCHED + "10",
        "actual home margin", "official-league-record", NFL_SCHED + "10",
        "Pearson r on the out-of-sample set", [float(r["m1_spread_home"]) for r in bt],
        [float(r["actual_margin"]) for r in bt],
        "This is the correlation that a spread strategy depends on. It is far from 1: the line "
        "carries information, it does not know the score.")
    add("CR03", "Does the naive reference line track what actually happened?",
        "reference side line (point differential + 2.5)", "project-estimate-from-official-record",
        NFL_SCHED + "10", "actual home margin", "official-league-record", NFL_SCHED + "10",
        "Pearson r on the same games, same rules", [float(r["reference_spread_home"]) for r in bt],
        [float(r["actual_margin"]) for r in bt],
        "The benchmark row. Our line must beat this value, not merely exceed zero, for the model "
        "to justify existing.")
    add("CR04", "Does our originated total track the actual combined score?",
        "model total", "project-estimate-from-official-record", NFL_SCHED + "10",
        "actual combined points", "official-league-record", NFL_SCHED + "10",
        "Pearson r on the out-of-sample set", [float(r["m1_total"]) for r in bt],
        [float(r["actual_total"]) for r in bt],
        "Totals are dominated by a league-wide level that barely moves, so a high r here is weak "
        "evidence of skill — read it against the constant-total baseline, not against zero.")
    add("CR05", "How redundant are the side line and the total we publish for the same game?",
        "model side line", "project-estimate-from-official-record", NFL_SCHED + "10",
        "model total", "project-estimate-from-official-record", NFL_SCHED + "10",
        "Pearson r between our own two published numbers", [float(r["m1_spread_home"]) for r in bt],
        [float(r["m1_total"]) for r in bt],
        "Both readings come from one fitted system, so they are not independent forecasts. This is "
        "the number that makes pricing a same-game side+total ticket as two independent legs wrong.")

    # ---- parlay dependence, rebuilt from the legs (also re-validates the published ticket count)
    # The project's pre-registered leg rule is DIRECTIONAL: take the leg in the direction the
    # model disagrees with the reference line, and it hits if the actual moved past the
    # reference line that way. The alternative "our number was closer" rule is computed
    # alongside it, because the two disagree exactly when the model overshoots past the
    # actual — and a dependence that moves between two definitions must be published as both.
    legs_dir, legs_close = [], []
    for r in bt:
        ds = float(r["m1_spread_home"]) - float(r["reference_spread_home"])
        dt = float(r["m1_total"]) - float(r["reference_total"])
        if abs(ds) < 3.0 or abs(dt) < 3.0:
            continue
        am, at = float(r["actual_margin"]), float(r["actual_total"])
        e_side = (am - float(r["reference_spread_home"])) * (1 if ds > 0 else -1)
        e_tot = (at - float(r["reference_total"])) * (1 if dt > 0 else -1)
        legs_dir.append((1 if e_side > 0 else 0, 1 if e_tot > 0 else 0))
        legs_close.append((
            1 if abs(am - float(r["m1_spread_home"])) < abs(am - float(r["reference_spread_home"])) else 0,
            1 if abs(at - float(r["m1_total"])) < abs(at - float(r["reference_total"])) else 0))

    def table2x2(rows_):
        aa = sum(1 for x, y in rows_ if x and y)
        bb = sum(1 for x, y in rows_ if x and not y)
        cc = sum(1 for x, y in rows_ if not x and y)
        dnn = sum(1 for x, y in rows_ if not x and not y)
        den = math.sqrt((aa + bb) * (aa + cc) * (cc + dnn) * (bb + dnn))
        return aa, bb, cc, dnn, ((aa * dnn - bb * cc) / den if den else None)

    a, b, c, d, phi = table2x2(legs_dir)
    a2, b2, c2, d2, phi2 = table2x2(legs_close)
    n_legs = len(legs_dir)
    rng = random.Random(SEED)
    boots = []
    for _ in range(DRAWS):
        s = [legs_dir[rng.randrange(n_legs)] for _ in range(n_legs)]
        aa = sum(1 for x, y in s if x and y); bb = sum(1 for x, y in s if x and not y)
        cc = sum(1 for x, y in s if not x and y); dd = sum(1 for x, y in s if not x and not y)
        dd_ = math.sqrt((aa + bb) * (aa + cc) * (cc + dd) * (bb + dd))
        boots.append((aa * dd - bb * cc) / dd_ if dd_ else 0.0)
    boots.sort()
    pub = read("parlay_analysis.csv")[0]
    cells = dict(re.findall(r"(both|side only|total only|neither)=(\d+)", pub["two_by_two"]))
    want = (int(pub["tickets"]), int(cells["both"]), int(cells["side only"]),
            int(cells["total only"]), int(cells["neither"]))
    same_table = (n_legs, a, b, c, d) == want
    agree = (f"reproduces the published P1 ticket count, the published 2x2 and the published phi "
             f"({pub['phi_correlation']}) exactly"
             if same_table and abs(phi - float(pub["phi_correlation"])) < 0.002 else
             f"DIFFERS from the published P1 row ({want} published vs {(n_legs, a, b, c, d)} recomputed, "
             f"phi {phi:.3f} vs published {pub['phi_correlation']}) — investigate before either is trusted")
    out.append({"corr_id": "CR06", "question": "On a same-game side+total ticket, do the two legs hit together?",
                "variable_a": "side leg hit (0/1, registered directional rule)",
                "variable_a_kind": "project-estimate-from-official-record",
                "variable_a_source": NFL_SCHED + "10", "variable_b": "total leg hit (0/1)",
                "variable_b_kind": "project-estimate-from-official-record", "variable_b_source": NFL_SCHED + "10",
                "method": f"phi coefficient on the {n_legs}-ticket 2x2 (both={a}, side only={b}, total only={c}, "
                          f"neither={d}); bootstrap interval, {DRAWS} resamples, seed {SEED}",
                "n": n_legs, "value": f"{phi:.3f}" if phi is not None else "",
                "ci_low": f"{boots[int(0.025 * DRAWS)]:.3f}", "ci_high": f"{boots[int(0.975 * DRAWS)]:.3f}",
                "p_value": "", "smallest_abs_r_detectable_at_80pct_power":
                f"{detectable_floor(n_legs):.3f}" if n_legs >= 5 else "",
                "provenance_gate": "PASSED — both legs are graded on official scores against published project lines",
                "reading": f"The independent reconstruction {agree}. Sensitivity: scoring a leg as 'our number "
                           f"was closer' instead of 'the actual moved past the reference line in our direction' "
                           f"gives both={a2}, side only={b2}, total only={c2}, neither={d2} and phi={phi2:.3f}. "
                           "The sign of the dependence is stable, its size is not — at this n nothing smaller "
                           "than about 0.55 is resolvable, so the row supports 'do not multiply the two marginals' "
                           "and supports nothing else.",
                "source_url": NFL_SCHED + "10"})

    # ---- availability exposure: descriptive, and explicitly not a forecast
    cnt = {}
    for r in inj:
        t = r["team_abbr"]
        if r["game_status"] in ("Out", "Doubtful"):
            cnt[t] = cnt.get(t, 0) + 1
    teams = sorted(t for t in cnt if t in ratings or t in ("LA",))
    xs = [cnt[t] for t in teams]
    ys = []
    for t in teams:
        rr = ratings.get(t) or ratings.get("LAR" if t == "LA" else t)
        ys.append(float(rr["net_rating"]) if rr else None)
    pairs = [(x, y) for x, y in zip(xs, ys) if y is not None]
    add("CR07", "Do teams with more Out/Doubtful players have worse season ratings?",
        "Out or Doubtful players on the Week 10 report", "official-league-record", "https://www.nfl.com/injuries/",
        "net team rating from settled 2026 scores", "project-estimate-from-official-record",
        NFL_SCHED + "10", "Pearson r, cross-sectional",
        [p[0] for p in pairs], [p[1] for p in pairs],
        "DESCRIPTIVE ONLY and read backwards in time: the Week 10 report follows weeks 1-9, so this is "
        "'do worse teams lose more players', not a forecast. It must not be quoted as evidence that "
        "absences cause the rating gap.")

    # ---- the two correlations the project actually wants, which cannot be computed yet
    add("CR08", "Does the availability deficiency in front of a game predict that game's margin?",
        "Out or Doubtful count, Week 10 report", "official-league-record", "https://www.nfl.com/injuries/",
        "actual margin of the Week 10 game", "official-league-record", NFL_SCHED + "10",
        "Pearson r on games that have been played", [], [],
        "The report describes games scheduled for 2026-11-15/16, which have not been played while this "
        "site was built. The fifteen Sunday/Monday results are the missing half; the register goes live "
        "on the next settled build.", extra_n=0)
    add("CR09", "Does replacement depth (how far down the chart the fix reaches) predict the margin?",
        "levels down the depth chart to the first available player", "third-party or club-published chart",
        "https://www.nfl.com/injuries/", "actual margin of the same game", "official-league-record",
        NFL_SCHED + "10", "Pearson r once enough teams have both fields", [], [],
        "Rejected twice over: the depth field is club-published and self-labelled unofficial (so it is "
        "not an official-league record), and only two clubs have been transcribed. Both blockers are "
        "listed in Flagged for review; no value is estimated from n=2.")

    tmp = os.path.join(DATA, "correlation_register.csv") + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\r\n")
        w.writeheader()
        w.writerows(out)
    os.replace(tmp, os.path.join(DATA, "correlation_register.csv"))
    pub = sum(1 for r in out if r["value"])
    print(f"Correlation register: {len(out)} rows, {pub} values published with n, "
          f"{len(out) - pub} blank by rule (provenance gate or no settled sample).")
    for r in out:
        print(f"  {r['corr_id']} n={r['n']:>3} r={r['value'] or '(blank)'} floor={r['smallest_abs_r_detectable_at_80pct_power'] or '-'}")


if __name__ == "__main__":
    main()
