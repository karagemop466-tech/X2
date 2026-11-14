#!/usr/bin/env python3
"""Build the replacement-depth DETAIL register: how far down the chart a fix has to reach.

Relationship to `data/replacement_depth_week10_2026.csv` (session 8a0bf37e, task T42): that
register is the availability-led view — one row per officially reported absence whose named
replacement could be checked, eleven rows, quarterback-heavy, each carrying the club-chart
order as fetched. This file is the slot-led view for the two clubs whose charts this project
has read directly (NE, DET) plus the unplaceable cases: it adds `charted_bodies_at_slot`,
`depth_consumed_in_unit` and `shared_backup_note`, the three fields needed to say how far the
damage reaches rather than who is out. The two files are joined by team and game_no, not merged,
so a correction in one cannot silently rewrite the other. Row IDs (RD-nn) do not collide with
theirs (A-nn).

Brief item: "Track the depth of the replacement, not just the fact of a replacement."

The injury report states that a player is Out. It never states whether he was the 1st,
2nd, 3rd or 4th string player, nor who is beneath him. Losing a fourth cornerback is not
the same event as losing the last two bodies charted at a position, and a model that
treats them alike is guessing. This register separates the two:

  * `levels_down` — how many charted places the first available player sits below the
    affected slot. It is filled ONLY where an official club depth chart was read for that
    team, in the same week, and lists both names.
  * `charted_bodies_at_slot` and `depth_consumed_in_unit` — whether the group has any
    charted body left at all. A slot with two charted names and both injured is a
    different problem from a slot with five.
  * `shared_backup_note` — when one backup is the charted replacement at two positions,
    elevating him for one hole opens the other. That is invisible in a count of absences.
  * `blank_reason` — for every team with no chart captured here, the fields are blank and
    the reason is stated. No string rank is ever inferred from roster order (F06).

Source discipline: statuses are read from the NFL.com injury report (the league's own
report, the same one the rest of the project uses); the chart order is read from the
club's own published depth chart. Both club pages label themselves "unofficial" — the
label is carried in `chart_self_label` on every row so the caveat travels with the number
(F18). The chart used here is the club's Week 10 chart, read 2026-11-14.

Run:  python3 scripts/replacement_depth.py
"""
import csv
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(DATA, "replacement_depth_detail_week10_2026.csv")
AS_OF = "2026-11-14"
INJ_URL = "https://www.nfl.com/injuries/"
DET_CHART = "https://www.detroitlions.com/team/depth-chart"
NE_CHART = "https://www.patriots.com/team/depth-chart"
DET_LABEL = ("Detroit Lions — '2026 Unofficial Depth Chart Compiled by Lions Football "
             "Communications'")
NE_LABEL = ("New England Patriots — 'The 2026 depth chart is unofficial and is published by the "
            "writers of Patriots.com'")
FIELDS = ["row_id", "season", "week", "game_no", "matchup", "team_abbr", "position_group", "affected_slot",
          "affected_player", "affected_status", "replacement_name", "replacement_status",
          "levels_down", "charted_bodies_at_slot", "depth_consumed_in_unit", "shared_backup_note",
          "chain_note", "blank_reason", "chart_source_kind", "chart_self_label", "chart_read_on",
          "status", "source_url", "chart_url"]

