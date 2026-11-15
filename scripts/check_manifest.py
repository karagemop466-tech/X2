#!/usr/bin/env python3
"""Retained-hash manifest for the committed captures and transcriptions (T100).

Every file in data/capture_manifest.csv is pinned to a SHA-256 digest, a byte
count and a row count. Any change to a pinned file makes the check fail, so a
change to a snapshot can never happen silently: it must be re-pinned on purpose
with --update, and the commit that does so is the record of the change.

What this proves: the bytes of these committed files are the bytes that were
pinned. What it does NOT prove: that the committed rows equal the official NFL
page. That comparison is scripts/verify_snapshot.py and the dated repo-review
registers. The official pages are not retained here (flag F16), so the hashes
cover the repository's transcriptions, not the official page bytes.

Run:   python3 scripts/check_manifest.py            (check; exit 1 on drift)
       python3 scripts/check_manifest.py --update   (re-pin after a deliberate change)

Not yet wired into scripts/build.py: build.py is a shared output, so wiring it in
is a Request to the integration session (COORDINATION.md).
Standard library only.
"""
import csv
import hashlib
import io
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MANIFEST = os.path.join(ROOT, "data", "capture_manifest.csv")
FIELDS = ["file", "sha256", "bytes", "rows", "captured_read_date", "source_url", "note"]


def _count_rows(path):
    with open(path, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8")
    if path.endswith(".csv"):
        return max(0, len(list(csv.reader(io.StringIO(text, newline=""))) ) - 1)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if path.endswith(".tsv"):
        return max(0, len(lines) - 1)           # first line is a header
    return len(lines)                           # plain transcription: one row per line


def _digest(path):
    with open(path, "rb") as f:
        data = f.read()
    return hashlib.sha256(data).hexdigest(), len(data)


def _read_manifest():
    with open(MANIFEST, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def verify_manifest():
    """Return a list of human-readable problems (empty list = all pinned files match)."""
    problems = []
    for row in _read_manifest():
        rel = row["file"]
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            problems.append(f"manifest: pinned file missing: {rel}")
            continue
        digest, size = _digest(path)
        rows = _count_rows(path)
        if digest != row["sha256"]:
            problems.append(f"manifest: hash changed for {rel} (pinned {row['sha256'][:12]}, now {digest[:12]})")
        if str(size) != row["bytes"]:
            problems.append(f"manifest: size changed for {rel} (pinned {row['bytes']}, now {size})")
        if str(rows) != row["rows"]:
            problems.append(f"manifest: row count changed for {rel} (pinned {row['rows']}, now {rows})")
    return problems


def update_manifest():
    rows = _read_manifest()
    for row in rows:
        path = os.path.join(ROOT, row["file"])
        digest, size = _digest(path)
        row["sha256"], row["bytes"], row["rows"] = digest, str(size), str(_count_rows(path))
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\r\n")
    w.writeheader()
    w.writerows(rows)
    with open(MANIFEST, "w", encoding="utf-8", newline="") as f:
        f.write(buf.getvalue())
    print(f"Re-pinned {len(rows)} files in {os.path.relpath(MANIFEST, ROOT)}")


if __name__ == "__main__":
    if "--update" in sys.argv:
        update_manifest()
        sys.exit(0)
    problems = verify_manifest()
    n = len(_read_manifest())
    if problems:
        print(f"MANIFEST CHECK FAILED ({len(problems)} problem(s) across {n} pinned files):")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print(f"Manifest check passed: {n} pinned files match their SHA-256, size and row count.")
