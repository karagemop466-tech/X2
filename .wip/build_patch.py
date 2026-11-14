# ---------- session e4e71368: line book, results feed, origination, staking, depth, gates ----
import json as _json
import collections as _coll


def read_json(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return _json.load(f)


def with_link(rows, url):
    out = []
    for r in rows:
        d = dict(r)
        d["source_url"] = url
        out.append(d)
    return out


lb_rows = read_csv("line_book_snapshots.csv")
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
lb_view = with_link(lb_rows, GITHUB_DATA + "line_book_snapshots.csv")
rf_view = [{"week": r["season_week"], "game_no": r["game_no"], "matchup": r["matchup"],
            "record_status": r["record_status"], "away_team": r["away_team"], "away_points": r["away_points"],
            "home_team": r["home_team"], "home_points": r["home_points"], "margin": r["margin"],
            "total_points": r["total_points"], "source_url": r["source_url"]} for r in rf_feed]
grade_view = with_link(rf_grades, GITHUB_DATA + "results_feed.csv")
orig_view = with_link(orig_rows, GITHUB_DATA + "originated_markets_week11.csv")
audit_view = with_link(orig_audit, GITHUB_DATA + "originated_markets_week11.csv")
contract_view = with_link(orig_contract, GITHUB_DATA + "originated_markets_week11.csv")
stake_view = with_link(stake_rows, GITHUB_DATA + "staking_book.csv")
depth_view = with_link(depth_detail, GITHUB_DATA + "replacement_depth_detail_week10_2026.csv")
corr_view = with_link(corr_reg, GITHUB_DATA + "correlation_register.csv")
demo_view = with_link(demo_eval, GITHUB_DATA + "demotion_evaluation.csv")
depth_blank_view = [r for r in depth_view if not r["levels_down"]]
depth_ok_count = len(depth_detail) - len(depth_blank_view)

lb_by_game = _coll.OrderedDict()
for r in lb_rows:
    lb_by_game.setdefault((r["season_week"], r["matchup"]), []).append(r)
lb_open = sum(1 for r in lb_rows if r["snapshot_kind"] == "opening")
lb_closed = sum(1 for r in lb_rows if r["closing_status"] != "window open")
rf_settled = sum(1 for r in rf_feed if r["record_status"] == "SETTLED-FINAL")
rf_unsett = len(rf_feed) - rf_settled
rf_pending = rf_summary["grade_rows"] - rf_summary["graded_rows"]
audit_ok = sum(1 for r in orig_audit if r["verdict"] == "consistent")
audit_bad = len(orig_audit) - audit_ok
clubs_read = sorted({r["team"] for r in depth_detail})
demo_fire = sum(1 for r in demo_eval if r["verdict"] == "FIRES")
demo_nc = sum(1 for r in demo_eval if r["verdict"] == "NOT COMPUTABLE")
demo_rules = len({r["rule_id"] for r in demo_eval})
cr_by_id = {r["corr_id"]: r for r in corr_reg}
cr06, cr05 = cr_by_id["CR06"], cr_by_id["CR05"]
bh_family = len(leaderboard) - 1
bh_factor = len(leaderboard) / bh_family
d1_m1 = next(r["measured_value"] for r in demo_eval
             if r["rule_id"] == "D1" and r["strategy_id"] == "M1")
canary_p = str(stake_canary["p_chance_alone_matches_or_beats_best"])
m2_row = stake_view[1]

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
%s
<p class="note">Every snapshot is timed against the official kickoff for its game. A line first published <em>after</em>
kickoff is excluded rather than recorded as an opening number, so the ledger cannot quietly fill itself with retrospective
numbers. Re-check with <code>python3 scripts/line_book.py --check</code>.</p>
<h2>2. The ledger</h2>
<p class="note">One row per market per snapshot. <em>Model fair line</em> is our published number. <em>Reference line</em>
is the naive benchmark this project grades against and is labelled as such — it is not a market price (Flag F32). Kickoff
dates come from the <a href="https://www.nfl.com/schedules/2026/by-week/week-11" target="_blank" rel="noopener">official
Week 11 schedule</a>.</p>
%s
<h2>3. Where this goes next</h2>
<ul class="findings">
<li><strong>Closing numbers are not missing by oversight.</strong> No game in this ledger has reached kickoff since the
store was built, so all %s closing windows are open. The cadence that would close them is an owner decision (Q43, D11,
suggestion S29).</li>
<li><strong>A closing number cannot be recovered after the fact.</strong> If a capture is missed the row says so; it is not
back-filled from a later line.</li>
<li><strong>The price-side tables written by session c125b2f7</strong> are on
<a href="markets.html">Market tables</a>. That session's note on where its reference prices came from is recorded as an
irregularity (F51), and the market cells stay blank here.</li>
</ul>
""" % (len(lb_rows),
       tiles([(len(lb_rows), "snapshots in the ledger"), (lb_open, "opening snapshots"),
              (lb_closed, "closing windows closed"), (len(lb_by_game), "games covered")]),
       table(contract_view, ["field", "rule", "why", "status", "source_url"],
             {"field": "Field", "rule": "Rule", "why": "Why", "status": "Status", "source_url": "Source"}),
       table(lb_view, ["ledger_seq", "season_week", "game_no", "matchup", "market", "selection", "snapshot_kind",
                       "snapshot_at", "closing_status", "model_fair_line", "market_line", "fair_minus_market",
                       "reference_line", "fair_minus_reference", "provenance", "source_url"],
             {"ledger_seq": "Seq", "season_week": "Wk", "game_no": "#", "matchup": "Game", "market": "Market",
              "selection": "Selection", "snapshot_kind": "Kind", "snapshot_at": "Snapshot at",
              "closing_status": "Closing", "model_fair_line": "Model fair line", "market_line": "Market line",
              "fair_minus_market": "Fair − market", "reference_line": "Reference line",
              "fair_minus_reference": "Fair − reference", "provenance": "Provenance", "source_url": "Source"},
             table_id="lb-table", filterable=True),
       len(lb_rows)))

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
scheduled and unsettled. Grading is permitted only against the first state: <code>scripts/results_feed.py grade</code>
raises if any unsettled row carries a grade. Of %s originated markets, %s are graded and %s are pending because their
fixture has not been played — the ten unplayed Week 10 games and all 13 of Week 11.</p>
<h2>2. The feed</h2>
%s
<h2>3. What each originated market is waiting for</h2>
<p class="note">The market, its fixture, the state of that fixture, and the number to be compared against. The
<em>market result</em> column stays blank until the fixture is settled; nothing here is graded on a forecast.</p>
%s
<h2>4. What this feed does not do</h2>
<ul class="findings">
<li><strong>It publishes no return.</strong> It records outcomes, not prices, so it makes outcome grading computable and
leaves monetary ROI blocked (Flags F07, F16).</li>
<li><strong>It is not the model's input.</strong> The feed and the backtest read the same transcribed finals; that shared
origin is stated wherever a check uses it, because a feed cannot validate the transcription it was built from.</li>
<li><strong>It keeps the LAR/LA alias visible</strong> — the standings use LAR and the schedule history use LA for the
same club. The reconciliation maps them to one club and says so (F55).</li>
<li><strong>One tie exists in %s settled games</strong> (week 5, Giants 27 at Commanders 27). It is kept as a tie rather
than absorbed into a side; the consequence for the moneyline is recorded as F58.</li>
</ul>
""" % (tiles([(len(rf_feed), "fixtures in the feed"), (rf_settled, "settled finals"),
             (rf_unsett, "scheduled, not settled"), (rf_pending, "originated markets awaiting settlement")]),
       rf_summary["grade_rows"], rf_summary["graded_rows"], rf_pending,
       table(rf_view, ["week", "game_no", "matchup", "record_status", "away_team", "away_points", "home_team",
                       "home_points", "margin", "total_points", "source_url"],
             {"week": "Wk", "game_no": "#", "matchup": "Matchup", "record_status": "Settlement state",
              "away_team": "Away", "away_points": "Away pts", "home_team": "Home", "home_points": "Home pts",
              "margin": "Margin", "total_points": "Total", "source_url": "Game page"},
             table_id="rf-table", filterable=True),
       table(grade_view, ["ledger_seq", "season_week", "game_no", "matchup", "market", "selection", "model_fair_line",
                          "feed_status", "settled_home_points", "settled_away_points", "market_result", "outcome",
                          "source_url"],
             {"ledger_seq": "Seq", "season_week": "Wk", "game_no": "#", "matchup": "Matchup", "market": "Market",
              "selection": "Selection", "model_fair_line": "Our line", "feed_status": "Fixture state",
              "settled_home_points": "Home pts", "settled_away_points": "Away pts", "market_result": "Market result",
              "outcome": "Outcome", "source_url": "Source"},
             table_id="rf-grade-table", filterable=True),
       rf_settled))

