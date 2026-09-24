#!/usr/bin/env python3
"""Independent raw-media and state-machine oracle for issue #72."""
from __future__ import annotations

import struct

from fixture import (
    BASE, DECLINE_AUDIO_SHA256, LIVE_A_SHA256, V3_AUDIO_SHA256,
    decline_case, from_compact, layout_name, source_block_known,
    target_before_block, v3_case,
)

COLUMNS = (
    "seek", "set_rate", "render", "service", "status_info_tell",
    "arm", "feed", "commit", "abort", "set_side", "reset_b",
    "promote", "respool", "dup", "unmount",
)
RESPOOL_ALLOWED = {"render", "service", "status_info_tell", "respool"}
RESPOOL_BUSY = set(COLUMNS) - RESPOOL_ALLOWED
FAULTED_ALLOWED = {"render", "status_info_tell", "abort", "unmount"}
FAULTED_F = set(COLUMNS) - FAULTED_ALLOWED

# Frozen API facts, not omissions: tape_respool(t, block_budget, more_work)
# has no stable operation-specific continuation argument, and no progress callback.
RESPOOL_STABLE_CONTINUATION_ARGS: tuple[str, ...] = ()
RESPOOL_PROGRESS_CALLBACK_REENTRY_APPLICABLE = False

class OracleError(AssertionError):
    pass

def need(cond, msg):
    if not cond:
        raise OracleError(msg)

def case_id(case: dict) -> str:
    return f"{case['case_index']}:{case['fixture']}:{case['pass']}:{case['mode']}:{case['target']}"

def transaction_media(case: dict):
    if case["fixture"] == "v3_003":
        c = v3_case()
        p1, p2 = c.passes
        after1 = BASE.with_slot(c.pre, p1.slot, BASE.idx(1, list(p1.entries), p1.sequence))
        after2 = BASE.with_slot(after1, p2.slot, BASE.idx(1, list(p2.entries), p2.sequence))
        if case["pass"] == "pass1":
            return c.pre, after1
        if case["pass"] == "pass2":
            return after1, after2
    if case["fixture"] == "no_lower_run" and case["pass"] == "pass1":
        c = decline_case()
        p = c.passes[0]
        return c.pre, BASE.with_slot(c.pre, p.slot, BASE.idx(1, list(p.entries), p.sequence))
    raise OracleError("unknown crash transaction")

def _pass_geometry(case: dict):
    if case["fixture"] == "v3_003" and case["pass"] == "pass1":
        return 12, 14, 3
    if case["fixture"] == "v3_003" and case["pass"] == "pass2":
        return 10, 12, 2
    if case["fixture"] == "no_lower_run" and case["pass"] == "pass1":
        return 10, 11, 3
    raise OracleError("unknown pass geometry")

def expected_target_lba(case: dict) -> int | None:
    start, _, slot = _pass_geometry(case)
    target = case["target"]
    if target == "chunk_copy":
        return BASE.LBA_CHUNK_BASE + start * BASE.BLOCKS_PER_CHUNK + case["injection"]["write_ordinal"]
    if target == "entry_block":
        return (BASE.LBA_A0, BASE.LBA_A1, BASE.LBA_B0, BASE.LBA_B1)[slot] + 1
    if target == "header_block":
        return (BASE.LBA_A0, BASE.LBA_A1, BASE.LBA_B0, BASE.LBA_B1)[slot]
    return None

def _assert_disjoint_target(case: dict):
    if case["target"] != "chunk_copy":
        return
    start, end, _ = _pass_geometry(case)
    ordinal = case["injection"]["write_ordinal"]
    chunk = start + ordinal // BASE.BLOCKS_PER_CHUNK
    need(start <= chunk < end, "chunk-copy target outside destination")
    need(chunk >= 10, "chunk-copy target below H floor")
    if case["fixture"] == "v3_003" and case["pass"] == "pass1":
        need(chunk not in {10, 11}, "pass1 overlap with live B")
    elif case["fixture"] == "v3_003" and case["pass"] == "pass2":
        need(chunk not in {12, 13}, "pass2 overlap with sole live pass1 copy")
    elif case["fixture"] == "no_lower_run":
        need(chunk not in set(range(11, 21)), "decline pass overlap with live B")

