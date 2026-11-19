#!/usr/bin/env python3
"""Roster-event register from the official NFL.com transactions logs (T133, D19 / R56).

Purpose: treat roster turnover as a dated, sourced data event. Depth, availability
and lineup evidence must be read against the last official roster event, not trusted
as durable (brief item "Treat roster turnover as a first-class data event").

Source of every row: the NFL.com transactions pages named in `SOURCE_PAGES`, read
on READ_DATE with the fetch tool. Rows are transcribed exactly as the log prints them
(date, name, from club, to club, transaction text). Nothing is inferred: a field the
log does not print is left blank. Coverage is only what the logs printed for the months
listed in SOURCE_PAGES; August and September 2026 were NOT read in this session and are
reported as NOT CHECKED, never as "no events".

Outputs (CRLF, the repository's CSV convention):
  data/roster_events_2026.csv         one row per logged event
  data/roster_events_checks_2026.csv  machine checks (exit 1 if any FAIL)
  data/roster_events_join_2026.csv    event players found in other registers (flags, not verdicts)

Usage: python3 scripts/roster_events.py          (regenerates and checks)
       python3 scripts/roster_events.py --check  (checks the committed files only)
"""
import csv
import datetime as dt
import glob
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
READ_DATE = "2026-11-19"
WINDOW = ("2026-10-01", "2026-11-18")  # months read; last date any row may carry

TRADES_NOV = "https://www.nfl.com/transactions/league/trades/2026/11"
RESERVE_NOV = "https://www.nfl.com/transactions/league/reserve-list/2026/11"
RESERVE_OCT = "https://www.nfl.com/transactions/league/reserve-list/2026/10"

# (date as printed MM/DD, from club, to club, player, transaction text)
# Club names are the NFL.com club nicknames as printed; the abbreviation map is below.
TRADES_NOV_ROWS = [
    ("11/10", "Falcons", "Jaguars", "Jessie Bates", "Traded"),
    ("11/10", "Eagles", "Jaguars", "Jordan Davis", "Traded"),
    ("11/10", "Titans", "Bills", "Amani Hooker", "Traded"),
    ("11/10", "Colts", "49ers", "Keenan Allen", "Traded"),
    ("11/10", "Raiders", "Vikings", "Kirk Cousins", "Traded"),
    ("11/10", "Chargers", "Broncos", "Daiyan Henley", "Traded"),
    ("11/10", "Colts", "Chiefs", "Josh Downs", "Traded"),
    ("11/10", "Falcons", "Ravens", "Ryan Neuzil", "Traded"),
    ("11/10", "Ravens", "Falcons", "Andrew Vorhees", "Traded"),
    ("11/09", "Jets", "Lions", "Andre Cisco", "Traded"),
    ("11/09", "Saints", "Jaguars", "Davon Godchaux", "Traded"),
    ("11/06", "Cardinals", "Ravens", "Jacoby Brissett", "Traded"),
]

RESERVE_OCT_ROWS = [
    ("10/31", "Chiefs", "L'Jarius Sneed", "Reserve/Injured"),
    ("10/31", "Jets", "T'Vondre Sweat", "Reserve/Injured"),
    ("10/31", "Raiders", "Patrick Johnson", "Reserve/Injured"),
    ("10/31", "Broncos", "RJ Harvey", "Reserve/Injured"),
    ("10/31", "Chargers", "Derwin James", "Reserve/Injured"),
    ("10/29", "Panthers", "Akayleb Evans", "Reserve/Injured"),
    ("10/28", "Commanders", "Terry McLaurin", "Reserve/Injured"),
    ("10/28", "Texans", "Jaylin Noel", "Reserve/Injured"),
    ("10/28", "Eagles", "Dameon Pierce", "Reserve/Injured"),
    ("10/27", "Panthers", "Taylor Moton", "Reserve/Injured"),
    ("10/27", "Bengals", "Erick All", "Reserve/Injured"),
    ("10/27", "Giants", "Tyrone Tracy Jr.", "Reserve/Injured"),
    ("10/27", "Colts", "Cam Taylor-Britt", "Reserve/Injured"),
    ("10/27", "Cardinals", "Jalen Brooks", "Reserve/Injured"),
    ("10/26", "Bills", "C.J. Gardner-Johnson", "Reserve/Suspended By Commissioner-Less than One Year"),
    ("10/26", "Packers", "Jacob Monk", "Reserve/Injured"),
    ("10/24", "Falcons", "Michael Jerrell", "Reserve/Injured"),
    ("10/24", "Panthers", "Thomas Incoom", "Reserve/Injured"),
    ("10/24", "Browns", "Teven Jenkins", "Reserve/Injured"),
    ("10/24", "Chiefs", "Brashard Smith", "Reserve/Injured"),
    ("10/24", "Giants", "Tremaine Edmunds", "Reserve/Injured"),
    ("10/24", "Jets", "Francisco Mauigoa", "Reserve/Injured"),
    ("10/24", "Broncos", "Tyler Badie", "Reserve/Injured"),
    ("10/24", "Broncos", "Jonah Elliss", "Reserve/Injured"),
    ("10/24", "Ravens", "Tavius Robinson", "Reserve/Injured"),
]

