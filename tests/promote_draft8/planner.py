#!/usr/bin/env python3
"""Canonical R29-A promote crash/resume + long-operation case planner."""
from __future__ import annotations
import hashlib
import json
from collections import Counter

DURABILITY_MODES = ("flush_required", "write_through")

SCENARIO_PHASES = {
    "fresh_alloc_full": (
        "phase1_copy",
        "step2_a_entries", "step2_a_header",
        "step3_b_entries", "step3_b_header",
        "step4_sb_partner", "step4_sb_candidate",
        "phase2_copy",
        "step7_a_entries", "step7_a_header",
        "step8_b_entries", "step8_b_header",
        "step9_sb_partner", "step9_sb_candidate",
    ),
    "fresh_adopt_full": (
        "step2_a_entries", "step2_a_header",
        "step4_sb_partner", "step4_sb_candidate",
        "phase2_copy",
        "step7_a_entries", "step7_a_header",
        "step8_b_entries", "step8_b_header",
        "step9_sb_partner", "step9_sb_candidate",
    ),
    "first_use_s0": (
        "step2_a_entries", "step2_a_header",
        "step4_sb_partner", "step4_sb_candidate",
        "step5_decline_sb_partner", "step5_decline_sb_candidate",
    ),
}

CLOSURE_PHASES = ("step4", "step5_decline", "step9")
CLOSURE_SEEDS = (
    "primary_only",
    "mirror_only",
    "primary_current_mirror_stale",
    "mirror_current_primary_stale",
)

PROMOTE_ROW_COLUMNS = (
    "seek", "set_rate", "render", "service", "status_info_tell",
    "arm", "feed", "commit", "abort", "set_side", "reset_b",
    "promote", "respool", "dup", "unmount",
)
FAULTED_ROW_COLUMNS = PROMOTE_ROW_COLUMNS

HEADROOM_BRANCHES = {
    "fresh_alloc_run": (4, 2),
    "fresh_alloc_decline": (2, 2),
    "fresh_adopt_run": (3, 2),
    "fresh_adopt_decline": (1, 2),
    "resume5_run": (2, 1),
    "resume5_decline": (0, 1),
    "resume8": (1, 1),
    "resume9": (0, 1),
    "nothing": (0, 0),
}

EXPECTED_CRASH_CASES = 44204
EXPECTED_CONTRACT_CASES = 107
EXPECTED_TOTAL_CASES = 44311
EXPECTED_CASESET_SHA256 = "8732af9434437d0411731b3e4909a2ca9a1278778e5d9c8947642cec7b793442"

EXPECTED_CRASH_BY_SCENARIO_MODE = {
    ("fresh_alloc_full", "flush_required"): 7196,
    ("fresh_alloc_full", "write_through"): 7196,
    ("fresh_adopt_full", "flush_required"): 5654,
    ("fresh_adopt_full", "write_through"): 5654,
    ("first_use_s0", "flush_required"): 3084,
    ("first_use_s0", "write_through"): 3084,
    ("closure", "flush_required"): 6168,
    ("closure", "write_through"): 6168,
}


def _write_outcomes():
    yield "before_write", 0
    for landed in range(1, 512):
        yield "torn_write", landed
    yield "after_write", 512


def _partner_outcomes():
    yield "before_partner", 0
    for landed in range(1, 512):
        yield "torn_partner", landed
    yield "after_partner", 512


