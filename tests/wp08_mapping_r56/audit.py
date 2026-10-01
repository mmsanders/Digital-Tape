#!/usr/bin/env python3
"""Audit the #129 package: pins, row census, case set, and ledger <-> package consistency."""
import json
from pathlib import Path

import oracle as O
import pins
import rows as R

EXPECTED_CASESET = "9eca914a4f2ed87db31bb5cd1212b89dec52731e37cdd76e1fb8aa2af8424e30"
HERE = Path(__file__).resolve().parent


def main():
    census = O.plan_census()
    assert census["caseset_sha256"] == EXPECTED_CASESET, census
    assert (census["row1"], census["row2"]) == (60, 2), census
    ledger = json.loads((HERE / "wp08-ledger.json").read_text(encoding="utf-8"))
    rows = ledger["rows"]
    assert [r["id"] for r in rows] == [f"WP08-L{i:02d}" for i in range(1, 15)]
    assert all(r["status"] in ledger["statuses"] for r in rows)
    gap_rows = {r["package_row"] for r in rows if "gap" in r["status"]}
    assert gap_rows == {R.ROW1, R.ROW2}, gap_rows
    assert all(("package_row" in r) == ("gap" in r["status"]) for r in rows)
    held = [r["id"] for r in rows if r["status"] == "listening-held"]
    assert held == ["WP08-L01", "WP08-L14"], held
    md = (HERE / "LEDGER.md").read_text(encoding="utf-8")
    for r in rows:
        assert f"| {r['id'][5:]} |" in md, r["id"]
    print(f"PASS pins {sorted(pins.PINS)} | rows {R.ROW1}, {R.ROW2} | census {census} | "
          f"ledger {len(rows)} rows, gaps -> {sorted(gap_rows)}")


if __name__ == "__main__":
    main()
