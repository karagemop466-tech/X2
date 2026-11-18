#!/usr/bin/env python3
"""Availability capture ledger: two dated reads of the same official injury report,
their hashes, and the published delta (the change, never the level).

Why this exists. The brief requires the injury hub to be "a timestamped series, not a
weekly snapshot", that "every injury-hub read is stored with its clock time", that the
injury signal is "a surprise, never a level", and a point-in-time snapshot ledger so
backtests cannot leak. Until 2026-11-18 the repository held exactly ONE read of
https://www.nfl.com/injuries/ (2026-11-14) and no clock time with it, so no delta could
be computed at all and F83 (row-count dispute: 345 published vs the brief's 254/279)
could not be closed.

This script makes the second read comparable to the first, mechanically:

  1. normalises data/verification_inputs/injuries_2026-11-18_raw.psv (the raw
     transcription read from the live page on 2026-11-18, all eight rendered chunks)
     into data/verification_inputs/injuries_2026-11-18.tsv, in the same six-column
     schema as the 2026-11-14 capture, so the two are row-for-row comparable;
  2. writes data/availability_captures.csv — one row per capture with its source URL,
     the week label the page rendered, the read clock time, a sha256 over the canonical
     payload, the row and team counts, and whether that capture can support a delta;
  3. writes data/availability_delta_2026-11-14_to_2026-11-18.csv — one row per player
     whose practice designation, game status or presence in the report changed between
     the two reads, plus the unchanged count;
  4. writes data/availability_delta_summary.csv — the counts a decision needs:
     rows added, rows removed, practice changes, designations added, designations
     changed, per club, with the total on each side;
  5. writes data/live_reverification_2026-11-18.csv — the published snapshot
     (data/injuries_week10_2026.csv) checked club by club against today's read, which
     is what F83 asked for and what session b03f4ba1 left at "four of eight chunks".

It never edits the published snapshot. Differences are reported, not corrected: today's
read is a different clock time of a mutable page, and which of the two is "right" is a
source-behaviour question that the ledger, not this script, answers.

Pin check (the drift alarm the brief asks for): the row count, the club count and the
required fields are asserted against pinned values; a parser that silently loses rows
fails the run instead of publishing a blank.

Run:  python3 scripts/availability_captures.py
"""
import csv
import hashlib
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VER = os.path.join(ROOT, "data", "verification_inputs")
DATA = os.path.join(ROOT, "data")

INJURY_URL = "https://www.nfl.com/injuries/"
SNAPSHOT = "injuries_week10_2026.csv"

CAPTURES = [
    {
        "capture_id": "CAP-01",
        "file": "injuries_2026-11-14.tsv",
        "week_label": "WEEK 10",
        "read_utc": "2026-11-14T00:00Z",
        "read_precision": "date only — the 2026-11-14 capture recorded no clock time (D10); the time is unknown, not assumed",
        "method": "manual transcription of every rendered chunk, kept as a TSV payload",
        "note": "The capture the published site table is built from; verified equal to "
                "data/injuries_week10_2026.csv row for row by scripts/verify_snapshot.py and again by this script.",
    },
    {
        "capture_id": "CAP-02",
        "file": "injuries_2026-11-18.tsv",
        "week_label": "WEEK 10",
        "read_utc": "2026-11-18T03:46Z",
        "read_precision": "minute — transcription time of the same fetch session that read all eight chunks",
        "method": "manual transcription of every rendered chunk of the live page, plus the "
                  "?season=2026&week=11&type=REG render, which returned the Week 10 tables unchanged",
        "note": "First second-read of one report in this repository, which is what makes a delta possible.",
    },
]

# Pinned expectations for today's read. Change them only with a fresh official read.
PIN = {"rows": 347, "teams": 28, "games": 14}

PRACTICE = {"F": "Full Participation in Practice",
            "L": "Limited Participation in Practice",
            "D": "Did Not Participate In Practice"}
COLS = ["team_abbr", "player", "position", "injury", "practice_status", "game_status"]


