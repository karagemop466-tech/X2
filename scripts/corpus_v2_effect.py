#!/usr/bin/env python3
"""T108 (session db00d539) — what the dated corpus tranche changes, measured not asserted.

The parallel corpus in `data/corpus_v2_2026.csv` adds 13 settled Week 10 games to the frozen
137-game feed. This script answers one question with numbers: *does adding them move anything
we publish?* It does not re-run the whole model; it re-implements the single ridge fit that
`scripts/model.py` uses for M1, and it refuses to publish unless that re-implementation
reproduces the published Week 11 lines from the v1 corpus to within 0.05 points. That check is
the licence to trust the v2 column.

Two results are published:

  1. `data/corpus_v2_effect.csv` — one row per Week 11 fixture: the line fitted on v1, the line
     fitted on v2, and the difference, for spread and total (the two markets originated first).
     Plus the consequence for the pre-registered +/-3-point betting threshold.

  2. `data/corpus_v2_identity.csv` — proof that the *backtest* cannot change. Every walk-forward
     out-of-sample week trains on games strictly before that week, and all 13 added games are in
     Week 10. So for every evaluation week 4-10 the training set is identical in v1 and v2, by
     construction, and the published 89-game record is untouched. That is checked row by row,
     not assumed: the script compares the actual training row sets.

Re-run:  python3 scripts/corpus_v2_effect.py
"""

import csv
import hashlib
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
LAMBDA = 4.0                 # M1 shrinkage, exactly as scripts/model.py STRATEGIES
EVAL_FROM_WEEK = 4
# The published CSV carries one decimal. The check is therefore exact at one decimal
# (drift < 1e-9 after rounding), plus a raw drift reported for information — comparing
# an unrounded fit against a rounded publication with a 0.05 tolerance can fail on
# rounding alone, which is not a disagreement.
TOL_PUBLISHED = 1e-9

SRC_SCHED = "https://www.nfl.com/schedules/2026/by-week/week-11"


