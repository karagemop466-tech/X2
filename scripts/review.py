#!/usr/bin/env python3
"""Decision console: a review section where a path can actually be *chosen*.

The site's Suggestions page already lists proposals with a recommended path.  What
it could not do is record a choice, which is the difference between a report and a
decision tool.  This script closes that gap without adding any hand-typed NFL value:

* every proposal gets an explicit option set, the evidence behind it, the exact file
  a session would change, and what it unblocks;
* a choice is written to ``data/decision_choices.json`` and is then shown on the
  page as *decided*, with a date and the person who decided;
* **no choice is pre-filled.**  The file ships empty, so every row reads
  "awaiting owner choice" until a human records one.  Nothing in this repository
  claims to know the owner's mind.

The generated status is also machine-checked: a choice naming an unknown option or
an unknown proposal is a build error, not a silent typo.

Sources: this file adds no external claim.  Each row cites the official source that
makes the proposal necessary (NFL.com terms, NFL.com schedule/injury pages, NIST
statistical guidance, Dutch gambling law).
"""
import csv
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
CHOICES = os.path.join(DATA, "decision_choices.json")

AS_OF = "2026-11-14"

# ---------------------------------------------------------------------------
# The proposal set.  Each entry states: the question, three options, which option
# is recommended and why, the file a chosen option would change, and what it
# unblocks.  "blocks" is what stays stuck while the row is undecided.
# ---------------------------------------------------------------------------
PROPOSALS = [
    {
        "id": "P01",
        "area": "Market data",
        "question": "Where do the market's opening and closing numbers come from?",
        "why_it_matters": ("Without a market number there is no edge, no closing-line value, no "
                           "return on investment and no demotion rule that can fire. Every "
                           "market column in this project is blank because of this one gap (F07)."),
        "option_a": "Licence a historical odds archive with explicit model-use rights",
        "option_b": "Keep every market column blank and publish forecast-only research",
        "option_c": "Scrape public sportsbook pages (not an official source; terms unreviewed)",
        "recommended": "B now, A if a priced result is ever required",
        "why": ("B is the only option that is both honest and free. C breaks the official-source "
                "rule this whole repository is built on. A costs money that has not been budgeted."),
        "files_changed": "data/price_snapshots.csv, data/line_comparison_week11.csv",
        "unblocks": "ROI, closing-line value, staking comparison, demotion rule D3",
        "blocks": "Every priced claim, every ROI figure, every staking leaderboard",
        "cost": "A: licence cost unknown. B: zero. C: unacceptable under the project rule",
        "source_url": "https://support.nfl.com/hc/en-us/articles/35869698780564-If-I-place-a-bet-on-NFL-com-or-the-NFL-app-am-I-betting-with-the-NFL",
    },
    {
        "id": "P02",
        "area": "Player props",
        "question": "Should player props be originated, and from what outcome data?",
        "why_it_matters": ("The brief asks for player prop bet combos. NFL.com publishes per-player "
                           "game logs, so prop OUTCOMES are obtainable from an official source even "
                           "though prop PRICES are not. The repository currently holds no player-level "
                           "game series (F31), so no prop can be graded today."),
        "option_a": "Transcribe official NFL.com player game logs for the Week 11 slate and grade props",
        "option_b": "Keep props blocked and say so, with the exact list of what is missing",
        "option_c": "Publish props from a third-party projection with no graded outcome",
        "recommended": "A, scoped to the Week 11 participants only",
        "why": ("A is the only path that turns the brief's prop requirement into a measured answer "
                "using an official source. It must be scoped: the NFL terms restrict bulk retrieval "
                "(F16), so a full-league season of logs needs written permission first. C publishes "
                "an unverifiable number."),
        "files_changed": "data/player_game_logs_2026.csv (new), data/prop_markets_week11.csv",
        "unblocks": "Prop origination, prop correlations (X05/X06), prop-combo pricing",
        "blocks": "Every prop and prop-combo claim",
        "cost": "A: transcription effort plus a rights question (F16). B: zero. C: unacceptable",
        "source_url": "https://www.nfl.com/players/jared-goff/stats/logs/",
    },
    {
        "id": "P03",
        "area": "Injuries and depth",
        "question": "How is the size of an injury or a backup's drop-off measured, rather than assumed?",
        "why_it_matters": ("The brief asks for 2nd/3rd/4th-string depth to be tracked. This repository "
                           "holds one week of injury data and no official string order (F06), so the "
                           "depth of a replacement cannot be ranked and the size of an injury effect "
                           "cannot be estimated."),
        "option_a": "Collect weekly injury reports across a full season and a game-day inactive list per game",
        "option_b": "Keep depth rank blank and publish only the officially named replacement",
        "option_c": "Infer string order from a club depth chart that self-labels 'unofficial'",
        "recommended": "A, after written permission (F16); B in the meantime",
        "why": ("C is what F18/F45 already rejected: an unofficial chart that lists an injured "
                "player ahead of his replacement. A is the only route to a measured effect size, "
                "and it needs more weeks than one."),
        "files_changed": "data/injuries_*_2026.csv (new weeks), data/injury_impact_2026.csv",
        "unblocks": "Quantified injury adjustment, replacement-depth rank, event-risk sizing",
        "blocks": "Any injury-based model adjustment and any depth claim",
        "cost": "A: substantial transcription and a rights review. B: zero",
        "source_url": "https://www.nfl.com/injuries/",
    },
    {
        "id": "P04",
        "area": "Statistical thresholds",
        "question": "Who approves the validation cut-offs, and is the demotion rule one-sided or two-sided?",
        "why_it_matters": ("The eight gates and the demotion rules use numeric cut-offs that this "
                           "project chose, not the league or a regulator. As drafted, demotion rule D1 "
                           "returns all four side models to paper at n = 50 even though all four have "
                           "positive point estimates (F54). A rule that demotes everything carries no "
                           "information."),
        "option_a": "Approve the cut-offs as published",
        "option_b": "Amend D1: require a 100-forecast window or a one-sided test before demotion",
        "option_c": "Reject the cut-offs and keep the leaderboard descriptive only",
        "recommended": "B",
        "why": ("B keeps a real safety rule while removing the version that fires on noise. A "
                "locks in a rule the evidence contradicts. C removes a control the brief asks for."),
        "files_changed": "data/demotion_gate.csv, data/strategy_gates.csv, scripts/model.py",
        "unblocks": "A demotion gate that can actually be evaluated",
        "blocks": "Any statement that a strategy has been validated against an approved rule",
        "cost": "One decision; no data collection",
        "source_url": "https://www.itl.nist.gov/div898/handbook/eda/section3/eda352.htm",
    },
    {
        "id": "P05",
        "area": "Legal and rewards",
        "question": "Is any reward, entry fee or referral lawful for the owner's jurisdiction?",
        "why_it_matters": ("The leaderboard is described as a competition with rewards. The owner is "
                           "in the Netherlands; Dutch law (Wet op de kansspelen, Kansspelautoriteit) "
                           "has not been reviewed (F19), and Japan-specific official guidance "
                           "prohibits online sports betting from Japan (F09)."),
        "option_a": "Obtain a written legal review for the Netherlands before any reward exists",
        "option_b": "Keep rewards, entry fees and referrals disabled",
        "option_c": "Proceed with a reward on the basis of it having no monetary value",
        "recommended": "B now, A before anything of value is offered",
        "why": ("C assumes a legal conclusion the project has not obtained. B costs nothing and "
                "does not block the research, which is the part that works today."),
        "files_changed": "research/nl-legal-review.md, data/flags.csv",
        "unblocks": "A lawful reward mechanic, if one is wanted",
        "blocks": "Any reward, prize, entry fee or referral",
        "cost": "A: legal fees, unknown. B: zero",
        "source_url": "https://wetten.overheid.nl/BWBR0002469/2025-02-12",
    },
    {
        "id": "P06",
        "area": "Data rights",
        "question": "Is written permission needed to keep publishing NFL.com-derived data?",
        "why_it_matters": ("NFL.com terms prohibit systematic retrieval to compile a collection absent "
                           "express prior written consent (F16). This repository publishes a 347-row "
                           "injury snapshot transcribed from that site. No permission is recorded."),
        "option_a": "Request written permission and record the response",
        "option_b": "Freeze what exists and expand nothing until A is answered",
        "option_c": "Continue expanding collection and address the question later",
        "recommended": "B now, A in parallel",
        "why": ("B is the only option that does not increase exposure. C is what the terms most "
                "directly forbid."),
        "files_changed": "README.md, data/flags.csv (F16)",
        "unblocks": "Any further bulk collection from NFL.com",
        "blocks": "New bulk collection, additional seasons, automated retrieval",
        "cost": "B: zero. A: correspondence effort",
        "source_url": "https://support.nfl.com/hc/en-us/articles/35869743904916-NFL-com-Terms-and-Conditions",
    },
    {
        "id": "P07",
        "area": "Sample size",
        "question": "Should the project wait for more games before publishing any leaderboard rank?",
        "why_it_matters": ("89 out-of-sample games is one partial season. This session's own weekly "
                           "consistency check finds that the best rule's skill is positive but NOT "
                           "repeatable across weeks (5 of 7 weeks positive, sign-test p = 0.45). A rank "
                           "computed on that sample is a description, not a prediction."),
        "option_a": "Publish ranks now with the luck columns shown beside every one",
        "option_b": "Suppress ranks until a full season is graded",
        "option_c": "Publish ranks and omit the luck columns to keep the page simple",
        "recommended": "A, with the luck columns mandatory",
        "why": ("A plus the luck columns answers the brief's 'remove luck from the equation' ask "
                "better than hiding the ranks. C is the failure mode this session existed to fix."),
        "files_changed": "data/strategy_leaderboard.csv, docs/leaderboard.html",
        "unblocks": "A defensible leaderboard page",
        "blocks": "Any claim that the top-ranked rule is the best rule",
        "cost": "Zero; already built this session",
        "source_url": "https://www.itl.nist.gov/div898/handbook/prc/section1/prc16.htm",
    },
    {
        "id": "P08",
        "area": "Site architecture",
        "question": "Should the two parallel site generators (Python docs/ and Node src/) be merged?",
        "why_it_matters": ("The repository ships two independent static sites. Only the Python one is "
                           "published by GitHub Pages; the Node one is built but not deployed. Two "
                           "sources of truth for the same dashboard is a known way to publish "
                           "contradictory numbers."),
        "option_a": "Retire the Node generator and keep the Python site as the single source",
        "option_b": "Keep both and label which one is published",
        "option_c": "Merge them into one generator with one data layer",
        "recommended": "A",
        "why": ("The Python site is the one Pages serves and the one with the row-level source "
                "validator. Keeping a second unpublished generator doubles the maintenance surface "
                "for no reader benefit."),
        "files_changed": "package.json, src/",
        "unblocks": "One dashboard with one set of numbers",
        "blocks": "A single source of truth for the dashboard",
        "cost": "A: deletion, low risk. C: large refactor",
        "source_url": "https://github.com/karagemop466-tech/X2",
    },
    # P09 was appended to data/decision_console.csv directly by session cf85d485
    # (T107) instead of through this file, so review.py used to drop it on the next
    # run. Registered here on 2026-11-18 (session 60c8c865, T111) so the console
    # round-trips; its recorded choice lives in data/decision_choices.json.
    {
        "id": "P09",
        "area": "Backtest corpus",
        "question": "Adopt the 13 settled Week 10 games and the nine neutral-site flags, and re-publish the corpus metrics?",
        "why_it_matters": ("The published results feed holds 137 games while today's official "
                           "standings imply 150 through Week 10; every published metric is computed "
                           "on the 137-game corpus, and the international games carry no neutral flag, "
                           "so the fitted home-field term is applied at venues the official slate says "
                           "are neutral. Both facts change published numbers if adopted quietly."),
        "option_a": "Splice into data/games_2026_results.csv, re-fit, and re-publish every metric as v2",
        "option_b": "Publish a parallel v2 research register and keep v1 (137 games) frozen as the published record",
        "option_c": "Keep 137 games and disclose the 13-game gap on every table that uses the corpus",
        "recommended": "B",
        "why": ("The transcription is already reconciled (32 of 32 clubs match today's official "
                "standings once the 13 rows are added), and three side picks plus one bet-gate "
                "crossing turn on the neutral flags. A re-run therefore changes published numbers, "
                "so it should be visible as a version, not a quiet correction; C alone leaves a "
                "known-wrong corpus as the only number the site shows."),
        "files_changed": ("data/games_2026_results.csv, data/model_backtest.csv, "
                          "data/model_bets.csv, data/strategy_backtest_scores.csv, "
                          "data/control_baselines*.csv, data/leaderboard_control_runs.csv, "
                          "docs/** (generated)"),
        "unblocks": "D29 (corpus definition), and a corpus that matches the official standings",
        "blocks": "Nothing is blocked by waiting; the gap is disclosed on this build",
        "cost": "One re-run plus a version tag on the pages that show metrics",
        "source_url": "https://github.com/karagemop466-tech/X2/blob/main/data/week_count_reconciliation_2026-11-18.csv",
    },
]


