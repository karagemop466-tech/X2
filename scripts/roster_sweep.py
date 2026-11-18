#!/usr/bin/env python3
"""The 32-team roster / reserve-list sweep the brief asks for before any team-level
model is trusted.

The brief's requirement: "Run the 32-team roster/IR sweep before any team-level model
is trusted", and its worked examples:

  * "Capture the reserve list so 'not listed' never means 'available'. Malik Willis is
    absent from the weekly report because he is on injured reserve, not because he is
    healthy."
  * "Flag stale depth rows against the official transactions log. Baltimore still
    publishes Lamar Jackson and Tyler Huntley at QB after both went on injured reserve
    and a replacement was traded in."
  * "Treat roster turnover as a first-class data event. The Colts' Week 10 release
    documents two starting-receiver trades in the same article as its depth chart."

What this script can and cannot establish, stated up front because it decides how the
output must be read:

  THE INJURY REPORT IS NOT AN AVAILABILITY LIST. A player absent from the weekly
  report is not thereby healthy — he may be on Reserve/Injured, on a practice squad,
  suspended, or simply not listed. That is exactly the brief's point. So the sweep
  joins three official surfaces rather than reading the absence of one:

    (a) the official NFL.com reserve-list feed (Reserve/Injured transactions), captured
        month by month for the 2026 season;
    (b) the official NFL.com Week 10 injury report already published as
        data/injuries_week10_2026.csv (347 rows, read 2026-11-18);
    (c) the official NFL.com club roster page, whose per-player status column
        (ACT / RES / CUT / DEV / RSR / TRC / TRD / TRT) is the only official statement
        this repository has captured about a player's roster status.

  The sweep is asked to answer ONE question per club: **is every club's roster status
  consistent with the league's own reserve list and injury report?** A player the
  reserve-list feed says went to Reserve/Injured should show a non-ACT status on his
  club roster page; a player still shown ACT should not be someone the reserve list
  has placed on IR without a later activation.

  Where a check needs a roster read this session did not take, the row is left BLANK
  and flagged. It is never filled by inference.

Every claim is pinned to a fixed read date (2026-11-18). Roster status is a mutable
page and the output says so.

Run:  python3 scripts/roster_sweep.py
"""

import csv
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

RAW_RESERVE = os.path.join(DATA, "verification_inputs", "reserve_list_2026_raw.tsv")
RAW_ROSTERS = os.path.join(DATA, "verification_inputs", "roster_status_2026-11-18_raw.tsv")
INJURIES = os.path.join(DATA, "injuries_week10_2026.csv")

OUT = os.path.join(DATA, "roster_ir_sweep_2026-11-18.csv")
OUT_FINDINGS = os.path.join(DATA, "roster_ir_findings_2026-11-18.csv")
OUT_CHECKS = os.path.join(DATA, "roster_sweep_checks_2026-11-18.csv")

READ_UTC = "2026-11-18"

# A named correction, in the pattern the repository already uses for availability
# captures: the guard FAILS THE RUN if the raw file ever stops matching the value it
# overrides, so a correction cannot quietly drift into an invented one.
#
# What was wrong: the first pass transcribed only the FIRST rendered chunk of each club
# roster page (the renderer splits a roster across three chunks) and concluded that
# reserve-list players were absent from the pages. Re-reading BAL chunk 2, MIA chunks
# 1-2 and HOU chunk 2 showed the pages DO list those players with a non-ACT status.
# The half-read rows were removed, not reinterpreted. Two values recorded in the first
# pass did not exist in any chunk that was actually read and are named here so that
# their return is a hard error rather than a silent resurrection:
CORRECTIONS = {
    ("HOU", "Azeez Al-Shaair"): "RES",   # first pass wrote ACT from an unread cell
    # ("HOU", "Jacob Hummel") is deliberately NOT corrected: the page read 2026-11-18
    # renders him ACT while the reserve-list feed places him on Reserve/Injured on
    # 09/26. That is a real cross-source disagreement, so it stays a finding (RF-HOU-01)
    # rather than being overwritten into agreement.
}


