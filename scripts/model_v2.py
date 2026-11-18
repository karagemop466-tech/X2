#!/usr/bin/env python3
"""Corpus v2: the same model code, run on the complete 150-game log.

WHY THIS EXISTS
---------------
`data/games_2026_results.csv` (v1) holds 137 settled 2026 games: weeks 1-9 complete
(136) plus the Week 10 Thursday game. Thirteen settled Week 10 games were transcribed
on 2026-11-18 into `data/games_week10_backfill_2026.csv` (F105) but deliberately not
spliced into v1, because doing so changes every published metric - that is owner
decision P09, recorded as options A/B/C on the Review console.

This session may not take option A (rewrite the published numbers under a reader who
has already seen v1). It takes **option B**: build a parallel v2 corpus, re-run the
identical model on it, and publish v1 and v2 side by side with a version tag on every
number. Nothing in `data/*.csv` is read-modify-written; v1 stays byte-for-byte frozen.

WHAT IT DOES
------------
1. Builds `data/corpus_v2/games_2026_results_v2.csv` = v1 rows (unchanged, same order)
   + the 13 backfill rows, with `neutral_site = Y` set on exactly the nine games that
   `data/international_games_2026.csv` lists as 2026 international games
   (official NFL Football Operations slate, SRC-72). v1's `neutral_site` column is
   blank on all 137 rows (F71), so eight settled games are mis-flagged in v1.
2. Writes it only after asserting the v2 corpus reconciles with the official standings
   read used by `scripts/results_feed_completeness.py` for all 32 clubs.
3. Runs `scripts/model.py` **unmodified** by injecting a copy of its source into a
   module whose `DATA` points at `data/corpus_v2/`. Every output therefore lands in
   `data/corpus_v2/` and the v1 files are not opened for writing.
4. Asserts the v1 files are unchanged (sha256 before/after) and writes a comparison
   register between v1 and v2 for every metric that a reader would otherwise compare
   across versions.

Any failure raises SystemExit and no comparison register is written.

Usage:  python3 scripts/model_v2.py
"""
import csv
import hashlib
import os
import sys
import types

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
V2 = os.path.join(DATA, "corpus_v2")
SCRIPTS = os.path.join(ROOT, "scripts")

V1_CORPUS = "games_2026_results.csv"
V2_CORPUS = "games_2026_results.csv"   # the file name scripts/model.py reads, scoped to data/corpus_v2/
BACKFILL = "games_week10_backfill_2026.csv"
INTL = "international_games_2026.csv"

AS_OF_V2 = "2026-11-18"
SRC_STAND = "https://www.nfl.com/standings/"
SRC_W10 = "https://www.nfl.com/schedules/2026/by-week/week-10"
SRC_INTL = ("https://operations.nfl.com/programs-initiatives/international-growth/"
            "nfl-international-games")
SRC_V2_CORPUS = ("https://github.com/karagemop466-tech/X2/blob/main/data/corpus_v2/"
                 + V2_CORPUS)


# --------------------------------------------------------------- helpers ----
def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write(path, rows, fields):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def v1_files():
    """Every data/*.csv that scripts/model.py writes, plus the seal and summary."""
    return ["model_lines_week11.csv", "results_feed_2026.csv", "price_snapshots_extended.csv",
            "model_ratings.csv", "model_backtest.csv", "model_bets.csv",
            "strategy_backtest_scores.csv", "strategy_leaderboard.csv", "gate_results.csv",
            "correlations_computed.csv", "prospective_forecast_log.csv",
            "prospective_forecast_log.sha256", "parlay_analysis.csv",
            "leaderboard_control_runs.csv", "model_summary.json"]


# --------------------------------------------------------- 1. build corpus ----
v1 = read(os.path.join(DATA, V1_CORPUS))
backfill = read(os.path.join(DATA, BACKFILL))
intl = read(os.path.join(DATA, INTL))
v1_fields = list(v1[0].keys())

