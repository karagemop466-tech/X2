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
}
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
    """Read a CSV and refuse anything that is not a clean rectangle.

    A mis-quoted cell silently shifts every later column, which is how a
    truncated or re-split row hides. We fail loudly instead.
    """
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        expected = reader.fieldnames or []
        rows = []
        for lineno, row in enumerate(reader, start=2):
            if None in row or "" in row:
                raise SystemExit(
                    f"{name}:{lineno}: ragged row — {len(expected)} columns expected, "
                    f"extra cell(s): {row.get(None)!r}")
            if any(v is None for v in row.values()):
                raise SystemExit(f"{name}:{lineno}: missing cell(s) in row")
            rows.append(row)
        return rows

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
gate_results = read_csv("gate_results.csv")
correlations = read_csv("correlations_computed.csv")
parlays = read_csv("parlay_analysis.csv")
# ---- session c125b2f7: market tables (generated by scripts/markets.py) ----
price_snapshots = read_csv("price_snapshots.csv")
line_comparison = read_csv("line_comparison_week11.csv")
signal_staking = read_csv("strategy_signal_staking.csv")
demotion_gate = read_csv("demotion_gate.csv")
# ---- session ca1ea224: the extended price-snapshot store (Week 11 + out-of-sample) ----
price_snapshots_extended = read_csv("price_snapshots_extended.csv")
with open(os.path.join(DATA, "model_summary.json"), encoding="utf-8") as f:
    ms = json.load(f)