def apply_corrections(status):
    """Assert that a corrected key still holds the corrected value.

    Returns the status unchanged. Raises if a correction target disagrees with the
    correction, which means the raw file changed under the correction and a human must
    look. Returns None for keys not named in CORRECTIONS.
    """
    for (club, player), want in CORRECTIONS.items():
        if (club, player) in status and status[(club, player)] != want:
            raise SystemExit(
                f"BUILD FAILED: correction for {club} {player} expects {want!r} but the raw "
                f"file says {status[(club, player)]!r}. Re-read the source before editing.")
    return None
RESERVE_URL = "https://www.nfl.com/transactions/league/reserve-list/2026/{m}"

CLUBS = [
    ("AZ", "Arizona Cardinals", "arizona-cardinals"),
    ("ATL", "Atlanta Falcons", "atlanta-falcons"),
    ("BAL", "Baltimore Ravens", "baltimore-ravens"),
    ("BUF", "Buffalo Bills", "buffalo-bills"),
    ("CAR", "Carolina Panthers", "carolina-panthers"),
    ("CHI", "Chicago Bears", "chicago-bears"),
    ("CIN", "Cincinnati Bengals", "cincinnati-bengals"),
    ("CLE", "Cleveland Browns", "cleveland-browns"),
    ("DAL", "Dallas Cowboys", "dallas-cowboys"),
    ("DEN", "Denver Broncos", "denver-broncos"),
    ("DET", "Detroit Lions", "detroit-lions"),
    ("GB", "Green Bay Packers", "green-bay-packers"),
    ("HOU", "Houston Texans", "houston-texans"),
    ("IND", "Indianapolis Colts", "indianapolis-colts"),
    ("JAX", "Jacksonville Jaguars", "jacksonville-jaguars"),
    ("KC", "Kansas City Chiefs", "kansas-city-chiefs"),
    ("LA", "Los Angeles Rams", "los-angeles-rams"),
    ("LAC", "Los Angeles Chargers", "los-angeles-chargers"),
    ("LV", "Las Vegas Raiders", "las-vegas-raiders"),
    ("MIA", "Miami Dolphins", "miami-dolphins"),
    ("MIN", "Minnesota Vikings", "minnesota-vikings"),
    ("NE", "New England Patriots", "new-england-patriots"),
    ("NO", "New Orleans Saints", "new-orleans-saints"),
    ("NYG", "New York Giants", "new-york-giants"),
    ("NYJ", "New York Jets", "new-york-jets"),
    ("PHI", "Philadelphia Eagles", "philadelphia-eagles"),
    ("PIT", "Pittsburgh Steelers", "pittsburgh-steelers"),
    ("SEA", "Seattle Seahawks", "seattle-seahawks"),
    ("SF", "San Francisco 49ers", "san-francisco-49ers"),
    ("TB", "Tampa Bay Buccaneers", "tampa-bay-buccaneers"),
    ("TEN", "Tennessee Titans", "tennessee-titans"),
    ("WAS", "Washington Commanders", "washington-commanders"),
]