pages["origination.html"] = ("Origination", """
<h1>Origination</h1>
<p class="note">What the pipeline puts out for each game, in the order the brief specifies, with the arithmetic re-run
against the published model file rather than restated from memory. Read it with
<a href="model-lines.html">Model and Week 11 lines</a>, which holds the model itself.</p>
%s
<h2>1. The order, and what it does and does not buy</h2>
<p class="note">Side first, then the total, then the moneyline. The moneyline is <em>derived</em> from stage 1, so it can
never contradict the side published before it. The side and the total are two readings of <strong>one fitted system</strong>:
a publication order is not two independent confirmations — CR05 measured the pair at r = %s (n = %s), which is what lets
them disagree.</p>
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
       cr05["r"], cr05["n"],
       table(contract_view, ["field", "rule", "why", "status", "source_url"],
             {"field": "Field", "rule": "Rule", "why": "Why", "status": "Status", "source_url": "Source"}),
       table(orig_view, ["game_no", "matchup", "kickoff_date", "market", "selection", "model_fair_line",
                         "market_line", "fair_minus_market", "reference_line", "fair_minus_reference", "source_url"],
             {"game_no": "#", "matchup": "Game", "kickoff_date": "Kickoff", "market": "Market", "selection": "Selection",
              "model_fair_line": "Model fair line", "market_line": "Market line", "fair_minus_market": "Fair − market",
              "reference_line": "Reference line", "fair_minus_reference": "Fair − reference",
              "source_url": "Game page"}, table_id="orig-table", filterable=True),
       table(audit_view, ["game_no", "matchup", "check", "gap", "tolerance_applied", "verdict", "source_url"],
             {"game_no": "#", "matchup": "Game", "check": "Check", "gap": "Gap", "tolerance_applied": "Tolerance",
              "verdict": "Verdict", "source_url": "Source"}, table_id="audit-table", filterable=True)))

pages["staking-ledger.html"] = ("Staking ledger", """
<h1>Staking ledger</h1>
<p class="note">The brief keeps <strong>signal</strong> and <strong>staking</strong> apart so a lucky run of bets cannot
disguise a bad forecast. That only works if the two are computed in different places, so the staking block is produced by
its own script and written to a file the ranking step never reads. The signal rank below is copied through from the
leaderboard; nothing to its right can move it.</p>
%s
<h2>1. Assumptions, stated in the file</h2>
<p class="note"><strong>Payout:</strong> %s. Every unit figure here is a units-against-the-reference-line number under
that assumption — not a return, not an ROI, and not comparable with a bookmaker result, because there is no price (Flags
F07, F16, F51). Moneyline rows would need a price to settle and are excluded from the unit ledger entirely.</p>
%s
<h2>2. Signal rank against staking outcome</h2>
%s
<h2>3. The luck canary</h2>
<p class="note">%s The simulation asks the honest version of "could this run be luck": each strategy keeps its own hit
rate and the sequence is redrawn, so it measures what <em>no skill at all</em> would produce with the same number of bets —
and it takes the maximum over the whole family, which is where selection bias lives. It assumes independence across
strategies, which is conservative here: the strategies share games, so the true spread of best-of-family runs is wider and
the chance-alone probability is if anything understated.</p>
<h2>4. Why the split is structural, not cosmetic</h2>
<ul class="findings">
<li><strong>The order does not follow the money.</strong> %s ranks %s on signal and %s on units won: the staking column
moved and the rank did not. Had the run decided the order, a two-unit difference in a coin-flip sequence would have moved
a strategy up the board.</li>
<li><strong>Uncertainty is shown, not hidden.</strong> Units carry a bootstrap interval over the actual sequence; the win
probability interval is exact (Clopper-Pearson); and the number of decided bets is printed on every row so a 10-bet
record cannot be read as a settled one.</li>
<li><strong>Nothing here demotes anything.</strong> Demotion is a separate gate with its own thresholds, on
<a href="demotion-gates.html">Demotion gates</a>.</li>
</ul>
""" % (tiles([(len(stake_rows), "strategies staked"), (str(stake_canary["observed_best_run_units"]),
             "best observed run (units)"), (canary_p, "P(chance alone gets that run)"),
             (str(sum(1 for r in stake_rows if r["rank_divergence"] != "OK")), "signal/staking divergences")]),
       stake_canary["payout"],
       table(orig_contract, ["field", "rule", "why", "status", "source_url"],
             {"field": "Field", "rule": "Rule", "why": "Why", "status": "Status", "source_url": "Source"}),
       table(stake_view, ["strategy_id", "signal_rank", "staking_rank_by_units", "rank_divergence", "record", "units",
                          "units_ci_low", "units_ci_high", "max_drawdown_units", "longest_win_streak",
                          "longest_loss_streak", "bets_decided", "units_assumption", "staking_status", "source_url"],
             {"strategy_id": "Strategy", "signal_rank": "Signal rank", "staking_rank_by_units": "Staking rank",
              "rank_divergence": "Divergence", "record": "W-L", "units": "Units", "units_ci_low": "Units CI low",
              "units_ci_high": "Units CI high", "max_drawdown_units": "Max drawdown",
              "longest_win_streak": "Best streak", "longest_loss_streak": "Worst streak",
              "bets_decided": "Decided bets", "units_assumption": "Payout assumption",
              "staking_status": "Staking state", "source_url": "Source"}),
       stake_canary["reading"],
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
(Flags F45, F18), and the fetch date is recorded on every row because a chart is an alignment snapshot that decays.</p>
<h2>2. The register</h2>
<p class="note"><em>Depth consumed</em> names the other absences at the same slot in the same game, so a reader can see
whether a backup is the first next man up or the third. <em>Shared backup</em> flags a single body covering two vacancies.
<em>Why blank</em> is filled whenever a field is empty on purpose.</p>
%s
<h2>3. Three things this register is built to show</h2>
<ul class="findings">
<li><strong>A replacement can be the last body in the unit.</strong> At Detroit's centre slot two bodies are charted and
one is Out, so the "first replacement available" is the final name on the page (RD-02). At left guard in Foxborough the
ratio is two of two, and the single remaining body is itself listed Questionable and charted at <em>both</em> guard slots
(RD-06) — one player covering two vacancies.</li>
<li><strong>A special-teamser standing in for a receiver is not the same event as a WR3 rising to WR1.</strong> Both are
one line of chart text and completely different exposures (RD-01 against the punt-returner entry at RD-05).</li>
<li><strong>Absences do not arrive one at a time.</strong> The <em>depth consumed in unit</em> field is what stops a count
of absent players being read as a count of depth problems — the failure mode the brief named (information gap G13).</li>
</ul>
<h2>4. What is left blank, and why</h2>
%s
<p class="note">Where a player on the league's availability report appears on <strong>no row at all</strong> of his club's
chart, the depth fields are left blank with that stated as the reason, rather than filled from a third-party chart the
official-source rule excludes. A chart omission means "this source cannot place him", not "he is fine" (F62, suggestion
S33). The availability-led register is on <a href="depth-deficiency.html">Deficiency tracking</a>.</p>
""" % (tiles([(len(depth_detail), "slot records"), (depth_ok_count, "with a verified depth position"),
             (len(depth_blank_view), "blank by rule"), (len(clubs_read), "clubs read directly")]),
       table(depth_view, ["depth_id", "game_no", "week", "team", "pos_slot", "unavailable_player", "availability_label",
                          "levels_down", "next_body_up", "charted_bodies_at_slot", "depth_consumed_in_unit",
                          "shared_backup_note", "chain_note", "blank_reason", "chart_read_on", "source_url"],
             {"depth_id": "ID", "game_no": "#", "week": "Wk", "team": "Club", "pos_slot": "Slot",
              "unavailable_player": "Absent", "availability_label": "League label", "levels_down": "Levels down",
              "next_body_up": "Next body up", "charted_bodies_at_slot": "Charted bodies at slot",
              "depth_consumed_in_unit": "Depth consumed", "shared_backup_note": "Shared backup",
              "chain_note": "Chart chain", "blank_reason": "Why blank", "chart_read_on": "Chart read",
              "source_url": "Source"}, table_id="depth-table", filterable=True),
       table(depth_blank_view, ["depth_id", "game_no", "team", "pos_slot", "unavailable_player", "availability_label",
                                "blank_reason", "source_url"],
             {"depth_id": "ID", "game_no": "#", "team": "Club", "pos_slot": "Slot", "unavailable_player": "Absent",
              "availability_label": "League label", "blank_reason": "Why this row is blank", "source_url": "Source"})))