ROWS = [
    # ---------------- Detroit Lions (club chart read 2026-11-14) ----------------
    dict(row_id="RD-01", team_abbr="DET", position_group="CB", affected_slot="CB1",
         affected_player="D.J. Reed", affected_status="Out (Hip; did not participate)",
         replacement_name="Rock Ya-Sin", replacement_status="no designation on the Week 10 report",
         levels_down="1", charted_bodies_at_slot="4", depth_consumed_in_unit="1 of 4 charted",
         shared_backup_note="", chain_note="Chart order for the group: D.J. Reed, Rock Ya-Sin, "
         "Khalil Dorsey, Nick Whiteside. With Reed out the coverage opposite the other corner "
         "falls to the charted second name and the top of the depth chart is two deep no longer.",
         blank_reason="", status="Verified against the club chart"),
    dict(row_id="RD-02", team_abbr="DET", position_group="C", affected_slot="C1",
         affected_player="Cade Mays", affected_status="Out (Ankle; did not participate)",
         replacement_name="Juice Scruggs", replacement_status="no designation on the Week 10 report",
         levels_down="1", charted_bodies_at_slot="2", depth_consumed_in_unit="1 of 2 charted",
         shared_backup_note="Scruggs is the only other body charted at center; if he is also "
         "unavailable there is no charted next man at the position.",
         chain_note="", blank_reason="", status="Verified against the club chart"),
    dict(row_id="RD-03", team_abbr="DET", position_group="S", affected_slot="unresolved",
         affected_player="Kerby Joseph", affected_status="Out (Knee; did not participate)",
         replacement_name="", replacement_status="", levels_down="", charted_bodies_at_slot="",
         depth_consumed_in_unit="", shared_backup_note="", chain_note="",
         blank_reason="The club chart published on the same page does not list Kerby Joseph on "
         "either safety row (it shows Chuck Clark alone, and Brian Branch with Christian Izien), "
         "so no depth position can be read for the affected slot. Flagged as an official-source "
         "inconsistency rather than guessed.",
         status="Unverified — flagged"),
    dict(row_id="RD-04", team_abbr="DET", position_group="WR", affected_slot="WR1 (X/Z split row)",
         affected_player="Amon-Ra St. Brown", affected_status="Questionable (Rib; limited)",
         replacement_name="DeAndre Carter", replacement_status="no designation on the Week 10 report",
         levels_down="1 (only if St. Brown does not play)", charted_bodies_at_slot="2 on that row",
         depth_consumed_in_unit="conditional — the starter is not ruled out",
         shared_backup_note="Carter is also charted as the primary punt returner and as the "
         "kick-returner opposite Jacob Saylors, so a snap increase at WR is taken from return work.",
         chain_note="", blank_reason="", status="Verified against the club chart; conditional on status"),
    dict(row_id="RD-05", team_abbr="DET", position_group="RB", affected_slot="RB2",
         affected_player="Sione Vaki", affected_status="Questionable (Ankle; limited)",
         replacement_name="Jacob Saylors", replacement_status="no designation (full participation)",
         levels_down="1 from Vaki's slot (2 from the RB1 slot)", charted_bodies_at_slot="3",
         depth_consumed_in_unit="2 of 3 charted carry a designation or a status",
         shared_backup_note="Saylors is also the charted kick returner, so the same body covers "
         "the third running back and the primary kick return.",
         chain_note="Jahmyr Gibbs (RB1) has no designation, so the deepest case is Gibbs out AND "
         "Vaki out, which would put the charted third name at both jobs.",
         blank_reason="", status="Verified against the club chart; conditional on status"),
    # ---------------- New England Patriots (club chart read 2026-11-14) ----------------
    dict(row_id="RD-06", team_abbr="NE", position_group="OL (LG)", affected_slot="LG1",
         affected_player="Ben Brown", affected_status="Out (Knee; did not participate)",
         replacement_name="Walter Rouse", replacement_status="Questionable (Concussion; limited)",
         levels_down="1", charted_bodies_at_slot="2", depth_consumed_in_unit="2 of 2 charted affected",
         shared_backup_note="Rouse is the charted backup at left guard AND at right guard. "
         "Elevating him at one spot leaves the other with no charted body, and Rouse himself is "
         "questionable — the whole left-guard solution rests on one player's clearance.",
         chain_note="Brown is charted twice: LG1 and C2 behind Jared Wilson. His absence removes "
         "a body from two different rows, which an absence count cannot express.",
         blank_reason="", status="Verified against the club chart"),
    dict(row_id="RD-07", team_abbr="NE", position_group="CB", affected_slot="CB1 (one of three CB rows)",
         affected_player="Carlton Davis III", affected_status="Out (Knee; did not participate)",
         replacement_name="Channing Canada", replacement_status="no designation on the Week 10 report",
         levels_down="1", charted_bodies_at_slot="2", depth_consumed_in_unit="1 of 2 charted on that row",
         shared_backup_note="", chain_note="The chart has no third name on the Davis row. Across "
         "all three corner rows the club charts seven bodies; one is out and one (Charles Woods, "
         "charted CB2 on the Marcus Jones row) is questionable.",
         blank_reason="", status="Verified against the club chart"),
    dict(row_id="RD-08", team_abbr="NE", position_group="RB", affected_slot="RB2",
         affected_player="TreVeyon Henderson", affected_status="Out (Illness; did not participate)",
         replacement_name="Corey Kiner", replacement_status="no designation on the Week 10 report",
         levels_down="1 from Henderson's slot; the RB1 slot (Rhamondre Stevenson) is Questionable, "
         "so the working depth at RB could reach the charted 3rd name",
         charted_bodies_at_slot="4", depth_consumed_in_unit="2 of 4 charted affected (RB1 questionable, RB2 out)",
         shared_backup_note="Lan Larison, charted RB4, is also charted on the kick-return unit.",
         chain_note="If Stevenson does not play, the top of the backfield is the charted third "
         "name, not the second — a two-deep hit on one unit from two separate designations.",
         blank_reason="", status="Verified against the club chart"),
    dict(row_id="RD-09", team_abbr="NE", position_group="S", affected_slot="S1 (Byard row)",
         affected_player="Kevin Byard III", affected_status="Questionable (Chest; full participation)",
         replacement_name="Jaylen Reed", replacement_status="no designation on the Week 10 report",
         levels_down="1 (only if Byard does not play)", charted_bodies_at_slot="3",
         depth_consumed_in_unit="2 of 3 charted carry a designation (Byard, Schooler)",
         shared_backup_note="Brenden Schooler, charted S3 on the same row, is also questionable "
         "(hamstring), so the row's second and third names are both in play only conditionally.",
         chain_note="", blank_reason="", status="Verified against the club chart; conditional on status"),
    dict(row_id="RD-10", team_abbr="NE", position_group="G", affected_slot="unresolved",
         affected_player="Greg Van Roten", affected_status="Questionable (Hamstring; full participation)",
         replacement_name="", replacement_status="", levels_down="", charted_bodies_at_slot="",
         depth_consumed_in_unit="", shared_backup_note="", chain_note="",
         blank_reason="Van Roten appears on the league's Week 10 report as a guard but on no guard "
         "row of the club chart, so no affected slot or replacement can be read for him. Flagged "
         "as a source inconsistency rather than guessed.",
         status="Unverified — flagged"),
    dict(row_id="RD-11", team_abbr="NE", position_group="TE", affected_slot="TE3",
         affected_player="Cameron Latu", affected_status="Questionable (Back; limited)",
         replacement_name="", replacement_status="no further body charted at TE",
         levels_down="0 — he is the third name, not a starter", charted_bodies_at_slot="3",
         depth_consumed_in_unit="1 of 3 charted; Hunter Henry (TE1) practised limited without a status",
         shared_backup_note="", chain_note="A third-string absence is a special-teams and "
         "package problem, not a starting-lineup problem; recorded so it is not counted like one.",
         blank_reason="", status="Verified against the club chart"),
    dict(row_id="RD-12", team_abbr="NE", position_group="FB", affected_slot="unresolved",
         affected_player="Reggie Gilliam", affected_status="Questionable (Knee; limited)",
         replacement_name="", replacement_status="", levels_down="", charted_bodies_at_slot="",
         depth_consumed_in_unit="", shared_backup_note="", chain_note="",
         blank_reason="The club chart publishes no fullback row, so there is no depth position to "
         "read. The absence is real on the league report and unplaceable on the chart.",
         status="Unverified — flagged"),
    # ---------------- teams whose chart has not been captured ----------------
    dict(row_id="RD-13", team_abbr="SEA", position_group="QB", affected_slot="QB1",
         affected_player="Sam Darnold", affected_status="Out (ribs/quadricep; did not participate)",
         replacement_name="Drew Lock", replacement_status="no designation on the Week 10 report",
         levels_down="", charted_bodies_at_slot="", depth_consumed_in_unit="",
         shared_backup_note="", chain_note="The league's own news desk names the replacement "
         "('Drew Lock (elbow/oblique) has no injury designation, will start'), so the FACT of a "
         "replacement is verified; the DEPTH of it is not, because no Seahawks depth chart has "
         "been captured under the official-source rule.",
         blank_reason="No club depth chart captured for SEA in this build.", status="Partial — fact verified, depth blank"),
    dict(row_id="RD-14", team_abbr="BAL", position_group="QB", affected_slot="QB1",
         affected_player="Lamar Jackson", affected_status="absent from the Week 10 report table",
         replacement_name="", replacement_status="", levels_down="", charted_bodies_at_slot="",
         depth_consumed_in_unit="", shared_backup_note="", chain_note="",
         blank_reason="The player is not on the league's Week 10 report at all (F27), and no club "
         "chart has been captured for BAL. Both halves are blank, and the row stays visible so the "
         "gap is not mistaken for 'no injury'.", status="Unverified — flagged"),
]