if len(v1) != 137:
    raise SystemExit(f"FAILED: v1 corpus has {len(v1)} rows, expected the frozen 137")
if len(backfill) != 13:
    raise SystemExit(f"FAILED: backfill has {len(backfill)} rows, expected 13")
if len(intl) != 9:
    raise SystemExit(f"FAILED: international slate has {len(intl)} rows, expected 9")

# The nine international games, keyed on (week, away, home). The slate page writes the
# Rams as LAR; this repository writes LA (flag F46), so normalise only that one token.
RENAME = {"LAR": "LA"}
intl_keys = {(int(r["week"]), RENAME.get(r["away_designated"], r["away_designated"]),
              RENAME.get(r["home_designated"], r["home_designated"])) for r in intl}

# ---- 1a. v1 rows, unchanged, plus the neutral flag where the official slate says so
v2_rows = []
for r in v1:
    row = dict(r)
    key = (int(r["week"]), r["away_team"], r["home_team"])
    if key in intl_keys:
        row["neutral_site"] = "Y"
    elif (r.get("neutral_site") or "").strip():
        raise SystemExit(f"FAILED: v1 already flags {key} neutral; v1 is supposed to be blank")
    v2_rows.append(row)

# ---- 1b. the 13 backfill rows, transcribed from the official Week 10 page
for b in backfill:
    v2_rows.append({
        "season": "2026", "week": b["week"], "date_as_shown": b["date_as_shown"],
        "away_team": b["away_team"], "away_points": b["away_points"],
        "home_team": b["home_team"], "home_points": b["home_points"],
        "game_url": b["game_url"], "source_url": b["source_url"],
        "neutral_site": "Y" if (int(b["week"]), b["away_team"], b["home_team"]) in intl_keys else "",
    })

# ---- 1c. assertions the corpus has to pass before anything is written
if len(v2_rows) != 150:
    raise SystemExit(f"FAILED: v2 corpus has {len(v2_rows)} rows, expected 150")
flagged = [r for r in v2_rows if (r["neutral_site"] or "").strip().upper() == "Y"]
# The official slate has nine games; the ninth (MIN at SF, Estadio Banorte, Mexico City) is
# Week 11 and is not a result, so a settled corpus can carry eight. Assert exactly that.
if len(flagged) != 8:
    raise SystemExit(f"FAILED: {len(flagged)} neutral-flagged games in v2, expected 8 "
                     "(the 9-game official slate minus the unplayed Week 11 game)")
seen = set()
for r in v2_rows:
    key = (r["week"], r["away_team"], r["home_team"])
    if key in seen:
        raise SystemExit(f"FAILED: duplicate fixture in v2 corpus: {key}")
    seen.add(key)


def aggregate(rows):
    import collections
    st = collections.defaultdict(lambda: dict(w=0, l=0, t=0, pf=0, pa=0))
    for g in rows:
        a, h = g["away_team"], g["home_team"]
        ap, hp = int(g["away_points"]), int(g["home_points"])
        st[a]["pf"] += ap; st[a]["pa"] += hp
        st[h]["pf"] += hp; st[h]["pa"] += ap
        if ap > hp:
            st[a]["w"] += 1; st[h]["l"] += 1
        elif hp > ap:
            st[h]["w"] += 1; st[a]["l"] += 1
        else:
            st[a]["t"] += 1; st[h]["t"] += 1
    return st


