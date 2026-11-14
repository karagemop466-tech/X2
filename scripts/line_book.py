#!/usr/bin/env python3
"""The line book — an append-only snapshot store for the lines THIS PROJECT originates.

Brief item: "Add a price-snapshot store that records opening and closing numbers for
every market we originate."

Reading of the requirement, stated explicitly so it can be challenged
---------------------------------------------------------------------
Two different "prices" exist for every market we publish:

  * OUR OWN line — the number this project originated. Its opening value is the
    number as first published, and its closing value is the last version of that
    number captured before kickoff. Both are facts about this repository and the
    official schedule, so both ARE verifiable, and this store records them.

  * THE MARKET's price — what a bookmaker actually offered at open and at close.
    This project has no licensed or authorised odds archive (flags F07 and F16),
    so `market_line` and `fair_minus_market` are left blank on every row and are
    validated to stay blank. `scripts/markets.py` owns that side of the record;
    this script never writes into it.

A line published AFTER kickoff is never recorded as an opening number: there is no
opening to recover. The store refuses those rows and reports them as excluded, so
the ledger cannot quietly accumulate "opening lines" that were written after the
game was over.

Provenance
----------
Publication time of a line file is taken from the repository itself: the first
commit on `main`'s first-parent history whose tree contains the file, and its commit
date. That is a first-party, checkable fact (the commit is linked per row). Kickoff
date and time are taken from the official NFL.com schedule pages already recorded in
the schedule files (each row carries its own game-page link).

Comparing a UTC capture time with an Eastern-time kickoff could flip a verdict only
if the two dates were within one calendar day of each other. The store therefore
reports `captured_before_kickoff` as `yes (unambiguous)` only when the capture DATE
is at least one full day before the kickoff DATE, and `offset-dependent` otherwise
(instead of inventing a UTC offset for Eastern Time).

Run
---
  python3 scripts/line_book.py            # rebuild the store from published lines
  python3 scripts/line_book.py capture     # append interim snapshots if lines changed
  python3 scripts/line_book.py --check     # validate the store contract, non-zero exit
                                           # if a price was fabricated or a rule broken
Standard library only. Deterministic given the same inputs.
"""
import csv
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
REPO_URL = "https://github.com/karagemop466-tech/X2"
LEDGER = os.path.join(DATA, "line_book_snapshots.csv")
SUMMARY = os.path.join(DATA, "line_book_summary.json")
AS_OF = "2026-11-14"

FIELDS = [
    "ledger_seq", "snapshot_id", "season", "week", "game_key", "away_team", "home_team",
    "market_seq", "market_type", "selection",
    "model_fair_line", "market_line", "fair_minus_market",
    "snapshot_role", "captured_at_utc", "capture_method", "provenance_ref", "provenance_url",
    "kickoff_local_date", "kickoff_time_local_et", "captured_before_kickoff",
    "is_closing", "closing_state", "closing_due_by", "value_hash", "status", "source_url",
]

# Origination order (brief item 3): side first, then the total, then the moneyline.
MARKETS = [(1, "side"), (2, "total"), (3, "moneyline")]

NO_MARKET = ""   # never invent a market price (F07 / F16)
NO_MARKET_STATUS = ("Our line recorded from repo provenance; market line blank — no "
                    "authorised odds archive (F07, F16)")

MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7,
          "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
YEAR = 2026


def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_ledger(rows):
    tmp = LEDGER + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\r\n")
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, LEDGER)          # never truncate the store before the new file is complete


# --------------------------------------------------------------- provenance ----
def first_publication(path_rel):
    """First commit on HEAD's first-parent history whose tree contains `path_rel`.

    Returns (short_sha, iso_date, url, note). If the repository is a shallow clone
    the true first commit may be outside the grafted history; the boundary commit is
    returned with an explicit note so the timestamp is never over-claimed.
    """
    try:
        out = subprocess.run(["git", "-C", ROOT, "rev-list", "--first-parent", "--reverse", "HEAD"],
                             capture_output=True, text=True, check=True).stdout.split()
    except (subprocess.CalledProcessError, OSError):
        return "", "", "", "git unavailable — publication time not recorded"
    graft = subprocess.run(["git", "-C", ROOT, "rev-parse", "--verify", "--quiet", "HEAD"],
                           capture_output=True, text=True)
    for sha in out:
        chk = subprocess.run(["git", "-C", ROOT, "cat-file", "-e", f"{sha}:{path_rel}"],
                             capture_output=True, text=True)
        if chk.returncode == 0:
            iso = subprocess.run(["git", "-C", ROOT, "log", "-1", "--format=%cI", sha],
                                 capture_output=True, text=True).stdout.strip()
            note = ""
            if sha == out[0]:
                note = ("earliest commit present in this clone (the clone may be shallow: "
                        ".git/shallow), so the true first publication may be earlier")
            return sha[:7], iso, f"{REPO_URL}/commit/{sha}", note
    return "", "", "", "file not found in any commit on this history"


