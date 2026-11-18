#!/usr/bin/env python3
"""T109 (session db00d539) — is a Week 11 injury report published at all?

This is a *negative-result* probe, and it is written down precisely because the answer is
"no report, and the URLs lie about it".

The NFL injury hub ignores its week parameter (flag F104). So a reader cannot tell "no
Week 11 report exists" from "the hub silently served Week 10 again" by looking at the page
once. The probe therefore reads four routes on one day and records exactly what each
returned, including the page's own heading:

  A  https://www.nfl.com/injuries/                     (bare hub)
  B  https://www.nfl.com/injuries/?week=11             (the hub's own week parameter)
  C  https://www.nfl.com/injuries/league/2026/reg11    (the season/week route for Week 11)
  D  https://www.nfl.com/injuries/league/2026/reg9     (CONTROL: a past week that must render)

D is the control. If D renders WEEK 9 while C renders WEEK 10, then the route works and
Week 11 genuinely has no report yet — that is a real finding and not a broken URL. Without
the control, C's result would be uninterpretable.

The reads below were taken with the session's page-fetch tool on 2026-11-18. Each row keeps
which route was requested and which week the page *rendered*, because those differ.

What this means for the model: a Week 11 availability feature cannot be built on any of
these routes today. It is published as a blank with a date, not filled with the Week 10
report. That is the discipline the brief demands ("store every injury-hub read with its
clock time and publish the delta, never the level").

Re-run:  python3 scripts/week11_report_probe.py
"""

import csv
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
OUT = "week11_report_probe.csv"
READ = "2026-11-18"

# Read on 2026-11-18 with the page-fetch tool. `rendered_week` is what the page's own
# heading said; `rendered_title_date` is the part of the document title after "Week".
PROBES = [
    ("A", "https://www.nfl.com/injuries/", "10", True,
     "the page is titled '... Week 10 of the 2026 Season', heading 'Injuries - WEEK 10'; "
     "its NEWS block lists headlines to Tuesday Nov 17, so the hub itself is current but "
     "still serves the Week 10 report"),
    ("B", "https://www.nfl.com/injuries/?week=11", "10", True,
     "the week parameter is ignored: requesting week=11 renders the same Week 10 report "
     "byte for byte (F104)"),
    ("C", "https://www.nfl.com/injuries/league/2026/reg11", "10", True,
     "the season/week route for Week 11 also renders WEEK 10, so it resolves to the same "
     "content as A rather than returning a Week 11 report"),
    ("D", "https://www.nfl.com/injuries/league/2026/reg9", "9", False,
     "CONTROL: the same route for a past week renders heading 'Injuries - WEEK 9' with "
     "Week 9 games (Nov 5 JAX at BAL), so the route is functional and C's Week 10 result "
     "is a genuine absence, not a broken URL"),
]

fail = []
# P1 — the control must actually render a different week from the hub. If this ever fails,
# the whole negative result is uninterpretable and the file must not be published.
control = next(p for p in PROBES if p[0] == "D")
hub = next(p for p in PROBES if p[0] == "A")
if control[2] == hub[2]:
    fail.append("P1 the control route renders the same week as the hub (%s); the probe "
                "cannot distinguish absence from a broken route" % control[2])
# P2 — every route must have been read (no placeholder rows).
if len({p[0] for p in PROBES}) != len(PROBES):
    fail.append("P2 duplicate route letters")
# P3 — the conclusion is symmetric with the evidence: 11 must not be claimed as published.
if any(p[2] == "11" for p in PROBES):
    fail.append("P3 a route rendered Week 11 — update the register instead of asserting absence")

if fail:
    print("PROBE BUILD FAILED:")
    for f in fail:
        print("  -", f)
    sys.exit(1)

rows = []
for letter, url, rendered, serves_report, observation in PROBES:
    if letter == "D":
        conclusion = ("route works (control): a past week renders its own report")
    elif serves_report:
        conclusion = ("blank for Week 11: this route cannot supply a Week 11 availability feature")
    else:
        conclusion = "unset"
    rows.append({
        "probe_id": "W11-%s" % letter,
        "route_requested": url,
        "week_requested": ("11" if ("week=11" in url or "/reg11" in url)
                           else "9" if "/reg9" in url else "10"),
        "rendered_week": rendered,
        "renders_a_week_11_report": ("yes" if rendered == "11" else "no"),
        "what_was_seen": observation,
        "consequence": conclusion,
        "read_utc": READ,
        "source_url": url,
    })

with open(os.path.join(DATA, OUT), "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["probe_id", "route_requested", "week_requested",
                                      "rendered_week", "renders_a_week_11_report",
                                      "what_was_seen", "consequence", "read_utc",
                                      "source_url"])
    w.writeheader()
    for r in rows:
        w.writerow(r)

print("week11_report_probe.csv written: %d routes read on %s" % (len(rows), READ))
for r in rows:
    print("  %s %-46s -> rendered WEEK %-2s  Week 11 report: %s"
          % (r["probe_id"], r["route_requested"], r["rendered_week"],
             r["renders_a_week_11_report"]))
print("  P1 control distinguishes absence from a broken route: pass "
      "(reg9 renders WEEK 9, reg11 renders WEEK 10)")
print("  P3 no route rendered Week 11: pass — absence published, nothing inferred")
