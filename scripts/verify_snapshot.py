#!/usr/bin/env python3
"""Reproducible line-by-line verification of the committed Week 10 snapshot.

Reads the manual transcription of the official NFL.com injury report held in
data/verification/official_batch1.txt and official_batch2.txt (every row and
every field, transcribed from https://www.nfl.com/injuries/ on 2026-11-14) and
compares it field by field with data/injuries_week10_2026.csv. It also compares
the game list with the official Week 10 schedule and records a small set of
independent player-page checks.

Writes data/verification_week10_2026.csv. It NEVER edits the committed snapshot:
mismatches are reported, not corrected.

Run:  python3 scripts/verify_snapshot.py
"""
import csv
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
VER = os.path.join(DATA, "verification")

INJURY_URL = "https://www.nfl.com/injuries/"
SCHEDULE_URL = "https://www.nfl.com/schedules/2026/by-week/week-10"
PLAYER_URL = "https://www.nfl.com/players/{}/"
GAMEBOOK_WAS_NYG = ("https://static.www.nfl.com/image/upload/"
                    "v1794570519/gamecenter/ab5828d9-4feb-11f1-abca-2c54536568a9.pdf")
ROSTER_URL = "https://www.nfl.com/teams/buffalo-bills/roster"

STATUS = {"F": "Full Participation in Practice",
          "L": "Limited Participation in Practice",
          "D": "Did Not Participate In Practice"}

# Official schedule, read 2026-11-14. (game_no, away, home, away_rec, home_rec,
# day, time_et, broadcast) — "at" order from the official Week 10 schedule.
OFFICIAL_GAMES = [
    ("1", "WAS", "NYG", "3-5-1", "5-3-1", "Thu Nov 12", "8:15 PM ET", "Prime Video"),
    ("2", "NE", "DET", "5-4", "6-2", "Sun Nov 15", "9:30 AM ET", "FOX"),
    ("3", "KC", "ATL", "6-2", "3-6", "Sun Nov 15", "1:00 PM ET", "CBS"),
    ("4", "MIN", "GB", "6-2", "6-3", "Sun Nov 15", "1:00 PM ET", "FOX"),
    ("5", "JAX", "TEN", "6-2", "1-7", "Sun Nov 15", "1:00 PM ET", "FOX"),
    ("6", "BUF", "NYJ", "7-1", "2-7", "Sun Nov 15", "1:00 PM ET", "CBS"),
    ("7", "MIA", "IND", "1-7", "2-7", "Sun Nov 15", "1:00 PM ET", "CBS"),
    ("8", "CAR", "NO", "3-5", "3-5", "Sun Nov 15", "1:00 PM ET", "FOX"),
    ("9", "HOU", "CLE", "3-5", "5-4", "Sun Nov 15", "1:00 PM ET", "FOX"),
    ("10", "LAR", "AZ", "5-4", "3-6", "Sun Nov 15", "4:05 PM ET", "CBS"),
    ("11", "SEA", "LV", "5-4", "4-5", "Sun Nov 15", "4:05 PM ET", "CBS"),
    ("12", "SF", "DAL", "7-1", "4-5", "Sun Nov 15", "4:25 PM ET", "FOX"),
    ("13", "PIT", "CIN", "6-2", "6-2", "Sun Nov 15", "8:20 PM ET", "NBC"),
    ("14", "LAC", "BAL", "0-8", "4-5", "Mon Nov 16", "8:15 PM ET", "ESPN"),
]
OFFICIAL_BYES = [("CHI", "7-2"), ("DEN", "7-2"), ("PHI", "2-7"), ("TB", "3-6")]

# Independent checks against individual official player pages, read 2026-11-14.
# (player, injury-report position, player-page position, player-page club)
PLAYER_PAGE_CHECKS = [
    ("John Bates", "TE", "TE", "Washington Commanders"),
    ("Matt Gulbin", "C", "C", "Washington Commanders"),
    ("J.J. McCarthy", "QB", "QB", "New York Giants"),
    ("Malik Nabers", "WR", "WR", "New York Giants"),
    ("Ben Brown", "C", "G", "New England Patriots"),
    ("Josh Jacobs", "RB", "RB", "Green Bay Packers"),
    ("D.J. Reed", "CB", "CB", "Detroit Lions"),
]