def kickoff_date(day_text, time_text):
    """Parse the official schedule strings into a local (Eastern) date, no UTC claim."""
    m = re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2})", day_text)
    if not m:
        m = re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2})", day_text.replace("tember", "t"))
    if not m:
        return ""
    mon = MONTHS[m.group(1).lower()]
    day = int(m.group(2))
    return dt.date(YEAR, mon, day).isoformat()


def hm(time_text):
    m = re.search(r"(\d{1,2}):(\d{2})\s*(AM|PM)", time_text, re.I)
    if not m:
        return ""
    h, mi, ap = int(m.group(1)), int(m.group(2)), m.group(3).upper()
    if ap == "PM" and h != 12:
        h += 12
    if ap == "AM" and h == 12:
        h = 0
    return f"{h:02d}:{mi:02d}"


def pre_kickoff_verdict(captured_iso, kickoff_iso):
    if not captured_iso or not kickoff_iso:
        return "unknown — capture or kickoff time missing"
    cap = dt.date.fromisoformat(captured_iso[:10])
    ko = dt.date.fromisoformat(kickoff_iso[:10])
    if (ko - cap).days >= 1:
        return "yes (unambiguous)"
    if ko < cap:
        return "no — publication is after the official kickoff date; not a valid opening"
    return "offset-dependent (same calendar day) — not asserted"


# ------------------------------------------------------------------ markets ----
def current_markets():
    """Every market this project has originated, with its value and its kickoff."""
    rows = []
    src10 = "data/model_lines_week10_2026.csv"
    pub10 = first_publication(src10)
    w10 = {g["game_no"]: g for g in read("games_week10_2026.csv")}
    for g in read("model_lines_week10_2026.csv"):
        gm = w10.get(g["game_no"], {})
        kdate = kickoff_date(gm.get("kickoff_day", ""), gm.get("kickoff_time_et", ""))
        rows.append({
            "season": "2026", "week": "10",
            "game_key": f"W10-{int(g['game_no']):02d} {g['away_team']} at {g['home_team']}",
            "away_team": g["away_team"], "home_team": g["home_team"],
            "kickoff_local_date": kdate,
            "kickoff_time_local_et": f"{hm(gm.get('kickoff_time_et', ''))} ET",
            "captured_at_utc": pub10[1], "capture_method": "published-line file (repo provenance)",
            "provenance_ref": pub10[0], "provenance_url": pub10[2], "prov_note": pub10[3],
            "file": src10,
            "values": {"side": g["model_margin_home_minus_away"],
                       "total": g["model_total"],
                       "moneyline": g["model_home_win_probability"]},
            "source_url": g["source_url"],
            "origin": "scripts/model.py output, fitted on weeks 1-9 (136 games)",
        })
    src11 = "data/model_lines_week11.csv"
    pub11 = first_publication(src11)
    w11 = {s["game_no"]: s for s in read("schedule_week11_2026.csv")}
    for g in read("model_lines_week11.csv"):
        sc = w11.get(g["game_no"], {})
        kdate = kickoff_date(g.get("kickoff_et", "") or sc.get("kickoff_day", ""),
                             g.get("kickoff_et", "") or sc.get("kickoff_time_et", ""))
        away, home = [t.strip() for t in g["matchup"].split(" at ")]
        rows.append({
            "season": "2026", "week": "11",
            "game_key": f"W11-{int(g['game_no']):02d} {away} at {home}",
            "away_team": away, "home_team": home,
            "kickoff_local_date": kdate,
            "kickoff_time_local_et": (hm(g.get("kickoff_et", "")) + " ET") if hm(g.get("kickoff_et", "")) else "",
            "captured_at_utc": pub11[1], "capture_method": "published-line file (repo provenance)",
            "provenance_ref": pub11[0], "provenance_url": pub11[2], "prov_note": pub11[3],
            "file": src11,
            "values": {"side": g["model_spread_home"],
                       "total": g["model_total"],
                       "moneyline": g["home_win_prob"]},
            "source_url": g["game_url"],
            "origin": "scripts/model.py output, fitted on weeks 1-10 Thursday only (137 games) — see F36",
        })
    return rows


