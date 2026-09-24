#!/usr/bin/env python3
"""Independent media/event oracle for frozen WP-07 allocator/COW evidence."""
from __future__ import annotations

import struct
import zlib
from typing import Any

from fixture import (
    BLOCK_COUNT,
    CHUNK_BLOCKS,
    CHUNK_FRAMES,
    FUZZ_A_HIGH_WATER,
    LBA_CHUNK_BASE,
    RESET_A_HIGH_WATER,
    TOTAL_CHUNKS,
    fuzz_entries_a,
    fuzz_initial_b_slots,
)
from generator import (
    EXPECTED_PLAN_SHA256,
    MASTER_SEED,
    SEQUENCE_COUNT,
    resolve_selector,
)

EVIDENCE_FORMAT = "WP07-COW-EVIDENCE-1"
RESULT_FORMAT = "WP07-COW-RESULT-1"
ADAPTER_FORMAT = "WP07-COW-ADAPTER-1"
RESET_LIMIT_NS = 1_000_000_000


class EvidenceError(RuntimeError):
    pass


def _need(cond: bool, msg: str) -> None:
    if not cond:
        raise EvidenceError(msg)


def _u32(b: bytes, off: int) -> int:
    return struct.unpack_from("<I", b, off)[0]


def _u64(b: bytes, off: int) -> int:
    return struct.unpack_from("<Q", b, off)[0]


def parse_slot(snapshot: dict, *, expected_side: int, total_chunks: int) -> dict:
    _need(isinstance(snapshot, dict), "slot snapshot is not an object")
    try:
        header = bytes.fromhex(snapshot.get("header_hex", ""))
        entries_raw = bytes.fromhex(snapshot.get("entries_hex", ""))
    except ValueError as exc:
        raise EvidenceError(f"slot hex malformed: {exc}") from exc
    _need(len(header) == 64, "slot header snapshot must be exactly 64 bytes")

    if header[:8] != b"TAPEIDX\x01":
        return {
            "structural_valid": False,
            "valid": False,
            "reason": "bad magic",
            "sequence": None,
            "entries": [],
        }

    sequence = _u32(header, 8)
    side = header[12]
    entry_count = _u32(header, 16)
    total_frames = _u64(header, 20)
    stored_crc = _u32(header, 60)

    if entry_count > 4096:
        return {
            "structural_valid": False,
            "valid": False,
            "reason": "entry_count > 4096",
            "sequence": sequence,
            "entries": [],
        }

    _need(
        len(entries_raw) == 12 * entry_count,
        "slot entries snapshot length does not match entry_count",
    )
    crc_ok = zlib.crc32(header[:60] + entries_raw) == stored_crc
    if not crc_ok:
        return {
            "structural_valid": False,
            "valid": False,
            "reason": "CRC mismatch",
            "sequence": sequence,
            "entries": [],
        }

    entries = []
    errors = []
    total = 0
    intervals = []
    for i in range(entry_count):
        first, start, count = struct.unpack_from("<III", entries_raw, 12 * i)
        total += count
        if count == 0:
            errors.append(f"entry {i}: frame_count == 0")
            last = first
        else:
            span = int(start) + int(count) - 1
            last = int(first) + span // CHUNK_FRAMES
        if start >= CHUNK_FRAMES:
            errors.append(f"entry {i}: start_frame out of range")
        if last >= total_chunks:
            errors.append(f"entry {i}: last chunk {last} >= total_chunks")
        base = int(first) * CHUNK_FRAMES + int(start)
        end = base + int(count)
        intervals.append((base, end, i))
        entries.append(
            {
                "first_chunk_id": first,
                "start_frame": start,
                "frame_count": count,
                "last": last,
                "base": base,
                "end": end,
            }
        )

    if side != expected_side:
        errors.append(f"slot side {side} != expected {expected_side}")
    if total != total_frames:
        errors.append(f"total_frames {total_frames} != entry sum {total}")

    ordered = sorted(intervals)
    for left, right in zip(ordered, ordered[1:]):
        if left[1] > right[0]:
            errors.append(
                f"physical-frame overlap entries {left[2]} and {right[2]}"
            )

    return {
        "structural_valid": True,
        "valid": not errors,
        "reason": "; ".join(errors) if errors else "",
        "sequence": sequence,
        "side": side,
        "entry_count": entry_count,
        "total_frames": total_frames,
        "entries": entries,
    }