pages["correlations.html"] = (pages["correlations.html"][0], pages["correlations.html"][1] + """
<h2>Session e4e71368: the computed register</h2>
<p class="note">The audit above states the rule; the register below runs it. Every published value names both variables,
states each one's kind and provenance, and carries n, a 95% interval, a two-sided p-value, and the smallest association a
sample that size could have detected at 80% power. That last column is the one that matters when a value is small: at
n = %s the sample could only have found |r| at or above %s, so "not significant" there is a statement about the sample,
not about independence.</p>
%s
<ul class="findings">
<li><strong>Two rows are blank by rule, not for want of trying.</strong> One is blank because no leg has a settled result
yet (Week 10 Sunday was unplayed at the read); the other is rejected by the provenance gate because its only inputs are
two self-labelled unofficial club charts.</li>
<li><strong>The parlay association is reproduced, and its size is not resolvable.</strong> Rebuilding the tickets from the
box scores with the rule the project registers reproduces the published P1 counts and its phi of %s exactly; the
alternative "our number was closer" rule gives −0.365. The sign is stable across definitions, the magnitude is not, at
n = %s.</li>
<li><strong>Two readings of one fit are not two confirmations.</strong> The model's side line and the model's total line
correlate at r = %s (n = %s), so they can and do disagree; a parlay built from both is not hedged by the pair.</li>
</ul>
""" % (cr06["n"], cr06["smallest_abs_r_detectable_at_80pct_power"],
       table(corr_view, ["corr_id", "question", "x_variable", "x_kind", "x_provenance", "y_variable", "y_kind",
                         "y_provenance", "provenance_gate", "r", "n", "ci95_low", "ci95_high", "p_two_sided",
                         "smallest_abs_r_detectable_at_80pct_power", "reading", "blank_reason", "source_url"],
             {"corr_id": "ID", "question": "Question", "x_variable": "X", "x_kind": "X kind",
              "x_provenance": "X source", "y_variable": "Y", "y_kind": "Y kind", "y_provenance": "Y source",
              "provenance_gate": "Gate", "r": "r", "n": "n", "ci95_low": "CI low", "ci95_high": "CI high",
              "p_two_sided": "p", "smallest_abs_r_detectable_at_80pct_power": "Smallest detectable |r|",
              "reading": "Reading", "blank_reason": "Why blank", "source_url": "Source"},
             table_id="corr-reg-table", filterable=True),
       cr06["r"], cr06["n"], cr05["r"], cr05["n"]))

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
advantage over the reference line is positive for every one of them (M1: %s), but each 95% bootstrap interval includes
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
values (Flag F17).</p>
""" % (tiles([(len(demo_eval), "trigger evaluations"), (demo_fire, "would fire"), (demo_nc, "not computable"),
             (demo_rules, "triggers (D1–D7 as proposed, D8–D9 new)")]),
       table(demo_view, ["rule_id", "strategy_id", "measured_value", "window", "proposed_threshold", "verdict",
                         "reading", "proposed_action", "source_url"],
             {"rule_id": "Rule", "strategy_id": "Strategy", "measured_value": "Measured value", "window": "Window",
              "proposed_threshold": "Proposed threshold", "verdict": "Verdict", "reading": "Reading",
              "proposed_action": "Proposed action", "source_url": "Source"},
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
empty, standings reconciliation, join integrity, reproduced q-values and reproduced correlations. It is the single command
that says whether the six stores still agree with the records they came from.</li>
<li><strong>Nothing in this block settles or grades a Week 10 game.</strong> At the read, the Sunday 15 November fixtures
were still unplayed on the league's own pages, so they are recorded as scheduled and unsettled.</li>
</ul>
""" % (lb_open, len(lb_by_game), len(rf_feed), rf_settled, rf_unsett, rf_summary["grade_rows"], rf_pending,
       len(orig_view), audit_ok, len(orig_audit), len(orig_audit) - audit_ok,
       str(stake_canary["observed_best_run_units"]), canary_p, len(depth_detail), depth_ok_count,
       len(depth_blank_view), len(corr_reg), len(demo_eval), demo_fire, demo_nc))

NAV = NAV + [("line-book.html", "Line book"), ("results-feed.html", "Results feed"),
             ("origination.html", "Origination"), ("staking-ledger.html", "Staking ledger"),
             ("replacement-depth.html", "Replacement depth"), ("demotion-gates.html", "Demotion gates")]