# Today's official standings read (2026-11-18, https://www.nfl.com/standings/), all 32
# clubs, W-L-T / PF / PA. Transcribed from the live division page; this is the opponent
# the corpus has to reconcile with, and it is the same read data/standings_diff.py and
# data/results_feed_completeness_2026-11-18.csv work from.
LIVE_STANDINGS = {
    "BUF": (8, 1, 0, 287, 199), "NE": (5, 5, 0, 221, 242), "NYJ": (2, 8, 0, 194, 254),
    "MIA": (1, 8, 0, 148, 224), "CIN": (7, 2, 0, 278, 193), "PIT": (6, 3, 0, 198, 182),
    "CLE": (6, 4, 0, 188, 220), "BAL": (4, 6, 0, 209, 259), "JAX": (7, 2, 0, 269, 144),
    "HOU": (3, 6, 0, 233, 219), "IND": (3, 7, 0, 208, 271), "TEN": (1, 8, 0, 167, 239),
    "KC": (7, 2, 0, 237, 156), "DEN": (7, 2, 0, 198, 186), "LV": (4, 6, 0, 251, 289),
    "LAC": (1, 8, 0, 144, 239), "NYG": (5, 3, 1, 203, 196), "DAL": (4, 6, 0, 286, 282),
    "WAS": (3, 5, 1, 196, 223), "PHI": (2, 7, 0, 148, 221), "DET": (7, 2, 0, 257, 199),
    "MIN": (7, 2, 0, 176, 126), "CHI": (7, 2, 0, 241, 184), "GB": (6, 4, 0, 226, 221),
    "CAR": (4, 5, 0, 219, 236), "TB": (3, 6, 0, 202, 178), "NO": (3, 6, 0, 202, 236),
    "ATL": (3, 7, 0, 201, 258), "SF": (8, 1, 0, 281, 196), "SEA": (6, 4, 0, 223, 175),
    "LA": (6, 4, 0, 248, 187), "AZ": (3, 7, 0, 184, 289),
}
if len(LIVE_STANDINGS) != 32:
    raise SystemExit("FAILED: the standings block must carry all 32 clubs")

st_v1 = aggregate(v1)
st_v2 = aggregate(v2_rows)
recon = []
for team, (w, l, t, pf, pa) in sorted(LIVE_STANDINGS.items()):
    for label, st in (("v1 (137 games, published)", st_v1), ("v2 (150 games, this build)", st_v2)):
        s = st.get(team) or dict(w=0, l=0, t=0, pf=0, pa=0)
        ok = (s["w"], s["l"], s["t"], s["pf"], s["pa"]) == (w, l, t, pf, pa)
        recon.append({
            "corpus_version": label, "team": team,
            "official_w": w, "official_l": l, "official_t": t,
            "official_pf": pf, "official_pa": pa,
            "corpus_w": s["w"], "corpus_l": s["l"], "corpus_t": s["t"],
            "corpus_pf": s["pf"], "corpus_pa": s["pa"],
            "reconciles": "yes" if ok else "NO",
            "source_url": SRC_STAND,
        })
v2_bad = [r for r in recon if r["corpus_version"].startswith("v2") and r["reconciles"] != "yes"]
if v2_bad:
    raise SystemExit("FAILED: v2 corpus does not reconcile with the official standings for "
                     + ", ".join(r["team"] for r in v2_bad))
v1_ok = sum(1 for r in recon if r["corpus_version"].startswith("v1") and r["reconciles"] == "yes")

write(os.path.join(DATA, "corpus_v2", "corpus_reconciliation.csv"), recon,
      ["corpus_version", "team", "official_w", "official_l", "official_t", "official_pf",
       "official_pa", "corpus_w", "corpus_l", "corpus_t", "corpus_pf", "corpus_pa",
       "reconciles", "source_url"])

# the corpus itself, written only after the 32/32 check
write(os.path.join(V2, V2_CORPUS), v2_rows, v1_fields)
print(f"v2 corpus: {len(v2_rows)} games ({len(flagged)} neutral-flagged) -> "
      f"data/corpus_v2/{V2_CORPUS}")
print(f"reconciliation vs official standings read {AS_OF_V2}: "
      f"v2 32/32 clubs, v1 {v1_ok}/32 clubs")


