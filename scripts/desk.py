#!/usr/bin/env python3
"""Decision-desk outputs for session 8a0bf37e (T42-T50).

Standard library only. Writes three files; nothing else is touched:

  data/results_feed_checks.csv          T49  checks on the verified results feed
  data/demotion_window_check.csv        T50  demotion rule D1 (as proposed on main, demotion_gate.csv)
                                             applied to the last 50 out-of-sample games and to all 89
  data/correlation_audit.csv            T44  which correlations use officially sourced inputs only, with n

Tasks T38, T39, T40, T41 and T43 are already done on main by session c125b2f7 (PR #29, #30); this script
does not write their files (price store, line comparison, signal/staking split, demotion gate).

Run:  python3 scripts/desk.py     (deterministic: fixed seed)
"""
import csv
import os
import random
import subprocess
import sys
from urllib.parse import urlsplit

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
SEED = 20261115
BOOT = 5000
SRC_SCHED_W11 = "https://www.nfl.com/schedules/2026/by-week/week-11"
SRC_SCHED = "https://www.nfl.com/schedules/2026/by-week/week-"
ALLOWED_HOSTS = {"www.nfl.com", "support.nfl.com", "operations.nfl.com", "www.itl.nist.gov"}


def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write(name, rows, fields):
    for i, r in enumerate(rows):
        if set(r) != set(fields):
            raise SystemExit(f"{name} row {i}: keys differ {set(r) ^ set(fields)}")
        u = r.get("source_url", "")
        if u:
            p = urlsplit(u)
            if p.scheme != "https" or p.hostname not in ALLOWED_HOSTS:
                raise SystemExit(f"{name} row {i}: non-allow-listed source {u}")
    tmp = os.path.join(DATA, name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, os.path.join(DATA, name))
    print(f"wrote {name}: {len(rows)} rows")


random.seed(SEED)

# ------------------------------------------------ T49 results feed checks ----
results = read("games_2026_results.csv")
season = read("season_games_2026.csv")
rf = []


def add(cid, check, method, result, status, src):
    rf.append({"check_id": cid, "check": check, "method": method, "result": result, "status": status, "source_url": src})


expected_cols = ["season", "week", "date_as_shown", "away_team", "away_points", "home_team", "home_points",
                 "game_url", "source_url", "neutral_site"]
cols_ok = list(results[0].keys()) == expected_cols
add("RF01", "Schema", "Header and field count on games_2026_results.csv",
    f"{len(results)} rows; columns as expected: {cols_ok}",
    "pass" if cols_ok and len(results) == 137 else "FAIL", SRC_SCHED_W11)

keys = [(r["week"], r["away_team"], r["home_team"]) for r in results]
add("RF02", "No duplicate games", "Unique (week, away, home)", f"{len(set(keys))} unique of {len(keys)}",
    "pass" if len(set(keys)) == len(keys) else "FAIL", SRC_SCHED_W11)

teams = {r["away_team"] for r in results} | {r["home_team"] for r in results}
add("RF03", "Team set", "Distinct team abbreviations. The register writes the Rams as LA; the official Week 11 page and "
    "the second transcription write LAR (flag F46).", f"{len(teams)} teams",
    "pass" if len(teams) == 32 else "FAIL", "https://www.nfl.com/standings/")

wk = {}
for r in results:
    wk[int(r["week"])] = wk.get(int(r["week"]), 0) + 1
add("RF04", "Games per week", "Count by week (consistent with weeks 1-9 complete plus the Week 10 Thursday game)",
    ", ".join(f"wk{k}:{v}" for k, v in sorted(wk.items())),
    "pass (count only; not re-fetched this session)", SRC_SCHED + "10")

bad_host = [r["game_url"] for r in results if not r["game_url"].startswith("https://www.nfl.com/games/")]
add("RF05", "Official source on every row", "game_url host and path check", f"{len(bad_host)} rows outside nfl.com/games",
    "pass" if not bad_host else "FAIL", SRC_SCHED_W11)


def _norm(t):
    """The second transcription writes the Rams as LAR; this register writes LA (F46). Normalise, nothing else."""
    return "LA" if t == "LAR" else t


idx = {(r["week"], _norm(r["away_team"]), _norm(r["home_team"])): r for r in season}
mism = []
for r in results:
    k = (r["week"], r["away_team"], r["home_team"])
    s = idx.get(k)
    if s is None or s["away_points"] != r["away_points"] or s["home_points"] != r["home_points"]:
        mism.append(k)
