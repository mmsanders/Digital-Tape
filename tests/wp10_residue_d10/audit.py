#!/usr/bin/env python3
"""Audit the supersession record, the DRAFT-10 ledger delta and the synthetic manifest against the planner."""
import hashlib
import json
from pathlib import Path

import plan as P

ROOT = Path(__file__).resolve().parent
DRAFT10 = {"product_main": "d8243c95c88f38ce8b7fd6ad0de4280dd735d7a1",
           "tapefs_sha256": "2a6a9f7b6fe1e5f9e3fe068b3c6460a81256276082bb7e336c01dbf1e9c17eba",
           "engine_api_sha256": "aa042e41e35b02bf2bb6b3896e59340a947720c27dc5fc52a24d657ccd66b33a",
           "acceptance_sha256": "50aa63bd751fdc6b4636de0eb48253887be19b7ec2841768449217b4e9b9e547"}


def load(name):
    raw = (ROOT / name).read_bytes().replace(b"\r\n", b"\n")
    return json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()


def span(ranges):
    assert all(a <= b for a, b in ranges) and all(ranges[i][1] < ranges[i + 1][0] for i in range(len(ranges) - 1))
    return sum(b - a + 1 for a, b in ranges)


def main():
    census = P.census()
    groups = {g["index"]: g for g in P.iter_groups()}

    sup, sup_sha = load("SUPERSESSION.json")
    assert sup["spec"] == DRAFT10
    s1, s2, s3 = sup["superseded"]
    assert (s1["id"], s2["id"], s3["id"]) == ("S1", "S2", "S3")
    assert s1["cases"] == sum(r["cases"] for r in s1["representatives"]) == \
        sum(span(r["index_ranges"]) for r in s1["representatives"]) == 22_604
    assert s1["v_r54_03_cells"] == 48 and s1["row_cases"] == 207_560
    for r in s1["representatives"]:
        assert r["class"] == ["TAPE_ERR_BAD_MAGIC", None] and r["first_inject"] == ["write", 1, 1]
    seen = set()
    for c in s1["replaced_by"]["exact_counterparts"]:
        g = groups[c["group_index"]]
        assert {k: g[k] for k in ("row", "op", "shape", "mode", "l1", "scope")} == \
            {k: c[k] for k in ("row", "op", "shape", "mode", "l1", "scope")}
        assert c["l1"] == 1 and c["scope"] == "all_writes"
        seen.add((c["shape"], c["mode"]))
    assert {r["shape"] for r in s1["representatives"]} == {s for s, _ in seen} and len(seen) == 4
    assert s2["cases"] == sum(g["cases"] for g in s2["groups"]) == sum(span(g["index_ranges"]) for g in s2["groups"]) \
        == 5_110 and s2["row_cases"] == 64_734
    assert all(g["landed"] == [1, 511] and g["cases"] == 511 for g in s2["groups"])
    assert s3["cases"] == sum(g["cases"] for g in s3["groups"]) == sum(span(g["index_ranges"]) for g in s3["groups"]) \
        == 4_032
    assert all(g["landed"] == [8, 511] for g in s3["groups"])

    d9, d9_sha = load("evidence/d9_census.json")
    dr = sup["draft9_rule_census"]
    assert (dr["resurrecting_injections"], dr["resurrecting_groups"]) == \
        (d9["resurrecting_injections"], d9["resurrecting_groups"]) == (1_456, 200)
    assert sum(v["injections"] for v in d9["by_group"].values()) == 1_456
    assert all(v.get("l1_max", 1) <= 12 for v in d9["by_group"].values())

    led, led_sha = load("ledger-d10.json")
    assert led["spec"] == DRAFT10
    w6 = led["ledgers"]["WP-06"]
    assert sum(w6["status_after"].values()) == w6["rows_total"] == 45
    assert sum(d["to"] == "unreachable by spec" for d in w6["deltas"]) == w6["status_after"]["unreachable by spec"] == 2
    assert w6["closed"] is True and set(w6["status_after"]) <= {"accepted exact evidence", "unreachable by spec",
                                                                "outside WP-06"}
    w10 = led["ledgers"]["WP-10"]
    assert w10["rows_total_after"] == w10["rows_total_before"] + sum(d["from"] is None for d in w10["deltas"])
    assert w10["closed"] is False
    assert any(d["to"] == "unreachable by spec" and d["finding"] == "V10-005" for d in led["ledgers"]["WP-12a"]["deltas"])

    man, man_sha = load("evidence/synthetic/manifest.json")
    for k in ("groups", "injections", "injections_total", "closure_reruns", "caseset_sha256"):
        assert man[k] == census[k], k
    assert man["group_count"] == sum(census["groups"].values())

    print(f"PASS audit: supersession S1 22,604 + S2 5,110 + S3 4,032 (sha256 {sup_sha}); DRAFT-9 rule census 1,456 "
          f"in 200 groups (sha256 {d9_sha}); ledger delta WP-06 closed, WP-10 open pending binding (sha256 {led_sha}); "
          f"manifest {man_sha} binds caseset {census['caseset_sha256']}")


if __name__ == "__main__":
    main()
