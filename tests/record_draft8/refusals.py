#!/usr/bin/env python3
"""Independent DRAFT-8 WP-09 refusal / abort rows.

Authored from Engine API §7 / §10 and TapeFS §4.5 / §8 / §9.1.
Does not inspect product implementation. Does not depend on acceptance
of the happy-path record families.
"""
from __future__ import annotations

import struct
import zlib

from oracle import (
    Media,
    base_fixture,
    cartridge_sequence,
    derived_total_chunks,
    free_next,
    idx,
    live_slot,
    parse_entries,
    sb,
    select_sb,
    semantic_valid,
)

TAPE_MAX_ENTRIES = 4096
SEQ_CAP = 0xFFFFFFFD


def _writes(events):
    return [e for e in events if e.get("op") == "write"]


def _flushes(events):
    return [e for e in events if e.get("op") == "flush"]


def _stage1_resume_fixture(*, exhausted: bool) -> Media:
    """Construct an actual §9.3.3 row-1 stage-1 cartridge.

    A and B are byte-identical at staging run S=3, len=1 and H=S+len=4.
    The A1 slot remains semantically invalid for A but is structurally valid;
    when exhausted=True it carries SEQ_CAP so cartridge_sequence is exhausted
    without disturbing the stage oracle.
    """
    pre = base_fixture()
    chunks = derived_total_chunks(60)
    staged = bytearray(sb(generation=7, high=4, chunks=chunks, stage=1))
    struct.pack_into("<I", staged, 128, 3)  # promote_staging_chunk = S
    struct.pack_into("<I", staged, 508, zlib.crc32(staged[:508]))
    slots = list(pre.slots)
    slots[0] = idx(0, [(3, 0, 128)], 10)
    slots[1] = idx(1, [(1, 0, 64)], SEQ_CAP if exhausted else 700)
    slots[2] = idx(1, [(3, 0, 128)], 20)
    return Media(pre.blocks, bytes(staged), bytes(staged), tuple(slots))


def refusal_cases():
    """Return (id, pre, mode, mount_side, expect) tuples."""
    pre = base_fixture()
    chunks = derived_total_chunks(60)

    slots = list(pre.slots)
    slots[1] = idx(1, [(1, 0, 64)], SEQ_CAP)
    exhausted = Media(pre.blocks, pre.primary, pre.mirror, tuple(slots))

    full_slots = list(pre.slots)
    full_slots[2] = idx(1, [(0, 0, 256), (chunks - 1, 0, 128)], 20)
    full = Media(pre.blocks, pre.primary, pre.mirror, tuple(full_slots))

    packed_entries = [(0, i, 1) for i in range(TAPE_MAX_ENTRIES)]
    packed_slots = list(pre.slots)
    packed_slots[2] = idx(1, packed_entries, 20)
    packed = Media(pre.blocks, pre.primary, pre.mirror, tuple(packed_slots))

    staged_exh = _stage1_resume_fixture(exhausted=True)

    return [
        ("WP09-RO-SIDE-A", pre, "overwrite", "A", "TAPE_ERR_READ_ONLY"),
        ("WP09-SEQ-EXHAUSTED", exhausted, "overwrite", "B", "TAPE_ERR_SEQUENCE_EXHAUSTED"),
        ("WP09-INDEX-FULL", packed, "splice", "B", "TAPE_ERR_INDEX_FULL"),
        ("WP09-CART-FULL", full, "overwrite", "B", "TAPE_ERR_CARTRIDGE_FULL"),
        ("WP09-ABORT-DISARM", pre, "overwrite", "B", "TAPE_OK"),
        ("WP09-STAGE-REFUSE", staged_exh, "overwrite", "B", "TAPE_ERR_SEQUENCE_EXHAUSTED"),
    ]


def fixture_ok(cid, pre):
    errors = []
    if cid == "WP09-SEQ-EXHAUSTED":
        if cartridge_sequence(pre) != SEQ_CAP:
            errors.append("exhaustion fixture sequence is not 0xFFFFFFFD")
        if live_slot(pre, 1) != 2:
            errors.append("exhaustion fixture lost live B")
    if cid == "WP09-INDEX-FULL":
        if live_slot(pre, 1) != 2:
            errors.append("index-full fixture lost live B")
        if len(parse_entries(pre.slots[2])) != TAPE_MAX_ENTRIES:
            errors.append("index-full fixture is not packed to TAPE_MAX_ENTRIES")
        if not semantic_valid(pre.slots[2], 1, select_sb(pre)):
            errors.append("index-full fixture live B is not semantically valid")
    if cid == "WP09-CART-FULL":
        chunks = derived_total_chunks(60)
        if free_next(pre) != chunks:
            errors.append(f"full fixture free_next={free_next(pre)} != total_chunks={chunks}")
        if live_slot(pre, 1) != 2:
            errors.append("full fixture lost live B")
    if cid == "WP09-STAGE-REFUSE":
        selected = select_sb(pre)
        if struct.unpack_from("<I", selected, 124)[0] != 1:
            errors.append("stage-refuse fixture promote_stage is not 1")
        if struct.unpack_from("<I", selected, 128)[0] != 3:
            errors.append("stage-refuse fixture staging chunk is not 3")
        if struct.unpack_from("<I", selected, 56)[0] != 4:
            errors.append("stage-refuse fixture H is not S+len")
        if cartridge_sequence(pre) != SEQ_CAP:
            errors.append("stage-refuse fixture sequence is not exhausted")
        if live_slot(pre, 0) != 0 or live_slot(pre, 1) != 2:
            errors.append("stage-refuse fixture lost live A/B")
        if parse_entries(pre.slots[0]) != [(3, 0, 128)] or parse_entries(pre.slots[2]) != [(3, 0, 128)]:
            errors.append("stage-refuse fixture does not match §9.3.3 row 1")
    return errors


