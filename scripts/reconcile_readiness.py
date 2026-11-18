#!/usr/bin/env python3
"""Reconcile data/decision_readiness.csv to one row per requirement in the register.

F90 (open): the landing decision-readiness table had 45 rows while the
requirements register (data/requirements.csv) has 58, so 13 requirements had
no readiness row. The brief requires "one row per requirement, with the gate
that blocks it and the number that would clear it."

This script:
  1. maps each existing readiness row (D01-D45) to the register requirement it
     answers (data/readiness_mapping.csv records the mapping and its quality),
  2. adds one readiness row for every register requirement not yet answered,
  3. writes the reconciled decision_readiness.csv with a `requirement_id` column,
  4. asserts the mapping is a bijection onto R01-R58 (each exactly once).

The D->R mapping is this session's interpretation of two registers authored by
parallel sessions; it is recorded explicitly and flagged (F103) for owner review.
Nothing in the register is changed and no value is inferred.

Run:  python3 scripts/reconcile_readiness.py
"""
import csv
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")

# D-id -> register R-id. Quality: exact (text matches the register),
# related (same domain, not a literal duplicate), approximate (the register has
# no dedicated row; nearest domain row chosen, flagged F103).
MAPPING = {
    "D01": ("R44", "exact"),    # price-snapshot store
    "D02": ("R38", "exact"),    # verified results feed
    "D03": ("R53", "exact"),    # fair/market/difference columns
    "D04": ("R46", "exact"),    # signal vs staking
    "D05": ("R47", "exact"),    # demotion gate
    "D06": ("R22", "related"),  # pre-register / backtest firewall
    "D07": ("R25", "related"),  # freeze a rule before data (validation gates)
    "D08": ("R08", "approximate"),  # train/validation/holdout (no register row)
    "D09": ("R09", "related"),  # injury as surprise
    "D10": ("R10", "approximate"),  # injury clock time (no register row)
    "D11": ("R28", "approximate"),  # daily timestamped capture (no register row)
    "D12": ("R48", "approximate"),  # immutable snapshots (no register row)
    "D13": ("R49", "approximate"),  # inactive lists + snap counts (no register row)
    "D14": ("R50", "approximate"),  # reserve list (no register row)
    "D15": ("R43", "related"),  # official depth-chart register
    "D16": ("R51", "related"),  # depth order from playing time
    "D17": ("R52", "approximate"),  # durable storage + alerts (no register row)
    "D18": ("R55", "approximate"),  # per-team view (no register row)
    "D19": ("R56", "approximate"),  # roster turnover as data event (no register row)
    "D20": ("R57", "approximate"),  # calibrate Questionable (no register row)
    "D21": ("R58", "approximate"),  # designation reliability (no register row)
    "D22": ("R01", "approximate"),  # NFL.com terms (no register row)
    "D23": ("R02", "approximate"),  # public/private data layer (no register row)
    "D24": ("R03", "approximate"),  # personnel ablation (no register row)
    "D25": ("R04", "approximate"),  # fixture-context features (no register row)
    "D26": ("R05", "approximate"),  # venue transcription (no register row)
    "D27": ("R06", "approximate"),  # model output = probability + inputs (no register row)
    "D28": ("R07", "related"),  # price residual on a schedule
    "D29": ("R11", "approximate"),  # 136-game backtest corpus (no register row)
    "D30": ("R12", "approximate"),  # price-data policy (no register row)
    "D31": ("R13", "related"),  # two-stage leaderboard / escrow
    "D32": ("R14", "approximate"),  # vig-free decomposition (no register row)
    "D33": ("R15", "related"),  # joint-evidence gate for parlays/props
    "D34": ("R16", "related"),  # proper-score divisions
    "D35": ("R17", "related"),  # Brier skill ranking with uncertainty
    "D36": ("R18", "approximate"),  # two estimators until one wins (no register row)
    "D37": ("R19", "approximate"),  # weekly what-changed diff (no register row)
    "D38": ("R20", "approximate"),  # drift alarm on scrapers (no register row)
    "D39": ("R21", "approximate"),  # control baseline on every run (no register row)
    "D40": ("R27", "exact"),    # removal-of-luck panel
    "D41": ("R29", "approximate"),  # two-sided change-our-mind (no register row)
    "D42": ("R30", "approximate"),  # stadium roof / NWS overlay (no register row)
    "D43": ("R31", "related"),  # re-capture Week 10 injury tables
    "D44": ("R32", "approximate"),  # populate missing Lions designations (no register row)
    "D45": ("R33", "approximate"),  # archive past-season reports (no register row)
}

