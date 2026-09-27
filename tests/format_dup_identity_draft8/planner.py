#!/usr/bin/env python3
"""Verifier-owned DRAFT-8 format/duplicate identity + duplicate WP-12a planner."""
from __future__ import annotations
import hashlib, json

BLOCK_BYTES = 512
DURABILITY_MODES = ("flush_required", "write_through")
OPERATIONS = ("format", "dup")
RAW_SHAPES = (
    "healthy_pair",
    "mirror_only",
    "generation_zero",
    "v2_only",
    "equal_divergent",
    "exhaustion_candidate",
    "exhaustion_equal_divergent",
)
DUP_ROW_COLUMNS = (
    "seek", "set_rate", "render", "service", "status_info_tell",
    "arm", "feed", "commit", "abort", "set_side", "reset_b",
    "promote", "respool", "dup", "unmount",
)
EXPECTED_CRASH_CASES = 57_568
EXPECTED_CONTRACT_CASES = 43
EXPECTED_TOTAL_CASES = 57_611
EXPECTED_CASESET_SHA256 = "c493e77dff948df48d9c67c51ef4b68f0a61d2e02615b2d08760a594e79dc4e3"

def canonical_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

def iter_crash_cases():
    # Every raw scenario has four targeted one-block superblock writes:
    # step-1 partner, step-1 candidate, final mirror, final primary.
    # Each write: before + 511 torn prefixes + after = 513.
    # Each write has a target following-flush fault.
    # 2 modes * (4*513 + 4) = 4112 cases/scenario.
    for operation in OPERATIONS:
        for shape in RAW_SHAPES:
            for mode in DURABILITY_MODES:
                for ordinal in range(4):
                    yield {
                        "scope": "crash", "operation": operation, "shape": shape, "mode": mode,
                        "injection": {"kind": "before_write", "write_ordinal": ordinal, "landed_bytes": 0},
                    }
                    for landed in range(1, BLOCK_BYTES):
                        yield {
                            "scope": "crash", "operation": operation, "shape": shape, "mode": mode,
                            "injection": {"kind": "torn_write", "write_ordinal": ordinal, "landed_bytes": landed},
                        }
                    yield {
                        "scope": "crash", "operation": operation, "shape": shape, "mode": mode,
                        "injection": {"kind": "after_write", "write_ordinal": ordinal, "landed_bytes": BLOCK_BYTES},
                    }
                for ordinal in range(4):
                    yield {
                        "scope": "crash", "operation": operation, "shape": shape, "mode": mode,
                        "injection": {"kind": "at_flush", "flush_ordinal": ordinal},
                    }

def iter_contract_cases():
    for variant in ("format_geometry", "dup_geometry", "dup_capacity"):
        yield {"scope": "contract", "family": "equal_divergent_refusal", "variant": variant}
    for column in DUP_ROW_COLUMNS:
        yield {"scope": "contract", "family": "dup_in_progress_row", "column": column}
    for variant in ("initiate", "continuation"):
        yield {"scope": "contract", "family": "zero_budget", "variant": variant}
    for argument in ("dst_ctx", "new_uuid", "epoch", "dst_nominal_length_s"):
        yield {"scope": "contract", "family": "changed_argument", "argument": argument}
    yield {"scope": "contract", "family": "changed_argument", "argument": "allowed_mutables"}
    yield {"scope": "contract", "family": "destination_failure_playing"}
    for column in DUP_ROW_COLUMNS:
        yield {"scope": "contract", "family": "callback_reentry", "column": column}
    yield {"scope": "contract", "family": "faulted_source", "variant": "dup_call"}
    yield {"scope": "contract", "family": "small_budget_completion", "variant": "dup"}

def iter_cases():
    index = 0
    for case in iter_crash_cases():
        yield {"case_index": index, **case}
        index += 1
    for case in iter_contract_cases():
        yield {"case_index": index, **case}
        index += 1

def caseset_digest():
    h = hashlib.sha256()
    for case in iter_cases():
        h.update((canonical_json(case) + "\n").encode("ascii"))
    return h.hexdigest()

def counts():
    crash = sum(1 for _ in iter_crash_cases())
    contract = sum(1 for _ in iter_contract_cases())
    return {"crash": crash, "contract": contract, "total": crash + contract}

def validate_planner():
    err = []
    c = counts()
    if c["crash"] != EXPECTED_CRASH_CASES:
        err.append("crash count drift")
    if c["contract"] != EXPECTED_CONTRACT_CASES:
        err.append("contract count drift")
    if c["total"] != EXPECTED_TOTAL_CASES:
        err.append("total count drift")
    if caseset_digest() != EXPECTED_CASESET_SHA256:
        err.append("case-set digest drift")
    for op in OPERATIONS:
        for shape in RAW_SHAPES:
            n = sum(1 for x in iter_crash_cases() if x["operation"] == op and x["shape"] == shape)
            if n != 4112:
                err.append(f"{op}/{shape} count {n}")
    if len(DUP_ROW_COLUMNS) != 15:
        err.append("duplicate matrix row is not 15 columns")
    return err