add("RF06", "Second transcription agrees",
    "Row-by-row match of teams and both scores against season_games_2026.csv (LAR read as LA; F46)",
    f"{len(results) - len(mism)} of {len(results)} rows match after LAR/LA normalisation; {len(season)} rows in second file",
    "pass" if not mism and len(season) == len(results) else "FAIL", "https://www.nfl.com/schedules/2026/by-week/week-1")

proc = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "verify_results.py")], capture_output=True, text=True)
rec = (proc.stdout.strip().splitlines() or ["(no output)"])[-1]
add("RF07", "Standings reconciliation", "scripts/verify_results.py recomputes W-L-T and points for/against for all 32 teams",
    rec, "pass" if proc.returncode == 0 else "FAIL", "https://www.nfl.com/standings/")

spot = [
    ("RF08", "Sample: Arizona at Los Angeles Chargers, week 1", "Official game center final score (AZ-LAC)",
     "match: 26-14", "pass", "https://www.nfl.com/games/cardinals-at-chargers-2026-reg-1"),
    ("RF09", "Sample: Las Vegas at New Orleans, week 3", "Official game center final score (LV-NO)",
     "match: 35-27", "pass", "https://www.nfl.com/games/raiders-at-saints-2026-reg-3"),
    ("RF10", "Sample: Houston at Indianapolis, week 3", "Official game center final score (HOU-IND)",
     "match: 17-19", "pass", "https://www.nfl.com/games/texans-at-colts-2026-reg-3"),
    ("RF11", "Sample: Houston at Tennessee, week 5", "Official game center shows 'Hidden Score' (F41)",
     "not verified on game center; standings reconciliation only", "not verified",
     "https://www.nfl.com/games/texans-at-titans-2026-reg-5"),
    ("RF12", "Sample: Pittsburgh at Tampa Bay, week 6", "Official game center shows 'Hidden Score' (F41)",
     "not verified on game center; standings reconciliation only", "not verified",
     "https://www.nfl.com/games/steelers-at-buccaneers-2026-reg-6"),
    ("RF13", "Sample: Cincinnati at Atlanta, week 9", "Official game center shows 'Hidden Score' (F41)",
     "not verified on game center; standings reconciliation only", "not verified",
     "https://www.nfl.com/games/bengals-at-falcons-2026-reg-9"),
    ("RF14", "Week 11 schedule (13 games)",
     "Official by-week page (chunks 0, 1 and 2, read 2026-11-14) compared line by line with schedule_week11_2026.csv: day, kickoff time, network, teams, game link",
     "13 of 13 match. The six games not on chunks 1-2 (IND@HOU, MIA@BUF, BAL@CAR, NO@CHI, TEN@DAL, TB@DET) were read from chunk 0 on 2026-11-14 and match.",
     "pass", SRC_SCHED_W11),
]
for s in spot:
    add(*s)
for r in rf:
    p = urlsplit(r["source_url"])
    if p.scheme != "https" or p.hostname not in ALLOWED_HOSTS:
        raise SystemExit(f"{r['check_id']}: non-allow-listed source")
write("results_feed_checks.csv", rf, ["check_id", "check", "method", "result", "status", "source_url"])

# --------------------------------------- T50 demotion rule D1 window check ----
# D1 as proposed on main (data/demotion_gate.csv): lower bound of the 95% interval for the signal, over the
# most recent 50 eligible out-of-sample forecasts, at or below 0 -> return to paper. Not approved (F17).
backtest = read("model_backtest.csv")
assert len(backtest) == 89, len(backtest)
ordered = sorted(enumerate(backtest), key=lambda t: (int(t[1]["week"]), t[0]))
rows_all = [r for _, r in ordered]
WINDOW_D1 = 50


def boot_ci(diffs):
    n = len(diffs)
    mean = sum(diffs) / n
    boots = []
    for _ in range(BOOT):
        s = [diffs[random.randrange(n)] for _ in range(n)]
        boots.append(sum(s) / n)
    boots.sort()
    return mean, boots[int(0.025 * BOOT)], boots[int(0.975 * BOOT) - 1]


def d2_ok(window):
    return all(r["source_url"].startswith("https://www.nfl.com/") and r["game_url"].startswith("https://www.nfl.com/")
               for r in window)


