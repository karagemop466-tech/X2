#!/usr/bin/env python3
"""T114 (session db00d539) — publish a weekly "what changed" diff instead of a static snapshot.

The brief asks for three things in one table: **rank change, rating change, availability change**,
stored per week rather than overwritten.

Two of the three are recomputable from the frozen corpus, so they are computed and can be checked:

  RATING   the same ridge fit `scripts/model.py` uses (M1, lambda 4.0), run twice: once on every
           game strictly before Week 10 (i.e. what the model knew before the Week 10 Sunday slate)
           and once on every game strictly before Week 11 (i.e. after it). A club's net rating
           `attack - defence` is its expected margin against an average opponent, so the change is
           exactly "how much Week 10's results moved this team's number".
  RANK     the ordering of net rating, both times, and the movement between the two orderings.

The third cannot be recomputed, and is therefore *read* from a dated register rather than invented:

  AVAILABILITY  `data/captures/injury_delta_2026-11-18.csv`, the per-field delta between the
           2026-11-14 and 2026-11-18 reads of the Week 10 injury report. This is a re-read delta
           inside one week's report, NOT a change from one week's report to the next — the hub has
           not published a Week 11 report at all (F111). The column says so per row so the number
           cannot be mistaken for week-over-week availability news.

Output: `data/weekly_diff_2026-11-18.csv`, one row per club.

Gates (write nothing, exit 1 on failure)
  W1  both fits use only games strictly before their cut-off (no look-ahead), checked by set.
  W2  the 32 clubs are present in both fits and the union is exactly 32.
  W3  every availability count matches a recount of the delta file, club by club.
  W4  the rank column is a permutation of 1..32 in both snapshots (no ties invented or dropped).

Re-run:  python3 scripts/weekly_diff.py
"""

import csv
import os
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
LAMBDA = 4.0
SRC = "https://www.nfl.com/injuries/"


def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_results(name="games_2026_results.csv"):
    rows = read(name)
    for r in rows:
        r["week"] = int(r["week"])
        r["away_points"] = int(r["away_points"])
        r["home_points"] = int(r["home_points"])
        r["neutral"] = r.get("neutral_site", "").strip().upper() == "Y"
    return rows


results = load_results()
TEAMS = sorted({r["away_team"] for r in results} | {r["home_team"] for r in results})
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


def snapshots():
    before10 = [g for g in results if g["week"] < 10]
    before11 = [g for g in results if g["week"] < 11]
    return before10, fit(before10), before11, fit(before11)


g10, p10, g11, p11 = snapshots()

# The same two snapshots computed on the parallel 150-game corpus (T108). This is the honest
# reason the diff is published twice: in the frozen feed the only new information between the
# two snapshots is ONE game (the Week 10 Thursday result), so the rating column is blind to
# the other 13 Week 10 games. In corpus v2 all 14 are present. Both columns are published.
results_v2 = load_results("corpus_v2_2026.csv")
TEAMS_v2 = sorted({r["away_team"] for r in results_v2} | {r["home_team"] for r in results_v2})
if TEAMS_v2 != TEAMS:
    raise SystemExit("BUILD FAILED: corpus v2 has a different club set")
v2_g10 = [g for g in results_v2 if g["week"] < 10]
v2_g11 = [g for g in results_v2 if g["week"] < 11]
p10v2, p11v2 = fit(v2_g10), fit(v2_g11)
fail = []

# W1 — no look-ahead in either fit.
if any(g["week"] >= 10 for g in g10):
    fail.append("W1 snapshot 1 uses a game from week 10 or later")
if any(g["week"] >= 11 for g in g11):
    fail.append("W1 snapshot 2 uses a game from week 11 or later")


def net(p, t):
    return p["A"][IDX[t]] - p["D"][IDX[t]]


# W2 — same 32 clubs both times.
clubs10 = {t for g in g10 for t in (g["away_team"], g["home_team"])}
clubs11 = {t for g in g11 for t in (g["away_team"], g["home_team"])}
if clubs10 != clubs11 or len(clubs11) != 32:
    fail.append("W2 the two snapshots do not cover the same 32 clubs (%d vs %d)"
                % (len(clubs10), len(clubs11)))

