#!/usr/bin/env python3
"""Validate the closing WP-10 ledger: #105's 61 rows plus WP10.dup.rerun_crash, none left uncovered."""
import hashlib
import json
from pathlib import Path

import oracle as O

ROOT = Path(__file__).resolve().parent
SOURCE_SHA = "369566e280a197a42e0be5c233f66241cde41268f9642881a107341669d27817"
NEW_ROW = "WP10.dup.rerun_crash"
HERE_ROWS = {O.ROW1, O.ROW2, O.ROW3, O.ROW4}


def main():
    raw = (ROOT / "coverage-ledger.json").read_bytes().replace(b"\r\n", b"\n")
    d = json.loads(raw)
    assert d["source_ledger"]["sha256"] == SOURCE_SHA and len(d["source_ledger"]["row_ids"]) == 61
    rows = d["rows"]
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)) == 62, "ledger must hold 62 unique rows"
    assert set(ids) == set(d["source_ledger"]["row_ids"]) | {NEW_ROW}, "ledger rows differ from #105 + rerun_crash"
    allowed = set(d["allowed_statuses"])
    assert not any("uncovered" in s for s in allowed), "uncovered is not a closing status"
    counts = {}
    for r in rows:
        assert r["status"] in allowed, f"{r['id']}: status {r['status']!r}"
        counts[r["status"]] = counts.get(r["status"], 0) + 1
        if r["status"] == "accepted exact evidence":
            assert r.get("evidence"), f"{r['id']}: accepted row without evidence"
            continue
        pkg = d["packages"][r["package_ref"]]
        assert pkg["package"].startswith("tests/") and pkg["publication"], f"{r['id']}: package reference"
        disposed = r["status"] == "published; Product binding disposed PASS"
        assert bool(pkg.get("disposition")) == disposed, f"{r['id']}: disposition does not match status"
        if r["package_ref"] == "R54-FINAL":
            assert r["id"] in HERE_ROWS, f"{r['id']} is not one of this package's rows"
    assert {r["id"] for r in rows if r.get("package_ref") == "R54-FINAL"} == HERE_ROWS
    census = O.plan_census()
    print(f"PASS closing ledger: 62 rows {counts} | this package: {sorted(HERE_ROWS)} | "
          f"row4 {census['row4']} over {census['row4_representatives']} representatives | "
          f"ledger sha256 {hashlib.sha256(raw).hexdigest()} | caseset {census['caseset_sha256']}")


if __name__ == "__main__":
    main()