RESERVE_NOV_ROWS = [
    ("11/18", "Steelers", "Mason McCormick", "Reserve/Injured"),
    ("11/18", "Chiefs", "Jared Wiley", "Reserve/Injured"),
    ("11/18", "Lions", "Aidan Hutchinson", "Reserve/Injured"),
    ("11/18", "Vikings", "Bo Richter", "Reserve/Injured"),
    ("11/17", "Texans", "Azeez Al-Shaair", "Reserve/Injured"),
    ("11/17", "Dolphins", "Zeek Biggers", "Reserve/Injured"),
    ("11/17", "Dolphins", "Jordan Phillips", "Reserve/Injured"),
    ("11/17", "Cardinals", "Andrew Wingard", "Reserve/Injured"),
    ("11/17", "Cardinals", "Jordan Burch", "Reserve/Injured"),
    ("11/17", "Bills", "Ar'maj Reed-Adams", "Reserve/Injured"),
    ("11/17", "Colts", "Jaylon Carlies", "Reserve/Injured"),
    ("11/17", "Titans", "Wan'Dale Robinson", "Reserve/Injured"),
    ("11/16", "Rams", "Dylan McMahon", "Reserve/Injured"),
    ("11/16", "Chargers", "Branson Taylor", "Reserve/Injured"),
    ("11/14", "Saints", "Christen Miller", "Reserve/Injured"),
    ("11/14", "Patriots", "TreVeyon Henderson", "Reserve/Injured"),
    ("11/14", "Browns", "Michael Burton", "Reserve/Injured"),
    ("11/14", "Colts", "Mo Alie-Cox", "Reserve/Injured"),
    ("11/14", "Colts", "Akeem Davis-Gaither", "Reserve/Injured"),
    ("11/14", "Titans", "Peter Skoronski", "Reserve/Injured"),
    ("11/14", "Titans", "Tommy Townsend", "Reserve/Injured"),
    ("11/14", "Cowboys", "Tyler Goodson", "Reserve/Injured"),
    ("11/14", "Packers", "Josh Whyle", "Reserve/Injured"),
    ("11/12", "Rams", "Puka Nacua", "Reserve/Injured"),
    ("11/10", "Rams", "Jordan Whittington", "Reserve/Injured"),
]

CLUB_ABBR = {
    "Cardinals": "ARI", "Falcons": "ATL", "Ravens": "BAL", "Bills": "BUF", "Panthers": "CAR",
    "Bears": "CHI", "Bengals": "CIN", "Browns": "CLE", "Cowboys": "DAL", "Broncos": "DEN",
    "Lions": "DET", "Packers": "GB", "Texans": "HOU", "Colts": "IND", "Jaguars": "JAX",
    "Chiefs": "KC", "Raiders": "LV", "Chargers": "LAC", "Rams": "LA", "Dolphins": "MIA",
    "Vikings": "MIN", "Patriots": "NE", "Saints": "NO", "Giants": "NYG", "Jets": "NYJ",
    "Eagles": "PHI", "Steelers": "PIT", "49ers": "SF", "Seahawks": "SEA", "Buccaneers": "TB",
    "Titans": "TEN", "Commanders": "WAS",
}