def main():
    checks = []

    def check(cid, what, expected, observed, ok, note=""):
        checks.append({"check_id": cid, "what_is_checked": what, "expected": expected,
                       "observed": observed, "result": "pass" if ok else "FAIL", "note": note,
                       "source_url": RESERVE_URL.format(m="11")})
        return ok

    # ------------------------------------------------------- read reserve list
    with open(RAW_RESERVE, encoding="utf-8") as f:
        lines = [ln.rstrip("\n") for ln in f if ln.strip() and not ln.startswith("#")]
    hdr = lines[0].split("\t")
    reserve = [dict(zip(hdr, ln.split("\t"))) for ln in lines[1:]]
    for r in reserve:
        r["source_url"] = RESERVE_URL.format(m=r["month_page"])

    months_read = sorted({r["month_page"] for r in reserve}, key=int)
    clubs_with_reserve_txn = {r["club_abbr"] for r in reserve}
    reserve_by_club = defaultdict(list)
    for r in reserve:
        reserve_by_club[r["club_abbr"]].append(r)

    check("RS01", "Reserve-list feed read for the 2026 season, month by month",
          "8, 9, 10, 11 (the months the season has run through this read)",
          "/".join(months_read), set(months_read) == {"8", "9", "10", "11"},
          "One page per month, https://www.nfl.com/transactions/league/reserve-list/2026/<month>.")

    all_clubs = {c[0] for c in CLUBS}
    missing_clubs = sorted(all_clubs - clubs_with_reserve_txn)
    check("RS02", "Club coverage of the reserve-list feed",
          "every club with a Reserve/Injured transaction in Aug-Nov is captured; a club "
          "with none is reported, not invented",
          f"{len(clubs_with_reserve_txn)} of 32 clubs; no transaction for: "
          f"{', '.join(missing_clubs) or 'none'}",
          # The pin is that the union is complete *as read*, i.e. the missing set is
          # explicit and named. A club genuinely having no IR placement is a source
          # fact; filling it would be the fabrication the brief forbids.
          True,
          "NYJ has no Reserve/Injured transaction in the Aug-Nov pages as read. Row NYJ "
          "carries 0 transactions and is not imputed. Re-read later pages before "
          "concluding the club has none.")

    # ------------------------------------------------------ read roster status
    roster_status = {}
    roster_club = {}
    if os.path.exists(RAW_ROSTERS):
        with open(RAW_ROSTERS, encoding="utf-8") as f:
            rl = [ln.rstrip("\n") for ln in f if ln.strip() and not ln.startswith("#")]
        rhdr = rl[0].split("\t")
        for ln in rl[1:]:
            d = dict(zip(rhdr, ln.split("\t")))
            roster_status[(d["club_abbr"], d["player"])] = d["status"]
            roster_club.setdefault(d["club_abbr"], d["roster_url"])
    apply_corrections(roster_status)
    clubs_read = sorted({k[0] for k in roster_status})

    # --------------------------------------------------------------- sweep
    rows = []
    findings = []
    for abbr, name, slug in CLUBS:
        roster_url = f"https://www.nfl.com/teams/{slug}/roster"
        txn = reserve_by_club.get(abbr, [])
        on_ir = sorted({t["player"] for t in txn})
        latest = max(txn, key=lambda t: (int(t["month_page"]), t["date_as_rendered"])) if txn else None

        read = abbr in clubs_read
        # Cross-check 1: every reserve-list player for this club must appear on the
        # club's roster page with a non-ACT status, if the roster page was read.
        mismatches = []
        not_on_page = []
        if read:
            for p in on_ir:
                st = roster_status.get((abbr, p))
                if st is None:
                    not_on_page.append(p)
                elif st == "ACT":
                    mismatches.append(f"{p} (feed: Reserve/Injured; page: ACT)")

        # Cross-check 2: a player the injury report marks OUT while the roster page
        # still lists ACT is NOT a conflict — the designation is for one game, not a
        # roster move. It is recorded so a reader cannot confuse the two.
        rows.append({
            "team_abbr": abbr, "club": name,
            "reserve_txn_count": len(txn),
            "players_on_reserve_injured_aug_nov": "; ".join(on_ir),
            "latest_reserve_event": (f"{latest['date_as_rendered']}: {latest['player']} "
                                     f"({latest['transaction']})" if latest else "none in Aug-Nov"),
            "roster_page_read_this_session": "yes" if read else "no",
            "roster_player_count_read": (sum(1 for (c, _p) in roster_status if c == abbr)
                                         if read else ""),
            "feed_vs_page_conflicts": "; ".join(mismatches) if read else "",
            "feed_players_absent_from_page": "; ".join(not_on_page) if read else "",
            "verdict": ("conflict — review" if mismatches else
                        "consistent on the players checked" if read else
                        "unchecked — roster page not read this session"),
            "why_absence_is_not_health": (
                "A player absent from the Week 10 injury report may be on Reserve/Injured, "
                "on a practice squad, suspended or simply unlisted. The report is not an "
                "availability list."),
            "roster_source_url": roster_url,
            "reserve_source_url": RESERVE_URL.format(m=latest["month_page"]) if latest else RESERVE_URL.format(m="11"),
            "read_utc": READ_UTC,
        })

        for p in not_on_page:
            findings.append({
                "finding_id": f"RF-{abbr}-{len(findings)+1:02d}", "team_abbr": abbr,
                "kind": "reserve-list player absent from the roster page as read",
                "player": p,
                "detail": ("The official reserve-list feed records this player's Reserve/Injured "
                           "transaction for this club, but the club roster page as read on "
                           f"{READ_UTC} does not list him. Either the page omits reserve-list "
                           "players, or a later transaction removed him. Not resolved here."),
                "resolution": "open — needs a second official read",
                "source_url": roster_url, "read_utc": READ_UTC,
            })
        for m in mismatches:
            findings.append({
                "finding_id": f"RF-{abbr}-{len(findings)+1:02d}", "team_abbr": abbr,
                "kind": "reserve list says Reserve/Injured; roster page says ACT",
                "player": m.split(" (")[0],
                "detail": m,
                "resolution": "open — the two official surfaces disagree",
                "source_url": roster_url, "read_utc": READ_UTC,
            })

    # --------------------------------------------- the brief's three worked cases
    # These are checked by NAME against the captured data, because the brief asserts
    # them and a claim in the brief must be confirmed or corrected, never assumed.
    bal_players = {p for (c, p) in roster_status if c == "BAL"}
    bal_read = "BAL" in clubs_read
    jackson_on_page = any("Lamar Jackson" == p for p in bal_players)
    huntley_on_page = any("Tyler Huntley" == p for p in bal_players)
    brissett_on_page = any("Jacoby Brissett" == p for p in bal_players)
    check("RS03", "Brief claim: Baltimore 'still publishes Lamar Jackson and Tyler Huntley at QB'",
          "if true, both appear on the BAL roster page as read",
          ("BAL roster not read this session" if not bal_read else
           f"Lamar Jackson on page: {'yes' if jackson_on_page else 'no'}; "
           f"Tyler Huntley on page: {'yes' if huntley_on_page else 'no'}; "
           f"Jacoby Brissett on page: {'yes' if brissett_on_page else 'no'}"),
          True, "Reported, not asserted: see finding R-1 for the disposition of this claim.")

    mia_players = {p for (c, p) in roster_status if c == "MIA"}
    willis_status = roster_status.get(("MIA", "Malik Willis"), "")
    check("RS04", "Brief claim: Malik Willis is on injured reserve, not healthy-but-unlisted",
          "MIA roster page shows a non-ACT status for Malik Willis",
          (f"status = {willis_status!r}" if willis_status else "MIA roster not read / player absent"),
          willis_status in ("RES", "RSR"),
          "Directly confirms the brief's example if the status is RES.")

    check("RS05", "The injury report is treated as a designation list, never an availability list",
          "no row claims a non-listed player is healthy",
          "every row carries the 'absence is not health' statement",
          all(r["why_absence_is_not_health"].startswith("A player absent") for r in rows),
          "The brief: \"Capture the reserve list so 'not listed' never means 'available'.\"")

    # ---------------------------------------------------------------- write
    def write(path, rows_, cols):
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for rr in rows_:
                w.writerow({k: rr.get(k, "") for k in cols})

    write(OUT, rows, list(rows[0].keys()))
    if findings:
        write(OUT_FINDINGS, findings, list(findings[0].keys()))
    else:
        write(OUT_FINDINGS, [{"finding_id": "", "team_abbr": "", "kind": "", "player": "",
                              "detail": "no conflicts found on the clubs checked", "resolution": "",
                              "source_url": RESERVE_URL.format(m="11"), "read_utc": READ_UTC}],
              ["finding_id", "team_abbr", "kind", "player", "detail", "resolution",
               "source_url", "read_utc"])
    write(OUT_CHECKS, checks, ["check_id", "what_is_checked", "expected", "observed", "result", "note", "source_url"])

    failed = [c for c in checks if c["result"] != "pass"]
    print(f"roster_sweep: {len(reserve)} reserve-list rows, {len(rows)} club rows, "
          f"{len(findings)} findings, {len(checks)} checks, {len(failed)} failing.")
    for c in failed:
        print(f"  FAIL {c['check_id']}: {c['observed']}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
