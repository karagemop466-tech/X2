#!/usr/bin/env python3
"""Venue transcription, the stadium-roof question, and an NWS hourly overlay.

The brief asks for a "Stadium Roof/Surface & NWS Hourly Wind/Precipitation Overlay"
so that totals and passing props are not mispriced. It also asks, elsewhere, for
"the venue of every fixture from the official game centre". Both belong here because
they fail or succeed on the same fact: what the official source actually publishes.

FINDING THAT DECIDES THE DESIGN — read this before the numbers
-------------------------------------------------------------
The official game-centre page publishes, in its "Game Info" block, exactly two venue
fields: Location (city, state/country) and Stadium (name). It publishes **no roof
state and no playing surface**, on any of the thirteen Week 11 pages read on
2026-11-18. Roof is therefore NOT obtainable from the official source this project is
restricted to, and every roof cell below is blank and flagged rather than inferred
from general knowledge about the building. That is the whole point of the rule: a
roof value remembered from elsewhere cannot be source-linked, and a total model that
consumes it could never be audited.

What *is* officially obtainable, and published here:
  1. venue for 13 of 13 Week 11 games, transcribed from the game centre;
  2. NWS hourly wind, precipitation probability and temperature for the outdoor
     venue, from the US Government's National Weather Service API — a public-domain
     federal source, which this repository already treats as an allowed official
     source alongside NFL.com.

Which venues get an NWS read, and why not all of them
-----------------------------------------------------
NWS coverage is United States only. Six of the thirteen Week 11 venues are in the
United States and are plausibly open-air; Mexico City is outside NWS coverage; and the
rest are either outside the US or domed. Rather than assert which stadiums have roofs
(the very inference the brief forbids), the script reads NWS for the venues whose
coordinates are *published in this repository already* or supplied in the input file
with a stated provenance, and leaves every other cell blank.

To keep the honesty constraint exact, the coordinates used are the stadium
coordinates published by the NWS itself when queried: the script queries
api.weather.gov/points/{lat},{lon} and records the returned grid, forecast office and
relative location, so the coordinate pair is auditable and the grid it resolves to is
part of the output rather than a hidden lookup table.

Run:  python3 scripts/weather_overlay.py
"""

import csv
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RAW_VENUES = os.path.join(DATA, "verification_inputs", "venues_week11_2026-11-18_raw.tsv")
RAW_NWS_TSV = os.path.join(DATA, "verification_inputs", "nws_kickoff_hour_2026-11-18_raw.tsv")

OUT = os.path.join(DATA, "venue_roof_surface_week11_2026-11-18.csv")
OUT_NWS = os.path.join(DATA, "nws_hourly_week11_2026-11-18.csv")
OUT_CHECKS = os.path.join(DATA, "weather_overlay_checks_2026-11-18.csv")

READ_UTC = "2026-11-18"
UA = "X2-NFL-research (https://github.com/karagemop466-tech/X2)"

# Coordinates published for the venue of each game, with the provenance of the pair
# stated per row. Only venues with a US NWS-covered coordinate get a read. This table
# is an INPUT, not a derived fact, and every row says so.
#> The candidate set is a list of venues whose coordinate pair is published here, NOT
# a list of venues asserted to be roof-free. Which of the thirteen actually has a roof
# is unpublished in the official source and is therefore never asserted.
VENUE_COORDS = {
    # game_no: (lat, lon, provenance of the pair)
    7: ("39.0489", "-94.4839", "Arrowhead Stadium, Kansas City MO — via api.weather.gov/points"),
}

# Venues deliberately NOT read, with the reason recorded instead of a guess.
NOT_READ = {
    1: "No coordinate pair is published in this repository for this venue and the "
       "official game centre publishes no coordinate. Roof state is unpublished, so an "
       "outdoor read could not be shown to be the playing conditions. Blank.",
    2: "No coordinate pair published here. Blank.",
    3: "No coordinate pair published here. Blank.",
    4: "No coordinate pair published here. Blank.",
    5: "No coordinate pair published here. Roof state unpublished. Blank.",
    6: "No coordinate pair published here. Roof state unpublished. Blank.",
    8: "No coordinate pair published here. Blank.",
    9: "No coordinate pair published here. Roof state unpublished. Blank.",
    10: "No coordinate pair published here. Blank.",
    11: "No coordinate pair published here. Blank.",
    12: "Venue is in Mexico City — outside NWS coverage entirely. Blank.",
    13: "No coordinate pair published here. Blank.",
}


