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
    # centers. It is a first-party NFL host, not a third-party data provider.
    "www.nfl.com", "static.www.nfl.com", "support.nfl.com", "operations.nfl.com",
    "laws.e-gov.go.jp", "www.jpnsport.go.jp", "www.gov-online.go.jp", "www.npa.go.jp",
    "www.itl.nist.gov", "github.com", "karagemop466-tech.github.io",
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
# Session 25d6114f registers (new, non-overlapping files).
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
    ("leaderboard_rules", lb_rules, "rule_id"),
    ("decision_questions", decisions, "q_id"),
    ("suggestions_register", sug_register, "sug_id"),
):
    for row in rows:
        if not row["evidence_url"].strip():
            errors.append(f"{label} {row[id_field]}: table row without evidence_url")
        check_official(row["evidence_url"], f"{label}.evidence_url")

# Registers that use source_url as their citation column.
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
    "verification_week10_2026": verification, "starters_gamebook_2026_reg_10": starters,
    "line_signals": line_signals, "skill_engine_gates": engine_gates, "luck_tests": luck_tests,
    "correlation_framework": corr_framework, "leaderboard_rules": lb_rules,
    "depth_deficiency": depth_def, "decision_questions": decisions,
    "suggestions_register": sug_register, "repo_review": repo_review,
}
for name, data in exports.items():
    with open(os.path.join(DOCS, "data", name + ".json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

# ---------- HTML helpers ----------
LINK_LABEL = {"source_url": "Source ↗", "player_url": "Player page ↗", "url": "Link ↗",
              "evidence_url": "Evidence ↗"}


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
    ("injuries.html", "Injuries"),
    ("games.html", "Games"),
    ("starters.html", "Starters &amp; depth"),
    ("depth-analysis.html", "Unit exposure"),
    ("strategy-lab.html", "Strategy lab"),
    ("signals.html", "Signals"),
    ("validation.html", "Skill engine"),
    ("anti-luck.html", "Anti-luck"),
    ("correlation.html", "Correlation"),
    ("leaderboard.html", "Leaderboard"),
    ("decisions.html", "Decision gates"),
    ("verification.html", "Verification"),
    ("repo-review.html", "Repo review"),
    ("questions.html", "Questions"),
    ("requirements.html", "Requirements"),
    ("suggestions.html", "Suggestions"),
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

# ---------- index ----------
pages["index.html"] = ("NFL Research Dashboard", f"""
<section class="hero">
  <h1>NFL Research Dashboard</h1>
  <p>A source-linked research dashboard for NFL availability, starter identity, independent-line signals, validation
  gates, anti-luck testing, correlation planning and the decisions still standing in the way.
  Every table row links to an official NFL, government or statistical source. Unconfirmed values are blank, never estimated.</p>
  <p class="note"><strong>What this site will not tell you:</strong> it will not give you a pick, a line or a price.
  No strategy here has been validated, and no reward is enabled. The evidence for both statements is on every page.</p>
  <p class="note">Snapshot: <a href="https://www.nfl.com/injuries/" target="_blank" rel="noopener">NFL.com Week 10, 2026 injury report</a> and the <a href="https://www.nfl.com/schedules/2026/by-week/week-10" target="_blank" rel="noopener">official Week 10 schedule</a> (read {AS_OF}).</p>
  <p class="note"><strong>Critical data-rights gate:</strong> NFL.com terms prohibit systematic retrieval to compile a database absent express prior written consent. No permission is recorded here for the published injury snapshot. Do not expand or automate this use pending review (Flag F16). <a href="https://support.nfl.com/hc/en-us/articles/35869743904916-NFL-com-Terms-and-Conditions" target="_blank" rel="noopener">NFL.com terms ↗</a> · <a href="flagged.html">Flagged for Review</a>.</p>
</section>
{tiles([(tot['teams'], 'teams on the Week 10 injury report'), (tot['rows'], 'players listed'),
        (tot['out'], 'marked Out'), (tot['doubtful'], 'marked Doubtful'), (tot['questionable'], 'marked Questionable'),
        (len(games), 'games in Week 10 list')])}
<h2>Start here</h2>
<div class="cards">
{card('executive-summary.html', 'Executive summary', 'The findings, what is verified, what is not, and the decisions waiting on you.')}
{card('decisions.html', 'Decision gates', 'Every question that must be answered before a path is chosen, with the choice you will face.')}
{card('suggestions.html', 'Suggestions', 'Eighteen recommendations with options; nothing is implemented without your choice.')}
</div>
<h2>Data and evidence</h2>
<div class="cards">
{card('injuries.html', 'Injuries', 'All 345 Week 10 injury-report rows, each with a source link.')}
{card('games.html', 'Games', 'The 14 Week 10 matchups with away/home, records and kickoff windows.')}
{card('starters.html', 'Starters and depth', 'Official gamebook starter identity, and why a 1st/2nd/3rd string rank cannot be official.')}
{card('depth-analysis.html', 'Unit exposure', 'Out and Doubtful players by unit, with replacement depth left blank.')}
{card('verification.html', 'Verification', 'The line-by-line re-check: 345 of 345 rows match, one official conflict flagged.')}
{card('repo-review.html', 'Repo review', 'Every file reviewed against a source; irregularities flagged, not hidden.')}
</div>
<h2>Strategy, lines and skill</h2>
<div class="cards">
{card('signals.html', 'Signals', 'Twenty original-line signal definitions for single bets, parlays and player-prop combos.')}
{card('validation.html', 'Skill engine', 'Seventeen gates; a strategy cannot be called valid until they pass.')}
{card('anti-luck.html', 'Anti-luck', 'Bootstrap intervals, multiplicity control and held-out blocks: how a lucky run is kept off the board.')}
{card('correlation.html', 'Correlation', 'The measurement plan for every dependent leg pair, with all values blank.')}
{card('leaderboard.html', 'Leaderboard', 'Rules first, entries later. No reward is enabled.')}
</div>
<h2>Reference</h2>
<div class="cards">
{card('strategy-lab.html', 'Strategy lab', 'The original framework: hypotheses, gates and market families.')}
{card('questions.html', 'Questions', 'What we know, what we do not, and how to find the missing information.')}
{card('requirements.html', 'Requirements', 'Each line of the brief with its current status.')}
{card('flagged.html', 'Flagged for review', 'Irregularities, unverified items and missing official data.')}
{card('sources.html', 'Sources', 'Every official source used, with what it supports.')}
</div>
</div>
""")

# ---------- executive summary ----------
top5 = team_summary[:5]
top5_txt = ", ".join(f"{t['team']} ({t['out']} Out, {t['doubtful']} Doubtful)" for t in top5)
pages["executive-summary.html"] = ("Executive summary", f"""
<h1>Executive summary</h1>
<p class="note">Snapshot read {AS_OF}. Every figure below is counted from <code>data/*.csv</code> and links to an
official source. Where a value could not be confirmed it is blank and flagged, not estimated.</p>
{tiles([(tot['out'] + tot['doubtful'], 'Out or Doubtful players'), (len(engine_gates), 'validation gates'),
        (sum(1 for r in engine_gates if r['current_status'].startswith(('Open', 'Blocked', 'Partially'))), 'gates still open or blocked'),
        (len(decisions), 'decisions waiting on you'), (0, 'strategies validated')])}

<h2>The five things that matter</h2>
<ol class="findings">
<li><strong>The data you have is solid; the data you need is not here.</strong> The Week 10 injury snapshot re-verified
cleanly: {tot['rows']} rows across {tot['teams']} teams and {tot['games']} games, 345 of 345 rows matching the official
page on position, injury, practice status and game status (1380 field comparisons).
<a href="verification.html">Verification</a></li>
<li><strong>Starter identity turned out to be officially verifiable after all.</strong> The NFL publishes no pregame
depth chart, so a "1st, 2nd, 3rd, 4th string" rank cannot be sourced. But the official NFL gamebook publishes the
starting lineup by slot, the substitutions and the inactive list. Nineteen starter-identity rows are verified, and the
earlier flag saying no official starter data existed is corrected as F20. <a href="starters.html">Starters and depth</a></li>
<li><strong>You cannot originate a line yet, and the reason is data, not method.</strong> Twenty signal definitions, a
seventeen-gate skill engine, ten anti-luck tests and a full correlation plan are written and published. Not one of them
has a value, because there is no licensed price series, no historical results ledger and no paired settled outcomes.
<a href="signals.html">Signals</a> · <a href="validation.html">Skill engine</a></li>
<li><strong>"Remove luck" is the wrong target; bounding it is the right one.</strong> Football results carry large
irreducible variance. What can be enforced is that a lucky result cannot pass: bootstrap intervals, a published search
log, multiplicity-adjusted decisions and a held-out block. <a href="anti-luck.html">Anti-luck</a></li>
<li><strong>Two gates block almost everything.</strong> Data rights (DQ-01) and jurisdiction plus contest design (DQ-02).
NFL terms prohibit systematic retrieval to compile a database without written consent, and official Japanese guidance
treats online sports betting as a criminal offence. Until those two are answered, expanding collection or enabling a
reward would be imprudent. <a href="decisions.html">Decision gates</a></li>
</ol>

<h2>What is verified today</h2>
<ul>
<li><strong>Injury snapshot:</strong> {tot['out']} Out, {tot['doubtful']} Doubtful, {tot['questionable']} Questionable,
{tot['no_status']} with no game status, across {tot['rows']} listed players. <a href="injuries.html">Injuries</a></li>
<li><strong>Schedule and records:</strong> all 14 Week 10 games, with away and home resolved from the official
"X at Y" order, and {', '.join(tot['missing_teams'])} confirmed on bye from the schedule rather than inferred.
<a href="games.html">Games</a></li>
<li><strong>Exposure by side of ball:</strong> offense {tot['off_od']}, defense {tot['def_od']}, special teams
{tot['st_od']} players Out or Doubtful.</li>
<li><strong>Starter identity:</strong> the Week 10 Commanders at Giants gamebook, including one full-practice player who
did not play at all and one limited participant who started. <a href="starters.html">Starters</a></li>
<li><strong>Law and terms:</strong> quoted directly from the NFL terms, the Government of Japan, the National Police
Agency and the Penal Code. <a href="sources.html">Sources</a></li>
</ul>

<h2>What is not verified, and is therefore left blank</h2>
<ul>
<li><strong>Any line, price or odds value.</strong> No licensed odds source exists in this repository (F07).</li>
<li><strong>Any correlation coefficient.</strong> No paired settled legs exist (C01 to C10 are blank).</li>
<li><strong>Any pregame depth order.</strong> No official pregame depth chart exists (F20, DQ-06).</li>
<li><strong>Any injury-designation probability.</strong> NFL.com publishes three labels and no probabilities (F04).</li>
<li><strong>Any strategy score.</strong> No strategy has been tested, and none may be entered on the leaderboard (EG14).</li>
<li><strong>Any reward.</strong> Nothing is defined, funded or legally reviewed (EG16, F09).</li>
</ul>

<h2>Most-exposed teams by Out plus Doubtful</h2>
<p class="note">Counted from the official report. This is availability, not a measured weakness.</p>
<ul>
{''.join(f"<li><strong>{t['team']}</strong> — {t['out']} Out, {t['doubtful']} Doubtful, {t['questionable']} Questionable (offense {t['offense_out_or_doubtful']}, defense {t['defense_out_or_doubtful']}, special teams {t['special_teams_out_or_doubtful']})</li>" for t in team_summary[:8])}
</ul>

<h2>The three decisions that unlock the most work</h2>
<ol>
<li><strong>DQ-01 — data rights.</strong> Settle permission or a licence. Until then the site stays a source-linked summary and collection is not expanded or automated (F16).</li>
<li><strong>DQ-02 — jurisdiction and contest design.</strong> Obtain a written legal opinion covering rewards and advertising before any prize is described (F09, EG16).</li>
<li><strong>DQ-09 — historical depth.</strong> Decide how many seasons of schedules and gamebooks to collect; one week cannot support a single statistical gate.</li>
</ol>
<p>Every other open question, the exact choice you will face, and how to find the missing answer are on the
<a href="decisions.html">Decision gates</a> page. Suggestions with options and effort are on the
<a href="suggestions.html">Suggestions</a> page. Nothing on this site has been changed on the basis of a suggestion.

<h2>Team exposure (Week 10, from the report)</h2>
{table(team_summary, ['team','listed','out','doubtful','questionable','offense_out_or_doubtful','defense_out_or_doubtful','special_teams_out_or_doubtful','source_url'],
   {'team':'Team','listed':'Listed','out':'Out','doubtful':'Doubtful','questionable':'Questionable','offense_out_or_doubtful':'Offense Out/Doubtful','defense_out_or_doubtful':'Defense Out/Doubtful','special_teams_out_or_doubtful':'ST Out/Doubtful','source_url':'Source'})}
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
{table(games, ['game_no','kickoff_day','kickoff_time_et','broadcast','first_listed_team','first_listed_record','second_listed_team','second_listed_record','source_url'],
       {'game_no':'Game','kickoff_day':'Day','kickoff_time_et':'Kickoff (ET)','broadcast':'Broadcast','first_listed_team':'First listed','first_listed_record':'Record','second_listed_team':'Second listed','second_listed_record':'Record','source_url':'Source'})}
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
<p class="note">This page defines how strategies would be judged. <strong>No strategy has been tested and none has passed.</strong>
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
<h2>Leaderboard — entries require every gate</h2>
<p class="note">The intended competition ranks strategy performance only after preregistered, out-of-sample validation. The requested top-performer reward is not defined or enabled: eligibility, jurisdiction, data rights and legal review remain unresolved. No monetary value, score, sample size or uncertainty interval is reported.</p>
{table(leaderboard_status, ['rank','strategy','skill_score','eligible_sample','uncertainty','validation_status','top_performance_reward','source_url'],
       {'rank':'Rank','strategy':'Strategy','skill_score':'Performance score','eligible_sample':'Eligible sample','uncertainty':'Uncertainty','validation_status':'Validation status','top_performance_reward':'Top-performance reward','source_url':'Project record'})}
""")

# ---------- starters and depth (official gamebook) ----------
starters_good = [r for r in starters if r["gamebook_status"] == "Starter"]
starters_bad = [r for r in starters if r["gamebook_status"] != "Starter"]
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
estimated. The string rank and the replacement impact are deliberately blank. See Flag F20 for the correction to the
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

# ---------- signals ----------
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
The correlation page holds the dependence plan; nothing has been measured.</p>
""")

# ---------- validation / skill engine ----------
pages["validation.html"] = ("Skill engine", f"""
<h1>Skill engine — the gates every strategy must pass</h1>
<p class="note"><strong>Seventeen gates, zero passed.</strong> The point of this page is to make a claim impossible
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
<li><strong>"Determine correlation values."</strong> Correlation is gated by EG12 and EG13, which cannot pass without paired settled data. See Correlation.</li>
<li><strong>"Remove luck from the equation."</strong> Luck cannot be removed. It can be bounded and disclosed: a bootstrap interval, a search log and a held-out block. See Anti-luck for why "remove" is the wrong target and what replaces it.</li>
<li><strong>"Build strategies that are selectively skill based."</strong> A strategy is selectively applied only where the gate ledger shows measured skill; until then the correct selective rule is to apply nothing.</li>
<li><strong>"Rewards for top performing strategies."</strong> EG16 blocks any reward until a qualified legal review covers the jurisdiction and the contest design.</li>
</ul>
""")

# ---------- anti-luck ----------
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

# ---------- correlation ----------
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

# ---------- leaderboard ----------
pages["leaderboard.html"] = ("Leaderboard", f"""
<h1>Leaderboard — rules first, entries later</h1>
<p class="note"><strong>There is no leaderboard yet, and that is the correct state.</strong> A leaderboard with no
validated entries would rank noise. The rules below exist so that when entries do arrive they cannot quietly reward
luck. The requested reward for top performers is <em>not defined or enabled</em>: it is blocked by gate EG16 because
contest and reward legality has not been reviewed for your jurisdiction.</p>
{tiles([(len(lb_rules), 'public rules'), (0, 'eligible entries'), (0, 'scored strategies'),
        (len([r for r in engine_gates if r['current_status'].startswith('Open')]), 'open gates before an entry is possible')])}
<h2>Leaderboard rules</h2>
{table(lb_rules, ['rule_id','topic','rule','why_this_rule','what_is_intentionally_left_blank','evidence_url'],
       {'rule_id':'Rule','topic':'Topic','rule':'Rule','why_this_rule':'Why','what_is_intentionally_left_blank':'Intentionally blank','evidence_url':'Evidence'})}
<h2>Entries</h2>
{table(leaderboard_status, ['rank','strategy','skill_score','eligible_sample','uncertainty','validation_status','top_performance_reward','source_url'],
       {'rank':'Rank','strategy':'Strategy','skill_score':'Score','eligible_sample':'Eligible N','uncertainty':'Uncertainty','validation_status':'Validation status','top_performance_reward':'Reward','source_url':'Record'})}
<h2>What a first entry would require</h2>
<ol>
<li>Written permission or a licence covering the data used (gate EG0).</li>
<li>A preregistration committed before any evaluation (EG1).</li>
<li>A point-in-time feature set that replays exactly (EG2).</li>
<li>A declared baseline and metric, and a held-out block (EG3, EG5).</li>
<li>Bootstrap and multiplicity-adjusted intervals (EG6).</li>
<li>Real costs and settlement rules (EG7).</li>
<li>A legal review of the reward itself (EG16).</li>
</ol>
""")

# ---------- decision gates ----------
pages["decisions.html"] = ("Decision gates", f"""
<h1>Decision gates — the questions that must be answered before any path is chosen</h1>
<p class="note">This is the review page you asked for. Each row is a question that must be answered <em>before</em> a
route can sensibly be chosen, what is known now with a source, how to find the missing answer, and the choice you
will be facing. The <em>Decision</em> column is yours: nothing is chosen automatically, and no route is implemented
while its gate is open. Gates are ordered, not equal: <strong>DQ-01 (data rights)</strong> and <strong>DQ-02
(jurisdiction and contest design)</strong> block everything downstream.</p>
{tiles([(len(decisions), 'decision gates'), (len({r['stage'] for r in decisions}), 'stages'), (2, 'gates that block all downstream work'),
        (len(decisions) - 2, 'gates that block one workstream each')])}
<h2>The funnel</h2>
<ol>
<li><strong>Gate 0 — can you legally use the data and run a contest?</strong> DQ-01, DQ-02, DQ-03, DQ-04.</li>
<li><strong>Gate 1 — can you establish who actually played?</strong> DQ-05, DQ-06, DQ-07, DQ-08.</li>
<li><strong>Gate 2 — do you have enough history to measure anything?</strong> DQ-09 to DQ-13.</li>
<li><strong>Gate 3 — can you measure dependence and settlement?</strong> DQ-14, DQ-15, DQ-16.</li>
<li><strong>Gate 4 — what may be published, and how is quality enforced?</strong> DQ-17 to DQ-20.</li>
</ol>
<h2>Answer register</h2>
{search_box('dec-table')}
{table(decisions, ['q_id','stage','decision_topic','question_that_must_be_answered','why_it_blocks_a_decision','known_now_source_backed','how_to_discover','the_choice_you_will_face','owner','evidence_url'],
       {'q_id':'ID','stage':'Stage','decision_topic':'Topic','question_that_must_be_answered':'Question to answer','why_it_blocks_a_decision':'Why it blocks a decision','known_now_source_backed':'Known now (sourced)','how_to_discover':'How to find out','the_choice_you_will_face':'The choice you will face','owner':'Owner','evidence_url':'Source'},
       table_id='dec-table', filterable=True)}
""")

# ---------- verification ----------
result_counts = Counter(r["result"].split(" — ")[0] for r in verification)
pages["verification.html"] = ("Verification", f"""
<h1>Verification — every check, with its result</h1>
<p class="note"><strong>This is the line-by-line re-check you asked for.</strong> The committed Week 10 snapshot was
compared, field by field, against a fresh transcription of the
<a href="https://www.nfl.com/injuries/" target="_blank" rel="noopener">official NFL injury report</a>, and the game
list was compared against the <a href="https://www.nfl.com/schedules/2026/by-week/week-10" target="_blank" rel="noopener">official schedule</a>.
The comparison is reproducible: run <code>python3 scripts/verify_snapshot.py</code>. No committed value was edited as a
result of this review; mismatches would be recorded and flagged, not silently corrected.</p>
{tiles([(len(verification), 'checks run'), (result_counts.get('PASS', 0), 'passed'),
        (result_counts.get('CONFIRMED', 0), 'confirmed'),
        (sum(v for k, v in result_counts.items() if k.startswith('NEW EVIDENCE')), 'new evidence'),
        (sum(1 for r in verification if 'REVIEW' in r['result']), 'needs review'),
        (sum(1 for r in verification if r['result'].startswith('FAIL')), 'failed')])}
<h2>What was compared</h2>
<ul>
<li><strong>Rows:</strong> 345 committed rows against 345 official rows. No player missing, no extra player.</li>
<li><strong>Fields:</strong> position, injury, practice status and game status for every row — 1380 comparisons.</li>
<li><strong>Teams:</strong> all 28 teams, with per-team row counts and field agreement.</li>
<li><strong>Games:</strong> all 14 games on teams, records, day, kickoff time and broadcast, with away and home resolved from the official "X at Y" order.</li>
<li><strong>Byes:</strong> CHI, DEN, PHI and TB confirmed on the official Teams on Bye list.</li>
<li><strong>Links:</strong> every player URL on the official players route, including the 48 slugs that differ from the display name.</li>
<li><strong>Cross-source:</strong> six independent player-page checks, the roster-page depth claim, and 19 gamebook starter rows.</li>
</ul>
<h2>The one item that needs your judgement</h2>
<p>The injury report lists <strong>Ben Brown</strong> (New England) as a centre. His
<a href="https://www.nfl.com/players/ben-brown-2/" target="_blank" rel="noopener">official player page</a> lists him as a
guard. Both are official nfl.com pages, so one of them is wrong. The snapshot keeps the value from the page it declares
as its source and the conflict is flagged as F19. You will need a source-precedence rule (decision gate DQ-18).</p>
<h2>Check register</h2>
{search_box('ver-table')}
{table(verification, ['check_id','scope','what_was_checked','committed_value','official_value','result','note','source_url'],
       {'check_id':'ID','scope':'Scope','what_was_checked':'What was checked','committed_value':'Committed value','official_value':'Official value','result':'Result','note':'Note','source_url':'Source'},
       table_id='ver-table', filterable=True)}
""")

# ---------- repo review ----------
review_counts = Counter(r["result"] for r in repo_review)
pages["repo-review.html"] = ("Repo review", f"""
<h1>Repo review — line by line, with sources</h1>
<p class="note">Every file this session owns was reviewed against a source, and any irregularity is recorded rather
than quietly fixed. Findings that contradict an earlier claim are flagged for review; findings that are correct are
left alone. Project-implementation claims link to first-party GitHub records and are <em>not</em> offered as evidence
for NFL facts.</p>
{tiles([(len(repo_review), 'files or groups reviewed'), (review_counts.get('PASS', 0), 'pass'),
        (sum(v for k, v in review_counts.items() if k.startswith('VERIFIED')) + review_counts.get('LIVE', 0) + review_counts.get('CORRECT', 0), 'verified'),
        (review_counts.get('NEW EVIDENCE', 0), 'new evidence'),
        (review_counts.get('IRREGULARITY', 0), 'irregularities')])}
<h2>Independence and timestamps</h2>
<ul>
<li>The snapshot is dated <strong>2026-11-14 (UTC)</strong> because the official page publishes no last-updated time (Flag F13).</li>
<li>The verification comparison is <strong>not fully independent</strong> of the original transcription because both were made in the same session (Flag F22). Suggestion SR-13 records the fix.</li>
<li>The official Thursday game has been played, so the injury report still shown is the pregame report for the remaining 13 games.</li>
</ul>
<h2>Review register</h2>
{search_box('rev-table')}
{table(repo_review, ['review_id','target','line_or_group','what_was_reviewed','verified_against','result','finding','action_taken','source_url'],
       {'review_id':'ID','target':'File','line_or_group':'Lines','what_was_reviewed':'Reviewed','verified_against':'Verified against','result':'Result','finding':'Finding','action_taken':'Action taken','source_url':'Source'},
       table_id='rev-table', filterable=True)}
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
<h1>Suggestions — choose a path before anything is implemented</h1>
<p class="note"><strong>How to use this page.</strong> Each row is a recommendation with the problem it fixes, the
evidence that it helps, the options available, and the gate it depends on. Read the <em>Recommended</em> column, then
record your choice. Nothing here is implemented: no option is switched on until you choose it and its gate is
answered on the <a href="decisions.html">Decision gates</a> page. Where a recommendation depends on an open gate, the
gap is named, so the choice is informed rather than optimistic.</p>
{tiles([(len(sug_register), 'recommendations'), (len({r['category'] for r in sug_register}), 'categories'),
        (sum(1 for r in sug_register if r['depends_on_gate'] not in ('None', '')), 'blocked by an open gate'),
        (0, 'implemented without your decision')])}
<h2>Suggestion register</h2>
{search_box('sug-table')}
{table(sug_register, ['sug_id','category','recommendation','improves_which_decision','evidence_that_it_helps','options','recommended_option','effort','risk','depends_on_gate','review_status','evidence_url'],
       {'sug_id':'ID','category':'Category','recommendation':'Recommendation','improves_which_decision':'Decision it improves','evidence_that_it_helps':'Evidence','options':'Options','recommended_option':'Recommended','effort':'Effort','risk':'Risk','depends_on_gate':'Depends on','review_status':'Review status','evidence_url':'Evidence'},
       table_id='sug-table', filterable=True)}
<h2>The three that matter most</h2>
<ol>
<li><strong>SR-02 — settle the data rights.</strong> Everything else is downstream of permission. Until DQ-01 is answered the site should stay a source-linked summary.</li>
<li><strong>SR-03 — adopt the official gamebook.</strong> This is the one requirement that turned out to be solvable from an official source: starter identity is published, just not as a pregame depth chart.</li>
<li><strong>SR-09 — make the anti-luck suite a hard gate.</strong> Without it the leaderboard rewards luck, which is the opposite of what you asked for.</li>
</ol>
<h2>Earlier proposals, kept for the record</h2>
<p class="note">The original ten proposals are retained unchanged so the record is not lost.</p>
{table(suggestions, ['suggestion_id','area','suggestion','benefit_for_decisions','effort','main_risk','options','status','evidence_url'],
       {'suggestion_id':'ID','area':'Area','suggestion':'Suggestion','benefit_for_decisions':'Benefit','effort':'Effort','main_risk':'Main risk','options':'Options','status':'Status','evidence_url':'Evidence'})}
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