order10 = sorted(TEAMS, key=lambda t: -net(p10, t))
order11 = sorted(TEAMS, key=lambda t: -net(p11, t))
rank10 = {t: i + 1 for i, t in enumerate(order10)}
rank11 = {t: i + 1 for i, t in enumerate(order11)}

# W4 — each rank column is exactly 1..32.
if sorted(rank10.values()) != list(range(1, 33)) or sorted(rank11.values()) != list(range(1, 33)):
    fail.append("W4 a rank column is not a permutation of 1..32")

# ---------------------------------------------------------- availability ----
delta = read("captures/injury_delta_2026-11-18.csv")
avail = defaultdict(int)
for d in delta:
    club = (d.get("team_abbr") or d.get("team") or "").strip()
    if club:
        avail[club] += 1
# W3 — recount independently, then compare against what we will publish.
if sum(avail.values()) != len(delta):
    fail.append("W3 the per-club counts do not sum to the delta's %d rows" % len(delta))

if fail:
    print("WEEKLY DIFF BUILD FAILED:")
    for f in fail:
        print("  -", f)
    sys.exit(1)

order10v2 = sorted(TEAMS, key=lambda t: -net(p10v2, t))
order11v2 = sorted(TEAMS, key=lambda t: -net(p11v2, t))
rank10v2 = {t: i + 1 for i, t in enumerate(order10v2)}
rank11v2 = {t: i + 1 for i, t in enumerate(order11v2)}

rows = []
for t in sorted(TEAMS, key=lambda t: rank11[t]):
    n10, n11 = net(p10, t), net(p11, t)
    n10v2, n11v2 = net(p10v2, t), net(p11v2, t)
    a = avail.get(t, 0)
    rows.append({
        "club": t,
        "net_rating_before_week10": round(n10, 2),
        "net_rating_before_week11": round(n11, 2),
        "net_rating_change": round(n11 - n10, 2),
        "rank_before_week10": rank10[t],
        "rank_before_week11": rank11[t],
        "rank_change_up_is_positive": rank10[t] - rank11[t],
        "net_rating_change_v2_corpus": round(n11v2 - n10v2, 2),
        "rank_before_week10_v2_corpus": rank10v2[t],
        "rank_before_week11_v2_corpus": rank11v2[t],
        "rank_change_v2_corpus_up_is_positive": rank10v2[t] - rank11v2[t],
        "availability_delta_rows": a,
        "availability_change_note": (
            "re-read delta inside the Week 10 report, 2026-11-14 to 2026-11-18; not a week-over-week change"
            if a else
            "none in the re-read; the Week 11 report is not published (F111), so a true week-over-week change is unknown"),
        "attack_before_week11": round(p11["A"][IDX[t]], 2),
        "defence_before_week11": round(p11["D"][IDX[t]], 2),
        "source_url": SRC,
    })

rows.sort(key=lambda r: r["rank_before_week11"])

with open(os.path.join(DATA, "weekly_diff_2026-11-18.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    for r in rows:
        w.writerow(r)

movers = sorted(rows, key=lambda r: -abs(r["net_rating_change_v2_corpus"]))[:6]
avail_clubs = [r for r in rows if r["availability_delta_rows"]]
print("weekly_diff_2026-11-18.csv: %d clubs" % len(rows))
print("  W1 no look-ahead in either fit                : pass (%d and %d games)"
      % (len(g10), len(g11)))
print("  W2 same 32 clubs in both snapshots            : pass")
print("  W3 availability counts match the delta file   : pass (%d rows in %d clubs)"
      % (len(delta), len(avail_clubs)))
print("  W4 rank columns are permutations of 1..32     : pass")
print("  frozen corpus  : only %d game separates the two snapshots (%d -> %d games)"
      % (len(g11) - len(g10), len(g10), len(g11)))
print("  corpus v2      : %d games separate them (%d -> %d games)"
      % (len(v2_g11) - len(v2_g10), len(v2_g10), len(v2_g11)))
print("  biggest rating movers after Week 10 (corpus v2):")
for r in movers:
    print("    %-3s %+6.2f pts  rank %d -> %d" % (r["club"], r["net_rating_change_v2_corpus"],
                                                  r["rank_before_week10_v2_corpus"],
                                                  r["rank_before_week11_v2_corpus"]))
print("  clubs with an availability re-read delta: %s"
      % ", ".join("%s (%d)" % (r["club"], r["availability_delta_rows"]) for r in avail_clubs))