def _with_slot_block(m, slot: int, block_index: int, data: bytes):
    need(len(data) == BASE.BLOCK, "slot replacement is not one block")
    slots = list(m.slots)
    b = bytearray(slots[slot])
    off = block_index * BASE.BLOCK
    b[off:off + BASE.BLOCK] = data
    slots[slot] = bytes(b)
    return BASE.Media(m.blocks, m.primary, m.mirror, tuple(slots))

def _slot_block(m, slot: int, block_index: int) -> bytes:
    off = block_index * BASE.BLOCK
    return m.slots[slot][off:off + BASE.BLOCK]

def _durable_write_result(case: dict, before: bytes, intended: bytes) -> bytes:
    need(len(before) == BASE.BLOCK and len(intended) == BASE.BLOCK,
         "write model requires one-block images")
    inj = case["injection"]
    kind = inj["kind"]
    if kind == "before_write":
        return before
    if kind == "torn_write":
        landed = inj["landed_bytes"]
        need(1 <= landed < BASE.BLOCK, "invalid torn prefix")
        # Torn prefixes are physically landed and therefore durable in BOTH modes.
        return intended[:landed] + before[landed:]
    if kind == "after_write":
        need(inj["landed_bytes"] == BASE.BLOCK, "after_write is not full block")
        return intended if case["mode"] == "write_through" else before
    raise OracleError("not a block-write injection")

def expected_metadata_post(case: dict):
    """Exact durable metadata after the injection; chunk bytes are observed separately."""
    pre, committed = transaction_media(case)
    target = case["target"]
    _, _, slot = _pass_geometry(case)
    old_entry, new_entry = _slot_block(pre, slot, 1), _slot_block(committed, slot, 1)
    old_header, new_header = _slot_block(pre, slot, 0), _slot_block(committed, slot, 0)

    if target in ("chunk_copy", "chunk_flush"):
        return pre
    if target == "entry_block":
        return _with_slot_block(pre, slot, 1, _durable_write_result(case, old_entry, new_entry))
    if target == "entry_block_flush":
        # The entry write completed; an interrupted flush makes it durable only
        # on write-through media.
        data = new_entry if case["mode"] == "write_through" else old_entry
        return _with_slot_block(pre, slot, 1, data)
    if target == "header_block":
        # Entry bytes were successfully flushed before the header write begins.
        m = _with_slot_block(pre, slot, 1, new_entry)
        return _with_slot_block(m, slot, 0, _durable_write_result(case, old_header, new_header))
    if target == "header_block_flush":
        m = _with_slot_block(pre, slot, 1, new_entry)
        data = new_header if case["mode"] == "write_through" else old_header
        return _with_slot_block(m, slot, 0, data)
    raise OracleError("unknown metadata target")

def expected_layout(case: dict) -> str:
    layout = layout_name(case["fixture"], expected_metadata_post(case))
    if layout is None:
        raise OracleError("expected durable metadata has no permitted live layout")
    return layout

def _validate_target_block(case: dict, obs: dict, pre, committed):
    """Exact one-block durability model for every write target."""
    if case["target"] not in ("chunk_copy", "entry_block", "header_block"):
        need("target_block" not in obs or obs.get("target_block") in (None, {}),
             "flush case supplied a write-target block")
        return

    raw = obs.get("target_block")
    need(isinstance(raw, dict), "missing raw target-block observation")
    try:
        before = bytes.fromhex(raw["before_hex"])
        intended = bytes.fromhex(raw["intended_hex"])
        durable = bytes.fromhex(raw["durable_hex"])
    except (KeyError, ValueError, TypeError) as exc:
        raise OracleError("malformed raw target-block observation") from exc
    need(len(before) == len(intended) == len(durable) == BASE.BLOCK,
         "target-block observation is not exactly 512 bytes")

    if case["target"] == "chunk_copy":
        need(before == target_before_block(case), "chunk target preimage drift")
        whole, prefix = source_block_known(case)
        if whole is not None:
            need(intended == whole, "chunk copy payload is not verifier source block")
        else:
            need(intended.startswith(prefix), "partial-timeline copy payload prefix mismatch")
    else:
        _, _, slot = _pass_geometry(case)
        block_index = 1 if case["target"] == "entry_block" else 0
        need(before == _slot_block(pre, slot, block_index),
             "metadata target preimage drift")
        need(intended == _slot_block(committed, slot, block_index),
             "metadata write payload drift")

    expected = _durable_write_result(case, before, intended)
    need(durable == expected, "target block durable bytes violate injection model")