def choose_live_b(slots: list[dict], *, total_chunks: int = TOTAL_CHUNKS) -> dict:
    _need(isinstance(slots, list) and len(slots) == 2, "need exactly two B slot snapshots")
    parsed = [
        parse_slot(s, expected_side=1, total_chunks=total_chunks) for s in slots
    ]

    # In this non-crash campaign, a structurally valid committed index must itself
    # satisfy full §5.2 validity, including interval disjointness.
    for i, row in enumerate(parsed):
        if row["structural_valid"] and not row["valid"]:
            raise EvidenceError(f"B{i} structurally valid but invalid: {row['reason']}")

    valid = [r for r in parsed if r["valid"]]
    _need(valid, "no valid Side-B index after successful action")
    if len(valid) == 1:
        live = valid[0]
    else:
        _need(
            valid[0]["sequence"] != valid[1]["sequence"],
            "two valid Side-B slots have equal sequence",
        )
        live = max(valid, key=lambda r: r["sequence"])
    return {"live": live, "slots": parsed}


def derived_free_next(live_b: dict, *, a_high_water: int) -> int:
    entries = live_b["entries"]
    if not entries:
        return a_high_water
    return max(a_high_water, max(int(e["last"]) + 1 for e in entries))


def chunk_write_ids(events: list[dict], *, total_chunks: int = TOTAL_CHUNKS) -> list[int]:
    _need(isinstance(events, list), "write_events is not an array")
    out = []
    chunk_end = LBA_CHUNK_BASE + total_chunks * CHUNK_BLOCKS
    for i, ev in enumerate(events):
        _need(isinstance(ev, dict), f"write event {i} malformed")
        lba = ev.get("lba")
        count = ev.get("count")
        _need(
            isinstance(lba, int) and not isinstance(lba, bool) and lba >= 0,
            f"write event {i} invalid lba",
        )
        _need(
            isinstance(count, int) and not isinstance(count, bool) and count > 0,
            f"write event {i} invalid count",
        )
        lo = max(lba, LBA_CHUNK_BASE)
        hi = min(lba + count, chunk_end)
        if lo >= hi:
            continue
        first = (lo - LBA_CHUNK_BASE) // CHUNK_BLOCKS
        last = (hi - 1 - LBA_CHUNK_BASE) // CHUNK_BLOCKS
        out.extend(range(first, last + 1))
    return out


def _check_floor(ids: list[int], *, a_high_water: int, label: str) -> None:
    bad = [x for x in ids if x < a_high_water]
    _need(not bad, f"{label}: chunk destination(s) below a_high_water: {bad[:8]}")


def _check_probe(probe: dict, expected_free_next: int, *, a_high_water: int) -> None:
    _need(isinstance(probe, dict), "missing allocation probe")
    _need(probe.get("event_overflow") is False, "allocation probe event overflow")
    for field in (
        "seek_result",
        "arm_result",
        "feed_result",
        "service_terminal_result",
        "abort_result",
        "unmount_result",
        "remount_result",
    ):
        _need(probe.get(field) == "TAPE_OK", f"allocation probe {field} failed")
    _need(probe.get("accepted_frames") == 1, "allocation probe did not accept one frame")
    ids = chunk_write_ids(probe.get("write_events"))
    _need(ids, "allocation probe produced no chunk write")
    _check_floor(ids, a_high_water=a_high_water, label="allocation probe")
    _need(
        ids[0] == expected_free_next,
        f"remount free_next mismatch: first allocation {ids[0]} != derived {expected_free_next}",
    )