def load_choices():
    if not os.path.exists(CHOICES):
        return {"as_of": AS_OF, "choices": {}}
    with open(CHOICES, encoding="utf-8") as f:
        return json.load(f)


def main():
    store = load_choices()
    choices = store.get("choices", {})
    errors = []

    known = {p["id"] for p in PROPOSALS}
    for key, val in choices.items():
        if key not in known:
            errors.append("decision_choices.json names an unknown proposal: %s" % key)
        elif val.get("choice") not in ("A", "B", "C"):
            errors.append("%s has an invalid choice %r (must be A, B or C)"
                          % (key, val.get("choice")))
        elif not val.get("decided_by") or not val.get("decided_on"):
            errors.append("%s is missing decided_by or decided_on" % key)

    rows = []
    for p in PROPOSALS:
        c = choices.get(p["id"], {})
        chosen = c.get("choice", "")
        rows.append({
            "proposal_id": p["id"],
            "area": p["area"],
            "question": p["question"],
            "option_a": p["option_a"],
            "option_b": p["option_b"],
            "option_c": p["option_c"],
            "recommended_now": p["recommended"],
            "why_recommended": p["why"],
            "recorded_choice": chosen,
            "choice_reason": c.get("reason", ""),
            "decided_by": c.get("decided_by", ""),
            "decided_on": c.get("decided_on", ""),
            "status": ("DECIDED - %s" % chosen) if chosen else "awaiting owner choice",
            "files_a_session_would_change": p["files_changed"],
            "unblocks": p["unblocks"],
            "blocks": p["blocks"],
            "cost": p["cost"],
            "source_url": p["source_url"],
        })

    out = os.path.join(DATA, "decision_console.csv")
    fields = ["proposal_id", "area", "question", "option_a", "option_b", "option_c",
              "recommended_now", "why_recommended", "recorded_choice", "choice_reason",
              "decided_by", "decided_on", "status", "files_a_session_would_change",
              "unblocks", "blocks", "cost", "source_url"]
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    if not os.path.exists(CHOICES):
        with open(CHOICES, "w", encoding="utf-8") as f:
            json.dump({"as_of": AS_OF, "how_to_use": [
                "Every proposal is undecided until a human edits",
                "data/decision_choices.json and sets choice to A, B or C with",
                "decided_by and decided_on. Re-run python3 scripts/review.py and",
                "python3 scripts/build.py. Nothing else changes automatically."
            ], "choices": {}}, f, indent=2, ensure_ascii=False)
            f.write("\n")

    decided = sum(1 for r in rows if r["recorded_choice"])
    print("Decision console: %d proposals, %d decided, %d awaiting a choice"
          % (len(rows), decided, len(rows) - decided))
    print("wrote data/decision_console.csv")
    if errors:
        print("\nERRORS:")
        for e in errors:
            print(" -", e)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
