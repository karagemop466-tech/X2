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
    "www.nfl.com", "support.nfl.com", "operations.nfl.com",
    "laws.e-gov.go.jp", "www.jpnsport.go.jp", "www.gov-online.go.jp", "www.npa.go.jp",
    "www.itl.nist.gov", "github.com", "karagemop466-tech.github.io",
    "wetten.overheid.nl", "www.kansspelautoriteit.nl",
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
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
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
decisions = read_csv("decision-chain.csv")
sugg_review = read_csv("suggestion_review.csv")
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
    "decision_chain": decisions, "suggestion_review": sugg_review,
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
    ("depth-analysis.html", "Depth exposure"),
    ("strategy-lab.html", "Strategy lab"),
    ("decision-path.html", "Decision path"),
    ("questions.html", "Questions"),
    ("requirements.html", "Requirements"),
    ("suggestions.html", "Suggestions"),
    ("verification.html", "Verification"),
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
  <p>A source-linked dashboard for NFL injury tracking, depth exposure, strategy research, open questions and suggestions.
  Every table row links to an official NFL, government or statistical source; repository and deployment claims link to first-party project records. Unconfirmed NFL/model values remain blank and flagged.</p>
  <p class="note">Snapshot: <a href="https://www.nfl.com/injuries/" target="_blank" rel="noopener">NFL.com Week 10, 2026 injury report</a> and the <a href="https://www.nfl.com/schedules/2026/by-week/week-10" target="_blank" rel="noopener">official Week 10 schedule</a> (read {AS_OF}).</p>
  <p class="note"><strong>Verification status:</strong> all {tot['rows']} injury rows and all {tot['games']} Week 10 games were independently re-verified row by row against the official NFL.com pages on {AS_OF}, with no discrepancies found. See the <a href="verification.html">Verification record</a>.</p>
  <p class="note"><strong>Critical data-rights gate:</strong> NFL.com terms prohibit systematic retrieval to compile a database absent express prior written consent. No permission is recorded here for the published injury snapshot. Do not expand or automate this use pending review (Flag F16). <a href="https://support.nfl.com/hc/en-us/articles/35869743904916-NFL-com-Terms-and-Conditions" target="_blank" rel="noopener">NFL.com terms ↗</a> · <a href="flagged.html">Flagged for Review</a>.</p>
</section>
{tiles([(tot['teams'], 'teams on the Week 10 injury report'), (tot['rows'], 'players listed'),
        (tot['out'], 'marked Out'), (tot['doubtful'], 'marked Doubtful'), (tot['questionable'], 'marked Questionable'),
        (len(games), 'games in Week 10 list')])}
