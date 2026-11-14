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
