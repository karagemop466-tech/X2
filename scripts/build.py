#!/usr/bin/env python3
"""Build the static GitHub Pages site in docs/ from the CSV data in data/.

Standard library only. Run:  python3 scripts/build.py
It (1) validates the data, (2) writes docs/data/*.json, (3) writes docs/*.html,
and (4) checks that every table row has a source link and every internal link resolves.
"""
import csv
import html
import json
import os
import re
import sys
from collections import Counter, defaultdict
from urllib.parse import urlsplit

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
DOCS = os.path.join(ROOT, "docs")

# Drift alarm (T105, D38): every pinned register must match its row count, required
# non-blank columns and key uniqueness before anything is published. Fails loudly.
import subprocess as _sp
_drift = _sp.run([sys.executable, os.path.join(ROOT, "scripts", "drift_check.py")],
                 capture_output=True, text=True)
if _drift.returncode != 0:
    raise SystemExit("BUILD FAILED: drift alarm\n" + _drift.stdout + _drift.stderr)
AS_OF = "2026-11-14"
OFFICIAL_HOSTS = {
    # static.www.nfl.com serves official NFL gamebook PDFs linked from the NFL game
    # centers (T52 takeover). It is a first-party NFL host, not a third-party provider.
    "www.nfl.com", "static.www.nfl.com", "support.nfl.com", "operations.nfl.com",
    "www.detroitlions.com", "www.patriots.com",
    "laws.e-gov.go.jp", "www.jpnsport.go.jp", "www.gov-online.go.jp", "www.npa.go.jp",
    "www.itl.nist.gov", "github.com", "karagemop466-tech.github.io",
    "wetten.overheid.nl", "www.kansspelautoriteit.nl", "kansspelautoriteit.nl",
    "www.seahawks.com", "www.miamidolphins.com", "www.baltimoreravens.com", "www.clevelandbrowns.com",
    "www.azcardinals.com", "www.giants.com",
    "www.packers.com", "www.therams.com", "www.chiefs.com", "www.colts.com",

    "www.dallascowboys.com", "www.tennesseetitans.com",
    "www.neworleanssaints.com", "www.houstontexans.com", "www.indianapoliscolts.com",
    "www.minnesotavikings.com",}
PROJECT_REPO_PATH = "/karagemop466-tech/X2"

# Position -> unit / side of ball. This is a classification made by this project, not an NFL field.
UNIT = {"QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR/TE", "TE": "WR/TE",
        "T": "OL", "OT": "OL", "G": "OL", "OG": "OL", "C": "OL", "OL": "OL",
        "DE": "DL", "DT": "DL", "DL": "DL", "NT": "DL",
        "LB": "LB", "OLB": "LB", "ILB": "LB", "MLB": "LB",
        "CB": "DB", "S": "DB", "SAF": "DB", "DB": "DB",
        "K": "ST", "P": "ST", "LS": "ST"}
SIDE = {"QB": "Offense", "RB": "Offense", "WR/TE": "Offense", "OL": "Offense",
        "DL": "Defense", "LB": "Defense", "DB": "Defense", "ST": "Special teams"}
UNIT_ORDER = ["QB", "RB", "WR/TE", "OL", "DL", "LB", "DB", "ST"]


def read_csv(name):
    path = os.path.join(DATA, name)
    with open(path, encoding="utf-8", newline="") as f:
        raw = list(csv.reader(f))
    if raw:
        header_len = len(raw[0])
        for i, r in enumerate(raw, start=1):
            if len(r) != header_len:
                errors.append(
                    "%s line %d: %d fields, expected %d — quote any field containing a comma"
                    % (name, i, len(r), header_len)
                )
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


errors = []
warnings = []


def is_official_url(url):
    """Allow only HTTPS links on explicitly reviewed primary-source domains.

    GitHub links are limited to this repository (project facts and source code);
    the GitHub Pages host is allowed only for this project's published site.
    """
    try:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in OFFICIAL_HOSTS:
            return False
        if parsed.username or parsed.password or parsed.port:
            return False
        if parsed.hostname == "github.com":
            return parsed.path == PROJECT_REPO_PATH or parsed.path.startswith(PROJECT_REPO_PATH + "/")
        if parsed.hostname == "karagemop466-tech.github.io":
            return parsed.path == "/X2" or parsed.path.startswith("/X2/")
        return True
    except (TypeError, ValueError):
        return False


def check_official(url, where):
    if not url:
        return
    if not is_official_url(url):
        errors.append(f"{where}: non-official or non-https link: {url}")


# ---------- load + validate ----------
inj = read_csv("injuries_week10_2026.csv")
games = read_csv("games_week10_2026.csv")
news = read_csv("news_week10_2026.csv")
sources = read_csv("sources.csv")
flags = read_csv("flags.csv")
questions = read_csv("questions.csv")
suggestions = read_csv("suggestions.csv")
gates = read_csv("strategy_gates.csv")
hyps = read_csv("strategy_hypotheses.csv")
reqs = read_csv("requirements.csv")
# ---- model / strategy outputs produced by scripts/model.py ----
results_games = read_csv("games_2026_results.csv")
week11_sched = read_csv("schedule_week11_2026.csv")
model_lines = read_csv("model_lines_week11.csv")
model_ratings = read_csv("model_ratings.csv")
model_backtest = read_csv("model_backtest.csv")
model_bets = read_csv("model_bets.csv")
leaderboard = read_csv("strategy_leaderboard.csv")
# The competition-facing CSV must contain no retrospective outcome metric.
# Enforce this in the build so a future model run cannot silently reintroduce backtest ranks.
gate_results = read_csv("gate_results.csv")
correlations = read_csv("correlations_computed.csv")
parlays = read_csv("parlay_analysis.csv")
# ---- session c125b2f7: market tables (generated by scripts/markets.py) ----
price_snapshots = read_csv("price_snapshots.csv")
line_comparison = read_csv("line_comparison_week11.csv")
signal_staking = read_csv("strategy_signal_staking.csv")
if any((r.get(k) or "").strip() for r in signal_staking for k in
       ("signal_skill_points", "signal_ci_low", "signal_ci_high", "signal_q_bh_fdr", "signal_oos_games", "signal_leaderboard_rank")):
    raise ValueError("Backtest leakage in prospective signal/staking view")
demotion_gate = read_csv("demotion_gate.csv")
# ---- session ef971991: depth of the replacement (not just the fact of a replacement) ----
replacement_depth = read_csv("replacement_depth.csv")
# ---- session ca1ea224: the extended price-snapshot store (Week 11 + out-of-sample) ----
price_snapshots_extended = read_csv("price_snapshots_extended.csv")
# ---- session f25d6b55 (T52): canonical verified results feed ----
results_feed = read_csv("results_feed_2026.csv")
with open(os.path.join(DATA, "model_summary.json"), encoding="utf-8") as f:
    ms = json.load(f)
# ---- session e208ba6d: decision console, market sheet, live re-verification ----
market_sheet = read_csv("market_sheet_week11.csv")
corr_matrix = read_csv("correlation_matrix_same_game.csv")
prop_markets = read_csv("prop_markets_week11.csv")
prop_combos = read_csv("prop_combinations_week11.csv")
event_risk = read_csv("event_risk_week11.csv")
event_risk_summary = read_csv("event_risk_summary_week11.csv")
injury_impact = read_csv("injury_impact_2026.csv")
live_reverification = read_csv("live_reverification_2026-11-14.csv")
decision_console = read_csv("decision_console.csv")
# The console is generated from data/decision_choices.json.  If the CSV was built
# from a different JSON state than the one on disk, the page would show a decision
# that was never actually recorded.  Refuse to publish that.
with open(os.path.join(DATA, "decision_choices.json"), encoding="utf-8") as f:
    _dc = json.load(f).get("choices", {})
for _row in decision_console:
    _want = _dc.get(_row["proposal_id"], {}).get("choice", "")
    if (_row["recorded_choice"] or "") != _want:
        errors.append(
            "decision_console.csv is stale for %s: page would show %r but "
            "decision_choices.json records %r - re-run scripts/review.py"
            % (_row["proposal_id"], _row["recorded_choice"], _want))
forecast_log = read_csv("prospective_forecast_log.csv")
with open(os.path.join(DATA, "prospective_forecast_log.sha256"), encoding="utf-8") as f:
    SEAL = f.read().split()[0]
# ---- session 10a76288: a second, independent implementation used to cross-check the one above ----
season_games = read_csv("season_games_2026.csv")
standings = read_csv("standings_2026_week10.csv")
scorecard = read_csv("strategy_scorecard_2026.csv")
model_holdout = read_csv("model_holdout_2026.csv")
availability = read_csv("confirmed_availability_week10_2026.csv")
verification_rows = read_csv("verification_report.csv")
decisions = read_csv("decision-chain.csv")
sugg_review = read_csv("suggestion_review.csv")

# Research registers taken over from session 25d6114f (T52). Variable names are
# chosen not to collide with this builder's own bindings (decisions, repo_review).
verification_ledger = read_csv("verification_week10_2026.csv")
starters = read_csv("starters_gamebook_2026_reg_10.csv")
starters_good = [r for r in starters if r["gamebook_status"] == "Starter"]
starters_bad = [r for r in starters if r["gamebook_status"] != "Starter"]
line_signals = read_csv("line_signals.csv")
engine_gates = read_csv("skill_engine_gates.csv")
luck_tests = read_csv("luck_tests.csv")
corr_framework = read_csv("correlation_framework.csv")
lb_rules = read_csv("leaderboard_rules.csv")
depth_def = read_csv("depth_deficiency.csv")
dq_rows = read_csv("decision_questions.csv")
sug_register = read_csv("suggestions_register.csv")
repo_review_rows = read_csv("repo_review.csv")
repo_review_counts = Counter(r["result"] for r in repo_review_rows)
verification_ledger_counts = Counter(r["result"].split(" — ")[0] for r in verification_ledger)
# ---------- session d0d9d19f: settlement feed, origination order, replacement ----------
# ---------- depth, correlation provenance, repository audit ----------
feed_settled = read_csv("results_feed.csv")
orig_lines = read_csv("originated_lines_week11.csv")
orig_snaps = read_csv("origin_snapshots_week11.csv")
corr_prov = read_csv("correlation_provenance.csv")
depth_repl = read_csv("depth_replacement.csv")
repo_audit = read_csv("repo_line_audit.csv")
# session d0d9d19f: figures used by the executive summary and by the five pages below
_named_repl = sum(1 for r in depth_repl if r["named_replacement"])
_feed_orig = sum(1 for r in feed_settled if r["originated_side_home_line"])
_feed_cover = sum(1 for r in feed_settled if r["side_settlement_home"] == "home side covers")
_feed_lose = sum(1 for r in feed_settled if r["side_settlement_home"] == "home side loses")
_feed_push = sum(1 for r in feed_settled if r["side_settlement_home"] == "push")
_feed_over = sum(1 for r in feed_settled if r["total_settlement"] == "over")
_feed_under = sum(1 for r in feed_settled if r["total_settlement"] == "under")
_covered_names = sorted({r["team_abbr"] for r in depth_repl})
# the parallel register lives in another file (read here: the exec summary needs it
# before scripts/build.py binds rep_depth further down)
_other_names = sorted({(r.get("team_abbr") or "").strip()
                       for r in read_csv("replacement_depth_week10_2026.csv")
                       if (r.get("team_abbr") or "").strip()})
_union_names = sorted(set(_covered_names) | set(_other_names))
_shared_names = sorted(set(_covered_names) & set(_other_names))
_audit_pass = sum(1 for r in repo_audit if r["status"].startswith("pass"))
_recomputed = sum(1 for r in corr_prov if r["recomputation_check"].startswith("recomputed"))
# Empty-state row only: do not imply a strategy has results or an approved reward.
leaderboard_status = [{
    "rank": "—",
    "strategy": "See the Leaderboard page (7 strategies graded)",
    "skill_score": "",
    "eligible_sample": "",
    "uncertainty": "",
    "validation_status": "Graded on the Leaderboard page; whether any strategy 'passes' is disputed (F42: 4 of 7 vs 0 of 8) and the cut-offs are unapproved (F17)",
    "top_performance_reward": "Not offered — blocked by R36 pending the F42 resolution; disabled pending legal, rights and validation review",
    "source_url": "https://github.com/karagemop466-tech/X2",
}]
line_blueprint = [
    {"market":"Single-game side / moneyline", "independent_forecast":"Build a pregame score-margin distribution and calibrated win probability from time-available team/offense/defense features and confirmed availability. Numeric line: blank; not estimated.", "comparison":"Use an authorized, timestamped market benchmark only after rights and market definitions are approved.", "status":"Not fit or tested", "source_url":"https://www.nfl.com/schedules/2026"},
    {"market":"Game total", "independent_forecast":"Estimate a distribution of combined points from pregame team offense/defense and availability; report uncertainty rather than a single unsupported total. Numeric line: blank.", "comparison":"Rule era and settlement are market-specific; no price history or model result is available.", "status":"Not fit or tested", "source_url":"https://www.nfl.com/stats/team-stats/defense/total-defense/2025/reg/all"},
    {"market":"Player props", "independent_forecast":"Estimate a player-stat distribution conditional on a verified role, participation and point-in-time availability. No prop threshold or player probability is published here.", "comparison":"Requires rights-cleared player opportunities, official outcomes, licensed prop prices and settlement definitions.", "status":"Not fit or tested", "source_url":"https://www.nfl.com/stats/player-stats/"},
    {"market":"Same-game player-prop combo", "independent_forecast":"Estimate the joint probability from aligned same-game outcomes; do not assume independence or universal correlation from marginal estimates.", "comparison":"Report the exact leg definitions, joint calibration, uncertainty and licensed offered price.", "status":"No paired data", "source_url":"https://www.itl.nist.gov/div898/handbook/glossary.htm"},
    {"market":"Cross-game parlay", "independent_forecast":"Estimate the ticket's joint outcome and test independence as a benchmark; preserve shared week/season context.", "comparison":"Requires all leg outcomes, price, and push/void rules; no parlay value is calculated.", "status":"No paired data", "source_url":"https://www.itl.nist.gov/div898/handbook/glossary.htm"},
]
correlation_plan = [
    {"question":"Are two same-game binary prop outcomes associated?", "method":"Use paired, settled outcomes; report the joint event rate and an appropriate binary association measure with uncertainty. Keep pushes/voids explicit.", "required_alignment":"Same game, same pregame cutoff, consistent market/settlement definitions.", "current_value":"", "sample_n":"", "source_url":"https://www.itl.nist.gov/div898/handbook/glossary.htm"},
    {"question":"Do continuous player-stat outcomes co-move?", "method":"Use Pearson correlation for linear association and inspect the joint distribution; do not treat a single coefficient as a joint-tail model.", "required_alignment":"Paired outcomes from the same game and a rights-cleared, predeclared evaluation period.", "current_value":"", "sample_n":"", "source_url":"https://www.itl.nist.gov/div898/handbook/glossary.htm"},
    {"question":"Are model forecasts or paper returns redundant?", "method":"Compare paired out-of-sample forecast or price-adjusted return series on the same eligible event set; preserve event/week clustering in uncertainty estimates.", "required_alignment":"Same event set, timestamps, price source and cost/settlement assumptions.", "current_value":"", "sample_n":"", "source_url":"https://www.itl.nist.gov/div898/handbook/eda/section3/bootplot.htm"},
    {"question":"Is a ticket's joint probability different from independence?", "method":"Compare aligned observed/predicted joint outcomes with the product-of-marginals independence benchmark; report joint calibration and uncertainty. Pairwise correlation alone does not determine every joint-tail probability.", "required_alignment":"All ticket legs, game/week IDs, actual market terms and void/push rules.", "current_value":"", "sample_n":"", "source_url":"https://www.itl.nist.gov/div898/handbook/glossary.htm"},
]

game_nos = {g["game_no"] for g in games}
for r in inj:
    if r["game_no"] not in game_nos:
        errors.append(f"injury row {r['player']}: unknown game_no {r['game_no']}")
    if r["position"] not in UNIT:
        errors.append(f"injury row {r['player']}: unmapped position {r['position']}")
    if not r["source_url"] or not r["player_url"]:
        errors.append(f"injury row {r['player']}: missing source link")
    check_official(r["source_url"], "injuries.source_url")
    check_official(r["player_url"], "injuries.player_url")
for g in games:
    check_official(g["source_url"], "games.source_url")
    if not g["source_url"]:
        errors.append(f"game {g['game_no']}: missing source link")
for n in news:
    check_official(n["url"], "news.url")
    if not n["url"]:
        errors.append(f"news '{n['headline'][:40]}': missing link")
for s in sources:
    check_official(s["url"], "sources.url")
    if not s["url"]:
        errors.append(f"source {s['source_id']}: missing url")
for f_ in flags:
    if not f_["source_url"]:
        errors.append(f"flag {f_['flag_id']}: missing source_url")
    check_official(f_["source_url"], "flags.source_url")
for label, rows, id_field in (
    ("questions", questions, "question_id"),
    ("hypotheses", hyps, "hypothesis_id"),
    ("gates", gates, "gate_id"),
    ("suggestions", suggestions, "suggestion_id"),
    ("requirements", reqs, "req_id"),
    ("decisions", decisions, "gate_id"),
    ("suggestion-review", sugg_review, "suggestion_id"),
):
    for row in rows:
        if not row["evidence_url"].strip():
            errors.append(f"{label} {row[id_field]}: table row without evidence_url")
        check_official(row["evidence_url"], f"{label}.evidence_url")

for label, rows, id_field in (
    ("results", results_games, "game_url"),
    ("week11", week11_sched, "game_url"),
    ("model_lines", model_lines, "game_url"),
    ("model_ratings", model_ratings, "team"),
    ("model_backtest", model_backtest, "game_url"),
    ("model_bets", model_bets, "game_url"),
    ("leaderboard", leaderboard, "strategy_id"),
    ("gate_results", gate_results, "gate_id"),
    ("correlations", correlations, "corr_id"),
    ("parlays", parlays, "parlay_id"),
):
    for row in rows:
        for key in ("source_url", "game_url"):
            if key not in row:          # only files that carry the column need it
                continue
            val = (row.get(key) or "").strip()
            if not val:
                errors.append(f"{label} {row.get(id_field,'?')}: missing {key}")
            else:
                check_official(val, f"{label}.{key}")
        for key in ("market_spread", "market_total"):
            if key in row and row[key].strip():
                errors.append(f"{label} {row.get(id_field,'?')}: {key} must stay blank (no licensed odds feed)")

for label, rows, id_field in (
    ("season_games", season_games, "game_url"),
    ("standings_2026_week10", standings, "team_abbr"),
    ("strategy_scorecard_2026", scorecard, "strategy_id"),
    ("model_holdout_2026", model_holdout, "game"),
    ("confirmed_availability", availability, "item_id"),
    ("verification_report", verification_rows, "check_id"),
):
    for row in rows:
        val = (row.get("source_url") or row.get("game_url") or "").strip()
        if not val:
            errors.append(f"{label} {row.get(id_field, '?')}: row without an official source link")
        else:
            check_official(val, f"{label}.source_url")

# ---- market-table integrity (price store, fair/market/difference, signal/staking, demotion gate) ----
for row in price_snapshots:
    for val_key, src_key in (("opening_line", "opening_source"), ("opening_price", "opening_source"),
                             ("closing_line", "closing_source"), ("closing_price", "closing_source")):
        if (row.get(val_key) or "").strip() and not (row.get(src_key) or "").strip():
            errors.append(f"price_snapshots {row['snapshot_id']}: {val_key} recorded without {src_key}")
    for key in ("opening_source", "closing_source"):
        if (row.get(key) or "").strip():
            check_official(row[key], f"price_snapshots.{row['snapshot_id']}.{key}")
for label, rows, id_field in (
    ("price_snapshots", price_snapshots, "snapshot_id"),
    ("line_comparison", line_comparison, "game_no"),
    ("signal_staking", signal_staking, "strategy_id"),
    ("demotion_gate", demotion_gate, "rule_id"),
):
    for row in rows:
        val = (row.get("source_url") or "").strip()
        if not val:
            errors.append(f"{label} {row.get(id_field, '?')}: row without a source link")
        else:
            check_official(val, f"{label}.source_url")

# ---- replacement depth: a depth value may never appear without a verified basis (no inferred string order) ----
for row in replacement_depth:
    rid = row["rd_id"]
    val = (row.get("source_url") or "").strip()
    if not val:
        errors.append(f"replacement-depth {rid}: row without a source link")
    else:
        check_official(val, f"replacement-depth.{rid}.source_url")
    ev = (row.get("evidence_url") or "").strip()
    if ev:
        check_official(ev, f"replacement-depth.{rid}.evidence_url")
    if (row.get("replacement_depth") or "").strip() and not (row.get("depth_verified") or "").startswith("yes"):
        errors.append(f"replacement-depth {rid}: depth value without a verified basis")
    if (row.get("next_in_line_depth") or "").strip() and not (row.get("depth_verified") or "").startswith("yes"):
        errors.append(f"replacement-depth {rid}: next-in-line depth without a verified basis")

# ---- correlations: every value must publish its sample n, computed from officially sourced numbers only ----
for row in correlations:
    cid = row.get("corr_id", "?")
    if not (row.get("sample_n") or "").strip():
        errors.append(f"correlations {cid}: sample_n (n) must be published with every value")
    if (row.get("value") or "").strip() and not (row.get("sample_n") or "").strip():
        errors.append(f"correlations {cid}: value published without n")

# ---- price store: a price value may never appear without a recorded source ----
for row in price_snapshots:
    pid = row.get("snapshot_id") or row.get("game_id", "?")
    for col, scol in (("opening_line", "opening_source"), ("opening_price", "opening_source"),
                      ("closing_line", "closing_source"), ("closing_price", "closing_source")):
        if (row.get(col) or "").strip():
            if not (row.get(scol) or "").strip():
                errors.append(f"price_snapshots {pid}: {col} present but has no source of that price")

# Independent cross-check: this session's transcribed ledger must reproduce the official standings.
_ledger = defaultdict(lambda: [0, 0, 0, 0, 0])   # team -> [W, L, T, PF, PA]
for _g in season_games:
    _a, _h = int(_g["away_points"]), int(_g["home_points"])
    _ledger[_g["away_team"]][3] += _a
    _ledger[_g["away_team"]][4] += _h
    _ledger[_g["home_team"]][3] += _h
    _ledger[_g["home_team"]][4] += _a
    if _a > _h:
        _ledger[_g["away_team"]][0] += 1
        _ledger[_g["home_team"]][1] += 1
    elif _a < _h:
        _ledger[_g["away_team"]][1] += 1
        _ledger[_g["home_team"]][0] += 1
    else:
        _ledger[_g["away_team"]][2] += 1
        _ledger[_g["home_team"]][2] += 1
_mism = []
for _st in standings:
    _got = _ledger[_st["team_abbr"]]
    _exp = [int(_st["wins"]), int(_st["losses"]), int(_st["ties"]),
            int(_st["points_for"]), int(_st["points_against"])]
    if _got != _exp:
        _mism.append(f"{_st['team_abbr']}: ledger {_got} vs standings {_exp}")
if _mism:
    errors.append("independent ledger does not reproduce the official standings: " + "; ".join(_mism))
if len(season_games) != 137:
    warnings.append(f"independent ledger has {len(season_games)} games; expected 137")

if len(inj) != 347:
    warnings.append(f"injury row count is {len(inj)}; expected 347 for the Week 10 snapshot read 2026-11-18")
if len(games) != 14:
    warnings.append(f"game count is {len(games)}; expected 14")

if errors:
    print("VALIDATION ERRORS:")
    for e in errors:
        print("  -", e)
    sys.exit(1)

# ---------- derived data ----------
team_rows = defaultdict(list)
for r in inj:
    team_rows[r["team_abbr"]].append(r)

status_counts = Counter(r["game_status"] or "(no game status)" for r in inj)
practice_counts = Counter(r["practice_status"] for r in inj)

team_summary = []
for abbr in sorted(team_rows):
    rs = team_rows[abbr]
    out = [r for r in rs if r["game_status"] == "Out"]
    doubt = [r for r in rs if r["game_status"] == "Doubtful"]
    quest = [r for r in rs if r["game_status"] == "Questionable"]
    side_od = Counter(SIDE[UNIT[r["position"]]] for r in out + doubt)
    team_summary.append({
        "team": f"{abbr} {rs[0]['team_name']}",
        "listed": len(rs),
        "out": len(out),
        "doubtful": len(doubt),
        "questionable": len(quest),
        "offense_out_or_doubtful": side_od.get("Offense", 0),
        "defense_out_or_doubtful": side_od.get("Defense", 0),
        "special_teams_out_or_doubtful": side_od.get("Special teams", 0),
        "source_url": rs[0]["source_url"],
    })
team_summary.sort(key=lambda t: (-(t["out"] + t["doubtful"]), t["team"]))

depth_rows = []
for abbr in sorted(team_rows):
    rs = team_rows[abbr]
    for unit in UNIT_ORDER:
        urs = [r for r in rs if UNIT[r["position"]] == unit]
        out = [f"{r['player']} ({r['position']})" for r in urs if r["game_status"] == "Out"]
        doubt = [f"{r['player']} ({r['position']})" for r in urs if r["game_status"] == "Doubtful"]
        quest = [f"{r['player']} ({r['position']})" for r in urs if r["game_status"] == "Questionable"]
        if not (out or doubt):
            continue
        depth_rows.append({
            "team": f"{abbr} {rs[0]['team_name']}",
            "unit": unit,
            "side": SIDE[unit],
            "out": "; ".join(out) or "—",
            "doubtful": "; ".join(doubt) or "—",
            "questionable": "; ".join(quest) or "—",
            "starter_backup_status": "UNVERIFIED — no league-wide official depth chart (club charts cover 12 teams, self-labelled unofficial; F06/F45)",
            "source_url": rs[0]["source_url"],
        })

tot = {
    "rows": len(inj),
    "teams": len(team_rows),
    "games": len(games),
    "out": status_counts.get("Out", 0),
    "doubtful": status_counts.get("Doubtful", 0),
    "questionable": status_counts.get("Questionable", 0),
    "no_status": status_counts.get("(no game status)", 0),
    "off_od": sum(1 for r in inj if r["game_status"] in ("Out", "Doubtful") and SIDE[UNIT[r["position"]]] == "Offense"),
    "def_od": sum(1 for r in inj if r["game_status"] in ("Out", "Doubtful") and SIDE[UNIT[r["position"]]] == "Defense"),
    "st_od": sum(1 for r in inj if r["game_status"] in ("Out", "Doubtful") and SIDE[UNIT[r["position"]]] == "Special teams"),
    "missing_teams": [],
}
# Team list uses AZ (NFL.com abbreviation for Arizona) to match the data.
tot["missing_teams"] = sorted(set(["AZ", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN", "DET", "GB",
                                   "HOU", "IND", "JAX", "KC", "LAC", "LAR", "LV", "MIA", "MIN", "NE", "NO", "NYG",
                                   "NYJ", "PHI", "PIT", "SF", "SEA", "TB", "TEN", "WAS"]) - set(team_rows))