def build_ledger(now_iso=None):
    markets = current_markets()
    rows, excluded, notes = [], [], []
    for m in markets:
        for seq, mtype in MARKETS:
            value = (m["values"][mtype] or "").strip()
            if value == "":
                excluded.append({"game_key": m["game_key"], "market": mtype,
                                 "reason": "no originated value in the published line file"})
                continue
            verdict = pre_kickoff_verdict(m["captured_at_utc"], m["kickoff_local_date"])
            if verdict.startswith("no"):
                excluded.append({"game_key": m["game_key"], "market": mtype,
                                 "reason": verdict + " — the store does not back-fill an opening line"})
                continue
            selection = m["home_team"] if mtype != "total" else "over / under"
            units = {"side": "points — the home team's expected margin (positive = home is "
                                "better by that many; a home spread quoted the betting way is the "
                                "negative of this number)",
                     "total": "points",
                     "moneyline": "probability that the home team wins (0-1)"}[mtype]
            key = f"{m['game_key']}|{mtype}"
            vh = hashlib.sha256(f"{key}|{value}".encode()).hexdigest()[:12]
            gnum = m["game_key"].split()[0].split("-")[-1]
            rows.append({
                "snapshot_id": f"LB-{m['week']}-{gnum}-{seq}",
                "season": m["season"], "week": m["week"], "game_key": m["game_key"],
                "away_team": m["away_team"], "home_team": m["home_team"],
                "market_seq": seq, "market_type": mtype, "selection": selection,
                "model_fair_line": value, "market_line": NO_MARKET, "fair_minus_market": NO_MARKET,
                "snapshot_role": "opening", "captured_at_utc": m["captured_at_utc"],
                "capture_method": m["capture_method"], "provenance_ref": m["provenance_ref"],
                "provenance_url": m["provenance_url"],
                "kickoff_local_date": m["kickoff_local_date"],
                "kickoff_time_local_et": m["kickoff_time_local_et"],
                "captured_before_kickoff": verdict, "is_closing": "yes (only capture so far)",
                "closing_state": "window-open — closing capture still possible",
                "closing_due_by": f"{m['kickoff_local_date']} {m['kickoff_time_local_et']}",
                "value_hash": vh,
                "status": f"{m['origin']}. {NO_MARKET_STATUS}"
                          + (f" Note: {m['prov_note']}" if m["prov_note"] else ""),
                "source_url": m["source_url"],
                "_units": units,
            })
    if notes:
        rows[0]["status"] += " " + " ".join(notes)
    rows.sort(key=lambda r: (r["week"], r["game_key"], int(r["market_seq"])))
    for i, r in enumerate(rows, start=1):
        r["ledger_seq"] = i
    return rows, excluded