def validate_sequence(plan: dict, obs: dict) -> dict:
    _need(isinstance(obs, dict), "sequence observation is not an object")
    _need(obs.get("format") == RESULT_FORMAT, "wrong sequence-result format")
    _need(obs.get("seq_index") == plan["seq_index"], "sequence index mismatch")
    _need(obs.get("seq_seed") == plan["seq_seed"], "sequence seed mismatch")
    _need(obs.get("event_overflow") is False, "sequence event overflow")
    _need(obs.get("normal_exit") is True, "sequence did not complete normally")

    initial = obs.get("initial_b_slots")
    _need(initial == fuzz_initial_b_slots(), "sequence did not start from exact verifier fixture")
    previous_slots = initial
    actions = obs.get("actions")
    _need(isinstance(actions, list), "actions observation missing")
    _need(len(actions) == len(plan["actions"]), "action count mismatch")

    stats = {
        "edit_actions": 0,
        "reset_actions": 0,
        "chunk_write_events": 0,
        "allocation_probes": 0,
        "legal_below_floor_reference_snapshots": 0,
    }

    for idx, (want, got) in enumerate(zip(plan["actions"], actions)):
        _need(isinstance(got, dict), f"action {idx} observation malformed")
        _need(got.get("kind") == want["kind"], f"action {idx} kind mismatch")
        _need(got.get("pre_b_slots") == previous_slots, f"action {idx} pre-media continuity mismatch")

        pre_sel = choose_live_b(got["pre_b_slots"])
        pre_live = pre_sel["live"]
        pre_free = derived_free_next(pre_live, a_high_water=FUZZ_A_HIGH_WATER)
        if any(e["first_chunk_id"] < FUZZ_A_HIGH_WATER for e in pre_live["entries"]):
            stats["legal_below_floor_reference_snapshots"] += 1

        if want["kind"] == "edit":
            stats["edit_actions"] += 1
            for key in ("mode", "selector", "frames", "service_budget"):
                _need(got.get(key) == want[key], f"action {idx} {key} mismatch")
            _need(
                got.get("pre_total_frames") == pre_live["total_frames"],
                f"action {idx} pre_total_frames not bound to raw live index",
            )
            expected_seek = resolve_selector(want["selector"], pre_live["total_frames"])
            _need(got.get("resolved_seek") == expected_seek, f"action {idx} selector resolution mismatch")
            for field in (
                "seek_result",
                "arm_result",
                "feed_result",
                "service_terminal_result",
                "commit_result",
                "unmount_result",
                "remount_result",
            ):
                _need(got.get(field) == "TAPE_OK", f"action {idx} {field} failed")
            _need(got.get("accepted_frames") == want["frames"], f"action {idx} short feed")
            ids = chunk_write_ids(got.get("write_events"))
            _need(ids, f"action {idx} edit produced no chunk write")
            stats["chunk_write_events"] += len(ids)
            _check_floor(ids, a_high_water=FUZZ_A_HIGH_WATER, label=f"action {idx} edit")
            _need(
                ids[0] == pre_free,
                f"action {idx} allocation start {ids[0]} != pre-remount derived free_next {pre_free}",
            )
        else:
            stats["reset_actions"] += 1
            _need(got.get("result") == "TAPE_OK", f"action {idx} reset failed")
            _need(got.get("timed_out") is False, f"action {idx} reset timed out")
            elapsed = got.get("elapsed_ns")
            _need(
                isinstance(elapsed, int) and 0 <= elapsed < RESET_LIMIT_NS,
                f"action {idx} reset not < 1 s",
            )
            ids = chunk_write_ids(got.get("write_events"))
            _need(not ids, f"action {idx} reset moved/wrote chunk data")

        _need(got.get("event_overflow") is False, f"action {idx} event overflow")
        post_slots = got.get("post_b_slots")
        post_sel = choose_live_b(post_slots)
        post_live = post_sel["live"]
        if got.get("post_info_total_frames") is not None:
            _need(
                got["post_info_total_frames"] == post_live["total_frames"],
                f"action {idx} public total_frames disagrees with raw index",
            )

        if want["kind"] == "reset":
            expected = fuzz_entries_a()
            actual = [
                (e["first_chunk_id"], e["start_frame"], e["frame_count"])
                for e in post_live["entries"]
            ]
            _need(actual == expected, f"action {idx} reset did not reference Side A index exactly")
            _need(
                all(e["first_chunk_id"] < FUZZ_A_HIGH_WATER for e in post_live["entries"]),
                f"action {idx} reset crafted below-water reference missing",
            )

        post_free = derived_free_next(post_live, a_high_water=FUZZ_A_HIGH_WATER)
        _check_probe(
            got.get("allocation_probe"),
            post_free,
            a_high_water=FUZZ_A_HIGH_WATER,
        )
        stats["allocation_probes"] += 1
        previous_slots = post_slots

    return stats


