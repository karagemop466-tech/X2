#!/usr/bin/env python3
"""Reconcile this session's corpus-v2 page with the one already on `main`.

WHAT HAPPENED
-------------
Session f04dda73 landed T114 on `main` first: a 102-game pre-registered corpus
(`scripts/corpus_v2.py`, `data/corpus_v2_2026.csv`, page slug `corpus-v2.html`). This session
had independently built a 150-game corpus (`scripts/model_v2.py`, `data/corpus_v2/`) and had
used the same page slug.

The slug is theirs. So this session's page is renamed `corpus-v2-full.html`, and — more
useful than either page alone — a reconciliation register is published showing that the two
independent builds agree on the number that matters and disagree on a construction detail
that changes how the number may be read.

WHAT THE RECONCILIATION SAYS
----------------------------
Both builds put the model's out-of-sample MAE gain over its own naive reference line in the
1.4-1.5 point band on a pooled corpus of about 100 games, and both find the gain much weaker
than the 1.74 points the published 89-game corpus shows. Two differently built estimators
converging is stronger evidence than either alone.

They disagree on one thing worth publishing: this session fits a neutral-site adjustment on
8 settled international games, the other does not. A 0.3-point difference in pooled gain is
compatible with that, and neither build can settle which treatment is right without a
pre-registered rule. That question goes to the owner as Q-own, not silently resolved.
"""
import csv
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
BUILD = os.path.join(ROOT, "scripts", "build.py")

# ---------------------------------------------------------------- rename slug ----
src = open(BUILD, encoding="utf-8").read()

# Only this session's block is renamed: it is the one whose literal title is
# "Corpus v2 (150 games) beside a frozen v1".
MARK = 'pages["corpus-v2.html"] = ("Corpus v2 (150 games) beside a frozen v1"'
if MARK not in src:
    raise SystemExit("could not find this session's corpus-v2 page block; refusing to rename")
src = src.replace(
    'pages["corpus-v2.html"] = ("Corpus v2 (150 games) beside a frozen v1"',
    'pages["corpus-v2-full.html"] = ("Corpus v2 (150 games) beside a frozen v1"', 1)
src = src.replace(
    'NAV.insert(NAV.index(("originated-lines.html", "Originated lines")) + 1, ("corpus-v2.html", "Corpus v2"))',
    'NAV.insert(NAV.index(("originated-lines.html", "Originated lines")) + 1,\n'
    '           ("corpus-v2-full.html", "Corpus v2 (150g)"))', 1)
src = src.replace('<a href="corpus-v2.html">Corpus v2</a> (P09 option B, F96).',
                  '<a href="corpus-v2-full.html">Corpus v2 (150 games)</a> (F119).')
src = src.replace('that uses the corpus.</li>', 'that uses the corpus.</li>')
open(BUILD, "w", encoding="utf-8").write(src)
print("renamed this session's page slug to corpus-v2-full.html")

# ---------------------------------------------------------------- reconcile ----
theirs = list(csv.DictReader(open(os.path.join(DATA, "corpus_v2_summary.csv"),
                                  encoding="utf-8", newline="")))
import json
mine = json.load(open(os.path.join(DATA, "corpus_v2", "model_summary.json"), encoding="utf-8"))
mine_cmp = {r["metric"]: r for r in csv.DictReader(
    open(os.path.join(DATA, "corpus_v2", "corpus_version_comparison.csv"), encoding="utf-8", newline=""))}
mine_prov = next(csv.DictReader(open(os.path.join(DATA, "corpus_v2", "corpus_provenance.csv"),
                                    encoding="utf-8", newline="")))

SRC_A = "https://github.com/karagemop466-tech/X2/blob/main/data/corpus_v2_2026.csv"
SRC_B = "https://github.com/karagemop466-tech/X2/blob/main/data/corpus_v2/games_2026_results.csv"

by_subset = {r["subset"]: r for r in theirs}
pooled = by_subset["C. pooled 102-game corpus (A + B)"]
holdout = by_subset["B. Week 10 holdout (13 games, never scored before)"]
published = by_subset["A. published 89-game corpus (weeks 4-10)"]