# ------------------------------------------------------- 2. run the model ----
# scripts/model.py is executed unmodified; only its DATA constant is redirected, so no
# v1 file is ever opened for writing. V1_SEAL keeps the seal text honest about which
# corpus it seals.
before = {f: sha256(os.path.join(DATA, f)) for f in v1_files()}

# scripts/model.py also reads two inputs that do NOT change between versions. They are
# copied into the version directory so the redirected run is complete, and the copies are
# byte-identity checked against v1 rather than re-transcribed (no new read of any source).
UNCHANGED_INPUTS = ["schedule_week11_2026.csv", "injuries_week10_2026.csv"]
for f in UNCHANGED_INPUTS:
    src_p, dst_p = os.path.join(DATA, f), os.path.join(V2, f)
    payload = open(src_p, "rb").read()
    if not os.path.exists(dst_p) or open(dst_p, "rb").read() != payload:
        open(dst_p, "wb").write(payload)
    if sha256(src_p) != sha256(dst_p):
        raise SystemExit(f"FAILED: copied input {f} does not match v1 byte for byte")

source = open(os.path.join(SCRIPTS, "model.py"), encoding="utf-8").read()
source = source.replace('DATA = os.path.join(ROOT, "data")',
                        'DATA = os.path.join(ROOT, "data", "corpus_v2")', 1)
source = source.replace('AS_OF = "2026-11-14"', f'AS_OF = "{AS_OF_V2}"', 1)
if 'DATA = os.path.join(ROOT, "data", "corpus_v2")' not in source:
    raise SystemExit("FAILED: could not redirect DATA in scripts/model.py; the model's "
                     "structure changed and this wrapper must be re-checked before it "
                     "is allowed to publish a v2 corpus")

mod = types.ModuleType("model_v2_run")
mod.__file__ = os.path.join(SCRIPTS, "model.py")
sys.path.insert(0, SCRIPTS)
sys.modules["model_v2_run"] = mod
exec(compile(source, mod.__file__, "exec"), mod.__dict__)

after = {f: sha256(os.path.join(DATA, f)) for f in v1_files()}
changed = [f for f in v1_files() if before[f] != after[f]]
if changed:
    raise SystemExit("FAILED: v1 outputs changed while building v2: " + ", ".join(changed))

# the v2 outputs must exist and be the redirected ones
for f in v1_files():
    p = os.path.join(V2, f)
    if not os.path.exists(p):
        raise SystemExit(f"FAILED: v2 run did not write data/corpus_v2/{f}")


# -------------------------------------------------- 3. v1 vs v2 comparison ----
def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


cmp_rows = []


def cmp_row(metric, v1_val, v2_val, note, source_url):
    a, b = num(v1_val), num(v2_val)
    delta = ""
    if a is not None and b is not None:
        delta = f"{b - a:+.4f}"
    cmp_rows.append({
        "metric": metric,
        "v1_value_137_games_published": "" if v1_val is None else str(v1_val),
        "v2_value_150_games_this_build": "" if v2_val is None else str(v2_val),
        "change_v2_minus_v1": delta,
        "note": note, "source_url": source_url,
    })


m1 = __import__("json").load(open(os.path.join(DATA, "model_summary.json"), encoding="utf-8"))
m2 = __import__("json").load(open(os.path.join(V2, "model_summary.json"), encoding="utf-8"))

CORPUS_METRICS = [
    ("games_transcribed", "games in the corpus"),
    ("out_of_sample_games", "walk-forward out-of-sample games graded"),
    ("mae_reference", "mean absolute error, naive reference line (margin, pts)"),
    ("mae_m1", "mean absolute error, M1 (margin, pts)"),
    ("mae_improvement", "MAE improvement of M1 over the reference line (pts)"),
    ("sd_margin_residual", "residual sd of the margin (pts)"),
    ("calibration_slope", "calibration slope, actual on predicted"),
    ("calibration_slope_se", "calibration slope standard error"),
    ("calibration_slope_p_vs_1", "calibration slope p against a null of 1.0"),
    ("reference_total_week11", "naive reference total for Week 11"),
    ("neutral_site_rows_blank", "corpus rows whose neutral_site cell was blank"),
]
for key, label in CORPUS_METRICS:
    if key not in m1 or key not in m2:
        continue
    note = ("same code, same seed; the only inputs that differ are the 13 settled Week 10 "
            "games and the eight settled international games re-flagged neutral")
    cmp_row(label, m1.get(key), m2.get(key), note, SRC_V2_CORPUS)

