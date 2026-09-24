#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
from pathlib import Path
import shlex
import sys
import tempfile

from fixture import (
    CHUNK_BLOCKS,
    FUZZ_A_HIGH_WATER,
    LBA_CHUNK_BASE,
    SLOT_BYTES,
    fuzz_initial_b_slots,
    make_index,
    slot_snapshot,
)
from generator import (
    EXPECTED_EDIT_ACTIONS,
    EXPECTED_PLAN_SHA256,
    EXPECTED_RESET_ACTIONS,
    EXPECTED_TOTAL_ACTIONS,
    MASTER_SEED,
    SEQUENCE_COUNT,
    census_and_digest,
    generate_sequence,
    validate_generator_census,
)
from oracle import (
    ADAPTER_FORMAT,
    EVIDENCE_FORMAT,
    EvidenceError,
    choose_live_b,
    derived_free_next,
    validate_acceptance_summary,
    validate_reset_stress,
    validate_sequence,
)
from runner import run_session
from synthetic_adapter import good_sequence_observation, reset_stress_observation

ROOT = Path(__file__).resolve().parent
SYNTH = ROOT / "synthetic_adapter.py"


def need(cond, msg):
    if not cond:
        raise AssertionError(msg)


def expect_reject(fn, needle: str):
    try:
        fn()
    except EvidenceError as exc:
        need(needle in str(exc), f"wrong rejection: {exc}")
        return
    raise AssertionError("negative control was accepted")


def synth_proxy(directory: Path) -> Path:
    proxy = directory / "synthetic-adapter"
    proxy.write_text(
        "#!/bin/sh\nexec "
        + shlex.quote(sys.executable)
        + " "
        + shlex.quote(str(SYNTH))
        + ' "$@"\n',
        encoding="utf-8",
    )
    proxy.chmod(0o700)
    return proxy


def conforming_summary() -> dict:
    return {
        "format": EVIDENCE_FORMAT,
        "generator": {
            "rng_algorithm": "splitmix64-v1",
            "master_seed": f"{MASTER_SEED:016x}",
            "sequence_count": SEQUENCE_COUNT,
            "plan_sha256": EXPECTED_PLAN_SHA256,
        },
        "completed_sequences": SEQUENCE_COUNT,
        "normal_exit": True,
        "failure_reproducer": None,
        "adapter_handshake": {
            "format": ADAPTER_FORMAT,
            "adapter_kind": "product",
        },
        "reset_stress": {"passed": True},
    }


def main() -> None:
    census, digest = census_and_digest()
    errors = validate_generator_census(census)
    need(not errors, "generator coverage invalid: " + "; ".join(errors))
    need(digest == EXPECTED_PLAN_SHA256, "canonical 10000-sequence digest drift")
    need(census["total_actions"] == EXPECTED_TOTAL_ACTIONS, "total action census drift")
    need(census["counts"]["edit"] == EXPECTED_EDIT_ACTIONS, "edit census drift")
    need(census["counts"]["reset"] == EXPECTED_RESET_ACTIONS, "reset census drift")
    print(
        "PASS deterministic 10000-sequence generator",
        digest,
        census["total_actions"],
        census["counts"]["edit"],
        census["counts"]["reset"],
    )

    # The initial B fixture has two entries sharing chunk 0 but occupying adjacent
    # physical-frame intervals. References below a_high_water are expressly legal.
    live = choose_live_b(fuzz_initial_b_slots())["live"]
    need(live["entries"][0]["first_chunk_id"] == 0, "crafted shared reference missing")
    need(live["entries"][1]["first_chunk_id"] == 0, "crafted shared reference missing")
    need(live["entries"][0]["end"] <= live["entries"][1]["base"], "crafted ranges overlap")
    need(derived_free_next(live, a_high_water=FUZZ_A_HIGH_WATER) == 3, "crafted free_next wrong")
    print("PASS legal shared below-high-water reference control")

    plan = generate_sequence(0)
    good = good_sequence_observation(plan)
    validate_sequence(plan, good)
    print("PASS synthetic sequence oracle control")

    bad = copy.deepcopy(good)
    edit_i = next(i for i, a in enumerate(plan["actions"]) if a["kind"] == "edit")
    bad["actions"][edit_i]["write_events"] = [
        {"lba": LBA_CHUNK_BASE + 2 * CHUNK_BLOCKS, "count": 1}
    ]
    expect_reject(lambda: validate_sequence(plan, bad), "below a_high_water")
    print("PASS below-floor allocation/write negative control")

    bad = copy.deepcopy(good)
    bad["actions"][0]["allocation_probe"]["write_events"] = [
        {"lba": LBA_CHUNK_BASE + 4 * CHUNK_BLOCKS, "count": 1}
    ]
    expect_reject(lambda: validate_sequence(plan, bad), "free_next mismatch")
    print("PASS wrong remount free_next negative control")

    overlap = slot_snapshot(make_index(1, 99, [(0, 0, 10), (0, 5, 10)]))
    zero = slot_snapshot(bytes(SLOT_BYTES))
    expect_reject(
        lambda: choose_live_b([overlap, zero]),
        "physical-frame overlap",
    )
    print("PASS interval-overlap negative control")

    stress = reset_stress_observation()
    validate_reset_stress(stress)
    bad_stress = copy.deepcopy(stress)
    bad_stress["write_events"] = [{"lba": LBA_CHUNK_BASE, "count": 1}]
    expect_reject(lambda: validate_reset_stress(bad_stress), "moved/wrote chunk")
    print("PASS reset chunk-movement negative control")

    bad_stress = copy.deepcopy(stress)
    bad_stress["elapsed_ns"] = 1_000_000_000
    expect_reject(lambda: validate_reset_stress(bad_stress), "not < 1 second")
    print("PASS reset timing negative control")

    summary = conforming_summary()
    need(not validate_acceptance_summary(summary), "conforming summary rejected")

    short = copy.deepcopy(summary)
    short["generator"]["sequence_count"] = 9_999
    short["completed_sequences"] = 9_999
    need(validate_acceptance_summary(short), "short campaign escaped")
    print("PASS fewer-than-10000 negative control")

    malformed = copy.deepcopy(summary)
    del malformed["generator"]["master_seed"]
    need(validate_acceptance_summary(malformed), "malformed provenance escaped")
    print("PASS malformed-provenance negative control")

    with tempfile.TemporaryDirectory(prefix="wp07-self-") as td:
        path = Path(td)
        adapter = synth_proxy(path)
        smoke = run_session(
            adapter,
            path / "evidence",
            sequence_count=32,
            acceptance=False,
            response_timeout_s=5.0,
        )
        need(smoke["completed_sequences"] == 32, "streaming smoke incomplete")
        need(smoke["reset_stress"]["passed"] is True, "streaming reset stress missing")
    print("PASS streaming protocol smoke")

    print("PASS all WP-07 allocator/COW package self-tests")


if __name__ == "__main__":
    main()