def check_refusal(cid, pre, mode, mount_side, expect, post, events, calls):
    err = []

    def req(cond, msg):
        if not cond:
            err.append(msg)

    req(post.encode() == pre.encode(), "refusal or abort wrote media bytes")
    req(not _writes(events), "refusal or abort issued a write")
    req(not _flushes(events), "refusal or abort issued a flush")
    req(post.primary == pre.primary and post.mirror == pre.mirror, "superblock bytes changed")
    req(post.slots == pre.slots, "index slot bytes changed")

    mounts = [c for c in calls if c.get("fn") == "tape_mount"]
    req(len(mounts) == 1 and mounts[0].get("result") == "TAPE_OK", "mount did not succeed")
    req(bool(mounts) and mounts[0].get("side") == mount_side, "mounted the wrong side")

    if cid == "WP09-RO-SIDE-A":
        arms = [c for c in calls if c.get("fn") == "tape_arm"]
        req(len(arms) == 1 and arms[0].get("result") == expect and arms[0].get("mode") == mode, "Side-A arm was not READ_ONLY")
        req(not any(c.get("fn") == "tape_feed" for c in calls), "Side-A refusal fed frames")
    elif cid in ("WP09-SEQ-EXHAUSTED", "WP09-INDEX-FULL", "WP09-STAGE-REFUSE"):
        arms = [c for c in calls if c.get("fn") == "tape_arm"]
        req(len(arms) == 1 and arms[0].get("result") == expect and arms[0].get("mode") == mode, "arm refusal mismatch")
        req(not any(c.get("fn") == "tape_feed" for c in calls), "refused arm still fed")
        if cid == "WP09-STAGE-REFUSE":
            req(struct.unpack_from("<I", post.primary, 124)[0] == 1, "stage-clearing write ran on a refusal")
    elif cid == "WP09-CART-FULL":
        arms = [c for c in calls if c.get("fn") == "tape_arm"]
        req(len(arms) == 1 and arms[0].get("result") == "TAPE_OK" and arms[0].get("mode") == mode, "full-cartridge arm should succeed")
        feeds = [c for c in calls if c.get("fn") == "tape_feed"]
        req(
            len(feeds) == 1
            and feeds[0].get("result") == expect
            and feeds[0].get("requested") == 64
            and feeds[0].get("accepted") == 0
            and "events_from_call" in feeds[0]
            and feeds[0].get("events_from_call") == 0,
            "cartridge-full short-accept missing",
        )
        req(not any(e.get("phase") == "feed" for e in events), "cartridge-full tape_feed issued raw block I/O")
        aborts = [c for c in calls if c.get("fn") == "tape_abort"]
        req(len(aborts) == 1 and aborts[0].get("result") == "TAPE_OK", "full-cartridge abort missing")
    elif cid == "WP09-ABORT-DISARM":
        arms = [c for c in calls if c.get("fn") == "tape_arm"]
        req(len(arms) == 1 and arms[0].get("result") == "TAPE_OK", "abort case arm failed")
        aborts = [c for c in calls if c.get("fn") == "tape_abort"]
        req(len(aborts) == 1 and aborts[0].get("result") == "TAPE_OK", "abort was not TAPE_OK")
        req(not any(c.get("fn") == "tape_commit" for c in calls), "abort case committed")

    unmounts = [c for c in calls if c.get("fn") == "tape_unmount"]
    req(len(unmounts) == 1 and unmounts[0].get("result") == "TAPE_OK",
        "refusal/abort did not leave a state that can unmount")
    return err


def synth_refusal(cid, pre, mode, mount_side, expect):
    calls = [{"phase": "mount", "fn": "tape_mount", "result": "TAPE_OK", "side": mount_side}]
    if cid == "WP09-RO-SIDE-A":
        calls.append({"phase": "arm", "fn": "tape_arm", "result": expect, "mode": mode})
    elif cid in ("WP09-SEQ-EXHAUSTED", "WP09-INDEX-FULL", "WP09-STAGE-REFUSE"):
        calls.append({"phase": "seek", "fn": "tape_seek", "result": "TAPE_OK", "frame": 0})
        calls.append({"phase": "arm", "fn": "tape_arm", "result": expect, "mode": mode})
    elif cid == "WP09-CART-FULL":
        calls.append({"phase": "seek", "fn": "tape_seek", "result": "TAPE_OK", "frame": 0})
        calls.append({"phase": "arm", "fn": "tape_arm", "result": "TAPE_OK", "mode": mode})
        calls.append(
            {
                "phase": "feed",
                "fn": "tape_feed",
                "result": expect,
                "requested": 64,
                "accepted": 0,
                "events_from_call": 0,
            }
        )
        calls.append({"phase": "abort", "fn": "tape_abort", "result": "TAPE_OK"})
    elif cid == "WP09-ABORT-DISARM":
        calls.append({"phase": "seek", "fn": "tape_seek", "result": "TAPE_OK", "frame": 128})
        calls.append({"phase": "arm", "fn": "tape_arm", "result": "TAPE_OK", "mode": mode})
        calls.append({"phase": "abort", "fn": "tape_abort", "result": "TAPE_OK"})
    calls.append({"phase": "unmount", "fn": "tape_unmount", "result": "TAPE_OK"})
    return pre, [], calls