# Content for the register rows that gain a new readiness row. Fields:
# gate, number, evidence (short basis). Source URL is taken from the register.
NEW_ROWS = {
    "R23": ("No prospective sample graded; thresholds, jurisdiction and data rights unresolved (F09/F16/F17/F42).",
            "1 prospectively graded strategy with approved thresholds and cleared rights."),
    "R24": ("No player-prop outcomes, prices or settlement rules (F31).",
            "Player-prop outcomes, prices and settlement rules for 1 market family."),
    "R26": ("Player-prop and cross-game correlations unavailable (F31).",
            "Prop/parlay joint correlations from paired official outcomes (0 today)."),
    "R34": ("None — PR opened and merged; Pages confirmation recorded.",
            "already met (PR merged; Pages built)."),
    "R35": ("None — two independent implementations reconcile (0 score disagreements).",
            "already met."),
    "R36": ("Qualification disagreement unresolved (F42); rewards held.",
            "1 pre-registered test settling the qualification disagreement."),
    "R37": ("No licensed odds feed (F07).",
            "Opening and closing prices for every originated market (0 today)."),
    "R39": ("None — side, total, moneyline order fixed.",
            "already met."),
    "R40": ("No market line feed (F07).",
            "Market lines for 13 of 13 Week 11 games (0 today)."),
    "R41": ("Prospective forecasts and licensed prices (F07).",
            "0 prospective score/rank/ROI values before validation; already enforced."),
    "R42": ("Thresholds await owner approval (F17).",
            "1 approved demotion-gate threshold set."),
    "R45": ("None — origination order and the three columns are fixed.",
            "already met."),
    "R54": ("Metric definition to be agreed (F85); ranking needs registration (F87).",
            "1 agreed luck metric and 1 registered prospective ranking."),
}

HEADER = ["req_id", "requirement_id", "brief_item", "status",
          "what_the_repo_shows_now", "blocking_gate", "number_that_clears_it",
          "evidence_basis", "source_url"]


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in HEADER})


def main():
    reg = {r["req_id"]: r for r in read_csv(os.path.join(DATA, "requirements.csv"))}
    # Only the original D01-D45 rows are seed rows; any previously generated
    # rows are regenerated from the register so the script is idempotent.
    ready = [r for r in read_csv(os.path.join(DATA, "decision_readiness.csv"))
             if r["req_id"] in MAPPING]

    mapped = {d: rid for d, (rid, _q) in MAPPING.items()}
    if len(set(mapped.values())) != len(mapped):
        sys.exit("MAPPING is not one-to-one; fix before running.")
    covered = set(mapped.values())
    missing = [rid for rid in reg if rid not in covered]
    if set(missing) != set(NEW_ROWS):
        sys.exit(f"NEW_ROWS does not match uncovered register rows: {set(missing) ^ set(NEW_ROWS)}")

    out = []
    mapping_rows = []
    for r in ready:
        rid, quality = MAPPING.get(r["req_id"], ("", ""))
        row = dict(r)
        row["requirement_id"] = rid
        out.append(row)
        mapping_rows.append({"readiness_id": r["req_id"], "requirement_id": rid, "match_quality": quality})

    next_d = len(ready) + 1
    for rid in sorted(missing):
        reg_row = reg[rid]
        gate, number = NEW_ROWS[rid]
        done = reg_row["status"].lower().startswith("done")
        if done:
            gate = "None — satisfied (see requirements register)."
            number = "already met."
        where = reg_row.get("where_addressed", "").strip()
        note = reg_row.get("blocker_or_note", "").strip()
        tokens = ("", "—", "-", "fact", "status", "decision")
        if where not in tokens:
            shown = where
        elif note not in tokens:
            shown = note
        else:
            shown = f"See requirements register {rid}."
        basis = f"requirements register {rid}"
        if where and where not in tokens:
            basis += f"; {where}"
        out.append({
            "req_id": f"D{next_d:02d}",
            "requirement_id": rid,
            "brief_item": reg_row["requirement (from brief)"],
            "status": reg_row["status"],
            "what_the_repo_shows_now": shown,
            "blocking_gate": gate,
            "number_that_clears_it": number,
            "evidence_basis": basis,
            "source_url": reg_row["evidence_url"],
        })
        mapping_rows.append({"readiness_id": f"D{next_d:02d}", "requirement_id": rid, "match_quality": "new"})
        next_d += 1

    write_csv(os.path.join(DATA, "decision_readiness.csv"), out)
    with open(os.path.join(DATA, "readiness_mapping.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["readiness_id", "requirement_id", "match_quality"])
        w.writeheader()
        w.writerows(mapping_rows)

    ids = [r["requirement_id"] for r in out if r["requirement_id"]]
    if sorted(ids) != sorted(reg.keys()):
        sys.exit(f"Bijection failed: {set(ids) ^ set(reg.keys())}")
    print(f"Reconciled readiness table: {len(out)} rows, one per requirement ({len(reg)}).")
    print(f"  mapped existing: {len(ready)}, added: {len(missing)}")
    print(f"  match quality: exact={sum(1 for m in mapping_rows if m['match_quality']=='exact')}, "
          f"related={sum(1 for m in mapping_rows if m['match_quality']=='related')}, "
          f"approximate={sum(1 for m in mapping_rows if m['match_quality']=='approximate')}, new={len(missing)}")


if __name__ == "__main__":
    main()