# Every team in this register is on the Week 10 slate, and every one of those games has
# an originated line in data/model_lines_week10_2026.csv — so a depth number here is a
# number about a game this project has published a price-free line for.
GAMES = {
    "NE": ("2", "NE at DET — Sun 2026-11-15 09:30 ET (originated: home margin +1.84, total 48.91)"),
    "DET": ("2", "NE at DET — Sun 2026-11-15 09:30 ET (originated: home margin +1.84, total 48.91)"),
    "SEA": ("11", "SEA at LV — Sun 2026-11-15 16:05 ET (originated: home margin -3.89, total 48.33)"),
    "BAL": ("14", "LAC at BAL — Mon 2026-11-16 20:15 ET (originated: home margin +3.51, total 44.86)"),
}


def main():
    out = []
    for r in ROWS:
        gno, matchup = GAMES.get(r["team_abbr"], ("", "no Week 10 game matched"))
        row = dict(season="2026", week="10", game_no=gno, matchup=matchup,
                   chart_source_kind="official club website, self-labelled unofficial"
                   if r["team_abbr"] in ("NE", "DET") else "none captured",
                   chart_self_label=DET_LABEL if r["team_abbr"] == "DET" else
                   (NE_LABEL if r["team_abbr"] == "NE" else ""),
                   chart_read_on=AS_OF if r["team_abbr"] in ("NE", "DET") else "",
                   source_url=INJ_URL,
                   chart_url=(DET_CHART if r["team_abbr"] == "DET" else
                             (NE_CHART if r["team_abbr"] == "NE" else "")),
                   **r)
        out.append(row)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\r\n")
        w.writeheader()
        w.writerows(out)
    os.replace(tmp, OUT)
    filled = sum(1 for r in out if r["levels_down"])
    print(f"Replacement depth: {len(out)} rows; {filled} carry a verified depth position from a "
          f"club chart read {AS_OF}; {len(out) - filled} left blank with the reason stated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
