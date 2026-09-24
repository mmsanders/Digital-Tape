#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shlex
import sys
import tempfile

from fixture import (
    all_fixture_digests,
    fixture_bytes,
)
from media import compact_snapshot, inspect_snapshot
from oracle import OracleError, expected_snapshot, validate_case
from planner import (
    CLOSURE_SEEDS,
    EXPECTED_CASESET_SHA256,
    EXPECTED_CLOSURE_CASES,
    EXPECTED_FIRST_CASES,
    EXPECTED_TOTAL_CASES,
    case_counts,
    caseset_digest,
    iter_cases,
    validate_planner,
)
from runner import run_session, validate_handshake
from synthetic_adapter import _observation

ROOT = Path(__file__).resolve().parent
SYNTH = ROOT / "synthetic_adapter.py"


def need(cond, msg):
    if not cond:
        raise AssertionError(msg)


def expect_reject(fn, needle: str | None = None):
    try:
        fn()
    except OracleError as exc:
        if needle is not None:
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


def find_case(**wanted):
    for case in iter_cases():
        ok = True
        for k, v in wanted.items():
            if k.startswith("inj_"):
                if case["injection"].get(k[4:]) != v:
                    ok = False
                    break
            elif case.get(k) != v:
                ok = False
                break
        if ok:
            return case
    raise AssertionError(f"case not found: {wanted}")


