#!/usr/bin/env python3
"""Verifier-owned exhaustive case planner for the bounded DRAFT-8 WP-10 core tranche."""
from __future__ import annotations

import hashlib
import json

BLOCK_BYTES = 512
DURABILITY_MODES = ("flush_required", "write_through")

FIRST_SCENARIOS = (
    ("record_commit", "overwrite"),
    ("record_commit", "overdub"),
    ("record_commit", "splice"),
    ("reset_b", "healthy"),
    ("reset_b", "degraded_equal"),
    ("stage_clear", "arm"),
    ("stage_clear", "reset_b"),
    ("stage_clear", "respool"),
)

STAGE_CALLERS = ("arm", "reset_b", "respool")
CLOSURE_SEEDS = (
    "primary_only",
    "mirror_only",
    "primary_newer_mirror_stale",
    "mirror_newer_primary_stale",
)

EXPECTED_FIRST_CASES = 16_448
EXPECTED_CLOSURE_CASES = 12_312
EXPECTED_TOTAL_CASES = 28_760
EXPECTED_CASESET_SHA256 = "6c924fd7bdd54b180084fe58cc50ef49d96fc068b968b8022383685ecf235c96"


def canonical_json(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def iter_first_interruption_cases():
    """
    Every bounded first-interruption scenario has exactly two targeted 512-byte
    block writes and two target flushes.

    Per durability mode:
      - before each block write (0 bytes landed);
      - every torn-prefix length 1..511;
      - power cut after a complete block write, before its following flush;
      - fault/power-loss at each target flush.

    That is 2*513 + 2 = 1028 injection cases per durability mode.
    """
    for family, variant in FIRST_SCENARIOS:
        for mode in DURABILITY_MODES:
            for ordinal in range(2):
                yield {
                    "scope": "first",
                    "family": family,
                    "variant": variant,
                    "mode": mode,
                    "injection": {
                        "kind": "before_write",
                        "write_ordinal": ordinal,
                        "landed_bytes": 0,
                    },
                }
                for landed in range(1, BLOCK_BYTES):
                    yield {
                        "scope": "first",
                        "family": family,
                        "variant": variant,
                        "mode": mode,
                        "injection": {
                            "kind": "torn_write",
                            "write_ordinal": ordinal,
                            "landed_bytes": landed,
                        },
                    }
                yield {
                    "scope": "first",
                    "family": family,
                    "variant": variant,
                    "mode": mode,
                    "injection": {
                        "kind": "after_write",
                        "write_ordinal": ordinal,
                        "landed_bytes": BLOCK_BYTES,
                    },
                }

            for ordinal in range(2):
                yield {
                    "scope": "first",
                    "family": family,
                    "variant": variant,
                    "mode": mode,
                    "injection": {
                        "kind": "at_flush",
                        "flush_ordinal": ordinal,
                    },
                }


def iter_two_interruption_closure_cases():
    """
    V7-001 closure for §8 stage clearing.

    Four raw recovery shapes are seeded:
      - primary-only current candidate;
      - mirror-only current candidate;
      - current primary + stale lower-generation mirror;
      - current mirror + stale lower-generation primary.

    Mount repair is deliberately failed before the tested operation so the raw
    one-copy/stale-partner shape reaches the logical update exactly as permitted
    by DRAFT-8. The second interruption targets the *next partner block write*:
    before, every 1..511 byte torn prefix, and after the complete write. Both
    durability modes are run.

    3 callers * 4 seeds * 2 modes * 513 cases = 12312.
    """
    for caller in STAGE_CALLERS:
        for seed in CLOSURE_SEEDS:
            for mode in DURABILITY_MODES:
                for landed in range(0, BLOCK_BYTES + 1):
                    if landed == 0:
                        kind = "before_partner"
                    elif landed == BLOCK_BYTES:
                        kind = "after_partner"
                    else:
                        kind = "torn_partner"
                    yield {
                        "scope": "closure",
                        "family": "stage_clear",
                        "variant": caller,
                        "seed": seed,
                        "mode": mode,
                        "injection": {
                            "kind": kind,
                            "write_ordinal": 0,
                            "landed_bytes": landed,
                        },
                    }


def iter_cases():
    index = 0
    for case in iter_first_interruption_cases():
        yield {"case_index": index, **case}
        index += 1
    for case in iter_two_interruption_closure_cases():
        yield {"case_index": index, **case}
        index += 1


def case_counts() -> dict:
    first = sum(1 for _ in iter_first_interruption_cases())
    closure = sum(1 for _ in iter_two_interruption_closure_cases())
    by_scenario = {}
    by_mode = {}
    for case in iter_cases():
        key = f"{case['family']}:{case['variant']}:{case['scope']}"
        by_scenario[key] = by_scenario.get(key, 0) + 1
        by_mode[case["mode"]] = by_mode.get(case["mode"], 0) + 1
    return {
        "first_interruption_cases": first,
        "two_interruption_closure_cases": closure,
        "total_injection_cases": first + closure,
        "by_scenario": dict(sorted(by_scenario.items())),
        "by_mode": dict(sorted(by_mode.items())),
    }


def caseset_digest() -> str:
    h = hashlib.sha256()
    for case in iter_cases():
        h.update((canonical_json(case) + "\n").encode("ascii"))
    return h.hexdigest()


def validate_planner() -> list[str]:
    errors = []
    counts = case_counts()
    if counts["first_interruption_cases"] != EXPECTED_FIRST_CASES:
        errors.append("first-interruption count drift")
    if counts["two_interruption_closure_cases"] != EXPECTED_CLOSURE_CASES:
        errors.append("closure count drift")
    if counts["total_injection_cases"] != EXPECTED_TOTAL_CASES:
        errors.append("total count drift")
    if caseset_digest() != EXPECTED_CASESET_SHA256:
        errors.append("case-set digest drift")

    # Every first scenario must be exactly 2056 cases:
    # 1028 per durability mode.
    for family, variant in FIRST_SCENARIOS:
        key = f"{family}:{variant}:first"
        if counts["by_scenario"].get(key) != 2056:
            errors.append(f"{key} count drift")

    # Every closure caller has 4 seeds * 2 modes * 513 = 4104.
    for caller in STAGE_CALLERS:
        key = f"stage_clear:{caller}:closure"
        if counts["by_scenario"].get(key) != 4104:
            errors.append(f"{key} count drift")

    if counts["by_mode"].get("flush_required") != EXPECTED_TOTAL_CASES // 2:
        errors.append("flush-required mode count drift")
    if counts["by_mode"].get("write_through") != EXPECTED_TOTAL_CASES // 2:
        errors.append("write-through mode count drift")
    return errors
