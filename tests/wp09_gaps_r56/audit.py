#!/usr/bin/env python3
"""Audit the #130 package: pins, row census, case set, and ledger <-> package consistency."""
import json
from pathlib import Path

import oracle as O
import pins
import rows as R

EXPECTED_CASESET = "5b14062694cfc1ef219612d8086bac56e0a1536680c129537548b687cfbc5fe0"
HERE = Path(__file__).resolve().parent


def main():
    census = O.plan_census()
    assert census["caseset_sha256"] == EXPECTED_CASESET, census
    assert (census["row1"], census["row2"]) == (3, 5), census
    ledger = json.loads((HERE / "wp09-ledger.json").read_text(encoding="utf-8"))
    rows = ledger["rows"]
    assert [r["id"] for r in rows] == [f"WP09-L{i:02d}" for i in range(1, 13)] + ["V-R55-01"]
    assert all(r["status"] in ledger["statuses"] for r in rows)
    gap_rows = {r["package_row"] for r in rows if "gap" in r["status"]}
    assert gap_rows == {R.ROW1, R.ROW2}, gap_rows
    assert all(("package_row" in r) == ("gap" in r["status"]) for r in rows)
    assert [r["id"] for r in rows if r["status"] == "listening-held"] == ["WP09-L01"]
    md = (HERE / "LEDGER.md").read_text(encoding="utf-8")
    for r in rows:
        assert f"| {r['id'][5:] if r['id'].startswith('WP09') else r['id']} |" in md, r["id"]
    print(f"PASS pins {sorted(pins.PINS)} | rows {R.ROW1}, {R.ROW2} | census {census} | "
          f"ledger {len(rows)} rows, gaps -> {sorted(gap_rows)}")


if __name__ == "__main__":
    main()
