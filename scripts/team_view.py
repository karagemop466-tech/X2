#!/usr/bin/env python3
"""Per-team view for Week 10, 2026 (session 6ee4d13e, T98).

For each of the 32 clubs: the official injury-report counts, the net injury count, the starters
who are Out or Doubtful according to a club depth chart, and the replacements named.

Inputs (all in data/):
  standings_2026_week10.csv          the 32 clubs (names)
  injuries_week10_2026.csv           the official Week 10 injury report, 347 rows (read 2026-11-18)
  depth_replacement.csv              club-chart replacement register (structured, 33 rows)
  replacement_depth_week10_2026.csv  news/roundup-based register (11 rows; used only as named evidence)
  schedule                           the Week 10 bye list, from the official schedule page

Definitions (stated on the page):
  listed players        = rows in the official Week 10 injury report for the club
  net injury count      = listed players whose game status is Out or Doubtful
  no game designation   = listed players with a blank game status (not designated for the game)
  starters out (chart)  = distinct players on a club-chart '1st string' row whose official game status is Out or Doubtful
  replacements (chart)  = distinct (player, named replacement) pairs on those rows whose verification status is Verified
  bye                   = the club has no injury section this week (official schedule "Teams on Bye": CHI DEN PHI TB), shown blank,
                          never as 'injury-free'

Every count is asserted against the injury report totals before the CSV is written.
Run:  python3 scripts/team_view.py
"""
import csv
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
SCHED = "https://www.nfl.com/schedules/2026/by-week/week-10"
INJ = "https://www.nfl.com/injuries/"
BYE_WEEK10 = {"CHI", "DEN", "PHI", "TB"}   # official Week 10 bye list (README; verified on the schedule page)
SELF_LABELLED_UNOFFICIAL = {"DET", "NE"}   # charts that label themselves unofficial (F05 / F18); others do not

FIELDS = ["team_abbr", "team_name", "week10_status", "listed_players", "out_count", "doubtful_count",
          "questionable_count", "no_game_designation_count", "net_injury_count", "starter_order_source",
          "starters_out_chart_players", "starters_out_chart_names", "replacements_named_chart_pairs",
          "replacements_named_chart", "replacements_named_article", "article_source_url", "unverified_note",
          "source_url", "chart_url"]


