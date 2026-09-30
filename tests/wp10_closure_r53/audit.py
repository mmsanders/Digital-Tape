#!/usr/bin/env python3
"""Validate the WP-10 ledger: vocabulary, citations, published rows <-> planner, ranked backlog."""
import hashlib
import json
from pathlib import Path

import model as M
from oracle import plan_census

ROOT = Path(__file__).resolve().parent


def main():
    raw = (ROOT / "coverage-ledger.json").read_bytes().replace(b"\r\n", b"\n")
    ledger = json.loads(raw)
    rows = ledger["rows"]
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate ledger row"
    census = plan_census()
    for r in rows:
        assert r["status"] in ledger["allowed_statuses"], r["id"]
        if r["status"] == "accepted exact evidence":
            assert r.get("evidence") and set(r["evidence"]) <= set(ledger["dispositions"]), r["id"]
        elif r["status"] == "uncovered: published here":
            pts = r["injection_points"]
            assert set(pts) == set(r["package_cases"]), r["id"]
            for scenario, n in pts.items():
                assert M.SCENARIOS[scenario][3] == r["id"], f"{scenario} not planned under {r['id']}"
                assert census["by_scenario"][scenario] == n, f"{scenario} census {census['by_scenario'][scenario]}"
        elif r["status"] == "uncovered: backlog":
            assert isinstance(r.get("backlog_rank"), int) and r.get("why_uncovered"), r["id"]
        else:
            assert r.get("citation"), r["id"]
    published = {r["id"] for r in rows if r["status"] == "uncovered: published here"}
    assert published == {v[3] for v in M.SCENARIOS.values()}, "published rows and planner disagree"
    assert len(published) == 3, "issue #105 publishes exactly three rows"
    ranks = sorted(r["backlog_rank"] for r in rows if r["status"] == "uncovered: backlog")
    assert ranks == list(range(1, len(ranks) + 1)), f"backlog ranks {ranks}"
    backlog = [r["id"] for r in sorted((r for r in rows if r["status"] == "uncovered: backlog"),
                                       key=lambda r: r["backlog_rank"])]
    by_status = {s: sum(r["status"] == s for r in rows) for s in ledger["allowed_statuses"]}
    print("PASS", len(rows), "ledger rows", by_status, "| published", sorted(published),
          "| injection points", census["crash"], census["by_mode"], "| backlog", backlog,
          "| PM findings", [r["id"] for r in rows if r.get("pm_finding")],
          "| ledger", hashlib.sha256(raw).hexdigest(), "| caseset", census["caseset_sha256"])


if __name__ == "__main__":
    main()
