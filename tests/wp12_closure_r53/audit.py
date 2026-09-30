#!/usr/bin/env python3
"""Validate the WP-12/WP-12a ledger vocabulary, citations and gap-plan mapping."""
import hashlib
import json
from pathlib import Path

from oracle import load_plan, plan_sha256

ROOT = Path(__file__).resolve().parent


def main():
    raw = (ROOT / "coverage-ledger.json").read_bytes().replace(b"\r\n", b"\n")
    ledger = json.loads(raw)
    plan = load_plan()
    allowed = set(ledger["allowed_statuses"])
    rows = ledger["rows"]
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate ledger row"
    for r in rows:
        assert r["status"] in allowed, r["id"]
        if r["status"] == "accepted exact evidence":
            assert r.get("evidence") and set(r["evidence"]) <= set(ledger["dispositions"]), r["id"]
            assert r.get("cases"), r["id"]
        elif r["status"] == "uncovered: published here":
            assert r.get("package_cases") and r.get("why_uncovered"), r["id"]
        else:
            assert r.get("citation"), r["id"]
    gap_rows = {r["id"]: set(r["package_cases"]) for r in rows if r["status"] == "uncovered: published here"}
    plan_rows = {}
    for case in plan["cases"]:
        for row in case["rows"]:
            plan_rows.setdefault(row, set()).add(case["id"])
    assert gap_rows == plan_rows, "ledger gap rows and plan cases disagree"
    assert len(gap_rows) >= 3, "tranche minimum (3 rows) not met"
    findings = [r["id"] for r in rows if r.get("pm_finding")]
    by_status = {s: sum(r["status"] == s for r in rows) for s in ledger["allowed_statuses"]}
    print("PASS", len(rows), "ledger rows", by_status, "| gap rows", len(gap_rows),
          "| gap cases", len(plan["cases"]), "| PM findings", findings,
          "| ledger", hashlib.sha256(raw).hexdigest(), "| plan", plan_sha256())


if __name__ == "__main__":
    main()
