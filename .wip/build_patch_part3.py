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
