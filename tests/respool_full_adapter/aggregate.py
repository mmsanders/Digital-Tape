#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "tests" / "respool_full_draft8"
sys.path.insert(0, str(PKG))

from planner import EXPECTED_BY_MODE, EXPECTED_BY_PASS, EXPECTED_CASESET_SHA256, EXPECTED_TOTAL, planner_summary  # noqa: E402

GROUP_TOTAL = {
    ("v3_003", "pass1"): 1_051_653,
    ("v3_003", "pass2"): 1_051_653,
    ("no_lower_run", "pass1"): 1_542,
}
PARTS = 8
EXPECTED_TARGETS = {
    "chunk_copy": 4_203_522,
    "entry_block": 3_078,
    "header_block": 3_078,
    "chunk_flush": 6,
    "entry_block_flush": 6,
    "header_block_flush": 6,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--evidence", type=Path, required=True)
    args = ap.parse_args()
    evidence = args.evidence if args.evidence.is_absolute() else ROOT / args.evidence
    evidence.mkdir(parents=True, exist_ok=True)

    summaries = []
    failures = []
    for p in sorted(args.input.rglob("summary.json")):
        obj = json.loads(p.read_text())
        if obj.get("format") != "WP10-RESPOOL-SHARD-1":
            continue
        summaries.append((p, obj))
        if obj.get("status") != "PASS":
            failures.append((obj.get("failed_case_index", 1 << 62), p, obj))

    if failures:
        failures.sort(key=lambda x: x[0])
        _, p, obj = failures[0]
        repros = list(p.parent.glob("failure-reproducer.json"))
        if repros:
            shutil.copy2(repros[0], evidence / "failure-reproducer.json")
        (evidence / "aggregate.json").write_text(
            json.dumps({
                "format": "WP10-RESPOOL-AGGREGATE-1",
                "status": "FAIL",
                "first_failed_case_index": obj.get("failed_case_index"),
                "failure_shard": obj,
                "shards_seen": len(summaries),
            }, indent=2, sort_keys=True) + "\n"
        )
        print(f"FAIL first_case={obj.get('failed_case_index')}", file=sys.stderr)
        return 1

    expected_keys = set()
    for fixture, pass_name in GROUP_TOTAL:
        for mode in ("flush_required", "write_through"):
            for part in range(PARTS):
                expected_keys.add((fixture, pass_name, mode, part, PARTS))

    seen = {}
    total = 0
    by_mode = {"flush_required": 0, "write_through": 0}
    by_pass = {
        "v3_003:pass1": 0,
        "v3_003:pass2": 0,
        "no_lower_run:pass1": 0,
    }
    by_target = {k: 0 for k in EXPECTED_TARGETS}
    product_ids = set()

    for _, s in summaries:
        key = (s["fixture"], s["pass"], s["mode"], s["part"], s["parts"])
        if key in seen:
            raise SystemExit(f"duplicate shard {key}")
        seen[key] = s
        group_total = GROUP_TOTAL[(s["fixture"], s["pass"])]
        start = group_total * s["part"] // s["parts"]
        end = group_total * (s["part"] + 1) // s["parts"]
        if s["range"] != [start, end] or s["completed"] != end - start:
            raise SystemExit(f"shard range/count mismatch {key}")
        total += s["completed"]
        by_mode[s["mode"]] += s["completed"]
        by_pass[f"{s['fixture']}:{s['pass']}"] += s["completed"]
        for target, n in s["by_target"].items():
            by_target[target] = by_target.get(target, 0) + n
        product_ids.add((
            s["product_base"], s["product_commit"], s["product_tree"],
            s["verifier_import_commit"], s["verifier_tree"],
        ))

    if set(seen) != expected_keys:
        missing = sorted(expected_keys - set(seen))
        extra = sorted(set(seen) - expected_keys)
        raise SystemExit(f"shard partition mismatch missing={missing[:4]} extra={extra[:4]}")
    if len(product_ids) != 1:
        raise SystemExit(f"product provenance drift across shards: {len(product_ids)}")

    plan = planner_summary()
    checks = {
        "total": total == EXPECTED_TOTAL == 4_209_696,
        "planner_total": plan["total"] == EXPECTED_TOTAL,
        "planner_digest": plan["sha256"] == EXPECTED_CASESET_SHA256,
        "mode_counts": by_mode == EXPECTED_BY_MODE,
        "pass_counts": by_pass == {
            "v3_003:pass1": EXPECTED_BY_PASS["v3_003:pass1"],
            "v3_003:pass2": EXPECTED_BY_PASS["v3_003:pass2"],
            "no_lower_run:pass1": EXPECTED_BY_PASS["no_lower_run:pass1"],
        },
        "target_counts": by_target == EXPECTED_TARGETS,
    }
    if not all(checks.values()):
        raise SystemExit(f"aggregate census mismatch: {checks} mode={by_mode} pass={by_pass} target={by_target}")

    base, commit, tree, import_commit, verifier_tree = next(iter(product_ids))
    aggregate = {
        "format": "WP10-RESPOOL-AGGREGATE-1",
        "status": "PASS",
        "total": total,
        "flush_required": by_mode["flush_required"],
        "write_through": by_mode["write_through"],
        "by_pass": by_pass,
        "by_target": by_target,
        "shards": len(summaries),
        "parts_per_group": PARTS,
        "case_set_sha256": EXPECTED_CASESET_SHA256,
        "planner_summary": plan,
        "checks": checks,
        "product_base": base,
        "product_commit": commit,
        "product_tree": tree,
        "verifier_import_commit": import_commit,
        "verifier_tree": verifier_tree,
        "failure_reproducer_sha256": None,
    }
    out = evidence / "aggregate.json"
    out.write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n")
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    print(f"PASS total={total} shards={len(summaries)} caseset={EXPECTED_CASESET_SHA256}")
    print(f"aggregate_sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