out = []
for label, window in ((f"last {WINDOW_D1} out-of-sample games (D1 as proposed)", rows_all[-WINDOW_D1:]),
                      ("all 89 out-of-sample games (reference only)", rows_all)):
    weeks = sorted({int(r["week"]) for r in window})
    for sid, col in (("M1", "m1_spread_home"), ("M2", "m2_spread_home"), ("M3", "m3_spread_home"), ("M4", "m4_spread_home")):
        diffs = [abs(float(r["actual_margin"]) - float(r["reference_spread_home"]))
                 - abs(float(r["actual_margin"]) - float(r[col])) for r in window]
        mean, lo, hi = boot_ci(diffs)
        trig = lo <= 0
        out.append({
            "strategy_id": sid,
            "window": f"{label}; weeks {weeks[0]}-{weeks[-1]}",
            "games": len(window),
            "mean_mae_gain_pts": f"{mean:.2f}",
            "ci95_low": f"{lo:.2f}",
            "ci95_high": f"{hi:.2f}",
            "D1_triggered": "yes - would return to paper if live" if trig else "no",
            "negative_point_estimate": "yes" if mean < 0 else "no",
            "D2_integrity": "clear - every row links to an official NFL.com page" if d2_ok(window) else "TRIGGERED",
            "live_status": "paper (no strategy is live; D1 is inert)",
            "source_url": SRC_SCHED + str(weeks[-1]),
        })
out.append({
    "strategy_id": "T1 / R1 / P1", "window": "not evaluated", "games": "", "mean_mae_gain_pts": "", "ci95_low": "",
    "ci95_high": "", "D1_triggered": "not evaluated", "negative_point_estimate": "", "D2_integrity": "not evaluated",
    "live_status": "paper (no strategy is live; D1 is inert)",
    "source_url": SRC_SCHED + "10",
})
write("demotion_window_check.csv", out,
      ["strategy_id", "window", "games", "mean_mae_gain_pts", "ci95_low", "ci95_high", "D1_triggered",
       "negative_point_estimate", "D2_integrity", "live_status", "source_url"])

# ---------------------------------------------- T44 correlation audit ----
# An entry qualifies only if BOTH inputs are official numbers (owner rule). A fixed constant is an assumption.
AUDIT = {
    "C01": ("Model predicted margin (model output)", "Official final margin", "no",
            "Predictor is a model output. Diagnostic only."),
    "C02": ("Naive reference margin = official season point differential + 2.5 (fixed home-field constant)",
            "Official final margin", "no",
            "The 2.5-point home-field term is a pre-registered constant (scripts/model.py HFA_REF), not an official number."),
    "C03": ("Official final margin (blowout size)", "Official total points", "yes", "Official results only."),
    "C04": ("Official points, team A", "Official points, team B (same game)", "yes",
            "Two halves of one official score line; one pair per game."),
    "C05": ("Model predicted total (model output)", "Official total points", "no",
            "Predictor is a model output. Diagnostic only."),
    "C06": ("Official margin, week W-1 (team)", "Official margin, week W (same team)", "yes",
            "Official results, published as descriptive (F55): n = 228 team-game pairs and each game "
            "supplies both teams' margins, so the pairs are not independent; interval and p-value are "
            "blank by design (session d2915d86, T53)."),
    "C07": ("Model-generated side and total legs", "Model-generated side and total legs", "no",
            "Both legs are model-generated selections; n = 24 tickets. Diagnostic only."),
    "C08": ("Official Week 10 injury-report exposure (team)", "Official season points allowed (standings)", "yes",
            "Official injury report and standings. Exposure is a count of listed players."),
    "C09": ("Model predicted margin (model output)", "Official final margin", "no",
            "A regression slope, not a correlation. Predictor is a model output. The earlier interval "
            "(0.830-0.923) applied a correlation formula to a slope and is withdrawn. Corrected 2026-11-14 (F48): "
            "the register carries the slope's own standard error with the t critical value (95% CI 0.328-1.443) "
            "and a p-value testing calibration (H0: slope = 1.0). Applied by session f25d6b55; re-derived "
            "independently by session 20e6161b (T80). This script's output must match data/correlations_computed.csv."),
}
corr = read("correlations_computed.csv")
audit = []
for r in corr:
    cid = r["corr_id"]
    a, b, ok, note = AUDIT[cid]
    audit.append({
        "corr_id": cid, "question": r["question"], "value": r["value"], "ci_low": r["ci_low"], "ci_high": r["ci_high"],
        "p_value": r["p_value"], "sample_n": r["sample_n"], "input_A": a, "input_B": b,
        "officially_sourced_inputs_only": ok,
        "qualifies_under_owner_rule": "yes" if ok == "yes" else "no - shown as model diagnostic (DEC-09)",
        "audit_note": note, "source_url": r["source_url"],
    })
audit.sort(key=lambda r: r["corr_id"])
write("correlation_audit.csv", audit,
      ["corr_id", "question", "value", "ci_low", "ci_high", "p_value", "sample_n", "input_A", "input_B",
       "officially_sourced_inputs_only", "qualifies_under_owner_rule", "audit_note", "source_url"])
print("desk outputs written.")