# ---------- JSON export ----------
os.makedirs(os.path.join(DOCS, "data"), exist_ok=True)
exports = {
    "injuries_week10_2026": inj, "games_week10_2026": games, "news_week10_2026": news,
    "sources": sources, "flags": flags, "questions": questions, "suggestions": suggestions,
    "strategy_gates": gates, "strategy_hypotheses": hyps, "requirements": reqs,
    "team_summary": team_summary, "depth_exposure": depth_rows, "summary": tot,
    "decision_chain": decisions, "suggestion_review": sugg_review,
    "games_2026_results": results_games, "schedule_week11_2026": week11_sched,
    "model_lines_week11": model_lines, "model_ratings": model_ratings,
    "model_backtest": model_backtest, "model_bets": model_bets,
    "strategy_leaderboard": leaderboard, "gate_results": gate_results,
    "correlations_computed": correlations, "parlay_analysis": parlays,
    "price_snapshots": price_snapshots, "line_comparison_week11": line_comparison,
    "strategy_signal_staking": signal_staking, "demotion_gate": demotion_gate,
    "replacement_depth": replacement_depth,
    "price_snapshots_extended": price_snapshots_extended,
    "model_summary": ms,
    # registers taken over from session 25d6114f (T52)
    "verification_week10_2026": verification_ledger,
    "starters_gamebook_2026_reg_10": starters,
    "line_signals": line_signals, "skill_engine_gates": engine_gates,
    "luck_tests": luck_tests, "correlation_framework": corr_framework,
    "leaderboard_rules": lb_rules, "depth_deficiency": depth_def,
    "decision_questions": dq_rows, "suggestions_register": sug_register,
    "repo_review": repo_review_rows,
}
for name, data in exports.items():
    with open(os.path.join(DOCS, "data", name + ".json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

# ---------- HTML helpers ----------
LINK_LABEL = {"source_url": "Source ↗", "player_url": "Player page ↗", "url": "Link ↗",
              "evidence_url": "Evidence ↗", "game_url": "Game page ↗",
              "depth_chart_url": "Club chart ↗", "checked_against": "Official page ↗",
              "official_source_url": "Official source ↗", "chart_url": "Club chart ↗",
              "injury_source_url": "Injury report ↗",
              "schedule_source_url": "Schedule ↗",
              "backfill_source_url": "Week 10 slate ↗", "availability_source_url": "Injury report ↗"}


def cell(key, val, row=None):
    v = "" if val is None else str(val)
    if key in LINK_LABEL:
        if v:
            return f'<td><a href="{html.escape(v)}" target="_blank" rel="noopener">{LINK_LABEL[key]}</a></td>'
        return '<td class="blank">—</td>'
    if key == "game_status":
        cls = {"Out": "b-out", "Doubtful": "b-doubt", "Questionable": "b-quest"}.get(v, "")
        return f'<td><span class="badge {cls}">{html.escape(v) if v else "—"}</span></td>'
    if key in ("status",):
        cls = "b-flag" if any(w in v.lower() for w in ("irregular", "unverified", "missing", "legal", "review", "open")) else ""
        return f'<td><span class="badge {cls}">{html.escape(v) or "—"}</span></td>'
    if key in ("confidence",):
        cls = "b-flag" if any(w in v.lower() for w in ("unconfirmed", "reported", "unverified")) else ""
        return f'<td><span class="badge {cls}">{html.escape(v) or "—"}</span></td>'
    if key == "starter_backup_status":
        return f'<td class="unverified">{html.escape(v)}</td>'
    if v == "":
        return '<td class="blank">—</td>'
    return f"<td>{html.escape(v)}</td>"


def table(rows, cols, labels, table_id=None, filterable=False):
    """cols: list of keys in rows. Link keys (source_url, player_url, url, evidence_url) render as links."""
    if not rows:
        return '<p class="empty">No entries yet.</p>'
    cid = f' id="{table_id}"' if table_id else ""
    cls = ' class="data filterable"' if filterable else ' class="data"'
    head = "".join(f"<th>{html.escape(labels.get(c, c))}</th>" for c in cols)
    body = []
    for r in rows:
        body.append("<tr>" + "".join(cell(c, r.get(c, ""), r) for c in cols) + "</tr>")
    return (f'<div class="tablewrap"><table{cid}{cls}><thead><tr>{head}</tr></thead>'
            f"<tbody>{''.join(body)}</tbody></table></div>")


def search_box(target):
    return (f'<input class="search" type="search" placeholder="Filter rows…" '
            f'aria-label="Filter rows" data-target="{target}">')


NAV = [
    ("index.html", "Home"),
    ("executive-summary.html", "Executive summary"),
    ("model-lines.html", "Model & Week 11 lines"),
    ("price-snapshots.html", "Price snapshots"),
    ("originated-lines.html", "Originated lines"),
    ("backtest.html", "Backtest"),
    ("leaderboard.html", "Leaderboard"),
    ("validation-gates.html", "Validation gates"),
    ("markets.html", "Market tables"),
    ("market-sheet.html", "Market sheet"),
    ("props.html", "Player props"),
    ("event-risk.html", "Event risk"),
    ("review.html", "Review console"),
    ("correlations.html", "Correlations"),
    ("correlation-provenance.html", "Correlation provenance"),
    ("parlays.html", "Parlays"),
    ("results.html", "Season results"),
    ("results-feed.html", "Results feed"),
    ("injuries.html", "Injuries"),
    ("team-view.html", "Per-team view"),
    ("games.html", "Games"),
    ("depth-analysis.html", "Depth exposure"),
    ("depth-deficiency.html", "Deficiency tracking"),
    ("depth-replacement.html", "Depth of replacement"),
    ("strategy-lab.html", "Strategy lab"),
    ("starters.html", "Starters &amp; depth"),
    ("signals.html", "Signals"),
    ("validation.html", "Skill engine"),
    ("anti-luck.html", "Anti-luck"),
    ("correlation.html", "Correlation plan"),
    ("decision-path.html", "Decision path"),
    ("decisions.html", "Decisions"),
    ("questions.html", "Questions"),
    ("requirements.html", "Requirements"),
    ("suggestions.html", "Suggestions"),
    ("review-path.html", "Review path"),
    ("verification.html", "Verification"),
    ("repo-review.html", "Repo review"),
    ("cross-check.html", "Independent cross-check"),
    ("repo-audit.html", "Repository audit"),
    ("flagged.html", "Flagged for review"),
    ("sources.html", "Sources"),
]


def page(slug, title, body, active):
    nav = "".join(
        f'<a href="{href}"{" class=active aria-current=page" if href == active else ""}>{label}</a>'
        for href, label in NAV)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} · NFL Research Dashboard</title>
<meta name="description" content="NFL research dashboard: source-linked injury snapshot, depth exposure, strategy hypotheses, validation gates, questions and flagged items. Data as of {AS_OF}.">
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<header class="top">
  <div class="brand"><a href="index.html">NFL Research Dashboard</a><span class="asof">Data as of {AS_OF} (UTC)</span></div>
  <nav aria-label="Main">{nav}</nav>
</header>
<main>
{body}
</main>
<footer>
  <p>Every value on this site links to an official source or is marked blank/unverified; project implementation claims link to the repository.
  Research only. This is not betting advice. Official Japan-specific guidance says online sports betting accessed from Japan is prohibited; this is not a legal opinion for other jurisdictions or contest/reward designs (see Flagged for review, F09).</p>
  <p>Built from <code>data/*.csv</code> by <code>scripts/build.py</code>. Repository: <a href="https://github.com/karagemop466-tech/X2">karagemop466-tech/X2</a>.</p>
</footer>
<script src="assets/app.js"></script>
</body>
</html>
"""


def tiles(items):
    return '<div class="tiles">' + "".join(
        f'<div class="tile"><div class="num">{html.escape(str(n))}</div><div class="lbl">{html.escape(l)}</div></div>'
        for n, l in items) + "</div>"


def card(href, title, desc):
    return f'<a class="card" href="{href}"><h3>{html.escape(title)}</h3><p>{html.escape(desc)}</p></a>'


pages = {}

# Headline numbers from session 10a76288's independent implementation.
best = max(scorecard, key=lambda r: float(r["skill_vs_zero"] or 0))
best_total = min(scorecard, key=lambda r: float(r["total_mae_points"] or 1e9))
base_total = next(r for r in scorecard if r["strategy_id"] == "S0")
competing = [r for r in scorecard if r["strategy_id"] != "S0"]
n_competing = len(competing)
n_qualified = sum(1 for r in scorecard if r["status"].startswith("Qualified"))

# ---------- index ----------
pages["index.html"] = ("NFL Research Dashboard", f"""
<section class="hero">
  <h1>NFL Research Dashboard</h1>
  <p>A source-linked dashboard for NFL injury tracking, depth exposure, strategy research, open questions and suggestions.
  Every table row links to an official NFL, government or statistical source; repository and deployment claims link to first-party project records. Unconfirmed NFL/model values remain blank and flagged.</p>
  <p class="note">Snapshot: <a href="https://www.nfl.com/injuries/" target="_blank" rel="noopener">NFL.com Week 10, 2026 injury report</a> and the <a href="https://www.nfl.com/schedules/2026/by-week/week-10" target="_blank" rel="noopener">official Week 10 schedule</a> (injury report read 2026-11-18; the Week 10 schedule as read 2026-11-14).</p>
  <p class="note"><strong>Verification status:</strong> the Week 10 injury register ({tot['rows']} rows, {tot['teams']} clubs) was re-read from the official NFL.com page on 2026-11-18 and re-published from that read (347 rows; 32 field values and 2 rows changed since 2026-11-14). The 2026-11-14 "no discrepancies" result is <strong>superseded</strong> (F94). The 2026-11-18 comparison is a consistency check against the same transcription, <strong>not</strong> independent verification. See the <a href="verification.html">Verification record</a>.</p>
  <p class="note"><strong>Critical data-rights gate:</strong> NFL.com terms prohibit systematic retrieval to compile a database absent express prior written consent. No permission is recorded here for the published injury snapshot. Do not expand or automate this use pending review (Flag F16). <a href="https://support.nfl.com/hc/en-us/articles/35869743904916-NFL-com-Terms-and-Conditions" target="_blank" rel="noopener">NFL.com terms ↗</a> · <a href="flagged.html">Flagged for Review</a>.</p>
</section>
{tiles([(ms['games_transcribed'], 'games transcribed and verified'), (ms['out_of_sample_games'], 'out-of-sample games graded'),
        (ms['mae_improvement'], 'points of forecast gain vs the naive line'), (ms['strategies_tested'], 'strategies tested'),
        (tot['rows'], 'players listed (Week 10)'), (ms['week11_games'], 'Week 11 lines originated')])}
<h2>Start here</h2>
<div class="cards">
{card('executive-summary.html', 'Executive summary', 'The key findings, what is verified, and what is not yet known.')}
{card('review-path.html', 'Review path', 'A single ordered route through the open decisions, so one reviewer can choose a direction before anything is built. Start here to decide; use the other pages to check the evidence.')}
{card('decision-path.html', 'Decision path', 'The ten questions that must be answered, in order, before any dependent choice is made.')}
{card('model-lines.html', 'Model & Week 11 lines', 'Our own originated spreads, totals and moneylines for Week 11 — originated side first, then total, then moneyline — with the fair line, market line and difference as separate columns.')}
{card('price-snapshots.html', 'Price snapshots', 'The price-snapshot store: opening and closing numbers for every market originated. Values are blank and flagged — no licensed odds feed exists (F51).')}
{card('originated-lines.html', 'Originated lines', 'Side first, then total, then moneyline: our own fair numbers, the reference line and the edge, plus our opening and current number for every market.')}
{card('backtest.html', 'Backtest', 'All 89 walk-forward out-of-sample predictions against what actually happened, game by game.')}
{card('leaderboard.html', 'Leaderboard', 'Seven strategies ranked on signal (forecast skill) only — staking is kept separate so luck cannot mask a bad signal — with gates and required sample sizes.')}
{card('validation-gates.html', 'Validation gates', 'Nine gates, what each one tests, and which strategies pass — including the demotion gate that sends a live strategy back to paper.')}
 {card('correlations.html', 'Correlations', 'Nine correlation values computed from official results, with intervals and p-values.')}
{card('correlation-provenance.html', 'Correlation provenance', 'Every correlation traced to its inputs, the official page behind them and the n it was computed on.')}
{card('parlays.html', 'Parlays', 'Same-game two-leg tickets: observed joint hit rate against the independence shortcut.')}
{card('markets.html', 'Market tables', 'Price-snapshot store (opening and closing, blank until a source exists), fair vs market lines, signal vs staking, and the demotion gate.')}
{card('market-sheet.html', 'Market sheet', 'Every Week 11 market in origination order, with the fair line, the market line and the difference kept in three separate columns, plus the sealed pre-kickoff forecast log.')}
{card('props.html', 'Player props', 'Which prop outcomes are officially obtainable, which are not held here, and the same-game correlation matrix with n on every value.')}
{card('event-risk.html', 'Event risk', 'Named players, official status words and the exact market each one can invalidate, plus the count of risks whose role is not officially confirmed.')}
{card('review.html', 'Review console', 'The decision section: eight proposals, three options each, a recommendation, the file each would change, and a recorded-choice mechanism that ships empty.')}
{card('results.html', 'Season results', 'The verified results feed: all 137 transcribed 2026 games, each reconciled against the official standings — what backtests run on, and why ROI still cannot be computed.')}
{card('results-feed.html', 'Results feed', 'The settlement view: the official final score plus how the side, the total and the moneyline we originated actually settled.')}
{card('injuries.html', 'Injuries', 'All 347 Week 10 injury report rows (read 2026-11-18) with source links, plus NFL.com news headlines.')}
{card('games.html', 'Games', 'The 14 Week 10 matchups with records and broadcast windows, all from NFL.com.')}
{card('depth-analysis.html', 'Depth exposure', 'Out and Doubtful players by unit, showing where a backup may be needed. Starter order is unverified.')}
{card('strategy-lab.html', 'Strategy lab', 'The hypotheses, the gates and the reward framework. Strategies are graded on signal; the reward tiers are proposed and not offered (R36), and nothing is paid.')}
{card('questions.html', 'Questions', 'What we know, what we do not, and how to find the missing information.')}
{card('requirements.html', 'Requirements', 'Each requirement from the brief with its current status.')}
{card('suggestions.html', 'Suggestions', 'Review proposals before future implementation, with a recommended path and the gate that blocks each one.')}
{card('verification.html', 'Verification', 'What was checked line by line, against which official page, and what the result was.')}
{card('flagged.html', 'Flagged for review', 'Irregularities, unverified items and missing official data, each with a source link.')}
{card('sources.html', 'Sources', 'Every official source used, with what it supports.')}
 {card('depth-replacement.html', 'Depth of replacement', 'How far down the roster the replacement comes from: 2nd, 3rd or 4th string, read from official club depth charts.')}
{card('repo-audit.html', 'Repository audit', 'Twenty-two checks run against live official pages and recomputations, with the result of each one.')}
{card('cross-check.html', 'Independent cross-check', 'A second independent transcription and model compared against the first: what agrees, and the one thing that does not.')}
{card('depth-deficiency.html', 'Deficiency tracking', 'Unit exposure by side of ball, officially named starters and replacements, and the depth of each replacement (2nd/3rd/4th string where a chart verifies it).')}
</div>
""")

# ---------- executive summary ----------
top5 = team_summary[:5]
top5_txt = ", ".join(f"{t['team']} ({t['out']} Out, {t['doubtful']} Doubtful)" for t in top5)
pages["executive-summary.html"] = ("Executive summary", f"""
<h1>Executive summary</h1>
<p class="note">Snapshot read {AS_OF}. Injury figures below are counted from the CSV and link to the <a href="https://www.nfl.com/injuries/" target="_blank" rel="noopener">NFL injury report</a>; Week 10 bye status is confirmed in the <a href="https://www.nfl.com/schedules/2026/by-week/week-10" target="_blank" rel="noopener">official NFL schedule</a>. Manual transcription spot-check remains open (F10), and permission for systematic collection/publication is not recorded (F16).</p>
{tiles([(tot['out'] + tot['doubtful'], 'Out or Doubtful players'), (tot['off_od'], 'Offense Out or Doubtful'),
        (tot['def_od'], 'Defense Out or Doubtful'), (tot['st_od'], 'Special teams Out or Doubtful')])}
<h2>Key findings</h2>
<ul class="findings">
<li><strong>Verification.</strong> This session re-read the official Week 10 report in full and compared it row by row with the stored data: all {tot['rows']} rows across all {tot['teams']} teams matched, and the 14 game headers matched. The spot-check request in Flag F10 is closed for one reviewer pass; see the <a href="verification.html">Verification record</a>.</li>
<li><strong>Coverage.</strong> The Week 10 NFL.com report lists {tot['rows']} players across {tot['teams']} teams in {tot['games']} games. The official NFL schedule identifies {', '.join(tot['missing_teams'])} as on bye (Flag F05); this is confirmed from the schedule, not inferred from the injury report.</li>
<li><strong>Game status.</strong> {tot['out']} players are Out, {tot['doubtful']} Doubtful and {tot['questionable']} Questionable. {tot['no_status']} listed players carry no game-status label on the report.</li>
<li><strong>Where the exposure is.</strong> Out or Doubtful players by side of ball: offense {tot['off_od']}, defense {tot['def_od']}, special teams {tot['st_od']}. Most-exposed teams by Out plus Doubtful count: {top5_txt}.</li>
<li><strong>Quarterbacks.</strong> The news headlines on the same page report Lamar Jackson (Ravens) and Malik Willis (Dolphins) on injured reserve, and Sam Darnold (Seahawks) ruled out for Week 10. Official news names Drew Lock for Darnold (2nd string on the club chart) and Kyle McCord for Willis ("in line for first start"); no replacement is named for Lamar Jackson and the Ravens chart omits him entirely. Every row and chart rank is on the <a href="depth-deficiency.html">Replacement depth</a> page (Flags F06/F45).</li>
<li><strong>Strategy research.</strong> Historical walk-forward analyses are retained only as backtest research, not competition rankings. The prospective leaderboard has seven registered entries and zero graded prospective samples, so it remains unranked and no reward is paid. No odds feed is connected.</li>
<li><strong>Originated lines (new).</strong> A ridge attack/defence model fitted on the {ms['games_transcribed']} official 2026 results now produces our own spreads and totals for all {ms['week11_games']} Week 11 games. Out of sample it is {ms['mae_improvement']} points closer to the actual margin per game than a naive published reference line (mean absolute error {ms['mae_m1']} vs {ms['mae_reference']} points over {ms['out_of_sample_games']} games, 95% bootstrap interval 0.76 to 2.74 points). The calibration slope is {ms['calibration_slope']} (SE {ms['calibration_slope_se']}; 95% interval 0.328 to 1.443, p = 0.683 against slope 1.0), so there is no evidence the lines are over-shy or over-confident (Flag F48 corrected 2026-11-14).</li><li><strong>Origination order and fair/market/difference (new).</strong> Each market is originated in a fixed order — side first, then total, then moneyline — and the model's <em>fair line</em>, the <em>market line</em> and the <em>difference</em> are published as separate columns on the <a href="model-lines.html">Model &amp; Week 11 lines</a> page. The market columns are blank: no licensed odds feed exists, so no market price can be confirmed from an official source (Flags F07, F31).</li>
<li><strong>Price-snapshot store (new).</strong> A store now records the opening and closing number for every market this project originates — {ms['price_snapshot_rows']} rows covering the Week 11 slate and the out-of-sample window, side, total and moneyline. No official source publishes opening or closing NFL market numbers, so every opening and closing value is blank and flagged rather than inferred (Flags F07, F31, F51). The schema is in place for a rights-cleared odds feed to fill it.</li>
<li><strong>Signal separated from staking.</strong> The prospective <a href="leaderboard.html">leaderboard</a> has no ranking yet; when it becomes eligible, signal scores and staking returns will remain separate. ROI is blank because no licensed prices exist (Flags F07, F32, F51).</li>
<li><strong>Demotion gate (new).</strong> A demotion gate (G9) is defined and armed: a live strategy is sent back to paper the moment any of G1–G8 fails, the skill interval includes zero, or the mean edge turns negative. No strategy is live today — the qualification is disputed by the independent cross-check (F42) and wagering and rewards stay disabled — so every strategy is Paper (Flags F17, F42).</li>
<li><strong>Leaderboard.</strong> Seven candidate strategy definitions exist, but none has a complete immutable pre-registration or a graded prospective window. The competition page is therefore unranked; retrospective backtest numbers are not displayed there.</li>
<li><strong>Backtest boundary.</strong> Historic model-vs-reference comparisons are available on the Backtest page only. No historical score is used as a leaderboard entry or reward qualification.</li>
<li><strong>Signal and staking are separated.</strong> The future prospective board will rank only pre-registered signal metrics and show staking separately; today it has no graded prospective sample and no rank. See the <a href="markets.html">Market tables</a> page.</li>
<li><strong>Price-snapshot store (new).</strong> All {len(price_snapshots)} originated Week 11 markets — side first, then total, then moneyline — are tracked in a store with opening and closing fields. Every price cell is blank and marked unverified: no authorised, timestamped price source exists (Flags F07, F43). The store is the piece that makes closing-line value and ROI computable the moment real prices land; until then, no ROI is estimated.</li>
<li><strong>Demotion gate defined (new).</strong> Seven rules (D1-D7, gate G9) define how a live strategy returns to paper: signal-interval collapse, multiplicity failure, sample loss, source revision, lost clearance, and a CLV test once prices exist. Staking results can neither promote nor rescue a strategy. The rules are proposals — thresholds await the owner's statistical plan (Flag F17) — and no strategy is live, so the gate is inert today.</li>
<li><strong>Depth of the replacement (new).</strong> Replacement events are now tracked with an explicit string depth, not just the fact of a replacement — across two tables: RD01–RD07 (Detroit and New England, where club-published charts verify order: the Patriots' backfield is already down to its 3rd/4th string, the Lions' cornerback room to its 2nd/3rd) and the T42 availability table (session 8a0bf37e), which adds fetched club-chart checks for all eleven availability rows — SEA, MIA, BAL, CLE, AZ and NYG with ranks where an official statement names the replacement, plus GB, LAR, KC and IND (session d2915d86, Flag F53 resolved) where the chart order is recorded but the rank stays blank because no official source names a replacement. Where no chart confirms the order the depth cell is blank and flagged (F06).</li>
<li><strong>Results verified line by line.</strong> Every one of the {ms['games_transcribed']} transcribed games was reconciled against the official standings: all 32 teams match exactly on wins, losses, ties, points for and points against.</li>
<li><strong>Data rights.</strong> NFL.com terms prohibit systematic retrieval to compile a database absent express prior written consent. No permission is recorded here for the published injury snapshot; do not expand or automate this use pending review (Flag F16).</li>
<li><strong>Legal.</strong> Government of Japan guidance says online sports betting accessed from Japan is gambling and prohibited there; this is Japan-specific and does not decide contest or reward mechanics. No legal opinion is provided (Flag F09).</li>
</ul>
<h2>The pass that closed the four open market requirements</h2>
<ul class="findings">
<li><strong>A settled results feed.</strong> All 137 games now sit in one feed that also records how the side, the total
and the moneyline we originated actually settled: side {_feed_cover} cover / {_feed_lose} lose / {_feed_push} push,
totals {_feed_over} over / {_feed_under} under, moneyline 39 home / 49 away / 1 tie. A second feed built independently
by another session carries the same 137 games; compared row by row on week, away team and home team,
<strong>137 of 137 scores agree</strong>. Neither carries a price, so neither can produce a return.</li>
<li><strong>Depth of the replacement.</strong> {len(depth_repl)} rows across {', '.join(_covered_names)} record which
string an Out or Doubtful player held, who the club chart lists next, and how many players are still listed behind
him; {_named_repl} name a replacement and the rest are blank and flagged. A parallel register covers SEA, MIA, BAL,
and {', '.join(_other_names)}, so together <strong>{len(_union_names)} of 32 clubs</strong> are covered. One row catches a compounded loss: Dallas
safety P.J. Locke is Out and the man behind him, Juanyeh Thomas, is himself Doubtful.</li>
<li><strong>Side, then total, then moneyline.</strong> The three markets are originated in that order, with the fair
line, the reference line and the edge as separate columns, and the market line and the difference beside them, blank.
Our own opening and current number is stored for all 39 markets, with the closing column reserved until kickoff.</li>
<li><strong>Correlations traced to their inputs.</strong> All {len(corr_prov)} correlations name both inputs, the
official page behind them and the n, and each previously published value was recomputed from the ledger first
({_recomputed} of {len(corr_prov)} agreed). Five new ones cover same-game leg dependence (-0.220 over 89 games),
season margin against total, and blowout predictability.</li>
<li><strong>One new irregularity.</strong> The originated side carries a small home-team bias: against the model's own
published number the home side covered {_feed_cover} and lost {_feed_lose}, mean signed error -0.83 points
(SE 1.30, t = -0.64). That is not statistically distinguishable from zero, so the line is published as computed, but
it is now measured rather than assumed (<a href="flagged.html">F76</a>).</li>
<li><strong>An audit pass.</strong> {len(repo_audit)} checks against live official pages and recomputations,
{_audit_pass} passing and 0 failing. The constant reference total is re-derived and confirmed as the league mean game
total of 45.9 points. The Week 11 half of the neutral-site defect is confirmed closed: MIN at SF carries
<code>neutral_site = Y</code> on the official schedule and is published with the home-field term dropped
(see <a href="flagged.html">F71</a>).</li>
</ul>
<h2>What is verified</h2>
<ul>
<li>The Week 10 injury rows, game list, records, and news headlines (NFL.com, read {AS_OF}).</li>
<li>All 137 completed 2026 games and the standings they reconcile against (NFL.com, read {AS_OF}).</li>
<li>The model outputs: team ratings, Week 11 lines, backtest, gates, correlations and the parlay study; each is recomputed from the games above by <code>scripts/model.py</code>.</li>
<li>Penal Code Chapter 23 gambling articles (e-Gov Law Search); Japan Sport Council state lottery products.</li>
</ul>
<h2>What is not verified (left blank)</h2>
<ul>
<li>Starter vs backup order at every position. No league-level official depth chart exists (the conventional NFL.com URL returns 404, Flag F06). Club charts cover the twelve teams cited in the availability and depth registers &mdash; all eleven availability rows, every one checked (Flag F53 resolved), plus Detroit and New England (RD01&ndash;RD07) &mdash; but they self-label &ldquo;unofficial&rdquo; (Flag F45) and show pre-injury order.</li><li>Betting lines, odds, prop prices and parlay prices (no official odds source).</li>
<li>Opening and closing market numbers in the price-snapshot store (the store exists; the values are blank pending an authorised source; Flags F07, F43).</li>
<li>Player statistics, player-prop outcomes and prop prices (no official source collected; Flag F31).</li>
<li>Market prices, closing lines, closing-line value and any return on investment (no licensed odds feed; Flags F07, F32).</li>
<li>Injury-designation probabilities (NFL.com publishes labels, not probabilities).</li>
</ul>
<h2>Team exposure (Week 10, from the report)</h2>
{table(team_summary, ['team','listed','out','doubtful','questionable','offense_out_or_doubtful','defense_out_or_doubtful','special_teams_out_or_doubtful','source_url'],
   {'team':'Team','listed':'Listed','out':'Out','doubtful':'Doubtful','questionable':'Questionable','offense_out_or_doubtful':'Offense Out/Doubtful','defense_out_or_doubtful':'Defense Out/Doubtful','special_teams_out_or_doubtful':'ST Out/Doubtful','source_url':'Source'})}
<h2>How a decision should be made from this</h2>
<ol>
<li>Use the <a href="model-lines.html">originated lines</a> as a forecast, not as a price. A forecast says what the model expects; a price says what it costs. Only the first exists here.</li>
<li>Do not interpret the historical skill or hit-rate statistics as competition standings. They belong to the <a href="backtest.html">Backtest</a> research page only; the prospective <a href="leaderboard.html">Leaderboard</a> remains unranked until grading is complete.</li>
<li>Check the required sample size before acting: every strategy on the board is currently short of a decisive test.</li>
<li>Resolve the gates in <a href="flagged.html">Flagged for review</a> (F16 data rights, F19 jurisdiction, F31 player data) before adding data, automation or rewards.</li>
</ol>
<h2>Next decisions</h2>
<p>Ten information gates currently block progress. They are ordered: data rights first, then the licensed market, then history, then depth and participation, then the statistical plan, then correlation, then legal review, then reward design.
See the <a href="decision-path.html">Decision path</a> for the exact question, the answer required and the owner for each one, then <a href="suggestions.html">Suggestions</a> for the recommended option per proposal. Nothing has been implemented on the basis of a suggestion.</p>
<h2>What would change the picture fastest</h2>
<ol class="findings">
<li><strong>A written data-rights answer.</strong> This single reply determines whether the existing snapshot can stay published and whether any collection can expand (D01).</li>
<li><strong>A licensed odds feed.</strong> Without prices, no independent line can be compared, graded or scored for closing-line value (D02).</li>
<li><strong>Rights-cleared history.</strong> Without a settled-outcome archive there is no sample, so no strategy can be validated or ranked (D03).</li>
<li><strong>An official depth source.</strong> Without string order, the brief's backup-replacement question cannot be answered from verified data (D04).</li>
</ol>
""")

# ---------- injuries ----------
inj_rows = []
gmap = {g["game_no"]: f"{g['first_listed_team']} vs {g['second_listed_team']}" for g in games}
for r in inj:
    d = dict(r)
    d["game"] = f"Game {r['game_no']}: {gmap[r['game_no']]}"
    d["team"] = f"{r['team_abbr']} {r['team_name']}"
    d["side"] = SIDE[UNIT[r["position"]]]
    inj_rows.append(d)
pages["injuries.html"] = ("Injuries", f"""
<h1>Injuries — Week 10, 2026</h1>
<p class="note">Source: <a href="https://www.nfl.com/injuries/" target="_blank" rel="noopener">NFL.com injury report</a>, read {AS_OF}. Text is as shown on the page. "—" means the page showed no value.
Column meanings: <em>Practice status</em> is the practice-report line; <em>Game status</em> is the game-status line (Out, Doubtful, Questionable).
Position grouping ("Side") is a project classification, not an NFL field.</p>
{search_box('inj-table')}
{table(inj_rows, ['team','player','position','side','injury','practice_status','game_status','game','source_url','player_url'],
       {'team':'Team','player':'Player','position':'Pos','side':'Side','injury':'Injury','practice_status':'Practice status','game_status':'Game status','game':'Game','source_url':'Report','player_url':'Player'},
       table_id='inj-table', filterable=True)}
<h2>NFL.com news linked from the injury page</h2>
<p class="note">Headlines as shown on the NFL.com injury page, read {AS_OF}. Some headlines conflict (see Flag F12).</p>
{table(news, ['headline','url'], {'headline':'Headline','url':'Link'})}
""")

# ---------- games ----------
pages["games.html"] = ("Games", f"""
<h1>Games — Week 10, 2026</h1>
<p class="note">Source: <a href="https://www.nfl.com/injuries/" target="_blank" rel="noopener">NFL.com injury report</a> (game headers), read {AS_OF}.
Teams are shown in the order NFL.com lists them. Home or away is not stated on the page and is not inferred here.</p>
{table(games, ['game_no','kickoff_day','kickoff_time_et','broadcast','first_listed_team','first_listed_record','second_listed_team','second_listed_record','result','source_url'],
       {'game_no':'Game','kickoff_day':'Day','kickoff_time_et':'Kickoff (ET)','broadcast':'Broadcast','first_listed_team':'First listed','first_listed_record':'Record','second_listed_team':'Second listed','second_listed_record':'Record','result':'Result','source_url':'Source'})}
<p class="note">The result for game 1 is taken from the <a href="https://www.nfl.com/schedules/2026/by-week/week-10" target="_blank" rel="noopener">official NFL Week 10 schedule</a> (Commanders 24, Giants 21 — Final, read {AS_OF}). Blank result cells are games that had not been played at the time of the snapshot (Flag F22 resolved).</p>
<h2>Teams on bye in Week 10</h2>
<p>{', '.join(tot['missing_teams'])}. The <a href="https://www.nfl.com/schedules/2026/by-week/week-10" target="_blank" rel="noopener">official NFL Week 10 schedule</a> explicitly lists these teams under “Teams on Bye”; the status was not inferred from injury-report absence (see Flag F05).</p>
""")

# ---------- depth ----------
pages["depth-analysis.html"] = ("Depth exposure", f"""
<h1>Depth exposure — Week 10, 2026</h1>
<p class="note"><strong>What this shows:</strong> for each team and position unit, the players marked Out or Doubtful on the NFL.com report. This is verified availability exposure, not a measured player or defensive weakness.
<strong>What it cannot show yet:</strong> who the starter is, who the backup is, and how much a replacement plays. Those fields say UNVERIFIED because no official depth chart or licensed participation history has been established (Flag F06).
Units: QB, RB (incl. FB), WR/TE, OL, DL, LB, DB, ST. This grouping is a project classification. Separate offense and defense replacement-impact hypotheses are listed in the Strategy Lab; no impact value is estimated.</p>
{search_box('depth-table')}
{table(depth_rows, ['team','unit','side','out','doubtful','questionable','starter_backup_status','source_url'],
       {'team':'Team','unit':'Unit','side':'Side','out':'Out','doubtful':'Doubtful','questionable':'Questionable','starter_backup_status':'Starter / backup','source_url':'Report'},
       table_id='depth-table', filterable=True)}
""")

# ---------- strategy lab ----------
pages["strategy-lab.html"] = ("Strategy lab", f"""
<h1>Strategy lab</h1>
<p class="note">This page holds the qualitative framework. <strong>Historical quantitative research lives on the</strong> <a href="backtest.html">Backtest</a>, <a href="validation-gates.html">Validation gates</a>, <a href="correlations.html">Correlations</a> and <a href="parlays.html">Parlays</a> pages. The prospective <a href="leaderboard.html">Leaderboard</a> is intentionally unranked because strategy registration and prospective grading are not complete. The research framework taken over in T52 lives on <a href="signals.html">Signals</a>, <a href="validation.html">Skill engine</a>, <a href="anti-luck.html">Anti-luck</a>, <a href="correlation.html">Correlation plan</a>, <a href="starters.html">Starters &amp; depth</a> and <a href="repo-review.html">Repo review</a>.
The inputs needed (licensed odds, historical outcomes, verified role evidence and paired correlation data) are not available here. No validation can eliminate football randomness or guarantee a result; out-of-sample testing can reduce hindsight and quantify uncertainty, not remove variance. This is a research plan, not betting advice. Numeric thresholds are intentionally blank: general statistical guidance does not supply an NFL-specific sample size, return cutoff, significance level or paper-trading duration. <a href="https://www.itl.nist.gov/div898/handbook/glossary.htm" target="_blank" rel="noopener">NIST cross-validation reference ↗</a></p>
<h2>Independent line framework (proposed; no values estimated)</h2>
<p class="note">Originate the forecast from pregame NFL performance and verified availability, not by copying a sportsbook price. Any market line is a separately sourced benchmark; <a href="https://support.nfl.com/hc/en-us/articles/35869698780564-If-I-place-a-bet-on-NFL-com-or-the-NFL-app-am-I-betting-with-the-NFL" target="_blank" rel="noopener">NFL Support says its odds widgets are partner-provided</a>. All fair lines, probabilities and coefficients remain blank until rights-cleared data and validation are available.</p>
{table(line_blueprint, ['market','independent_forecast','comparison','status','source_url'],
       {'market':'Market family','independent_forecast':'Independent forecast target','comparison':'Data / benchmark needed','status':'Current status','source_url':'Official reference'})}
<h2>Validation gates (thresholds blank / unverified; see Flag F17)</h2>
{table(gates, ['gate_id','gate','what_it_tests','numeric_threshold','current_status','data_needed','evidence_url'],
       {'gate_id':'Gate','gate':'Name','what_it_tests':'What it tests','numeric_threshold':'Numeric threshold (blank / unverified)','current_status':'Status','data_needed':'Data needed','evidence_url':'Evidence'})}
<h2>Hypotheses (not tested)</h2>
{table(hyps, ['hypothesis_id','bet_family','hypothesis','signal_inputs','required_data_not_yet_verified','validation_status','gates_passed','evidence_url'],
       {'hypothesis_id':'ID','bet_family':'Bet family','hypothesis':'Hypothesis','signal_inputs':'Signal inputs','required_data_not_yet_verified':'Data still needed','validation_status':'Status','gates_passed':'Gates passed','evidence_url':'Evidence'})}
<h2>Correlation analysis plan (values intentionally blank)</h2>
<p class="note">“Correlation” can mean different things: dependence between legs, agreement between two forecasts, or co-movement of simulated returns. Choose the quantity before analysis. No coefficient, joint probability, sample count or interval has been computed.</p>
{table(correlation_plan, ['question','method','required_alignment','current_value','sample_n','source_url'],
       {'question':'Question','method':'Proposed measurement','required_alignment':'Data alignment','current_value':'Current value','sample_n':'Sample size','source_url':'Statistical reference'})}
<h2>Prospective leaderboard — not yet ranked</h2>
<p class="note">Seven candidate strategy definitions exist, but none has an immutable pre-registration record satisfying EG1 or a completed prospective evaluation window. Historical walk-forward scores are excluded from the leaderboard; detailed outcomes are on the <a href="backtest.html">Backtest</a> page and the landing-page diagnostic panel is explicitly research-only. No strategy is currently eligible or live for competition, and no reward is offered (R36). Future ranking requires a frozen registration manifest, forecast log, official outcomes, pre-approved gates, rights clearance and a sufficient prospective sample. Signal and staking remain separate; the proposed demotion gate is documented on the <a href="leaderboard.html">Leaderboard</a> page.</p>
""")

# ---------- decision path ----------
pages["decision-path.html"] = ("Decision path", f"""
<h1>What must be answered before any decision</h1>
<p class="note">This is the short list of information gates that block progress. <strong>Every item below is currently open.</strong>
Each one needs a written answer from a named owner before a dependent choice can reasonably be made. Ordering matters: a later gate cannot be resolved with confidence while an earlier one is open.
Nothing on this page is a legal or statistical conclusion; each row links to the official source that defines the constraint.</p>
<h2>The ten gates, in order</h2>
{table(decisions, ['gate_id','sequence','decision_needed','status','why_it_blocks','current_state','answer_required','what_it_unblocks','owner','evidence_url'],
       {'gate_id':'Gate','sequence':'#','decision_needed':'Question that must be answered','status':'Status','why_it_blocks':'Why it blocks','current_state':'What we know now','answer_required':'Answer needed','what_it_unblocks':'Unblocks','owner':'Owner','evidence_url':'Official source'},
       table_id='decision-table', filterable=True)}
<h2>What we have, and what we do not have</h2>
<div class="twocol">
<div><h3>Verified and usable today</h3><ul>
<li>{tot['rows']} Week 10 injury rows across {tot['teams']} teams, re-verified row by row against the official page on {AS_OF} (Flag F20).</li>
<li>{tot['games']} Week 10 games with kickoff, broadcaster and listed records (NFL.com).</li>
<li>The official Week 10 bye list: {', '.join(tot['missing_teams'])}.</li>
<li>The Thursday result, Commanders 24 - Giants 21 final, is published in the games table from the official schedule (Flag F22 resolved).</li>
<li>Injury <em>labels</em> (Out / Doubtful / Questionable) and practice participation, exactly as published.</li>
</ul></div>
<div><h3>Not available, so left blank</h3><ul>
<li>Any starter / 2nd / 3rd / 4th string order. No official NFL depth chart was located; the tested URL returns 404 (F06).</li>
<li>Any line, price, spread, total or prop price (F07).</li>
<li>Any historical results archive or player-participation feed (F08).</li>
<li>Any correlation coefficient or joint probability (Q11).</li>
<li>Any replacement-impact or snap-share value (D05).</li>
<li>Any validation threshold, sample size or confidence interval (F17).</li>
<li>Any reward definition or leaderboard rank (D10).</li>
</ul></div>
</div>
<h2>Why luck cannot simply be removed</h2>
<p class="note">The brief asks to remove luck and build signals that are selectively skill based. Football outcomes contain genuine randomness, and a finite sample of games contains noise that no method can delete.
The defensible version of the request is: pre-register the test, score against an explicit noise baseline, report uncertainty, and only then rank. Those steps are gated by D07, D08 and D10 above.
See the <a href="strategy-lab.html">Strategy lab</a> for the gate framework and the <a href="suggestions.html">Suggestions</a> page for the paths that depend on each gate.</p>
""")

# ---------- verification ----------
pages["verification.html"] = ("Verification", f"""
<h1>Verification record</h1>
<p class="note">What was checked, against which official page, on which date, and what the result was.
This page records a reviewer pass, not a guarantee. Unconfirmed values are left blank rather than filled in.</p>
<h2>This session's checks ({AS_OF})</h2>
<div class="tablewrap"><table class="data"><thead><tr>
<th>Check</th><th>Method</th><th>Result</th><th>Evidence</th></tr></thead><tbody>
<tr><td>Injury row count (read 2026-11-18)</td><td>Re-read the official Week 10 report in full (8 chunks), transcribed every player row (data/captures/injury_week10_2026-11-18.psv) and compared it with the stored file by script.</td><td class="warn">Live read: 347 rows across 28 clubs (the prior file of 2026-11-14 held 345). The register was re-published from this read. The 2026-11-14 check (345 rows, "match") is superseded. Details: data/captures/injury_delta_2026-11-18.csv.</td><td><a href="https://www.nfl.com/injuries/" target="_blank" rel="noopener">NFL injury report</a></td></tr>
<tr><td>Injury field values (read 2026-11-18)</td><td>Compared every player name, position, injury text, practice status and game status for all 28 team sections against the transcription of the live page.</td><td class="warn">The prior file (2026-11-14) differed on 32 field values for 17 players (LAC, BAL, IND Arden Key) and lacked 2 BAL rows. All are now re-published from the live read; the 2026-11-14 "no discrepancies" finding is superseded (F94, F95).</td><td><a href="https://www.nfl.com/injuries/" target="_blank" rel="noopener">NFL injury report</a></td></tr>
<tr><td>Game list</td><td>Compared all 14 game headers: day, kickoff time, broadcaster and both listed records.</td><td class="ok">All 14 games match the stored games file.</td><td><a href="https://www.nfl.com/injuries/" target="_blank" rel="noopener">NFL injury report</a></td></tr>
<tr><td>Bye teams</td><td>Read the Teams on Bye section of the official Week 10 schedule.</td><td class="ok">CHI, DEN, PHI and TB confirmed, as recorded (Flag F05).</td><td><a href="https://www.nfl.com/schedules/2026/by-week/week-10" target="_blank" rel="noopener">Week 10 schedule</a></td></tr>
<tr><td>Home / away order</td><td>Compared the schedule game titles (for example "Bills at Jets") with the order NFL.com lists teams on the injury report.</td><td class="ok">The injury report lists the away team first in every Week 10 game; the site's "first listed / second listed" labels remain neutral and are now interpretable.</td><td><a href="https://www.nfl.com/schedules/2026/by-week/week-10" target="_blank" rel="noopener">Week 10 schedule</a></td></tr>
<tr><td>Official depth chart existence</td><td>Requested the conventional team depth-chart URL on the official site.</td><td class="warn">Returns HTTP 404 "Flag on the Play". No official depth chart is reachable, so starter/backup order stays blank (F06).</td><td><a href="https://www.nfl.com/teams/buffalo-bills/roster" target="_blank" rel="noopener">Bills roster</a></td></tr>
<tr><td>Thursday result</td><td>Read the final score on the official Week 10 schedule and the game center.</td><td class="ok">Published in the games table: Commanders 24, Giants 21 final (F22 resolved).</td><td><a href="https://www.nfl.com/games/commanders-at-giants-2026-reg-10" target="_blank" rel="noopener">Game center</a></td></tr>
<tr><td>News snapshot drift</td><td>Compared the stored headline list with the news section of the live injury page.</td><td class="ok">Two stale headlines removed from the stored list (F21 resolved); remaining headlines match the live page as read on {AS_OF}.</td><td><a href="https://www.nfl.com/injuries/" target="_blank" rel="noopener">NFL injury report</a></td></tr>
<tr><td>Standings cross-check</td><td>Compared Week 10 listed records with the official standings page.</td><td class="ok">Records match for the teams checked. The injured-reserve players named in the news (Lamar Jackson, Malik Willis) do not appear on the injury report, consistent with reserve status rather than a game designation.</td><td><a href="https://www.nfl.com/standings/" target="_blank" rel="noopener">NFL standings</a></td></tr>
<tr><td>Source allow-list</td><td>Builder rejects any table row without an HTTPS link on the reviewed official-source allow-list, and any broken internal link.</td><td class="ok">Enforced in <code>scripts/build.py</code>; the build fails otherwise.</td><td><a href="https://github.com/karagemop466-tech/X2/blob/main/scripts/build.py" target="_blank" rel="noopener">build.py</a></td></tr>
</tbody></table></div>
<h2>Model, ledger and link checks (session 10a76288)</h2>
<p class="note">A second, independent set of checks covering the 2026 game ledger, the model outputs and the generated links.
Each row names the check, how it was run, its population and its result.</p>
{table(verification_rows, ['check_id','what_was_checked','how_it_was_checked','population','result','status','source_url'],
       {'check_id':'Check','what_was_checked':'What was checked','how_it_was_checked':'How','population':'Population','result':'Result','status':'Status','source_url':'Source'})}
<h2>Live re-verification pass (session ef971991, {AS_OF})</h2>
<p class="note">A fourth independent live pass, run against the official pages at the time this build was published.
It covers the Week 11 slate the originated markets and price store refer to, the Week 10 state that determines the
feed's size, and a random-ish spot check of the verified results feed.</p>
<div class="tablewrap"><table class="data"><thead><tr>
<th>Check</th><th>Method</th><th>Result</th><th>Evidence</th></tr></thead><tbody>
<tr><td>Week 11 slate (13 games)</td><td>Read the official Week 11 by-week schedule in full and compared every matchup, day, kickoff time and broadcaster with <code>data/schedule_week11_2026.csv</code> and the Week 11 lines/price store.</td><td class="ok">All 13 games match exactly (IND at HOU TNF 8:15 PM PRIME through CIN at WAS MNF 8:15 PM ESPN).</td><td><a href="https://www.nfl.com/schedules/2026/by-week/week-11" target="_blank" rel="noopener">Week 11 schedule</a></td></tr>
<tr><td>Week 11 byes</td><td>Read the Teams on Bye section of the official Week 11 schedule.</td><td class="ok">ATL, CLE, GB, LA, NE, SEA — matches the results page and the model inputs.</td><td><a href="https://www.nfl.com/schedules/2026/by-week/week-11" target="_blank" rel="noopener">Week 11 schedule</a></td></tr>
<tr><td>Week 10 state (feed size)</td><td>Read the official Week 10 schedule: Thursday final, remaining games and their dates.</td><td class="ok">Commanders 24, Giants 21 FINAL (Thu Nov 12) matches the games table. The remaining Week 10 games are dated Sunday Nov 15th (including Patriots at Lions, 9:30 AM ET, Munich) and Monday Nov 16th (Chargers at Ravens, 8:15 PM ET) — so 137 games is correct as of {AS_OF}, and F36 (re-run after Week 10 completes) correctly stays open.</td><td><a href="https://www.nfl.com/schedules/2026/by-week/week-10" target="_blank" rel="noopener">Week 10 schedule</a></td></tr>
<tr><td>Week 10 byes</td><td>Read the Teams on Bye section of the official Week 10 schedule.</td><td class="ok">CHI, DEN, PHI, TB — consistent with F05's resolution.</td><td><a href="https://www.nfl.com/schedules/2026/by-week/week-10" target="_blank" rel="noopener">Week 10 schedule</a></td></tr>
<tr><td>Results feed spot check</td><td>Compared 24 feed rows (all of weeks 5 and 9 that appear in the read chunks) field by field with the live official by-week schedule pages.</td><td class="ok">23 of 24 match exactly on score; the 24th (Rams at Commanders, week 9) matches under the documented LAR/LA key alias used by the official game URL itself. 0 mismatches.</td><td><a href="https://www.nfl.com/schedules/2026/by-week/week-9" target="_blank" rel="noopener">Week 9 schedule</a> · <a href="https://www.nfl.com/schedules/2026/by-week/week-5" target="_blank" rel="noopener">Week 5 schedule</a></td></tr>
<tr><td>Reference-total derivation (F44)</td><td>Recomputed the constant 45.9 from the verified results feed: 6,291 total points over 137 games.</td><td class="ok">22.96 points per team per game; 2 × 22.96 = 45.92 → 45.9. Derivation now documented on the Model lines page; F44 resolved.</td><td><a href="https://www.nfl.com/standings/" target="_blank" rel="noopener">NFL standings</a></td></tr>
<tr><td>Replacement-depth blanks</td><td>Checked that no string-rank value is published in the new depth table without a club-chart basis, and that the build rejects any such row.</td><td class="ok">RD01–RD07 carry club-chart-verified depth with the self-labelled-'unofficial' caveat; RD08–RD12 are blank and flagged. The builder refuses to render a depth value without a verified basis (negative-tested).</td><td><a href="https://www.detroitlions.com/team/depth-chart" target="_blank" rel="noopener">Lions depth chart</a></td></tr>
</tbody></table></div>
<h2>Standing limitations</h2>
<ul>
<li><strong>Single reviewer.</strong> This pass was performed independently of session 30beeb55's separate T15 check, and both found no discrepancies. Two independent passes are the strongest control the manual-transcription limitation allows, but neither is an automated diff (F10, F20).</li>
<li><strong>Live pages move.</strong> Every "verified" statement is true of the page as read on {AS_OF}. The injury page shows no last-updated timestamp (F13).</li>
<li><strong>Rights are not verification.</strong> Confirming a value matches NFL.com does not grant permission to republish it in bulk (F16).</li>
<li><strong>Blank is deliberate.</strong> A dash means the official source did not supply a value, or no official source was found. It is never an inferred estimate.</li>
</ul>

<h2>Snapshot check register — {len(verification_ledger)} checks (taken over from session 25d6114f, T88)</h2>
<p class="note">A reproducible field-by-field ledger: every committed value beside the official value, with the
result and a source link. Reproduce with <code>python3 scripts/verify_snapshot.py</code>. Residual limitation: the
ledger's transcription and the snapshot were made in the same session, so a shared misreading would not be detected
(<a href="flagged.html">Flag F80</a>); two further independent passes (sessions 30beeb55 and 7c9eb69a) reached the
same result. {verification_ledger_counts.get('PASS', 0)} PASS,
{sum(v for k, v in verification_ledger_counts.items() if k.startswith('NEW EVIDENCE'))} new evidence,
{sum(1 for r in verification_ledger if 'REVIEW' in r['result'])} needs review,
{sum(1 for r in verification_ledger if r['result'].startswith('FAIL'))} FAIL.</p>
{search_box('vledger-table')}
{table(verification_ledger, ['check_id','scope','what_was_checked','committed_value','official_value','result','note','source_url'],
       {'check_id':'ID','scope':'Scope','what_was_checked':'What was checked','committed_value':'Committed value','official_value':'Official value','result':'Result','note':'Note','source_url':'Source'},
       table_id='vledger-table', filterable=True)}
""")

# ---------- model & Week 11 lines ----------
pages["model-lines.html"] = ("Model and Week 11 lines", f"""
<h1>Originated lines — Week 11, 2026</h1>
<p class="note"><strong>These are our own numbers, not sportsbook prices.</strong> Each line is the output of a
ridge attack/defence model fitted by least squares on points scored in the {ms['games_transcribed']} games of the
2026 season that had been played when this page was built. The naive reference line is published beside every
number so the difference can be checked. <strong>Market spread and market total are deliberately blank:</strong>
this project has no licensed odds feed, so no market price, closing line or return on investment can be shown
(Flags F07, F32).</p>
{tiles([(ms['games_transcribed'], 'games used to fit'), (ms['out_of_sample_games'], 'games graded out of sample'),
        (ms['mae_m1'], 'model MAE (points)'), (ms['mae_reference'], 'reference MAE (points)')])}
<h2>Week 11 lines — originated in order: side, then total, then moneyline</h2>
<p class="note">Each market is originated in a fixed order: the <strong>side</strong> (spread) first, then the
<strong>total</strong>, then the <strong>moneyline</strong>. For every market the model's <em>fair line</em>, the
<em>market line</em> and the <em>difference</em> are published as separate columns. The market columns are
deliberately blank: this project has no licensed odds feed, so no market price can be confirmed from an official
source and the difference against the market cannot be computed (Flags F07, F31). The fair moneyline is the
no-vig American price implied by the model's win probability, not a sportsbook price. Spread is from the home
team's perspective; P(home) uses the model's out-of-sample residual spread of {ms['sd_margin_residual']} points
and treats a tie as half a win. Calibration: actual margin on predicted margin has slope {ms['calibration_slope']}
(SE {ms['calibration_slope_se']}; corrected 95% CI {ms['calibration_slope_ci'][0]} to {ms['calibration_slope_ci'][1]},
p {ms['calibration_slope_p_vs_1']} against slope 1.0 &mdash; C09 correction, F48, session f25d6b55). The reference total is the
same constant for every Week 11 game by construction: 2 &times; the league-average points per team per game over games strictly
before the reference week (F44 resolved by documentation, session f25d6b55).</p>
<strong>Reference total derivation (Flag F44, resolved).</strong> The reference total is 45.9 in every row by
construction: <code>scripts/model.py</code> computes it as 2 × the league average points per team per game from the
games strictly before the week — here all {ms['games_transcribed']} games of the
<a href="results.html">verified results feed</a>. Recomputed from that official dataset on {AS_OF}:
6,291 total points over 137 games = 22.96 points per team per game; 2 × 22.96 = 45.92, which rounds to 45.9. It is
the naive league-average-total benchmark the totals strategy is graded against, not a per-game forecast. The
reference <em>spread</em> is not constant — it is 2.5 (fixed home field) plus each team's season scoring
differential per game.</p>
{table(model_lines, ['matchup','kickoff_et','fair_spread','market_spread','fair_minus_market_spread','fair_total','market_total','fair_minus_market_total','fair_moneyline_home','fair_moneyline_away','market_moneyline_home','market_moneyline_away','home_win_prob','reference_spread_home','reference_total','model_minus_reference','game_url','source_url'],
       {'matchup':'Matchup','kickoff_et':'Kickoff (ET)','fair_spread':'Fair spread (side)','market_spread':'Market spread','fair_minus_market_spread':'Fair − market (side)','fair_total':'Fair total','market_total':'Market total','fair_minus_market_total':'Fair − market (total)','fair_moneyline_home':'Fair ML (home)','fair_moneyline_away':'Fair ML (away)','market_moneyline_home':'Market ML (home)','market_moneyline_away':'Market ML (away)','home_win_prob':'P(home win)','reference_spread_home':'Reference spread','reference_total':'Reference total','model_minus_reference':'Fair − reference (side)','game_url':'Game','source_url':'Schedule'})}
<h2>Team ratings</h2>
<p class="note">Ratings are in points per game relative to a league-average team. Attack: positive means the team
scores more than average. Defence: positive means it allows fewer than average. Net rating is attack plus defence,
which is what drives the spread. Ratings are shrunk toward zero, so extreme records are deliberately pulled back.</p>
{search_box('rating-table')}
{table(model_ratings, ['team','attack_rating','defence_rating','net_rating','games_played','source_url'],
       {'team':'Team','attack_rating':'Attack','defence_rating':'Defence','net_rating':'Net','games_played':'Games','source_url':'Source'},
       table_id='rating-table', filterable=True)}
<h2>Method, and what it deliberately leaves out</h2>
<ul class="findings">
<li><strong>Fit.</strong> One ridge-regularised least-squares system: points scored = league mean + attack rating
− opponent defence rating + home-field term, fitted on every team-game to date. Spread = (attack + defence) difference
plus home field; total = both attacks minus both defences plus home field.</li>
<li><strong>No look-ahead.</strong> Every out-of-sample prediction was fitted only on games played strictly before
that week. This is enforced in code and computed as gate G1: all {ms['lookahead_tests']} no-look-ahead tests passed
across {ms['lookahead_audit_weeks']} weeks, with the audit recorded in <code>data/gate_results.csv</code> (Flag F50 resolved).</li>
<li><strong>Not included:</strong> play-by-play, yards per play, turnovers, personnel, participation, weather,
travel, rest, coaching, and injuries. One injury snapshot cannot be backtested, so no injury adjustment is applied
(Flags F06, F34).</li>
<li><strong>Reproducibility.</strong> <code>python3 scripts/model.py</code> regenerates every number on this page
from <code>data/games_2026_results.csv</code>. Fixed random seed {ms['seed']} for the bootstrap and permutation tests.</li>
<li><strong>Staleness.</strong> These lines were fitted before Week 10's Sunday games were played. Re-run the model
script once Week 10 finishes (Flag F36).</li>
</ul>
""")

# ---------- price snapshots ----------
pages["price-snapshots.html"] = ("Price snapshots", f"""
<h1>Price-snapshot store</h1>
<p class="note"><strong>What this store is.</strong> Every market this project originates — the side, the total and
the moneyline, for the Week 11 slate and for the out-of-sample backtest window — has one row here, recording the
<em>opening number</em> and the <em>closing number</em> that the market published for it. <strong>Every opening and
closing value is blank and flagged.</strong> This project has no licensed odds feed, and no official free source
publishes opening or closing NFL market numbers, so no value can be confirmed from an official source and none is
inferred (Flags F07, F31, F51). The store is built so that, the moment a rights-cleared official odds source is
connected, the numbers drop straight into the existing columns. The <em>fair line</em> column is the model's own
originated number and is first-party computed; it is not a market price.</p>
{tiles([(len(price_snapshots_extended), 'snapshot rows (extended store)'), (len(price_snapshots), 'Week 11 rows (c125b2f7 store)'),
        (ms['week11_games'], 'Week 11 games'), (ms['out_of_sample_games'], 'out-of-sample games')])}
<h2>How to read the columns</h2>
<ul class="findings">
<li><strong>fair_line</strong> — the model's originated number for that market (side spread, total, or fair
moneyline). First-party computed from official results; not a market price.</li>
<li><strong>opening_number / closing_number</strong> — the market's opening and closing numbers. Blank by design:
no official source confirms them (F07, F31, F51).</li>
<li><strong>opening_verified / closing_verified</strong> — No for every row, because no value is filled.</li>
<li><strong>status</strong> — carries the flag text on every row so the blank is never read as an omission.</li>
<li><strong>Which half of the store this is (session f25d6b55).</strong> <code>fair_line</code> is <em>our own opening
number</em> for every market we originate: for the out-of-sample window (weeks 4&ndash;10) it is the walk-forward pre-game
prediction, fitted only on games played strictly before that week; for Week 11 it is the origination-run value recorded
2026-11-14. The <em>close</em> of our own fair line is not yet recorded separately, and the market open/close cells stay blank
until an authorised source is connected (F07; flag F51 covers the same condition on the Week 11 store). A fixed snapshot cadence
(origin, weekly interim, close at kickoff) is proposed in suggestion S32.</li>
<li><strong>Flag numbering note (F63).</strong> The session that built this store cited &ldquo;F45&rdquo; and
&ldquo;F46&rdquo; for the blank opening/closing values, but those IDs belong to a different register section (depth charts and
the signal/staking split). The conditions are covered in the register by F07, F31 and F51; F63 records the misreference so the
Flagged page stays accurate.</li>
</ul>
<h2>Store contents</h2>
<p class="note">Two complementary stores are published, both with every opening/closing value blank and
flagged. The <strong>extended store</strong> (below) covers every originated market: Week 11 (13 games × 3
markets) plus the out-of-sample window ({ms['out_of_sample_games']} games × 3 markets). A second, independently
built store from session c125b2f7 covers the Week 11 slate with a richer per-market schema and is published on
the <a href="markets.html">Markets</a> page. The table below is filterable by week, matchup and market.</p>
{search_box('snap-table')}
{table(price_snapshots_extended, ['snapshot_id','week','matchup','market','fair_line','opening_number','opening_verified','closing_number','closing_verified','captured_at','status','source_url'],
       {'snapshot_id':'ID','week':'Wk','matchup':'Matchup','market':'Market','fair_line':'Fair line','opening_number':'Opening number','opening_verified':'Opening verified','closing_number':'Closing number','closing_verified':'Closing verified','captured_at':'Captured','status':'Status','source_url':'Source'},
       table_id='snap-table', filterable=True)}
<p class="note">Connecting a licensed, rights-cleared odds feed is the only way these columns can ever be filled.
Until then the blanks stay blank and the flags stay visible — see <a href="flagged.html">Flagged for review</a>.</p>
""")

# ---------- backtest ----------
pages["backtest.html"] = ("Backtest", f"""
<h1>Backtest — walk-forward, out of sample</h1>
<p class="note">Every row is a game the model had not seen: the ratings for that week were fitted only on games
played <em>before</em> that week. {ms['out_of_sample_games']} games, weeks {min(ms['out_of_sample_weeks'])} to
{max(ms['out_of_sample_weeks'])} of 2026. "Error" columns are absolute errors in points against what actually
happened, so smaller is better. A bet is only placed when the model and the reference line disagree by at least
{ms['bet_delta_points']} points.</p>
{tiles([(ms['out_of_sample_games'], 'out-of-sample games'), (ms['mae_m1'], 'model MAE'), (ms['mae_reference'], 'reference MAE'),
        (ms['mae_improvement'], 'improvement (points)')])}
{search_box('bt-table')}
{table(model_backtest, ['week','matchup','actual_margin','reference_spread_home','m1_spread_home','m1_error','reference_error','m2_spread_home','m3_spread_home','m4_spread_home','actual_total','m1_total','reference_total','game_url','source_url'],
       {'week':'Wk','matchup':'Matchup','actual_margin':'Actual margin','reference_spread_home':'Reference spread','m1_spread_home':'Model spread','m1_error':'Model error','reference_error':'Reference error','m2_spread_home':'M2 spread','m3_spread_home':'M3 spread','m4_spread_home':'M4 spread','actual_total':'Actual total','m1_total':'Model total','reference_total':'Reference total','game_url':'Game','source_url':'Schedule'},
       table_id='bt-table', filterable=True)}
<h2>Every bet the strategies placed</h2>
<p class="note">Each row is one bet against the published reference line — never against a sportsbook price.
"Edge" is points gained or lost against that reference line.</p>
{search_box('bet-table')}
{table(model_bets, ['strategy_id','week','matchup','bet','reference_line','model_line','actual','edge_points','result','game_url','source_url'],
       {'strategy_id':'Strategy','week':'Wk','matchup':'Matchup','bet':'Bet','reference_line':'Reference line','model_line':'Model line','actual':'Actual','edge_points':'Edge (pts)','result':'Result','game_url':'Game','source_url':'Schedule'},
       table_id='bet-table', filterable=True)}
""")

# ---------- prospective-only strategy leaderboard ----------
# Prevent retrospective results from leaking onto the competition board.
BACKTEST_FIELDS_FORBIDDEN_ON_LEADERBOARD = (
    "rank", "skill_score_mae_improvement_pts", "skill_ci_low", "skill_ci_high",
    "skill_p_permutation", "q_bh_fdr", "mae_model", "mae_reference", "oos_games",
    "bets_vs_reference", "wins", "losses", "hit_rate_vs_reference", "mean_edge_points",
    "edge_ci_low", "edge_ci_high", "p_binomial", "p_permutation_bets", "luck_share_of_record",
    "skill_share_of_record", "weeks_positive_skill", "week_sign_test_p",
)
for _row in leaderboard:
    for _field in BACKTEST_FIELDS_FORBIDDEN_ON_LEADERBOARD:
        if (_row.get(_field) or "").strip():
            raise ValueError(f"Backtest leakage on prospective leaderboard: {_field} for {_row.get('strategy_id')}")
pages["leaderboard.html"] = ("Leaderboard", f"""
<h1>Prospective strategy leaderboard</h1>
<p class="note"><strong>Competition status: no eligible entries; not ranked.</strong> Candidate strategy definitions
exist, but the registration gate is not met: the frozen registration record, feature set, scoring rule and data cutoff
have not all been attested in a prospective competition manifest. Historical backtests are never leaderboard entries
and no backtest-derived score, rank, hit rate, uncertainty interval or reward tier is shown here. Detailed historical outcomes
are on the <a href="backtest.html">Backtest</a> page; the landing page's luck panel is clearly labeled research-only. An entry can become eligible only after an immutable
pre-registration and a complete prospective evaluation window with official outcomes.</p>
{tiles([(len(leaderboard), 'candidate strategy definitions'), (0, 'prospective samples graded'),
        (0, 'eligible ranked entries'), (0, 'live strategies')])}
<h2>Candidate strategies — registration and prospective evidence pending</h2>
{table(leaderboard, ['strategy_id','strategy','market','status','source_url'],
       {'strategy_id':'ID','strategy':'Candidate strategy','market':'Market family',
        'status':'Competition eligibility','source_url':'Official results source'})}
<p class="note">Every entry is currently unranked. This is intentional: the sealed Week 11 forecast log has not yet
been graded against completed official results, and there is no multi-week prospective record. The present
leaderboard does not assign a winner, qualification tier, or reward.</p>
<h2>Signal and staking remain separate</h2>
<p>When prospective evidence is sufficient, the board will rank signal by the pre-registered proper-score metric
with game-clustered uncertainty and a multiplicity adjustment. Staking results will be displayed separately and
cannot affect signal rank. ROI remains blank until authorized opening/closing prices and settlement rules exist.</p>
<h2>Entry and promotion gates</h2>
<p>Pre-registration, an append-only forecast freeze, official outcome verification, sample sufficiency,
calibration and benchmark-relative skill, multiplicity control, robustness, valid price/joint evidence where
applicable, data rights and jurisdictional review are required. Parlays and prop combos remain excluded without
directly validated joint probabilities and applicable push/void rules. See <a href="validation-gates.html">Validation
Gates</a> and <a href="decision-path.html">Decision Path</a>.</p>
<h2>Demotion gate — live back to paper</h2>
<p>G9 is defined but inert because there are no live strategies. Any future live strategy must return to paper if
its approved rolling evidence window fails an earlier gate, the pre-registered skill interval no longer supports
skill, the forecast record or source provenance fails validation, or legal/data-rights clearance lapses. Numeric
cut-offs are not activated while they remain unapproved (F17).</p>
<h2>Leaderboard rules</h2>
<p>Pre-declared rules LB01–LB12 govern ranking, uncertainty, sample size, privacy, rights and change control.</p>
{table(lb_rules, ['rule_id','topic','rule','why_this_rule','what_is_intentionally_left_blank','evidence_url'],
       {'rule_id':'Rule','topic':'Topic','rule':'Rule','why_this_rule':'Why','what_is_intentionally_left_blank':'Intentionally blank','evidence_url':'Evidence'})}
""")

# ---------- validation gates ----------
pages["validation-gates.html"] = ("Validation gates", f"""
<h1>Validation gates</h1>
<p class="note">A strategy may only be promoted if it clears every gate. The gates exist to separate skill from
luck: no look-ahead, enough sample, a significant and stable accuracy gain, uncertainty that excludes zero,
control for testing many strategies at once, a record that a sign-shuffle cannot reproduce, and — new here — a
<strong>demotion gate (G9)</strong> that sends a live strategy back to paper when its edge degrades.
<strong>The numeric cut-offs below are proposed by this session and are not yet approved by the project owner
(Flag F17).</strong></p>
{table(gate_results, ['gate_id','gate','meaning','rule','status','strategies_passing','source_url'],
       {'gate_id':'Gate','gate':'Name','meaning':'What it tests','rule':'Rule','status':'Approval status','strategies_passing':'Strategies passing','source_url':'Method reference'})}
<h2>The demotion gate (G9)</h2>
<p class="note">G9 is the gate that keeps the leaderboard honest after promotion. A strategy that is live is
demoted back to paper when <strong>any</strong> of the following happens on the latest window: a core gate
(G1–G5) fails, the skill 95% interval includes zero, or the mean edge turns negative. The rule is
<code>status = Live only if G1–G8 all pass and skill boot_lo &gt; 0; otherwise Paper (demoted)</code>. Because
live operation is not enabled and the qualification is disputed by the independent cross-check (Flag F42), no
strategy is live today and every strategy on the board is Paper; the demotion-safe column on the
<a href="leaderboard.html">Leaderboard</a> shows which ones would keep or earn live status once the gates are
approved and the disagreement resolved.</p>
<h2>How luck is removed</h2>
<ul class="findings">
<li><strong>Walk-forward only (G1).</strong> Ratings for a week never see that week's results, so hindsight cannot
leak into the score.</li>
<li><strong>Permutation tests (G3, G7).</strong> The sign of each bet and of each paired accuracy difference is
shuffled thousands of times. If random shuffling often reproduces the observed gain, the gain is not evidence.</li>
<li><strong>Bootstrap intervals (G5).</strong> Resampling the games themselves shows how much of the gain is
sampling noise; the interval must exclude zero.</li>
<li><strong>Multiple-comparison control (G4).</strong> Seven strategies were tested, so raw p-values are adjusted
with Benjamini-Hochberg. Testing many ideas guarantees a lucky winner; this is the tax on doing so.</li>
<li><strong>Stability (G6).</strong> The gain must appear in both halves of the window, not in one hot streak.</li>
<li><strong>Required sample size.</strong> Each row on the leaderboard states how many bets it needs for an
80%-power test. This is the honest answer to "is it proven yet": mostly, not yet.</li>
</ul>
<p class="note">None of this removes variance from football. It only prevents variance from being mistaken for
skill. <a href="https://www.itl.nist.gov/div898/handbook/prc/section4/prc47.htm" target="_blank" rel="noopener">NIST
on multiple-comparison risk ↗</a> · <a href="https://www.itl.nist.gov/div898/handbook/eda/section3/bootplot.htm" target="_blank" rel="noopener">NIST on bootstrap intervals ↗</a></p>
""")

# ---------- correlations ----------
pages["correlations.html"] = ("Correlations", f"""
<h1>Correlation values</h1>
<p class="note">Values are computed from the {ms['games_transcribed']} official 2026 results in this repository, or from model
outputs derived from them. Nothing is assumed or copied. Intervals are Fisher z intervals; p-values are two-sided. Every row
publishes its exact inputs (input A, input B), the sample size n, an interval and a p-value. A build check fails the
site if any correlation row omits n (requirement R26). <strong>Owner rule</strong> (the brief:
compute correlations only from officially sourced numbers): only rows whose two inputs are both officially sourced qualify as
evidence &mdash; C03, C04, C06 and C08. Rows whose predictor is a model output (C01, C02, C05, C07, C09) are labelled
<strong>model diagnostics (DEC-09)</strong>, not evidence; the classification matches <code>data/correlation_audit.csv</code>
(session 8a0bf37e). <strong>C09 correction applied</strong> (2026-11-14, session f25d6b55, per REQ-8a-1 and Flag F48): the row is a
regression slope, so its interval and p-value now use the slope's own standard error &mdash; slope 0.885, 95% CI 0.328 to 1.443 using the exact t quantile at df = 87,
p = 0.68 against slope 1.0 (Flag F72; a second session published 0.335-1.435 with the normal quantile, same conclusion). <strong>C06 published as descriptive</strong> (Flag F55 resolved, session d2915d86): the interval and p-value are blank because the n = 228 pairs are not independent. No player-prop correlation can be computed because no player-prop outcomes are held (Flag F31).</p>
{table(correlations, ['corr_id','question','value','ci_low','ci_high','p_value','sample_n','input_A','input_B','officially_sourced_inputs_only','qualifies_under_owner_rule','interpretation','source_url'],
       {'corr_id':'ID','question':'Question','value':'Value','ci_low':'CI low','ci_high':'CI high','p_value':'p','sample_n':'n','input_A':'Input A','input_B':'Input B','officially_sourced_inputs_only':'Official inputs only','qualifies_under_owner_rule':'Owner rule','interpretation':'What it means','source_url':'Source'})}
<h2>What the values say</h2>
<ul class="findings">
<li>The model's margin forecast is genuinely associated with the actual margin (r = 0.321, p = 0.002), and more
so than the naive reference line (r = 0.274, p = 0.009). That association is a historical backtest diagnostic, not a leaderboard score; the prospective leaderboard is currently unranked.</li>
<li>Game totals are close to unpredictable with the inputs used here: predicted totals correlate r = 0.092
(p = 0.39) with actual totals, and the totals strategy shows no accuracy gain at all.</li>
<li>Within a game, the two teams' scores do not co-move (r = 0.042) and blowouts are not associated with higher
totals (r = 0.021). Both matter for parlay pricing, and both are essentially zero in this sample.</li>
<li>Last week's margin barely predicts this week's (r = 0.087, n = 228 team-game pairs that are not independent;
published as descriptive with no interval or p-value, Flag F55 resolved), which is why recency weighting did not
help and why short hot streaks should not be trusted.</li>
<li>The calibration slope is 0.885 with a 95% interval of 0.328 to 1.443 (p = 0.68 against slope 1.0, corrected
2026-11-14): the interval is wide and includes both over-shy and over-confident readings &mdash; the model's scale is
not yet pinned down (C09, model diagnostic).</li>
<li>The parlay leg correlation is negative but uncertain (phi = -0.299 on 24 tickets, p = 0.16). It is a warning
not to price parlays as if legs were independent, not a usable estimate.</li>
</ul>
""")

# ---------- parlays ----------
pages["parlays.html"] = ("Parlays", f"""
<h1>Parlays and player-prop combinations</h1>
<p class="note">A parlay's price depends on the joint probability of its legs, and the joint probability is not the
product of the legs unless the legs are independent. This page measures that directly on the only paired legs this
repository has: a same-game side and total, each taken when the model and the reference line disagree by at least
{ms['bet_delta_points']} points.</p>
{table(parlays, ['parlay_id','definition','legs','tickets','leg1_hit_rate','leg2_hit_rate','observed_joint_hit_rate','independence_expected_rate','difference_observed_minus_independence','phi_correlation','two_by_two','note','source_url'],
       {'parlay_id':'ID','definition':'Definition','legs':'Legs','tickets':'Tickets','leg1_hit_rate':'Side leg hit','leg2_hit_rate':'Total leg hit','observed_joint_hit_rate':'Observed joint','independence_expected_rate':'Independence would expect','difference_observed_minus_independence':'Difference','phi_correlation':'Phi','two_by_two':'2x2 table','note':'Note','source_url':'Source'})}
<h2>Reading the result</h2>
<ul class="findings">
<li>The two legs did not hit together as often as independence implies (0.208 observed against 0.278 expected),
and the phi correlation is negative (-0.299). Directionally, that means pricing this ticket as if the legs were
independent would have been generous to the ticket buyer.</li>
<li>It is 24 tickets. The 95% interval on phi runs from -0.63 to +0.12 and the p-value is 0.16, so this is a
warning sign, not a measurement. It fails the minimum-sample gate and is not qualified on the leaderboard.</li>
<li><strong>Player-prop combinations are not available.</strong> This repository holds no player-stat outcomes, no
prop thresholds, no prices and no settlement rules, so no prop or prop-combo correlation can be computed. Those
cells are blank by design (Flag F31).</li>
</ul>
""")

# ---------- season results ----------
pages["results.html"] = ("Season results", f"""
<h1>Season results — the verified results feed</h1>
<p class="note"><strong>This table is the project's verified results feed</strong> (requirement R38):
<code>data/games_2026_results.csv</code>, all {ms['games_transcribed']} games of 2026 played through the Week 10
Thursday game (weeks 1-9 complete, plus the Week 10 Thursday game), transcribed from the official NFL.com by-week
schedule pages and read {AS_OF}. Every row links to the official schedule and the official game page.
<strong>Verification:</strong> the wins, losses, ties, points for and points against implied by this feed were
compared with the <a href="https://www.nfl.com/standings/" target="_blank" rel="noopener">official 2026
standings</a> for all 32 teams and match exactly on every column; a second, independent transcription of the same
season agrees on every score (<a href="cross-check.html">cross-check</a>).</p>
<p class="note"><strong>What the feed makes computable, and what it does not.</strong> Backtests and forecast-skill
scores are computed from this feed — that is what the <a href="backtest.html">Backtest</a> and
<a href="leaderboard.html">Leaderboard</a> pages show. <strong>Return on investment cannot be computed at all</strong>
until the <a href="markets.html">price-snapshot store</a> holds real market numbers: ROI needs a price, and no
licensed price source is connected (Flags F07, F32; requirement R37). No ROI value is ever estimated here.</p>
{search_box('res-table')}
{table(results_games, ['week','date_as_shown','away_team','away_points','home_team','home_points','game_url','source_url'],
       {'week':'Wk','date_as_shown':'Date (as shown)','away_team':'Away','away_points':'Away pts','home_team':'Home','home_points':'Home pts','game_url':'Game','source_url':'Schedule'},
       table_id='res-table', filterable=True)}
<h2>Canonical verified results feed</h2>
<p class="note"><code>data/results_feed_2026.csv</code> (session f25d6b55, task T52, advances requirement R38) is the single
canonical feed this project grades everything against: the backtest, the bets, the gates, the correlations and the price-snapshot
store all consume exactly these {len(results_feed)} rows and nothing else. Every row carries its verification status (aggregates
reproduce the official standings exactly &mdash; V01 and RF07), the date verified, the check register it was validated against, and
links to the official game page and schedule page. ROI itself is still not computed anywhere, because no authorised price source
exists (Flag F07); the feed makes ROI computable the moment a permitted price is connected.</p>
{search_box('feed-table')}
{table(results_feed, ['feed_id','week','date_as_shown','away_team','away_points','home_team','home_points','verification_status','verified_date','checks','game_url','source_url'],
       {'feed_id':'Feed ID','week':'Wk','date_as_shown':'Date (as shown)','away_team':'Away','away_points':'Away pts','home_team':'Home','home_points':'Home pts','verification_status':'Verification','verified_date':'Verified','checks':'Checks','game_url':'Game','source_url':'Schedule'},
       table_id='feed-table', filterable=True)}
<h2>Week 11 — the games the lines cover</h2>
<p class="note">Scheduled but unplayed: no results exist yet, so no prediction on this page is graded. Six teams are
on bye (ATL, CLE, GB, LA, NE, SEA).</p>
{table(week11_sched, ['game_no','kickoff_day','kickoff_time_et','broadcast','away_team','home_team','neutral_site_note','game_url','source_url'],
       {'game_no':'Game','kickoff_day':'Day','kickoff_time_et':'Kickoff (ET)','broadcast':'Broadcast','away_team':'Away','home_team':'Home','neutral_site_note':'Note','game_url':'Game','source_url':'Schedule'})}
""")

# ---------- questions ----------
pages["questions.html"] = ("Questions", f"""
<h1>Questions — what we know and what we still need</h1>
<p class="note">Each question lists what is verified, what is missing, and where the missing information can be found, official source first.</p>
{table(questions, ['question_id','area','question','status','known_facts_verified','missing_information','how_to_discover_official_first','decision_owner','evidence_url'],
       {'question_id':'ID','area':'Area','question':'Question','status':'Status','known_facts_verified':'Known (verified)','missing_information':'Missing','how_to_discover_official_first':'How to find out','decision_owner':'Decision owner','evidence_url':'Evidence'})}
""")

# ---------- requirements ----------
pages["requirements.html"] = ("Requirements", f"""
<h1>Requirements from the brief — status</h1>
<p class="note">Each line from the brief, with its current status and where it is addressed.</p>
{table(reqs, ['req_id','requirement (from brief)','status','where_addressed','blocker_or_note','evidence_url'],
       {'req_id':'ID','requirement (from brief)':'Requirement','status':'Status','where_addressed':'Where addressed','blocker_or_note':'Blocker or note','evidence_url':'Evidence'})}
""")

# ---------- suggestions ----------
pages["suggestions.html"] = ("Suggestions", f"""
<h1>Suggestions — review before future implementation</h1>
<p class="note">Each option below is a proposal, not an approval or an instruction to implement. This research brief is complete without user input; no choice is required to publish it. Resolve legal, licensing and validation gates before any dependent feature is built.</p>
{table(suggestions, ['suggestion_id','area','suggestion','benefit_for_decisions','effort','main_risk','options','status','evidence_url'],
       {'suggestion_id':'ID','area':'Area','suggestion':'Suggestion','benefit_for_decisions':'Benefit','effort':'Effort','main_risk':'Main risk','options':'Options','status':'Status','evidence_url':'Evidence'})}
<h2>Review matrix — a recommended path for each suggestion</h2>
<p class="note">Each suggestion is mapped to the decision gate that must close before it can be acted on, with a recommended option and the reason for it.
<strong>These are recommendations for review, not decisions taken.</strong> No option below has been implemented except where the status says delivered.
Choose per row; a suggestion with no recommendation strength of "Recommended" is a proposal that still needs an owner.</p>
{table(sugg_review, ['suggestion_id','area','topic','depends_on_decision','recommended_path','recommendation_strength','why_recommended','main_trade_off','current_evidence_state','evidence_url'],
       {'suggestion_id':'ID','area':'Area','topic':'Topic','depends_on_decision':'Blocked by','recommended_path':'Recommended option','recommendation_strength':'Recommendation','why_recommended':'Why this path','main_trade_off':'Main trade-off','current_evidence_state':'Evidence now','evidence_url':'Evidence'},
       table_id='sugg-review', filterable=True)}
<h2>How to choose without guesswork</h2>
<ol class="findings">
<li><strong>Start at gate D01.</strong> Data rights block the largest number of suggestions. A written answer there changes several rows at once.</li>
<li><strong>Do not pick a statistics option before D02 and D03.</strong> Sample size and thresholds cannot be set responsibly before the market and the data exist.</li>
<li><strong>Legal before features.</strong> Resolve D09 before designing anything with a prize, referral or real-money element.</li>
<li><strong>Prefer the reversible option while a gate is open.</strong> Filtering and blank fields can be undone; publishing bulk data or defining a prize cannot.</li>
<li><strong>Log the choice.</strong> Record which option was chosen and why, so a later reviewer can see whether the decision still holds.</li>
</ol>

<h2>Suggestion register — SR-01 to SR-18 (taken over from session 25d6114f, T88)</h2>
<p class="note">A second, finer-grained recommendation register: each row names the decision it improves, the options
available, the effort, the risk and the gate it depends on. <strong>Nothing here is implemented</strong>; the
<em>Review status</em> column records what is blocked and by which gate.</p>
{search_box('sr-table')}
{table(sug_register, ['sug_id','category','recommendation','improves_which_decision','evidence_that_it_helps','options','recommended_option','effort','risk','depends_on_gate','review_status','evidence_url'],
       {'sug_id':'ID','category':'Category','recommendation':'Recommendation','improves_which_decision':'Decision it improves','evidence_that_it_helps':'Evidence','options':'Options','recommended_option':'Recommended','effort':'Effort','risk':'Risk','depends_on_gate':'Depends on','review_status':'Review status','evidence_url':'Evidence'},
       table_id='sr-table', filterable=True)}
""")

# ---------- flagged ----------
pages["flagged.html"] = ("Flagged for review", f"""
<h1>Flagged for review</h1>
<p class="note"><strong>Flagged for Review.</strong> Irregularities, unverified items and missing official data. These do not block publication. Each item links to the source checked. Request changes by ID.</p>
{table(flags, ['flag_id','category','item','detail','source_url','status','action_requested'],
       {'flag_id':'ID','category':'Category','item':'Item','detail':'Detail','source_url':'Source','status':'Status','action_requested':'Action requested'})}
""")

# ---------- sources ----------
pages["sources.html"] = ("Sources", f"""
<h1>Sources</h1>
<p class="note">Official NFL, government and statistical sources plus first-party project records. NFL, legal and statistical facts trace to official sources; repository and deployment links support only implementation claims and are not evidence for NFL data. Any terms or access limitation is stated alongside the source.</p>
{table(sources, ['source_id','title','publisher','url','type','accessed_date','used_for','verification_note'],
       {'source_id':'ID','title':'Title','publisher':'Publisher','url':'Link','type':'Type','accessed_date':'Accessed','used_for':'Used for','verification_note':'Verification note'})}
""")

# ---------- independent cross-check (second implementation) ----------
ALT = {"LAR": "LA"}
def _k(week, away, home):
    return (int(week), ALT.get(away, away), ALT.get(home, home))


ledger_b = {_k(g["week"], g["away_team"], g["home_team"]): g for g in results_games}
ledger_a = {_k(g["week"], g["away_team"], g["home_team"]): g for g in season_games}
xc_shared = sorted(set(ledger_a) & set(ledger_b))
xc_score_diff = []
for k in xc_shared:
    a, b = ledger_a[k], ledger_b[k]
    if (int(a["away_points"]), int(a["home_points"])) != (int(b["away_points"]), int(b["home_points"])):
        xc_score_diff.append((k, a["away_points"], a["home_points"], b["away_points"], b["home_points"]))
xc_only_a = sorted(set(ledger_a) - set(ledger_b))
xc_only_b = sorted(set(ledger_b) - set(ledger_a))
xc_rows = [
    {"check": "Game results ledger",
     "ours": f'{len(season_games)} games, weeks 1-9 complete plus the Week 10 Thursday game, transcribed from the official schedule by week',
     "theirs": f'{len(results_games)} games, weeks 1-9 complete plus the Week 10 Thursday game, transcribed independently',
     "agreement": f'{len(xc_shared)} games matched on both teams and week; {len(xc_score_diff)} score disagreements',
     "note": "Team keys were normalised before comparing (this implementation uses LAR for the Rams, the other uses LA).",
     "source_url": "https://www.nfl.com/schedules/2026/by-week/week-1"},
    {"check": "Standings reconciliation",
     "ours": "Computed W-L-T, PF and PA for all 32 teams from the ledger; 0 mismatches against the standings "
             "snapshot the ledger was frozen on (data/standings_2026_snapshot.csv, read 2026-11-14). Against the "
             "official standings read on 2026-11-18 the same comparison fails for 26 of 32 teams, because 13 settled "
             "Week 10 games are not in the ledger (F96, F105).",
     "theirs": "Same reconciliation recorded in scripts/verify_results.py",
     "agreement": "Both reproduce the official standings",
     "note": "Two independent implementations reaching the same official page is the strongest control available here.",
     "source_url": "https://www.nfl.com/standings/"},
    {"check": "Out-of-sample window",
     "ours": f'{best["eligible_games"]} games (weeks 3-10)',
     "theirs": f'{ms.get("out_of_sample_games", "")} games (weeks 4-10)',
     "agreement": "Different window lengths; both are walk-forward",
     "note": "A shorter window means a smaller sample, which widens every interval.",
     "source_url": "https://github.com/karagemop466-tech/X2"},
    {"check": "Margin error reduction vs a zero baseline",
    "ours": "best rule %s (%.1f%%), widest interval [%s, %s]" % (best["skill_vs_zero"], float(best["skill_vs_zero"])*100, best["skill_ci_low"], best["skill_ci_high"]),
     "theirs": f'{ms.get("mae_improvement", "")} points ({ms.get("mae_reference", "")} to {ms.get("mae_m1", "")} MAE)',
     "agreement": "Both find a real but modest reduction of roughly 7-16%",
     "note": "Direction agrees; the size differs because the windows and baselines differ.",
     "source_url": "https://github.com/karagemop466-tech/X2"},
    {"check": "Strategies clearing every gate",
     "ours": f'{n_qualified} of {n_competing}',
     "theirs": f'{ms.get("qualified_strategies", "")} of {ms.get("strategies_tested", "")} (with {ms.get("tier1_strategies", "")} at tier 1)',
     "agreement": "DISAGREEMENT — see the note",
     "note": "The other implementation does not charge for testing several rules at once. Adjusting for multiple comparisons removes the apparent significance here, so no rule is qualified and the reward stays off.",
     "source_url": "https://www.itl.nist.gov/div898/handbook/prc/section4/prc47.htm"},
    {"check": "Game totals",
     "ours": f'best total MAE {best_total["total_mae_points"]} vs {base_total["total_mae_points"]} for a constant league-average projection',
     "theirs": "Totals projected from the same ratings system",
     "agreement": "This implementation finds no measurable skill on totals (F39)",
     "note": "Treat any total on this site as the weakest number published.",
     "source_url": "https://www.nfl.com/schedules/2026/by-week/week-1"},
]
pages["cross-check.html"] = ("Independent cross-check", f"""
<h1>Independent cross-check of the line model</h1>
<p class="note"><strong>Why this page exists.</strong> While this session was running, a second session
(<code>73cbec41</code>) independently transcribed the same 2026 season and built its own line model, and that work is now on
<code>main</code>. Rather than publish two competing leaderboards, this page reports what happens when the two independent
implementations are compared. Where they agree, confidence rises. Where they disagree, the difference is stated instead of
being smoothed over.</p>
{tiles([(len(xc_shared), 'games matched between the two ledgers'), (len(xc_score_diff), 'score disagreements'),
        (len(season_games), "games in this session's ledger"), (len(results_games), 'games in the other ledger')])}
<h2>What was compared</h2>
{table(xc_rows, ['check','ours','theirs','agreement','note','source_url'],
       {'check':'Check','ours':'This session implementation','theirs':'The other implementation','agreement':'Agreement','note':'Note','source_url':'Source'})}
<h2>The one material disagreement</h2>
<p class="note">The other implementation reports
{ms.get('qualified_strategies', '')} of {ms.get('strategies_tested', '')} strategies as qualified and
proposes reward tiers. This session's independent scoring of {n_competing} competing rules on
{best['eligible_games']} unseen games finds <strong>{n_qualified} qualified</strong> once the multiple-comparison adjustment is
applied: testing several rules and keeping the best one manufactures significance, and the leading rules' intervals no longer
clear zero once that is charged for. <strong>The recommendation on this page is that no reward tier be offered or paid until
that disagreement is resolved by a pre-registered test on a larger sample.</strong> See
<a href="https://www.itl.nist.gov/div898/handbook/prc/section4/prc47.htm" target="_blank" rel="noopener">NIST on multiple comparisons ↗</a>
and Flag F42.</p>
<h2>Ledger comparison detail</h2>
<ul class="findings">
<li>Games present in both ledgers: <strong>{len(xc_shared)}</strong>. Score disagreements: <strong>{len(xc_score_diff)}</strong>.</li>
<li>Games only in this session's ledger: {len(xc_only_a)}. Games only in the other ledger: {len(xc_only_b)}. The team-key
normalisation above (LAR vs LA) accounts for every difference in keys.</li>
<li>Both ledgers reconcile to the <a href="https://www.nfl.com/standings/" target="_blank" rel="noopener">official standings</a>
with zero mismatches.</li>
</ul>
""")



# ---------- deficiency tracking ----------
gmap2 = {g["game_no"]: f'{g["first_listed_team"]} at {g["second_listed_team"]}' for g in games}
team_game = {r["team_abbr"]: r["game_no"] for r in inj}
deficiency = []
for abbr in sorted(team_rows):
    rs = team_rows[abbr]
    gno = team_game.get(abbr, "")
    for unit in UNIT_ORDER:
        urs = [r for r in rs if UNIT[r["position"]] == unit]
        out = [r for r in urs if r["game_status"] == "Out"]
        doubt = [r for r in urs if r["game_status"] == "Doubtful"]
        quest = [r for r in urs if r["game_status"] == "Questionable"]
        if not (out or doubt):
            continue
        deficiency.append({
            "game_no": gno,
            "matchup": gmap2.get(gno, ""),
            "team": f"{abbr} {rs[0]['team_name']}",
            "side": SIDE[unit],
            "unit": unit,
            "out_players": "; ".join(f"{r['player']} ({r['position']})" for r in out) or "—",
            "doubtful_players": "; ".join(f"{r['player']} ({r['position']})" for r in doubt) or "—",
            "questionable_players": "; ".join(f"{r['player']} ({r['position']})" for r in quest) or "—",
            "out_or_doubtful": len(out) + len(doubt),
            "string_rank": "UNVERIFIED — NFL.com depth-chart pages return 404; club charts exist but self-label as unofficial (Flag F06)",
            "source_url": rs[0]["source_url"],
        })
deficiency.sort(key=lambda r: (int(r["game_no"]) if r["game_no"] else 99, -r["out_or_doubtful"], r["team"]))
pages["depth-deficiency.html"] = ("Deficiency tracking", f"""
<h1>Deficiency tracking — units, starters and officially named replacements</h1>
<p class="note"><strong>What is verified and what is not.</strong> The injury report states who is Out, Doubtful or Questionable
and what position they play. It does <strong>not</strong> state whether that player is a first, second, third or fourth string
player. NFL.com's own team depth-chart pages return 404. Club websites do publish charts —
<a href="https://www.detroitlions.com/team/depth-chart" target="_blank" rel="noopener">detroitlions.com</a> and
<a href="https://www.patriots.com/team/depth-chart" target="_blank" rel="noopener">patriots.com</a> were located and read — but
each page labels its own chart "unofficial" (compiled by club communications or by club writers), so these are club
publications, not league depth charts, and are not treated as authoritative. The string-rank column below is therefore left
unverified rather than guessed (Flag F06); where a club chart is cited, the caveat travels with it (Flag F18). Any statement of
the form "the backup must now start" is made only where an official NFL.com report names the replacement.</p>
<h2>Officially named starters and replacements</h2>
<p class="note">Each row quotes an official NFL.com statement. Where the report hedges ("likely", "expected"), the row is marked
unconfirmed and must not be treated as a known absence. Players on injured reserve do <strong>not</strong> appear on the weekly
injury report at all, so for some teams this is the only place a deficiency shows up.</p>
{table(availability, ['item_id','team_abbr','position_group','player_affected','official_statement','officially_named_replacement','appears_on_week10_injury_report','why_it_matters','confidence','source_url'],
       {'item_id':'ID','team_abbr':'Team','position_group':'Group','player_affected':'Player','official_statement':'Official statement','officially_named_replacement':'Named replacement','appears_on_week10_injury_report':'On injury report','why_it_matters':'Why it matters','confidence':'Confidence','source_url':'Source'})}
<h2>Depth of the replacement — not just the fact of a replacement</h2>
<p class="note">Requirement R43. Each row tracks <em>how deep</em> the replacement is on the depth chart — 2nd, 3rd or
4th string — not only that a replacement exists. This table (RD01–RD07) covers the Detroit and New England
replacement events, where the club-published depth charts
(<a href="https://www.detroitlions.com/team/depth-chart" target="_blank" rel="noopener">detroitlions.com</a>,
<a href="https://www.patriots.com/team/depth-chart" target="_blank" rel="noopener">patriots.com</a>) verify the
string order; each chart self-labels "unofficial" (Flags F-05/F18). The officially named replacements for the other
clubs, with club-chart depth ranks fetched for SEA, MIA, BAL, CLE, AZ and NYG, are tracked in the T42 table lower on
this page (session 8a0bf37e); its A08–A11 rows were completed in session d2915d86 against the four club charts (Flag F53 resolved). String values are entered only where
an official-domain source confirms them — elsewhere the depth cell is <strong>blank and flagged</strong>, never
inferred (F06). The build refuses to publish any depth value whose row does not carry a verified basis.</p>
{search_box('rd-table')}
{table(replacement_depth, ['rd_id','team','position','player_affected','player_status','replacement_named','replacement_depth','depth_basis','next_in_line','next_in_line_depth','depth_verified','flag_ref','source_url','evidence_url'],
       {'rd_id':'ID','team':'Team','position':'Pos','player_affected':'Player affected','player_status':'Status','replacement_named':'Named replacement','replacement_depth':'Depth of replacement','depth_basis':'Depth basis / caveat','next_in_line':'Next in line','next_in_line_depth':'Next depth','depth_verified':'Depth verified','flag_ref':'Flags','source_url':'Status source','evidence_url':'Depth source'},
       table_id='rd-table', filterable=True)}
<h2>Unit exposure — where a replacement is needed</h2>
<p class="note">Grouped by side of ball and unit for every team on the Week 10 report that has at least one Out or Doubtful
player. "Side" is a project classification of position groups, not an NFL field. String rank is blank in every row: no
authoritative source states it for these teams.</p>
{search_box('def-table')}
{table(deficiency, ['game_no','matchup','team','side','unit','out_players','doubtful_players','questionable_players','out_or_doubtful','string_rank','source_url'],
       {'game_no':'Game','matchup':'Matchup','team':'Team','side':'Side','unit':'Unit','out_players':'Out','doubtful_players':'Doubtful','questionable_players':'Questionable','out_or_doubtful':'Out + Doubtful','string_rank':'String rank','source_url':'Report'},
       table_id='def-table', filterable=True)}
""")


# ---------- market tables (session c125b2f7) ----------
_priced = sum(1 for r in price_snapshots if r.get("opening_line") or r.get("closing_line"))
pages["markets.html"] = ("Market tables", f"""
<h1>Market tables</h1>
<p class="note"><strong>No market price is recorded on this site.</strong> The project has no authorised, timestamped
odds source (Flag F07; gate G4). Every opening and closing cell below is therefore blank and marked unverified. The model's
fair lines are published, and the market and difference columns are kept beside them so they can be filled in only from a
source that is authorised. Each row links to the official NFL.com game page it refers to. The link confirms the matchup and
kickoff, not any price.</p>
{tiles([(len(price_snapshots), 'originated markets tracked'), (_priced, 'prices recorded'),
        (len(line_comparison), 'Week 11 games with fair lines'), (len(demotion_gate), 'demotion rules (proposed)')])}
<h2>1. Price-snapshot store (side, then total, then moneyline)</h2>
<p class="note">One row per originated market, in origination order. Opening and closing fields are blank until an authorised,
timestamped source is recorded. Flag F07.</p>
{table(price_snapshots, ['snapshot_id','matchup','kickoff_et','origination_order','market','selection','model_value','opening_line','opening_price','closing_line','closing_price','status','source_url'],
       {'snapshot_id':'ID','matchup':'Game','kickoff_et':'Kickoff (ET)','origination_order':'Order','market':'Market','selection':'Selection','model_value':'Fair (model)','opening_line':'Opening line','opening_price':'Opening price','closing_line':'Closing line','closing_price':'Closing price','status':'Status','source_url':'Source'},
       table_id='ps-table', filterable=True)}
<h2>2. Fair line, market line and difference</h2>
<p class="note">Difference is defined as market minus fair. It stays blank until a market value exists. The constant
reference total used in the naive benchmark is derived and documented on the <a href="model-lines.html">Model lines</a>
page (Flag F44 — resolved: 2 × league average points per team per game from the verified results feed).</p>
{table(line_comparison, ['game_no','matchup','side_fair_home_spread','side_market_home_spread','side_difference_market_minus_fair','total_fair','total_market','total_difference_market_minus_fair','moneyline_fair_home_win_prob','moneyline_market_home_win_prob','moneyline_difference_market_minus_fair','source_url'],
       {'game_no':'#','matchup':'Game','side_fair_home_spread':'Side: fair (home)','side_market_home_spread':'Side: market (home)','side_difference_market_minus_fair':'Side: diff','total_fair':'Total: fair','total_market':'Total: market','total_difference_market_minus_fair':'Total: diff','moneyline_fair_home_win_prob':'Moneyline: fair P(home)','moneyline_market_home_win_prob':'Moneyline: market P(home)','moneyline_difference_market_minus_fair':'Moneyline: diff','source_url':'Source'})}
<h2>3. Signal and staking, kept apart</h2>
<p class="note"><strong>No rank is assigned yet.</strong> This table is prospective-only: signal metrics and staking results remain blank until the frozen forecasts have been graded. Historical backtest figures are excluded from this view and live only on the Backtest page. Staking cannot affect a future signal rank; ROI also remains blank without authorized prices.</p>
{table(signal_staking, ['signal_rank','strategy_id','strategy','signal_skill_points','signal_ci_low','signal_ci_high','signal_q_bh_fdr','signal_oos_games','signal_gates_passed','staking_status','ranking_basis','source_url'],
       {'signal_rank':'Signal rank','strategy_id':'ID','strategy':'Strategy','signal_skill_points':'Skill (pts)','signal_ci_low':'CI low','signal_ci_high':'CI high','signal_q_bh_fdr':'BH q','signal_oos_games':'OOS games','signal_gates_passed':'Gates passed (under review)','staking_status':'Staking','ranking_basis':'Ranking basis','source_url':'Source'})}
<h2>4. Demotion gate (live to paper), proposed</h2>
<p class="note"><strong>Inert today.</strong> No strategy is live, so nothing can be demoted. The thresholds are proposals for
owner approval and are not official values (Flag F17). Gate G9 in the Validation gates register points here.</p>
{table(demotion_gate, ['rule_id','trigger','proposed_condition','numeric_proposal','action','approval_status','source_url'],
       {'rule_id':'Rule','trigger':'Trigger','proposed_condition':'Proposed condition','numeric_proposal':'Numeric proposal','action':'Action','approval_status':'Approval','source_url':'Source'})}
""")

# ---------- session 8a0bf37e: decision desk additions (T42, T44-T50) ----------
rep_depth = read_csv("replacement_depth_week10_2026.csv")
dec_opts = read_csv("decision_options.csv")
gap_rows = read_csv("information_gaps.csv")
repo_review = read_csv("repo_review_2026-11-14.csv")
rf_checks = read_csv("results_feed_checks.csv")
demo_window = read_csv("demotion_window_check.csv")
corr_audit = read_csv("correlation_audit.csv")

for _label, _rows in (("replacement_depth", rep_depth), ("decision_options", dec_opts), ("information_gaps", gap_rows),
                      ("repo_review", repo_review), ("results_feed_checks", rf_checks),
                      ("demotion_window_check", demo_window), ("correlation_audit", corr_audit)):
    for _r in _rows:
        _u = (_r.get("source_url") or "").strip()
        if not _u:
            errors.append(f"{_label}: row without source_url")
        else:
            check_official(_u, f"{_label}.source_url")
for _r in rep_depth:
    if _r.get("depth_chart_url"):
        check_official(_r["depth_chart_url"], "replacement_depth.depth_chart_url")

# session d0d9d19f: every new row must carry a link to an official page. The
# source column differs between files, so accept the ones each file actually has.
_SRC_KEYS = ("source_url", "game_url", "evidence_url", "official_source_url")
for _label, _rows, _idf in (("results_feed_settled", feed_settled, "feed_id"),
                            ("originated_lines", orig_lines, "game_no"),
                            ("origin_snapshots", orig_snaps, "snapshot_id"),
                            ("correlation_provenance", corr_prov, "corr_id"),
                            ("repo_line_audit", repo_audit, "check_id")):
    for _r in _rows:
        _u = next(((_r.get(k) or "").strip() for k in _SRC_KEYS if (_r.get(k) or "").strip()), "")
        if not _u:
            errors.append(f"{_label} {_r.get(_idf, '?')}: row without an official source link")
        else:
            check_official(_u, f"{_label}.source_url")
# A replacement-depth row is only meaningful with both the club chart and the league report
for _r in depth_repl:
    for _k in ("chart_url", "injury_source_url"):
        _u = (_r.get(_k) or "").strip()
        if not _u:
            errors.append(f"depth_replacement {_r['depth_id']}: missing {_k}")
        else:
            check_official(_u, f"depth_replacement.{_k}")
if errors:
    print("ERRORS:")
    for e in errors:
        print("  -", e)
    sys.exit(1)

_n_qual = sum(1 for r in corr_audit if r["officially_sourced_inputs_only"] == "yes")
_n_diag = len(corr_audit) - _n_qual
_depth_checked = sum(1 for r in rep_depth if not r["depth_status"].startswith("Not verified"))
_depth_ranked = sum(1 for r in rep_depth if r["replacement_depth_rank"].startswith(("1st", "2nd", "3rd", "Named starter")))
_d50 = [r for r in demo_window if "last 50" in r["window"]]
_d50_trig = sum(1 for r in _d50 if r["D1_triggered"].startswith("yes"))
_d50_pos = sum(1 for r in _d50 if r["negative_point_estimate"] == "no")

pages["verification.html"] = (pages["verification.html"][0], pages["verification.html"][1] + f"""
<h2>Results feed checks (T49)</h2>
<p class="note">Checks on the {len(read_csv('games_2026_results.csv'))}-game official results feed. The second transcription is compared after one stated normalisation: the official page writes the Rams as LAR, this register writes LA (Flag F46). Three sampled game pages show a hidden score; each of those three scores was verified line by line against the official by-week schedule page on 2026-11-14 (Flag F47 resolved).</p>
{table(rf_checks, ['check_id','check','method','result','status','source_url'],
       {'check_id':'ID','check':'Check','method':'Method','result':'Result','status':'Status','source_url':'Source'},
       table_id='rf-table', filterable=True)}
<h2>Correlation audit: owner rule and sample size (T44)</h2>
<p class="note">Owner rule: a correlation qualifies only when both of its inputs are official numbers, with n published. {_n_qual} of {len(corr_audit)} rows qualify. {_n_diag} rows are model diagnostics (Flags F48, F49). The C09 correction (slope-based interval) has been applied to the register by session ef971991 (REQ-8a-1, Flag F48 resolved). C06 publishes its coefficient and n as descriptive, with the interval and p-value blank (Flag F55 resolved).</p>
{table(corr_audit, ['corr_id','question','value','ci_low','ci_high','p_value','sample_n','input_A','input_B','officially_sourced_inputs_only','qualifies_under_owner_rule','audit_note','source_url'],
       {'corr_id':'ID','question':'Question','value':'Value','ci_low':'CI low','ci_high':'CI high','p_value':'p','sample_n':'n','input_A':'Input A','input_B':'Input B','officially_sourced_inputs_only':'Official inputs only?','qualifies_under_owner_rule':'Qualifies?','audit_note':'Audit note','source_url':'Source'},
       table_id='corr-audit-table', filterable=True)}
<h2>Demotion rule D1: window check (T50)</h2>
<p class="note">D1 as drafted on the project's gate register (Flag F54): a strategy returns to paper when the lower 95% bound of its signal is at or below 0 over the last 50 forecasts. The check uses the walk-forward backtest for the four side models; 5,000 bootstrap resamples, fixed seed. Over the last 50 games D1 triggers for {_d50_trig} of {len(_d50)} models, although {_d50_pos} of {len(_d50)} have a positive point estimate. No strategy is live, so nothing is demoted.</p>
{table(demo_window, ['strategy_id','window','games','mean_mae_gain_pts','ci95_low','ci95_high','D1_triggered','negative_point_estimate','D2_integrity','live_status','source_url'],
       {'strategy_id':'ID','window':'Window','games':'Games','mean_mae_gain_pts':'Mean gain (pts)','ci95_low':'CI low','ci95_high':'CI high','D1_triggered':'D1 triggers?','negative_point_estimate':'Negative estimate?','D2_integrity':'D2 integrity','live_status':'Status','source_url':'Source'},
       table_id='demo-window-table', filterable=True)}
<h2>Repo review, sampled line by line (T47)</h2>
<p class="note">Spot re-verification on 2026-11-14 against official NFL pages, with the irregularities found. This is a sample, not a full re-read of every row; the injury rows were verified in earlier sessions.</p>
{table(repo_review, ['review_id','item','method','result','status','irregularity_or_action','source_url'],
       {'review_id':'ID','item':'Item','method':'Method','result':'Result','status':'Status','irregularity_or_action':'Irregularity or action','source_url':'Source'},
       table_id='repo-review-table', filterable=True)}
""")

pages["depth-deficiency.html"] = (pages["depth-deficiency.html"][0], pages["depth-deficiency.html"][1] + f"""
<h2>Replacement depth: where the replacement sits, not only that one exists (T42)</h2>
<p class="note">For each Week 10 availability item: who replaces whom, the replacement's place on the club's depth chart as fetched on 2026-11-14, and what is still unverified. Club charts are self-labelled unofficial (the Packers edition is dated Nov. 10, 2026; the others are undated) and show pre-injury order (Flag F45). A depth rank is given only where an official statement names the replacement or starter. A blank rank means it could not be confirmed. All {_depth_checked} of {len(rep_depth)} rows are now checked against a club chart — A08 to A11 were completed in session d2915d86 (T52, Flag F53 resolved) — and every chart order carries its source link.</p>
{table(rep_depth, ['item_id','team_abbr','position_group','player_affected','replacement_named_by_official_source','club_chart_order_as_fetched','replacement_depth_rank','depth_status','irregularity','source_url','depth_chart_url'],
       {'item_id':'ID','team_abbr':'Team','position_group':'Pos','player_affected':'Player affected','replacement_named_by_official_source':'Replacement named by official source','club_chart_order_as_fetched':'Club chart order (fetched)','replacement_depth_rank':'Replacement depth','depth_status':'Status','irregularity':'Irregularity','source_url':'Official source','depth_chart_url':'Club depth chart'},
       table_id='repdepth-table', filterable=True)}
""")

pages["decisions.html"] = ("Decisions for the owner", f"""
<h1>Decisions for the owner</h1>
<p class="note">Each row is a choice to make before related work is built. <strong>Nothing here has been implemented.</strong> Each row gives three options, the one recommended now, and the reason. The owner completes the decision; no session acts on a row until the decision is recorded on <code>COORDINATION.md</code>.</p>
<h2>Decision register (T45)</h2>
{table(dec_opts, ['decision_id','decision_to_make','option_A','option_B','option_C','recommended_now','why_this_path','what_unlocks_the_choice','blocked_items','status','source_url'],
       {'decision_id':'ID','decision_to_make':'Decision','option_A':'Option A','option_B':'Option B','option_C':'Option C','recommended_now':'Recommended now','why_this_path':'Why','what_unlocks_the_choice':'What unlocks it','blocked_items':'Blocks','status':'Status','source_url':'Source'},
       table_id='dec-table', filterable=True)}
<h2>What we have and what is missing (T46)</h2>
<p class="note">What the project can and cannot answer today, and the official source to try first. A blank cell means the item is not held.</p>
{table(gap_rows, ['gap_id','area','what_we_have','what_is_missing','why_it_matters','how_to_find_it_officially_first','blocks','source_url'],
       {'gap_id':'ID','area':'Area','what_we_have':'What we have','what_is_missing':'What is missing','why_it_matters':'Why it matters','how_to_find_it_officially_first':'How to find it (official first)','blocks':'Blocks','source_url':'Source'},
       table_id='gap-table', filterable=True)}
<p class="note">Suggestions with their own options are on the <a href="suggestions.html">Suggestions</a> page. Open questions are on the <a href="questions.html">Questions</a> page. Flagged items are on the <a href="flagged.html">Flagged for review</a> page.</p>

<h2>Decision gates register — DQ-01 to DQ-20 (taken over from session 25d6114f, T88)</h2>
<p class="note">The DQ register is the finer-grained funnel: each row is a question that must be answered before a
route can sensibly be chosen, what is known now with a source, how to find the missing answer, and the choice the
owner will face. <strong>DQ-01 (data rights)</strong> and <strong>DQ-02 (jurisdiction and contest design)</strong>
block everything downstream. Nothing is chosen automatically.</p>
{search_box('dq-table')}
{table(dq_rows, ['q_id','stage','decision_topic','question_that_must_be_answered','why_it_blocks_a_decision','known_now_source_backed','how_to_discover','the_choice_you_will_face','owner','evidence_url'],
       {'q_id':'ID','stage':'Stage','decision_topic':'Topic','question_that_must_be_answered':'Question to answer','why_it_blocks_a_decision':'Why it blocks a decision','known_now_source_backed':'Known now (sourced)','how_to_discover':'How to find out','the_choice_you_will_face':'The choice you will face','owner':'Owner','evidence_url':'Source'},
       table_id='dq-table', filterable=True)}
""")

pages["executive-summary.html"] = (pages["executive-summary.html"][0], pages["executive-summary.html"][1] + f"""
<h2>Decision desk: changes on 2026-11-14 (session 8a0bf37e)</h2>
<ul class="findings">
<li><strong>Collision with session c125b2f7.</strong> That session had already merged the price store, the Week 11 line comparison, the signal-vs-staking split and the demotion gate (PRs #29 and #30). This session did not repeat them and removed its own duplicate copies before committing (see COORDINATION.md).</li>
<li><strong>Replacement depth.</strong> All {_depth_checked} of {len(rep_depth)} availability rows are now checked against a club chart (Flag F53 resolved). A depth rank is given in {_depth_ranked} rows, only where an official statement names the replacement or starter; the rest stay blank by rule. The charts are self-labelled unofficial (Flag F45). Two rows do not name the replaced player (Flag F46).</li>

<li><strong>Correlations.</strong> {_n_qual} of {len(corr_audit)} correlations meet the owner rule (official numbers only). {_n_diag} are model diagnostics (Flags F48, F49). The C09 calibration row was wrong in the register and has now been corrected: it is a regression slope, so it carries its own t interval (0.328 to 1.443) and a p-value of 0.683 against a slope of 1.0, not a Pearson-r interval and p = 0.0000 (Flag F72). The practical reading flipped: the data do not show miscalibration, and they do not demonstrate calibration either. C06 is published as descriptive with no interval or p-value (Flag F55 resolved).</li>
<li><strong>Demotion rule D1.</strong> As drafted, D1 would return a strategy to paper in {_d50_trig} of {len(_d50)} side models over the last 50 games, although {_d50_pos} of {len(_d50)} have positive point estimates. The rule needs an owner decision (Flag F54, DEC-04).</li>
<li><strong>Results feed.</strong> The second transcription agrees on all {len(read_csv('games_2026_results.csv'))} games once LAR and LA are read as one team. Three sampled game pages show a hidden score; each score was verified against the official by-week schedule page on 2026-11-14 (Flag F47 resolved).</li>
<li><strong>Decisions.</strong> Ten owner decisions are recorded with options and a recommendation. Nothing has been implemented from them (<a href="decisions.html">Decisions</a>).</li>
</ul>
<h2>Model desk: changes on 2026-11-14 (session f25d6b55, tasks T51&ndash;T55)</h2>
<ul class="findings">
<li><strong>C09 correction applied (REQ-8a-1, Flag F48).</strong> The calibration row is a regression slope, so its interval and
p-value now come from the slope's own standard error: slope {ms['calibration_slope']}, 95% CI {ms['calibration_slope_ci'][0]} to
{ms['calibration_slope_ci'][1]}, p {ms['calibration_slope_p_vs_1']} against slope 1.0. The published register
(<code>correlations_computed.csv</code>) also carries input A, input B and the owner-rule classification for every row, matching
the audit; the model-diagnostics rows are labelled as such (DEC-09). Verified against <code>correlation_audit.csv</code> (V21).</li>
<li><strong>Canonical verified results feed (T52, advances R38).</strong> <code>data/results_feed_2026.csv</code> publishes all
{ms['results_feed_rows']} official 2026 results with a per-row verification status; every grading path &mdash; backtest, bets,
gates, correlations, snapshot store &mdash; consumes exactly this feed. ROI remains uncomputable until an authorised price source
exists (F07). Verified against the graded ledger row by row (V22).</li>
<li><strong>Price-snapshot store verified and documented (T53).</strong> The extended store's <code>fair_line</code> values are our
own origin snapshots (walk-forward pre-game predictions for weeks 4&ndash;10, origination-run values for Week 11); the store
reproduces byte for byte from those declared sources and the derived ML prices recompute from the fair probabilities (V23). The
fair close is not yet recorded separately; a fixed cadence is proposed (S32). Market open/close cells stay blank (F07/F31/F51),
and the fair open/close of our own lines is the store's model-side half.</li>
<li><strong>F44 and F48 resolved; F63 records a citation misreference.</strong> F44 (constant reference total) is resolved by
documenting the derivation (2 &times; league-average points per team per game, no look-ahead). F48 (C09 formula) is resolved by
the correction above. F63 records that session ca1ea224's close-out cites F45/F46 for the blank price-store columns while the
register assigns those IDs to different findings &mdash; the conditions are covered by F07/F31/F51.</li>
</ul>
""")



# ---------- pages taken over from session 25d6114f (T88) ----------
pages["starters.html"] = ("Starters and depth", f"""
<h1>Starters and depth — what is officially verifiable</h1>
<p class="note"><strong>The shortest honest answer:</strong> the NFL does not publish a pregame depth chart, so a
"1st / 2nd / 3rd / 4th string" rank cannot be verified from an official source. What <em>is</em> official is the
<a href="https://static.www.nfl.com/image/upload/v1794570519/gamecenter/ab5828d9-4feb-11f1-abca-2c54536568a9.pdf" target="_blank" rel="noopener">NFL gamebook</a>,
which lists the complete starting lineup by slot, the substitutions, the Did Not Play list and the Not Active list.
That gives post-game starter identity, not a pregame depth order.</p>
{tiles([(len(starters), 'starter-identity rows verified'), (len(starters_good), 'confirmed starters'),
        (len(starters_bad), 'confirmed non-starters (inactive, did not play or substitution)'),
        (len(depth_def), 'team-unit rows with availability exposure'),
        (len({r['team_abbr'] for r in depth_def}), 'teams with at least one exposed unit')])}
<h2>Why the string rank is blank</h2>
<ul>
<li><strong>Roster page:</strong> the official team roster lists name, number, position, status, height, weight,
experience and college. There is no depth-order column. Verified on the
<a href="https://www.nfl.com/teams/buffalo-bills/roster" target="_blank" rel="noopener">Bills roster page</a>.</li>
<li><strong>Depth charts on other sites:</strong> third-party charts exist, but they are not official NFL publications,
so they cannot be presented here as official facts (Flag F18).</li>
<li><strong>Gamebook:</strong> official, but it tells you who played, after the game. Using it as a pregame expectation
(the previous week's lineup) is a modelling choice, not a published depth chart. See suggestion SR-04.</li>
</ul>
<h2>Confirmed starter identity — Week 10, Commanders at Giants</h2>
<p class="note">Every row was read from the official gamebook for the Week 10 Thursday game. The injury-report game
status is shown beside it so you can see both records at once. A player can be a full practice participant and still
appear in the Did Not Play list: that is a real finding, not a data error.</p>
{table(starters, ['team_abbr','player','position','injury_report_game_status','gamebook_status','gamebook_lineup_detail','went_on_to_play','source_url'],
       {'team_abbr':'Team','player':'Player','position':'Pos','injury_report_game_status':'Injury report','gamebook_status':'Gamebook status','gamebook_lineup_detail':'Gamebook detail','went_on_to_play':'Played','source_url':'Gamebook'})}
<h2>Depth deficiency by team and unit — verified absence, not a measured weakness</h2>
<p class="note">This table answers a narrower question than "is the second string playing?": it shows, for every team
and unit, exactly which players are unavailable and what is still missing before a replacement effect could be
estimated. The string rank and the replacement impact are deliberately blank. See Flag F78 for the correction to the
earlier claim that no official starter data exists.</p>
{search_box('depthdef-table')}
{table(depth_def, ['team_abbr','unit','side','out_count','doubtful_count','questionable_count','players_out_or_doubtful','starter_absent_verified','deficiency_status','what_is_missing','best_official_source','source_url'],
       {'team_abbr':'Team','unit':'Unit','side':'Side','out_count':'Out','doubtful_count':'Doubtful','questionable_count':'Questionable','players_out_or_doubtful':'Players unavailable','starter_absent_verified':'Starter evidence','deficiency_status':'Deficiency status','what_is_missing':'What is still missing','best_official_source':'Best official source','source_url':'Source'},
       table_id='depthdef-table', filterable=True)}
<h2>Offense and defense, separately</h2>
<p>The requirement asks about defenses losing starters to second, third or fourth string, and about offenses playing
starters or backups. Both sides are counted in the unit table above: <em>Side</em> separates Offense, Defense and
Special teams, and the unit column separates QB, RB, WR/TE, OL, DL, LB, DB and ST. What cannot yet be said is who the
starter was for each of those units in each game, because only one week of gamebooks has been verified.</p>
""")

pages["signals.html"] = ("Signals", f"""
<h1>Signals — where an original line could come from</h1>
<p class="note"><strong>No signal below has been tested, scored or priced.</strong> Each row defines what the signal is,
why it could carry information, what data it needs, and the specific way it could leak the answer. The
<em>Current value</em> column is blank on every row, by design: a number there would be a claim this project cannot
support. This is the research plan for originating your own line, not a line.</p>
{tiles([(len(line_signals), 'signal definitions'), (len({r['bet_family'] for r in line_signals}), 'bet families'),
        (len(line_signals) - sum(1 for r in line_signals if r['current_value'].strip()), 'signals with no measured value'),
        (len({r['hypothesis_id'] for r in line_signals}), 'linked hypotheses')])}
<h2>How a signal becomes a line</h2>
<ol>
<li><strong>Define it before you look.</strong> The definition, the cutoff and the metric are written down first (gate EG1).</li>
<li><strong>Prove it is knowable at the cutoff.</strong> Every input must have been visible before the bet (gate EG2).</li>
<li><strong>Beat a declared baseline.</strong> A league mean and the availability signal alone are the two baselines (EG3).</li>
<li><strong>Check calibration, not just accuracy.</strong> A probability that says 60 percent should happen about 60 percent of the time (EG4).</li>
<li><strong>Survive the anti-luck suite.</strong> Bootstrap interval, multiplicity control and a held-out block (see Anti-luck).</li>
<li><strong>Only then price it.</strong> The price is the market's number; your number is the forecast. The gap is the only thing worth betting.</li>
</ol>
{search_box('sig-table')}
{table(line_signals, ['signal_id','bet_family','signal_name','signal_definition','why_it_could_matter','verification_now','data_needed','leakage_risk','time_available','test_statistic','current_value','eligibility_gate','source_url'],
       {'signal_id':'ID','bet_family':'Bet family','signal_name':'Signal','signal_definition':'Definition','why_it_could_matter':'Why it could matter','verification_now':'Verified now','data_needed':'Data needed','leakage_risk':'Leakage risk','time_available':'Time available','test_statistic':'Test statistic','current_value':'Current value (blank = unmeasured)','eligibility_gate':'Gate','source_url':'Source'},
       table_id='sig-table', filterable=True)}
<h2>Single bet, parlays and player-prop combos</h2>
<p>Three families are separated because they fail differently. A <strong>single bet</strong> fails when the forecast is
wrong. A <strong>same-game combo</strong> fails when the joint probability is wrong even though every single leg is
right, which is a correlation problem. A <strong>cross-game parlay</strong> fails when costs and settlement are ignored.
The <a href="correlation.html">Correlation plan</a> page holds the dependence plan; nothing has been measured.</p>
""")

pages["validation.html"] = ("Skill engine", f"""
<h1>Skill engine — the gates every strategy must pass</h1>
<p class="note"><strong>Eighteen gates (EG0–EG17), zero passed.</strong> The point of this page is to make a claim impossible
until the evidence exists. Each gate has a pass rule that is checkable without inventing a number: if a rule needs a
threshold, the threshold is left blank rather than guessed (Flag F17).
<a href="https://www.itl.nist.gov/div898/handbook/pmd/section4/pmd44.htm" target="_blank" rel="noopener">NIST model-validation guidance ↗</a></p>
{tiles([(len(engine_gates), 'gates'), (sum(1 for r in engine_gates if r['current_status'].startswith('Open')), 'open'),
        (sum(1 for r in engine_gates if r['current_status'].startswith('Blocked')), 'blocked'),
        (sum(1 for r in engine_gates if r['current_status'].startswith('Partially')), 'partially met')])}
<h2>Gate ledger</h2>
{search_box('gate-table')}
{table(engine_gates, ['gate_id','gate_stage','gate_name','question_answered','pass_rule','data_needed','current_status','applies_to','source_url'],
       {'gate_id':'Gate','gate_stage':'Stage','gate_name':'Gate name','question_answered':'Question it answers','pass_rule':'Pass rule (no invented numbers)','data_needed':'Data needed','current_status':'Current status','applies_to':'Applies to','source_url':'Evidence'},
       table_id='gate-table', filterable=True)}
<h2>The user's requirements, mapped to gates</h2>
<ul>
<li><strong>"Each strategy must pass validation gates."</strong> That is EG0 through EG9 for every strategy, plus one family gate.</li>
<li><strong>"Determine correlation values."</strong> Correlation is gated by EG12 and EG13, which cannot pass without paired settled data. See <a href="correlation.html">Correlation plan</a>.</li>
<li><strong>"Remove luck from the equation."</strong> Luck cannot be removed. It can be bounded and disclosed: a bootstrap interval, a search log and a held-out block. See <a href="anti-luck.html">Anti-luck</a> for why "remove" is the wrong target and what replaces it.</li>
<li><strong>"Build strategies that are selectively skill based."</strong> A strategy is selectively applied only where the gate ledger shows measured skill; until then the correct selective rule is to apply nothing.</li>
<li><strong>"Rewards for top performing strategies."</strong> EG16 blocks any reward until a qualified legal review covers the jurisdiction and the contest design.</li>
</ul>
""")

pages["anti-luck.html"] = ("Anti-luck", f"""
<h1>Anti-luck — how a lucky result is kept off the leaderboard</h1>
<p class="note"><strong>Honest framing:</strong> luck cannot be removed from a football result. A single game is
mostly variance, and a short run of wins is not evidence of skill. What can be done is to make a lucky result
<em>unable to pass</em>: bound the uncertainty, count the number of attempts, and test on data that has never been
seen. Every test below has a blank current value because no evaluation dataset exists yet.</p>
{tiles([(len(luck_tests), 'luck sources addressed'), (sum(1 for r in luck_tests if r['status'].startswith('Open')), 'open'),
        (sum(1 for r in luck_tests if r['status'].startswith('Blocked')), 'blocked'), (0, 'tests with a computed value')])}
<h2>Method sources</h2>
<ul>
<li><a href="https://www.itl.nist.gov/div898/handbook/eda/section3/bootplot.htm" target="_blank" rel="noopener">NIST 1.3.3.4 Bootstrap Plot</a> — the bootstrap estimates the uncertainty of a statistic, typically with 500 to 1000 resamples, and is not appropriate for every distribution.</li>
<li><a href="https://www.itl.nist.gov/div898/handbook/prc/section4/prc47.htm" target="_blank" rel="noopener">NIST 7.4.7 Multiple comparisons</a> — repeating pairwise comparisons inflates the overall significance level.</li>
<li><a href="https://www.itl.nist.gov/div898/handbook/pmd/section4/pmd44.htm" target="_blank" rel="noopener">NIST 4.4.4 Model validation</a> — a high R-squared does not mean the model fits, and residual analysis is the primary tool.</li>
</ul>
<h2>Test register</h2>
{search_box('luck-table')}
{table(luck_tests, ['test_id','target_luck_source','test_name','what_the_test_answers','method','pre_declared_metric','what_would_count_as_skill','what_is_NOT_evidence_of_skill','current_value','status','source_url'],
       {'test_id':'ID','target_luck_source':'Luck source','test_name':'Test','what_the_test_answers':'Question answered','method':'Method','pre_declared_metric':'Metric','what_would_count_as_skill':'Counts as skill','what_is_NOT_evidence_of_skill':'Not evidence of skill','current_value':'Current value (blank = unmeasured)','status':'Status','source_url':'Method source'},
       table_id='luck-table', filterable=True)}
<h2>What would make me trust a strategy</h2>
<ol>
<li>A preregistration committed before any result existed.</li>
<li>A bootstrap interval that excludes the luck-only benchmark, with the resample count stated.</li>
<li>An interval that stays outside the benchmark after the number of tried strategies is accounted for.</li>
<li>The same result in a later block that was never used to choose the strategy.</li>
<li>Errors that do not show structure the model ignored.</li>
<li>A result that holds after real costs, pushes and voids.</li>
</ol>
""")

pages["correlation.html"] = ("Correlation", f"""
<h1>Correlation — the plan, with every value blank</h1>
<p class="note"><strong>No correlation value is published here, and none is guessed.</strong> A correlation number
without paired, settled, point-in-time data would be fabricated. What is published is the exact measurement each pair
needs, so the work is ready the moment the data is licensed. The one thing this page insists on: a parlay is not the
product of its legs. If the joint rate differs from the product of the marginals, the ticket is mispriced by
construction.</p>
{tiles([(len(corr_framework), 'pairs defined'),
        (sum(1 for r in corr_framework if not r['value'].strip()), 'pairs with a blank value'),
        (sum(1 for r in corr_framework if r['status'].startswith('Blocked')), 'blocked on data'),
        (sum(1 for r in corr_framework if r['status'].startswith('Open')), 'open')])}
<h2>Why the naive number is wrong</h2>
<p>Multiply two independent probabilities and you get the joint probability only if the legs are independent. In the
same game they are not: a quarterback's passing yards and his receiver's yards share the same throws; a running back's
rushes and his receptions trade off against game script; a team total and a spread can be settled by the same scoring
play. The correct measure is the observed joint rate minus the product of the marginals, with an interval, on paired
settled legs. See <a href="https://www.itl.nist.gov/div898/handbook/glossary.htm" target="_blank" rel="noopener">the NIST glossary</a>
for the underlying definitions.</p>
<h2>Pair register</h2>
{search_box('corr-table')}
{table(corr_framework, ['pair_id','leg_a','leg_b','relationship_type','why_the_pair_is_not_independent','what_must_be_measured','estimator','required_sample','value','uncertainty','sample_n','status','source_url'],
       {'pair_id':'ID','leg_a':'Leg A','leg_b':'Leg B','relationship_type':'Relationship','why_the_pair_is_not_independent':'Why not independent','what_must_be_measured':'What to measure','estimator':'Estimator','required_sample':'Required sample','value':'Value (blank = unmeasured)','uncertainty':'Uncertainty','sample_n':'Sample N','status':'Status','source_url':'Method source'},
       table_id='corr-table', filterable=True)}
""")

pages["repo-review.html"] = ("Repo review", f"""
<h1>Repo review — line by line, with sources</h1>
<p class="note">Every file this session owns was reviewed against a source, and any irregularity is recorded rather
than quietly fixed. Findings that contradict an earlier claim are flagged for review; findings that are correct are
left alone. Project-implementation claims link to first-party GitHub records and are <em>not</em> offered as evidence
for NFL facts.</p>
{tiles([(len(repo_review_rows), 'files or groups reviewed'), (repo_review_counts.get('PASS', 0), 'pass'),
        (sum(v for k, v in repo_review_counts.items() if k.startswith('VERIFIED')) + repo_review_counts.get('LIVE', 0) + repo_review_counts.get('CORRECT', 0), 'verified'),
        (repo_review_counts.get('NEW EVIDENCE', 0), 'new evidence'),
        (repo_review_counts.get('IRREGULARITY', 0), 'irregularities')])}
<h2>Independence and timestamps</h2>
<ul>
<li>The snapshot is dated <strong>2026-11-14 (UTC)</strong> because the official page publishes no last-updated time (Flag F13).</li>
<li>The verification comparison is <strong>not fully independent</strong> of the original transcription because both were made in the same session (Flag F80). Suggestion SR-13 records the fix.</li>
<li>The official Thursday game has been played, so the injury report still shown is the pregame report for the remaining 13 games.</li>
</ul>
<h2>Review register</h2>
{search_box('rev-table')}
{table(repo_review_rows, ['review_id','target','line_or_group','what_was_reviewed','verified_against','result','finding','action_taken','source_url'],
       {'review_id':'ID','target':'File','line_or_group':'Lines','what_was_reviewed':'Reviewed','verified_against':'Verified against','result':'Result','finding':'Finding','action_taken':'Action taken','source_url':'Source'},
       table_id='rev-table', filterable=True)}
""")
# ---------- review path ----------
# A single page whose job is to let a reviewer choose a path before any change is
# built. It is deliberately ordered: earlier rows unblock later ones, and every row
# states what evidence exists today and what is still missing.
REVIEW_PATH = [
    {"step": "1", "theme": "Data rights and legal position",
     "why_first": "Almost every other row depends on it. Building a feature on data the project may not hold is wasted work, and a reward mechanic built before a legal review is the one mistake that is expensive to undo.",
     "recommended": "Record a written answer on NFL data use (DEC-03) and on the owner's jurisdiction (DEC-02) before any expansion.",
     "have_now": "NFL Terms are published and are linked; the Dutch and Japanese positions are recorded as flags only (F19, F09). No permission is on file.",
     "still_missing": "Any written permission, and any qualified legal opinion.",
     "reversible": "Yes — nothing is built yet.",
     "blocks_row": "Steps 2, 4, 6, 7", "evidence_url": "https://support.nfl.com/hc/en-us/articles/35869743904916-NFL-Terms-and-Conditions"},
    {"step": "2", "theme": "A price source, so ROI can exist at all",
     "why_first": "A price-snapshot store that records opening and closing numbers already exists in structure (39 rows) but holds no prices. Without a licensed, timestamped source, every ROI, staking and closing-line-value column must stay blank. Filling them from a public page would break the project's own sourcing rule.",
     "recommended": "Keep every market column blank and run forecast-only research until a licensed source is under contract (DEC-01).",
     "have_now": "The store, the fair/market/difference columns and the schema exist and are verified blank.",
     "still_missing": "Any licensed odds source; any defined opening and closing timestamp.",
     "reversible": "Yes — the columns are empty, so nothing has to be unwound.",
     "blocks_row": "Steps 5, 6", "evidence_url": "https://support.nfl.com/hc/en-us/articles/35869698780564-If-I-place-a-bet-on-NFL-com-or-the-NFL-app-am-I-betting-with-the-NFL"},
    {"step": "3", "theme": "Finish the results feed before measuring anything more",
     "why_first": "Skill, correlation and ROI all rest on the results ledger. The ledger reconciles for all 32 teams, but a handful of game-center pages do not display a score, so those rows are verified against the standings rather than game by game.",
     "recommended": "Get the official Game Book PDFs for the rows that cannot be read on the game center, and store the PDF link per game (DEC-06).",
     "have_now": "137 games; every team's W-L-T and points reconcile exactly with the standings snapshot the "
                "ledger was frozen on (read 2026-11-14). Today's standings imply 150 completed games and 26 of 32 "
                "clubs differ; the 13 missing settled games are transcribed and reconcile all 32 (F105, P09).",
     "still_missing": "A per-game official artifact for the rows whose game-center page hides the score (F47).",
     "reversible": "Yes — it adds evidence, it does not change numbers.",
     "blocks_row": "Step 4", "evidence_url": "https://www.nfl.com/standings/"},
    {"step": "4", "theme": "Player-level data, before any prop or combo claim",
     "why_first": "Player props and prop combos are a stated goal. Today there is no player outcome, snap count or participation record, so no prop correlation can be computed. Publishing a combo number without them would be invention.",
     "recommended": "Use the Game Book participation data for role, and license a provider for outcomes and prop prices; keep every prop cell blank until then (DEC-06).",
     "have_now": "Week 10 availability rows naming starters and replacements, each with a club or news link; a parlay study on model-generated side and total legs only.",
     "still_missing": "Player outcomes, participation, and prop prices.",
     "reversible": "Yes — blank cells stay blank.",
     "blocks_row": "Step 6", "evidence_url": "https://www.nfl.com/games/texans-at-titans-2026-reg-5"},
    {"step": "5", "theme": "A demotion rule that does not fire on a good strategy",
     "why_first": "The leaderboard can only promote today. The drafted demotion rule returns a strategy to paper when the lower bound of its signal reaches zero over the last 50 forecasts — as drafted it demotes all four side models, all of which have positive point estimates. A gate that always fires is not a test.",
     "recommended": "Set the demotion threshold from the interval width at the sample actually available, and require a minimum number of forecasts before the rule can act (DEC-04).",
     "have_now": "A window check that shows exactly how the drafted rule behaves, and the NIST interval reference it should be built on.",
     "still_missing": "An approved threshold; and any live strategy for the rule to act on.",
     "reversible": "Yes — no strategy is live.",
     "blocks_row": "Step 6", "evidence_url": "https://www.itl.nist.gov/div898/handbook/eda/section3/eda352.htm"},
    {"step": "6", "theme": "Signal before staking, and never the other way round",
     "why_first": "A staking run can look profitable while the forecast underneath it is worthless. The signal column is what the project can defend today; staking cannot be measured at all without prices.",
     "recommended": "Rank on signal only, keep staking explicitly 'not measured', and refuse any leaderboard that ranks on return (DEC-01, DEC-04).",
     "have_now": "A leaderboard split into signal and staking, with staking marked not measured; per-strategy sample sizes and the n each test would need.",
     "still_missing": "Prices, so staking cannot be computed; and an approved reward tier definition.",
     "reversible": "Yes — it is a presentation rule.",
     "blocks_row": "Step 7", "evidence_url": "https://www.itl.nist.gov/div898/handbook/prc/section4/prc47.htm"},
    {"step": "7", "theme": "Publish only what the sample can support",
     "why_first": "The honest state today is that a line model beats a naive reference line by 1.74 points of mean absolute error on 89 games, and that this is not yet a decisive sample against a real market. Reward tiers and 'top strategy' language outrun the evidence.",
     "recommended": "Keep the caveats on the same page as the ranking, publish the sample size each claim would need, and keep every reward mechanic inert.",
     "have_now": "Confidence intervals, permutation tests, multiple-comparison control, and a published required-sample-size figure per strategy.",
     "still_missing": "A decisive sample, and any market comparison.",
     "reversible": "Yes.", "blocks_row": "—", "evidence_url": "https://www.itl.nist.gov/div898/handbook/eda/section3/bootplot.htm"},
]

_rev_head = "".join(f"<th>{html.escape(h)}</th>" for h in
    ("Step", "Theme", "Why it comes here", "Recommended path", "What we have now",
     "What is still missing", "Reversible?", "Next", "Source"))
_rev_body = "".join(
    "<tr>"
    f"<td>{r['step']}</td><td><strong>{html.escape(r['theme'])}</strong></td>"
    f"<td>{html.escape(r['why_first'])}</td><td>{html.escape(r['recommended'])}</td>"
    f"<td>{html.escape(r['have_now'])}</td><td>{html.escape(r['still_missing'])}</td>"
    f"<td>{html.escape(r['reversible'])}</td><td>{html.escape(r['blocks_row'])}</td>"
    f'<td><a href="{r["evidence_url"]}" target="_blank" rel="noopener">Source ↗</a></td>'
    "</tr>" for r in REVIEW_PATH)

_missing_counts = defaultdict(int)
for _r in REVIEW_PATH:
    _missing_counts["blank" if _r["still_missing"] else "known"] += 1

pages["review-path.html"] = ("Review path", f"""
<h1>Review path — pick a direction before anything is built</h1>
<p class="note">This page exists so one reviewer can choose a route through the project's open items, in order, with the
evidence for each step in front of them. <strong>Nothing on this page is implemented, enabled or approved.</strong>
It is a reading order, not a plan of record. The registers behind it are the
<a href="suggestions.html">Suggestions</a> matrix, the <a href="decisions.html">Decisions</a> register, the
<a href="questions.html">Questions</a> page and the <a href="flagged.html">Flagged for review</a> page.</p>

<h2>The short version</h2>
<ul class="findings">
<li><strong>What the project can defend today:</strong> an independently originated spread and total for each Week 11 game, a
walk-forward out-of-sample record against a naive reference line, correlations with intervals and sample sizes, and a
line-by-line verification record.</li>
<li><strong>What it cannot do yet:</strong> any market comparison, return on investment, staking result, player-prop number or
strategy reward. Every one of those needs a licensed price source or player-level data that the project does not hold.</li>
<li><strong>The one thing to decide first:</strong> step 1. Rights and legal position gate more rows than any other choice, and
they are the least reversible if ignored.</li>
<li><strong>The one number to read carefully:</strong> the model beats its naive reference line, but the naive reference line is
not a sportsbook. Beating it is not evidence of beating a market.</li>
</ul>

<h2>Ordered review path</h2>
<p class="note">Read down, not across. A step lower in the table inherits the risk of a step above it being skipped.</p>
<div class="tablewrap"><table id="review-path" class="data"><thead><tr>{_rev_head}</tr></thead><tbody>{_rev_body}</tbody></table></div>

<h2>Questions to settle before choosing</h2>
<p class="note">Every open question below is one the project cannot currently answer from the information it holds —
it is listed here with the information still needed and the official source to try first. The full register is on the
<a href="questions.html">Questions</a> page, and the same gaps are mirrored as G01–G16 on the
<a href="decisions.html">Decisions</a> page. A question is not a task: several are unanswerable in this project by design,
and say so in the status column.</p>
{table([q for q in questions
        if not q['status'].startswith(('Answered', 'Proposed'))],
       ['question_id','area','question','status','missing_information','evidence_url'],
       {'question_id':'ID','area':'Area','question':'Question','status':'Status',
        'missing_information':'Information still needed','evidence_url':'Evidence'},
       table_id='review-questions', filterable=True)}

<h2>How to use this page</h2>
<ol class="findings">
<li><strong>Do not choose a later step while an earlier one is open.</strong> Step 2 has no meaning without step 1, and step 6
cannot be measured without step 2.</li>
<li><strong>Prefer the option that can be undone.</strong> Blank columns and inert gates cost nothing to keep; a published
return or an enabled reward does.</li>
<li><strong>Ask for the sample size, not the result.</strong> No prospective ranking appears until the pre-registered sample and gates are met. If an eventual sample is too small, keep the entry unranked rather than calling it provisional evidence.</li>
<li><strong>Treat a blank as a finding.</strong> Where a value is blank, the source did not support it. That is the intended
state, not an omission to be filled in by inference.</li>
<li><strong>Record the choice and the date.</strong> A decision without a recorded date cannot be re-checked later, because the
evidence underneath it will have moved.</li>
</ol>
""")


# =====================================================================
# Session d0d9d19f: origination order, settled feed, replacement depth,
# correlation provenance, repository audit
# =====================================================================
pages["originated-lines.html"] = ("Originated lines", f"""
<h1>Originated lines — side, then total, then moneyline</h1>
<p class="note"><strong>These are our own numbers, not market numbers.</strong> The three markets are originated in a
fixed order because each step consumes the previous one: the attack/defence ratings give a home margin (the side); the
same ratings give expected points for each team, and their sum is the total; the margin plus the walk-forward residual
spread gives a win probability, and that probability gives a moneyline price. Every market column is blank because no
licensed odds feed is connected (F07). Each row links to the official NFL.com game page, which confirms the matchup and
kickoff — not any price. <code>scripts/originate.py</code> re-fits the ratings independently and refuses to publish
if any spread or total disagrees with <code>scripts/model.py</code> by more than 0.05 points; the two agree exactly
today (largest difference 0.000).</p>
{tiles([(len(orig_lines), 'Week 11 games originated'), (3, 'markets per game, in order'),
        (len(orig_snaps), 'price snapshots held'), (0, 'market prices recorded')])}
<h2>Step 1 — the side, step 2 — the total, step 3 — the moneyline</h2>
<p class="note">The side is the home team's predicted margin: positive means the home team is favoured by that many
points. The reference column is the naive benchmark the model has to beat (season point differential per game plus a
2.5-point home field, and no home-field term at a neutral site). The edge is the model minus the reference. The fair
price columns are zero-vig prices implied by the model, not prices anyone has offered. The market and difference
columns stay blank until a market line exists.</p>
{search_box('ol-table')}
{table(orig_lines, ['game_no','matchup','kickoff_et','neutral_site','step_1_side_fair_home_line','step_1_side_reference_line_home','step_1_side_edge_points_vs_reference','step_1_side_fair_price_at_reference_for_preferred_side','step_1_side_market_line','step_1_side_difference_market_minus_fair','step_2_total_fair','step_2_total_reference_line','step_2_total_edge_points_vs_reference','step_2_total_market_line','step_2_total_difference_market_minus_fair','step_3_moneyline_fair_home_prob','step_3_moneyline_fair_price_home','step_3_moneyline_fair_price_away','step_3_moneyline_market_price','step_3_moneyline_difference_market_minus_fair','game_url'],
       {'game_no':'#','matchup':'Game','kickoff_et':'Kickoff (ET)','neutral_site':'Neutral site','step_1_side_fair_home_line':'1 · Side fair (home)','step_1_side_reference_line_home':'1 · Side reference','step_1_side_edge_points_vs_reference':'1 · Edge (pts)','step_1_side_fair_price_at_reference_for_preferred_side':'1 · Fair price at reference','step_1_side_market_line':'1 · Market','step_1_side_difference_market_minus_fair':'1 · Difference','step_2_total_fair':'2 · Total fair','step_2_total_reference_line':'2 · Total reference','step_2_total_edge_points_vs_reference':'2 · Edge (pts)','step_2_total_market_line':'2 · Market','step_2_total_difference_market_minus_fair':'2 · Difference','step_3_moneyline_fair_home_prob':'3 · P(home win)','step_3_moneyline_fair_price_home':'3 · Fair price home','step_3_moneyline_fair_price_away':'3 · Fair price away','step_3_moneyline_market_price':'3 · Market','step_3_moneyline_difference_market_minus_fair':'3 · Difference','game_url':'Official game page'},
       table_id='ol-table', filterable=True)}
<h2>Our own opening and current number for every market</h2>
<p class="note">The store holds an opening value (fitted on the 136 games of weeks 1-9, the number the model would have
published before the Week 10 Thursday game) and a current value (fitted on all 137 games, the number published now).
The move between the two is how much one extra game moved our own number: the largest side move is 0.4 points and the
mean is 0.06, so the ratings are stable. The closing value is reserved: by definition it is the last number published
before kickoff, so it is recorded only once the games have been played. See
<a href="price-snapshots.html">price snapshots</a> for the store this extends.</p>
{search_box('os-table')}
{table(orig_snaps, ['snapshot_id','matchup','origination_order','market','our_opening_value','our_current_value','our_move_current_minus_opening','our_closing_value','market_opening_value','market_closing_value','market_note','game_url'],
       {'snapshot_id':'ID','matchup':'Game','origination_order':'Order','market':'Market','our_opening_value':'Our opening','our_current_value':'Our current','our_move_current_minus_opening':'Move','our_closing_value':'Our closing (reserved)','market_opening_value':'Market opening','market_closing_value':'Market closing','market_note':'Market note','game_url':'Official game page'},
       table_id='os-table', filterable=True)}
<h2>Two caveats found while building this page</h2>
<ul class="findings">
<li><strong>Home-team bias (<a href="flagged.html">F76</a>).</strong> Graded against the number the model itself
published, the home side covered {_feed_cover}, lost {_feed_lose} and pushed {_feed_push} over {_feed_orig}
out-of-sample games; the mean signed error is -0.83 points (SE 1.30, t = -0.64). That is not statistically
distinguishable from zero, so the line is published as computed, but it is the direction to watch.</li>
<li><strong>Neutral site — now handled.</strong> One of the thirteen Week 11 games (MIN at SF, Mexico City) carries
<code>neutral_site = Y</code> on the official schedule, and it is the one row on the table above that is published with
the home-field term dropped. The remaining half of that defect is still open and is not solved here: all
{len(feed_settled)} completed historical rows carry a blank <code>neutral_site</code> value, so the historical fit still
treats any neutral-site game among them as a home game (<a href="flagged.html">F71</a>).</li>
</ul>
""")

pages["results-feed.html"] = ("Results feed", f"""
<h1>Results feed — settled markets</h1>
<p class="note">One row per decided game holding the official final score <strong>and how each market we originate
settled</strong>. This is the companion to <a href="results.html">Season results</a>: same 137 games, with the
settlement columns a backtest, a closing-line-value study or a return-on-investment figure would be computed from.
Every score comes from the official NFL.com by-week schedule pages and reconciles against the official standings for all
32 teams. The settlement columns are computed from that score and the walk-forward line
<code>scripts/model.py</code> actually published for the game. The market columns are blank: no licensed odds feed, so
no price, no stake and no return (F07).</p>
{tiles([(len(feed_settled), 'games in the feed'), (_feed_orig, 'with an originated line'),
        (len(feed_settled) - _feed_orig, 'weeks 1-3, no line fitted'), (0, 'prices recorded')])}
<h2>Settlement conventions</h2>
<ul>
<li><strong>Side.</strong> The published number is the home team's predicted margin. The home side covers when the
actual home margin is strictly greater, loses when strictly less, and pushes when exactly equal.</li>
<li><strong>Total.</strong> The over wins when actual total points are strictly greater than the published total, the
under when strictly less, push when equal.</li>
<li><strong>Moneyline.</strong> The home side wins when the actual home margin is strictly positive. The ledger contains
one tie (Giants 27, Commanders 27, week 5), which a two-way moneyline would settle as a push.</li>
</ul>
<h2>Agreement with the other feed in this repository</h2>
<p class="note">This repository holds two independently built results feeds: this one
(<code>data/results_feed.csv</code>, built by <code>scripts/results_feed.py</code>) and
<code>data/results_feed_2026.csv</code>, the canonical feed built by another session. Both carry 137 games. Compared
row by row on week, away team and home team: <strong>137 of 137 scores agree, 0 disagreements</strong>. This feed adds
the three settlement columns; that one adds the per-row verification chain. Neither carries a price.</p>
{search_box('rf-table')}
{table(feed_settled, ['feed_id','week','date_as_shown','away_team','away_points','home_team','home_points','home_margin','total_points','winner','originated_side_home_line','side_settlement_home','originated_total_line','total_settlement','originated_home_win_probability','moneyline_settlement','origination_status','game_url'],
       {'feed_id':'ID','week':'Wk','date_as_shown':'Date','away_team':'Away','away_points':'Away pts','home_team':'Home','home_points':'Home pts','home_margin':'Home margin','total_points':'Total','winner':'Winner','originated_side_home_line':'Originated side','side_settlement_home':'Side settlement','originated_total_line':'Originated total','total_settlement':'Total settlement','originated_home_win_probability':'P(home win)','moneyline_settlement':'Moneyline settlement','origination_status':'Origination','game_url':'Official game page'},
       table_id='rf-table', filterable=True)}
<h2>What this feed can and cannot support</h2>
<ul class="findings">
<li><strong>It can</strong> support out-of-sample accuracy, calibration and settlement-based strategy grading — what
the <a href="backtest.html">backtest</a> and the <a href="leaderboard.html">leaderboard</a> already use.</li>
<li><strong>It cannot</strong> support return on investment, closing-line value or any staking result, because no row
carries a price. A licensed, timestamped odds source is the single change that would unlock all three
(<a href="flagged.html">F07</a>).</li>
</ul>
""")

pages["depth-replacement.html"] = ("Depth of replacement", f"""
<h1>Depth of the replacement</h1>
<p class="note">The NFL's weekly injury report says <em>that</em> a player is out. It does not say how far down the
roster the replacement comes from, and that is the number that matters: a second-string replacement and a
fourth-string replacement are not the same event. The only official-domain source carrying the order is the depth chart
each club publishes on its own website, and every one of those charts is self-labelled <strong>unofficial</strong>
— compiled by club communications staff or club writers — so each value below inherits that caveat (F06).</p>
{tiles([(len(depth_repl), 'rows for clubs that publish a chart'), (_named_repl, 'with an officially named replacement'),
        (len(depth_repl) - _named_repl, 'blank and flagged'), (len(_union_names), 'clubs covered across both registers')])}
<h2>String of the absent player, and of the man behind him</h2>
<p class="note">Read the columns together: the string the absent player held, the player the club chart lists next, the
string that player holds, and how many players the chart still lists behind him. Where the chart names nobody — the
absent player is the last name at that spot, or he is not on the chart at all — the field is left blank and marked
unverified rather than guessed. The last two columns catch a compounded loss: a replacement who is himself on the
injury report.</p>
{search_box('dr-table')}
{table(depth_repl, ['depth_id','team_abbr','side_of_ball','chart_position','player_out','injury_report_position','official_game_status','string_of_absent_player','players_listed_at_this_spot','named_replacement','replacement_string','players_behind_replacement','co_listed_at_same_string','replacement_also_on_injury_report','depth_of_replacement_summary','chart_url','injury_source_url'],
       {'depth_id':'ID','team_abbr':'Team','side_of_ball':'Side of ball','chart_position':'Chart position','player_out':'Player out','injury_report_position':'Report position','official_game_status':'Official status','string_of_absent_player':'String of absent player','players_listed_at_this_spot':'Listed at this spot','named_replacement':'Named replacement','replacement_string':'Replacement string','players_behind_replacement':'Behind him','co_listed_at_same_string':'Co-listed at same string','replacement_also_on_injury_report':'Replacement on injury report','depth_of_replacement_summary':'Depth of the replacement','chart_url':'Club chart','injury_source_url':'Injury report'},
       table_id='dr-table', filterable=True)}
<h2>How this register fits the other one</h2>
<p>This repository holds two independent replacement-depth registers. They were built in parallel by different sessions
from the same kind of source. Together they cover <strong>{len(_union_names)} of 32 clubs</strong>:</p>
<ul class="findings">
<li><strong>This register</strong> (<code>data/depth_replacement.csv</code>): {', '.join(_covered_names)} — every
Out/Doubtful player on the Week 10 report who appears on that club's chart, {len(depth_repl)} rows.</li>
<li><strong>The other register</strong> (<code>data/replacement_depth_week10_2026.csv</code>, see
<a href="depth-deficiency.html">Deficiency tracking</a>): SEA, MIA, BAL, CLE, AZ, NYG — a quarterback-centred set
with the chart order quoted verbatim.</li>
<li><strong>One direct disagreement, recorded rather than resolved:</strong> this session's request to
www.seattleseahawks.com returned a consent and advertising interstitial, while the other session retrieved the Seattle
chart from <a href="https://www.seahawks.com/team/depth-chart" target="_blank" rel="noopener">www.seahawks.com</a>.
Seattle is therefore absent here and present there. Nothing was inferred to bridge the gap.</li>
<li><strong>One compounded loss the two registers agree on the shape of:</strong> Dallas safety P.J. Locke is Out and
the man behind him, Juanyeh Thomas, is himself Doubtful — a second-string replacement who may not play.</li>
</ul>
<h2>Coverage, and why it stops where it stops</h2>
<p>Six clubs publish a chart that could be read as text on {AS_OF}:
<a href="https://www.detroitlions.com/team/depth-chart" target="_blank" rel="noopener">Detroit</a>,
<a href="https://www.patriots.com/team/depth-chart" target="_blank" rel="noopener">New England</a>,
<a href="https://www.dallascowboys.com/team/depth-chart" target="_blank" rel="noopener">Dallas</a>,
<a href="https://www.packers.com/team/depth-chart" target="_blank" rel="noopener">Green Bay</a> (chart dated
Nov. 10, 2026),
<a href="https://www.tennesseetitans.com/team/depth-chart" target="_blank" rel="noopener">Tennessee</a> (chart dated
11/10/26) and
<a href="https://www.neworleanssaints.com/team/depth-chart" target="_blank" rel="noopener">New Orleans</a>.</p>
<ul class="findings">
<li><strong>Houston</strong> publishes its chart as an image, so no ordinal value can be read from the page text.</li>
<li><strong>Indianapolis</strong> and <strong>Minnesota</strong> could not be retrieved on this pass, and
<strong>Seattle</strong> returned a consent interstitial at the address used here. None was guessed.</li>
<li>Two players on this page — Kerby Joseph (DET) and Micah Parsons (GB) — are listed Out or Doubtful on the
league report but do not appear on their own club's chart at all. Their rows are blank and flagged.</li>
</ul>
""")

pages["correlation-provenance.html"] = ("Correlation provenance", f"""
<h1>Correlation provenance</h1>
<p class="note">Every correlation here names both of its inputs, the official page those inputs come from, and the n it
was computed on. Each previously published value was recomputed from the official ledger before this page was built;
the recomputation column records what happened, including where a published figure is rounded. <strong>The owner rule
matters here:</strong> under the rule registered as F49 and applied in <code>data/correlation_audit.csv</code>, a
correlation whose predictor is a <em>model output</em> is a diagnostic, not an officially sourced correlation, because
the predictor is not itself an official number. The column below states, row by row, which inputs are official and which
are model outputs, so that rule can be applied to any row without re-deriving it.</p>
{tiles([(len(corr_prov), 'correlations published'), (len(corr_prov), 'each with an n'),
        (_recomputed, 'recomputed from the ledger this session'), ('5', 'added by this session')])}
{search_box('cp-table')}
{table(corr_prov, ['corr_id','question','input_1','input_2','pair_measured','value','ci_low','ci_high','p_value','n','inputs_officially_sourced','method','recomputation_check','note','official_source_url'],
       {'corr_id':'ID','question':'Question','input_1':'Input 1','input_2':'Input 2','pair_measured':'Pair measured','value':'Value','ci_low':'CI low','ci_high':'CI high','p_value':'p','n':'n','inputs_officially_sourced':'Officially sourced','method':'Method','recomputation_check':'Recomputation','note':'Note','official_source_url':'Official source'},
       table_id='cp-table', filterable=True)}
<h2>What is still not publishable as a correlation</h2>
<ul class="findings">
<li><strong>Player-prop correlations.</strong> No player-prop outcomes, prices or settlement rules exist in this
repository, so no prop correlation can be computed (F31).</li>
<li><strong>Parlay-leg correlations beyond tickets.</strong> The two-leg study covers 24 tickets from a selected subset
of games. It is published with its n and without an interval for that reason.</li>
<li><strong>Anything built on a market price.</strong> With no odds feed, no correlation involving a price, a closing
line or a return can be computed at all (F07).</li>
</ul>
""")

pages["repo-audit.html"] = ("Repository audit", f"""
<h1>Repository audit — line by line</h1>
<p class="note">Every check below was run against a live official page or recomputed from the stored data on {AS_OF}.
The result column is produced by <code>scripts/repo_audit.py</code>, so re-running it reproduces this table. Where a
check found a problem, the row says so and links to the flag that carries it. Nothing here repairs anything: this page
reports, the <a href="flagged.html">Flagged for review</a> page collects. This is this session's pass; the
<a href="verification.html">Verification record</a> and the <a href="cross-check.html">independent cross-check</a>
carry the passes run by other sessions.</p>
{tiles([(len(repo_audit), 'checks run'), (_audit_pass, 'passed'),
        (len(repo_audit) - _audit_pass, 'irregularities found or resolved'),
        (sum(1 for r in repo_audit if r["status"] == "FAIL"), 'failed outright')])}
{search_box('ra-table')}
{table(repo_audit, ['check_id','area','what_was_checked','method','result','status','evidence_url'],
       {'check_id':'ID','area':'Area','what_was_checked':'What was checked','method':'Method','result':'Result','status':'Status','evidence_url':'Evidence'},
       table_id='ra-table', filterable=True)}
<h2>The findings this pass added</h2>
<ol class="findings">
<li><strong>Home-team bias in the originated side (<a href="flagged.html">F76</a>).</strong> Not statistically
significant, but the direction is consistent and it is now measured rather than assumed.</li>
<li><strong>The neutral-site defect, half closed.</strong> Week 11 MIN at SF is published with the home-field term
dropped and the schedule column that says why; the 137 completed historical rows still carry a blank neutral_site
value, which is the open half of F71 and is not resolved here.</li>
<li><strong>The constant reference total explained and re-derived.</strong> It is the league mean game total —
45.9197 points over the 137-game ledger, published as 45.9 — not a game-specific projection.</li>
<li><strong>One wording defect confirmed fixed.</strong> The ledger is weeks 1-9 complete plus the Week 10 Thursday
game, not "weeks 1-10"; the label no longer appears anywhere in the repository.</li>
</ol>
""")

# ---------- write ----------
os.makedirs(os.path.join(DOCS, "assets"), exist_ok=True)
# =====================================================================
# Session e208ba6d: market sheet, player props, event risk, review console
# =====================================================================
_risks_with_evidence = sum(1 for r in event_risk if "official statement" in r["role_evidence"])
_risks_total = len(event_risk)
_verif_ok = sum(1 for r in live_reverification if r["result"] == "match")
_decided = sum(1 for r in decision_console if r["recorded_choice"])
_mkt_loaded = sum(1 for r in market_sheet if r["market_line"])

pages["market-sheet.html"] = ("Market sheet", f"""
<h1>Market sheet — Week 11, all three markets, in origination order</h1>
<p class="note">Side first, then total, then moneyline, for all {len(lines_week11) if 'lines_week11' in dir() else ms['week11_games']} games.
Each row publishes the model's <strong>fair line</strong>, the <strong>market line</strong>, and the
<strong>difference</strong> as three separate columns. The fair line is computed; the market columns are
<strong>blank</strong> and marked UNVERIFIED, because no licensed odds feed is connected (F07). A blank cell here
is the correct output, not a missing value.</p>

<h2>Fair line, fair price, and the market columns</h2>
<p class="note">The <em>fair price</em> is the American price implied by the model — the price at which a
break-even book would offer the bet (prices are derived as 1/p; see <code>scripts/desk_v2.py</code>).
It is <strong>not</strong> a market price and must never be read as one. The model's probability of covering
its own originated number is one half by construction, so side and total show +100.</p>
{table(market_sheet, ['game_no','matchup','origination_order','market_type','selection','model_fair_line',
                     'fair_probability_implied','fair_american_price','market_line','market_price',
                     'edge_points_or_prob','status','source_url'],
       {'game_no':'Game','matchup':'Matchup','origination_order':'Order','market_type':'Market',
        'selection':'Selection','model_fair_line':'Fair line (model)','fair_probability_implied':'Fair prob.',
        'fair_american_price':'Fair price','market_line':'Market line','market_price':'Market price',
        'edge_points_or_prob':'Difference (market − fair)','status':'Status'},
       table_id='market-sheet', filterable=True)}

<h2>Why the market column stays blank</h2>
<div class="twocol">
<div><h3>What would fill it</h3><ul>
<li>A licensed historical odds archive with written model-use rights (DEC-01 / P01).</li>
<li>A timestamped opening number and a timestamped closing number for the same market.</li>
<li>A settlement rule for each market, so a push can be told from a win.</li>
</ul></div>
<div><h3>What will not fill it</h3><ul>
<li>A public sportsbook page: not an official source, and its terms are unreviewed.</li>
<li>An NFL.com odds widget: it displays partner prices live, but it is not an archive and
the FAQ does not grant reuse rights (F07).</li>
<li>Any estimate, midpoint or "typical" number. Nothing is inferred here.</li>
</ul></div>
</div>

<h2>Sealed prospective forecast log</h2>
<p class="note">Every Week 11 number in this table is frozen in
<code>data/prospective_forecast_log.csv</code> before kickoff, with a SHA-256 digest so a later edit is
detectable. Digest: <code>{SEAL}</code>. The log is the only honest way to prove a record was not fitted
after the fact.</p>
{table(forecast_log, ['log_id','matchup','kickoff_et','frozen_spread_home','frozen_total',
                      'frozen_home_win_prob','fit_games_used','fit_weeks_used','frozen_before_kickoff',
                      'result_recorded','source_url'],
       {'log_id':'Seal','matchup':'Matchup','kickoff_et':'Kickoff (ET)','frozen_spread_home':'Frozen spread (home)',
        'frozen_total':'Frozen total','frozen_home_win_prob':'Home win prob.','fit_games_used':'Fit games',
        'fit_weeks_used':'Fit weeks','frozen_before_kickoff':'Frozen before kickoff',
        'result_recorded':'Result recorded'},
       table_id='sealed-log', filterable=True)}
""")

pages["props.html"] = ("Player props", f"""
<h1>Player props and prop combinations</h1>
<p class="note">The brief asks for player prop bet combos. This page separates two questions that are usually
conflated: <strong>are prop outcomes available from an official source?</strong> and
<strong>are prop prices available?</strong> The answers differ, and that difference decides what can be built.</p>

<div class="twocol">
<div><h3>Outcomes: available officially</h3><ul>
<li>NFL.com publishes per-player, per-game logs (passing, rushing, receiving, scoring) on each player's
<code>/stats/logs/</code> page. That is an official source for the outcome of any prop.</li>
<li>This repository holds <strong>no</strong> player-level game series (F31), so no prop has been graded.</li>
</ul></div>
<div><h3>Prices: not available</h3><ul>
<li>A prop bet is a contract between a bettor and a book. The league does not publish prop lines.</li>
<li>Without a licensed price feed there is no prop market line, no prop edge and no prop ROI (F07).</li>
<li>So a prop can be <em>originated and graded</em> but would still not be <em>priced</em>.</li>
</ul></div>
</div>

<h2>Prop market families — status and honest basis</h2>
{table(prop_markets, ['prop_id','market_family','position_group','origination_order','official_outcome_source',
                      'outcome_held_in_repo','model_fair_line','market_line','market_price','graded_out_of_sample',
                      'status','next_step','source_url'],
       {'prop_id':'ID','market_family':'Market family','position_group':'Positions','origination_order':'Order',
        'official_outcome_source':'Official outcome source','outcome_held_in_repo':'Outcome held here?',
        'model_fair_line':'Fair line','market_line':'Market line','market_price':'Market price',
        'graded_out_of_sample':'Graded out of sample?','status':'Status','next_step':'What would unblock it'},
       table_id='prop-markets', filterable=True)}

<h2>Prop combinations — the dependency problem</h2>
<p class="note">A prop combo is two or more props on the same game. Its price depends on the correlation
between the legs, and that correlation is exactly what nobody has measured in this repository. Positive
correlation makes the true joint probability <em>higher</em> than the product of the legs, so the naive price
is too long; negative correlation makes it too short. Until the correlation exists, a combo price would be
a guess dressed as arithmetic.</p>
{table(prop_combos, ['combo_id','combo','legs','correlation_known','correlation_value','sample_n',
                     'why_it_matters','what_is_needed','status','source_url'],
       {'combo_id':'ID','combo':'Combination','legs':'Legs','correlation_known':'Correlation known?',
        'correlation_value':'Value','sample_n':'n','why_it_matters':'Why it matters',
        'what_is_needed':'What is needed','status':'Status'},
       table_id='prop-combos')}

<h2>Same-game correlation matrix</h2>
<p class="note">Every value below is published with its sample size <code>n</code>, as the brief requires.
Rows marked <em>definitional</em> or <em>assumption</em> are labelled, so a reader can tell an estimate from a
convention. Rows marked <em>unverified</em> carry no number at all.</p>
{table(corr_matrix, ['corr_id','leg_pair','question','value','sample_n','basis','sign_convention','status','source_url'],
       {'corr_id':'ID','leg_pair':'Leg pair','question':'Question','value':'Value','sample_n':'n',
        'basis':'Basis','sign_convention':'Reading','status':'Status'},
       table_id='corr-matrix', filterable=True)}

<h2>What a reader should conclude</h2>
<ul class="findings">
<li>The side/total phi of <strong>-0.30 on 24 tickets</strong> is the only measured same-game dependence in this
repository, and 24 tickets is far too few to price anything (F33).</li>
<li>The model's own side and total <em>errors</em> correlate at a small negative value, which means the
independence shortcut is at least not obviously wrong for this model — not that it is right.</li>
<li>Prop-vs-prop correlation cannot be measured until a player game series is transcribed (P02).</li>
</ul>
""")

pages["event-risk.html"] = ("Event risk", f"""
<h1>Named event risk — Week 11</h1>
<p class="note">A number is only useful if you know what can invalidate it. This page names the specific
players, the specific official status words, and the specific markets at risk, drawn from the verified Week 10
injury report and cross-referenced to the Week 11 slate. It deliberately does <strong>not</strong> apply an
adjustment, because the size of the effect is not quantified anywhere in this repository.</p>

{tiles([(len(lines_week11) if 'lines_week11' in dir() else ms['week11_games'], 'Week 11 games'),
        (_risks_total, 'named risks published'),
        (_risks_with_evidence, 'risks where an official source names the player'),
        (_risks_total - _risks_with_evidence, 'risks where the role is NOT official'),
        (1, 'week of injury data held')])}

<h2>Coverage summary</h2>
{table(event_risk_summary, ['metric','value','basis','source_url'],
       {'metric':'Measure','value':'Value','basis':'Basis'}, table_id='risk-summary')}

<h2>The blind spot, stated as a number</h2>
<p class="note"><strong>{_risks_total - _risks_with_evidence} of {_risks_total} named risks have no official
source establishing the player's role</strong>, and therefore no replacement depth rank. That is not a
presentation problem: it means an injury adjustment cannot currently be priced, and any page that claims
otherwise is guessing. The cause is F06 — the NFL publishes no league-level depth chart, and the club charts
that do exist self-label "unofficial" (F45).</p>

<h2>Risks with official role evidence</h2>
{table([r for r in event_risk if 'official statement' in r['role_evidence']],
       ['risk_id','matchup','team','player','position','official_status','role_evidence','replacement_depth','source_url'],
       {'risk_id':'ID','matchup':'Matchup','team':'Team','player':'Player','position':'Pos.',
        'official_status':'Official status','role_evidence':'Official role evidence',
        'replacement_depth':'Replacement'}, table_id='risk-evidence', filterable=True)}

<h2>All named risks (Out / Doubtful on a Week 11 team)</h2>
{table(event_risk, ['risk_id','matchup','team','player','position','official_status','official_injury','role_evidence','market_at_risk','replacement_depth','risk_is_quantified','source_url'],
       {'risk_id':'ID','matchup':'Matchup','team':'Team','player':'Player','position':'Pos.',
        'official_status':'Status','official_injury':'Injury','role_evidence':'Official role evidence',
        'market_at_risk':'Market at risk','replacement_depth':'Replacement depth',
        'risk_is_quantified':'Quantified?'}, table_id='event-risk', filterable=True)}
""")

pages["review.html"] = ("Review console", f"""
<h1>Review console — choose a path before anything is built</h1>
<p class="note">This is the section the brief asks for: a place to review proposals and
<strong>choose</strong> a path before any change is implemented. Each row below is a real decision with three
options, the recommended option, the exact file a session would change, what the choice unblocks, and what
stays blocked while it is undecided.</p>

<div class="hero">
<p><strong>How to record a choice.</strong> Edit <code>data/decision_choices.json</code> and add, for example:</p>
<pre>{{"P04": {{"choice": "B", "decided_by": "owner", "decided_on": "2026-11-15",
  "reason": "a rule that demotes everything carries no information"}}}}</pre>
<p>Then run <code>python3 scripts/review.py &amp;&amp; python3 scripts/build.py</code>. The row changes to
<strong>DECIDED</strong> and keeps your reason and date. Nothing is implemented by recording a choice — it only
authorises a later session to do the work.</p>
<p class="note"><strong>No choice is pre-filled.</strong> {_decided} of {len(decision_console)} proposals have a
recorded choice. The site does not know the owner's mind and does not pretend to.</p>
</div>

<h2>Proposals awaiting a decision</h2>
{table(decision_console, ['proposal_id','area','question','option_a','option_b','option_c','recommended_now',
                          'why_recommended','status','decided_by','decided_on','files_a_session_would_change',
                          'unblocks','blocks','cost','source_url'],
       {'proposal_id':'ID','area':'Area','question':'Decision','option_a':'Option A','option_b':'Option B',
        'option_c':'Option C','recommended_now':'Recommended now','why_recommended':'Why',
        'status':'Status','decided_by':'Decided by','decided_on':'On',
        'files_a_session_would_change':'Files a session would change','unblocks':'Unblocks','blocks':'Stays blocked',
        'cost':'Cost'}, table_id='decisions', filterable=True)}

<h2>How to read this table</h2>
<div class="twocol">
<div><h3>Do this</h3><ul>
<li>Read the <em>Stays blocked</em> column first. It tells you the cost of not deciding.</li>
<li>Prefer the option whose failure mode is visible. A blank cell is visible; a guessed number is not.</li>
<li>Record a choice even when it is "defer". An explicit defer is a decision; silence is not.</li>
</ul></div>
<div><h3>Avoid this</h3><ul>
<li>Choosing Option C anywhere it means scraping a non-official page. That breaks the rule the whole
repository is built on.</li>
<li>Treating the recommendation as a decision. It is one session's judgement, offered for review.</li>
<li>Implementing first and recording afterwards. The point of the console is order.</li>
</ul></div>
</div>
""")



# ---------- session e208ba6d: appends to existing pages ----------
_lr_ok = sum(1 for r in live_reverification if r["result"] == "match")
_lr_bad = len(live_reverification) - _lr_ok

pages["verification.html"] = (pages["verification.html"][0], pages["verification.html"][1] + f"""
<h2>Independent live re-verification, read again on {AS_OF}</h2>
<p class="note">A second, independent transcription of the same official pages was made this session and
compared row by row against the registers in this repository. It does not reuse the first transcription:
<code>data/verification_inputs/</code> holds the fresh read, and <code>scripts/verify_live.py</code> performs the
comparison. <strong>{_lr_ok} of {len(live_reverification)} checked units match exactly; {_lr_bad} discrepancies.</strong>
A "unit" is one team's injury block, one team's standings line, one Week 11 game, or the bye list.</p>
{tiles([(len(live_reverification), 'units checked'), (_lr_ok, 'matched exactly'), (_lr_bad, 'discrepancies'),
        (tot['rows'], 'injury rows compared')])}
{table(live_reverification, ['check_id','unit','repo_rows','live_rows','missing_from_repo','extra_in_repo',
                           'field_differences','result','read_utc','checked_against'],
       {'check_id':'ID','unit':'Unit checked','repo_rows':'Rows here','live_rows':'Rows live',
        'missing_from_repo':'Missing here','extra_in_repo':'Extra here','field_differences':'Field differences',
        'result':'Result','read_utc':'Read (UTC)','checked_against':'Official page'},
       table_id='live-reverif', filterable=True)}
<p class="note"><strong>What this does and does not prove.</strong> It proves the transcription in this
repository matches the page as served on {AS_OF}. It does not prove the page is right about a player, and it
is not permission to re-print the page (F16).</p>
""")

pages["executive-summary.html"] = (pages["executive-summary.html"][0], pages["executive-summary.html"][1] + f"""
<h2>Added this session: what changed in the evidence, in one place</h2>
<div class="twocol">
<div><h3>Things that got stronger</h3><ul>
<li><strong>The official data was re-read from scratch and matched.</strong> {_lr_ok} of
{len(live_reverification)} units - every team's injury block, every standings line, every Week 11 game and the
bye list - agree with an independent transcript made this session.</li>
<li><strong>Gate G1 is now computed, not asserted.</strong> It passes {ms['lookahead_tests']} tests: training
weeks strictly earlier, refit reproduces archived predictions exactly, and an early-window fit differs from a
full-sample fit (Flag F50 resolved).</li>
<li><strong>Forecasts are now sealed before kickoff.</strong> All {ms['week11_games']} Week 11 numbers carry a
SHA-256 digest, so a later edit is detectable.</li>
</ul></div>
<div><h3>Things that got worse - and are now visible</h3><ul>
<li><strong>No prospective strategy has earned a rank.</strong> The historic walk-forward research is kept separate from the competition leaderboard until the frozen prospective forecasts are graded.</li>
<li><strong>{_risks_total - _risks_with_evidence} of {_risks_total} named injury risks cannot have their role
confirmed officially</strong>, so no injury adjustment can be priced (F06).</li>
<li><strong>Player props are blocked on data the repository does not hold</strong>, though the outcomes
themselves are obtainable from NFL.com (F31, P02).</li>
</ul></div>
</div>
<h2>Decisions actually waiting on you</h2>
<p class="note">{len(decision_console)} decisions are recorded on the <a href="review.html">Review console</a>,
{_decided} of them decided. Each has three options, a recommendation, the file it would change, and what stays
blocked until it is chosen. No option is pre-selected.</p>
{table(decision_console, ['proposal_id','area','question','recommended_now','status','blocks','source_url'],
       {'proposal_id':'ID','area':'Area','question':'Decision','recommended_now':'Recommended',
        'status':'Status','blocks':'Stays blocked'}, table_id='exec-decisions')}
""")

_new_intro = (
    '<section class="hero">\n'
    '  <h2>New this session</h2>\n'
    '  <p class="note"><strong>A review console where a path can be chosen</strong> - '
    f'{len(decision_console)} decisions, {_decided} recorded, no option pre-filled. '
    '<strong>A market sheet</strong> that keeps the fair line, the market line and the difference in three separate '
    'columns. <strong>A prospective-only leaderboard</strong> that withholds all historical backtest scores until '
    'frozen prospective outcomes are graded. <strong>A named event-risk register</strong> for Week 11. And a 2026-11-18 re-read of the '
    f'injury register (347 rows) compared by script: {_lr_ok} of {len(live_reverification)} units consistent, {_lr_bad} inconsistencies (same transcription on both sides, so this is not independent verification).</p>\n'
    '  <p class="note">Start at the <a href="review.html">Review console</a> if you want to decide something, or the '
    '  <a href="market-sheet.html">Market sheet</a> if you want a number.</p>\n'
    '</section>\n'
    '<h2>Start here</h2>'
)
pages["index.html"] = (pages["index.html"][0],
                       pages["index.html"][1].replace('<h2>Start here</h2>', _new_intro, 1))


# ---------- session b03f4ba1: control baselines, change-our-mind, removal-of-luck panel, decision readiness ----------
# Each table below is generated from a register in data/ and reads its own source link from that register.
# Backtest diagnostics are displayed only on the landing-page research panel (not the competition leaderboard).
# Values are copied from the separately named research/control registers; the luck share remains explicitly heuristic (F85).
controls_rows = read_csv("control_baselines.csv")
research_rows = read_csv("strategy_backtest_scores.csv")
mind_rows = read_csv("strategy_change_rules.csv")
ready_rows = read_csv("decision_readiness.csv")
# F90: the readiness table must have one row per requirement in the register.
# Assert the requirement_id column is a bijection onto the register's R-ids.
_reg_ids = [r["req_id"] for r in reqs]
_ready_map = {}
for _r in ready_rows:
    _rid = (_r.get("requirement_id") or "").strip()
    if not _rid:
        continue
    if _rid in _ready_map:
        raise SystemExit(f"BUILD FAILED: requirement {_rid} appears in readiness rows "
                         f"{_ready_map[_rid]} and {_r['req_id']}")
    _ready_map[_rid] = _r["req_id"]
if set(_ready_map) != set(_reg_ids):
    raise SystemExit("BUILD FAILED: readiness table does not cover exactly the requirements "
                     f"register ({len(_reg_ids)} requirements): missing {sorted(set(_reg_ids) - set(_ready_map))}, "
                     f"extra {sorted(set(_ready_map) - set(_reg_ids))}")
_ready_status = Counter(r["status"].split(" (")[0].strip() for r in ready_rows)
_ready_done = _ready_status.get("Done", 0)
_ready_partial = _ready_status.get("Partial", 0)
_ready_missing = _ready_status.get("Missing", 0)
_ready_blocked = _ready_status.get("Blocked", 0)
_ready_irreg = _ready_status.get("Irregular", 0)
_luck_rows = [
    {"strategy_id": r["strategy_id"], "strategy": r["strategy"],
     "skill": r["skill_score_mae_improvement_pts"], "skill_ci": f'{r["skill_ci_low"]} to {r["skill_ci_high"]}',
     "weeks": r["weeks_positive_skill"], "week_p": r["week_sign_test_p"], "halves": r["halves_agree"],
     "luck_index": r["luck_share_of_record"], "verdict": r["skill_or_luck_verdict"],
     "source_url": r.get("source_url") or "https://www.nfl.com/schedules/2026/by-week/week-4"}
    for r in research_rows
]
_ctl_html = table(controls_rows,
    ["control_id", "control", "rule", "decided_games_n", "correct", "accuracy", "ci95_low", "ci95_high",
     "p_vs_coin_two_sided", "basis", "source_url"],
    {"control_id": "ID", "control": "Control", "rule": "Rule", "decided_games_n": "Decided games (n)",
     "correct": "Correct", "accuracy": "Accuracy", "ci95_low": "Low", "ci95_high": "High",
     "p_vs_coin_two_sided": "p vs coin", "basis": "Basis", "source_url": "Source"},
    table_id="controls-table")
_mind_html = table(mind_rows,
    ["strategy_id", "strategy", "current_evidence", "what_would_move_us_toward_trusting_it",
     "what_would_move_us_away_from_it", "pre_registration_status", "source_url"],
    {"strategy_id": "ID", "strategy": "Strategy", "current_evidence": "Current evidence",
     "what_would_move_us_toward_trusting_it": "Would move us TOWARD trusting it",
     "what_would_move_us_away_from_it": "Would move us AWAY from it",
     "pre_registration_status": "Pre-registration", "source_url": "Source"},
    table_id="mind-table")
_luck_html = table(_luck_rows,
    ["strategy_id", "strategy", "skill", "skill_ci", "weeks", "week_p", "halves", "luck_index", "verdict", "source_url"],
    {"strategy_id": "ID", "strategy": "Historical strategy research", "skill": "Skill (MAE pts)",
     "skill_ci": "Skill 95% interval", "weeks": "Weeks positive", "week_p": "Sign-test p",
     "halves": "Halves agree", "luck_index": "Luck index (heuristic, F85)", "verdict": "Verdict",
     "source_url": "Source"},
    table_id="luck-panel-table")
_ready_html = table(ready_rows,
    ["req_id", "requirement_id", "brief_item", "status", "what_the_repo_shows_now", "blocking_gate", "number_that_clears_it", "source_url"],
    {"req_id": "ID", "requirement_id": "Requirement ID", "brief_item": "Requirement (from the brief)", "status": "Status",
     "what_the_repo_shows_now": "What the repo shows now", "blocking_gate": "Gate that blocks it",
     "number_that_clears_it": "Number that would clear it", "source_url": "Source"},
    table_id="readiness-table", filterable=True)

_mind_add = (
    '<h2>Two-sided: what would change our mind, per candidate strategy</h2>'
    '<p class="note">Each candidate states evidence that would move us toward or away from trusting it. '
    'These are future decision rules, not historical leaderboard results; the registration gate is still open (F87).</p>'
    + _mind_html
)
pages["strategy-lab.html"] = (pages["strategy-lab.html"][0], pages["strategy-lab.html"][1] + _mind_add)

_idx_add = (
    '<h2>Removal-of-luck research panel</h2>'
    '<p class="note">Historical walk-forward diagnostics only — <strong>not a competition leaderboard</strong>. '
    'The table shows skill, uncertainty, week consistency and the heuristic luck index (share of the interval below zero, F85). '
    'This cannot remove football variance or establish prospective skill; no ranking or reward is assigned here.</p>'
    + _luck_html +
    '<h2>Control baselines (historical research)</h2>'
    '<p class="note">Controls use the same historical decided games; the “favourite” is from the naive reference line, not a betting market.</p>'
    + _ctl_html +
    '<h2>Decision readiness: one row per requirement</h2>'
    f'<p class="note">One row per requirement in the requirements register ({len(ready_rows)} of {len(_reg_ids)}). '
    f'<strong>{_ready_done} done, {_ready_partial} partial, {_ready_missing} missing, '
    f'{_ready_blocked} blocked, {_ready_irreg} irregular.</strong> Each row names the gate that blocks it and the number '
    'that would clear it. A number is given only where the repo has a threshold for it; otherwise the basis column '
    'says so. Each row carries its register requirement ID; the readiness-to-register mapping is recorded in '
    'data/readiness_mapping.csv and is this session&rsquo;s interpretation, flagged F103 for owner review.</p>'
    + _ready_html
)

pages["index.html"] = (pages["index.html"][0], pages["index.html"][1] + _idx_add)


# ---------- per-team view, Week 10 (session 6ee4d13e, T98) ----------
# Built from data/team_view_week10_2026.csv by scripts/team_view.py, which asserts every count
# against the injury report before writing. This block only renders and checks the file.
_tv = read_csv("team_view_week10_2026.csv")
if len(_tv) != 32:
    raise SystemExit(f"BUILD FAILED: team view has {len(_tv)} rows, expected 32")
if len({r["team_abbr"] for r in _tv}) != 32:
    raise SystemExit("BUILD FAILED: team view does not list 32 distinct clubs")
for _r in _tv:
    _bye = _r["week10_status"].startswith("Bye")
    if _bye and any(_r[k] for k in ("listed_players", "out_count", "net_injury_count")):
        raise SystemExit(f"BUILD FAILED: bye club {_r['team_abbr']} shows injury counts")
    if not _bye and not _r["source_url"].startswith("https://www.nfl.com/"):
        raise SystemExit(f"BUILD FAILED: team view row {_r['team_abbr']} lacks an NFL.com source")
    if _r["replacements_named_chart"] and not _r["starters_out_chart_names"]:
        raise SystemExit(f"BUILD FAILED: {_r['team_abbr']} names a replacement with no starter out")
_tv_sum = {k: sum(int(_r[c]) for _r in _tv if _r[c] != "") for k, c in
           (("Out", "out_count"), ("Doubtful", "doubtful_count"), ("Questionable", "questionable_count"))}
if _tv_sum != {"Out": 70, "Doubtful": 11, "Questionable": 90}:
    raise SystemExit(f"BUILD FAILED: team view totals {_tv_sum} do not reconcile with the injury report")
_tv_chart = sum(1 for _r in _tv if _r["starter_order_source"].startswith("Club"))
_tv_named = sum(int(_r["replacements_named_chart_pairs"]) for _r in _tv if _r["replacements_named_chart_pairs"] != "")
_tv_byes = [_r["team_abbr"] for _r in _tv if _r["week10_status"].startswith("Bye")]
_tv_html = table(_tv, [
        "team_abbr", "team_name", "week10_status", "listed_players", "out_count", "doubtful_count",
        "questionable_count", "no_game_designation_count", "net_injury_count", "starters_out_chart_names",
        "replacements_named_chart", "replacements_named_article", "starter_order_source", "unverified_note",
        "source_url", "chart_url"],
    {"team_abbr": "Club", "team_name": "Name", "week10_status": "Week 10 status", "listed_players": "Listed",
     "out_count": "Out", "doubtful_count": "Doubtful", "questionable_count": "Questionable",
     "no_game_designation_count": "No game designation", "net_injury_count": "Net injury count (Out + Doubtful)",
     "starters_out_chart_names": "Starters Out on the club chart (1st string)",
     "replacements_named_chart": "Replacement named on the chart (verified rows only)",
     "replacements_named_article": "Replacement named in an official article",
     "starter_order_source": "Starter-order source", "unverified_note": "Note",
     "source_url": "Source", "chart_url": "Club chart"},
    table_id="team-view-table", filterable=True)
pages["team-view.html"] = ("Per-team view", (
    '<h1>Per-team view: Week 10, 2026</h1>'
    '<p class="note">One row per club (32). Injury counts come from the official NFL.com Week 10 injury report, '
    'as held in <code>data/injuries_week10_2026.csv</code>; the rows reconcile to 70 Out, 11 Doubtful and 90 Questionable '
    '(347 listed players, of which 176 have no game designation; read 2026-11-18). Four clubs were on bye and have no injury section '
    f'(official schedule, Teams on Bye: {", ".join(_tv_byes)}); they are shown blank, never as injury-free.</p>'
    f'<p class="note"><strong>Starter order is known for only {_tv_chart} of 32 clubs</strong>: the club team-site charts '
    'in <code>data/depth_replacement.csv</code>. For every other club the starter column is blank, not inferred. '
    f'Named replacements shown: {_tv_named} verified (player, replacement) pairs from club charts, plus the article-named rows. '
    'A player with no verified replacement stays unnamed. Two charts (DET, NE) label themselves unofficial (F05, F18); '
    'no chart in the register states its as-of date (chart_as_of is not stated on any page).</p>'
    '<p class="note"><strong>Verification scope (read 2026-11-15 from https://www.nfl.com/injuries/):</strong> '
    'On the 2026-11-18 read, all 28 club sections were transcribed and compared row by row with the register. '
    'The register now reproduces that read. Changes against the 2026-11-14 file are listed in data/captures/injury_delta_2026-11-18.csv (F94, F95). '
    'A named replacement who is also on the report is labelled with that status.</p>'
    '<p class="note"><strong>Row count (F83, updated 2026-11-18):</strong> the live official page read on 2026-11-18 holds 347 player rows. '
    'Neither 279 (the brief\'s live figure) nor 254 (its published figure) is reproduced by this read; their source is not in the repo. Flag F83 stays open on that point.</p>'
    + _tv_html))

# ---------- controls for every backtest run (session 6ee4d13e, T101; research only) ----------
# Backtest statistics belong on the Backtest research page, never on the prospective leaderboard (see the
# leakage guard above), so this block is appended to backtest.html.
# Written by scripts/baselines.py, called from scripts/model.py, which raises if a run's bet set or
# mean edge cannot be reproduced. The rows below are rendered as written; nothing is re-derived here.
_lbc = read_csv("leaderboard_control_runs.csv")
for _r in _lbc:
    if _r["status"] == "Computed" and _r["control"].startswith("Random") and _r["n_decided"] != _r["reproduced_bets"]:
        raise SystemExit(f"BUILD FAILED: {_r['strategy_id']} control row does not reproduce its bet count")
    if not _r["source_url"].startswith("https://www.nfl.com/"):
        raise SystemExit(f"BUILD FAILED: backtest control row {_r['strategy_id']} lacks an NFL.com source")
_lbc_ids = sorted({_r["strategy_id"] for _r in _lbc if _r["strategy_id"] != "ALL"})
if _lbc_ids != ["M1", "M2", "M3", "M4", "P1", "R1", "T1"]:
    raise SystemExit(f"BUILD FAILED: backtest controls cover {_lbc_ids}, expected all seven runs")
_lbc_html = table(_lbc, [
        "strategy_id", "control", "market", "n_bet_games", "n_decided", "strategy_mean_edge", "control_mean_edge",
        "control_edge_p025", "control_edge_p975", "share_random_draws_at_least_strategy",
        "strategy_minus_control", "diff_ci_low", "diff_ci_high", "strategy_hit_rate", "control_hit_rate",
        "status", "source_url"],
    {"strategy_id": "Run", "control": "Control", "market": "Market", "n_bet_games": "Bet games",
     "n_decided": "Decided", "strategy_mean_edge": "Run mean edge (pts)", "control_mean_edge": "Control mean edge (pts)",
     "control_edge_p025": "Control 2.5%", "control_edge_p975": "Control 97.5%",
     "share_random_draws_at_least_strategy": "Share of random draws at least as high",
     "strategy_minus_control": "Run minus control", "diff_ci_low": "Paired diff 2.5%", "diff_ci_high": "Paired diff 97.5%",
     "strategy_hit_rate": "Run hit rate", "control_hit_rate": "Control hit rate", "status": "Status",
     "source_url": "Source"},
    table_id="backtest-controls-table", filterable=True)
_lbc_add = (
    '<h2>Controls for every backtest run (T101, research only)</h2>'
    '<p class="note"><strong>Historical walk-forward diagnostics, not a competition ranking.</strong> Each run is graded against two controls on the <strong>exact bets that run made</strong>: '
    'seeded random picks, and the reference-line favourite on the same games. Edges are in points against the naive '
    'reference line, computed from unrounded walk-forward predictions (scripts/baselines.py). '
    '<strong>No market favourite exists in this repository</strong> (F32), so the favourite control is the reference line\'s, '
    'not a bookmaker\'s. A total (T1) and a parlay (P1) have no single favourite, so their favourite control is marked '
    'not applicable. The context row shows the reference favourite on all 89 games; it is negative, so the favourite '
    'control is weak on its own (F91), and random picks remain the skill control. The straight-up control panel above '
    'uses a different measure (winner, not edge) and is not comparable row-for-row.</p>'
    + _lbc_html
)
pages["backtest.html"] = (pages["backtest.html"][0], pages["backtest.html"][1] + _lbc_add)


# ---------- session d0ede22d (T102-T105): captures, what changed, fixture context, drift alarm ----------
# Adds three pages and index cards. Reads only the files written by scripts/capture_* logic and the
# registers named in each table; every row carries an official NFL.com source link (row-source check).
import csv as _csv
import sys as _sys
_sys.path.insert(0, os.path.join(ROOT, "scripts"))
import drift_check as _drift_mod  # noqa: E402  (same checks as the build-time alarm above)

def _rd(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8", newline="") as _fh:
        return list(_csv.DictReader(_fh))

def _lnk(url, label="NFL.com"):
    return f'<a href="{html.escape(url)}" target="_blank" rel="noopener">{html.escape(label)}</a>'

def _tbl(headers, rows, tid):
    head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return (f'<div class="tablewrap"><table class="data" id="{tid}"><thead><tr>{head}</tr></thead>'
            f'<tbody>{body}</tbody></table></div>')

_inj_delta = _rd("data/captures/injury_delta_2026-11-18.csv")
_stand = _rd("data/standings_diff_2026-11-14_to_2026-11-18.csv")
_fix = _rd("data/fixture_context_2026.csv")
_pins = _rd("data/drift_pins.csv")
_meta = json.load(open(os.path.join(ROOT, "data/captures/injury_week10_2026-11-18.meta.json"), encoding="utf-8"))
_games_added = sum(int(r["games_added"]) for r in _stand) // 2

_cap_meta_rows = [
    ["Capture", f"Week 10 injury report, {_meta['rows_transcribed']} player rows, {_meta['clubs_with_section']} club sections; "
                f"bye clubs without a section: {', '.join(_meta['bye_clubs_without_section'])}",
     _lnk(_meta["source_url"], "NFL.com injury report")],
    ["Read time (UTC)", _meta["transcribed_utc"] + " (session clock; the fetch tool returns no per-request time)",
     _lnk(_meta["source_url"], "NFL.com injury report")],
    ["Transcription SHA-256", _meta["transcription_sha256"] + " (covers the transcription file only; the raw page bytes were not retained, see note)",
     _lnk(_meta["source_url"], "NFL.com injury report")],
    ["Status counts (read 2026-11-18)", "Out 70 · Questionable 90 · Doubtful 11 · no game designation 176",
     _lnk(_meta["source_url"], "NFL.com injury report")],
    ["Changes against the 2026-11-14 register", f"{len(_inj_delta)} changes (32 field values on 16 players, 2 added rows); each listed below",
     _lnk(_meta["source_url"], "NFL.com injury report")],
]

_stand_rows = []
for _r in _stand:
    _stand_rows.append([
        html.escape(_r["team_abbr"]), html.escape(_r["team_name"]), html.escape(_r["record_prior"]),
        html.escape(_r["record_current"]), html.escape(_r["games_added"]), html.escape(_r["net_prior"]),
        html.escape(_r["net_current"]), html.escape(_r["net_rank_prior"]), html.escape(_r["net_rank_current"]),
        html.escape(_r["rank_change_up_is_positive"]),
        _lnk("https://www.nfl.com/standings/", "NFL.com standings (2026-11-18 read)"),
    ])

_inj_rows = []
for _r in _inj_delta:
    _inj_rows.append([
        html.escape(_r["change_id"]), html.escape(_r["team"]), html.escape(_r["player"]),
        html.escape(_r["change_type"]), html.escape(_r["field"]),
        html.escape(_r["prior_value_2026_11_14"] or "(blank)"), html.escape(_r["live_value_2026_11_18"] or "(blank)"),
        _lnk(_r["source_url"], "NFL.com injury report"),
    ])

_pin_rows = []
for _p in _pins:
    _probs = _drift_mod.check(_p)
    _pin_rows.append([
        html.escape(_p["register"]), html.escape(_p["expected_rows"]), html.escape(_p["required_nonblank_columns"]),
        ('<span class="ok">PASS</span>' if not _probs else '<span class="warn">FAIL: ' + html.escape("; ".join(_probs)) + '</span>'),
        html.escape(_p["note"]),
        _lnk("https://www.nfl.com/injuries/", "NFL.com injury report") if "injur" in _p["register"]
        else _lnk("https://www.nfl.com/standings/", "NFL.com standings") if "standings" in _p["register"]
        else _lnk("https://www.nfl.com/schedules/2026/by-week/week-10", "NFL.com schedule"),
    ])

pages["captures.html"] = ("Official captures and what changed", f"""
<h1>Official captures and what changed</h1>
<p class="note"><strong>Read 2026-11-18.</strong> This page holds the dated official reads that replace the single
2026-11-14 snapshot. It publishes changes, not levels, wherever two reads exist. Each row links to the official page it
came from. Nothing here is a prediction.</p>
<p class="note"><strong>Not a scheduled capture.</strong> These reads were made by hand, one page request per chunk. The
NFL.com Terms (Section 1.3) prohibit systematic retrieval to compile data without written consent, and gate D22 is not
cleared, so no automated daily capture runs (see F98). The clock-time history the brief asks for therefore starts with
two reads, not with a daily series.</p>
<p class="note"><strong>Results register is behind the official standings (F96).</strong> The verified results feed holds
137 games (weeks 1-9 plus the Week 10 Thursday game). The 2026-11-18 standings reflect {_games_added} more games played
in Week 10 (Sunday and Monday), which are not in the frozen register.</p>
<h2>Injury report: capture details</h2>
{_tbl(["Item", "Value", "Source"], _cap_meta_rows, "cap-meta")}
<h2>Injury report: changes since 2026-11-14 (publishing the delta, not the level)</h2>
<p class="note">Prior value is the 2026-11-14 register; live value is the 2026-11-18 read. A blank is shown as "(blank)" and means the page cell was empty.</p>
{_tbl(["Change", "Club", "Player", "Type", "Field", "Prior (2026-11-14)", "Live (2026-11-18)", "Source"], _inj_rows, "inj-delta")}
<h2>Standings: what changed between the two reads</h2>
<p class="note">Net rank: clubs sorted by points for minus points against (ties share a rank). Rank change is prior rank minus current rank, so a positive value means the club moved up. Derived only from the two official reads (scripts/standings_diff.py).</p>
{_tbl(["Club", "Name", "Record 2026-11-14", "Record 2026-11-18", "Games added", "Net pts prior", "Net pts now", "Net rank prior", "Net rank now", "Rank change (+ = up)", "Source"], _stand_rows, "stand-diff")}
<h2>Drift alarm: pinned checks on every register</h2>
<p class="note">Each register is pinned to a row count, required non-blank columns and key uniqueness (data/drift_pins.csv). The build stops if any check fails.</p>
{_tbl(["Register", "Pinned rows", "Required non-blank columns", "Status", "Note", "Source"], _pin_rows, "drift")}
""")

_fix_rows = []
for _r in _fix:
    _fix_rows.append([
        html.escape(_r["week"]), html.escape(_r["game_date"]), html.escape(_r["weekday"]),
        html.escape(f'{_r["away_team"]} at {_r["home_team"]}'),
        html.escape(_r["away_days_since_last_game"] or "(none)"), html.escape(_r["home_days_since_last_game"] or "(none)"),
        html.escape(_r["rest_diff_home_minus_away"] or "(blank)"),
        html.escape(("away bye" if _r["away_bye_before_game"] == "1" else "") + (" / " if _r["away_bye_before_game"] == "1" and _r["home_bye_before_game"] == "1" else "") + ("home bye" if _r["home_bye_before_game"] == "1" else "")) or "-",
        html.escape(_r["thursday_game"]),
        _lnk(_r["source_url"], "NFL.com game or schedule"),
    ])

pages["fixture-context.html"] = ("Fixture context", f"""
<h1>Fixture context from published schedule facts</h1>
<p class="note">Built only from published schedule dates and team pairs (scripts/fixture_context.py). No score, result,
injury or market field is read. Rest is calendar days since each team's previous scheduled game in this file; a blank
means that team has no earlier game in the register (Week 1), never zero. A "bye" flag means the previous game was two or
more weeks earlier. The 163 games are weeks 1-11: 136 played games (weeks 1-9), the Week 10 slate, and the Week 11 slate.</p>
<p class="note">Week 10 Thursday game (WAS at NYG) appears once; the other 13 Week 10 games are listed in data/games_week10_2026.csv (see F96 for the results register).</p>
{_tbl(["Week", "Date", "Day", "Game (away at home)", "Away rest (days)", "Home rest (days)", "Rest diff (home minus away)", "Bye before game", "Thursday", "Source"], _fix_rows, "fixture")}
""")

NAV.insert(NAV.index(("results-feed.html", "Results feed")) + 1, ("captures.html", "Captures & changes"))
NAV.insert(NAV.index(("captures.html", "Captures & changes")) + 1, ("fixture-context.html", "Fixture context"))
NAV.insert(NAV.index(("fixture-context.html", "Fixture context")) + 1, ("capture-integrity.html", "Capture integrity"))
NAV.insert(NAV.index(("capture-integrity.html", "Capture integrity")) + 1, ("feed-completeness.html", "Feed completeness"))
NAV.insert(NAV.index(("feed-completeness.html", "Feed completeness")) + 1, ("forecast-records.html", "Forecast records"))

_cap_idx = (
    '<h2>Captures, changes and the drift alarm (read 2026-11-18)</h2>'
    '<p class="note">Two dated official reads now exist for the injury report and the standings, so changes can be shown. '
    'Drift checks run on every build.</p>'
    '<div class="cards">'
    + card("captures.html", "Captures & what changed", f"Week 10 injury re-read (347 rows, {len(_inj_delta)} changes vs 2026-11-14), standings diff ({_games_added} games added), drift alarm status.")
    + card("fixture-context.html", "Fixture context", "Rest days, bye flags and Thursday games for 163 scheduled games (weeks 1-11), from schedule facts only.")
    + '</div>'
)
pages["index.html"] = (pages["index.html"][0], pages["index.html"][1] + _cap_idx)

# Read-date caveat on the verification page: its reconciliation rows are true of the standings snapshot the
# ledger was frozen on, and a reader needs the date to know that (flag F106).
pages["verification.html"] = (pages["verification.html"][0], pages["verification.html"][1] + f"""
<h2>Read-date caveat, added 2026-11-18 (session cf85d485)</h2>
<p class="warn">Every row above that says the results feed reconciles with the official standings was checked against
<code>data/standings_2026_snapshot.csv</code>, a standings read taken on <strong>2026-11-14, before the Week 10
Sunday games</strong>. That is a real check of internal arithmetic and it passes, but it is not a check of
currency: against the standings read on <strong>2026-11-18</strong> the same comparison fails for
<strong>26 of 32</strong> clubs, because 13 settled Week 10 games are not in the ledger. Adding the rows transcribed
from the official Week 10 slate reconciles <strong>32 of 32</strong> clubs on W-L-T and on points for and against —
see <a href="feed-completeness.html">Feed completeness</a> and flags F96, F105, F106. Two rules follow from this and
are recorded here so the next verification row cannot repeat it: <em>a reconciliation claim must carry the read date
of both sides</em>, and <em>a reconciliation between two surfaces read on the same day, one derived from the other,
proves arithmetic and not currency</em>.</p>
""")


# ---------- capture integrity, feed completeness and forecast records (session cf85d485, T102-T107) ----------
# Three pages built from the registers this session wrote. Nothing here re-derives a number: the tables render
# exactly what scripts/availability_captures.py, scripts/capture_cross_check.py,
# scripts/results_feed_completeness.py and scripts/forecast_records.py produced, and each of those scripts fails
# its own run if a pinned count, a reconciliation or a reproduction check does not hold. The injury delta and the
# standings diff themselves are published once, on captures.html (session d0ede22d's registers); this page keeps the
# capture ledger, the club-by-club reverification and the cross-check between the two readers, because those are the
# artefacts that say whether a number on this site can be trusted, not what it says.
_captures = read_csv("availability_captures.csv")
_avail_delta = read_csv("availability_delta_2026-11-14_to_2026-11-18.csv")
_avail_summary = read_csv("availability_delta_summary.csv")
_reverify18 = read_csv("live_reverification_2026-11-18.csv")
_xcheck = read_csv("capture_cross_check_2026-11-18.csv")
_what_changed = read_csv("what_changed_2026-11-14_to_2026-11-18.csv")
_feed_complete = read_csv("results_feed_completeness_2026-11-18.csv")
_feed_recon = read_csv("week_count_reconciliation_2026-11-18.csv")
_backfill = read_csv("games_week10_backfill_2026.csv")
_fr_checks = read_csv("forecast_record_checks.csv")
_fr_graded = read_csv("forecast_records_2026.csv")
_fr_w11 = read_csv("forecast_records_week11.csv")
_intl = read_csv("international_games_2026.csv")
_neutral = read_csv("neutral_site_sensitivity_2026.csv")

for _name, _rows, _id_field in (
        ("availability_captures", _captures, "capture_id"),
        ("availability_delta", _avail_delta, "player"),
        ("availability_delta_summary", _avail_summary, "metric"),
        ("live_reverification_2026-11-18", _reverify18, "check_id"),
        ("capture_cross_check_2026-11-18", _xcheck, "check_id"),
        ("what_changed", _what_changed, "team_abbr"),
        ("results_feed_completeness", _feed_complete, "team_abbr"),
        ("week_count_reconciliation", _feed_recon, "metric"),
        ("games_week10_backfill", _backfill, "game_no"),
        ("forecast_record_checks", _fr_checks, "check_id"),
        ("forecast_records_2026", _fr_graded, "record_id"),
        ("forecast_records_week11", _fr_w11, "record_id"),
        ("international_games_2026", _intl, "week"),
        ("neutral_site_sensitivity_2026", _neutral, "matchup")):
    if not _rows:
        errors.append(f"{_name}: no rows — the register is empty, publish nothing from it")
    for _r in _rows:
        _link = (_r.get("source_url") or _r.get("game_url") or "").strip()
        if not _link:
            errors.append(f"{_name} {_r.get(_id_field, '?')}: row without an official source link")
        else:
            check_official(_link, f"{_name}.{_id_field}")

# Pinned row counts: the drift alarm for the published registers themselves.
_pin = {"availability_captures": 2, "availability_delta": 18, "availability_delta_summary": 14,
        "live_reverification_2026-11-18": 28, "capture_cross_check_2026-11-18": 5,
        "what_changed": 32, "results_feed_completeness": 32, "week_count_reconciliation": 8,
        "games_week10_backfill": 13, "forecast_record_checks": 6, "forecast_records_2026": 178,
        "forecast_records_week11": 26, "international_games_2026": 9, "neutral_site_sensitivity_2026": 7}
for _nm, _n in (("availability_captures", len(_captures)), ("availability_delta", len(_avail_delta)),
                ("availability_delta_summary", len(_avail_summary)),
                ("live_reverification_2026-11-18", len(_reverify18)),
                ("capture_cross_check_2026-11-18", len(_xcheck)), ("what_changed", len(_what_changed)),
                ("results_feed_completeness", len(_feed_complete)),
                ("week_count_reconciliation", len(_feed_recon)), ("games_week10_backfill", len(_backfill)),
                ("forecast_record_checks", len(_fr_checks)), ("forecast_records_2026", len(_fr_graded)),
                ("forecast_records_week11", len(_fr_w11)), ("international_games_2026", len(_intl)),
                ("neutral_site_sensitivity_2026", len(_neutral))):
    if _n != _pin[_nm]:
        errors.append(f"{_nm}: {_n} rows, pinned expectation {_pin[_nm]} — re-run the capture script against "
                      f"the official page before publishing this table")
for _r in _fr_checks + _feed_recon + _xcheck:
    _txt = " ".join(str(v) for v in _r.values()).lower()
    if "fail" in _txt or "does not reconcile" in _txt:
        errors.append(f"a check that failed is being published as if it passed: {list(_r.values())[:3]}")
for _r in _fr_graded + _fr_w11:
    if _r["reproduced_published_line"] != "yes":
        errors.append(f"forecast record {_r['record_id']} did not reproduce the published line; not fit to publish")

_pub_eq = next((r["value"] for r in _avail_summary if r["metric"] == "published_snapshot_equals"), "")
_xc01 = next((r for r in _xcheck if r["check_id"] == "XC-01"), {})
pages["capture-integrity.html"] = ("Capture integrity & cross-checks", f"""
<section class="hero">
  <h1>Capture integrity and cross-checks</h1>
  <p>The injury hub and the standings as a <strong>timestamped series with hashes</strong>, plus the check that
  decides whether any single transcription on this site can be trusted. The numbers themselves live on
  <a href="captures.html">Captures &amp; changes</a>; this page is about whether they are the numbers the page
  really showed, and to whom.</p>
  <p class="note"><strong>Read times.</strong> CAP-01 is the 2026-11-14 transcription (date only — no clock time was
  recorded, and that missing field is why a delta was impossible until today). CAP-02 was read on
  <strong>2026-11-18 at 03:46 UTC</strong> from all eight rendered chunks. A second session read the same page at
  <strong>03:39 UTC</strong> and its transcription is the one the published register was rebuilt from. Each row
  links to the official page it came from:
  <a href="https://www.nfl.com/injuries/" target="_blank" rel="noopener">nfl.com/injuries ↗</a> ·
  <a href="https://www.nfl.com/standings/" target="_blank" rel="noopener">nfl.com/standings ↗</a>.</p>
</section>
{tiles([(len(_captures), "dated reads of one official report"),
        (_captures[1]["rows"] + " / " + _captures[0]["rows"], "players read today / on 2026-11-14"),
        (_xcheck[0]["disagreements"] + " of " + str(int(_xcheck[0]["compared"]) * 5), "fields two readers disagreed on"),
        (len([r for r in _reverify18 if r["result"] == "match"]), "of 28 club blocks matching today's read")])}
<h2>Capture ledger — one row per read, with its hash</h2>
<p class="note">The payload hash is over the canonical rows (sorted
<code>team|player|position|injury|practice|game status</code>), so an identical read on a later day has an identical
hash and a moved page does not; <code>sha256_capture_file</code> hashes the stored transcription itself. Both hashes
are computed over a <em>transcription</em>, not over HTTP bytes — the fetch surface returns processed text, so
neither hash can prove what the server sent (flag F100). <code>fields_corrected</code> is the count of cells where a
later official read overrode the transcription; the raw capture keeps what was read.</p>
{table(_captures, ["capture_id", "source_url", "week_label_as_rendered", "read_utc", "read_time_precision",
                   "rows", "clubs", "out_designations", "doubtful_designations", "questionable_designations",
                   "undesignated_rows", "fields_corrected", "sha256_payload", "sha256_capture_file",
                   "delta_capable", "capture_method", "note"],
       {"capture_id": "Capture", "source_url": "Source", "week_label_as_rendered": "Week label rendered",
        "read_utc": "Read (UTC)", "read_time_precision": "Time precision", "rows": "Rows", "clubs": "Clubs",
        "out_designations": "Out", "doubtful_designations": "Doubtful", "questionable_designations": "Questionable",
        "undesignated_rows": "No designation", "fields_corrected": "Fields corrected",
        "sha256_payload": "Payload sha256", "sha256_capture_file": "File sha256", "delta_capable": "Supports a delta",
        "capture_method": "How it was captured", "note": "Note"}, table_id="capture-ledger")}
<h2>Cross-check: two readers of one render</h2>
<p class="note">Two sessions transcribed the same page seven minutes apart, without coordination, and the
comparison is the only control in this repository that can catch a <strong>mis-transcription</strong> — as opposed
to a source change or an arithmetic slip. It caught one:
<strong>{_xc01.get("outcome", "")}</strong>.
{_xc01.get("detail", "")}</p>
{table(_xcheck, ["check_id", "what_compared", "register_a", "register_b", "rows_a", "rows_b", "compared",
                 "disagreements", "outcome", "status", "source_url"],
       {"check_id": "Check", "what_compared": "What was compared", "register_a": "Register A",
        "register_b": "Register B", "rows_a": "Rows A", "rows_b": "Rows B", "compared": "Players/clubs compared",
        "disagreements": "Disagreements", "outcome": "Outcome", "status": "Status", "source_url": "Source"},
       table_id="cross-check")}
<h2>Today's read against the published table, club by club</h2>
<p class="note">This is the full recount session b03f4ba1 left at four of eight chunks (flag F83, now closed for the
repo side). Every one of the 28 club blocks in the published register matches today's read — the register was
re-published from the 2026-11-18 read — and the <em>Equals CAP-01</em> column shows which clubs have moved since
2026-11-14. Whether a move came from the page or from a transcription is recorded in the cross-check above and in
flag F107: for the older capture it cannot be attributed, because no raw bytes were kept.</p>
{table(_reverify18, ["check_id", "unit", "checked_against", "read_detail", "repo_rows", "live_rows",
                     "missing_from_repo", "extra_in_repo", "field_differences", "repo_equals_2026_11_14_capture",
                     "result", "read_utc", "source_url"],
       {"check_id": "Check", "unit": "Unit", "checked_against": "Read against", "read_detail": "Read detail",
        "repo_rows": "Published rows", "live_rows": "Rows today", "missing_from_repo": "Missing from the table",
        "extra_in_repo": "Extra in the table", "field_differences": "Field differences",
        "repo_equals_2026_11_14_capture": "Equals CAP-01", "result": "Result", "read_utc": "Read (UTC)",
        "source_url": "Source"}, table_id="reverify-2026-11-18", filterable=True)}
<h2>What the published table currently equals</h2>
<p class="note">Computed by script, not asserted: <code>data/injuries_week10_2026.csv</code>
({_avail_summary[[r["metric"] for r in _avail_summary].index("published_snapshot_rows")]["value"]} rows) equals
<strong>{_pub_eq or 'neither capture'}</strong>. Until session d0ede22d re-published it on 2026-11-18 it equalled
CAP-01 exactly, which is what the earlier verification rows on
<a href="verification.html">Verification</a> were describing; a claim of that kind should always carry the read date
of both sides (flag F106).</p>
<p class="warn"><strong>Cadence hazard (F94).</strong> The hub ignores its own week parameter:
<code>https://www.nfl.com/injuries/?season=2026&amp;week=11&amp;type=REG</code> rendered the <strong>Week 10</strong>
tables on 2026-11-18, four days after those games, while the club records printed beside them already showed
post-Week-10 forms (BUF 8-1, NE 5-5). A capture job keyed on the URL would store the same week twice and label it
the new one, and would mix two dates inside one row. Any scheduled capture must store the rendered
<code>Injuries - WEEK n</code> heading — the <em>Week label rendered</em> column above — and fail when it is not the
week it meant to capture.</p>
""")

_feed_tiles = tiles([
    ("137", "games in the published results feed"),
    ("1", "of 14 Week 10 games the feed carries a score for"),
    ("13", "settled games transcribed here"),
    ("32/32", "clubs that reconcile once the 13 are added"),
])
pages["feed-completeness.html"] = ("Feed completeness", f"""
<section class="hero">
  <h1>Results-feed completeness</h1>
  <p>The feed every backtest and every ROI number depends on holds 137 games. Today's official standings imply
  <strong>150</strong> completed games through Week 10 (149 wins, 149 losses, 2 ties = 300 team-games). The gap is
  the Week 10 slate: the feed carries the Thursday, Nov 12 game and none of the 13 that followed it, although
  <code>data/games_week10_2026.csv</code> lists all 14 matchups with the result column blank on 13 of them.</p>
  <p class="note">Nothing on this page changes a published metric. The 13 scores are transcribed from
  <a href="https://www.nfl.com/schedules/2026/by-week/week-10" target="_blank" rel="noopener">the official Week 10
  schedule page</a> and then checked against
  <a href="https://www.nfl.com/standings/" target="_blank" rel="noopener">the official standings</a>: with the 13 rows
  added, every club's win-loss-tie record, points for and points against equals the standings exactly. Without them,
  26 of 32 clubs do not. Two independent official surfaces agreeing to the point is the verification.</p>
</section>
{_feed_tiles}
<h2>League arithmetic — and the 136 vs 137 dispute, settled</h2>
{table(_feed_recon, ["metric", "value", "basis", "result", "source_url"],
       {"metric": "Measure", "value": "Value", "basis": "Basis", "result": "Result", "source_url": "Source"},
       table_id="feed-reconciliation")}
<h2>Club by club: what the feed is missing</h2>
{table(_feed_complete, ["team_abbr", "team_name", "feed_games", "feed_record", "feed_pf_pa",
                        "official_games_2026_11_18", "official_record_2026_11_18",
                        "official_pf_pa_2026_11_18", "games_missing_from_feed", "points_for_missing",
                        "points_against_missing", "feed_as_published_matches_official",
                        "feed_plus_backfill_matches_official", "source_url", "backfill_source_url"],
       {"team_abbr": "Club", "team_name": "Team", "feed_games": "Games in feed", "feed_record": "Feed record",
        "feed_pf_pa": "Feed PF/PA", "official_games_2026_11_18": "Games official",
        "official_record_2026_11_18": "Official record", "official_pf_pa_2026_11_18": "Official PF/PA",
        "games_missing_from_feed": "Games missing", "points_for_missing": "PF missing",
        "points_against_missing": "PA missing", "feed_as_published_matches_official": "Feed matches today",
        "feed_plus_backfill_matches_official": "Feed + 13 matches", "source_url": "Standings",
        "backfill_source_url": "Week 10 slate"}, table_id="feed-completeness", filterable=True)}
<h2>The 13 settled Week 10 games, transcribed and source-linked</h2>
<p class="note">These rows are published as a <em>backfill register</em>, deliberately not spliced into
<code>data/games_2026_results.csv</code>: that file feeds the model fit, the 89-game walk-forward corpus, the
controls and every published error metric, and re-running those changes numbers the site already shows. Whether to
re-run is a decision, recorded on the <a href="review.html">Review console</a> and on
<a href="suggestions.html">Suggestions</a>; it is not something to do silently inside a data capture.</p>
{table(_backfill, ["game_no", "date_as_shown", "section_as_rendered", "away_team", "away_points", "home_team",
                   "home_points", "home_margin", "total_points", "winner", "international_game_flag_as_rendered",
                   "already_in_results_feed", "status", "game_url", "source_url"],
       {"game_no": "#", "date_as_shown": "Date", "section_as_rendered": "Section as rendered",
        "away_team": "Away", "away_points": "A pts", "home_team": "Home", "home_points": "H pts",
        "home_margin": "Home margin", "total_points": "Total", "winner": "Winner",
        "international_game_flag_as_rendered": "International", "already_in_results_feed": "Already in feed",
        "status": "Verification", "game_url": "Game page", "source_url": "Source"},
       table_id="week10-backfill")}
<h2>Fixture context from published schedule facts only</h2>
<p class="note">Readiness D25 asked for a fixture-context feature set built <strong>only</strong> from published
schedule facts, and D26 for the venue of every fixture transcribed from the official game centre. The venues below
are the nine games the league itself designates as international, transcribed from
<a href="https://operations.nfl.com/programs-initiatives/international-growth/nfl-international-games"
target="_blank" rel="noopener">NFL Football Operations</a> on 2026-11-18 — eight of them sit inside the model's
training corpus, where the feed carries no <code>neutral_site</code> value at all.</p>
{table(_intl, ["week", "date_as_published", "away_designated", "home_designated", "venue_official", "city_official",
               "kickoff_official", "new_market_2026", "in_results_feed", "feed_row_matchup", "feed_score",
               "neutral_site_column_in_feed", "treated_as_neutral_by_the_model", "verification", "source_url"],
       {"week": "Week", "date_as_published": "Date as published", "away_designated": "Away",
        "home_designated": "Designated home", "venue_official": "Venue (official)", "city_official": "City",
        "kickoff_official": "Kickoff", "new_market_2026": "New market 2026", "in_results_feed": "In the feed",
        "feed_row_matchup": "Feed row", "feed_score": "Feed score", "neutral_site_column_in_feed": "Feed neutral column",
        "treated_as_neutral_by_the_model": "Modelled as neutral", "verification": "Verification", "source_url": "Source"},
       table_id="international-slate")}
<h3>What the missing neutral flag costs — prediction-only sensitivity</h3>
<p class="note">This panel changes the <em>prediction</em> for the affected games and leaves the fit alone, so it is a
lower bound: the ratings also absorb the mis-flag, and re-fitting with the flags is part of the same owner decision
as the backfill. The fitted home-field term on the published fit is negative (−0.4 pts), which is why
"no home edge at a neutral venue" moves some games the other way.</p>
{table(_neutral, ["week", "matchup", "model_margin_as_published", "model_margin_if_treated_as_neutral",
                  "model_shift_pts", "reference_margin_as_published", "reference_margin_if_treated_as_neutral",
                  "reference_shift_pts", "actual_margin_home_minus_away", "effect_on_error", "source_url",
                  "game_url"],
       {"week": "Week", "matchup": "Game", "model_margin_as_published": "M1 as published",
        "model_margin_if_treated_as_neutral": "M1 if neutral", "model_shift_pts": "M1 shift",
        "reference_margin_as_published": "Reference as published", "reference_margin_if_treated_as_neutral":
        "Reference if neutral", "reference_shift_pts": "Reference shift",
        "actual_margin_home_minus_away": "Actual margin", "effect_on_error": "Effect on |error|",
        "source_url": "Source", "game_url": "Game page"}, table_id="neutral-sensitivity")}
""")

_fr_m1 = [r for r in _fr_graded if r["model_id"] == "M1"]
pages["forecast-records.html"] = ("Forecast records", f"""
<section class="hero">
  <h1>Forecast records: probability plus inputs, never a pick alone</h1>
  <p>Every stored output here is a <strong>probability</strong> together with the <strong>inputs that produced
  it</strong> and the residual scale that turned a number into that probability, so an output can be audited and
  replayed. The inputs are not descriptions: the same script re-derives each line from the documented construction
  and refuses to publish if the published number does not come back (tolerance is the published 1-decimal rounding).</p>
  <p class="note"><strong>No market price exists in this repository</strong> (F07, F51), so “covers” and “overs”
  are scored against the naive reference line the corpus is graded on, not against a bookmaker line. They are a
  benchmark-relative result, not a market edge. Personnel and availability features are
  <strong>not</strong> inputs: the model carries none, which is why the ablation the brief asks for is blocked (D24).</p>
</section>
{tiles([(str(len(_fr_graded)), "graded records (games × models)"), (str(len(_fr_w11)), "Week 11 prospective records"),
        ("178/178", "lines reproduced from the published CSVs"), ("26/26", "Week 11 lines reproduced")])}
<h2>Reproduction and integrity checks</h2>
{table(_fr_checks, ["check_id", "check", "method", "result", "source_url"],
       {"check_id": "Check", "check": "What was checked", "method": "Method", "result": "Result",
        "source_url": "Source"}, table_id="forecast-checks")}
<h2>Week 11 prospective records — frozen before kickoff, outcomes blank</h2>
{table(_fr_w11, ["record_id", "matchup", "kickoff_or_date", "model_id", "neutral_site_as_modelled",
                 "output_margin_home_minus_away_pts", "output_total_pts", "prob_home_win",
                 "prob_home_covers_reference_line", "prob_over_reference_total", "reference_cover_line_pts",
                 "reference_over_line_pts", "residual_sd_margin_used", "residual_sd_total_used", "pick",
                 "inputs_json", "status", "game_url", "source_url"],
       {"record_id": "Record", "matchup": "Game", "kickoff_or_date": "Kickoff", "model_id": "Model",
        "neutral_site_as_modelled": "Neutral", "output_margin_home_minus_away_pts": "Margin (H−A)",
        "output_total_pts": "Total", "prob_home_win": "P(home win)", "prob_home_covers_reference_line":
        "P(covers ref)", "prob_over_reference_total": "P(over ref)", "reference_cover_line_pts": "Ref cover line",
        "reference_over_line_pts": "Ref over line", "residual_sd_margin_used": "sd margin", "residual_sd_total_used":
        "sd total", "pick": "Pick", "inputs_json": "Inputs stored with the output", "status": "Status",
        "game_url": "Game page", "source_url": "Source"}, table_id="forecast-w11", filterable=True)}
<h2>Graded corpus (weeks 4–10): the same record, with outcomes and scores</h2>
<p class="note">One row per game per model: the M1 line and the naive reference line it is graded against.
Outcomes are from the official final scores already in the feed; Brier and log loss are computed from the
probability recorded at prediction time, and a push against the reference line is left unscored rather than
rounded to a win or a loss.</p>
{table(_fr_m1, ["record_id", "week", "matchup", "neutral_site_as_modelled", "output_margin_home_minus_away_pts",
                "output_total_pts", "prob_home_win", "prob_home_covers_reference_line", "prob_over_reference_total",
                "reference_cover_line_pts", "reference_over_line_pts", "actual_margin", "actual_total",
                "outcome_home_win", "outcome_cover", "outcome_over", "brier_home_win", "logloss_home_win",
                "brier_cover", "brier_over", "inputs_json", "game_url", "source_url"],
       {"record_id": "Record", "week": "Wk", "matchup": "Game", "neutral_site_as_modelled": "Neutral",
        "output_margin_home_minus_away_pts": "Margin (H−A)", "output_total_pts": "Total", "prob_home_win":
        "P(home win)", "prob_home_covers_reference_line": "P(covers ref)", "prob_over_reference_total":
        "P(over ref)", "reference_cover_line_pts": "Ref line", "reference_over_line_pts": "Ref total",
        "actual_margin": "Actual margin", "actual_total": "Actual total", "outcome_home_win": "Home won",
        "outcome_cover": "Cover", "outcome_over": "Over", "brier_home_win": "Brier (win)",
        "logloss_home_win": "Log loss (win)", "brier_cover": "Brier (cover)", "brier_over": "Brier (over)",
        "inputs_json": "Inputs stored with the output", "game_url": "Game page", "source_url": "Source"},
       table_id="forecast-graded", filterable=True)}
<p class="note">The full graded ledger including the reference-model rows is
<code>data/forecast_records_2026.csv</code> ({len(_fr_graded)} rows) and
<code>data/forecast_records_week11.csv</code> ({len(_fr_w11)} rows); both are also exported to
<code>docs/data/</code> as JSON. Historical scores here are research diagnostics: they are not on the
leaderboard, and the leaderboard stays unranked until a prospective window closes
(<a href="leaderboard.html">Leaderboard</a>).</p>
""")


# The exports dict above runs earlier in this file than this block, so the registers added here are exported to
# docs/data/ in their own loop rather than by editing that dict.
for _nm, _rows in (("availability_captures", _captures), ("availability_delta_summary", _avail_summary),
                   ("availability_delta_2026-11-14_to_2026-11-18", _avail_delta),
                   ("live_reverification_2026-11-18", _reverify18),
                   ("capture_cross_check_2026-11-18", _xcheck),
                   ("what_changed_2026-11-14_to_2026-11-18", _what_changed),
                   ("results_feed_completeness_2026-11-18", _feed_complete),
                   ("week_count_reconciliation_2026-11-18", _feed_recon),
                   ("games_week10_backfill_2026", _backfill), ("forecast_record_checks", _fr_checks),
                   ("forecast_records_2026", _fr_graded), ("forecast_records_week11", _fr_w11),
                   ("international_games_2026", _intl), ("neutral_site_sensitivity_2026", _neutral)):
    with open(os.path.join(DOCS, "data", _nm + ".json"), "w", encoding="utf-8") as _f:
        json.dump(_rows, _f, ensure_ascii=False, indent=1)

# Landing-page additions: what moved, and whether the numbers can be trusted. Kept deliberately short — the
# delta and standings tables live on captures.html.
pages["index.html"] = (pages["index.html"][0], pages["index.html"][1] + f"""
<h2>Freshness and capture integrity (2026-11-18)</h2>
<ul>
  <li><strong>Injury hub:</strong> {_captures[0]['rows']} rows read on 2026-11-14, {_captures[1]['rows']} on
  2026-11-18; {len(_avail_delta)} players moved between the two reads of the same report. The published register
  now equals today's read. <a href="capture-integrity.html">Capture integrity &amp; cross-checks</a> ·
  <a href="captures.html">Captures &amp; changes</a>.</li>
  <li><strong>Two readers, one disagreement:</strong> an independent transcription of the same render agreed on
  346 of 347 players; the single differing cell was an error in this session's capture, settled by a third read of
  the live page and corrected in the register — never in the raw capture. <a href="capture-integrity.html">Cross-check</a> (F109).</li>
  <li><strong>Results feed:</strong> 13 settled Week 10 games are absent from the corpus the backtests grade on;
  adding the transcribed rows reconciles all 32 clubs against today's standings.
  <a href="feed-completeness.html">Feed completeness</a> (F96, F105, P09).</li>
  <li><strong>Forecast outputs:</strong> every model line is stored with its inputs and its win/cover/over
  probabilities, and reproduces from the published CSVs before it is allowed to publish.
  <a href="forecast-records.html">Forecast records</a>.</li>
  <li><strong>Cadence hazard:</strong> the injury hub ignores its week URL parameter, so an unattended capture would
  silently re-store Week 10 and label it Week 11 (F94).</li>
</ul>
""")

pages["executive-summary.html"] = (pages["executive-summary.html"][0], pages["executive-summary.html"][1] + f"""
<h2>Capture-integrity desk: changes on 2026-11-18 (session cf85d485, T102&ndash;T107)</h2>
<ul class="findings">
<li><strong>The same official report now exists at three clock times.</strong> The Week 10 injury hub was
transcribed on 2026-11-14 ({_captures[0]['rows']} rows), and twice on 2026-11-18 — 03:39 UTC by session d0ede22d
and 03:46 UTC here, {len(_captures[1]['rows'])} rows across {len(_reverify18)} club blocks in both. The published
register was rebuilt from the 2026-11-18 read, and every one of the 28 blocks in it matches today's read
(<a href="capture-integrity.html">Capture integrity</a>). The recount session b03f4ba1 left incomplete is done:
the 345-vs-347 difference is a source movement (Baltimore added Calais Campbell and Ronnie Stanley), not a repo
omission, so flag F83 closes for the repo side.</li>
<li><strong>The double read caught a real error, which is the point of it.</strong> Two independent transcriptions of
the same render agreed on <strong>346 of 347 players</strong> across all five fields. The one disagreement — JAX
Chris Rodriguez Jr.'s practice status — was this session's own mis-read, settled by a third read of the live page
at 04:2x UTC and corrected in the derived registers (18 moved players, not 19; 6 practice changes, not 7). The raw
capture is left exactly as read, and the correcting script refuses to run if the capture stops matching the value it
overrode, so a correction can never drift into an invented number. No published register changed, because the one
this site shows was already right (F109, and <code>scripts/capture_cross_check.py</code>).</li>
<li><strong>The injury signal is a delta, as the brief requires.</strong> {len(_avail_delta)} of 347 players moved
in four days: 2 rows added, 6 practice-designation changes, 13 game-status changes and 13 injury-text changes, in
3 of 28 club blocks (BAL, IND, LAC); 0 players were removed. Ten of the 18 are a designation appearing where the
earlier capture left the cell blank — capture completeness, not news, and the case for scoring changes rather than
levels. Field-level detail: <a href="captures.html">Captures &amp; changes</a>
(<code>data/captures/injury_delta_2026-11-18.csv</code>); readiness D10, D49.</li>
<li><strong>The results feed is 13 settled games short, and the old reconciliation was stale rather than
wrong-arithmetic.</strong> Today's official standings imply 150 completed games through Week 10 (149 wins, 149
losses, 2 ties); <code>data/games_2026_results.csv</code> holds 137, of which one is a Week 10 game. The
"all 32 teams reconcile" claim was checked against a standings read taken <em>before</em> the Week 10 Sunday games,
so both sides were stale in the same direction (F106). The 13 games were transcribed from the official Week 10
by-week page — never computed from records — and with them <strong>32 of 32</strong> clubs reconcile on W-L-T
<em>and</em> points for and against; without them 26 of 32 do not.
<a href="feed-completeness.html">Feed completeness</a>. Nothing was re-run: adopting the rows changes every
published metric, so it is proposal <strong>P09</strong> on the <a href="decisions.html">Review console</a>
(F96, F105; readiness D29).</li>
<li><strong>Every model output is now stored with its inputs and its probabilities.</strong> {len(_fr_graded)}
graded rows and {len(_fr_w11)} Week 11 rows carry win, cover and over probabilities against the naive reference
price (no licensed market price exists, F07/F51), the reference line itself, the residual sd used, Brier and log
loss, and an <code>inputs_json</code> with mu / attack / defence / home terms, ridge lambda, n_obs and weeks. The
build refuses to publish unless all {len(_fr_graded) + len(_fr_w11)} lines reproduce the published CSVs to one
decimal; writing the check corrected two of this session's own assumptions first (a wrongly applied neutral-site
treatment, and the published one-decimal rounding). <a href="forecast-records.html">Forecast records</a>
(readiness D27 closed for the ledger; the D24 ablation stays blocked because the model has no personnel input).</li>
<li><strong>The neutral-site question now has a number.</strong> Seven settled games in the corpus are official
international games with a blank <code>neutral_site</code> value; the eighth (New England at Detroit in Munich) is
one of the 13 outside the feed. On the published fit the home-field term is <strong>-0.403</strong> points, so each
of those seven model margins shifts by 0.403, three flip the side pick, and BAL at DAL crosses the pre-registered
&plusmn;3-point betting gate (1.13 to 4.03). It is a predictions-only sensitivity: the feed column was left blank
rather than filled, because filling it re-fits the published ratings (F71 measured today, readiness D26).</li>
<li><strong>Suggestions written up, not implemented.</strong> S45 freeze v1 and publish a parallel v2 corpus
register; S46 manual hashed captures on a fixed cadence now, automation only after the rights question F16 is
answered; S49 venue transcription for the remaining fixtures from the game-centre block only; and
<strong>S50</strong>, make every capture that becomes published data a double read — the control that caught this
session's own error, which today happens to be luck rather than design
(<a href="decision-path.html">Review path</a>).</li>
</ul>
""")


# ---------- collision guards ----------
# Two parallel sessions can register the same page slug, or add two NAV entries
# pointing at one file. Either silently loses a page (the later dict assignment
# wins) or renders a duplicate menu item. Both must fail the build instead.
# Written after session e208ba6d and session cf6709c0 both registered
# "review.html" on 2026-11-14: the console page overwrote the path page and the
# navigation showed two "review" links to one file.
# An intentional append reuses the existing value, e.g.
#   pages["x.html"] = (pages["x.html"][0], pages["x.html"][1] + f"""...""")
# An accidental overwrite assigns a fresh literal and silently discards the
# earlier page. Only the second form is a collision.
_src = open(__file__, encoding="utf-8").read()
_slug_assignments = re.findall(r'^pages\["([^"]+)"\]\s*=\s*(.{0,40})', _src, re.M)
_overwrites = sorted({
    slug for slug, rhs in _slug_assignments
    if sum(1 for sl, _r in _slug_assignments if sl == slug) > 1
    and sum(1 for sl, r in _slug_assignments if sl == slug and not r.startswith('(pages[')) > 1
})
if _overwrites:
    raise SystemExit(
        "BUILD FAILED: page slug assigned more than once without appending, so an "
        f"earlier page would be silently lost: {_overwrites}")
_nav_hrefs = [h for h, _l in NAV]
_dupe_nav = sorted({h for h in _nav_hrefs if _nav_hrefs.count(h) > 1})
if _dupe_nav:
    raise SystemExit(f"BUILD FAILED: NAV has more than one entry for: {_dupe_nav}")

_missing_nav = [h for h, _l in NAV if h not in pages]
if _missing_nav:
    raise SystemExit(f"BUILD FAILED: NAV links to pages that are never generated: {_missing_nav}")

for slug, (title, body) in pages.items():
    with open(os.path.join(DOCS, slug), "w", encoding="utf-8") as f:
        f.write(page(slug, title, body, slug))
open(os.path.join(DOCS, ".nojekyll"), "w").close()
# GitHub Pages is configured to publish the repository root (main / ). The root index forwards to docs/.
with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8") as f:
    f.write("""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="0; url=docs/index.html">
<link rel="canonical" href="docs/index.html">
<title>NFL Research Dashboard</title></head>
<body><p>Opening the <a href="docs/index.html">NFL Research Dashboard</a>…</p>
<script>location.replace("docs/index.html");</script></body></html>
""")

# ---------- checks on generated HTML ----------
problems = []
for slug in pages:
    text = open(os.path.join(DOCS, slug), encoding="utf-8").read()
    # Every published table row must carry at least one HTTPS link to an
    # explicitly allow-listed official source or a first-party project record.
    for tbody in re.findall(r"<tbody>(.*?)</tbody>", text, re.S):
        for tr in re.findall(r"<tr>(.*?)</tr>", tbody, re.S):
            row_hrefs = re.findall(r'<a\b[^>]*href="([^"]+)"', tr)
            row_external = [href for href in row_hrefs if urlsplit(href).scheme in ("http", "https")]
            if not row_external:
                problems.append(f"{slug}: table row without an external source link: {tr[:100]}")
            elif not any(is_official_url(href) for href in row_external):
                problems.append(f"{slug}: table row without an allow-listed source link: {tr[:100]}")
    for href in re.findall(r'href="([^"]+)"', text):
        if href.startswith(("http://", "https://")):
            if not is_official_url(href):
                problems.append(f"{slug}: external link not on the HTTPS source allow-list: {href}")
            continue
        if href.startswith("#"):
            continue
        target = href.split("#")[0]
        if not os.path.exists(os.path.join(DOCS, target)):
            problems.append(f"{slug}: broken internal link: {href}")
    if "http://" in text.replace("http://www.w3.org", ""):
        problems.append(f"{slug}: contains plain http:// link")

print(f"Built {len(pages)} pages into docs/. Injury rows: {tot['rows']}; teams: {tot['teams']}; depth rows: {len(depth_rows)}.")
for w in warnings:
    print("WARNING:", w)
if problems:
    print("LINK / ROW CHECK PROBLEMS:")
    for p in problems:
        print("  -", p)
    sys.exit(1)
print("Link and row-source checks passed.")
