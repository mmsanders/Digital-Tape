#!/usr/bin/env python3
"""Validate the coverage ledger vocabulary, gap mapping and frozen identities."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    ledger = json.loads((ROOT / "coverage-ledger.json").read_text())
    plan = json.loads((ROOT / "gap_plan.json").read_text())
    allowed = set(ledger["allowed_statuses"])
    rows = ledger["rows"]
    assert len(rows) == len({r["id"] for r in rows})
    assert all(r["status"] in allowed for r in rows)
    cases = {c["id"] for c in plan["cases"]}
    mapped = {c for r in rows for c in r.get("package_cases", [])}
    assert cases == mapped
    missing = [r for r in rows if r["status"] == "missing Product observation"]
    assert len(cases) >= 3 and len(missing) >= 3
    blocked = {r["row"] for r in plan["blocked_rows"]}
    assert blocked == {r["id"] for r in missing if r.get("blocker")}
    print("PASS", len(rows), "ledger rows;", len(cases), "observable gap rows;",
          len(blocked), "contract-blocked rows; ledger",
          hashlib.sha256((ROOT / "coverage-ledger.json").read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
