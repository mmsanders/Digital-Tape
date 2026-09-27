#!/usr/bin/env python3
"""Deterministic DRAFT-8 full re-spool crash case planner."""
from __future__ import annotations

import hashlib
import json

BLOCK_BYTES = 512
DURABILITY_MODES = ("flush_required", "write_through")
CRASH_PASSES = (
    ("v3_003", "pass1", 2048),
    ("v3_003", "pass2", 2048),
    ("no_lower_run", "pass1", 1),
)

EXPECTED_TOTAL_CASES = 4_209_696
EXPECTED_CASESET_SHA256 = "02c52de7a7c51a6ffafe5c9d5afad9c23032b72fc11aaf206bb27a9c9506d3e1"
EXPECTED_BY_PASS = {
    "no_lower_run:pass1": 3_084,
    "v3_003:pass1": 2_103_306,
    "v3_003:pass2": 2_103_306,
}
EXPECTED_BY_MODE = {"flush_required": 2_104_848, "write_through": 2_104_848}
EXPECTED_BY_TARGET = {
    "chunk_copy": 4_203_522,
    "chunk_flush": 6,
    "entry_block": 3_078,
    "entry_block_flush": 6,
    "header_block": 3_078,
    "header_block_flush": 6,
}

def canonical_json(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

def iter_cases():
    index = 0
    for fixture, pass_name, chunk_blocks in CRASH_PASSES:
        for mode in DURABILITY_MODES:
            # Frozen WP-10: torn writes at EVERY block write, exhaustive rather
            # than sampled. Each copied audio block therefore gets all 513 write
            # boundaries: before/0, torn/1..511, after/512.
            for ordinal in range(chunk_blocks):
                yield {
                    "case_index": index, "fixture": fixture, "pass": pass_name,
                    "mode": mode, "target": "chunk_copy",
                    "injection": {
                        "kind": "before_write", "write_ordinal": ordinal,
                        "landed_bytes": 0,
                    },
                }
                index += 1
                for landed in range(1, BLOCK_BYTES):
                    yield {
                        "case_index": index, "fixture": fixture, "pass": pass_name,
                        "mode": mode, "target": "chunk_copy",
                        "injection": {
                            "kind": "torn_write", "write_ordinal": ordinal,
                            "landed_bytes": landed,
                        },
                    }
                    index += 1
                yield {
                    "case_index": index, "fixture": fixture, "pass": pass_name,
                    "mode": mode, "target": "chunk_copy",
                    "injection": {
                        "kind": "after_write", "write_ordinal": ordinal,
                        "landed_bytes": BLOCK_BYTES,
                    },
                }
                index += 1

            yield {
                "case_index": index, "fixture": fixture, "pass": pass_name,
                "mode": mode, "target": "chunk_flush",
                "injection": {"kind": "at_flush", "flush_ordinal": 0},
            }
            index += 1

            # Each pass has one one-block entry-array write and one one-block
            # header commit. These receive the same exhaustive 513 write
            # boundaries plus their following flush fault.
            for target, ordinal in (("entry_block", 0), ("header_block", 1)):
                yield {
                    "case_index": index, "fixture": fixture, "pass": pass_name,
                    "mode": mode, "target": target,
                    "injection": {
                        "kind": "before_write", "write_ordinal": ordinal,
                        "landed_bytes": 0,
                    },
                }
                index += 1
                for landed in range(1, BLOCK_BYTES):
                    yield {
                        "case_index": index, "fixture": fixture, "pass": pass_name,
                        "mode": mode, "target": target,
                        "injection": {
                            "kind": "torn_write", "write_ordinal": ordinal,
                            "landed_bytes": landed,
                        },
                    }
                    index += 1
                yield {
                    "case_index": index, "fixture": fixture, "pass": pass_name,
                    "mode": mode, "target": target,
                    "injection": {
                        "kind": "after_write", "write_ordinal": ordinal,
                        "landed_bytes": BLOCK_BYTES,
                    },
                }
                index += 1
                yield {
                    "case_index": index, "fixture": fixture, "pass": pass_name,
                    "mode": mode, "target": target + "_flush",
                    "injection": {"kind": "at_flush", "flush_ordinal": ordinal + 1},
                }
                index += 1

def planner_summary() -> dict:
    """One exhaustive pass computes census and canonical digest together."""
    by_pass, by_mode, by_target = {}, {}, {}
    total = 0
    h = hashlib.sha256()
    for case in iter_cases():
        total += 1
        p = f"{case['fixture']}:{case['pass']}"
        by_pass[p] = by_pass.get(p, 0) + 1
        by_mode[case["mode"]] = by_mode.get(case["mode"], 0) + 1
        by_target[case["target"]] = by_target.get(case["target"], 0) + 1
        h.update((canonical_json(case) + "\n").encode("ascii"))
    return {
        "total": total,
        "by_pass": dict(sorted(by_pass.items())),
        "by_mode": dict(sorted(by_mode.items())),
        "by_target": dict(sorted(by_target.items())),
        "sha256": h.hexdigest(),
    }

def case_counts() -> dict:
    s = planner_summary()
    return {k: s[k] for k in ("total", "by_pass", "by_mode", "by_target")}

def caseset_digest() -> str:
    return planner_summary()["sha256"]

def validate_summary(summary: dict) -> list[str]:
    errors = []
    if summary["total"] != EXPECTED_TOTAL_CASES:
        errors.append("total case count drift")
    if summary["by_pass"] != EXPECTED_BY_PASS:
        errors.append("per-pass count drift")
    if summary["by_mode"] != EXPECTED_BY_MODE:
        errors.append("durability-mode count drift")
    if summary["by_target"] != EXPECTED_BY_TARGET:
        errors.append("target count drift")
    if summary["sha256"] != EXPECTED_CASESET_SHA256:
        errors.append("case-set digest drift")
    return errors

def validate_planner() -> list[str]:
    return validate_summary(planner_summary())
