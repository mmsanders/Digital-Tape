#!/usr/bin/env python3
from __future__ import annotations

import struct

from fixture import (
    BASE, DECLINE_AUDIO_SHA256, LIVE_A_SHA256, V3_AUDIO_SHA256,
    clean_cases, compact, empty_at, functional_fixture_errors,
    source_block_known, target_before_block,
)
from oracle import (
    COLUMNS, FAULTED_ALLOWED, RESPOOL_ALLOWED, OracleError, case_id,
    expected_metadata_post, expected_target_lba, transaction_media,
    validate_clean_case, validate_crash_observation, validate_longop_contract,
    validate_zero_needed_empty,
)
from planner import (
    EXPECTED_CASESET_SHA256, EXPECTED_TOTAL_CASES, iter_cases,
    planner_summary, validate_summary,
)

def need(cond, msg):
    if not cond:
        raise AssertionError(msg)

def expect_reject(fn, needle=None):
    try:
        fn()
    except OracleError as exc:
        if needle is not None:
            need(needle in str(exc), f"wrong rejection: {exc}")
        return
    raise AssertionError("negative control was accepted")

def _matches(c, s):
    if c["fixture"] != s["fixture"] or c["pass"] != s["pass"]:
        return False
    if c["mode"] != s["mode"] or c["target"] != s["target"]:
        return False
    inj = c["injection"]
    for key in ("kind", "write_ordinal", "flush_ordinal", "landed_bytes"):
        if key in s and inj.get(key) != s[key]:
            return False
    return True

def collect_cases(specs):
    """One planner traversal obtains all representative/negative-control cases."""
    found = [None] * len(specs)
    remaining = len(specs)
    for c in iter_cases():
        for i, s in enumerate(specs):
            if found[i] is None and _matches(c, s):
                found[i] = c
                remaining -= 1
        if remaining == 0:
            break
    need(remaining == 0, "representative planner case missing")
    return found

def _write_durable(case, before: bytes, intended: bytes) -> bytes:
    inj = case["injection"]
    if inj["kind"] == "before_write":
        return before
    if inj["kind"] == "torn_write":
        n = inj["landed_bytes"]
        return intended[:n] + before[n:]
    if inj["kind"] == "after_write":
        return intended if case["mode"] == "write_through" else before
    raise AssertionError("not a write case")

def _metadata_target_blocks(case, pre, committed):
    if case["fixture"] == "v3_003" and case["pass"] == "pass1":
        slot = 3
    elif case["fixture"] == "v3_003" and case["pass"] == "pass2":
        slot = 2
    elif case["fixture"] == "no_lower_run" and case["pass"] == "pass1":
        slot = 3
    else:
        raise AssertionError("unknown pass")
    block_index = 1 if case["target"] == "entry_block" else 0
    lo = block_index * BASE.BLOCK
    hi = lo + BASE.BLOCK
    return pre.slots[slot][lo:hi], committed.slots[slot][lo:hi]

def _remount_info(post):
    sbx = BASE.select_sb(post)
    live = BASE.live_slot(post, 1)
    need(live is not None, "synthetic post has no live B")
    entries = BASE.parse_entries(post.slots[live])
    total_chunks = struct.unpack_from("<I", sbx, 52)[0]
    free_next = BASE.free_next(post)
    return {
        "uuid_hex": sbx[20:36].hex(),
        "total_chunks": total_chunks,
        "free_chunks": total_chunks - free_next,
        "entry_count": len(entries),
        "total_frames": sum(e[2] for e in entries),
        "side_b_valid": True,
    }

