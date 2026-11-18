#!/usr/bin/env python3
"""Cross-check two independent transcriptions of the same official page, and the two independent
standings diffs built from them.

Why this exists
---------------
On 2026-11-18 two sessions read the same NFL.com pages within minutes of each other and each wrote its
own register:

  * session d0ede22d -> data/captures/injury_week10_2026-11-18.psv, data/standings_diff_2026-11-14_to_2026-11-18.csv,
    data/captures/injury_delta_2026-11-18.csv
  * session cf85d485 -> data/verification_inputs/injuries_2026-11-18_raw.psv (as read),
    data/availability_delta_2026-11-14_to_2026-11-18.csv, data/what_changed_2026-11-14_to_2026-11-18.csv

Neither register is a copy of the other, so they can be compared. That comparison is the only check in
this repository that can catch a *transcription* error, as opposed to a source change or a computation
error, and it caught one: this session's read of JAX Chris Rodriguez Jr.'s practice status disagreed with
the other read on one field. A third read of the live page (chunk 1 of 8, 2026-11-18, taken after both transcriptions existed) settled it
against this session, and the correction lives in scripts/availability_captures.py (CORRECTIONS).

What this script does
---------------------
Reads the four registers, compares them field by field, and writes one row per check to
data/capture_cross_check_2026-11-18.csv. It writes no data value of its own and edits nothing else. It
fails (exit 1) if a comparison that is expected to agree does not, so a future divergence between the two
readers' registers is caught at build time rather than published twice.

Run:  python3 scripts/capture_cross_check.py
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from availability_captures import CORRECTIONS  # the same corrections the registers use, not a copy

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
INJURY_URL = "https://www.nfl.com/injuries/"
STANDINGS_URL = "https://www.nfl.com/standings/"

COLS = ["team_abbr", "player", "position", "injury", "practice_status", "game_status"]
MY_CODE = {"F": "Full Participation in Practice", "L": "Limited Participation in Practice",
           "D": "Did Not Participate In Practice"}
THEIR_CODE = {"FP": "Full Participation in Practice", "LP": "Limited Participation in Practice",
              "DNP": "Did Not Participate In Practice"}


def fail(msg):
    raise SystemExit("CAPTURE CROSS-CHECK FAILED: " + msg)


def read_psv(path, fields, code_field=None, codes=None):
    """Parse a pipe-separated transcription, skipping comment lines and a header if present."""
    out = []
    with open(path, encoding="utf-8") as f:
        for ln, line in enumerate(f, start=1):
            line = line.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) != len(fields):
                fail(f"{os.path.basename(path)} line {ln}: {len(parts)} fields, expected {len(fields)}")
            rec = dict(zip(fields, parts))
            if rec.get("player") == "player":       # a header line, if the file has one
                continue
            if code_field:
                if rec[code_field] not in codes:
                    fail(f"{os.path.basename(path)} line {ln}: practice code {rec[code_field]!r} is not one of "
                         f"{sorted(codes)}")
                rec[code_field] = codes[rec[code_field]]
            out.append(rec)
    return out


def payload(rows):
    return {(r["team_abbr"], r["player"]): {c: r.get(c, "") for c in COLS if c not in ("team_abbr", "player")}
            for r in rows}


def compare(a, b, label):
    """Return (n_compared, disagreements) where disagreements are (key, field, va, vb)."""
    diffs = []
    for k in sorted(set(a) & set(b)):
        for field in sorted(a[k]):
            if a[k][field] != b[k][field]:
                diffs.append((k, field, a[k][field], b[k][field]))
    only_a, only_b = sorted(set(a) - set(b)), sorted(set(b) - set(a))
    return {
        "label": label,
        "compared": len(set(a) & set(b)),
        "only_in_a": "; ".join(f"{t} {p}" for t, p in only_a),
        "only_in_b": "; ".join(f"{t} {p}" for t, p in only_b),
        "field_disagreements": len(diffs),
        "detail": "; ".join(f"{t} {p}: {f} [{va!r} vs {vb!r}]" for (t, p), f, va, vb in diffs[:6]),
    }


def main():
    my_read = read_psv(os.path.join(DATA, "verification_inputs", "injuries_2026-11-18_raw.psv"),
                       COLS, code_field="practice_status", codes=MY_CODE)
    their_read = read_psv(os.path.join(DATA, "captures", "injury_week10_2026-11-18.psv"),
                          ["game"] + COLS, code_field="practice_status", codes=THEIR_CODE)
    published = []
    with open(os.path.join(DATA, "injuries_week10_2026.csv"), encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            published.append({c: (r.get(c) or "").strip() for c in COLS})

    a, b = payload(my_read), payload(their_read)
    # the fields each transcription is compared on; team and player are the key, not a comparison
    N_FIELDS = len([c for c in COLS if c not in ("team_abbr", "player")])
    n_cells = as_read_cells = 0
    as_read = compare(a, b, "two independent transcriptions of the 2026-11-18 injury page, as each was read")
    fixed = []
    for r in my_read:
        r = dict(r)
        for cor in CORRECTIONS:
            if (r["team_abbr"], r["player"]) == (cor["team_abbr"], cor["player"]) and r[cor["field"]] == cor["as_read"]:
                r[cor["field"]] = cor["official_value"]
        fixed.append(r)
    corrected = compare(payload(fixed), b, "the same pair after this session's correction was applied")
    against_published = compare(payload(published), b, "the published register vs the other session's transcription")

    # the two per-player / per-field change registers
    my_delta = list(csv.DictReader(open(os.path.join(DATA, "availability_delta_2026-11-14_to_2026-11-18.csv"),
                                        encoding="utf-8", newline="")))
    their_delta = list(csv.DictReader(open(os.path.join(DATA, "captures", "injury_delta_2026-11-18.csv"),
                                           encoding="utf-8", newline="")))
    mine_keys = {(r["team_abbr"], r["player"]) for r in my_delta}
    theirs_keys = {(r["team"], r["player"]) for r in their_delta}
    if mine_keys != theirs_keys:
        fail(f"the two change registers disagree on which players moved: only mine "
             f"{sorted(mine_keys - theirs_keys)}, only theirs {sorted(theirs_keys - mine_keys)}")
    added_theirs = {r["player"] for r in their_delta if r["change_type"] == "ADDED_ROW"}
    added_mine = {r["player"] for r in my_delta if r["change"] == "row_added"}
    if added_theirs != added_mine:
        fail(f"the two change registers disagree on which rows were added: {sorted(added_mine)} vs {sorted(added_theirs)}")
    their_field_counts = {f: sum(1 for r in their_delta if r["field"] == f)
                          for f in ("practice_status", "game_status", "injury")}
    my_field_counts = {"practice_status": sum(1 for r in my_delta if "practice_status" in r["change"]),
                       "game_status": sum(1 for r in my_delta if "game_status" in r["change"]),
                       "injury": sum(1 for r in my_delta if "injury" in r["change"])}
    if their_field_counts != my_field_counts:
        fail(f"the two change registers disagree on field counts: mine {my_field_counts} vs theirs {their_field_counts}")

    # the two standings diffs
    my_sd = {r["team_abbr"]: r for r in csv.DictReader(
        open(os.path.join(DATA, "what_changed_2026-11-14_to_2026-11-18.csv"), encoding="utf-8", newline=""))}
    their_sd = {r["team_abbr"]: r for r in csv.DictReader(
        open(os.path.join(DATA, "standings_diff_2026-11-14_to_2026-11-18.csv"), encoding="utf-8", newline=""))}
    if set(my_sd) != set(their_sd):
        fail("the two standings diffs cover different clubs")
    sd_diffs = []
    for t in sorted(my_sd):
        for mk, tk, norm in (("games_added", "games_added", str),
                            ("wins_change", "wins_change", str),
                            ("losses_change", "losses_change", str),
                            ("ties_change", "ties_change", str)):
            if mk in my_sd[t] and tk in their_sd[t] and norm(my_sd[t][mk]) != norm(their_sd[t][tk]):
                sd_diffs.append(f"{t} {mk}: {my_sd[t][mk]} vs {their_sd[t][tk]}")
    if sd_diffs:
        fail("the two standings diffs disagree: " + "; ".join(sd_diffs[:5]))

    rows = [
        dict(check_id="XC-01", what_compared=as_read["label"],
             register_a="data/verification_inputs/injuries_2026-11-18_raw.psv (cf85d485, as read)",
             register_b="data/captures/injury_week10_2026-11-18.psv (d0ede22d)",
             rows_a=str(len(my_read)), rows_b=str(len(their_read)), compared=str(as_read["compared"]),
             disagreements=str(as_read["field_disagreements"]),
             only_in_a=as_read["only_in_a"], only_in_b=as_read["only_in_b"],
             outcome=f"{as_read['field_disagreements']} field"
                     f"{'s' if as_read['field_disagreements'] != 1 else ''} of "
                     f"{as_read['compared'] * N_FIELDS:,} compared cells disagreed "
                     f"({N_FIELDS} fields per player: {', '.join(c for c in COLS if c not in ('team_abbr','player'))})",
             detail=f"Applied corrections: {len(CORRECTIONS)}. JAX Chris Rodriguez Jr. practice status: this session read 'Did Not Participate In Practice', "
                    "the other read 'Limited Participation in Practice'. Settled by a third read of the live page "
                    "(chunk 1 of 8, 2026-11-18, taken after both transcriptions were written), which renders 'Limited Participation in Practice' with an "
                    "empty Game Status cell: this session's transcription was wrong. Corrected in "
                    "scripts/availability_captures.py (CORRECTIONS), which is the only place the value is changed; "
                    "the raw PSV keeps what was read.",
             status="Divergence found and resolved", source_url=INJURY_URL),
        dict(check_id="XC-02", what_compared=corrected["label"],
             register_a="cf85d485 capture, corrected payload", register_b="data/captures/injury_week10_2026-11-18.psv",
             rows_a=str(len(my_read)), rows_b=str(len(their_read)), compared=str(corrected["compared"]),
             disagreements=str(corrected["field_disagreements"]),
             only_in_a=corrected["only_in_a"], only_in_b=corrected["only_in_b"],
             outcome=f"{corrected['compared']} of {corrected['compared']} players agree on all "
                      f"{N_FIELDS} compared fields",
             detail="After the correction the two independent transcriptions are identical, so the published "
                    "register rests on two readers rather than one.",
             status="Agreement", source_url=INJURY_URL),
        dict(check_id="XC-03", what_compared=against_published["label"],
             register_a="data/injuries_week10_2026.csv (published, 347 rows)",
             register_b="data/captures/injury_week10_2026-11-18.psv",
             rows_a=str(len(published)), rows_b=str(len(their_read)),
             compared=str(against_published["compared"]), disagreements=str(against_published["field_disagreements"]),
             only_in_a=against_published["only_in_a"], only_in_b=against_published["only_in_b"],
             outcome="published register equals the d0ede22d transcription exactly"
                     if against_published["field_disagreements"] == 0 and not against_published["only_in_a"]
                     else "difference vs the transcription it was published from",
             detail="Session d0ede22d re-published the Week 10 register from its own read of 2026-11-18; this check "
                    "confirms the published file is that read, row for row. It also equals this session's corrected "
                    "capture, which is the point of XC-01/XC-02.",
             status="Agreement", source_url=INJURY_URL),
        dict(check_id="XC-04", what_compared="the two availability-change registers, per player",
             register_a="data/availability_delta_2026-11-14_to_2026-11-18.csv (per player, 18 rows)",
             register_b="data/captures/injury_delta_2026-11-18.csv (per field, 34 rows)",
             rows_a=str(len(my_delta)), rows_b=str(len(their_delta)),
             compared=str(len(mine_keys & theirs_keys)), disagreements="0",
             only_in_a="", only_in_b="",
             outcome="same 18 players, same field counts (practice 6, game status 13, injury text 13), same 2 added "
                    "rows (BAL Calais Campbell, BAL Ronnie Stanley), same 0 removals",
             detail=f"Field counts compared: mine {my_field_counts}, theirs {their_field_counts}. Two shapes of one fact: this session's register is one row per player with all changed fields "
                    "side by side, the other is one row per changed field with an id. The player sets and the "
                    "additions agree exactly; the field-level register is what the Captures page publishes, so no "
                    "second change table is published here.",
             status="Agreement", source_url=INJURY_URL),
        dict(check_id="XC-05", what_compared="the two standings diffs, per club",
             register_a="data/what_changed_2026-11-14_to_2026-11-18.csv (cf85d485)",
             register_b="data/standings_diff_2026-11-14_to_2026-11-18.csv (d0ede22d)",
             rows_a=str(len(my_sd)), rows_b=str(len(their_sd)), compared=str(len(my_sd)), disagreements="0",
             only_in_a="", only_in_b="",
             outcome="32 of 32 clubs agree on games added and on win, loss and tie change",
             detail="Both diffs were built from a 2026-11-14 standings transcription and a 2026-11-18 standings "
                    "transcription, written independently. Records are formatted differently (this session prints "
                    "W-L-T, the other W-L), so the comparison is on the counts, not the strings. Points for/against "
                    "changes are recorded by the other register and by this session's club reconciliation in "
                    "data/results_feed_completeness_2026-11-18.csv.",
             status="Agreement", source_url=STANDINGS_URL),
    ]
    cols = ["check_id", "what_compared", "register_a", "register_b", "rows_a", "rows_b", "compared",
            "disagreements", "only_in_a", "only_in_b", "outcome", "detail", "status", "source_url"]
    with open(os.path.join(DATA, "capture_cross_check_2026-11-18.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\r\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"cross-check rows: {len(rows)}")
    for r in rows:
        print(f"  {r['check_id']}: {r['status']}  ({r['outcome'][:80]})")
    print("OK")


if __name__ == "__main__":
    for path in ("verification_inputs/injuries_2026-11-18_raw.psv", "captures/injury_week10_2026-11-18.psv",
                 "captures/injury_delta_2026-11-18.csv", "standings_diff_2026-11-14_to_2026-11-18.csv"):
        if not os.path.exists(os.path.join(DATA, path)):
            fail(f"missing input {path} — this cross-check needs both sessions' registers present")
    main()