def main() -> None:
    errors = validate_planner()
    need(not errors, "planner invalid: " + "; ".join(errors))
    counts = case_counts()
    need(counts["first_interruption_cases"] == EXPECTED_FIRST_CASES, "first count")
    need(counts["two_interruption_closure_cases"] == EXPECTED_CLOSURE_CASES, "closure count")
    need(counts["total_injection_cases"] == EXPECTED_TOTAL_CASES, "total count")
    need(caseset_digest() == EXPECTED_CASESET_SHA256, "case digest")
    print(
        "PASS exhaustive planner",
        EXPECTED_FIRST_CASES,
        EXPECTED_CLOSURE_CASES,
        EXPECTED_TOTAL_CASES,
        EXPECTED_CASESET_SHA256,
    )

    # Frozen fixtures are mountable in their intended states.
    rec = compact_snapshot(fixture_bytes("record_commit", "overwrite"))
    need(inspect_snapshot(rec, requested_side="B")["mount_result"] == "TAPE_OK", "record fixture")
    deg = compact_snapshot(fixture_bytes("reset_b", "degraded_equal"))
    di = inspect_snapshot(deg, requested_side="A")
    need(di["mount_result"] == "TAPE_OK" and di["degraded_b"], "degraded reset fixture")
    stage = compact_snapshot(fixture_bytes("stage_clear", "arm"))
    si = inspect_snapshot(stage, requested_side="B")
    need(si["mount_result"] == "TAPE_OK" and si["stage_row"] == "step5", "stage fixture")
    for seed in CLOSURE_SEEDS:
        ss = compact_snapshot(fixture_bytes("stage_clear", "arm", seed=seed))
        state = inspect_snapshot(ss, requested_side="B")
        need(
            state["mount_result"] == "TAPE_OK" and state["stage_row"] == "step5",
            f"closure fixture {seed}",
        )
    print("PASS frozen fixture/media-oracle controls")

    # Representative positive cases from every family and both durability modes.
    representatives = [
        find_case(scope="first", family="record_commit", variant="overwrite",
                  mode="flush_required", inj_kind="torn_write", inj_write_ordinal=1,
                  inj_landed_bytes=63),
        find_case(scope="first", family="record_commit", variant="overdub",
                  mode="write_through", inj_kind="after_write", inj_write_ordinal=1),
        find_case(scope="first", family="record_commit", variant="splice",
                  mode="flush_required", inj_kind="at_flush", inj_flush_ordinal=1),
        find_case(scope="first", family="reset_b", variant="healthy",
                  mode="write_through", inj_kind="torn_write", inj_write_ordinal=0,
                  inj_landed_bytes=17),
        find_case(scope="first", family="reset_b", variant="degraded_equal",
                  mode="flush_required", inj_kind="after_write", inj_write_ordinal=0),
        find_case(scope="first", family="stage_clear", variant="arm",
                  mode="flush_required", inj_kind="torn_write", inj_write_ordinal=0,
                  inj_landed_bytes=128),
        find_case(scope="first", family="stage_clear", variant="reset_b",
                  mode="write_through", inj_kind="after_write", inj_write_ordinal=0),
        find_case(scope="first", family="stage_clear", variant="respool",
                  mode="write_through", inj_kind="at_flush", inj_flush_ordinal=1),
        find_case(scope="closure", family="stage_clear", variant="arm",
                  seed="mirror_newer_primary_stale", mode="flush_required",
                  inj_kind="torn_partner", inj_landed_bytes=257),
        find_case(scope="closure", family="stage_clear", variant="reset_b",
                  seed="primary_only", mode="write_through",
                  inj_kind="after_partner", inj_landed_bytes=512),
    ]
    for case in representatives:
        validate_case(case, _observation(case))
    print("PASS representative exact-byte crash oracles")

    # Negative: planned injection never actually fired.
    case = representatives[0]
    obs = _observation(case)
    obs["injection_fired"] = False
    expect_reject(lambda: validate_case(case, obs), "skipped")
    print("PASS skipped-injection negative control")

    # Negative: interpret a flush-required after-write boundary as write-through.
    case = find_case(
        scope="first",
        family="record_commit",
        variant="overwrite",
        mode="flush_required",
        inj_kind="after_write",
        inj_write_ordinal=1,
        inj_landed_bytes=512,
    )
    obs = _observation(case)
    wrong_case = copy.deepcopy(case)
    wrong_case["mode"] = "write_through"
    obs["post_snapshot"] = expected_snapshot(wrong_case, obs["pre_snapshot"])
    expect_reject(lambda: validate_case(case, obs), "durable post-crash bytes")
    print("PASS wrong-durability-mode negative control")

    # Negative: substitute a clean final state for a torn-write durable image.
    case = find_case(
        scope="first",
        family="reset_b",
        variant="healthy",
        mode="flush_required",
        inj_kind="torn_write",
        inj_write_ordinal=1,
        inj_landed_bytes=31,
    )
    obs = _observation(case)
    clean_case = copy.deepcopy(case)
    clean_case["mode"] = "write_through"
    clean_case["injection"] = {
        "kind": "after_write",
        "write_ordinal": 1,
        "landed_bytes": 512,
    }
    obs["post_snapshot"] = expected_snapshot(clean_case, obs["pre_snapshot"])
    expect_reject(lambda: validate_case(case, obs), "durable post-crash bytes")
    print("PASS illegal-torn-outcome negative control")

    # Negative: recreate the V7-001 rollback hazard — destroy the current mirror
    # so the stale primary is the only structurally valid superblock.
    case = find_case(
        scope="closure",
        family="stage_clear",
        variant="arm",
        seed="mirror_newer_primary_stale",
        mode="write_through",
        inj_kind="torn_partner",
        inj_landed_bytes=200,
    )
    obs = _observation(case)
    bad = copy.deepcopy(obs["pre_snapshot"])
    bad["mirror_hex"] = (b"\0" * 512).hex()
    obs["post_snapshot"] = bad
    obs["actual_remount_result"] = inspect_snapshot(bad, requested_side="B")["mount_result"]
    expect_reject(lambda: validate_case(case, obs), "durable post-crash bytes")
    need(
        inspect_snapshot(bad, requested_side="B")["mount_result"]
        == "TAPE_ERR_NO_VALID_INDEX",
        "stale-partner hazard did not make Side A unusable",
    )
    print("PASS stale-partner-selection negative control")

    # Negative: omitting one V7-001 seed changes both manifest count and digest.
    manifest = list(iter_cases())
    missing = [
        c for c in manifest
        if not (
            c["scope"] == "closure"
            and c.get("seed") == "mirror_newer_primary_stale"
            and c["variant"] == "arm"
        )
    ]
    need(len(missing) != EXPECTED_TOTAL_CASES, "missing closure state escaped count")
    h = hashlib.sha256()
    for c in missing:
        h.update((json.dumps(c, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii"))
    need(h.hexdigest() != EXPECTED_CASESET_SHA256, "missing closure state escaped digest")
    print("PASS missing-second-interruption-state negative control")

    # Negative: malformed provenance/handshake.
    hello = {
        "format": "WP10-CORE-ADAPTER-1",
        "adapter_kind": "product",
        "caseset_sha256": EXPECTED_CASESET_SHA256,
        "fixture_sha256": all_fixture_digests(),
    }
    need(not validate_handshake(hello), "valid handshake rejected")
    malformed = copy.deepcopy(hello)
    del malformed["fixture_sha256"]
    need(validate_handshake(malformed), "malformed provenance escaped")
    print("PASS malformed-provenance negative control")

    # End-to-end protocol smoke without weakening the production CLI, which has
    # no count override.
    with tempfile.TemporaryDirectory(prefix="wp10-core-self-") as td:
        path = Path(td)
        adapter = synth_proxy(path)
        summary = run_session(
            adapter,
            path / "evidence",
            case_limit=64,
            acceptance=False,
            timeout_s=5.0,
        )
        need(summary["completed_injection_cases"] == 64, "stream smoke incomplete")
    print("PASS streaming protocol smoke")

    print("PASS all WP-10 core crash package self-tests")


if __name__ == "__main__":
    main()