def synthetic_crash(case):
    pre, committed = transaction_media(case)
    post = expected_metadata_post(case)

    lba = expected_target_lba(case)
    target_event = {"target": case["target"]}
    target_block = None
    if lba is None:
        target_event.update({"op": "flush"})
    else:
        target_event.update({"op": "write", "lba": lba, "count": 1})
        if case["target"] == "chunk_copy":
            before = target_before_block(case)
            whole, prefix = source_block_known(case)
            intended = whole if whole is not None else prefix + bytes([0xD7]) * (BASE.BLOCK - len(prefix))
        else:
            before, intended = _metadata_target_blocks(case, pre, committed)
        durable = _write_durable(case, before, intended)
        target_block = {
            "before_hex": before.hex(),
            "intended_hex": intended.hex(),
            "durable_hex": durable.hex(),
        }

    hashes = {"live_a": LIVE_A_SHA256}
    layout = __import__("fixture").layout_name(case["fixture"], post)
    if case["fixture"] == "v3_003":
        if case["pass"] == "pass1":
            hashes["source_10_12"] = V3_AUDIO_SHA256
            if layout == "post_pass1":
                hashes["copy_12_14"] = V3_AUDIO_SHA256
        else:
            hashes["pass1_12_14"] = V3_AUDIO_SHA256
            if layout == "post_pass2":
                hashes["copy_10_12"] = V3_AUDIO_SHA256
    else:
        hashes["source_fragments"] = DECLINE_AUDIO_SHA256
        if layout == "post_pass1":
            hashes["copy_10_frames"] = DECLINE_AUDIO_SHA256

    obs = {
        "format": "WP10-RESPOOL-OBSERVATION-1",
        "case_id": case_id(case),
        "injection_fired": True,
        "fresh_remount_from_durable_only": True,
        "actual_remount_result": "TAPE_OK",
        "remount_side": "B",
        "remount_info": _remount_info(post),
        "pre_snapshot": compact(pre),
        "post_snapshot": compact(post),
        "target_event": target_event,
        "live_a_sha256": LIVE_A_SHA256,
        "raw_region_sha256": hashes,
    }
    if target_block is not None:
        obs["target_block"] = target_block
    return obs

def row_observation(*, faulted=False):
    allowed = FAULTED_ALLOWED if faulted else RESPOOL_ALLOWED
    row = []
    token = "op-72"
    for name in COLUMNS:
        if faulted:
            result = "TAPE_OK" if name in allowed else "TAPE_ERR_FAULTED"
        else:
            result = "TAPE_OK" if name in allowed else "TAPE_ERR_BUSY"
        cell = {
            "call": name,
            "result": result,
            "block_ops": 0,
            "operation_token_before": token,
            "operation_token_after": token,
        }
        if not faulted and name == "respool":
            cell.update({"progress_before": 4, "progress_after": 5})
        row.append(cell)
    return row

def longop_observation():
    return {
        "in_progress_row": row_observation(),
        "faulted_row": row_observation(faulted=True),
        "small_budget_calls": [
            {"result": "TAPE_OK", "block_budget": 1, "more_work": True,
             "operation_token": "op-small", "progress_before": 0, "progress_after": 1},
            {"result": "TAPE_OK", "block_budget": 1, "more_work": True,
             "operation_token": "op-small", "progress_before": 1, "progress_after": 2},
            {"result": "TAPE_OK", "block_budget": 2, "more_work": False,
             "operation_token": "op-small", "progress_before": 2, "progress_after": 4},
        ],
        "zero_budget": [
            {"phase": "initiation", "block_budget": 0, "result": "TAPE_ERR_INVALID_ARG",
             "block_ops": 0, "state_before": "idle", "state_after": "idle"},
            {"phase": "continuation", "block_budget": 0, "result": "TAPE_ERR_INVALID_ARG",
             "block_ops": 0, "state_before": "respool:2", "state_after": "respool:2"},
        ],
        "busy_then_continue": {
            "busy": {
                "result": "TAPE_ERR_BUSY", "block_ops": 0,
                "operation_token_before": "op-busy", "operation_token_after": "op-busy",
            },
            "continuation": {
                "result": "TAPE_OK", "operation_token": "op-busy",
                "progress_before": 6, "progress_after": 7,
            },
        },
        "own_device_failures": [
            {"failure": "write", "result": "TAPE_ERR_IO", "more_work": False, "state_after": "FAULTED"},
            {"failure": "flush", "result": "TAPE_ERR_IO", "more_work": False, "state_after": "FAULTED"},
        ],
        "faulted_over_armed": {
            "armed": True, "frames_owed": 3, "respool_result": "TAPE_ERR_FAULTED", "block_ops": 0,
        },
        "faulted_ring_drain": {
            "rendered_frames": [4, 2, 1, 0], "underrun": True, "abort_result": "TAPE_OK",
        },
        "stable_continuation_args": [],
        "progress_callback_reentry_applicable": False,
    }