def _validate_remount_info(got_post, obs: dict):
    """Bind the universal free_next invariant to the public frozen tape_info API.

    DRAFT-8 tape_info exposes total_chunks/free_chunks rather than a free_next field.
    The runtime frontier is therefore observed as total_chunks - free_chunks and
    independently compared with the raw-media-derived invariant-12 value.
    """
    need(obs.get("remount_side") == "B", "fresh crash remount was not Side B")
    info = obs.get("remount_info")
    need(isinstance(info, dict), "missing raw post-crash tape_info")

    sbx = BASE.select_sb(got_post)
    expected_uuid = sbx[20:36].hex()
    total_chunks = struct.unpack_from("<I", sbx, 52)[0]
    live = BASE.live_slot(got_post, 1)
    need(live is not None, "post-crash Side B is not selectable")
    entries = BASE.parse_entries(got_post.slots[live])
    total_frames = sum(e[2] for e in entries)

    need(info.get("uuid_hex") == expected_uuid, "tape_info UUID not bound to remounted cartridge")
    need(info.get("side_b_valid") is True, "tape_info reports invalid Side B")
    need(info.get("total_chunks") == total_chunks, "tape_info total_chunks mismatch")
    need(info.get("entry_count") == len(entries), "tape_info entry_count mismatch")
    need(info.get("total_frames") == total_frames, "tape_info total_frames mismatch")

    free_chunks = info.get("free_chunks")
    need(isinstance(free_chunks, int) and 0 <= free_chunks <= total_chunks,
         "tape_info free_chunks out of range")
    reported_free_next = total_chunks - free_chunks
    expected_free_next = BASE.free_next(got_post)
    need(reported_free_next == expected_free_next,
         "fresh-remount free_next invariant mismatch")

def validate_clean_case(case, post, events, calls):
    need(case.id != "WP12-STAGE-CLEAR", "stage-clear closure belongs to accepted #69")
    errors = BASE.check(case, post, events, calls)
    need(not errors, "; ".join(errors))

def validate_zero_needed_empty(pre, post, events: list, call: dict):
    need(BASE.live_slot(pre, 1) is not None, "empty fixture has no valid B index")
    live = BASE.live_slot(pre, 1)
    need(BASE.parse_entries(pre.slots[live]) == [], "empty fixture is non-empty")
    need(call.get("result") == "TAPE_OK" and call.get("more_work") is False, "empty respool result")
    need(call.get("block_budget", 1) > 0, "empty test must call with valid budget")
    need(not [e for e in events if e.get("op") in ("write", "flush")], "empty zero-needed branch wrote")
    need(post.encode() == pre.encode(), "empty zero-needed branch changed media")