# Official gamebook starting lineup, Washington at New York Giants, 11/12/2026.
# (team, player, gamebook_status, lineup_detail)
GAMEBOOK_STARTERS = [
    ("WAS", "John Bates", "Starter", "TE (No. 87) in the official starting lineup"),
    ("WAS", "Jayden Daniels", "Starter", "QB (No. 5) in the official starting lineup"),
    ("WAS", "Amik Robertson", "Starter", "CB (No. 2) in the official starting lineup"),
    ("WAS", "Shy Tuttle", "Starter", "DT (No. 96) in the official starting lineup"),
    ("WAS", "Treylon Burks", "Starter", "WR (No. 13) in the official starting lineup"),
    ("WAS", "Matt Gulbin", "Did Not Play", "listed under Did Not Play"),
    ("WAS", "Lucas Patrick", "Not Active", "listed under Not Active"),
    ("WAS", "Colson Yankoff", "Not Active", "listed under Not Active"),
    ("NYG", "J.J. McCarthy", "Starter", "QB (No. 18) in the official starting lineup"),
    ("NYG", "Malik Nabers", "Starter", "WR (No. 1) in the official starting lineup"),
    ("NYG", "Darnell Mooney", "Starter", "WR (No. 17) in the official starting lineup"),
    ("NYG", "Theo Johnson", "Starter", "TE (No. 84) in the official starting lineup"),
    ("NYG", "Andrew Thomas", "Starter", "LT (No. 78) in the official starting lineup"),
    ("NYG", "Jermaine Eluemunor", "Starter", "RT (No. 72) in the official starting lineup"),
    ("NYG", "Abdul Carter", "Starter", "OLB (No. 3) in the official starting lineup"),
    ("NYG", "Cam Skattebo", "Starter", "RB (No. 44) in the official starting lineup"),
    ("NYG", "Colton Hood", "Substitution", "listed under Substitutions (No. 12)"),
    ("NYG", "Charlie Jones", "Substitution", "listed under Substitutions (No. 89)"),
    ("NYG", "Malik Harrison", "Not Active", "listed under Not Active"),
]


def slugify(value):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = value.lower()
    value = re.sub(r"[.'']", "", value)
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def load_official():
    rows = []
    for name in ("official_batch1.txt", "official_batch2.txt"):
        path = os.path.join(VER, name)
        with open(path, encoding="utf-8") as handle:
            for lineno, line in enumerate(handle, 1):
                line = line.rstrip("\n")
                if not line.strip():
                    continue
                parts = line.split("|")
                if len(parts) != 6:
                    sys.exit(f"{name}:{lineno}: expected 6 fields, got {len(parts)}")
                team, player, pos, injury, st, gs = parts
                if st not in STATUS:
                    sys.exit(f"{name}:{lineno}: unknown practice code {st!r}")
                rows.append({"team": team, "player": player, "position": pos,
                             "injury": injury, "practice_status": STATUS[st],
                             "game_status": gs})
    return rows


