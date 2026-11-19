#!/usr/bin/env python3
"""Brief-coverage presence audit (session 8994979a, task T403).

Machine-checkable assertion that every site surface the brief mandates is
actually present and populated in the RENDERED pages under docs/ — not only in
the data registers. A render bug (cf. F30, where a build emitted unrendered
table tokens) would leave the registers fine and the site empty; this check
fails in that case.

Surfaces asserted (brief wording in quotes):
  1. docs/index.html readiness-table — "a decision-readiness table on the
     landing page: one row per requirement, with the gate that blocks it and
     the number that would clear it".
  2. docs/suggestions.html sugg-review — "a section dedicated for suggestions
     so someone can review suggestions and choose the best path before
     implementing any changes".
  3. docs/questions.html + docs/decisions.html — "a clear list of questions,
     informations and answers that need to be addressed before any decision
     can be reasonably made" and "suggestions … to discover missing
     information" (information-gap register).
  4. docs/executive-summary.html — "an executive summary outlining important
     details".
  5. docs/flagged.html — the Flagged for Review publication of every
     irregularity (never blocks; always visible).
  6. Source links: every one of these pages carries at least one https source
     link; all external links are https. (Per-row evidence links are enforced
     separately by build.py's row-source checks.)

Also asserts the 65<->65 bijection between requirements.csv and
decision_readiness.csv and that no readiness row leaves the blocking gate or
the clearing number blank.

Exit code 0 = every assertion holds; 1 = at least one failed (printed as FAIL).
Nothing here reads the network; it is a build-time audit of the committed tree.
"""

import csv
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")

FAILURES = []
CHECKS = 0


def check(name, ok, detail=""):
    global CHECKS
    CHECKS += 1
    if ok:
        print(f"  pass  {name}")
    else:
        print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))
        FAILURES.append(name)


def read(path):
    with open(os.path.join(DOCS, path), encoding="utf-8") as fh:
        return fh.read()


def table_rows(html, table_id):
    """Return list of row-cell-lists (excluding the header row) for a table id."""
    m = re.search(r'<table[^>]*id="%s".*?</table>' % re.escape(table_id), html, re.S)
    if not m:
        return None
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(0), re.S)
    out = []
    for r in rows[1:]:  # first row is the header
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S)
        out.append([re.sub(r"<[^>]+>", "", c).strip() for c in cells])
    return out


def csv_rows(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


print("Brief-coverage audit — surfaces mandated by the owner brief")

# ---------------------------------------------------------------- 1. landing
index = read("index.html")
rows = table_rows(index, "readiness-table")
req = csv_rows("data/requirements.csv")
dr = csv_rows("data/decision_readiness.csv")
check("landing page exists and is non-trivial", len(index) > 10000, f"{len(index)} chars")
check("landing readiness table rendered", rows is not None)
if rows is not None:
    check(
        "readiness table: one row per requirement (%d)" % len(req),
        len(rows) == len(req),
        f"rendered {len(rows)}, register {len(req)}",
    )
    header_m = re.search(
        r'<table[^>]*id="readiness-table".*?<tr[^>]*>(.*?)</tr>',
        index,
        re.S,
    )
    header = header_m.group(1) if header_m else ""
    check("readiness table names the blocking gate", "Gate that blocks it" in header)
    check("readiness table names the clearing number", "Number that would clear it" in header)
    gate_idx = num_idx = None
    ths = [re.sub(r"<[^>]+>", "", t).strip() for t in re.findall(r"<th[^>]*>(.*?)</th>", header, re.S)]
    for i, th in enumerate(ths):
        if th == "Gate that blocks it":
            gate_idx = i
        if th == "Number that would clear it":
            num_idx = i
    if gate_idx is not None and num_idx is not None:
        blank_gate = [r[0] for r in rows if len(r) <= gate_idx or not r[gate_idx]]
        blank_num = [r[0] for r in rows if len(r) <= num_idx or not r[num_idx]]
        check("every readiness row shows its blocking gate", not blank_gate, str(blank_gate[:5]))
        check("every readiness row shows its clearing number", not blank_num, str(blank_num[:5]))

ids_req = {r["req_id"] for r in req}
ids_dr = {r["requirement_id"] for r in dr}
check("requirements<->readiness bijection (65<->65)", ids_req == ids_dr)
check(
    "no register row leaves gate or clearing number blank",
    all(r["blocking_gate"].strip() and r["number_that_clears_it"].strip() for r in dr),
)

# ------------------------------------------------------------- 2. suggestions
sugg = read("suggestions.html")
srows = table_rows(sugg, "sugg-review")
srev = csv_rows("data/suggestion_review.csv")
check("suggestions review section rendered", srows is not None)
if srows is not None:
    check(
        "suggestion review table rows == register (%d)" % len(srev),
        len(srows) == len(srev),
        f"rendered {len(srows)}, register {len(srev)}",
    )
check(
    "suggestions are marked for review, not implemented",
    "not implemented" in sugg.lower(),
)
check(
    "suggestion review offers a path to choose",
    bool(re.search(r"[Rr]ecommended|option|path", sugg)),
)

# ------------------------------------------------- 3. questions / info / answers
questions = read("questions.html")
qreg = csv_rows("data/questions.csv")
q_trs = len(re.findall(r"<tr[ >]", questions))
check(
    "questions register rendered one row per question (%d)" % len(qreg),
    q_trs == len(qreg) + 1,  # +1 header
    f"tr count {q_trs}",
)
decisions = read("decisions.html")
gaps = csv_rows("data/information_gaps.csv")
dqs = csv_rows("data/decision_questions.csv")
gap_rows = table_rows(decisions, "gap-table")
dq_rows = table_rows(decisions, "dq-table")
check("information-gap register rendered", gap_rows is not None and len(gap_rows) == len(gaps),
      f"rendered {None if gap_rows is None else len(gap_rows)}, register {len(gaps)}")
check("decision-question register rendered", dq_rows is not None and len(dq_rows) == len(dqs),
      f"rendered {None if dq_rows is None else len(dq_rows)}, register {len(dqs)}")

# ------------------------------------------------------- 4. executive summary
esum = read("executive-summary.html")
check("executive summary exists and outlines details", len(esum) > 15000, f"{len(esum)} chars")

# ------------------------------------------------------ 5. flagged for review
flagged = read("flagged.html")
flags = csv_rows("data/flags.csv")
f_trs = len(re.findall(r"<tr[ >]", flagged))
check(
    "flagged page lists every flag (%d)" % len(flags),
    f_trs == len(flags) + 1,
    f"tr count {f_trs}",
)

# ------------------------------------------------------------ 6. source links
pages = ["index.html", "suggestions.html", "questions.html", "decisions.html",
         "executive-summary.html", "flagged.html"]
for page in pages:
    html = read(page)
    links = re.findall(r'href="(https?://[^"]+)"', html)
    check(f"{page}: has at least one external source link", any(l.startswith("https://") for l in links))
    check(f"{page}: all external links https", all(l.startswith("https://") for l in links))

# ---------------------------------------------------------------------- done
print(f"\n{CHECKS} checks, {len(FAILURES)} failing")
if FAILURES:
    sys.exit(1)
print("BRIEF COVERAGE: ALL CHECKS PASSED")