def validate_crash_observation(case: dict, obs: dict):
    need(obs.get("format") == "WP10-RESPOOL-OBSERVATION-1", "observation format")
    need(obs.get("case_id") == case_id(case), "case identity")
    need(obs.get("injection_fired") is True, "planned injection skipped")
    need(obs.get("fresh_remount_from_durable_only") is True, "remount did not use durable bytes only")
    need(obs.get("actual_remount_result") == "TAPE_OK", "post-crash remount failed")

    pre, committed = transaction_media(case)
    got_pre = from_compact(obs["pre_snapshot"])
    got_post = from_compact(obs["post_snapshot"])
    need(got_pre.encode() == pre.encode(), "pre-snapshot fixture drift")

    expected_post = expected_metadata_post(case)
    need(got_post.encode() == expected_post.encode(),
         "durable metadata bytes differ from exact injection model")
    need(got_post.primary == pre.primary and got_post.mirror == pre.mirror,
         "ordinary stage-0 respool changed superblock")
    need(got_post.slots[0] == pre.slots[0] and got_post.slots[1] == pre.slots[1],
         "respool changed Side A metadata")
    need(obs.get("live_a_sha256") == LIVE_A_SHA256, "Side A bytes changed")

    layout = layout_name(case["fixture"], got_post)
    want = expected_layout(case)
    need(layout == want, f"selected layout {layout!r} != {want!r}")

    committed_layout = layout_name(case["fixture"], committed)
    if layout == committed_layout:
        live = BASE.live_slot(got_post, 1)
        expected_live = BASE.live_slot(committed, 1)
        need(live is not None and expected_live is not None, "committed B missing")
        need(got_post.slots[live][:1024] == committed.slots[expected_live][:1024],
             "selected committed-pass metadata is not exact")

    _assert_disjoint_target(case)
    target = obs.get("target_event", {})
    need(target.get("target") == case["target"], "target event kind")
    lba = expected_target_lba(case)
    if lba is not None:
        need(target.get("lba") == lba, "target event LBA/destination mismatch")
        need(target.get("count") == 1, "targeted write is not one block")
    else:
        need(target.get("op") == "flush", "planned flush target not observed")

    _validate_target_block(case, obs, pre, committed)
    _validate_remount_info(got_post, obs)

    hashes = obs.get("raw_region_sha256", {})
    need(hashes.get("live_a") == LIVE_A_SHA256, "raw Side A hash mismatch")
    if case["fixture"] == "v3_003":
        if case["pass"] == "pass1":
            need(hashes.get("source_10_12") == V3_AUDIO_SHA256, "pass1 source audio changed")
            if layout == "post_pass1":
                need(hashes.get("copy_12_14") == V3_AUDIO_SHA256, "pass1 committed copy not bit-identical")
        else:
            need(hashes.get("pass1_12_14") == V3_AUDIO_SHA256,
                 "pass2 destroyed/changed the sole live pass1 copy")
            if layout == "post_pass2":
                need(hashes.get("copy_10_12") == V3_AUDIO_SHA256,
                     "pass2 committed copy not bit-identical")
    else:
        need(hashes.get("source_fragments") == DECLINE_AUDIO_SHA256,
             "no-lower-run source render changed")
        if layout == "post_pass1":
            need(hashes.get("copy_10_frames") == DECLINE_AUDIO_SHA256,
                 "decline-case compacted copy not bit-identical")

def _row_map(row: list[dict]) -> dict:
    out = {}
    for cell in row:
        name = cell.get("call")
        need(name in COLUMNS, f"unknown matrix column {name!r}")
        need(name not in out, f"duplicate matrix column {name}")
        out[name] = cell
    need(set(out) == set(COLUMNS), "15-column row incomplete")
    return out

def validate_respool_in_progress_row(row: list[dict]):
    cells = _row_map(row)
    need(len(RESPOOL_BUSY) == 11 and len(RESPOOL_ALLOWED) == 4, "respool row cardinality")
    token = cells["respool"].get("operation_token_before")
    for name in RESPOOL_BUSY:
        c = cells[name]
        need(c.get("result") == "TAPE_ERR_BUSY", f"{name} did not return BUSY")
        need(c.get("block_ops") == 0, f"{name} BUSY performed block operations")
        need(c.get("operation_token_before") == token == c.get("operation_token_after"),
             f"{name} BUSY terminated/restarted operation")
    for name in RESPOOL_ALLOWED:
        c = cells[name]
        need(c.get("result") == "TAPE_OK", f"{name} not allowed in respool row")
    cont = cells["respool"]
    need(cont.get("operation_token_before") == cont.get("operation_token_after") == token,
         "matching continuation changed operation identity")
    need(cont.get("progress_after", 0) > cont.get("progress_before", -1),
         "matching continuation did not advance")