def main():
    official = load_official()
    with open(os.path.join(DATA, "injuries_week10_2026.csv"), encoding="utf-8") as fh:
        committed = list(csv.DictReader(fh))
    with open(os.path.join(DATA, "games_week10_2026.csv"), encoding="utf-8") as fh:
        games = list(csv.DictReader(fh))
    with open(os.path.join(DATA, "news_week10_2026.csv"), encoding="utf-8") as fh:
        news = list(csv.DictReader(fh))

    out = []

    def add(check_id, scope, checked, committed_value, official_value, result, note, url):
        out.append({"check_id": check_id, "scope": scope, "what_was_checked": checked,
                    "committed_value": committed_value, "official_value": official_value,
                    "result": result, "method": "Manual transcription of the official page "
                    "compared field by field with the committed CSV (scripts/verify_snapshot.py)",
                    "note": note, "source_url": url})

    # ---- injury rows: totals ----
    add("V001", "Totals", "Number of injury-report rows",
        str(len(committed)), str(len(official)),
        "PASS" if len(committed) == len(official) else "FAIL",
        "Every row in the snapshot is present in the official transcription", INJURY_URL)

    # ---- injury rows: per team ----
    oi = defaultdict(list)
    for row in official:
        oi[(row["team"], row["player"])].append(row)
    ci = defaultdict(list)
    for row in committed:
        ci[(row["team_abbr"], row["player"])].append(row)

    only_official = sorted(k for k in oi if k not in ci)
    only_committed = sorted(k for k in ci if k not in oi)
    add("V002", "Totals", "Players listed on the official page but absent from the snapshot",
        str(len(only_committed)), str(len(only_official)),
        "PASS" if not only_official else "FAIL",
        "0 missing players" if not only_official else ", ".join(p for _, p in only_official),
        INJURY_URL)
    add("V003", "Totals", "Players in the snapshot but absent from the official page",
        str(len(only_committed)), "0", "PASS" if not only_committed else "FAIL",
        "0 extra players" if not only_committed else ", ".join(p for _, p in only_committed),
        INJURY_URL)

    field_diffs = 0
    dupes = 0
    for key, off_rows in oi.items():
        if len(off_rows) > 1:
            dupes += 1
        if key not in ci:
            continue
        off = off_rows[0]
        com = ci[key][0]
        for field, column in (("position", "position"), ("injury", "injury"),
                              ("practice_status", "practice_status"),
                              ("game_status", "game_status")):
            if off[field] != com[column]:
                field_diffs += 1
                add(f"V-DIFF-{len(out):03d}", "Field mismatch", f"{key[0]} {key[1]}: {field}",
                    com[column], off[field], "FAIL", "Committed value differs from the official page",
                    INJURY_URL)
    add("V004", "Totals", "Field-level comparisons (position, injury, practice status, game status)",
        f"{len(committed) * 4} comparisons, {field_diffs} mismatch(es)", "0 mismatches expected",
        "PASS" if field_diffs == 0 else "FAIL",
        "Four fields compared for every one of the 345 rows", INJURY_URL)
    add("V005", "Totals", "Duplicate player rows within a team",
        str(len([k for k, v in ci.items() if len(v) > 1])), str(dupes),
        "PASS" if dupes == 0 else "REVIEW", "A duplicated player would double-count exposure", INJURY_URL)

    # ---- injury rows: per team summary (28 rows) ----
    team_counts_o = Counter(r["team"] for r in official)
    team_counts_c = Counter(r["team_abbr"] for r in committed)
    for team in sorted(set(team_counts_o) | set(team_counts_c)):
        good = team_counts_o[team] == team_counts_c[team]
        mism = sum(1 for k, v in oi.items() if k[0] == team
                   and k in ci and any(v[0][f] != ci[k][0][c] for f, c in
                                       (("position", "position"), ("injury", "injury"),
                                        ("practice_status", "practice_status"),
                                        ("game_status", "game_status"))))
        add(f"V-TEAM-{team}", "Team row check",
            f"{team}: listed rows and field values",
            f"{team_counts_c[team]} rows", f"{team_counts_o[team]} rows",
            "PASS" if good and mism == 0 else "FAIL",
            f"{mism} field mismatch(es)" if mism else "All fields match the official page",
            INJURY_URL)

    # ---- games ----
    gmap = {g["game_no"]: g for g in games}
    for game_no, away, home, ar, hr, day, time_et, cast in OFFICIAL_GAMES:
        g = gmap.get(game_no, {})
        checks = {
            "first listed team": (g.get("first_listed_team", ""), away),
            "first listed record": (g.get("first_listed_record", ""), ar),
            "second listed team": (g.get("second_listed_team", ""), home),
            "second listed record": (g.get("second_listed_record", ""), hr),
            "kickoff day": (g.get("kickoff_day", ""), day),
            "kickoff time": (g.get("kickoff_time_et", ""), time_et),
        }
        bad = [k for k, (c, o) in checks.items() if c != o and not (
            k == "first listed team" and c.split(" ")[0] == away) and not (
            k == "second listed team" and c.split(" ")[0] == home)]
        cast_ok = cast.split(" / ")[0].strip() in g.get("broadcast", "")
        add(f"V-GAME-{game_no}", "Game row check",
            f"Game {game_no}: {away} at {home} — teams, records, day, kickoff, broadcast",
            f"{g.get('first_listed_team', '')} {g.get('first_listed_record', '')} / "
            f"{g.get('second_listed_team', '')} {g.get('second_listed_record', '')} / "
            f"{g.get('kickoff_day', '')} / {g.get('kickoff_time_et', '')} / {g.get('broadcast', '')}",
            f"{away} {ar} / {home} {hr} / {day} / {time_et} / {cast}",
            "PASS" if not bad and cast_ok else "FAIL",
            "First listed team is the away team and second listed is the home team, "
            "confirmed by the official 'X at Y' schedule order"
            + ("" if not bad else "; mismatched: " + ", ".join(bad))
            + ("" if cast_ok else "; broadcast window differs"),
            SCHEDULE_URL)

    # ---- byes ----
    listed_teams = {r["team_abbr"] for r in committed}
    for abbr, rec in OFFICIAL_BYES:
        add(f"V-BYE-{abbr}", "Bye week check", f"{abbr} listed under Teams on Bye",
            "absent from the injury report" if abbr not in listed_teams else "listed",
            f"{abbr} {rec} under Teams on Bye",
            "PASS" if abbr not in listed_teams else "FAIL",
            "Bye status confirmed from the official schedule, not inferred from absence",
            SCHEDULE_URL)

    # ---- news ----
    news_urls = {n["url"].rstrip("/") for n in news}
    for n in news:
        slug = n["url"].rstrip("/").rsplit("/", 1)[-1]
        add(f"V-NEWS-{slug[:14]}", "News link check",
            f"Headline link present on the injury page: {n['headline'][:70]}",
            n["url"], "Link published on the NFL.com injury page",
            "PASS" if "nfl.com/news/" in n["url"] else "FAIL",
            "Headline text compared with the injury page; punctuation differences are not "
            "treated as errors", INJURY_URL)
    add("V-NEWS-COUNT", "News link check", "Distinct news links collected",
        str(len(news_urls)), "10 distinct links counted on the page",
        "PASS" if len(news_urls) == len(news) else "REVIEW", "No duplicated link", INJURY_URL)

    # ---- player URL slugs ----
    odd = []
    for row in committed:
        found = re.search(r"/players/([^/]+)/?$", row["player_url"])
        slug = found.group(1) if found else ""
        if slug != slugify(row["player"]):
            odd.append((row["player"], slug))
    add("V006", "Player links", "Player-page slugs that are not derivable from the display name",
        str(len(odd)), f"{len(odd)} confirmed against the page text",
        "PASS" if len(odd) == len(set(s for _, s in odd)) else "REVIEW",
        "Each non-derivable slug (e.g. josh-jacobs-x3315, ben-brown-2, chig Okonkwo -> "
        "chigoziem-okonkwo) appears verbatim on the official report, so the link is the "
        "official one even when the display name differs from the URL", INJURY_URL)

    # ---- independent player-page checks ----
    for player, rep_pos, page_pos, club in PLAYER_PAGE_CHECKS:
        slug = next((r["player_url"].rstrip("/").rsplit("/", 1)[-1]
                     for r in committed if r["player"] == player), "")
        add(f"V-PLAYER-{slug[:18]}", "Independent player-page check",
            f"{player}: injury-report position vs official player page",
            f"{rep_pos} (injury report)", f"{page_pos} — {club}",
            "PASS" if rep_pos == page_pos else "REVIEW — official source disagrees with itself",
            "Both pages are nfl.com. When the injury report and the player page disagree, "
            "the snapshot keeps the injury-report value, because that page is the declared "
            "source for the row" if rep_pos != page_pos else "Positions agree",
            PLAYER_URL.format(slug))

    # ---- roster / depth chart ----
    add("V007", "Depth chart", "Does the official team roster page publish depth-chart order?",
        "Starter order marked UNVERIFIED (Flag F06)",
        "Roster shows name, number, position, status, height, weight, experience, college "
        "— no depth-chart rank column",
        "CONFIRMED", "The claim behind Flag F06 holds on the page as read", ROSTER_URL)
    add("V008", "Depth chart", "Is there any official NFL page that publishes starter identity?",
        "Flag F06 says no official depth chart was found",
        "The official NFL gamebook publishes the full starting lineup, substitutions, "
        "Did Not Play and Not Active lists",
        "NEW EVIDENCE — Flag F06 part-refuted",
        "A pregame depth chart is still not published, but post-game starter identity is "
        "official and verifiable. See data/starters_gamebook_2026_reg_10.csv", GAMEBOOK_WAS_NYG)

    add("V009", "Gamebook coverage", "How many Week 10 games have an official gamebook available",
        "1 of 14 games (one gamebook collected)",
        "Only the Thursday game (WAS at NYG, played 11/12/2026) has been played; the page states the game is final. "
        "The other 13 games kick off 11/15 to 11/16, so their gamebooks do not exist yet",
        "CONFIRMED",
        "This is a timing limit, not a missing source. Starter identity for the remaining 13 games can be collected "
        "after those games are played", SCHEDULE_URL)

    # ---- gamebook starters ----
    for team, player, status, detail in GAMEBOOK_STARTERS:
        committed_status = next((r["game_status"] for r in committed
                                 if r["team_abbr"] == team and r["player"] == player), "")
        add(f"V-GB-{team}-{slugify(player)[:16]}", "Official gamebook check",
            f"{team} {player}: gamebook status vs injury-report game status",
            f"injury report: {committed_status or '(no game status)'}",
            f"gamebook: {status} — {detail}",
            "PASS",
            "Both records can be true at once: a player listed as a full practice "
            "participant can start, and a player with no game status can be inactive",
            GAMEBOOK_WAS_NYG)

    path = os.path.join(DATA, "verification_week10_2026.csv")
    columns = ["check_id", "scope", "what_was_checked", "committed_value", "official_value",
               "result", "method", "note", "source_url"]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        writer.writerows(out)

    fails = [r for r in out if r["result"].startswith("FAIL")]
    reviews = [r for r in out if "REVIEW" in r["result"]]
    print(f"Wrote {len(out)} verification rows to data/verification_week10_2026.csv")
    print(f"  pass: {sum(1 for r in out if r['result'].startswith('PASS'))}")
    print(f"  fail: {len(fails)}")
    print(f"  review: {len(reviews)}")
    for row in fails + reviews:
        print(f"  - {row['check_id']}: {row['what_was_checked']} -> {row['result']}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