def validate_reset_stress(obs: dict) -> dict:
    _need(isinstance(obs, dict), "reset stress evidence missing")
    _need(obs.get("format") == "WP07-RESET-STRESS-1", "wrong reset stress format")
    _need(obs.get("result") == "TAPE_OK", "reset stress call failed")
    _need(obs.get("timed_out") is False, "reset stress timed out")
    elapsed = obs.get("elapsed_ns")
    _need(
        isinstance(elapsed, int) and 0 <= elapsed < RESET_LIMIT_NS,
        "reset stress is not < 1 second",
    )
    _need(obs.get("event_overflow") is False, "reset stress event overflow")
    _need(not chunk_write_ids(obs.get("write_events")), "reset stress moved/wrote chunk data")

    env = obs.get("timing_environment")
    _need(isinstance(env, dict), "missing timing environment")
    _need(env.get("clock") == "CLOCK_MONOTONIC", "timing clock is not CLOCK_MONOTONIC")
    for field in ("platform", "kernel", "cpu_model"):
        _need(isinstance(env.get(field), str) and env[field], f"missing timing environment {field}")
    res = env.get("timer_resolution_ns")
    _need(isinstance(res, int) and res > 0, "invalid timer resolution")

    post = choose_live_b(obs.get("post_b_slots"), total_chunks=TOTAL_CHUNKS)["live"]
    _need(post["entry_count"] == 4096, "reset stress did not commit 4096-entry Side-A copy")
    _need(post["total_frames"] == 4096, "reset stress total_frames mismatch")
    _need(
        all(
            e["first_chunk_id"] < RESET_A_HIGH_WATER
            for e in post["entries"]
        ),
        "reset stress did not retain legal below-high-water references",
    )
    return {"elapsed_ns": elapsed, "entry_count": post["entry_count"]}


def validate_acceptance_summary(summary: dict) -> list[str]:
    errors = []

    def need(cond: bool, msg: str) -> None:
        if not cond:
            errors.append(msg)

    need(summary.get("format") == EVIDENCE_FORMAT, "wrong evidence format")
    gen = summary.get("generator")
    need(isinstance(gen, dict), "missing generator provenance")
    if isinstance(gen, dict):
        need(gen.get("rng_algorithm") == "splitmix64-v1", "wrong RNG")
        need(gen.get("master_seed") == f"{MASTER_SEED:016x}", "wrong master seed")
        need(gen.get("sequence_count") == SEQUENCE_COUNT, "campaign count is not 10000")
        need(gen.get("plan_sha256") == EXPECTED_PLAN_SHA256, "wrong canonical plan digest")
    need(summary.get("completed_sequences") == SEQUENCE_COUNT, "fewer than 10000 sequences completed")
    need(summary.get("normal_exit") is True, "adapter did not exit normally")
    need(summary.get("failure_reproducer") is None, "failure reproducer present")
    hs = summary.get("adapter_handshake")
    need(isinstance(hs, dict), "missing adapter handshake")
    if isinstance(hs, dict):
        need(hs.get("format") == ADAPTER_FORMAT, "wrong adapter format")
        need(hs.get("adapter_kind") == "product", "non-product adapter")
    stress = summary.get("reset_stress")
    need(isinstance(stress, dict) and stress.get("passed") is True, "reset stress not passed")
    return errors