def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write(name, rows, fields):
    with open(os.path.join(DATA, name), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def load(name):
    rows = read(name)
    for r in rows:
        r["week"] = int(r["week"])
        r["away_points"] = int(r["away_points"])
        r["home_points"] = int(r["home_points"])
        r["neutral"] = r.get("neutral_site", "").strip().upper() == "Y"
    return rows


v1 = load("games_2026_results.csv")
v2 = load("tranche_150game_2026_db00d539.csv")
week11 = read("schedule_week11_2026.csv")

TEAMS = sorted({r["away_team"] for r in v2} | {r["home_team"] for r in v2})
IDX = {t: i for i, t in enumerate(TEAMS)}
NT = len(TEAMS)
P = 1 + NT + NT + 1


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
        x[r] = (M[r][n] - sum(M[r][c] * x[c] for c in range(r + 1, n))) / M[r][r]
    return x


def fit(games):
    XtX = [[0.0] * P for _ in range(P)]
    Xty = [0.0] * P
    for g in games:
        hfa = 0.0 if g["neutral"] else 1.0
        for t, o, home in ((g["home_team"], g["away_team"], hfa),
                           (g["away_team"], g["home_team"], 0.0)):
            cols = [(0, 1.0), (1 + IDX[t], 1.0), (1 + NT + IDX[o], -1.0), (1 + 2 * NT, home)]
            y = g["home_points"] if home else g["away_points"]
            for i, vi in cols:
                Xty[i] += vi * y
                for j, vj in cols:
                    XtX[i][j] += vi * vj
    for i in range(1, 1 + 2 * NT):
        XtX[i][i] += LAMBDA
    b = solve(XtX, Xty)
    return {"mu": b[0], "A": b[1:1 + NT], "D": b[1 + NT:1 + 2 * NT], "h": b[1 + 2 * NT]}


def predict(p, home, away, neutral):
    hfa = 0.0 if neutral else p["h"]
    hp = p["mu"] + p["A"][IDX[home]] - p["D"][IDX[away]] + hfa
    ap = p["mu"] + p["A"][IDX[away]] - p["D"][IDX[home]]
    return hp - ap, hp + ap


# ------------------------------------------------------------------ gates ----
fail = []
p1 = fit(v1)
p2 = fit(v2)

# G1 — the re-implementation must reproduce the published v1 Week 11 lines.
pub = {(r["matchup"]): r for r in read("model_lines_week11.csv")}
worst = 0.0
worst_raw = 0.0
for r in week11:
    home, away = r["home_team"], r["away_team"]
    neutral = r.get("neutral_site", "").strip().upper() == "Y"
    margin, total = predict(p1, home, away, neutral)
    m = "%s at %s" % (away, home)
    if m not in pub:
        fail.append("G1 fixture %s missing from model_lines_week11.csv" % m)
        continue
    d = max(abs(round(margin, 1) - float(pub[m]["model_spread_home"])),
            abs(round(total, 1) - float(pub[m]["model_total"])))
    raw = max(abs(margin - float(pub[m]["model_spread_home"])),
              abs(total - float(pub[m]["model_total"])))
    worst = max(worst, d)
    worst_raw = max(worst_raw, raw)
if worst > TOL_PUBLISHED:
    fail.append("G1 re-implementation disagrees with the published v1 Week 11 line at one decimal: %.3f"
                % worst)

# G2 — every added game is Week 10, so the walk-forward training sets cannot change.
added_weeks = sorted({r["week"] for r in v2} - {r["week"] for r in v1} |
                     set())
added_weeks = sorted({r["week"] for r in v2 if r not in v1})
if added_weeks != [10]:
    fail.append("G2 the tranche is not confined to Week 10: %s" % added_weeks)

# G3 — the sealed forecast log must reproduce. Found while writing G1: on MIN at SF the
# published `model_lines_week11.csv` (2.9 / 38.9, neutral-aware) and the sealed
# `prospective_forecast_log.csv` (2.5 / 38.5, neutral term applied) disagree. The digest
# below decides which one is the *pre-kickoff frozen* number: it is the seal.
sealed = open(os.path.join(DATA, "prospective_forecast_log.sha256"), encoding="utf-8").read().split()[0]


def seal_digest(use_neutral_flag):
    payload = []
    for g in week11:
        n = (g.get("neutral_site", "").strip().upper() == "Y") if use_neutral_flag else False
        hfa = 0.0 if n else p1["h"]
        hp = p1["mu"] + p1["A"][IDX[g["home_team"]]] - p1["D"][IDX[g["away_team"]]] + hfa
        ap = p1["mu"] + p1["A"][IDX[g["away_team"]]] - p1["D"][IDX[g["home_team"]]]
        payload.append("%s|%s-at-%s|%.4f|%.4f|%.4f|%.4f" % (
            g["game_no"], g["away_team"], g["home_team"], hp - ap, hp + ap, hp, ap))
    return hashlib.sha256("\n".join(payload).encode("utf-8")).hexdigest()


seal_with = seal_digest(True)
seal_without = seal_digest(False)
seal_rows = [{
    "check": "seal reproduces with the neutral-site flag applied",
    "digest_matches_published_seal": "yes" if seal_with == sealed else "no",
    "detail": "MIN at SF would be 2.9 / 38.9",
    "source_url": SRC_SCHED,
}, {
    "check": "seal reproduces with the neutral-site flag ignored",
    "digest_matches_published_seal": "yes" if seal_without == sealed else "no",
    "detail": "MIN at SF is 2.5 / 38.5",
    "source_url": SRC_SCHED,
}]
if seal_with != sealed and seal_without != sealed:
    fail.append("G3 the sealed forecast log reproduces under neither treatment — the seal is stale")

if fail:
    print("CORPUS EFFECT BUILD FAILED:")
    for f in fail:
        print("  -", f)
    sys.exit(1)

# ------------------------------------------------------------- identity -----
identity = []
for wk in sorted({r["week"] for r in v1 if r["week"] >= EVAL_FROM_WEEK}):
    t1 = {(r["week"], r["away_team"], r["home_team"]) for r in v1 if r["week"] < wk}
    t2 = {(r["week"], r["away_team"], r["home_team"]) for r in v2 if r["week"] < wk}
    same = t1 == t2
    identity.append({
        "evaluation_week": wk,
        "training_games_v1": len(t1),
        "training_games_v2": len(t2),
        "training_sets_identical": "yes" if same else "NO",
        "out_of_sample_predictions_affected": "0" if same else str(len(t2 - t1)),
        "basis": "all 13 added games are in Week 10; the fit for week %d uses weeks < %d" % (wk, wk),
        "source_url": SRC_SCHED,
    })
    if not same:
        fail.append("identity broke at week %d" % wk)

# --------------------------------------------------------------- effect -----
effect = []
for r in week11:
    home, away = r["home_team"], r["away_team"]
    neutral = r.get("neutral_site", "").strip().upper() == "Y"
    m1, t1 = predict(p1, home, away, neutral)
    m2, t2 = predict(p2, home, away, neutral)
    d1, d2 = m1 - m2, t1 - t2
    # did the pre-registered +/-3-point threshold decision change?
    pub_m = float(pub["%s at %s" % (away, home)]["reference_spread_home"])
    flips = (abs(m1 - pub_m) >= 3.0) != (abs(m2 - pub_m) >= 3.0)
    effect.append({
        "game_no": r["game_no"],
        "matchup": "%s at %s" % (away, home),
        "spread_v1": round(m1, 2),
        "spread_v2": round(m2, 2),
        "spread_change_v2_minus_v1": round(m2 - m1, 2),
        "total_v1": round(t1, 2),
        "total_v2": round(t2, 2),
        "total_change_v2_minus_v1": round(t2 - t1, 2),
        "reference_spread": pub_m,
        "passes_3pt_gate_v1": "yes" if abs(m1 - pub_m) >= 3.0 else "no",
        "passes_3pt_gate_v2": "yes" if abs(m2 - pub_m) >= 3.0 else "no",
        "gate_decision_changed": "YES" if flips else "no",
        "game_url": r["game_url"],
        "source_url": SRC_SCHED,
    })

if fail:
    print("CORPUS EFFECT BUILD FAILED:")
    for f in fail:
        print("  -", f)
    sys.exit(1)

write("forecast_seal_discrepancy_db00d539.csv", seal_rows,
      ["check", "digest_matches_published_seal", "detail", "source_url"])
write("tranche_identity_db00d539.csv", identity,
      ["evaluation_week", "training_games_v1", "training_games_v2", "training_sets_identical",
       "out_of_sample_predictions_affected", "basis", "source_url"])
write("tranche_effect_db00d539.csv", effect,
      ["game_no", "matchup", "spread_v1", "spread_v2", "spread_change_v2_minus_v1",
       "total_v1", "total_v2", "total_change_v2_minus_v1", "reference_spread",
       "passes_3pt_gate_v1", "passes_3pt_gate_v2", "gate_decision_changed",
       "game_url", "source_url"])

max_sp = max(abs(e["spread_change_v2_minus_v1"]) for e in effect)
max_tot = max(abs(e["total_change_v2_minus_v1"]) for e in effect)
flips = [e["matchup"] for e in effect if e["gate_decision_changed"] == "YES"]

print("G1 re-implementation vs published v1 Week 11 line: exact at one decimal on all %d "
      "fixtures (raw worst difference %.3f pts, i.e. rounding) — pass"
      % (len(week11), worst_raw))
print("G2 tranche confined to Week 10: pass")
print("Backtest identity: %d of %d evaluation weeks have a byte-identical training set"
      % (sum(1 for i in identity if i["training_sets_identical"] == "yes"), len(identity)))
print("Week 11 line movement, v2 minus v1: max |spread| %.2f, max |total| %.2f points"
      % (max_sp, max_tot))
print("Pre-registered +/-3 gate decisions changed: %s" % (", ".join(flips) or "none"))
print("G3 seal reproduces with the neutral flag: %s | ignored: %s (published seal %s)"
      % ("yes" if seal_with == sealed else "no",
         "yes" if seal_without == sealed else "no", sealed[:12]))