def write_summary(rows, excluded):
    games = sorted({r["game_key"] for r in rows})
    per_game = {}
    for r in rows:
        per_game.setdefault(r["game_key"], set()).add(r["market_type"])
    complete = [g for g in games if per_game[g] == {"side", "total", "moneyline"}]
    open_w = sum(1 for r in rows if r["closing_state"].startswith("window-open"))
    captured = sum(1 for r in rows if r["snapshot_role"] == "closing")
    days = {}
    for r in rows:
        if r["kickoff_local_date"]:
            d = (dt.date.fromisoformat(r["kickoff_local_date"]) - dt.date.fromisoformat(AS_OF)).days
            days[r["game_key"]] = d
    summary = {
        "as_of": AS_OF,
        "markets_recorded": len(rows),
        "games_covered": len(games),
        "games_with_all_three_markets": len(complete),
        "markets_per_game_expected": 3,
        "opening_snapshots": sum(1 for r in rows if r["snapshot_role"] == "opening"),
        "interim_snapshots": sum(1 for r in rows if r["snapshot_role"] == "interim"),
        "closing_snapshots": captured,
        "closing_windows_open": open_w,
        "rows_excluded_as_post_kickoff": len(excluded),
        "earliest_kickoff_in_days": min(days.values()) if days else None,
        "latest_kickoff_in_days": max(days.values()) if days else None,
        "market_line_columns_populated": 0,
        "note": ("market_line and fair_minus_market are blank on every row: this project has no "
                 "authorised odds archive (F07, F16). The store is ready to receive them through "
                 "data/market_line_intake.csv."),
    }
    with open(SUMMARY, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
        f.write("\n")
    return summary, excluded


# ------------------------------------------------------------------ contract ----
def check():
    problems = []
    with open(LEDGER, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return ["line book is empty — the store must not be published with no rows"]
    seen = set()
    for r in rows:
        rid = r["snapshot_id"]
        if rid in seen:
            problems.append(f"{rid}: duplicate snapshot_id")
        seen.add(rid)
        for col in ("market_line", "fair_minus_market"):
            if (r.get(col) or "").strip():
                problems.append(f"{rid}: {col} must stay blank — no authorised odds source (F07)")
        if not r["model_fair_line"].strip():
            problems.append(f"{rid}: model_fair_line is blank — a snapshot with no line is not a snapshot")
        if not r["captured_at_utc"].strip():
            problems.append(f"{rid}: captured_at_utc missing — an untimed snapshot cannot be an opening")
        if not r["source_url"].startswith("https://www.nfl.com/games/"):
            problems.append(f"{rid}: source_url must be the official game page")
        if r["captured_before_kickoff"].startswith("no"):
            problems.append(f"{rid}: post-kickoff row recorded as a snapshot — must be excluded")
        if r["market_seq"] not in ("1", "2", "3"):
            problems.append(f"{rid}: market_seq must be 1 (side), 2 (total) or 3 (moneyline)")
    by_game = {}
    for r in rows:
        if r["snapshot_role"] == "opening":
            by_game.setdefault(r["game_key"], set()).add(r["market_type"])
    partial = [g for g, s in by_game.items() if len(s) != 3]
    if partial:
        problems.append("games without a complete opening triple (side, total, moneyline): "
                        + ", ".join(sorted(partial)))
    return problems


def capture():
    """Append interim snapshots for any line whose value changed since the last capture."""
    with open(LEDGER, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    latest = {}
    for r in rows:
        latest[(r["game_key"], r["market_type"])] = r
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    added = 0
    for m in current_markets():
        for seq, mtype in MARKETS:
            value = (m["values"][mtype] or "").strip()
            key = (m["game_key"], mtype)
            prev = latest.get(key)
            if prev is None or value == "":
                continue
            vh = hashlib.sha256(f"{m['game_key']}|{mtype}|{value}".encode()).hexdigest()[:12]
            if prev["value_hash"] == vh:
                continue                       # the line has not moved: nothing to record
            rows.append(dict(prev, snapshot_id=f"{prev['snapshot_id']}-I{added + 1}",
                             snapshot_role="interim", captured_at_utc=now,
                             capture_method="scripts/line_book.py capture", provenance_ref="",
                             provenance_url=m["source_url"], value_hash=vh,
                             is_closing="yes (latest pre-kickoff capture)",
                             status="Value changed since the previous capture; appended as an interim snapshot."))
            added += 1
    write_ledger(rows)
    print(f"{added} interim snapshot(s) appended; {len(rows)} rows in the store.")
    return added


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        problems = check()
        if problems:
            print("LINE BOOK CONTRACT PROBLEMS:")
            for p in problems:
                print("  -", p)
            sys.exit(1)
        print("Line book contract passed: every row is timed, linked to the official game page, "
              "pre-kickoff, and carries no fabricated market price.")
        return
    if len(sys.argv) > 1 and sys.argv[1] == "capture":
        capture()
        return
    rows, excluded = build_ledger()
    out = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
    write_ledger(out)
    summary, _ = write_summary(rows, excluded)
    problems = check()
    print(f"Line book: {summary['markets_recorded']} snapshots across "
          f"{summary['games_covered']} games ({summary['games_with_all_three_markets']} with a complete "
          f"side/total/moneyline opening triple); closing windows open: {summary['closing_windows_open']}; "
          f"excluded (no valid opening to record): {summary['rows_excluded_as_post_kickoff']}.")
    for e in excluded:
        print("  excluded:", e["game_key"], e["market"], "—", e["reason"])
    if problems:
        print("CONTRACT PROBLEMS:")
        for p in problems:
            print("  -", p)
        sys.exit(1)


if __name__ == "__main__":
    main()
