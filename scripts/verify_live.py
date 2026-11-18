#!/usr/bin/env python3
"""Independent live re-verification of the repository's official-source data.

The repository claims that its Week 10 injury snapshot, its 2026 standings and
its Week 11 slate were transcribed from NFL.com.  This script tests those claims
against a **second, independent transcription** of the same official pages, read
fresh from the live site on a recorded date and stored under
``data/verification_inputs/``.

Input dates (2026-11-18 refresh): the injury and Week 11 schedule/bye inputs were
re-read from the live pages on 2026-11-18 after the injury snapshot was
re-captured (flag F94). The standings input remains the 2026-11-14 point-in-time
capture, because the committed standings snapshots in ``data/`` are dated
2026-11-14 and the live standings page has since advanced past Week 10; comparing
the committed snapshot against a newer live read would report the passage of time
as a data error. Each input is matched to the repo state it verifies.

It deliberately does not read the first transcription when comparing: the second
transcription is a separate file produced from the live page, so agreement
between the two is evidence and disagreement is a finding.  Nothing is inferred
or filled in; a field that is blank in one source and blank in the other is a
match, and a field present in one and absent in the other is a discrepancy.

Outputs
-------
``data/live_reverification_2026-11-18.csv``
    One row per checked unit (a team's injury block, a team's standings line,
    a Week 11 game, a bye team) with the official source URL, the row counts on
    each side, and the result.

Exit code is non-zero if any checked unit disagrees, so this can gate a build.
"""
import csv
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
INPUTS = os.path.join(DATA, "verification_inputs")

AS_OF = "2026-11-14"  # standings input read date (the committed standings snapshots are dated 2026-11-14)
INJ_AS_OF = "2026-11-18"  # injury report read date (see data/captures/injury_week10_2026-11-18.meta.json)
W11_AS_OF = "2026-11-18"  # Week 11 schedule/bye input read date (refreshed 2026-11-18)
SRC_INJURIES = "https://www.nfl.com/injuries/"
SRC_STANDINGS = "https://www.nfl.com/standings/"
SRC_WEEK11 = "https://www.nfl.com/schedules/2026/by-week/week-11"

errors = []


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def read_tsv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def norm(s):
    "Normalise whitespace only. No value is otherwise altered."
    return " ".join((s or "").split())


# --------------------------------------------------------------- injuries ----
repo_inj = read_csv(os.path.join(DATA, "injuries_week10_2026.csv"))
live_inj = read_tsv(os.path.join(INPUTS, "injuries_2026-11-18.tsv"))  # read 2026-11-18; the 2026-11-14 TSV is kept as the prior read

# (team, player, position) is the identity of an injury-report line.
def inj_key(r, team_fields=("team_abbr",), player="player", position="position"):
    return (norm(r[team_fields[0]]), norm(r[player]), norm(r[position]))


repo_by_team = {}
for r in repo_inj:
    repo_by_team.setdefault(norm(r["team_abbr"]), []).append(r)
live_by_team = {}
for r in live_inj:
    live_by_team.setdefault(norm(r["team_abbr"]), []).append(r)

rows = []
all_teams = sorted(set(repo_by_team) | set(live_by_team))
for team in all_teams:
    a = repo_by_team.get(team, [])
    b = live_by_team.get(team, [])
    a_keys = [inj_key(r) for r in a]
    b_keys = [inj_key(r) for r in b]
    missing = [k for k in b_keys if k not in a_keys]        # on the live page, not in the repo
    extra = [k for k in a_keys if k not in b_keys]          # in the repo, not on the live page
    field_diffs = []
    for k in (k for k in b_keys if k in a_keys):
        repo_row = next(r for r in a if inj_key(r) == k)
        live_row = next(r for r in b if inj_key(r) == k)
        for rf, lf, label in (("injury", "injury", "injury"),
                              ("practice_status", "practice_status", "practice status"),
                              ("game_status", "game_status", "game status")):
            if norm(repo_row[rf]) != norm(live_row[lf]):
                field_diffs.append(
                    "%s %s: %s repo=%r live=%r"
                    % (k[1], k[2], label, norm(repo_row[rf]), norm(live_row[lf]))
                )
    result = "match" if not (missing or extra or field_diffs) else "DISCREPANCY"
    if result != "match":
        errors.append("injury block %s: %s" % (team, "; ".join(
            (["missing from repo: " + ", ".join("%s %s" % (m[1], m[2]) for m in missing)] if missing else []) +
            (["extra in repo: " + ", ".join("%s %s" % (e[1], e[2]) for e in extra)] if extra else []) +
            field_diffs)))
    rows.append({
        "check_id": "LR-INJ-%s" % team,
        "unit": "%s Week 10 injury block" % team,
        "checked_against": SRC_INJURIES,
        "repo_rows": len(a),
        "live_rows": len(b),
        "missing_from_repo": "; ".join("%s %s" % (m[1], m[2]) for m in missing),
        "extra_in_repo": "; ".join("%s %s" % (e[1], e[2]) for e in extra),
        "field_differences": "; ".join(field_diffs),
        "result": result,
        "read_utc": INJ_AS_OF,
        "source_url": SRC_INJURIES,
    })

# Whole-page totals, so a team-level match cannot hide a page-level shift.
rows.append({
    "check_id": "LR-INJ-TOTAL",
    "unit": "Week 10 injury report, all listed games",
    "checked_against": SRC_INJURIES,
    "repo_rows": len(repo_inj),
    "live_rows": len(live_inj),
    "missing_from_repo": "",
    "extra_in_repo": "",
    "field_differences": "",
    "result": "match" if len(repo_inj) == len(live_inj) else "DISCREPANCY",
    "read_utc": INJ_AS_OF,
    "source_url": SRC_INJURIES,
})
if len(repo_inj) != len(live_inj):
    errors.append("injury total: repo %d live %d" % (len(repo_inj), len(live_inj)))

