#!/usr/bin/env python3
from __future__ import annotations
import copy, struct, zlib

from fixture import (
    BLOCK, FRESH_FORMAT_UUID, FRESH_DUP_UUID,
    initial_snapshot, raw_shapes, target_writes,
)
from media import inspect_snapshot, identity_tuple
from oracle import (
    VerificationError, expected_observation, expected_snapshot,
    validate_case, failure_reproducer,
)
from planner import (
    EXPECTED_CASESET_SHA256, EXPECTED_CONTRACT_CASES, EXPECTED_CRASH_CASES,
    EXPECTED_TOTAL_CASES, caseset_digest, counts, iter_cases, validate_planner,
)


def need(c, m):
    if not c:
        raise AssertionError(m)


def reject(fn, label):
    try:
        fn()
    except VerificationError:
        return
    raise AssertionError("negative control escaped: " + label)


def find(**want):
    for c in iter_cases():
        ok = True
        for k, v in want.items():
            if k.startswith("inj_"):
                if c.get("injection", {}).get(k[4:]) != v:
                    ok = False
                    break
            elif c.get(k) != v:
                ok = False
                break
        if ok:
            return c
    raise AssertionError("case not found " + repr(want))


def mutate_geometry(snap, *, nominal=None, total_chunks=None, version=None, state=None):
    out = copy.deepcopy(snap)
    for key in ("primary_hex", "mirror_hex"):
        raw = bytearray.fromhex(out[key])
        if nominal is not None:
            struct.pack_into("<I", raw, 48, nominal)
        if total_chunks is not None:
            struct.pack_into("<I", raw, 52, total_chunks)
        if version is not None:
            struct.pack_into("<H", raw, 8, version)
        if state is not None:
            raw[16] = state
        struct.pack_into("<I", raw, 508, zlib.crc32(raw[:508]) & 0xFFFFFFFF)
        out[key] = raw.hex()
    return out


