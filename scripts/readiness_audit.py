#!/usr/bin/env python3
"""Mechanics-only audit of the decision-readiness -> requirements mapping (T212).

THE PUBLISHED CONTRACT, QUOTED
------------------------------
The landing page says of the decision-readiness table:

    "One row per requirement in the requirements register (65 of 65)."

and prints, per row, an `R..` id from ``data/requirements.csv`` beside a
"Requirement (from the brief)" cell taken from ``data/decision_readiness.csv``.
``data/readiness_mapping.csv`` records how strongly each pair was judged to
correspond, using four labels whose meaning is stated in flag F103:

    exact       -- the two texts are the same brief item
    related     -- same domain, different item
    approximate -- the register has no dedicated row; the nearest domain row was used
    new         -- a readiness row authored here, for a register requirement that
                   had no readiness row (keeps the bijection complete)

WHAT THIS SCRIPT MEASURES
-------------------------
Three things, all falsifiable by reading two CSVs, none of which needs a network:

  1. DUPLICATE REQUIREMENT ROWS. If two rows of the requirements register are the
     same brief item written twice, then "65 of 65 requirements" over-counts: the
     denominator includes the same requirement more than once. The script groups
     near-identical requirement texts and reports the group sizes, and for each
     group it reports whether the two rows carry the SAME readiness answer or a
     DIVERGENT one -- because a divergent answer to one question is the concrete
     harm to a reader deciding what to do next.

  2. MISLABELLED PAIRS. A row labelled `exact` whose two texts are not the same
     item, and a row whose printed brief item is a better match to a requirement
     OTHER than the R-id beside it (a misroute). `new` is checked differently: it
     predicts the register DID hold a matching row, so a `new` row whose text
     matches nothing is the contradiction, not the reverse.

  3. DUPLICATE PUBLICATION. The same brief item printed on more than one readiness
     row, which the "one row per requirement" contract cannot support.

WHAT IT DOES NOT DO
-------------------
It does not decide which register is canonical, does not rewrite any mapping, and
does not touch any NFL datum. `www.nfl.com` is unreachable from this sandbox
(flag F130) and no official read is attempted or implied.

Similarity is a pointer, not a verdict: every emitted row carries both strings so
a human can overrule the threshold by eye.

Exit status is always 0. The build imports `audit()` and publishes the result.
"""
import csv
import difflib
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")

# Disclosure thresholds, named so the published table can state what it meant.
# These are not model parameters and nothing downstream depends on them.
DUP_THRESHOLD = 0.85     # two register rows describing one brief item
ABSENT_THRESHOLD = 0.60  # nothing in the register comes close

OUT_CSV = os.path.join(DATA, "readiness_mapping_audit.csv")
OUT_GROUPS = os.path.join(DATA, "requirements_duplicate_groups.csv")
OUT_LANES = os.path.join(DATA, "identifier_lane_collisions.csv")


def _norm(s):
    s = (s or "").lower()
    for a, b in (("\u2014", "-"), ("\u2013", "-"), ("\u2019", "'"), ("\u2018", "'"),
                 ("\u201c", '"'), ("\u201d", '"')):
        s = s.replace(a, b)
    return " ".join(s.split())


def _ratio(a, b):
    if _norm(a) == _norm(b):
        return 1.0
    return difflib.SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def _line_index(name, key_col):
    out = {}
    with open(os.path.join(DATA, name), encoding="utf-8-sig", newline="") as fh:
        for n, row in enumerate(csv.DictReader(fh), start=2):
            out[(row.get(key_col) or "").strip()] = n
    return out