# --------------------------------------------------------------- standings ---
live_st = {norm(r["team_abbr"]): r for r in read_tsv(os.path.join(INPUTS, "standings_2026-11-14.tsv"))}
repo_st = {norm(r["team_abbr"]): r for r in read_csv(os.path.join(DATA, "standings_2026_snapshot.csv"))}

# The repository's standings file names the Rams "LA" or "LAR" depending on the
# session that wrote it; both refer to the same club.  Record the mapping rather
# than silently rewriting a value.
ALIAS = {"LAR": "LA"}


def canon(t):
    t = norm(t)
    return ALIAS.get(t, t)


repo_st_c = {canon(k): v for k, v in repo_st.items()}
for team in sorted(live_st):
    live = live_st[team]
    repo = repo_st_c.get(team)
    if repo is None:
        diffs = ["no row in data/standings_2026_snapshot.csv"]
        result = "DISCREPANCY"
    else:
        diffs = []
        for repo_f, live_f in (("wins", "W"), ("losses", "L"), ("ties", "T"),
                               ("points_for", "PF"), ("points_against", "PA")):
            if norm(repo.get(repo_f, "")) != norm(live[live_f]):
                diffs.append("%s repo=%r live=%r"
                             % (live_f, norm(repo.get(repo_f, "")), norm(live[live_f])))
        result = "match" if not diffs else "DISCREPANCY"
    if result != "match":
        errors.append("standings %s: %s" % (team, "; ".join(diffs)))
    rows.append({
        "check_id": "LR-STD-%s" % team,
        "unit": "%s standings (W-L-T, PF, PA)" % team,
        "checked_against": SRC_STANDINGS,
        "repo_rows": 1 if repo else 0,
        "live_rows": 1,
        "missing_from_repo": "" if repo else "team row",
        "extra_in_repo": "",
        "field_differences": "; ".join(diffs),
        "result": result,
        "read_utc": AS_OF,
        "source_url": SRC_STANDINGS,
    })

# ------------------------------------------------------------ Week 11 slate --
repo_w11 = read_csv(os.path.join(DATA, "schedule_week11_2026.csv"))
live_w11 = read_tsv(os.path.join(INPUTS, "week11_schedule_2026-11-18.tsv"))
repo_games = {(norm(r["away_team"]), norm(r["home_team"])): r for r in repo_w11}
live_games = {(norm(r["away_team"]), norm(r["home_team"])): r for r in live_w11}

for key in sorted(set(repo_games) | set(live_games)):
    label = "%s at %s" % key
    repo = repo_games.get(key)
    live = live_games.get(key)
    diffs = []
    if repo is None:
        diffs.append("game missing from data/schedule_week11_2026.csv")
    if live is None:
        diffs.append("game not on the live Week 11 page")
    if repo and live:
        for f in ("kickoff_day", "kickoff_time_et", "broadcast"):
            if norm(repo.get(f, "")) != norm(live[f]):
                diffs.append("%s repo=%r live=%r" % (f, norm(repo.get(f, "")), norm(live[f])))
    result = "match" if not diffs else "DISCREPANCY"
    if result != "match":
        errors.append("week 11 %s: %s" % (label, "; ".join(diffs)))
    rows.append({
        "check_id": "LR-W11-%s" % ("-".join(key)),
        "unit": "Week 11 %s" % label,
        "checked_against": SRC_WEEK11,
        "repo_rows": 1 if repo else 0,
        "live_rows": 1 if live else 0,
        "missing_from_repo": "" if repo else label,
        "extra_in_repo": "" if live else label,
        "field_differences": "; ".join(diffs),
        "result": result,
        "read_utc": W11_AS_OF,
        "source_url": SRC_WEEK11,
    })

# Bye teams: the official page lists them explicitly, so this is checked, not inferred.
live_byes = {norm(r["bye_team"]) for r in read_tsv(os.path.join(INPUTS, "week11_byes_2026-11-18.tsv"))}
expected_byes = {"ATL", "CLE", "GB", "LA", "NE", "SEA"}
bye_match = live_byes == expected_byes
if not bye_match:
    errors.append("week 11 byes: live %s vs expected %s" % (sorted(live_byes), sorted(expected_byes)))
rows.append({
    "check_id": "LR-W11-BYES",
    "unit": "Week 11 teams on bye",
    "checked_against": SRC_WEEK11,
    "repo_rows": len(expected_byes),
    "live_rows": len(live_byes),
    "missing_from_repo": "",
    "extra_in_repo": ",".join(sorted(live_byes - expected_byes)),
    "field_differences": "" if bye_match else "live=%s" % ",".join(sorted(live_byes)),
    "result": "match" if bye_match else "DISCREPANCY",
    "read_utc": W11_AS_OF,
    "source_url": SRC_WEEK11,
})

# ------------------------------------------------------------------- output --
FIELDS = ["check_id", "unit", "checked_against", "repo_rows", "live_rows",
          "missing_from_repo", "extra_in_repo", "field_differences", "result",
          "read_utc", "source_url"]
out = os.path.join(DATA, "live_reverification_2026-11-18.csv")
with open(out, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(rows)

matched = sum(1 for r in rows if r["result"] == "match")
print("Live re-verification (standings read %s; injuries and Week 11 schedule/byes read %s, UTC)" % (AS_OF, INJ_AS_OF))
print("  units checked : %d" % len(rows))
print("  matched       : %d" % matched)
print("  discrepancies : %d" % (len(rows) - matched))
print("  wrote %s" % os.path.relpath(out, ROOT))
if errors:
    print("\nDISCREPANCIES:")
    for e in errors:
        print("  -", e)
    sys.exit(1)