def validate_faulted_row(row: list[dict]):
    cells = _row_map(row)
    need(len(FAULTED_F) == 11 and len(FAULTED_ALLOWED) == 4, "faulted row cardinality")
    for name in FAULTED_F:
        c = cells[name]
        need(c.get("result") == "TAPE_ERR_FAULTED", f"{name} leaked through FAULTED row")
        need(c.get("block_ops") == 0, f"{name} FAULTED performed block operations")
    for name in FAULTED_ALLOWED:
        need(cells[name].get("result") == "TAPE_OK", f"{name} not allowed in FAULTED row")

def validate_longop_contract(obs: dict):
    validate_respool_in_progress_row(obs["in_progress_row"])
    validate_faulted_row(obs["faulted_row"])

    calls = obs["small_budget_calls"]
    need(len(calls) >= 2, "small-budget campaign did not continue")
    token = calls[0].get("operation_token")
    need(all(c.get("result") == "TAPE_OK" and c.get("operation_token") == token for c in calls),
         "small-budget continuation restarted/failed")
    need(all(c.get("block_budget", 0) > 0 for c in calls), "small-budget campaign used zero budget")
    need(all(c.get("more_work") is True for c in calls[:-1]) and calls[-1].get("more_work") is False,
         "small-budget campaign did not terminate exactly once")
    need(all(calls[i]["progress_after"] > calls[i]["progress_before"] for i in range(len(calls))),
         "small-budget call failed to advance")

    for z in obs["zero_budget"]:
        need(z.get("block_budget") == 0 and z.get("result") == "TAPE_ERR_INVALID_ARG",
             "zero budget not INVALID_ARG")
        need(z.get("block_ops") == 0 and z.get("state_before") == z.get("state_after"),
             "zero budget changed work/state")
    need({z.get("phase") for z in obs["zero_budget"]} == {"initiation", "continuation"},
         "zero budget initiation/continuation coverage incomplete")

    busy = obs["busy_then_continue"]["busy"]
    nxt = obs["busy_then_continue"]["continuation"]
    need(busy.get("result") == "TAPE_ERR_BUSY" and busy.get("block_ops") == 0,
         "interfering BUSY call")
    need(busy.get("operation_token_before") == busy.get("operation_token_after") == nxt.get("operation_token"),
         "BUSY terminated/restarted operation")
    need(nxt.get("result") == "TAPE_OK" and nxt.get("progress_after") > nxt.get("progress_before"),
         "ordinary continuation did not resume same operation")

    failures = obs["own_device_failures"]
    need({f.get("failure") for f in failures} == {"write", "flush"}, "write+flush fault coverage incomplete")
    for f in failures:
        need(f.get("result") == "TAPE_ERR_IO" and f.get("more_work") is False,
             "own-device failure did not terminate")
        need(f.get("state_after") == "FAULTED", "own-device failure did not enter FAULTED")

    foa = obs["faulted_over_armed"]
    need(foa.get("armed") is True and foa.get("frames_owed", 0) > 0, "faulted-over-armed premise")
    need(foa.get("respool_result") == "TAPE_ERR_FAULTED" and foa.get("block_ops") == 0,
         "Faulted did not override armed state")

    ring = obs["faulted_ring_drain"]
    rendered = ring.get("rendered_frames", [])
    need(rendered and rendered[-1] == 0, "faulted ring did not drain to zero")
    need(all(rendered[i] >= rendered[i+1] for i in range(len(rendered)-1)),
         "faulted ring drain grew")
    need(ring.get("underrun") is True and ring.get("abort_result") == "TAPE_OK",
         "faulted underrun/abort behavior")

    need(obs.get("stable_continuation_args") == list(RESPOOL_STABLE_CONTINUATION_ARGS),
         "invented respool stable continuation argument")
    need(obs.get("progress_callback_reentry_applicable") is RESPOOL_PROGRESS_CALLBACK_REENTRY_APPLICABLE,
         "invented respool progress callback/re-entry surface")