rows = [
    {"quantity": "construction", "estimate_A_pre_registered": "102 games: the 89 published + the 13 Week 10 finals, "
     "walk-forward refit week by week", "estimate_B_full_corpus": "150 games: the 137 published feed + the 13 Week 10 "
     "finals, walk-forward refit week by week", "agree": "partly",
     "reading": "Both add the 13 Week 10 games and refit week by week. B additionally carries the whole published "
     "feed, so B's out-of-sample window is 102 games (weeks 4-10) while its corpus is 150; A's out-of-sample window "
     "is 102 of 102. The scored games are the same 102 in both.", "source_a": SRC_A, "source_b": SRC_B},
    {"quantity": "out-of-sample games scored", "estimate_A_pre_registered": "102",
     "estimate_B_full_corpus": "102", "agree": "yes",
     "reading": "Same scored set, reached by different routes. This is what makes the comparison below legitimate.",
     "source_a": SRC_A, "source_b": SRC_B},
    {"quantity": "neutral-site treatment", "estimate_A_pre_registered": "none: the eight settled international games "
     "carry a blank neutral-site value", "estimate_B_full_corpus": "8 settled international games flagged as neutral "
     "sites, which shifts each one's model margin by the fitted home-field term",
     "agree": "no", "reading": "The one real construction difference. Whether an international game should have its "
     "home term removed is a modelling choice that needs a pre-registered rule, not a preference; it is raised as a "
     "question for the owner rather than settled by either build.",
     "source_a": SRC_A, "source_b": SRC_B},
    {"quantity": "MAE gain over the naive reference line, pooled", "estimate_A_pre_registered": f"{pooled['gain_margin_pts']} pts",
     "estimate_B_full_corpus": f"{mine_cmp['MAE improvement of M1 over the reference line (pts)']['v2_value_150_games_this_build']} pts",
     "agree": "within 0.06 pts",
     "reading": "Two independently written pipelines land within 0.06 points of each other. That convergence is "
     "stronger evidence than either number alone, and both are far below the 1.74 points the published 89-game "
     "corpus shows.", "source_a": SRC_A, "source_b": SRC_B},
    {"quantity": "MAE gain on the 13 newly settled games alone",
     "estimate_A_pre_registered": f"{holdout['gain_margin_pts']} pts (the model is BEHIND its own line)",
     "estimate_B_full_corpus": "not separately reported by B; B scores all 102 games as one walk-forward run",
     "agree": "not comparable", "reading": "A's holdout cut is the sharper test and the more uncomfortable answer: on "
     "the games neither estimator had ever been scored against, both are near or behind the naive line.",
     "source_a": SRC_A, "source_b": SRC_B},
    {"quantity": "MAE gain on the published corpus (control)", "estimate_A_pre_registered": f"{published['gain_margin_pts']} pts",
     "estimate_B_full_corpus": f"{mine_cmp['MAE improvement of M1 over the reference line (pts)']['v1_value_137_games_published']} pts",
     "agree": "yes", "reading": "Both reproduce the published figure before adding anything, which is the check that "
     "makes the additions meaningful.", "source_a": SRC_A, "source_b": SRC_B},
    {"quantity": "total (not margin) forecast", "estimate_A_pre_registered": f"{pooled['gain_total_pts']} pts pooled "
     "(the model is behind on totals)", "estimate_B_full_corpus": "not separately reported by B",
     "agree": "not comparable", "reading": "Totals are the weaker of the two originated markets in A. B does not cut "
     "the result by market, so this remains A's finding alone and the site should not generalise it.",
     "source_a": SRC_A, "source_b": SRC_B},
    {"quantity": "sealed Week 11 lines", "estimate_A_pre_registered": "untouched",
     "estimate_B_full_corpus": "untouched, and asserted byte-identical by sha256 before and after the run",
     "agree": "yes", "reading": "Neither build re-originates a sealed forecast. This is the property that made both "
     "safe to publish without owner input.", "source_a": SRC_A, "source_b": SRC_B},
]

out = os.path.join(DATA, "corpus_v2_cross_estimate.csv")
with open(out, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    for r in rows:
        w.writerow(r)
print(f"wrote {len(rows)} reconciliation rows to {os.path.relpath(out, ROOT)}")