def _read(name):
    with open(os.path.join(DATA, name), encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _status_family(status):
    """Collapse a long free-text status to its leading verdict word."""
    s = (status or "").strip().split("(")[0].split(" - ")[0].split(" \u2014 ")[0].strip()
    return (s.split()[0] if s.split() else "").lower()


def audit():
    reqs = _read("requirements.csv")
    ready = _read("decision_readiness.csv")
    mapping = _read("readiness_mapping.csv")

    req_text = {r["req_id"].strip(): (r.get("requirement (from brief)") or "") for r in reqs}
    req_line = _line_index("requirements.csv", "req_id")
    ready_line = _line_index("decision_readiness.csv", "req_id")
    claimed = {(m.get("readiness_id") or "").strip(): (m.get("match_quality") or "").strip()
               for m in mapping}
    ready_by_req = {}
    for r in ready:
        ready_by_req.setdefault((r.get("requirement_id") or "").strip(), []).append(r)

    # ---- 1. duplicate requirement rows ------------------------------------
    req_ids = list(req_text)
    parent = {i: i for i in req_ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    edges = []
    for i, a in enumerate(req_ids):
        for b in req_ids[i + 1:]:
            s = _ratio(req_text[a], req_text[b])
            if s >= DUP_THRESHOLD:
                union(a, b)
                edges.append((a, b, round(s, 3)))

    groups = {}
    for i in req_ids:
        groups.setdefault(find(i), []).append(i)

    group_rows, groups_with_divergence = [], 0
    for root, members in sorted(groups.items(), key=lambda kv: min(kv[1])):
        if len(members) < 2:
            continue
        members = sorted(members)
        answers, verdict_bits = [], []
        for m in members:
            rr = ready_by_req.get(m) or []
            st = rr[0]["status"] if rr else "(no readiness row)"
            answers.append((m, st, _status_family(st)))
        distinct = sorted({a[2] for a in answers if a[2]})
        divergent = len(distinct) > 1
        groups_with_divergence += 1 if divergent else 0
        pair_sim = max([s for a, b, s in edges if a in members and b in members] or [1.0])
        group_rows.append({
            "requirement_ids_in_group": "; ".join(members),
            "group_size": len(members),
            "identical_text": "yes" if all(_norm(req_text[m]) == _norm(req_text[members[0]]) for m in members) else "no",
            "max_pair_similarity": f"{pair_sim:.3f}",
            "requirement_text": req_text[members[0]],
            "readiness_answers": " | ".join(f"{m}: {st}" for m, st, _ in answers),
            "answers_agree": "no - DIVERGENT" if divergent else "yes",
            "requirement_register_lines": ", ".join(str(req_line.get(m, "")) for m in members),
            "evidence_basis": "data/requirements.csv text compared within the register by scripts/readiness_audit.py",
            "source_url": "https://github.com/karagemop466-tech/X2/blob/main/data/requirements.csv",
        })

    with open(OUT_GROUPS, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(group_rows[0].keys()))
        w.writeheader()
        w.writerows(group_rows)

    # ---- 1b. identifier lanes ---------------------------------------------
    # Several registers mint IDs of the form D<n> for different things: the
    # decision-chain gates ("Gate #", D01..D10), the readiness rows (D01..D65),
    # the demotion-gate rules and the decision-queue ids. A bare "D01" is
    # therefore ambiguous on a site whose navigation includes all of them, and a
    # reader cross-referencing "D01" between two pages can land on a different
    # object. This is measured, not fixed here: the fix renumbers a register that
    # other flags and pages cite, which is the owner's call (see F132).
    chain_path = os.path.join(DATA, "decision-chain.csv")
    lane_rows = []
    if os.path.exists(chain_path):
        with open(chain_path, encoding="utf-8-sig", newline="") as fh:
            chain = list(csv.DictReader(fh))
        chain_line = _line_index("decision-chain.csv", "gate_id")
        ready_ids = {r["req_id"].strip() for r in ready}
        for c in chain:
            gid = (c.get("gate_id") or "").strip()
            if gid in ready_ids:
                lane_rows.append({
                    "identifier": gid,
                    "lane_a_register": "data/decision-chain.csv (a gate that must be answered)",
                    "lane_a_meaning": c.get("decision_needed") or "",
                    "lane_a_line": chain_line.get(gid, ""),
                    "lane_b_register": "data/decision_readiness.csv (a requirement's readiness row)",
                    "lane_b_meaning": next((x["brief_item"] for x in ready
                                            if x["req_id"].strip() == gid), ""),
                    "lane_b_line": ready_line.get(gid, ""),
                    "collision_is": "same label, different object",
                    "evidence_basis": "ID equality across two registers, checked by scripts/readiness_audit.py",
                    "source_url": "https://github.com/karagemop466-tech/X2/blob/main/data/decision-chain.csv",
                })
    with open(OUT_LANES, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(lane_rows[0].keys()) if lane_rows else
                           ["identifier", "lane_a_register", "lane_a_meaning", "lane_a_line",
                            "lane_b_register", "lane_b_meaning", "lane_b_line", "collision_is",
                            "evidence_basis", "source_url"])
        w.writeheader()
        w.writerows(lane_rows)

    # ---- 2 & 3. per-readiness-row checks ----------------------------------
    seen_brief = {}
    for r in ready:
        seen_brief.setdefault(_norm(r.get("brief_item")), []).append(r["req_id"].strip())

    rows = []
    for r in ready:
        did = r["req_id"].strip()
        rid = (r.get("requirement_id") or "").strip()
        brief = r.get("brief_item") or ""
        own = req_text.get(rid, "")
        sim_own = round(_ratio(brief, own), 3)

        best_id, best_sim = "", -1.0
        for cand, text in req_text.items():
            s = _ratio(brief, text)
            if s > best_sim:
                best_id, best_sim = cand, s
        best_sim = round(best_sim, 3)

        dup_of = [x for x in seen_brief.get(_norm(brief), []) if x != did]
        recorded = claimed.get(did, "")

        # Verdicts are ordered from "this row is exactly its requirement" to
        # "the register does not carry this brief line at all". The distinction
        # between a MISROUTE and an UNREGISTERED line matters: a misroute means the
        # text belongs to some other R-id, while an unregistered line means the
        # register is missing a row entirely. Collapsing the two would overstate.
        if sim_own >= 0.999:
            verdict = "text is identical to its own requirement"
        elif sim_own >= DUP_THRESHOLD:
            verdict = "same brief item as its own requirement, reworded"
        elif best_sim >= 0.999 and best_id != rid:
            verdict = "published text is identical to a DIFFERENT requirement (%s)" % best_id
        elif best_sim >= DUP_THRESHOLD and best_id != rid:
            verdict = "published text belongs to a different requirement (%s) better than its own" % best_id
        elif best_sim < ABSENT_THRESHOLD:
            verdict = "brief line the register has no requirement row for"
        else:
            verdict = "related to, but not the same item as, its own requirement"

        # The label check, using each label's stated meaning (F103).
        if recorded == "exact":
            agrees = "yes" if sim_own >= DUP_THRESHOLD else "NO - labelled exact; texts are not the same item"
        elif recorded == "new":
            agrees = ("yes" if sim_own >= DUP_THRESHOLD
                      else "NO - labelled new; the register holds no matching row")
        elif recorded in ("approximate", "related", "extension"):
            weak = sim_own < DUP_THRESHOLD
            agrees = "yes - weak label, weak match" if weak else "check - labelled %s, texts are near-identical" % recorded
        else:
            agrees = "unrecorded"

        rows.append({
            "readiness_id": did,
            "requirement_id_printed": rid,
            "match_quality_recorded": recorded,
            "verdict": verdict,
            "text_similarity_to_own_requirement": f"{sim_own:.3f}",
            "best_matching_requirement_id": best_id,
            "best_matching_similarity": f"{best_sim:.3f}",
            "same_brief_item_on_another_row": "; ".join(dup_of) or "",
            "label_agrees_with_text": agrees,
            "requirement_text_printed_beside_it": own,
            "brief_item_published_on_the_site": brief,
            "requirement_register_line": req_line.get(rid, ""),
            "readiness_register_line": ready_line.get(did, ""),
            "evidence_basis": "data/decision_readiness.csv vs data/requirements.csv, compared by scripts/readiness_audit.py",
            "source_url": "https://github.com/karagemop466-tech/X2/blob/main/data/readiness_mapping.csv",
        })

    with open(OUT_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    def n(pred):
        return sum(1 for x in rows if pred(x))

    dup_groups = group_rows
    summary = {
        "readiness_rows": len(rows),
        "requirements_rows": len(req_text),
        "distinct_requirement_groups": len(groups),
        "duplicate_groups": len(dup_groups),
        "rows_absorbed_by_duplicates": sum(g["group_size"] - 1 for g in dup_groups),
        "duplicate_groups_with_divergent_answers": groups_with_divergence,
        "identical": n(lambda x: x["verdict"] == "text is identical to its own requirement"),
        "reworded": n(lambda x: x["verdict"] == "same brief item as its own requirement, reworded"),
        "misrouted_identical": n(lambda x: x["verdict"].startswith("published text is identical")),
        "misrouted_near": n(lambda x: x["verdict"].startswith("published text belongs to a different")),
        "no_register_row": n(lambda x: x["verdict"] == "brief line the register has no requirement row for"),
        "related_only": n(lambda x: x["verdict"] == "related to, but not the same item as, its own requirement"),
        "duplicate_publication": n(lambda x: bool(x["same_brief_item_on_another_row"])),
        "labels_contradicted": n(lambda x: x["label_agrees_with_text"].startswith("NO")),
        "lane_collisions": len(lane_rows),
        "dup_threshold": DUP_THRESHOLD,
        "absent_threshold": ABSENT_THRESHOLD,
    }
    return rows, group_rows, summary


def main():
    rows, groups, s = audit()
    print(f"readiness rows: {s['readiness_rows']}   requirement rows: {s['requirements_rows']}   "
          f"distinct requirement statements: {s['distinct_requirement_groups']}")
    print(f"duplicate requirement groups ............... {s['duplicate_groups']} "
          f"({s['rows_absorbed_by_duplicates']} surplus rows; "
          f"{s['duplicate_groups_with_divergent_answers']} carry DIVERGENT answers)")
    print(f"  text identical to its own requirement .... {s['identical']}")
    print(f"  same item, reworded ...................... {s['reworded']}")
    print(f"  published text identical to another row .. {s['misrouted_identical']}")
    print(f"  belongs to another row better than its own  {s['misrouted_near']}")
    print(f"  related, not the same item ............... {s['related_only']}")
    print(f"  register has no row for the brief line ... {s['no_register_row']}")
    print(f"  same brief item published twice .......... {s['duplicate_publication']}")
    print(f"  recorded match_quality contradicted ...... {s['labels_contradicted']}")
    print(f"identifier labels shared by two different registers ... {s['lane_collisions']}")
    print(f"wrote {os.path.relpath(OUT_CSV, ROOT)}, {os.path.relpath(OUT_GROUPS, ROOT)} "
          f"and {os.path.relpath(OUT_LANES, ROOT)}")


if __name__ == "__main__":
    main()