FIELDS = ["event_id", "log_month", "event_date", "transaction", "player",
          "from_club", "to_club", "from_abbr", "to_abbr", "source_url", "read_date"]

CHECK_FIELDS = ["check_id", "result", "detail"]
JOIN_FIELDS = ["event_id", "player", "event_date", "transaction", "register", "matched_line", "note"]

# Registers searched for event players. These are the depth / availability files
# the brief asks to be checked against roster events.
JOIN_REGISTERS = [
    "depth_chart_strings_2026.csv", "depth_replacement.csv", "replacement_depth_week10_2026.csv",
    "injuries_week10_2026.csv", "confirmed_availability_week10_2026.csv",
    "matchup_matrix_week11.csv", "matchup_pairs_week11.csv", "roster_ir_sweep_2026-11-18.csv",
    "event_risk_week11.csv", "depth_deficiency.csv", "news_week10_2026.csv",
]


def iso(md):
    """'11/10' -> '2026-11-10' (the logs print MM/DD inside the 2026 season page)."""
    m, d = md.split("/")
    return f"2026-{int(m):02d}-{int(d):02d}"


def build_rows():
    rows = []
    n = {"TR": 0, "RL": 0}

    def add(prefix, month, page, md, frm, to, player, txn):
        n[prefix] += 1
        rows.append({
            "event_id": f"RE-{prefix}-{n[prefix]:03d}",
            "log_month": month,
            "event_date": iso(md),
            "transaction": txn,
            "player": player,
            "from_club": frm,
            "to_club": to,
            "from_abbr": CLUB_ABBR[frm],
            "to_abbr": CLUB_ABBR[to],
            "source_url": page,
            "read_date": READ_DATE,
        })

    for md, frm, to, player, txn in TRADES_NOV_ROWS:
        add("TR", "2026-11", TRADES_NOV, md, frm, to, player, txn)
    # Reserve rows: the log prints one club (From = To); it is stored in from_club and to_club.
    for md, club, player, txn in RESERVE_OCT_ROWS:
        add("RL", "2026-10", RESERVE_OCT, md, club, club, player, txn)
    for md, club, player, txn in RESERVE_NOV_ROWS:
        add("RL", "2026-11", RESERVE_NOV, md, club, club, player, txn)
    # Event ids: TR rows first, then RL. The Oct/Nov split is carried by log_month.
    return rows


def write_csv(path, fields, rows):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\r\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def norm(s):
    return re.sub(r"[^a-z]", "", s.lower())