<h2>Start here</h2>
<div class="cards">
{card('executive-summary.html', 'Executive summary', 'The key findings, what is verified, and what is not yet known.')}
{card('decision-path.html', 'Decision path', 'The ten questions that must be answered, in order, before any dependent choice is made. Start here.')}
{card('injuries.html', 'Injuries', 'All 345 Week 10 injury report rows with source links, plus NFL.com news headlines.')}
{card('games.html', 'Games', 'The 14 Week 10 matchups with records and broadcast windows, all from NFL.com.')}
{card('depth-analysis.html', 'Depth exposure', 'Out and Doubtful players by unit, showing where a backup may be needed. Starter order is unverified.')}
{card('strategy-lab.html', 'Strategy lab', 'Validation gates, hypotheses and the leaderboard framework. No strategy has passed yet.')}
{card('questions.html', 'Questions', 'What we know, what we do not, and how to find the missing information.')}
{card('requirements.html', 'Requirements', 'Each requirement from the brief with its current status.')}
{card('suggestions.html', 'Suggestions', 'Review proposals before future implementation, with a recommended path and the gate that blocks each one.')}
{card('verification.html', 'Verification', 'What was checked line by line, against which official page, and what the result was.')}
{card('flagged.html', 'Flagged for review', 'Irregularities, unverified items and missing official data, each with a source link.')}
{card('sources.html', 'Sources', 'Every official source used, with what it supports.')}
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
<li><strong>Strategy research.</strong> No strategy has been tested. Odds, historical results and correlation data have not been obtained through a verified, authorized source, so every performance gate is open (Strategy lab).</li>
<li><strong>Data rights.</strong> NFL.com terms prohibit systematic retrieval to compile a database absent express prior written consent. No permission is recorded here for the published injury snapshot; do not expand or automate this use pending review (Flag F16).</li>
<li><strong>Legal.</strong> Government of Japan guidance says online sports betting accessed from Japan is gambling and prohibited there; this is Japan-specific and does not decide contest or reward mechanics. No legal opinion is provided (Flag F09).</li>
</ul>
<h2>What is verified</h2>
<ul>
<li>The Week 10 injury rows, game list, records, and news headlines (NFL.com, read {AS_OF}).</li>
<li>Penal Code Chapter 23 gambling articles (e-Gov Law Search); Japan Sport Council state lottery products.</li>
</ul>
<h2>What is not verified (left blank)</h2>
<ul>
<li>Starter vs backup order at every position (no official depth chart collected).</li>
<li>Betting lines, odds, prop prices and parlay prices (no official odds source).</li>
<li>Historical results, player stats and correlation values (not yet collected).</li>
<li>Injury-designation probabilities (NFL.com publishes labels, not probabilities).</li>
</ul>
<h2>Team exposure (Week 10, from the report)</h2>
{table(team_summary, ['team','listed','out','doubtful','questionable','offense_out_or_doubtful','defense_out_or_doubtful','special_teams_out_or_doubtful','source_url'],
   {'team':'Team','listed':'Listed','out':'Out','doubtful':'Doubtful','questionable':'Questionable','offense_out_or_doubtful':'Offense Out/Doubtful','defense_out_or_doubtful':'Defense Out/Doubtful','special_teams_out_or_doubtful':'ST Out/Doubtful','source_url':'Source'})}
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
<li>The Thursday result, Commanders 24 - Giants 21 final, is verified on the official schedule (Flag F22).</li>
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
<tr><td>Injury field values</td><td>Compared every player name, position, injury text, practice status and game status for all 28 team sections against the stored CSV.</td><td class="ok">No discrepancies found in this pass. Closes the F10 spot-check request.</td><td><a href="https://www.nfl.com/injuries/" target="_blank" rel="noopener">NFL injury report</a></td></tr>
<tr><td>Game list</td><td>Compared all 14 game headers: day, kickoff time, broadcaster and both listed records.</td><td class="ok">All 14 games match the stored games file.</td><td><a href="https://www.nfl.com/injuries/" target="_blank" rel="noopener">NFL injury report</a></td></tr>
<tr><td>Bye teams</td><td>Read the Teams on Bye section of the official Week 10 schedule.</td><td class="ok">CHI, DEN, PHI and TB confirmed, as recorded (Flag F05).</td><td><a href="https://www.nfl.com/schedules/2026/by-week/week-10" target="_blank" rel="noopener">Week 10 schedule</a></td></tr>
<tr><td>Home / away order</td><td>Compared the schedule game titles (for example "Bills at Jets") with the order NFL.com lists teams on the injury report.</td><td class="ok">The injury report lists the away team first in every Week 10 game; the site's "first listed / second listed" labels remain neutral and are now interpretable.</td><td><a href="https://www.nfl.com/schedules/2026/by-week/week-10" target="_blank" rel="noopener">Week 10 schedule</a></td></tr>
<tr><td>Official depth chart existence</td><td>Requested the conventional team depth-chart URL on the official site.</td><td class="warn">Returns HTTP 404 "Flag on the Play". No official depth chart is reachable, so starter/backup order stays blank (F06).</td><td><a href="https://www.nfl.com/teams/buffalo-bills/roster" target="_blank" rel="noopener">Bills roster</a></td></tr>
<tr><td>Thursday result</td><td>Read the final score on the official Week 10 schedule and the game center.</td><td class="warn">Verified as Commanders 24 - Giants 21 final, but not published: the games table has no result column (F22).</td><td><a href="https://www.nfl.com/games/commanders-at-giants-2026-reg-10" target="_blank" rel="noopener">Game center</a></td></tr>
<tr><td>News snapshot drift</td><td>Compared the stored headline list with the news section of the live injury page.</td><td class="warn">Two stored headlines are no longer shown on the live page. The injury rows are unaffected (F21).</td><td><a href="https://www.nfl.com/injuries/" target="_blank" rel="noopener">NFL injury report</a></td></tr>
<tr><td>Standings cross-check</td><td>Compared Week 10 listed records with the official standings page.</td><td class="ok">Records match for the teams checked. The injured-reserve players named in the news (Lamar Jackson, Malik Willis) do not appear on the injury report, consistent with reserve status rather than a game designation.</td><td><a href="https://www.nfl.com/standings/" target="_blank" rel="noopener">NFL standings</a></td></tr>
<tr><td>Source allow-list</td><td>Builder rejects any table row without an HTTPS link on the reviewed official-source allow-list, and any broken internal link.</td><td class="ok">Enforced in <code>scripts/build.py</code>; the build fails otherwise.</td><td><a href="https://github.com/karagemop466-tech/X2/blob/main/scripts/build.py" target="_blank" rel="noopener">build.py</a></td></tr>
</tbody></table></div>
<h2>Standing limitations</h2>
<ul>
<li><strong>Single reviewer.</strong> This pass was performed independently of session 30beeb55's separate T15 check, and both found no discrepancies. Two independent passes are the strongest control the manual-transcription limitation allows, but neither is an automated diff (F10, F20).</li>
<li><strong>Live pages move.</strong> Every "verified" statement is true of the page as read on {AS_OF}. The injury page shows no last-updated timestamp (F13).</li>
<li><strong>Rights are not verification.</strong> Confirming a value matches NFL.com does not grant permission to republish it in bulk (F16).</li>
<li><strong>Blank is deliberate.</strong> A dash means the official source did not supply a value, or no official source was found. It is never an inferred estimate.</li>
</ul>
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