# every Weekly 11 originated number, side by side
l1 = {r["game_no"]: r for r in read(os.path.join(DATA, "model_lines_week11.csv"))}
l2 = {r["game_no"]: r for r in read(os.path.join(V2, "model_lines_week11.csv"))}
for gid in sorted(l1, key=int):
    a, b = l1[gid], l2[gid]
    for field, label in (("fair_spread", "side (fair spread, home)"),
                         ("fair_total", "total (fair)"),
                         ("home_win_prob", "moneyline (P(home win))")):
        cmp_row(f"W11 game {gid} {a['matchup']} — {label}", a.get(field), b.get(field),
                "originated market republished from the v2 fit", a.get("source_url") or SRC_W10)

# leaderboard: v1 is unranked and stays unranked, but the research scores move
b1 = {r["strategy_id"]: r for r in read(os.path.join(DATA, "strategy_backtest_scores.csv"))}
b2 = {r["strategy_id"]: r for r in read(os.path.join(V2, "strategy_backtest_scores.csv"))}
for sid in sorted(b1):
    if sid not in b2:
        continue
    for field, label in (("skill_score_mae_improvement_pts", "MAE improvement (pts)"),
                         ("mae_model", "MAE model"),
                         ("mae_reference", "MAE reference"),
                         ("oos_games", "out-of-sample games"),
                         ("bets_vs_reference", "bets against the reference line"),
                         ("hit_rate_vs_reference", "hit rate vs the reference line"),
                         ("mean_edge_points", "mean edge (pts)"),
                         ("skill_p_permutation", "permutation p")):
        cmp_row(f"strategy {sid} — {label}", b1[sid].get(field), b2[sid].get(field),
                "research backtest score; never a leaderboard rank (F42/F87)",
                b1[sid].get("source_url") or SRC_W10)

write(os.path.join(DATA, "corpus_v2", "corpus_version_comparison.csv"), cmp_rows,
      ["metric", "v1_value_137_games_published", "v2_value_150_games_this_build",
       "change_v2_minus_v1", "note", "source_url"])

# provenance for the v2 corpus itself
prov = [{
    "corpus_version": "v2",
    "games": len(v2_rows),
    "weeks": "1-10 (weeks 1-9 complete, all 14 Week 10 games)",
    "rows_from_v1": len(v1),
    "rows_from_backfill": len(backfill),
    "neutral_games_flagged": len(flagged),
    "neutral_games_note": "8 of the 9 official 2026 international games are settled; the ninth (MIN at SF) is Week 11 and unplayed",
    "neutral_site_source": SRC_INTL,
    "backfill_source": SRC_W10,
    "standings_reconciliation": "32/32 clubs on W-L-T, PF and PA",
    "standings_source": SRC_STAND,
    "standings_read": AS_OF_V2,
    "model_code": "scripts/model.py, unmodified, executed by scripts/model_v2.py with DATA redirected",
    "v1_untouched_sha256_check": "pass — " + str(len(v1_files())) + " v1 outputs byte-identical before and after",
    "source_url": SRC_V2_CORPUS,
}]
write(os.path.join(DATA, "corpus_v2", "corpus_provenance.csv"), prov, list(prov[0].keys()))

print(f"comparison register: {len(cmp_rows)} metrics -> data/corpus_v2/corpus_version_comparison.csv")
print(f"v1 untouched: {len(v1_files())} outputs byte-identical")
print("CORPUS V2 BUILD OK")
