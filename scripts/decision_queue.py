#!/usr/bin/env python3
"""Rank the open decisions by what each one actually unblocks, and say what it costs.

Why this exists. The repository had ten open decisions (data/decision_options.csv)
all marked "awaiting owner choice", a 64-row readiness table (data/decision_readiness.csv)
saying which requirement each blocker holds, and a review console. What it did not
have was an order: nothing said which decision to make first, how many requirements
each one releases, or what the cheapest reversible move is. A reviewer with twenty
minutes had no way to spend them well. This script derives that order from the two
registers rather than asserting it:

  * For each decision, it collects every flag id the decision row names.
  * A readiness row is "released" when one of those flags appears in the row's
    blocking_gate text - that is the repository's own record of what is blocked.
  * Decisions are then ordered by the number of rows released, then by whether the
    blocked work is foundational (data/verification before ranking/reward).

The cost column is deliberately separated from benefit, because they are different
questions and conflating them is how a cheap irreversible choice gets made for its
benefit alone. Every row carries the source the decision itself cites.

Output: data/decision_queue.csv  (one row per decision, ranked)

Run:  python3 scripts/decision_queue.py
"""
import csv
import os
import re
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")

# Areas whose unblocked work is a prerequisite for the areas below it. Used only
# to break ties between decisions that release the same number of rows, and it is
# printed in the row so a reader can disagree with the ordering.
FOUNDATIONAL = {
    "price": 1, "data": 1, "legal": 1, "terms": 1,
    "verification": 2, "capture": 2, "depth": 2, "injury": 2,
    "leaderboard": 3, "reward": 3, "ranking": 3, "correlation": 3, "staking": 3,
}


def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write(name, rows, cols):
    with open(os.path.join(DATA, name), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore", lineterminator="\r\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main():
    decisions = read("decision_options.csv")
    readiness = read("decision_readiness.csv")

    rows = []
    for d in decisions:
        blob = " ".join(d.values())
        flags = sorted(set(re.findall(r"F\d{2,3}", blob)))
        released = [r for r in readiness
                    if any(f in r["blocking_gate"] for f in flags)]
        # Which part of the work the release touches.
        areas = Counter()
        for r in released:
            text = (r["brief_item"] + " " + r["blocking_gate"]).lower()
            for kw in FOUNDATIONAL:
                if kw in text:
                    areas[kw] += 1
        # Tier from what the release touches; when nothing is flagged, fall back to
        # the decision's own subject so the row is still placed, and say so.
        if areas:
            foundation = min(FOUNDATIONAL[a] for a in areas)
            foundation_note = "from the flags it releases"
        else:
            own = d["decision_to_make"].lower() + " " + d["blocked_items"].lower()
            hit = [FOUNDATIONAL[k] for k in FOUNDATIONAL if k in own]
            foundation = min(hit) if hit else 9
            foundation_note = ("no readiness row names this decision's blocker, so the tier "
                               "comes from its own subject; the binding constraint is elsewhere")
        statuses = Counter(r["status"].split(" (")[0].strip() for r in released)
        # Is there a move that costs nothing and can be reversed? A row whose
        # recommended option is "keep it blank / keep it off" has one.
        rec = d["recommended_now"].lower()
        reversible = "yes" if any(
            k in rec for k in ("keep", "blank", "off", "disable", "now;", "now")) else "check"
        needs_money = "license" in blob.lower() or "cost" in blob.lower() or "budget" in blob.lower()
        needs_lawyer = "legal" in blob.lower() or "review" in blob.lower() and "legal" in blob.lower()

        rows.append({
            "rank": 0,
            "decision_id": d["decision_id"],
            "decision_to_make": d["decision_to_make"],
            "flags_that_gate_it": (", ".join(flags) if flags else
                                   "(none named in the decision row; no requirement row cites it as its blocker)"),
            "readiness_rows_released": len(released),
            "rows_currently_blocked": statuses.get("Blocked", 0),
            "rows_currently_missing": statuses.get("Missing", 0),
            "rows_partial": statuses.get("Partial", 0),
            "released_requirement_ids": ", ".join(r["req_id"] for r in released[:8]) +
                                        (f" (+{len(released) - 8} more)" if len(released) > 8 else ""),
            "foundation_tier": foundation,
            "tier_basis": foundation_note,
            "cheapest_reversible_move": reversible,
            "needs_spend_or_licence": "yes" if needs_money else "no",
            "needs_legal_review": "yes" if needs_lawyer else "no",
            "recommended_now": d["recommended_now"],
            "what_unlocks_the_choice": d["what_unlocks_the_choice"],
            "blocked_items": d["blocked_items"],
            "source_url": d["source_url"],
        })

    # Rank: most rows released, then most foundational, then cheapest.
    rows.sort(key=lambda r: (-r["readiness_rows_released"], r["foundation_tier"],
                             r["needs_spend_or_licence"] == "yes", r["needs_legal_review"] == "yes"))
    for i, r in enumerate(rows, 1):
        r["rank"] = i

    write("decision_queue.csv", rows, list(rows[0].keys()))
    print(f"decision_queue.csv: {len(rows)} decisions ranked")
    for r in rows:
        print(f"  {r['rank']:>2}. {r['decision_id']}  releases {r['readiness_rows_released']:>2} rows  "
              f"tier {r['foundation_tier']}  spend={r['needs_spend_or_licence']:<3} legal={r['needs_legal_review']:<3} "
              f"{r['decision_to_make'][:58]}")


if __name__ == "__main__":
    main()