def iter_cases():
    idx = 0

    for scenario, phases in SCENARIO_PHASES.items():
        for mode in DURABILITY_MODES:
            for ordinal, phase in enumerate(phases):
                for kind, landed in _write_outcomes():
                    yield {
                        "case_index": idx,
                        "scope": "crash",
                        "scenario": scenario,
                        "mode": mode,
                        "phase": phase,
                        "injection": {
                            "kind": kind,
                            "write_ordinal": ordinal,
                            "landed_bytes": landed,
                        },
                    }
                    idx += 1
                yield {
                    "case_index": idx,
                    "scope": "crash",
                    "scenario": scenario,
                    "mode": mode,
                    "phase": phase,
                    "injection": {"kind": "at_flush", "flush_ordinal": ordinal},
                }
                idx += 1

    for phase in CLOSURE_PHASES:
        for seed in CLOSURE_SEEDS:
            for mode in DURABILITY_MODES:
                for kind, landed in _partner_outcomes():
                    yield {
                        "case_index": idx,
                        "scope": "crash",
                        "scenario": "closure",
                        "phase": phase,
                        "seed": seed,
                        "mode": mode,
                        "injection": {"kind": kind, "landed_bytes": landed},
                    }
                    idx += 1
                yield {
                    "case_index": idx,
                    "scope": "crash",
                    "scenario": "closure",
                    "phase": phase,
                    "seed": seed,
                    "mode": mode,
                    "injection": {"kind": "at_partner_flush"},
                }
                idx += 1

    for variant in ("row1", "row2", "row3", "unmatched", "row1_s0"):
        yield {"case_index": idx, "scope": "contract", "family": "stage_oracle", "variant": variant}
        idx += 1

    for row in range(1, 12):
        yield {"case_index": idx, "scope": "contract", "family": "rerun_row", "row": row}
        idx += 1
    for variant in ("exact_tail_capacity", "repeated_between3_4"):
        yield {"case_index": idx, "scope": "contract", "family": "rerun_special", "variant": variant}
        idx += 1

    for variant in ("full_path", "step5_decline", "resume8", "resume9", "nothing_to_do"):
        yield {"case_index": idx, "scope": "contract", "family": "stored_position", "variant": variant}
        idx += 1

    for branch in HEADROOM_BRANCHES:
        if branch != "nothing":
            yield {"case_index": idx, "scope": "contract", "family": "headroom_exact", "branch": branch}
            idx += 1

    for branch, (sequence_needed, generation_needed) in HEADROOM_BRANCHES.items():
        if sequence_needed:
            yield {
                "case_index": idx, "scope": "contract", "family": "headroom_short",
                "branch": branch, "counter": "sequence",
            }
            idx += 1
        if generation_needed:
            yield {
                "case_index": idx, "scope": "contract", "family": "headroom_short",
                "branch": branch, "counter": "sb_generation",
            }
            idx += 1

    for variant in (
        "fresh_decline_seq_FFFFFFFB",
        "fresh_alloc_seq_FFFFFFFC",
        "resume5_decline_seq_FFFFFFFC",
    ):
        yield {"case_index": idx, "scope": "contract", "family": "headroom_special", "variant": variant}
        idx += 1

    for counter in ("sequence", "sb_generation"):
        for value in ("FFFFFFFE", "FFFFFFFF"):
            yield {
                "case_index": idx, "scope": "contract", "family": "zero_needed_reserved",
                "counter": counter, "value": value,
            }
            idx += 1

    yield {"case_index": idx, "scope": "contract", "family": "shared_sequence"}
    idx += 1
    yield {"case_index": idx, "scope": "contract", "family": "counter_domains"}
    idx += 1

    for variant in ("empty_b", "degraded_b", "capacity_full"):
        yield {"case_index": idx, "scope": "contract", "family": "entry_refusal", "variant": variant}
        idx += 1

    for column in PROMOTE_ROW_COLUMNS:
        yield {
            "case_index": idx, "scope": "contract",
            "family": "promote_in_progress_row", "column": column,
        }
        idx += 1

    for variant in ("initiate", "continuation"):
        yield {"case_index": idx, "scope": "contract", "family": "zero_budget", "variant": variant}
        idx += 1

    yield {"case_index": idx, "scope": "contract", "family": "allowed_mutables"}
    idx += 1
    yield {"case_index": idx, "scope": "contract", "family": "own_device_failure"}
    idx += 1

    for column in FAULTED_ROW_COLUMNS:
        yield {"case_index": idx, "scope": "contract", "family": "faulted_row", "column": column}
        idx += 1

    for column in PROMOTE_ROW_COLUMNS:
        yield {"case_index": idx, "scope": "contract", "family": "callback_reentry", "column": column}
        idx += 1

    yield {"case_index": idx, "scope": "contract", "family": "small_budget_completion"}


def canonical_case_bytes(case):
    return json.dumps(case, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"


def caseset_digest():
    h = hashlib.sha256()
    for case in iter_cases():
        h.update(canonical_case_bytes(case))
    return h.hexdigest()


def counts():
    result = Counter()
    by_scenario_mode = Counter()
    contract_families = Counter()
    last = -1
    for case in iter_cases():
        last = case["case_index"]
        result[case["scope"]] += 1
        if case["scope"] == "crash":
            by_scenario_mode[(case["scenario"], case["mode"])] += 1
        else:
            contract_families[case["family"]] += 1
    result["total"] = last + 1
    return {
        "crash": result["crash"],
        "contract": result["contract"],
        "total": result["total"],
        "crash_by_scenario_mode": dict(by_scenario_mode),
        "contract_families": dict(contract_families),
    }


def validate_planner():
    c = counts()
    errors = []
    if c["crash"] != EXPECTED_CRASH_CASES:
        errors.append(f"crash census {c['crash']}")
    if c["contract"] != EXPECTED_CONTRACT_CASES:
        errors.append(f"contract census {c['contract']}")
    if c["total"] != EXPECTED_TOTAL_CASES:
        errors.append(f"total census {c['total']}")
    if c["crash_by_scenario_mode"] != EXPECTED_CRASH_BY_SCENARIO_MODE:
        errors.append("scenario/mode census")
    digest = caseset_digest()
    if digest != EXPECTED_CASESET_SHA256:
        errors.append(f"digest {digest}")
    return errors


if __name__ == "__main__":
    problems = validate_planner()
    if problems:
        raise SystemExit("; ".join(problems))
    print(counts())
    print(EXPECTED_CASESET_SHA256)