def read(name):
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    teams = read("standings_2026_week10.csv")
    if len(teams) != 32:
        sys.exit(f"expected 32 clubs, found {len(teams)}")
    names = {t["team_abbr"]: t["team_name"] for t in teams}
    inj = read("injuries_week10_2026.csv")
    if len(inj) != 347:
        sys.exit(f"expected 347 injury rows, found {len(inj)}")
    dr = read("depth_replacement.csv")
    art = read("replacement_depth_week10_2026.csv")

    chart_by_team = {}
    for r in dr:
        chart_by_team.setdefault(r["team_abbr"], []).append(r)
    chart_url = {}
    for r in dr:
        chart_url.setdefault(r["team_abbr"], r["chart_url"])
    article_by_team = {}
    for r in art:
        ds = r["depth_status"]
        named = (r["replacement_named_by_official_source"] or "").strip()
        if not ds.startswith("Verified"):
            continue
        if not named or named.lower().startswith(("none", "not named", "n/a")):
            continue
        article_by_team.setdefault(r["team_abbr"], []).append((r["player_affected"], named, r["source_url"]))

    rows = []
    totals = {"Out": 0, "Doubtful": 0, "Questionable": 0, "": 0}
    for t in sorted(names):
        team_inj = [r for r in inj if r["team_abbr"] == t]
        bye = t in BYE_WEEK10
        if bye and team_inj:
            sys.exit(f"{t} is on bye but has injury rows")
        if not bye and not team_inj:
            sys.exit(f"{t} plays in Week 10 but has no injury rows")
        out = sum(1 for r in team_inj if r["game_status"] == "Out")
        dbt = sum(1 for r in team_inj if r["game_status"] == "Doubtful")
        qst = sum(1 for r in team_inj if r["game_status"] == "Questionable")
        blank = sum(1 for r in team_inj if r["game_status"] == "")
        for r in team_inj:
            totals[r["game_status"]] = totals.get(r["game_status"], 0) + 1
        covered = t in chart_by_team
        # one entry per player: a player listed at several special-teams spots (e.g. P and holder) counts once
        starter_rows = [r for r in chart_by_team.get(t, [])
                        if r["string_of_absent_player"] == "1st string" and r["official_game_status"] in ("Out", "Doubtful")]
        starters, seen = [], set()
        for r in starter_rows:
            if r["player_out"] not in seen:
                seen.add(r["player_out"])
                starters.append(r)
        for s in starters:
            hit = [r for r in team_inj if r["player"] == s["player_out"]]
            if not hit or hit[0]["game_status"] != s["official_game_status"]:
                sys.exit(f"starter {s['player_out']} ({t}) does not match the injury report")
        named_chart = []
        for s_ in starter_rows:       # pairs: (player, replacement); one pair per named replacement
            if (s_["named_replacement"] or "").strip() and s_["verification_status"].startswith("Verified"):
                pair = (s_["player_out"], s_["named_replacement"])
                if pair not in named_chart:
                    named_chart.append(pair)
        def _rep_label(name):
            # a named replacement can himself be on the official report: show that status, never hide it
            hit = [r for r in team_inj if r["player"] == name]
            if not hit:
                return name + " (not on the Week 10 report)"
            return name + " (on the Week 10 report: " + (hit[0]["game_status"] or "no game designation") + ")"
        named_art = article_by_team.get(t, [])
        art_urls = sorted({u for _p, _n, u in named_art})
        if len(art_urls) > 1:
            sys.exit(f"{t}: more than one article source; one URL per row is required")
        if bye:
            status = "Bye (no injury section)"
            src = SCHED
        else:
            status = "Playing (injury section published)"
            src = INJ
        if covered:
            order_src = ("Club team-site depth chart, self-labelled unofficial (F05 / F18)" if t in SELF_LABELLED_UNOFFICIAL\
                         else "Club team-site depth chart (self-label not stated on the page)") + \
                        "; chart_as_of not stated on the page"
            note = ""
        else:
            order_src = "None - no club chart on the depth register (see F06, F78)"
            note = "Starter order not verified: no club chart on the depth register." if not bye else \
                "Bye week: no injury section and no depth evidence this week."
        rows.append({
            "team_abbr": t, "team_name": names[t], "week10_status": status,
            "listed_players": "" if bye else len(team_inj),
            "out_count": "" if bye else out, "doubtful_count": "" if bye else dbt,
            "questionable_count": "" if bye else qst, "no_game_designation_count": "" if bye else blank,
            "net_injury_count": "" if bye else out + dbt,
            "starter_order_source": "" if bye else order_src,
            "starters_out_chart_players": (len(starters) if covered else "") if not bye else "",
            "starters_out_chart_names": "; ".join(f"{s['player_out']} ({s['official_game_status']})" for s in starters)
                                       if covered and not bye else "",
            "replacements_named_chart_pairs": (len(named_chart) if covered else "") if not bye else "",
            "replacements_named_chart": "; ".join(f"{p} -> {_rep_label(n)}" for p, n in named_chart) if covered and not bye else "",
            "replacements_named_article": "; ".join(f"{p} -> {n}" for p, n, _u in named_art),
            "article_source_url": art_urls[0] if art_urls else "",
            "unverified_note": note,
            "source_url": src,
            "chart_url": chart_url.get(t, ""),
        })

    # reconciliation against the official report totals (347 rows: 70 Out, 11 Doubtful, 90 Questionable)
    sums = {k: sum(int(r[c]) for r in rows if r[c] != "") for k, c in
            (("Out", "out_count"), ("Doubtful", "doubtful_count"), ("Questionable", "questionable_count"))}
    listed = sum(int(r["listed_players"]) for r in rows if r["listed_players"] != "")
    if (sums["Out"], sums["Doubtful"], sums["Questionable"], listed) != (70, 11, 90, 347):
        sys.exit(f"team totals do not reconcile with the injury report: {sums}, listed {listed}")
    blank_total = sum(int(r["no_game_designation_count"]) for r in rows if r["no_game_designation_count"] != "")
    if blank_total != 176:
        sys.exit(f"blank game-status rows do not reconcile: {blank_total} vs 176")
    if sum(1 for r in rows if r["week10_status"].startswith("Bye")) != 4:
        sys.exit("expected 4 bye clubs")

    with open(os.path.join(DATA, "team_view_week10_2026.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"wrote {len(rows)} team rows; reconciled: Out {sums['Out']}, Doubtful {sums['Doubtful']}, "
          f"Questionable {sums['Questionable']}, listed {listed}")


if __name__ == "__main__":
    main()
