# ---------- session e4e71368: line book, results feed, origination, staking, depth, gates ----
import json as _json
import collections as _coll


def read_json(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return _json.load(f)


def with_link(rows, url, override=("source_url",)):
    out = []
    for r in rows:
        d = dict(r)
        for k in override:
            if not d.get(k):
                d[k] = url
        d.setdefault("source_url", url)
        out.append(d)
    return out


lb_rows = read_csv("line_book_snapshots.csv")
lb_summary = read_json("line_book_summary.json")
rf_feed = read_csv("results_feed.csv")
rf_grades = read_csv("results_feed_grades.csv")
rf_summary = read_json("results_feed_summary.json")
orig_rows = read_csv("originated_markets_week11.csv")
orig_audit = read_csv("origination_audit.csv")
orig_contract = read_csv("origination_contract.csv")
stake_rows = read_csv("staking_book.csv")
stake_canary = read_json("staking_canary.json")
depth_detail = read_csv("replacement_depth_detail_week10_2026.csv")
corr_reg = read_csv("correlation_register.csv")
demo_eval = read_csv("demotion_evaluation.csv")

GITHUB_DATA = "https://github.com/karagemop466-tech/X2/blob/main/data/"
_matchup_by_key = {}
for _r in rf_feed:
    _matchup_by_key[(_r["week"], _r["away_team"] + " at " + _r["home_team"])] = (
        _r["away_team"] + " at " + _r["home_team"])

lb_view = with_link(lb_rows, GITHUB_DATA + "line_book_snapshots.csv")
for _d, _r in zip(lb_view, lb_rows):
    _d["matchup"] = "%s at %s" % (_r["away_team"], _r["home_team"])
    _d["week_label"] = "W" + _r["week"]

rf_view = []
for _r in rf_feed:
    rf_view.append({"feed_id": _r["feed_id"], "week": "W" + _r["week"],
                    "matchup": "%s at %s" % (_r["away_team"], _r["home_team"]),
                    "kickoff": (_r["kickoff_local_date"] + (" " + _r["kickoff_time_local_et"]
                                                            if _r["kickoff_time_local_et"] else "")),
                    "settlement_state": _r["settlement_state"],
                    "away_points": _r["away_points"], "home_points": _r["home_points"],
                    "margin_home": _r["margin_home"], "total": _r["total"],
                    "capture_method": _r["capture_method"], "source_url": _r["source_url"]})
grade_view = with_link(rf_grades, GITHUB_DATA + "results_feed_grades.csv")
for _d, _r in zip(grade_view, rf_grades):
    _d["matchup"] = _r["game_key"].split(" ", 1)[1] if " " in _r["game_key"] else _r["game_key"]
orig_view = with_link(orig_rows, GITHUB_DATA + "originated_markets_week11.csv")
for _d, _r in zip(orig_view, orig_rows):
    _d["week_label"] = "W" + _r["week"]
    _d["game_page"] = _r["source_url"]
audit_view = with_link(orig_audit, GITHUB_DATA + "originated_markets_week11.csv")
for _d, _r in zip(audit_view, orig_audit):
    _d["matchup"] = _r["game_key"].split(" ", 1)[1] if " " in _r["game_key"] else _r["game_key"]
contract_view = with_link(orig_contract, GITHUB_DATA + "origination_contract.csv")
stake_view = with_link(stake_rows, GITHUB_DATA + "staking_book.csv")
depth_view = with_link(depth_detail, GITHUB_DATA + "replacement_depth_detail_week10_2026.csv")
corr_view = with_link(corr_reg, GITHUB_DATA + "correlation_register.csv")
demo_view = with_link(demo_eval, GITHUB_DATA + "demotion_evaluation.csv")
depth_blank_view = [r for r in depth_view if not r["levels_down"]]
depth_ok_count = len(depth_detail) - len(depth_blank_view)

lb_by_game = _coll.OrderedDict()
for r in lb_rows:
    lb_by_game.setdefault((r["week"], r["game_key"]), []).append(r)
lb_open = lb_summary["opening_snapshots"]
lb_closed = lb_summary["closing_snapshots"]
rf_settled = rf_summary["settled_final"]
rf_unsett = rf_summary["scheduled_unsettled"]
rf_pending = rf_summary["grade_rows_pending"]
audit_ok = sum(1 for r in orig_audit if r["verdict"] == "consistent")
audit_bad = len(orig_audit) - audit_ok
clubs_read = sorted({r["team_abbr"] for r in depth_detail})
demo_fire = sum(1 for r in demo_eval if r["verdict"] == "FIRES")
demo_nc = sum(1 for r in demo_eval if r["verdict"] == "NOT COMPUTABLE")
demo_rules = len({r["rule_id"] for r in demo_eval})
cr_by_id = {r["corr_id"]: r for r in corr_reg}
cr06, cr05 = cr_by_id["CR06"], cr_by_id["CR05"]
bh_family = sum(1 for r in leaderboard if r["skill_p_permutation"])
bh_factor = len(leaderboard) / bh_family
d1_m1 = next(r["measured_value"] for r in demo_eval
             if r["rule_id"] == "D1" and r["strategy_id"] == "M1")
canary_p = str(stake_canary["probability_some_strategy_reaches_that_run_by_chance_alone"])
m2_row = stake_view[1]
w11_matchup = {r["game_no"]: r["matchup"] for r in model_lines}
for _d in orig_view:
    _d["matchup"] = w11_matchup.get(_d["game_no"], _d["game_key"])
for _d in contract_view:
    _d.setdefault("status", "Enforced by scripts/originate.py")

pages["line-book.html"] = ("Line book", """
<h1>Line book</h1>
<p class="note">Opening and closing numbers for the markets <strong>this project originates</strong>. The opening number of
our own line is a fact about our own publication — the timestamp of the commit that first published it — so it is recorded
here and never estimated. <strong>No bookmaker price appears on this page or in this file</strong>: the project has no
authorised odds source (Flag F07), and NFL.com's terms prohibit systematic retrieval of odds to compile a database absent
written consent (Flag F16). The market-price columns exist so the shape is fixed now and the cell can be filled only from a
source that is authorised — they are blank in all %s rows.</p>
%s
<h2>1. What is stored, and what may never be back-filled</h2>
<p class="note">The same contract governs the store and the originated view
(<a href="origination.html">Origination</a>), so the two cannot drift apart.</p>
<p class="note">Every snapshot is timed against the official kickoff for its game. A line first published <em>after</em>
kickoff is excluded rather than recorded as an opening number, so the ledger cannot quietly fill itself with retrospective
numbers. Re-check with <code>python3 scripts/line_book.py --check</code>.</p>
<h2>2. The ledger</h2>
<p class="note">One row per market per snapshot. <em>Model fair line</em> is our published number. <em>Reference line</em>
is the naive benchmark this project grades against and is labelled as such — it is not a market price (Flag F32). Kickoff
dates come from the <a href="https://www.nfl.com/schedules/2026/by-week/week-11" target="_blank" rel="noopener">official
Week 11 schedule</a> and the
<a href="https://www.nfl.com/schedules/2026/by-week/week-10" target="_blank" rel="noopener">Week 10 schedule</a>.
<em>Provenance</em> names the commit that published the line; the history is read from the repository, and this sandbox
clone may be shallow (Flag F60).</p>
%s
<h2>3. Where this goes next</h2>
<ul class="findings">
<li><strong>Closing numbers are not missing by oversight.</strong> No game in this ledger has reached kickoff since the
store was built, so all %s closing windows are open and the earliest kickoff is %s days away. The cadence that would close
them is an owner decision (Q43, D11, suggestion S29).</li>
<li><strong>A closing number cannot be recovered after the fact.</strong> If a capture is missed the row says so; it is not
back-filled from a later line.</li>
<li><strong>The price-side tables written by session c125b2f7</strong> are on
<a href="markets.html">Market tables</a>. That session's note on where its reference prices came from is recorded as an
irregularity (F51), and the market cells stay blank here.</li>
</ul>
""" % (len(lb_rows),
       tiles([(len(lb_rows), "snapshots in the ledger"), (lb_open, "opening snapshots"),
              (lb_closed, "closing snapshots recorded"), (len(lb_by_game), "games covered")]),
       table(lb_view, ["ledger_seq", "week_label", "game_key", "matchup", "market_type", "selection",
                       "model_fair_line", "market_line", "fair_minus_market", "snapshot_role", "captured_at_utc",
                       "closing_state", "closing_due_by", "captured_before_kickoff", "provenance_ref",
                       "provenance_url", "source_url"],
             {"ledger_seq": "Seq", "week_label": "Wk", "game_key": "Game key", "matchup": "Matchup",
              "market_type": "Market", "selection": "Selection", "model_fair_line": "Model fair line",
              "market_line": "Market line", "fair_minus_market": "Fair − market", "snapshot_role": "Role",
              "captured_at_utc": "Captured at (UTC)", "closing_state": "Closing state", "closing_due_by": "Closing due",
              "captured_before_kickoff": "Pre-kickoff?", "provenance_ref": "Provenance",
              "provenance_url": "Provenance link", "source_url": "Source"}, table_id="lb-table", filterable=True),
       lb_summary["closing_windows_open"], lb_summary["earliest_kickoff_in_days"]))
pages["results-feed.html"] = ("Results feed", """
<h1>Results feed</h1>
<p class="note">One row per 2026 fixture with an explicit settlement state, so a backtest can join to a score and a
fixture with no score yet can be excluded honestly rather than silently. Settled scores are the transcribed official
finals; the settled half is re-aggregated per club and compared with the
<a href="https://www.nfl.com/standings/" target="_blank" rel="noopener">official standings</a> as its own check. Unsettled
rows carry no score and no result — that is the purpose of the column, not a gap in the work.</p>
%s
<h2>1. Settlement states</h2>
<p class="note">A fixture is either <em>SETTLED-FINAL</em> (a score exists, and margin and total are recomputed from it) or
<em>SCHEDULED-UNSETTLED</em>. Grading is permitted only against the first state: <code>scripts/results_feed.py grade</code>
refuses to grade a row that is not settled. Of %s originated markets, %s are graded and %s are pending because their
fixture has not been played — the ten unplayed Week 10 games and all 13 of Week 11. The last settled kickoff in the feed
is %s and the next is %s.</p>
<h2>2. The feed</h2>
<p class="note">%s settled finals; %s fixtures recorded as scheduled with empty score cells. Each row links to the official
page it was read from, and the <em>how recorded</em> column says whether a row is a result or a fixture.</p>
%s
<h2>3. What each originated market is waiting for</h2>
<p class="note">The market, its fixture, the state of that fixture, and the number to be compared against. The
<em>result</em> columns stay blank until the fixture is settled; nothing here is graded on a forecast, and no payout is
computed because no price exists (Flag F07).</p>
%s
<h2>4. What this feed does not do</h2>
<ul class="findings">
<li><strong>It publishes no return.</strong> It records outcomes, not prices, so it makes outcome grading computable and
leaves monetary ROI blocked (Flags F07, F16); the summary file states this in the field
<code>roi_computable_against_market: %s</code>.</li>
<li><strong>It is not the model's input.</strong> The feed and the backtest read the same transcribed finals; that shared
origin is stated wherever a check uses it, because a feed cannot validate the transcription it was built from.</li>
<li><strong>It keeps the LAR/LA alias visible</strong> — the standings and one schedule history use different abbreviations
for the same club, so the reconciliation maps them to one club and says so (F55).</li>
<li><strong>One tie is recorded among %s settled games</strong> (week 5, Giants 27 at Commanders 27). It is kept as a tie rather
than absorbed into a side; the consequence for the originated moneyline is recorded as F58.</li>
</ul>
""" % (tiles([(len(rf_feed), "fixtures in the feed"), (rf_settled, "settled finals"),
             (rf_unsett, "scheduled, not settled"), (rf_pending, "originated markets awaiting settlement")]),
       rf_summary["grade_rows"], rf_summary["grade_rows_graded"], rf_pending,
       rf_summary["last_settled_kickoff"], rf_summary["next_kickoff"],
       rf_settled, rf_unsett,
       table(rf_view, ["feed_id", "week", "matchup", "kickoff", "settlement_state", "away_points", "home_points",
                       "margin_home", "total", "capture_method", "source_url"],
             {"feed_id": "ID", "week": "Wk", "matchup": "Matchup", "kickoff": "Kickoff",
              "settlement_state": "Settlement state", "away_points": "Away pts", "home_points": "Home pts",
              "margin_home": "Margin (home)", "total": "Total", "capture_method": "How recorded",
              "source_url": "Official page"}, table_id="rf-table", filterable=True),
       table(grade_view, ["grade_id", "matchup", "week", "market_type", "selection", "model_fair_line",
                          "settlement_state", "actual_margin_home", "actual_total", "side_result", "total_result",
                          "moneyline_result", "grade_status", "source_url"],
             {"grade_id": "ID", "matchup": "Matchup", "week": "Wk", "market_type": "Market", "selection": "Selection",
              "model_fair_line": "Our line", "settlement_state": "Fixture state", "actual_margin_home": "Actual margin",
              "actual_total": "Actual total", "side_result": "Side result", "total_result": "Total result",
              "moneyline_result": "Moneyline result", "grade_status": "Grade status", "source_url": "Source"},
             table_id="rf-grade-table", filterable=True),
       str(rf_summary["roi_computable_against_market"]), rf_summary["tie_games_in_feed"]))

pages["origination.html"] = ("Origination", """
<h1>Origination</h1>
<p class="note">What the pipeline puts out for each game, in the order the brief specifies, with the arithmetic re-run
against the published model file rather than restated from memory. Read it with
<a href="model-lines.html">Model and Week 11 lines</a>, which holds the model itself.</p>
%s
<h2>1. The order, and what it does and does not buy</h2>
<p class="note">Side first, then the total, then the moneyline. The moneyline is <em>derived</em> from stage 1, so it can
never contradict the side published before it. The side and the total are two readings of <strong>one fitted system</strong>:
a publication order is not two independent confirmations — CR05 measured the pair at r = %s (n = %s), which is exactly
what lets them disagree.</p>
%s
<h2>2. Week 11 markets, in publication order</h2>
<p class="note"><code>fair_minus_market</code> is blank in every row: no market line has been recorded under an authorised
source (Flags F07, F16, F51). <code>fair_minus_reference</code> is populated because both of its terms are this project's
own numbers, and the reference line is a naive benchmark, not a price (Flag F32).</p>
%s
<h2>3. Internal consistency, game by game</h2>
<p class="note">Three checks per game, run against the published file. The tolerances are the published rounding, not a
fudge factor: the model writes team scores to one decimal and margin and total to two, so a gap of up to 0.10 is rounding
(Flag F57) while a one-point disagreement would be a different thing.</p>
%s
<p class="note">Re-run with <code>python3 scripts/originate.py</code>. The audit is rewritten from the published files
each time, so a model change that breaks consistency appears here rather than as a silent discrepancy.</p>
""" % (tiles([(len(orig_view), "markets published"), (len({r["game_no"] for r in orig_view}), "games"),
             (audit_ok, "checks consistent"), (audit_bad, "checks not consistent")]),
       cr05["value"], cr05["n"],
       table(contract_view, ["stage", "market", "must_be_produced_from", "must_not_use", "published_columns",
                             "if_a_market_line_is_missing", "blocking_condition", "source_url"],
             {"stage": "Stage", "market": "Market", "must_be_produced_from": "Produced from",
              "must_not_use": "Must not use", "published_columns": "Published columns",
              "if_a_market_line_is_missing": "If no market line", "blocking_condition": "Blocking condition",
              "source_url": "Source"}),
       table(orig_view, ["row_id", "week_label", "game_no", "matchup", "kickoff_local_date", "market_seq",
                         "market_name", "selection", "model_fair_line", "market_line", "fair_minus_market",
                         "reference_line", "fair_minus_reference", "consistency_check", "status", "source_url"],
             {"row_id": "ID", "week_label": "Wk", "game_no": "#", "matchup": "Game", "kickoff_local_date": "Kickoff",
              "market_seq": "Order", "market_name": "Market", "selection": "Selection",
              "model_fair_line": "Model fair line", "market_line": "Market line",
              "fair_minus_market": "Fair − market", "reference_line": "Reference line",
              "fair_minus_reference": "Fair − reference", "consistency_check": "Consistency", "status": "Status",
              "source_url": "Game page"}, table_id="orig-table", filterable=True),
       table(audit_view, ["game_key", "matchup", "week", "score_grid_reconstructs_margin",
                          "score_grid_reconstructs_total", "moneyline_reproduces_from_side", "tolerance_applied",
                          "verdict", "source_url"],
             {"game_key": "Game key", "matchup": "Matchup", "week": "Wk", "score_grid_reconstructs_margin":
              "Scores → margin", "score_grid_reconstructs_total": "Scores → total", "moneyline_reproduces_from_side":
              "Moneyline ← side", "tolerance_applied": "Tolerance", "verdict": "Verdict", "source_url": "Source"},
             table_id="audit-table", filterable=True)))

pages["staking-ledger.html"] = ("Staking ledger", """
<h1>Staking ledger</h1>
<p class="note">The brief keeps <strong>signal</strong> and <strong>staking</strong> apart so a lucky run of bets cannot
disguise a bad forecast. That only works if the two are computed in different places, so this block is produced by its own
script and written to a file the ranking step never reads. The signal rank below is copied through from the leaderboard;
nothing to its right can move it.</p>
%s
<h2>1. Assumptions, stated in the file</h2>
<p class="note"><strong>Payout:</strong> %s. Every unit figure here is a units-against-the-reference-line number under
that assumption — not a return, not an ROI, and not comparable with a bookmaker result, because there is no price (Flags
F07, F16, F51). A <code>roi_units_pct</code> column is published only because the payout is declared in the same row: it is
units divided by stakes under that flat assumption, nothing more. Moneyline rows would need a price to settle and are
excluded from the unit ledger entirely.</p>
<h2>2. Signal rank against staking outcome</h2>
%s
<h2>3. The luck canary</h2>
<p class="note">%s</p>
<p class="note">The simulation asks the honest version of "could this run be luck": each strategy keeps its own bet count
and hit rate and the sequence is redrawn (%s draws, seed %s), so it measures what <em>no skill at all</em> would produce —
and it takes the maximum over the whole family, which is where selection bias lives. Under that model the best run among
the %s strategies averages %s units and its 95th percentile is %s; the observed best is %s, reached or beaten by chance in
%s of draws. It assumes independence across strategies, which is conservative here because the strategies share games, so
the true spread of lucky runs is wider and this probability is if anything understated.</p>
<h2>4. Why the split is structural, not cosmetic</h2>
<ul class="findings">
<li><strong>The order does not follow the money.</strong> %s ranks %s on signal and %s on units won: the staking column
moved and the rank did not. Had the run decided the order, a two-unit difference in a coin-flip sequence would have moved
a strategy up the board. The divergence column reports this as a watch item rather than silently absorbing it.</li>
<li><strong>Uncertainty is shown, not hidden.</strong> Units carry a bootstrap interval over the actual sequence; the win
probability interval is exact; and the number of decided bets is printed on every row, so a 10-bet record cannot be read
as a settled one (R1 and P1 are the two that most need that warning).</li>
<li><strong>Nothing here demotes anything.</strong> Demotion is a separate gate with its own thresholds, on
<a href="demotion-gates.html">Demotion gates</a>.</li>
</ul>
""" % (tiles([(len(stake_rows), "strategies staked"), (str(stake_canary["observed_best_units"]),
             "best observed run (units)"), (canary_p, "P(chance alone gets that run)"),
             (str(sum(1 for r in stake_rows if r["rank_divergence"] != "OK")), "signal/staking divergences")]),
       stake_canary["payout_assumption"],
       table(stake_view, ["strategy_id", "strategy", "market", "signal_rank", "signal_skill_points", "signal_q_bh",
                          "n_bets", "wins", "losses", "push", "win_rate", "binom_p_one_sided_vs_coin",
                          "units_even_money", "roi_units_pct", "units_boot_ci_low", "units_boot_ci_high",
                          "max_drawdown_units", "longest_win_streak", "longest_loss_streak", "mean_edge_points",
                          "bet_coverage_of_eligible_games", "staking_rank_by_units", "rank_divergence", "canary",
                          "payout_assumption", "source_url"],
             {"strategy_id": "ID", "strategy": "Strategy", "market": "Market", "signal_rank": "Signal rank",
              "signal_skill_points": "Signal skill (pts)", "signal_q_bh": "BH q", "n_bets": "Bets", "wins": "W",
              "losses": "L", "push": "Push", "win_rate": "Hit rate", "binom_p_one_sided_vs_coin": "p vs coin (exact)",
              "units_even_money": "Units", "roi_units_pct": "Units ROI*", "units_boot_ci_low": "Units CI low",
              "units_boot_ci_high": "Units CI high", "max_drawdown_units": "Max drawdown", "longest_win_streak":
              "Best streak", "longest_loss_streak": "Worst streak", "mean_edge_points": "Mean edge (pts)",
              "bet_coverage_of_eligible_games": "Coverage", "staking_rank_by_units": "Staking rank",
              "rank_divergence": "Divergence", "canary": "Canary", "payout_assumption": "Payout assumption",
              "source_url": "Source"}),
       stake_canary["reading"], stake_canary["draws"], stake_canary["seed"],
       stake_canary["strategies_in_the_family"], stake_canary["expected_best_units_with_no_skill_mean"],
       stake_canary["expected_best_units_with_no_skill_p95"], stake_canary["observed_best_units"], canary_p,
       m2_row["strategy_id"], m2_row["signal_rank"], m2_row["staking_rank_by_units"]))
pages["replacement-depth.html"] = ("Replacement depth", """
<h1>Replacement depth</h1>
<p class="note">The brief asks not "who is out" but <strong>how deep the fall is when the starter is out</strong>. This is
the slot-led detail register: for each affected position it records how many charted bodies stand between the absent
player and the next one, and how much of that depth the same unit of absence has already consumed. It is deliberately a
<em>separate file</em> from the availability-led register, joined by game number, so a correction in one cannot silently
rewrite the other.</p>
%s
<h2>1. What counts as verified here</h2>
<p class="note">Both club chart pages read for this register label themselves <strong>unofficial</strong> and carry no
date — "Unofficial Depth Chart Compiled by Lions Football Communications", and a chart "published by the writers of
Patriots.com". They are the clubs' own publications, which is the closest thing to an official depth source that exists
(Flags F45, F18), and the read date is recorded on every row because a chart is an alignment snapshot that decays. The
availability label comes from the league's own report; the depth position comes from the club chart; the two are not the
same kind of statement and are not merged into one column.</p>
<h2>2. The register</h2>
<p class="note"><em>Depth consumed</em> names the other absences at the same slot in the same game, so a reader can see
whether a backup is the first next man up or the third. <em>Shared backup</em> flags a single body covering two vacancies.
<em>Why blank</em> is filled whenever a field is empty on purpose.</p>
%s
<h2>3. Three things this register is built to show</h2>
<ul class="findings">
<li><strong>A replacement can be the last body in the unit.</strong> At Detroit's centre slot two bodies are charted and
one is Out, so the "first replacement available" is the final name on the page (RD-02). At left guard in Foxborough the
ratio is two of two, and the single remaining body is itself listed questionable and charted at <em>both</em> guard slots
(RD-06) — one player covering two vacancies.</li>
<li><strong>A returner standing in for a receiver is not the same event as a third receiver rising to first.</strong> Both
are one line of chart text and completely different exposures (RD-01 against the returner entry at RD-05).</li>
<li><strong>Absences do not arrive one at a time.</strong> The <em>depth consumed in the unit</em> field is what stops a
count of absent players being read as a count of depth problems — the failure mode the brief named (information gap
G13). RD-11 is the mirror case: an absence two lines down the chart is recorded as such so it is not counted like a
starter problem.</li>
</ul>
<h2>4. What is left blank, and why</h2>
%s
<p class="note">Where a player on the league's availability report appears on <strong>no row at all</strong> of his club's
chart, the depth fields are left blank with that stated as the reason, rather than filled from a third-party chart the
official-source rule excludes. A chart omission means "this source cannot place him", not "he is fine" (F62, suggestion
S33). Rows RD-13 and RD-14 are blank for a different reason again — no chart captured for that club this week, and a
player on the chart who is not on the league report — which is recorded rather than guessed.</p>
""")

pages["correlations.html"] = (pages["correlations.html"][0], pages["correlations.html"][1] + """
<h2>Session e4e71368: the computed register</h2>
<p class="note">The audit above states the rule; the register below runs it. Every published value names both variables,
states each one's kind and provenance, and carries n, a 95% interval, a two-sided p-value, and the smallest association a
sample that size could have detected at 80% power. That last column is the one that matters when a value is small: at
n = %s the sample could only have found |r| at or above %s, so "not significant" there is a statement about the sample,
not about independence.</p>
%s
<ul class="findings">
<li><strong>Two rows carry no value, for two different reasons.</strong> CR08 passed the provenance gate but has no
settled sample — the Week 10 games whose outcomes it needs were unplayed at the read. CR09 was rejected by the gate
because its only available inputs are two self-labelled unofficial club charts. Both stay blank; neither is quietly
dropped from the register.</li>
<li><strong>The parlay association is reproduced, and its size is not resolvable.</strong> Rebuilding the tickets from the
box scores with the rule the project registers reproduces the published P1 counts and its phi of %s exactly; the
alternative "our number was closer" rule gives −0.365. The sign is stable across definitions, the magnitude is not, at
n = %s.</li>
<li><strong>Two readings of one fit are not two confirmations.</strong> The model's side line and the model's total line
correlate at r = %s (n = %s), so they can and do disagree; a same-game ticket built from both is not hedged by the pair.</li>
</ul>
""" % (cr06["n"], cr06["smallest_abs_r_detectable_at_80pct_power"],
       table(corr_view, ["corr_id", "question", "variable_a", "variable_a_kind", "variable_b", "variable_b_kind",
                         "provenance_gate", "method", "value", "n", "ci_low", "ci_high", "p_value",
                         "smallest_abs_r_detectable_at_80pct_power", "reading", "source_url"],
             {"corr_id": "ID", "question": "Question", "variable_a": "X", "variable_a_kind": "X kind",
              "variable_b": "Y", "variable_b_kind": "Y kind", "provenance_gate": "Provenance gate",
              "method": "Method", "value": "Value", "n": "n", "ci_low": "95% CI low", "ci_high": "95% CI high",
              "p_value": "p (two-sided)", "smallest_abs_r_detectable_at_80pct_power": "Smallest detectable |r|",
              "reading": "Reading", "source_url": "Source"},
             table_id="corr-reg-table", filterable=True),
       cr06["value"], cr06["n"], cr05["value"], cr05["n"]))

pages["demotion-gates.html"] = ("Demotion gates", """
<h1>Demotion gates</h1>
<p class="note">A gate written down but never evaluated is not a control. The proposed conditions are on
<a href="markets.html">Market tables</a>; this page runs each of them against measured numbers for every strategy on the
board, so a threshold can be argued about with a number beside it. <strong>No strategy is live today</strong>, so nothing
is demoted — the verdict column says what the rule <em>would</em> do.</p>
%s
<h2>1. Triggers, and what each one is for</h2>
<p class="note">D7's "closing line value worse than zero for two consecutive windows" is kept <em>not computable</em>:
there is no closing market line at all (Flags F07, F16), and an unmeasurable rule must not read as a passed one. Two
triggers added here are labelled as new so they are not mistaken for the owner's list: D8 (the results feed has not
updated within its window) and D9 (a market reached kickoff with no closing capture).</p>
<h2>2. The evaluation</h2>
%s
<h2>3. What the numbers say</h2>
<ul class="findings">
<li><strong>D1 as drafted fires on all four ridge variants.</strong> Over the most recent 50 out-of-sample games the mean
advantage over the reference line is positive for every one of them (M1: %s), but each 95%% bootstrap interval includes
zero, so a rule of "lower bound above zero" demotes the whole board. A gate that always fires distinguishes nothing — this
is decision D13 and suggestion S34, and it agrees with session 8a0bf37e's independent window check.</li>
<li><strong>D2 reproduces the published q-values exactly.</strong> Adjusting over the %s strategies that have a skill test
gives the numbers the leaderboard publishes; adjusting over all %s rows would raise every q by %.4f times. Both
conventions give the same verdict today, and the convention is now recorded rather than assumed (Flag F56).</li>
<li><strong>D5 already fires.</strong> The rights and jurisdiction flags that suspend a strategy are open, so every row
fires — correct behaviour for a suspend-first gate, and a reminder that the statistical gates sit downstream of an
unresolved legal question (Flags F16, F09, F19).</li>
<li><strong>D6 cannot fire by construction, and that is the design.</strong> Units, drawdown and streaks are written to a
file the ranking step never reads, so no staking run can move a rank; the check measures the resulting order rather than
trusting the intention (<a href="staking-ledger.html">Staking ledger</a>).</li>
</ul>
<p class="note">Re-run with <code>python3 scripts/demote.py</code>. Thresholds are proposals and are not owner-approved
values (Flag F17). The store-level re-check in <code>python3 scripts/verify_stores.py</code> recomputes the D1 error
series and the D2 adjustment from the published columns, so this page cannot silently disagree with the leaderboard.</p>
""" % (tiles([(len(demo_eval), "trigger evaluations"), (demo_fire, "would fire"), (demo_nc, "not computable"),
             (demo_rules, "triggers (D1–D7 as proposed, D8–D9 new)")]),
       table(demo_view, ["evaluation_id", "rule_id", "rule_definition", "strategy_id", "measured_value", "window",
                         "threshold_proposed", "verdict", "reason", "action_if_fires", "new_this_session",
                         "source_url"],
             {"evaluation_id": "ID", "rule_id": "Rule", "rule_definition": "Rule as defined", "strategy_id":
              "Strategy", "measured_value": "Measured value", "window": "Window", "threshold_proposed":
              "Proposed threshold", "verdict": "Verdict", "reason": "Reason", "action_if_fires": "Action if fires",
              "new_this_session": "New here", "source_url": "Source"},
             table_id="demo-table", filterable=True),
       d1_m1, bh_family, len(leaderboard), bh_factor))

pages["executive-summary.html"] = (pages["executive-summary.html"][0], pages["executive-summary.html"][1] + """
<h2>Line book, results feed, origination, staking, depth and gates (session e4e71368, 2026-11-14)</h2>
<ul class="findings">
<li><strong>Line book.</strong> %s opening snapshots across %s games are recorded for the markets this project originates,
each tied to the commit that published it and timed against the official kickoff. Market prices stay blank by rule — an
opening number for a line we publish is a first-party fact; a bookmaker price is not something we hold (Flags F07, F16).
No closing window has elapsed yet. <a href="line-book.html">Line book</a></li>
<li><strong>Results feed.</strong> %s fixtures: %s settled finals that reconcile to the official standings for all 32
clubs with 0 mismatches, and %s recorded as scheduled and unsettled with no score and no grade. All %s originated markets
join to a feed row; %s are pending because their game has not been played.
<a href="results-feed.html">Results feed</a></li>
<li><strong>Origination.</strong> %s Week 11 markets in side → total → moneyline order, with the moneyline derived from
the side; %s of %s internal consistency checks pass, and the %s that do not are published rounding (a tenth of a point on
the score grid), recorded as F57 rather than smoothed away. <a href="origination.html">Origination</a></li>
<li><strong>Staking kept apart from signal.</strong> Units, drawdown, streaks and a bootstrap interval are computed by a
separate script into a file the ranking step never reads — which is what makes the separation checkable rather than
rhetorical. The best run in the family (+%s units) is reached by chance alone in %s of no-skill simulations, and the
staking order and the signal order do not coincide. <a href="staking-ledger.html">Staking ledger</a></li>
<li><strong>Replacement depth.</strong> %s slot records, %s carrying a depth position verified against a club chart read
the same day and %s left blank with the reason. Two club charts omit a player the league report lists as Out or
Questionable entirely, which is recorded as a source inconsistency (F62) rather than filled in.
<a href="replacement-depth.html">Replacement depth</a></li>
<li><strong>Correlations and gates.</strong> %s correlation rows with n, interval and the smallest detectable |r|
published beside every value; %s demotion trigger evaluations against measured numbers, of which %s would fire today and
%s are not computable because the input does not exist. <a href="correlations.html">Correlations</a> ·
<a href="demotion-gates.html">Demotion gates</a></li>
<li><strong>Store-level checks.</strong> <code>python3 scripts/verify_stores.py</code> re-runs 11 independent checks over
every file this session wrote — values against their published sources, timing against the official schedule, market cells
empty, standings reconciliation, join integrity, reproduced q-values and reproduced correlations. It is the one command
that says whether the six stores still agree with the records they came from.</li>
<li><strong>Nothing in this block settles or grades a Week 10 game.</strong> At the read, the Sunday 15 November fixtures
were still unplayed on the league's own pages, so they are recorded as scheduled and unsettled.</li>
</ul>
""" % (lb_open, len(lb_by_game), len(rf_feed), rf_settled, rf_unsett, rf_summary["grade_rows"], rf_pending,
       len(orig_view), audit_ok, len(orig_audit), len(orig_audit) - audit_ok,
       str(stake_canary["observed_best_units"]), canary_p, len(depth_detail), depth_ok_count,
       len(depth_blank_view), len(corr_reg), len(demo_eval), demo_fire, demo_nc))

NAV = NAV + [("line-book.html", "Line book"), ("results-feed.html", "Results feed"),
             ("origination.html", "Origination"), ("staking-ledger.html", "Staking ledger"),
             ("replacement-depth.html", "Replacement depth"), ("demotion-gates.html", "Demotion gates")]
HOME_CARDS = """
{card('line-book.html', 'Line book', 'Opening and closing numbers for the markets this project originates, timed and linked; no market price.')}
{card('results-feed.html', 'Results feed', 'Every 2026 fixture with an explicit settlement state, and what each originated market is waiting for.')}
{card('origination.html', 'Origination', 'Side, then total, then moneyline — with the arithmetic re-run against the published file.')}
{card('staking-ledger.html', 'Staking ledger', 'Units, drawdown and streaks, computed apart from the rank so a lucky run cannot move it.')}
{card('replacement-depth.html', 'Replacement depth', 'How many bodies stand between an absent starter and the next man up, per slot.')}
{card('demotion-gates.html', 'Demotion gates', 'Every proposed trigger evaluated against measured numbers, with what it would do today.')}
"""
pages["index.html"] = (pages["index.html"][0], pages["index.html"][1].replace(
    """{card('depth-deficiency.html', 'Deficiency tracking', 'Unit exposure by side of ball, and officially named starters and replacements.')}\n""",
    """{card('depth-deficiency.html', 'Deficiency tracking', 'Unit exposure by side of ball, and officially named starters and replacements.')}\n"""
    + HOME_CARDS))