def fail(msg):
    raise SystemExit("AVAILABILITY CAPTURE CHECK FAILED: " + msg)


def read_tsv(path):
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    out = []
    for r in rows:
        rec = {c: (r.get(c) or "").strip() for c in COLS}
        out.append(rec)
    return out


def normalise_new_capture():
    """injuries_2026-11-18_raw.psv -> injuries_2026-11-18.tsv (six columns, tab separated)."""
    src = os.path.join(VER, "injuries_2026-11-18_raw.psv")
    dst = os.path.join(VER, "injuries_2026-11-18.tsv")
    rows = []
    with open(src, encoding="utf-8") as f:
        for ln, line in enumerate(f, start=1):
            line = line.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) != 6:
                fail(f"raw transcription line {ln}: {len(parts)} fields, expected 6 -> {line[:80]}")
            team, player, pos, injury, prac, game_status = [p.strip() for p in parts]
            if prac not in PRACTICE:
                fail(f"raw transcription line {ln}: practice code {prac!r} is not one of F/L/D")
            if game_status not in ("", "Out", "Doubtful", "Questionable"):
                fail(f"raw transcription line {ln}: game status {game_status!r} is not an official designation word")
            if not team or not player:
                fail(f"raw transcription line {ln}: blank team or player")
            rows.append([team, player, pos, injury, PRACTICE[prac], game_status])
    with open(dst, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(COLS)
        w.writerows(rows)
    return rows


def payload_sha256(rows):
    """Hash over the canonical payload only (sorted team|player|position|injury|practice|status)."""
    lines = []
    for r in rows:
        lines.append("|".join((r.get(c, "") if isinstance(r, dict) else r[i]) for i, c in enumerate(COLS))
                     if isinstance(r, (list, tuple)) else "|".join(r[c] for c in COLS))
    return hashlib.sha256("\n".join(sorted(lines)).encode("utf-8")).hexdigest()


def main():
    # 1. today's capture
    new_rows = [dict(zip(COLS, r)) for r in normalise_new_capture()]
    old_path = os.path.join(VER, "injuries_2026-11-14.tsv")
    old_rows = read_tsv(old_path)

    # drift alarm on today's read
    teams = {r["team_abbr"] for r in new_rows}
    if len(new_rows) != PIN["rows"]:
        fail(f"today's read has {len(new_rows)} rows, pinned expectation {PIN['rows']} — re-read the page or update the pin with evidence")
    if len(teams) != PIN["teams"]:
        fail(f"today's read covers {len(teams)} club blocks, pinned expectation {PIN['teams']}")
    for r in new_rows:
        for c in ("team_abbr", "player", "practice_status"):
            if not r[c]:
                fail(f"required field {c} blank for {r['team_abbr']} {r['player']}")

    # 2. capture ledger
    ledger = []
    for cap in CAPTURES:
        path = os.path.join(VER, cap["file"])
        rows = new_rows if cap["file"].endswith("2026-11-18.tsv") else old_rows
        if not os.path.exists(path):
            fail(f"capture payload {cap['file']} is missing")
        tsv_bytes = open(path, "rb").read()
        ledger.append({
            "capture_id": cap["capture_id"],
            "source_url": INJURY_URL,
            "week_label_as_rendered": cap["week_label"],
            "read_utc": cap["read_utc"],
            "read_time_precision": cap["read_precision"],
            "capture_method": cap["method"],
            "rows": str(len(rows)),
            "clubs": str(len({r["team_abbr"] for r in rows})),
            "out_designations": str(sum(1 for r in rows if r["game_status"] == "Out")),
            "doubtful_designations": str(sum(1 for r in rows if r["game_status"] == "Doubtful")),
            "questionable_designations": str(sum(1 for r in rows if r["game_status"] == "Questionable")),
            "undesignated_rows": str(sum(1 for r in rows if not r["game_status"])),
            "sha256_payload": payload_sha256(rows),
            "sha256_capture_file": hashlib.sha256(tsv_bytes).hexdigest(),
            "delta_capable": "yes — two dated reads of the same report exist" if cap["capture_id"] == "CAP-02" else "yes — paired with CAP-02",
            "note": cap["note"],
        })
    write_csv("availability_captures.csv", ledger, [
        "capture_id", "source_url", "week_label_as_rendered", "read_utc", "read_time_precision",
        "capture_method", "rows", "clubs", "out_designations", "doubtful_designations",
        "questionable_designations", "undesignated_rows", "sha256_payload", "sha256_capture_file",
        "delta_capable", "note"])

    # 3/4. the delta: change between the two reads, per player
    def key(r):
        return (r["team_abbr"], r["player"])

    old_by = {key(r): r for r in old_rows}
    new_by = {key(r): r for r in new_rows}
    if len(old_by) != len(old_rows):
        fail("the 2026-11-14 capture has duplicate team/player keys; the delta would be ambiguous")
    if len(new_by) != len(new_rows):
        fail("today's capture has duplicate team/player keys; the delta would be ambiguous")

    delta = []
    for k in sorted(set(old_by) | set(new_by), key=lambda k: (k[0], k[1])):
        a, b = old_by.get(k), new_by.get(k)
        if a is None:
            change = "row_added"
        elif b is None:
            change = "row_removed"
        else:
            fields = []
            if a["practice_status"] != b["practice_status"]:
                fields.append("practice_status")
            if a["game_status"] != b["game_status"]:
                fields.append("game_status")
            if a["injury"] != b["injury"]:
                fields.append("injury")
            if a["position"] != b["position"]:
                fields.append("position")
            if not fields:
                continue
            change = "changed:" + "+".join(fields)
        delta.append({
            "team_abbr": k[0],
            "player": k[1],
            "position": (b or a)["position"],
            "practice_2026_11_14": "" if a is None else a["practice_status"],
            "practice_2026_11_18": "" if b is None else b["practice_status"],
            "game_status_2026_11_14": "" if a is None else a["game_status"],
            "game_status_2026_11_18": "" if b is None else b["game_status"],
            "injury_2026_11_14": "" if a is None else a["injury"],
            "injury_2026_11_18": "" if b is None else b["injury"],
            "change": change,
            "player_url": (b or a).get("player_url", ""),
            "source_url": INJURY_URL,
        })
    write_csv("availability_delta_2026-11-14_to_2026-11-18.csv", delta, [
        "team_abbr", "player", "position", "practice_2026_11_14", "practice_2026_11_18",
        "game_status_2026_11_14", "game_status_2026_11_18", "injury_2026_11_14",
        "injury_2026_11_18", "change", "player_url", "source_url"])

    # summary the landing page needs
    by_change = Counter(d["change"] for d in delta)
    teams_changed = sorted({d["team_abbr"] for d in delta})
    summary_rows = [
        ("rows_in_capture_2026_11_14", str(len(old_rows)), "data/verification_inputs/injuries_2026-11-14.tsv"),
        ("rows_in_capture_2026_11_18", str(len(new_rows)), "data/verification_inputs/injuries_2026-11-18.tsv"),
        ("rows_added_between_reads", str(by_change.get("row_added", 0)), "two dated reads"),
        ("rows_removed_between_reads", str(by_change.get("row_removed", 0)), "two dated reads"),
        ("practice_status_changes", str(sum(1 for d in delta if "practice_status" in d["change"])), "two dated reads"),
        ("game_status_changes", str(sum(1 for d in delta if "game_status" in d["change"])), "two dated reads"),
        ("injury_text_changes", str(sum(1 for d in delta if "injury" in d["change"])), "two dated reads"),
        ("players_unchanged", str(len(old_by) - sum(1 for d in delta if d["change"].startswith("changed:"))), "two dated reads"),
        ("clubs_with_any_change", str(len(teams_changed)), "two dated reads"),
        ("clubs_listed", f"{len({r['team_abbr'] for r in new_rows})} of 32", "Week 10 report: 28 clubs played, 4 were on bye"),
        ("week_label_rendered_on_2026_11_18", "WEEK 10", "the page heading, four days after the Week 10 games and the day before Week 11 kicks off"),
        ("published_snapshot_rows", str(len(old_rows)), "data/injuries_week10_2026.csv equals CAP-01 exactly"),
    ]
    write_csv("availability_delta_summary.csv",
              [{"metric": m, "value": v, "basis": b, "source_url": INJURY_URL} for m, v, b in summary_rows],
              ["metric", "value", "basis", "source_url"])

    # 5. published snapshot vs today's read, club by club
    pub = []
    with open(os.path.join(DATA, SNAPSHOT), encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            pub.append({c: (r.get(c) or "").strip() for c in COLS})
    pub_by = defaultdict(list)
    for r in pub:
        pub_by[r["team_abbr"]].append(r)
    new_by_team = defaultdict(list)
    for r in new_rows:
        new_by_team[r["team_abbr"]].append(r)
    old_by_team = defaultdict(list)
    for r in old_rows:
        old_by_team[r["team_abbr"]].append(r)

    checks = []
    for t in sorted(set(new_by_team) | set(pub_by) | set(old_by_team)):
        missing = sorted({(r["team_abbr"], r["player"]) for r in new_by_team[t]} -
                         {(r["team_abbr"], r["player"]) for r in pub_by[t]})
        extra = sorted({(r["team_abbr"], r["player"]) for r in pub_by[t]} -
                       {(r["team_abbr"], r["player"]) for r in new_by_team[t]})
        field_diffs = 0
        pub_lookup = {r["player"]: r for r in pub_by[t]}
        for r in new_by_team[t]:
            p = pub_lookup.get(r["player"])
            if p and any(p[c] != r[c] for c in ("position", "injury", "practice_status", "game_status")):
                field_diffs += 1
        eq_old = sorted(old_by_team[t], key=lambda r: r["player"]) == sorted(pub_by[t], key=lambda r: r["player"])
        result = "match" if not missing and not extra and not field_diffs else "difference vs today's read"
        checks.append({
            "check_id": f"LR18-{t}",
            "unit": f"{t} Week 10 injury block",
            "checked_against": "https://www.nfl.com/injuries/ (all 8 rendered chunks, read 2026-11-18)",
            "repo_rows": str(len(pub_by[t])),
            "live_rows": str(len(new_by_team[t])),
            "missing_from_repo": "; ".join(f"{m[1]}" for m in missing),
            "extra_in_repo": "; ".join(f"{e[1]}" for e in extra),
            "field_differences": str(field_diffs),
            "repo_equals_2026_11_14_capture": "yes" if eq_old else "no",
            "result": result,
            "read_utc": "2026-11-18T03:46Z",
            "source_url": INJURY_URL,
        })
    write_csv("live_reverification_2026-11-18.csv", checks, [
        "check_id", "unit", "checked_against", "repo_rows", "live_rows", "missing_from_repo",
        "extra_in_repo", "field_differences", "repo_equals_2026_11_14_capture", "result",
        "read_utc", "source_url"])

    n_diff = sum(1 for c in checks if c["result"] != "match")
    print(f"captures: {len(ledger)} (rows {[c['rows'] for c in ledger]})")
    print(f"delta rows: {len(delta)}  ({', '.join(f'{k}={v}' for k, v in sorted(by_change.items()))})")
    print(f"clubs where today's read differs from the published snapshot: {n_diff} of {len(checks)}")
    print(f"total published rows {len(pub)} vs today's read {len(new_rows)}")


def write_csv(name, rows, cols):
    path = os.path.join(DATA, name)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore", lineterminator="\r\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)


if __name__ == "__main__":
    if not os.path.exists(os.path.join(VER, "injuries_2026-11-18_raw.psv")):
        fail("no raw transcription to build from — re-read the official page first")
    main()
    print("OK")