def run_checks(events):
    out = []

    def rec(cid, ok, detail):
        out.append({"check_id": cid, "result": "PASS" if ok else "FAIL", "detail": detail})

    trades = [e for e in events if e["log_month"] == "2026-11" and e["transaction"] == "Traded"]
    rec("RE-01", len(trades) == 12,
        f"November trades log rows read = {len(trades)} (pinned 12; {TRADES_NOV})")
    oct_rl = [e for e in events if e["log_month"] == "2026-10"]
    rec("RE-02", len(oct_rl) == 25, f"October reserve-list rows read = {len(oct_rl)} (pinned 25; {RESERVE_OCT})")
    nov_rl = [e for e in events if e["log_month"] == "2026-11" and e["source_url"] == RESERVE_NOV]
    rec("RE-03", len(nov_rl) == 25, f"November reserve-list rows read = {len(nov_rl)} (pinned 25; {RESERVE_NOV})")

    bad_dates = [e["event_id"] for e in events if not (WINDOW[0] <= e["event_date"] <= WINDOW[1])]
    rec("RE-04", not bad_dates, f"every event date inside the read window {WINDOW[0]}..{WINDOW[1]}"
        + (f"; outside: {bad_dates}" if bad_dates else ""))
    bad_src = [e["event_id"] for e in events if not e["source_url"].startswith("https://www.nfl.com/transactions/")]
    rec("RE-05", not bad_src, "every row links to an NFL.com transactions page"
        + (f"; not: {bad_src}" if bad_src else ""))
    keys = [(e["transaction"], e["player"], e["event_date"], e["from_club"], e["to_club"]) for e in events]
    dups = sorted({k for k in keys if keys.count(k) > 1})
    rec("RE-06", not dups, "no duplicate (transaction, player, date, from, to)" + (f"; duplicates: {dups}" if dups else ""))
    unmapped = sorted({c for e in events for c in (e["from_club"], e["to_club"]) if c not in CLUB_ABBR})
    rec("RE-07", not unmapped, "every club name maps to a standard abbreviation" + (f"; unmapped: {unmapped}" if unmapped else ""))

    colts_recv = {e["player"] for e in trades if e["from_abbr"] == "IND" and e["event_date"] == "2026-11-10"}
    rec("RE-08", {"Keenan Allen", "Josh Downs"} <= colts_recv,
        "Colts 11/10 trades present: Keenan Allen (IND to SF) and Josh Downs (IND to KC) — both WRs per the brief's "
        "description; the club-article text itself is NOT located or read (see RE-11)")

    bal = [e for e in trades if e["to_abbr"] == "BAL" and e["player"] == "Jacoby Brissett"]
    rec("RE-09", len(bal) == 1, "Jacoby Brissett traded to BAL on 2026-11-06 (from ARI) is in the November trades log")
    jackson = [e for e in events if e["player"] in ("Lamar Jackson", "Tyler Huntley")]
    out.append({"check_id": "RE-10", "result": "INFO" if not jackson else "FLAG",
                "detail": "Lamar Jackson and Tyler Huntley are "
                          + ("NOT on the October or November reserve logs as read" if not jackson else "on a log read (see register)")
                          + "; an August or September injured-reserve entry cannot be ruled out because those logs were "
                            "not read, so the brief's Baltimore example stays UNVERIFIED"})
    out.append({"check_id": "RE-11", "result": "NOT CHECKED",
                "detail": "Colts Week 10 article (the 'release' that carries the depth chart) was not located on "
                          "colts.com or nfl.com in this session; the trade dates come from the NFL trades log only"})
    out.append({"check_id": "RE-12", "result": "NOT CHECKED",
                "detail": "August and September 2026 transaction logs were not read; this register is NOT a "
                          "season-long roster-event history"})
    return out


def join(events):
    """Find each event player's name in the depth / availability registers. Flags only."""
    reg_rows = {}
    for name in JOIN_REGISTERS:
        path = os.path.join(DATA, name)
        if os.path.exists(path):
            with open(path, encoding="utf-8", newline="") as fh:
                reg_rows[name] = list(csv.reader(fh))
    out = []
    for e in events:
        key = norm(e["player"])
        if len(key) < 6:
            continue
        for reg, rows in reg_rows.items():
            for i, row in enumerate(rows[1:], start=2):
                if any(key in norm(cell) for cell in row):
                    out.append({"event_id": e["event_id"], "player": e["player"], "event_date": e["event_date"],
                                "transaction": e["transaction"], "register": reg,
                                "matched_line": str(i),
                                "note": "name found in a depth/availability register; the register row was NOT "
                                        "re-read against the event — review by hand"})
                    break  # one hit per event per register is enough to flag
    return out


def main():
    check_only = "--check" in sys.argv
    ev_path = os.path.join(DATA, "roster_events_2026.csv")
    if not check_only:
        rows = build_rows()
        write_csv(ev_path, FIELDS, rows)
    events = read_csv(ev_path)
    checks = run_checks(events)
    write_csv(os.path.join(DATA, "roster_events_checks_2026.csv"), CHECK_FIELDS, checks)
    if not check_only:
        write_csv(os.path.join(DATA, "roster_events_join_2026.csv"), JOIN_FIELDS, join(events))
    fails = [c for c in checks if c["result"] == "FAIL"]  # FLAG/INFO/NOT CHECKED never fail the build
    for c in checks:
        print(f"{c['check_id']} {c['result']}: {c['detail']}")
    print(f"events={len(events)} fails={len(fails)}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