# ---- session 10a76288: a second, independent implementation used to cross-check the one above ----
season_games = read_csv("season_games_2026.csv")
standings = read_csv("standings_2026_week10.csv")
scorecard = read_csv("strategy_scorecard_2026.csv")
model_holdout = read_csv("model_holdout_2026.csv")
availability = read_csv("confirmed_availability_week10_2026.csv")
verification_rows = read_csv("verification_report.csv")
decision_chain = read_csv("decision-chain.csv")
# ---- session 25d6114f registers (new, non-overlapping files) ----
verification = read_csv("verification_week10_2026.csv")
starters = read_csv("starters_gamebook_2026_reg_10.csv")
line_signals = read_csv("line_signals.csv")
engine_gates = read_csv("skill_engine_gates.csv")
luck_tests = read_csv("luck_tests.csv")
corr_framework = read_csv("correlation_framework.csv")
lb_rules = read_csv("leaderboard_rules.csv")
depth_def = read_csv("depth_deficiency.csv")
decisions = read_csv("decision_questions.csv")
sug_register = read_csv("suggestions_register.csv")
repo_review = read_csv("repo_review.csv")
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
# Empty-state row only: do not imply a strategy has results or an approved reward.
leaderboard_status = [{
    "rank": "—",
    "strategy": "No qualified strategy",
    "skill_score": "",
    "eligible_sample": "",
    "uncertainty": "",
    "validation_status": "Not tested — no strategy has passed the gates",
    "top_performance_reward": "Not defined; disabled pending legal, rights and validation review",
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

# Registers that use source_url as their citation column (session 25d6114f).
for label, rows, id_field in (
    ("depth_deficiency", depth_def, "team_abbr"),
    ("starters", starters, "player"),
    ("verification", verification, "check_id"),
    ("line_signals", line_signals, "signal_id"),
    ("engine_gates", engine_gates, "gate_id"),
    ("luck_tests", luck_tests, "test_id"),
    ("correlation_framework", corr_framework, "pair_id"),
    ("repo_review", repo_review, "review_id"),
):
    for row in rows:
        if not row["source_url"].strip():
            errors.append(f"{label} {row[id_field]}: table row without source_url")
        check_official(row["source_url"], f"{label}.source_url")

# A verification row may never claim a check it did not run.
for row in verification:
    if not row["what_was_checked"].strip() or not row["result"].strip():
        errors.append(f"verification {row['check_id']}: missing check description or result")
    if row["result"].startswith("FAIL"):
        errors.append(f"verification {row['check_id']}: recorded FAIL — the snapshot must be "
                      f"reconciled before publishing")
if len(verification) < 80:
    warnings.append(f"verification ledger has only {len(verification)} rows")

if len(inj) != 345:
    warnings.append(f"injury row count is {len(inj)}; expected 345 for the Week 10 snapshot")
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
            "starter_backup_status": "UNVERIFIED — no official depth chart collected",
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
    "decision_chain": decision_chain, "decision_questions": decisions, "suggestion_review": sugg_review,
    "games_2026_results": results_games, "schedule_week11_2026": week11_sched,
    "model_lines_week11": model_lines, "model_ratings": model_ratings,
    "model_backtest": model_backtest, "model_bets": model_bets,
    "strategy_leaderboard": leaderboard, "gate_results": gate_results,
    "correlations_computed": correlations, "parlay_analysis": parlays,
    "price_snapshots": price_snapshots, "price_snapshots_extended": price_snapshots_extended,
    "model_summary": ms,
    "verification_week10_2026": verification, "starters_gamebook_2026_reg_10": starters,
    "line_signals": line_signals, "skill_engine_gates": engine_gates, "luck_tests": luck_tests,
    "correlation_framework": corr_framework, "leaderboard_rules": lb_rules,
    "depth_deficiency": depth_def,
    "suggestions_register": sug_register, "repo_review": repo_review,
}
for name, data in exports.items():
    with open(os.path.join(DOCS, "data", name + ".json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

# ---------- HTML helpers ----------
LINK_LABEL = {"source_url": "Source ↗", "player_url": "Player page ↗", "url": "Link ↗",
              "evidence_url": "Evidence ↗", "game_url": "Game page ↗"}


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
    ("backtest.html", "Backtest"),
    ("leaderboard.html", "Leaderboard"),
    ("validation-gates.html", "Validation gates"),
    ("markets.html", "Market tables"),
    ("correlations.html", "Correlations"),
    ("parlays.html", "Parlays"),
    ("results.html", "Season results"),
    ("injuries.html", "Injuries"),
    ("games.html", "Games"),
    ("starters.html", "Starters &amp; depth"),
    ("depth-analysis.html", "Unit exposure"),
    ("depth-deficiency.html", "Deficiency tracking"),
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
    ("verification.html", "Verification"),
    ("repo-review.html", "Repo review"),
    ("cross-check.html", "Independent cross-check"),
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
  <p class="note">Snapshot: <a href="https://www.nfl.com/injuries/" target="_blank" rel="noopener">NFL.com Week 10, 2026 injury report</a> and the <a href="https://www.nfl.com/schedules/2026/by-week/week-10" target="_blank" rel="noopener">official Week 10 schedule</a> (read {AS_OF}).</p>
  <p class="note"><strong>Verification status:</strong> all {tot['rows']} injury rows and all {tot['games']} Week 10 games were independently re-verified row by row against the official NFL.com pages on {AS_OF}, with no discrepancies found. See the <a href="verification.html">Verification record</a>.</p>
  <p class="note"><strong>Critical data-rights gate:</strong> NFL.com terms prohibit systematic retrieval to compile a database absent express prior written consent. No permission is recorded here for the published injury snapshot. Do not expand or automate this use pending review (Flag F16). <a href="https://support.nfl.com/hc/en-us/articles/35869743904916-NFL-com-Terms-and-Conditions" target="_blank" rel="noopener">NFL.com terms ↗</a> · <a href="flagged.html">Flagged for Review</a>.</p>
</section>
{tiles([(ms['games_transcribed'], 'games transcribed and verified'), (ms['out_of_sample_games'], 'out-of-sample games graded'),
        (ms['mae_improvement'], 'points of forecast gain vs the naive line'), (ms['strategies_tested'], 'strategies tested'),
        (tot['rows'], 'players listed (Week 10)'), (ms['week11_games'], 'Week 11 lines originated')])}
<h2>Start here</h2>
<div class="cards">
{card('executive-summary.html', 'Executive summary', 'The key findings, what is verified, and what is not yet known.')}
{card('decision-path.html', 'Decision path', 'The ten questions that must be answered, in order, before any dependent choice is made. Start here.')}
{card('decisions.html', 'Decision gates', 'Every question that must be answered before a path is chosen, with the choice you will face.')}
{card('suggestions.html', 'Suggestions', 'Recommendations with options; nothing is implemented without your choice.')}
</div>
<h2>Data and evidence</h2>
<div class="cards">
{card('injuries.html', 'Injuries', 'All 345 Week 10 injury report rows with source links, plus NFL.com news headlines.')}
{card('games.html', 'Games', 'The 14 Week 10 matchups with records and broadcast windows, all from NFL.com.')}
{card('starters.html', 'Starters and depth', 'Official gamebook starter identity, and why a 1st/2nd/3rd string rank cannot be official.')}
{card('depth-analysis.html', 'Unit exposure', 'Out and Doubtful players by unit, with replacement depth left blank.')}
{card('verification.html', 'Verification', 'The line-by-line re-check: 345 of 345 rows match, one official conflict flagged.')}
{card('repo-review.html', 'Repo review', 'Every file reviewed against a source; irregularities flagged, not hidden.')}
{card('results.html', 'Season results', 'All 137 transcribed 2026 games, each reconciled against the official standings.')}
</div>
<h2>Lines, markets and skill</h2>
<div class="cards">
{card('model-lines.html', 'Model & Week 11 lines', 'Our own originated spreads, totals and moneylines for Week 11 — originated side first, then total, then moneyline — with the fair line, market line and difference as separate columns.')}
{card('price-snapshots.html', 'Price snapshots', 'The price-snapshot store: opening and closing numbers for every market originated. Values are blank and flagged — no licensed odds feed exists (F51).')}
{card('markets.html', 'Market tables', 'Price-snapshot store (opening and closing, blank until a source exists), fair vs market lines, signal vs staking, and the demotion gate.')}
{card('backtest.html', 'Backtest', 'All 89 walk-forward out-of-sample predictions against what actually happened, game by game.')}
{card('leaderboard.html', 'Leaderboard', 'Seven strategies ranked on forecast skill, with signal separated from staking, gates, uncertainty and required sample sizes.')}
{card('validation-gates.html', 'Validation gates', 'Nine gates, what each one tests, and which strategies pass — including the demotion gate that sends a live strategy back to paper.')}
{card('validation.html', 'Skill engine', 'The validation gates a strategy must pass before it can be called valid.')}
{card('signals.html', 'Signals', 'Signal definitions for single bets, parlays and player-prop combos.')}
{card('anti-luck.html', 'Anti-luck', 'Bootstrap intervals, multiplicity control and held-out blocks: how a lucky run is kept off the board.')}
{card('correlation.html', 'Correlation plan', 'The measurement plan for every dependent leg pair, with all values blank.')}
{card('correlations.html', 'Correlations', 'Nine correlation values computed from official results, with intervals and p-values.')}
{card('parlays.html', 'Parlays', 'Same-game two-leg tickets: observed joint hit rate against the independence shortcut.')}
</div>
<h2>Reference</h2>
<div class="cards">
{card('strategy-lab.html', 'Strategy lab', 'The original framework: hypotheses, gates and market families.')}
{card('questions.html', 'Questions', 'What we know, what we do not, and how to find the missing information.')}
{card('requirements.html', 'Requirements', 'Each requirement from the brief with its current status.')}
{card('suggestions.html', 'Suggestions', 'Review proposals before future implementation, with a recommended path and the gate that blocks each one.')}
{card('verification.html', 'Verification', 'What was checked line by line, against which official page, and what the result was.')}
{card('flagged.html', 'Flagged for review', 'Irregularities, unverified items and missing official data, each with a source link.')}
{card('sources.html', 'Sources', 'Every official source used, with what it supports.')}
{card('cross-check.html', 'Independent cross-check', 'A second independent transcription and model compared against the first: what agrees, and the one thing that does not.')}
{card('depth-deficiency.html', 'Deficiency tracking', 'Unit exposure by side of ball, and officially named starters and replacements.')}
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
<li><strong>Quarterbacks.</strong> The news headlines on the same page report Lamar Jackson (Ravens) and Malik Willis (Dolphins) on injured reserve, and Sam Darnold (Seahawks) ruled out for Week 10. Their replacements are not verified in depth-chart data (see Flag F06).</li>
<li><strong>Strategy research.</strong> Seven pre-registered strategies have been graded walk-forward on official 2026 results. Two independent implementations disagree on qualification (F42), so <strong>no reward tier is assigned</strong>. Rankings describe forecast signal, not profit; no odds feed or staking result is available (Flags F32, F33, F43).</li>
<li><strong>Originated lines (new).</strong> A ridge attack/defence model fitted on the {ms['games_transcribed']} official 2026 results now produces our own spreads and totals for all {ms['week11_games']} Week 11 games. Out of sample it is {ms['mae_improvement']} points closer to the actual margin per game than a naive published reference line (mean absolute error {ms['mae_m1']} vs {ms['mae_reference']} points over {ms['out_of_sample_games']} games, 95% bootstrap interval 0.76 to 2.74 points). The calibration slope is {ms['calibration_slope']} (SE {ms['calibration_slope_se']}), so the lines are neither over-shy nor over-confident.</li>
<li><strong>Origination order and fair/market/difference (new).</strong> Each market is originated in a fixed order — side first, then total, then moneyline — and the model's <em>fair line</em>, the <em>market line</em> and the <em>difference</em> are published as separate columns on the <a href="model-lines.html">Model &amp; Week 11 lines</a> page. The market columns are blank: no licensed odds feed exists, so no market price can be confirmed from an official source (Flags F07, F31).</li>
<li><strong>Price-snapshot store (new).</strong> A store now records the opening and closing number for every market this project originates — {ms['price_snapshot_rows']} rows covering the Week 11 slate and the out-of-sample window, side, total and moneyline. No official source publishes opening or closing NFL market numbers, so every opening and closing value is blank and flagged rather than inferred (Flags F07, F51). The schema is in place for a rights-cleared odds feed to fill it.</li>
<li><strong>Signal separated from staking (new).</strong> The <a href="leaderboard.html">leaderboard</a> now reads in two separate blocks: a signal block (forecast skill, intervals, significance) and a staking block (plan and return). Staking return is blank because no prices exist, so a lucky staking run cannot mask a weak signal (Flags F07, F32).</li>
<li><strong>Demotion gate (new).</strong> A demotion gate (G9) is defined and armed: a live strategy is sent back to paper the moment any of G1–G8 fails, the skill interval includes zero, or the mean edge turns negative. No strategy is live today — the qualification is disputed by the independent cross-check (F42) and wagering and rewards stay disabled — so every strategy is Paper (Flags F17, F42).</li>
<li><strong>Leaderboard (new).</strong> {ms['strategies_tested']} strategies were graded walk-forward. The base model's gate counts are shown as evidence, but independent validation disagrees on qualification (F42); no leaderboard row receives a reward tier, and no reward is enabled (F43). The totals strategy shows no measured skill and the parlay strategy fails on sample size. None has enough observations for a decisive test (F33).</li>
<li><strong>What the leaderboard does not prove.</strong> Bets are graded against a naive reference line, because this project has no licensed odds feed. Beating a noisy benchmark is easier than beating a sportsbook price, so no hit rate here may be read as market return (Flag F32).</li>
<li><strong>Results verified line by line.</strong> Every one of the {ms['games_transcribed']} transcribed games was reconciled against the official standings: all 32 teams match exactly on wins, losses, ties, points for and points against.</li>
<li><strong>Data rights.</strong> NFL.com terms prohibit systematic retrieval to compile a database absent express prior written consent. No permission is recorded here for the published injury snapshot; do not expand or automate this use pending review (Flag F16).</li>
<li><strong>Legal.</strong> Government of Japan guidance says online sports betting accessed from Japan is gambling and prohibited there; this is Japan-specific and does not decide contest or reward mechanics. No legal opinion is provided (Flag F09).</li>
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
<li>Starter vs backup order at every position (no official pregame depth chart collected; Flags F06, F31, DQ-06).</li>
<li>Betting lines, odds, prop prices and parlay prices (no official odds source; Flag F07).</li>
<li>Player statistics, player-prop outcomes and prop prices (no official source collected; Flag F31).</li>
<li>Market prices, closing lines, closing-line value and any return on investment (no licensed odds feed; Flags F07, F32).</li>
<li>Any correlation coefficient (no paired settled legs exist; the correlation plan C01–C10 is blank).</li>
<li>Injury-designation probabilities (NFL.com publishes labels, not probabilities; Flag F04).</li>
<li>Any strategy score (no strategy has been tested or entered on the leaderboard).</li>
<li>Any reward (nothing is defined, funded or legally reviewed; Flags F09, F16, F17).</li>
</ul>
<h2>Team exposure (Week 10, from the report)</h2>
{table(team_summary, ['team','listed','out','doubtful','questionable','offense_out_or_doubtful','defense_out_or_doubtful','special_teams_out_or_doubtful','source_url'],
   {'team':'Team','listed':'Listed','out':'Out','doubtful':'Doubtful','questionable':'Questionable','offense_out_or_doubtful':'Offense Out/Doubtful','defense_out_or_doubtful':'Defense Out/Doubtful','special_teams_out_or_doubtful':'ST Out/Doubtful','source_url':'Source'})}
<h2>How a decision should be made from this</h2>
<ol>
<li>Use the <a href="model-lines.html">originated lines</a> as a forecast, not as a price. A forecast says what the model expects; a price says what it costs. Only the first exists here.</li>
<li>Judge strategies on the <a href="leaderboard.html">skill column</a> (points of forecast gain), not on the hit-rate column, which is measured against a naive benchmark.</li>
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
<p class="note">This page holds the qualitative framework. <strong>The quantitative results now live on their own pages:</strong> <a href="leaderboard.html">Leaderboard</a>, <a href="validation-gates.html">Validation gates</a>, <a href="correlations.html">Correlations</a>, <a href="parlays.html">Parlays</a> and <a href="backtest.html">Backtest</a>, all graded walk-forward on {ms['out_of_sample_games']} out-of-sample games. The research framework taken over in T52 lives on <a href="signals.html">Signals</a>, <a href="validation.html">Skill engine</a>, <a href="anti-luck.html">Anti-luck</a>, <a href="correlation.html">Correlation plan</a>, <a href="starters.html">Starters &amp; depth</a> and <a href="repo-review.html">Repo review</a>.
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
<h2>Leaderboard — now graded, on the Leaderboard page</h2>
<p class="note">{ms['strategies_tested']} strategies have been graded walk-forward out of sample. One implementation reports {ms['measured_gate_qualified_strategies']} passing its core gates; the independent cross-check disagrees after multiple-comparison adjustment (F42). Per-gate results remain visible, but no reward tier is assigned or enabled. Full figures and uncertainty intervals are on the <a href="leaderboard.html">Leaderboard</a> page. Jurisdiction, data rights and legal review also remain unresolved.</p>
{table(leaderboard_status, ['rank','strategy','skill_score','eligible_sample','uncertainty','validation_status','top_performance_reward','source_url'],
       {'rank':'Rank','strategy':'Strategy','skill_score':'Performance score','eligible_sample':'Eligible sample','uncertainty':'Uncertainty','validation_status':'Validation status','top_performance_reward':'Top-performance reward','source_url':'Project record'})}
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
<tr><td>Injury row count</td><td>Re-read the official Week 10 report in full (8 chunks) and recounted players per team section independently of the stored file.</td><td class="ok">Match: 345 rows across 28 teams, equal to the stored row count.</td><td><a href="https://www.nfl.com/injuries/" target="_blank" rel="noopener">NFL injury report</a></td></tr>
<tr><td>Injury field values</td><td>Compared every player name, position, injury text, practice status and game status for all 28 team sections against the stored CSV.</td><td class="ok">No discrepancies found. Performed independently of session 30beeb55's T15 check, which also found none; together these close the F10 spot-check request.</td><td><a href="https://www.nfl.com/injuries/" target="_blank" rel="noopener">NFL injury report</a></td></tr>
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
<h2>Standing limitations</h2>
<ul>
<li><strong>Single reviewer.</strong> This pass was performed independently of session 30beeb55's separate T15 check, and both found no discrepancies. Two independent passes are the strongest control the manual-transcription limitation allows, but neither is an automated diff (F10, F20).</li>
<li><strong>Live pages move.</strong> Every "verified" statement is true of the page as read on {AS_OF}. The injury page shows no last-updated timestamp (F13).</li>
<li><strong>Rights are not verification.</strong> Confirming a value matches NFL.com does not grant permission to republish it in bulk (F16).</li>
<li><strong>Blank is deliberate.</strong> A dash means the official source did not supply a value, or no official source was found. It is never an inferred estimate.</li>
</ul>

<h2>Snapshot check register — {len(verification_ledger)} checks (taken over from session 25d6114f, T52)</h2>
<p class="note">A reproducible field-by-field ledger: every committed value beside the official value, with the
result and a source link. Reproduce with <code>python3 scripts/verify_snapshot.py</code>. Residual limitation: the
ledger's transcription and the snapshot were made in the same session, so a shared misreading would not be detected
(<a href="flagged.html">Flag F59</a>); two further independent passes (sessions 30beeb55 and 7c9eb69a) reached the
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
(SE {ms['calibration_slope_se']}).</p>
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
that week. This is enforced in code, not by hand.</li>
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
inferred (Flags F07, F51). The store is built so that, the moment a rights-cleared official odds source is
connected, the numbers drop straight into the existing columns. The <em>fair line</em> column is the model's own
originated number and is first-party computed; it is not a market price.</p>
{tiles([(len(price_snapshots_extended), 'snapshot rows (extended store)'), (len(price_snapshots), 'Week 11 rows (c125b2f7 store)'),
        (ms['week11_games'], 'Week 11 games'), (ms['out_of_sample_games'], 'out-of-sample games')])}
<h2>How to read the columns</h2>
<ul class="findings">
<li><strong>fair_line</strong> — the model's originated number for that market (side spread, total, or fair
moneyline). First-party computed from official results; not a market price.</li>
<li><strong>opening_number / closing_number</strong> — the market's opening and closing numbers. Blank by design:
no official source confirms them (F07, F51).</li>
<li><strong>opening_verified / closing_verified</strong> — No for every row, because no value is filled.</li>
<li><strong>status</strong> — carries the flag text on every row so the blank is never read as an omission.</li>
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

# ---------- leaderboard ----------
pages["leaderboard.html"] = ("Leaderboard", f"""
<h1>Strategy leaderboard</h1>
<p class="note"><strong>How to read this.</strong> <strong>Signal and staking are separated on purpose.</strong>
The <em>signal</em> block ranks strategies on forecast skill: how many points per game closer the strategy's
forecast landed to the actual result than the naive reference line, across all {ms['out_of_sample_games']}
out-of-sample games. It is a forecast-accuracy measure, not profit. The <em>staking</em> block records the staking
plan and its return — which is blank, because no licensed odds feed exists, so no staking return can be computed
(Flags F07, F32). A lucky staking run therefore cannot mask a weak signal: the two are read separately. The
hit rate and edge columns describe a paper record against the naive reference line and <strong>must not be read
as a market result</strong> (Flag F32). Required sample size is how many bets the strategy would need, at the
effect size it observed, for an 80%-power test; every strategy on this board is currently short. <strong>No reward
tier is assigned to any row:</strong> independent validation disagrees on qualification (F42), so ranks describe
forecast signal only (F43).</p>
{tiles([(ms['strategies_tested'], 'strategies tested'), (ms['measured_gate_qualified_strategies'], 'gate-qualified'),
        (ms['live_strategies'], 'live strategies'), (ms['out_of_sample_games'], 'out-of-sample games')])}
<h2>Signal — ranked by forecast skill</h2>
{table(leaderboard, ['rank','strategy_id','strategy','market','status','demotion_safe','skill_score_mae_improvement_pts','skill_ci_low','skill_ci_high','skill_p_permutation','q_bh_fdr','mae_model','mae_reference','oos_games','min_n_for_80pct_power','sample_shortfall','gates_passed','gates_failed','reward_tier','source_url'],
       {'rank':'#','strategy_id':'ID','strategy':'Strategy','market':'Market','status':'Status','demotion_safe':'Demotion-safe','skill_score_mae_improvement_pts':'Skill (pts)','skill_ci_low':'CI low','skill_ci_high':'CI high','skill_p_permutation':'Permutation p','q_bh_fdr':'BH q','mae_model':'MAE model','mae_reference':'MAE reference','oos_games':'OOS games','min_n_for_80pct_power':'Bets needed (80% power)','sample_shortfall':'Short by','gates_passed':'Gates','gates_failed':'Failed','reward_tier':'Tier (none assigned)','source_url':'Source'})}
<h2>Staking — separate from signal</h2>
<p class="note">Staking returns depend on prices, which this project does not hold. The plan is published for
completeness; the return columns are blank and flagged, not estimated.</p>
{table(leaderboard, ['strategy_id','strategy','status','staking_plan','staking_units_wagered','staking_roi_pct','staking_note','source_url'],
       {'strategy_id':'ID','strategy':'Strategy','status':'Status','staking_plan':'Staking plan','staking_units_wagered':'Units wagered','staking_roi_pct':'Staking ROI %','staking_note':'Staking note','source_url':'Source'})}
<h2>Full detail</h2>
{search_box('lb-table')}
{table(leaderboard, ['strategy_id','strategy','mae_model','mae_reference','oos_games','wins','losses','hit_rate_vs_reference','mean_edge_points','edge_ci_low','edge_ci_high','sd_edge_points','p_binomial','p_permutation_bets','reward_status','source_url'],
       {'strategy_id':'ID','strategy':'Strategy','mae_model':'MAE model','mae_reference':'MAE reference','oos_games':'OOS games','wins':'Wins','losses':'Losses','hit_rate_vs_reference':'Hit rate','mean_edge_points':'Mean edge (pts)','edge_ci_low':'Edge CI low','edge_ci_high':'Edge CI high','sd_edge_points':'Edge SD','p_binomial':'Binomial p','p_permutation_bets':'Permutation p (bets)','reward_status':'Reward status','source_url':'Source'},
       table_id='lb-table', filterable=True)}
<h2>Demotion gate — live back to paper</h2>
<p class="note">The demotion gate (G9) is armed. A strategy that is <em>live</em> is demoted back to
<em>paper</em> the moment any of G1–G8 fails on the latest window, or its skill 95% interval includes zero, or its
mean edge turns negative. <strong>No strategy is live today:</strong> the qualification is disputed by the
independent cross-check (Flag F42), the gate cut-offs await owner approval (F17) and wagering and rewards stay
disabled (F09, F16, F19). Every strategy is therefore <em>Paper</em>; the demotion-safe column shows which ones
would keep (or earn) live status once the gates are approved and the disagreement resolved.</p>
<h2>Reward structure — proposal only; no current tier assignments</h2>
<p class="note"><strong>F42 blocks assigning any reward tier:</strong> the independent qualification analysis disagrees, and thresholds remain unapproved (F17). The labels below are only a historical design proposal, not current outcomes.</p>
<ul class="findings">
<li><strong>Tier 1 concept</strong> — would require all eight gates and a resolved independent qualification test.</li>
<li><strong>Tier 2 concept</strong> — proposed gate subset only; not assigned or enabled.</li>
<li><strong>Tier 3 concept</strong> — proposed tracking only; not assigned or enabled.</li>
<li><strong>Current state</strong> — zero active reward tiers; no reward is offered or paid.</li>
</ul>
<p class="note">The competition is between strategies inside this repository, not between people, and no reward
has monetary value. Any reward, entry fee, referral or wager mechanic stays disabled pending jurisdiction
confirmation and qualified legal review (Flags F09, F19) and data-rights clearance (F16). Approve, amend or reject
these tiers on the <a href="suggestions.html">Suggestions</a> page; nothing here has been implemented on the
basis of a suggestion.</p>

<h2>Leaderboard rules — LB01 to LB12 (taken over from session 25d6114f, T52)</h2>
<p class="note">Pre-declared ranking rules written before any entry exists, so that when entries do arrive they
cannot quietly reward luck. <strong>No entry is eligible and no reward is enabled</strong>: eligibility, jurisdiction,
data rights and legal review remain unresolved (F17, F42, F09, F19, F16).</p>
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
outputs derived from them. Nothing is assumed or copied. Intervals are Fisher z intervals; p-values are two-sided. Under the owner
rule only correlations with official inputs qualify: C03, C04, C06 and C08 (see the correlation audit on the <a href="verification.html">Verification</a> page).
C01, C02, C05, C07 and C09 are model diagnostics (Flags F48, F49). The C09 row still shows the earlier interval; the corrected interval
(0.335 to 1.435) is requested and not yet applied (Flag F48). No player-prop correlation can be computed because no player-prop outcomes are held (Flag F31).</p>
{table(correlations, ['corr_id','question','value','ci_low','ci_high','p_value','sample_n','interpretation','source_url'],
       {'corr_id':'ID','question':'Question','value':'Value','ci_low':'CI low','ci_high':'CI high','p_value':'p','sample_n':'n','interpretation':'What it means','source_url':'Source'})}
<h2>What the values say</h2>
<ul class="findings">
<li>The model's margin forecast is genuinely associated with the actual margin (r = 0.321, p = 0.002), and more
so than the naive reference line (r = 0.274, p = 0.009). That gap is the skill the leaderboard measures.</li>
<li>Game totals are close to unpredictable with the inputs used here: predicted totals correlate r = 0.092
(p = 0.39) with actual totals, and the totals strategy shows no accuracy gain at all.</li>
<li>Within a game, the two teams' scores do not co-move (r = 0.042) and blowouts are not associated with higher
totals (r = 0.021). Both matter for parlay pricing, and both are essentially zero in this sample.</li>
<li>Last week's margin barely predicts this week's (r = 0.087, p = 0.19), which is why recency weighting did not
help and why short hot streaks should not be trusted.</li>
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
<h1>Season results — 2026, weeks 1 to 10</h1>
<p class="note">All {ms['games_transcribed']} games transcribed from the official NFL.com by-week schedule pages and
read {AS_OF}. <strong>Verification:</strong> the wins, losses, ties, points for and points against implied by this
table were compared with the <a href="https://www.nfl.com/standings/" target="_blank" rel="noopener">official 2026
standings</a> for all 32 teams and match exactly on every column. Week 10 contains only the Thursday game; the rest
of that week had not been played when this page was built.</p>
{search_box('res-table')}
{table(results_games, ['week','date_as_shown','away_team','away_points','home_team','home_points','game_url','source_url'],
       {'week':'Wk','date_as_shown':'Date (as shown)','away_team':'Away','away_points':'Away pts','home_team':'Home','home_points':'Home pts','game_url':'Game','source_url':'Schedule'},
       table_id='res-table', filterable=True)}
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

<h2>Suggestion register — SR-01 to SR-18 (taken over from session 25d6114f, T52)</h2>
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
     "ours": "Computed W-L-T, PF and PA for all 32 teams from the ledger; 0 mismatches against the official standings",
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
     "theirs": f'{ms.get("measured_gate_qualified_strategies", "")} of {ms.get("strategies_tested", "")} pass its core gate rule (with {ms.get("measured_all_gate_passes_single_implementation", "")} meeting all 8 gates)',
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
<p class="note">The base implementation's unadjusted core-gate count is
{ms.get('measured_gate_qualified_strategies', '')} of {ms.get('strategies_tested', '')};
{ms.get('measured_all_gate_passes_single_implementation', '')} meet all eight of its gates. Reward-tier labels have since been disabled pending review (F43). This session's independent scoring of {n_competing} competing rules on
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
<p class="note">Difference is defined as market minus fair. It stays blank until a market value exists. Flag F44 covers the constant reference total.</p>
{table(line_comparison, ['game_no','matchup','side_fair_home_spread','side_market_home_spread','side_difference_market_minus_fair','total_fair','total_market','total_difference_market_minus_fair','moneyline_fair_home_win_prob','moneyline_market_home_win_prob','moneyline_difference_market_minus_fair','source_url'],
       {'game_no':'#','matchup':'Game','side_fair_home_spread':'Side: fair (home)','side_market_home_spread':'Side: market (home)','side_difference_market_minus_fair':'Side: diff','total_fair':'Total: fair','total_market':'Total: market','total_difference_market_minus_fair':'Total: diff','moneyline_fair_home_win_prob':'Moneyline: fair P(home)','moneyline_market_home_win_prob':'Moneyline: market P(home)','moneyline_difference_market_minus_fair':'Moneyline: diff','source_url':'Source'})}
<h2>3. Signal and staking, kept apart</h2>
<p class="note"><strong>The rank uses signal only.</strong> Signal is forecast skill against the naive reference line, with a
95% bootstrap interval. No staking result has been measured, because there are no prices. A staking result therefore cannot
raise or lower a strategy's rank. The tier labels on the leaderboard are under review (Flag F43).</p>
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
<p class="note">Checks on the {len(read_csv('games_2026_results.csv'))}-game official results feed. The second transcription is compared after one stated normalisation: the official page writes the Rams as LAR, this register writes LA (Flag F46). Three sampled game pages show a hidden score (Flag F47) and are not verified on the game center.</p>
{table(rf_checks, ['check_id','check','method','result','status','source_url'],
       {'check_id':'ID','check':'Check','method':'Method','result':'Result','status':'Status','source_url':'Source'},
       table_id='rf-table', filterable=True)}
<h2>Correlation audit: owner rule and sample size (T44)</h2>
<p class="note">Owner rule: a correlation qualifies only when both of its inputs are official numbers, with n published. {_n_qual} of {len(corr_audit)} rows qualify. {_n_diag} rows are model diagnostics (Flags F48, F49). The C09 row shows the register's earlier interval; the corrected interval is requested, not applied (Flag F48).</p>
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
<p class="note">For each Week 10 availability item: who replaces whom, the replacement's place on the club's depth chart as fetched on 2026-11-14, and what is still unverified. Club charts are undated and show pre-injury order (Flag F45). A depth rank is given only where an official statement names the replacement or starter. A blank rank means it could not be confirmed. {_depth_checked} of {len(rep_depth)} rows are checked against a club chart; A08 to A11 are open (Flag F53).</p>
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

<h2>Decision gates register — DQ-01 to DQ-20 (taken over from session 25d6114f, T52)</h2>
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
<li><strong>Replacement depth.</strong> {_depth_checked} of {len(rep_depth)} availability rows are checked against a club chart. A depth rank is given in {_depth_ranked} rows, only where an official statement names the replacement or starter. The charts are undated (Flag F45). Two rows do not name the replaced player (Flag F46). Four rows are not yet checked (Flag F53).</li>
<li><strong>Correlations.</strong> {_n_qual} of {len(corr_audit)} correlations meet the owner rule (official numbers only). {_n_diag} are model diagnostics (Flags F48, F49). The C09 calibration row is wrong in the register: its corrected interval is 0.335 to 1.435, p = 0.683 against slope 1.0. The correction is requested, not applied (Flag F48).</li>
<li><strong>Demotion rule D1.</strong> As drafted, D1 would return a strategy to paper in {_d50_trig} of {len(_d50)} side models over the last 50 games, although {_d50_pos} of {len(_d50)} have positive point estimates. The rule needs an owner decision (Flag F54, DEC-04).</li>
<li><strong>Results feed.</strong> The second transcription agrees on all {len(read_csv('games_2026_results.csv'))} games once LAR and LA are read as one team. Three sampled game pages show a hidden score and are not verified on the game center (Flag F47).</li>
<li><strong>Decisions.</strong> Ten owner decisions are recorded with options and a recommendation. Nothing has been implemented from them (<a href="decisions.html">Decisions</a>).</li>
</ul>
""")



# ---------- pages taken over from session 25d6114f (T52) ----------
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
estimated. The string rank and the replacement impact are deliberately blank. See Flag F57 for the correction to the
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
<li>The verification comparison is <strong>not fully independent</strong> of the original transcription because both were made in the same session (Flag F59). Suggestion SR-13 records the fix.</li>
<li>The official Thursday game has been played, so the injury report still shown is the pregame report for the remaining 13 games.</li>
</ul>
<h2>Review register</h2>
{search_box('rev-table')}
{table(repo_review_rows, ['review_id','target','line_or_group','what_was_reviewed','verified_against','result','finding','action_taken','source_url'],
       {'review_id':'ID','target':'File','line_or_group':'Lines','what_was_reviewed':'Reviewed','verified_against':'Verified against','result':'Result','finding':'Finding','action_taken':'Action taken','source_url':'Source'},
       table_id='rev-table', filterable=True)}
""")
# ---------- write ----------
os.makedirs(os.path.join(DOCS, "assets"), exist_ok=True)
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