def main():
    summary = planner_summary()
    errors = validate_summary(summary)
    need(not errors, "planner: " + "; ".join(errors))
    need(summary["total"] == EXPECTED_TOTAL_CASES, "planner total")
    need(summary["sha256"] == EXPECTED_CASESET_SHA256, "planner digest")
    print("PASS planner", EXPECTED_TOTAL_CASES, EXPECTED_CASESET_SHA256)

    errors = functional_fixture_errors()
    need(not errors, "fixtures: " + "; ".join(errors))
    print("PASS verifier-owned fixture premises and pinned base oracle")

    for c in clean_cases():
        post, events, calls = BASE.synth_observation(c)
        validate_clean_case(c, post, events, calls)
    print("PASS clean WP-12 functional/headroom shapes")

    for seq, generation in ((0xFFFFFFFD, 7), (0xFFFFFFFF, 0xFFFFFFFF)):
        pre = empty_at(seq, generation)
        validate_zero_needed_empty(
            pre, pre, [],
            {"result": "TAPE_OK", "more_work": False, "block_budget": 1},
        )
    print("PASS zero-needed empty counter boundaries")

    specs = [
        {"fixture":"v3_003","pass":"pass1","mode":"flush_required","target":"chunk_copy",
         "kind":"torn_write","write_ordinal":700,"landed_bytes":257},
        {"fixture":"v3_003","pass":"pass1","mode":"write_through","target":"chunk_copy",
         "kind":"torn_write","write_ordinal":123,"landed_bytes":31},
        {"fixture":"v3_003","pass":"pass1","mode":"write_through","target":"entry_block",
         "kind":"torn_write","write_ordinal":0,"landed_bytes":129},
        {"fixture":"v3_003","pass":"pass1","mode":"write_through","target":"header_block",
         "kind":"after_write","write_ordinal":1,"landed_bytes":512},
        {"fixture":"v3_003","pass":"pass2","mode":"flush_required","target":"chunk_copy",
         "kind":"torn_write","write_ordinal":0,"landed_bytes":17},
        {"fixture":"v3_003","pass":"pass2","mode":"write_through","target":"header_block_flush",
         "kind":"at_flush","flush_ordinal":2},
        {"fixture":"no_lower_run","pass":"pass1","mode":"flush_required","target":"chunk_copy",
         "kind":"torn_write","write_ordinal":0,"landed_bytes":39},
        {"fixture":"no_lower_run","pass":"pass1","mode":"write_through","target":"header_block",
         "kind":"after_write","write_ordinal":1,"landed_bytes":512},
    ]
    representatives = collect_cases(specs)
    for case in representatives:
        validate_crash_observation(case, synthetic_crash(case))
    print("PASS representative exact torn/raw-layout/free_next oracles")

    longop = longop_observation()
    validate_longop_contract(longop)
    print("PASS complete respool/Faulted state rows and long-operation contract")

    # Negative: Side-A raw bytes change.
    case = representatives[0]
    obs = synthetic_crash(case)
    obs["raw_region_sha256"]["live_a"] = "0" * 64
    expect_reject(lambda: validate_crash_observation(case, obs), "Side A")
    print("PASS overlap/live-set corruption negative control")

    # Negative: exact torn destination prefix is wrong by one byte.
    case = representatives[1]
    obs = synthetic_crash(case)
    bad = bytearray.fromhex(obs["target_block"]["durable_hex"])
    bad[0] ^= 0x01
    obs["target_block"]["durable_hex"] = bytes(bad).hex()
    expect_reject(lambda: validate_crash_observation(case, obs), "durable bytes")
    print("PASS torn-copy durable-prefix negative control")

    # Negative: freshly remounted public allocator view reports the wrong frontier.
    case = representatives[4]
    obs = synthetic_crash(case)
    obs["remount_info"]["free_chunks"] -= 1
    expect_reject(lambda: validate_crash_observation(case, obs), "free_next")
    print("PASS remount free_next negative control")

    # Negative: substitute pre-pass metadata where a write-through header committed.
    case = representatives[3]
    obs = synthetic_crash(case)
    pre, _ = transaction_media(case)
    obs["post_snapshot"] = compact(pre)
    expect_reject(lambda: validate_crash_observation(case, obs), "durable metadata")
    print("PASS stale/illegal layout-selection negative control")

    # Negative: pass 2 writes to the wrong physical destination.
    case = representatives[4]
    obs = synthetic_crash(case)
    obs["target_event"]["lba"] += 2 * BASE.BLOCKS_PER_CHUNK
    expect_reject(lambda: validate_crash_observation(case, obs), "destination")
    print("PASS wrong pass-2 destination negative control")

    bad = longop_observation()
    seek = next(c for c in bad["in_progress_row"] if c["call"] == "seek")
    seek["operation_token_after"] = "restarted"
    expect_reject(lambda: validate_longop_contract(bad), "terminated/restarted")
    print("PASS false-BUSY-termination negative control")

    bad = longop_observation()
    service = next(c for c in bad["faulted_row"] if c["call"] == "service")
    service["result"] = "TAPE_OK"
    service["block_ops"] = 1
    expect_reject(lambda: validate_longop_contract(bad), "leaked")
    print("PASS FAULTED-row leakage negative control")

if __name__ == "__main__":
    main()