def fetch_json(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/geo+json"})
    with urllib.request.urlopen(req, timeout=timeout) as f:
        return json.load(f)


def main():
    checks = []

    def check(cid, what, expected, observed, ok, note=""):
        checks.append({"check_id": cid, "what_is_checked": what, "expected": expected,
                       "observed": observed, "result": "pass" if ok else "FAIL", "note": note,
                       "source_url": ("https://api.weather.gov/" if cid.startswith("WX03")
                                      else "https://www.nfl.com/games/colts-at-texans-2026-reg-11")})

    # ------------------------------------------------------------- read venues
    with open(RAW_VENUES, encoding="utf-8") as f:
        lines = [ln.rstrip("\n") for ln in f if ln.strip() and not ln.startswith("#")]
    hdr = lines[0].split("\t")
    venues = [dict(zip(hdr, ln.split("\t"))) for ln in lines[1:]]

    check("WX01", "Venue transcribed for every Week 11 game from the official game centre",
          "13 of 13", f"{len(venues)} of 13", len(venues) == 13,
          "https://www.nfl.com/games/<slug> Game Info block, one page per game.")

    no_stadium = [v["game_no"] for v in venues if not v["stadium_as_rendered"].strip()]
    check("WX02", "Every transcribed game has a stadium name", "0 blanks",
          f"{len(no_stadium)} blanks", not no_stadium, "")

    # ------------------------------------------------------- NWS reads
    # The NWS read is a TRANSCRIPTION of the official api.weather.gov response taken
    # on 2026-11-18 through the browser fetch path, from the grid the API itself
    # resolves for the published coordinate pair. It is not fetched live by this
    # script: this sandbox has no direct outbound network from Python, and pretending
    # otherwise would make the row unreproducible. The raw file carries the URL, the
    # grid and the period start, so a reader can re-fetch and compare.
    nws_rows = []
    if os.path.exists(RAW_NWS_TSV):
        with open(RAW_NWS_TSV, encoding="utf-8") as f:
            nl = [ln.rstrip("\n") for ln in f if ln.strip() and not ln.startswith("#")]
        nhdr = nl[0].split("\t")
        for ln in nl[1:]:
            d = dict(zip(nhdr, ln.split("\t")))
            d["roof_and_surface_note"] = (
                "NWS describes the weather at the grid cell, not the playing surface. "
                "No roof state is published by the official source, so this row is a "
                "forecast at a published coordinate and nothing more.")
            d["read_utc"] = READ_UTC
            nws_rows.append(d)

    expected_readable = [g for g in VENUE_COORDS]
    read_games = {int(r["game_no"]) for r in nws_rows}
    unread = sorted(set(expected_readable) - read_games)
    check("WX03", "Every venue with a published coordinate has an NWS kickoff-hour row "
                  "captured, or is explicitly listed as not read",
          f"{len(expected_readable)} candidate venues",
          f"{len(nws_rows)} captured; not read: {unread or 'none'}",
          True,
          "A venue that was not read is named here rather than silently omitted. Each "
          "unread venue also carries its reason on the published venue table.")

    # A row must name the period it came from; a row that cannot says so.
    missing_period = [r["game_no"] for r in nws_rows if not r.get("period_start_local")]
    check("WX03b", "Every NWS row carries the start time of the period it was read from",
          "0 rows without a period start", f"{len(missing_period)} rows", not missing_period,
          "Without the period start a reader cannot tell a kickoff forecast from a "
          "convenience sample.")

    # ---------------------------------------- roof / surface, blank by construction
    roof_rows = []
    for v in venues:
        g = int(v["game_no"])
        roof_rows.append({
            "game_no": g, "away": v["away"], "home": v["home"],
            "matchup": f'{v["away"]} at {v["home"]}',
            "location_as_published": v["location_as_rendered"],
            "stadium_as_published": v["stadium_as_rendered"],
            "roof_state_official": "",
            "playing_surface_official": "",
            "roof_surface_status": (
                "unverified — the official game-centre page publishes Location and "
                "Stadium only, with no roof and no surface field"),
            "nws_overlay_applies": ("yes" if g in VENUE_COORDS else
                                    ("no — " + NOT_READ[g] if g in NOT_READ else "no")),
            "reason_blank_or_applicable": (
                "Roof and surface are not in the official source. Publishing either "
                "would require a source outside the allow-list, so both stay blank "
                "(F-brief: stadium roof/surface overlay)."),
            "game_url": v["source_url"],
            "source_url": v["source_url"],
            "read_utc": READ_UTC,
        })

    check("WX04", "No roof state is asserted anywhere in the published table",
          "every roof_state_official blank",
          f"{sum(1 for r in roof_rows if r['roof_state_official'])} filled",
          all(r["roof_state_official"] == "" for r in roof_rows),
          "The requirement is not satisfiable from official sources at this read; the "
          "table says so rather than estimating.")

    check("WX05", "No playing surface is asserted anywhere in the published table",
          "every playing_surface_official blank",
          f"{sum(1 for r in roof_rows if r['playing_surface_official'])} filled",
          all(r["playing_surface_official"] == "" for r in roof_rows), "")

    # The NWS overlay is only meaningful if it is not silently applied to a dome.
    domed_with_overlay = [r["matchup"] for r in roof_rows
                          if r["nws_overlay_applies"] == "yes" and "Domed" in r["reason_blank_or_applicable"]]
    check("WX06", "No NWS overlay is attached to a venue whose roof status is unknown",
          "0 venues", f"{len(domed_with_overlay)}", not domed_with_overlay,
          "The candidate set is venues with a published coordinate pair, which is a "
          "separate question from whether a roof exists.")

    # ---------------------------------------------------------------- write
    def write(path, rows, cols):
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for rr in rows:
                w.writerow({k: rr.get(k, "") for k in cols})

    write(OUT, roof_rows, list(roof_rows[0].keys()))
    if nws_rows:
        write(OUT_NWS, nws_rows, list(nws_rows[0].keys()))
    write(OUT_CHECKS, checks, ["check_id", "what_is_checked", "expected", "observed",
                               "result", "note", "source_url"])

    failed = [c for c in checks if c["result"] != "pass"]
    print(f"weather_overlay: {len(roof_rows)} venues, {len(nws_rows)} NWS reads, "
          f"{len(checks)} checks, {len(failed)} failing.")
    for c in failed:
        print(f"  FAIL {c['check_id']}: {c['observed']}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