def main():
    need(not validate_planner(), "planner validation failed")
    c = counts()
    need(
        c == {
            "crash": EXPECTED_CRASH_CASES,
            "contract": EXPECTED_CONTRACT_CASES,
            "total": EXPECTED_TOTAL_CASES,
        },
        "counts",
    )
    need(caseset_digest() == EXPECTED_CASESET_SHA256, "digest")
    print("PASS exhaustive planner", c, EXPECTED_CASESET_SHA256)

    expected_initial = {
        "healthy_pair": "TAPE_OK",
        "mirror_only": "TAPE_OK",
        "generation_zero": "TAPE_OK",
        "v2_only": "TAPE_ERR_VERSION",
        "equal_divergent": "TAPE_ERR_INCONSISTENT",
        "exhaustion_candidate": "TAPE_OK",
        "exhaustion_equal_divergent": "TAPE_ERR_INCONSISTENT",
    }
    for name, result in expected_initial.items():
        got = inspect_snapshot(initial_snapshot(name))["mount_result"]
        need(got == result, f"{name} initial classification {got}")
    print("PASS mandatory raw destination fixture classifications")

    seed = initial_snapshot("healthy_pair")
    need(inspect_snapshot(seed)["mount_result"] == "TAPE_OK", "9s/4 seed")
    need(inspect_snapshot(mutate_geometry(seed, nominal=60))["mount_result"] == "TAPE_ERR_GEOMETRY", "60s/4 escaped")
    need(inspect_snapshot(mutate_geometry(seed, nominal=100000))["mount_result"] == "TAPE_ERR_GEOMETRY", "frame cap escaped")
    need(inspect_snapshot(mutate_geometry(seed, total_chunks=5))["mount_result"] == "TAPE_ERR_GEOMETRY", "stored/derived mismatch escaped")
    short = copy.deepcopy(seed)
    short["block_count"] -= 1
    need(inspect_snapshot(short)["mount_result"] == "TAPE_ERR_GEOMETRY", "short device escaped")
    precedence = copy.deepcopy(seed)
    precedence["block_count"] = 1
    precedence["primary_hex"] = "00" * 512
    precedence["mirror_hex"] = "00" * 512
    got = inspect_snapshot(precedence)
    need(got["mount_result"] == "TAPE_ERR_GEOMETRY" and got.get("phase") == 0, "phase-0 precedence")
    need(inspect_snapshot(mutate_geometry(seed, nominal=60, version=2))["mount_result"] == "TAPE_ERR_VERSION", "version precedence")
    need(inspect_snapshot(mutate_geometry(seed, nominal=60, state=1))["mount_result"] == "TAPE_ERR_INCOMPLETE", "state precedence")
    print("PASS truthful 9s/4 geometry and phase-0/admission red controls")

    shapes = raw_shapes()
    for op in ("format", "dup"):
        for name, s in shapes.items():
            tw = target_writes(op, name)
            need(tw[0]["copy"] == s.partner_copy, "partner not first")
            need(tw[1]["copy"] != s.partner_copy, "candidate/other not last")
            need(tw[2]["copy"] == "mirror" and tw[3]["copy"] == "primary", "identity order")
    for name in ("healthy_pair", "generation_zero"):
        raw = target_writes("format", name)[0]["bytes"]
        need(struct.unpack_from("<I", raw, 12)[0] == 2 and raw[16] == 1, f"{name} step1")
    for name in ("exhaustion_candidate", "exhaustion_equal_divergent"):
        need(target_writes("dup", name)[0]["bytes"] == bytes(BLOCK), "fallback not zero")
    print("PASS step-1 partner ordering, generation-2 path, and fallback zeroing")

    reps = [
        find(scope="crash", operation="format", shape="healthy_pair", mode="flush_required",
             inj_kind="before_write", inj_write_ordinal=0),
        find(scope="crash", operation="format", shape="healthy_pair", mode="write_through",
             inj_kind="after_write", inj_write_ordinal=0, inj_landed_bytes=512),
        find(scope="crash", operation="dup", shape="mirror_only", mode="flush_required",
             inj_kind="torn_write", inj_write_ordinal=0, inj_landed_bytes=13),
        find(scope="crash", operation="dup", shape="equal_divergent", mode="flush_required",
             inj_kind="before_write", inj_write_ordinal=0),
        find(scope="crash", operation="dup", shape="equal_divergent", mode="write_through",
             inj_kind="torn_write", inj_write_ordinal=0, inj_landed_bytes=13),
        find(scope="crash", operation="dup", shape="equal_divergent", mode="write_through",
             inj_kind="after_write", inj_write_ordinal=0, inj_landed_bytes=512),
        find(scope="crash", operation="format", shape="exhaustion_candidate", mode="write_through",
             inj_kind="torn_write", inj_write_ordinal=0, inj_landed_bytes=17),
        find(scope="crash", operation="format", shape="exhaustion_equal_divergent", mode="write_through",
             inj_kind="before_write", inj_write_ordinal=0),
        find(scope="crash", operation="format", shape="exhaustion_equal_divergent", mode="write_through",
             inj_kind="torn_write", inj_write_ordinal=0, inj_landed_bytes=1),
        find(scope="crash", operation="format", shape="exhaustion_equal_divergent", mode="write_through",
             inj_kind="after_write", inj_write_ordinal=1, inj_landed_bytes=512),
        find(scope="crash", operation="dup", shape="healthy_pair", mode="write_through",
             inj_kind="after_write", inj_write_ordinal=2, inj_landed_bytes=512),
        find(scope="crash", operation="dup", shape="healthy_pair", mode="write_through",
             inj_kind="torn_write", inj_write_ordinal=3, inj_landed_bytes=23),
        find(scope="crash", operation="format", shape="exhaustion_candidate", mode="write_through",
             inj_kind="after_write", inj_write_ordinal=2, inj_landed_bytes=512),
    ]
    outcomes = []
    for case in reps:
        obs = expected_observation(case)
        validate_case(case, obs)
        outcomes.append((case["shape"], case["injection"]["kind"], obs["actual_remount_result"]))
    need(outcomes[0][2] == "TAPE_OK", "old healthy before write")
    need(outcomes[1][2] == "TAPE_ERR_INCOMPLETE", "durable WIP")
    need(outcomes[3][2] == "TAPE_ERR_INCONSISTENT", "eqdiv before")
    need(outcomes[4][2] == "TAPE_OK", "eqdiv torn first surviving primary")
    need(outcomes[5][2] == "TAPE_ERR_INCOMPLETE", "eqdiv durable template")
    need(outcomes[7][2] == "TAPE_ERR_INCONSISTENT", "exhausted eqdiv before zero")
    need(outcomes[8][2] == "TAPE_OK", "exhausted eqdiv first zero torn")
    need(outcomes[9][2] == "TAPE_ERR_BAD_MAGIC", "exhausted eqdiv both zeros")
    need(outcomes[10][2] == "TAPE_ERR_INCOMPLETE", "headroom final mirror vs WIP primary")
    need(outcomes[11][2] == "TAPE_OK", "torn final primary selects final mirror")
    need(outcomes[12][2] == "TAPE_OK", "fallback final mirror sole valid")
    print("PASS representative exact durable-byte crash/remount oracles")

    for op, uuidhex in (("format", FRESH_FORMAT_UUID.hex()), ("dup", FRESH_DUP_UUID.hex())):
        case = find(
            scope="crash", operation=op, shape="healthy_pair", mode="write_through",
            inj_kind="after_write", inj_write_ordinal=3, inj_landed_bytes=512,
        )
        ident = identity_tuple(expected_snapshot(case))
        need(ident == (uuidhex, 1, 1, 2), f"{op} identity boundary {ident}")
    print("PASS final identity generation/A0/B0 boundary")

    contract = 0
    for case in iter_cases():
        if case["scope"] == "contract":
            validate_case(case, expected_observation(case))
            contract += 1
    need(contract == EXPECTED_CONTRACT_CASES, "contract census")
    print("PASS duplicate WP-12a raw-fact contract census", contract)

    # Crash-oracle negative controls.
    case = reps[1]
    obs = expected_observation(case)
    obs["injection_fired"] = False
    reject(lambda: validate_case(case, obs), "skipped injection")

    obs = expected_observation(case)
    bad = copy.deepcopy(obs["target_baseline"])
    bad[0], bad[1] = bad[1], bad[0]
    obs["target_baseline"] = bad
    reject(lambda: validate_case(case, obs), "reversed partner order")

    case = find(
        scope="crash", operation="format", shape="healthy_pair", mode="flush_required",
        inj_kind="after_write", inj_write_ordinal=0, inj_landed_bytes=512,
    )
    obs = expected_observation(case)
    other = copy.deepcopy(case)
    other["mode"] = "write_through"
    obs["post_snapshot"] = expected_snapshot(other)
    obs["actual_remount_result"] = inspect_snapshot(obs["post_snapshot"])["mount_result"]
    reject(lambda: validate_case(case, obs), "wrong durability mode")

    case = find(
        scope="crash", operation="dup", shape="healthy_pair", mode="write_through",
        inj_kind="after_write", inj_write_ordinal=3, inj_landed_bytes=512,
    )
    obs = expected_observation(case)
    obs["post_snapshot"]["a0_head_hex"] = initial_snapshot("healthy_pair")["a0_head_hex"]
    obs["actual_remount_result"] = inspect_snapshot(obs["post_snapshot"])["mount_result"]
    reject(lambda: validate_case(case, obs), "identity sequence drift")

    # Binding-boundary negative controls: raw mismatches must be detected by
    # Verification rather than accepted through product-side verdict booleans.
    case = find(scope="contract", family="dup_in_progress_row", column="seek")
    obs = expected_observation(case)
    obs["after_probe"]["progress_blocks"] += 1
    reject(lambda: validate_case(case, obs), "BUSY advanced raw progress")

    case = find(scope="contract", family="dup_in_progress_row", column="seek")
    obs = expected_observation(case)
    obs["operation_running_after"] = True
    reject(lambda: validate_case(case, obs), "derived adapter verdict field")

    case = find(scope="contract", family="callback_reentry", column="dup")
    obs = expected_observation(case)
    obs["callback_after"]["callback_entry_count"] = 2
    obs["callback_after"]["callback_max_depth"] = 2
    reject(lambda: validate_case(case, obs), "callback recursion raw counters")

    case = find(scope="contract", family="destination_failure_playing")
    obs = expected_observation(case)
    obs["source_after"]["rate_q16_16"] += 1
    reject(lambda: validate_case(case, obs), "destination failure changed raw rate")

    case = find(scope="contract", family="destination_failure_playing")
    obs = expected_observation(case)
    obs["source_after"]["ring"]["content_sha256"] = "22" * 32
    reject(lambda: validate_case(case, obs), "destination failure changed raw ring digest")

    case = find(scope="contract", family="destination_failure_playing")
    obs = expected_observation(case)
    obs["render_after_failure"]["output_hex"] = "00000000"
    reject(lambda: validate_case(case, obs), "destination failure stopped audible output")

    case = find(scope="contract", family="zero_budget", variant="continuation")
    obs = expected_observation(case)
    obs["after"]["progress_blocks"] += 1
    reject(lambda: validate_case(case, obs), "zero budget advanced raw progress")

    case = find(scope="contract", family="changed_argument", argument="new_uuid")
    obs = expected_observation(case)
    obs["call_args"]["epoch"] += 1
    reject(lambda: validate_case(case, obs), "multiple fixed continuation args changed")

    case = find(scope="contract", family="small_budget_completion", variant="dup")
    obs = expected_observation(case)
    obs["call_sequence"][1]["chunk_write_lbas_after"] = [2048, 2048]
    obs["call_sequence"][2]["chunk_write_lbas_before"] = [2048, 2048]
    reject(lambda: validate_case(case, obs), "constant-token repeated-copy restart")

    case = reps[5]
    obs = expected_observation(case)
    rep = failure_reproducer(case, obs, "synthetic")
    for k in (
        "pre_primary", "pre_mirror", "post_primary", "post_mirror",
        "actual_remount_result", "raw_oracle_result",
    ):
        need(rep.get(k) is not None, "reproducer missing " + k)

    print("PASS raw-observation boundary negative controls and crash reproducer")
    print("PASS all R29 format/duplicate identity + duplicate long-op self-tests")


if __name__ == "__main__":
    main()
