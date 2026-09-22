#!/usr/bin/env python3
"""Additional independent DRAFT-8 WP-09 record families.

Covers boundary/breadth cases that do not depend on WP-10 crash tables:
- multi-chunk overwrite
- splice onto empty Side B and at an exact existing run boundary
- zero-accepted commit matrix beyond the core overwrite/middle case
- successful stage-1 clearing on arm from a mountable §9.3.3 resume state
"""
from __future__ import annotations

import struct
import zlib

from oracle import (
    BLOCK,
    CF,
    LBA_B1,
    LBA_CHUNK_BASE,
    Media,
    base_fixture,
    derived_total_chunks,
    free_next,
    idx,
    live_slot,
    parse_entries,
    sb,
    select_sb,
    semantic_valid,
    structural_sequence,
)

BLOCKS_PER_CHUNK = 1024
SLOT_BLOCKS = 128


def _writes(events, phase=None):
    return [e for e in events if e.get("op") == "write" and (phase is None or e.get("phase") == phase)]


def _flushes(events, phase=None):
    return [e for e in events if e.get("op") == "flush" and (phase is None or e.get("phase") == phase)]


def _chunk_lo(chunk: int) -> int:
    return LBA_CHUNK_BASE + chunk * BLOCKS_PER_CHUNK


def _touches(e, lba: int) -> bool:
    return (
        e.get("op") == "write"
        and isinstance(e.get("lba"), int)
        and isinstance(e.get("count"), int)
        and e["lba"] <= lba < e["lba"] + e["count"]
    )


def _commit_trace_errors(events):
    err = []
    ce = [(i, e) for i, e in enumerate(events) if e.get("phase") == "commit"]
    writes = [(i, e) for i, e in ce if e.get("op") == "write"]
    flush = [i for i, e in ce if e.get("op") == "flush"]
    if len(flush) != 2:
        err.append("commit did not perform exactly two flushes")
    for _, e in writes:
        if not (e.get("lba", -1) >= LBA_B1 and e.get("lba", -1) + e.get("count", 0) <= LBA_B1 + SLOT_BLOCKS):
            err.append("commit wrote outside inactive B1")
    entries = [i for i, e in writes if _touches(e, LBA_B1 + 1) and not _touches(e, LBA_B1)]
    header = [i for i, e in writes if e.get("lba") == LBA_B1 and e.get("count") == 1]
    if not entries or len(header) != 1:
        err.append("commit missing entry/header writes")
    elif len(flush) == 2:
        if not (max(entries) < flush[0] < header[0] < flush[1]):
            err.append("commit order is not entries -> flush -> header -> flush")
        if not all(i < flush[1] for i, _ in writes):
            err.append("commit wrote after final flush")
    return err


def _record_commit_events():
    return [
        {"phase": "commit", "op": "write", "lba": LBA_B1 + 1, "count": 1},
        {"phase": "commit", "op": "flush"},
        {"phase": "commit", "op": "write", "lba": LBA_B1, "count": 1},
        {"phase": "commit", "op": "flush"},
    ]


def empty_b_fixture() -> Media:
    pre = base_fixture()
    slots = list(pre.slots)
    slots[2] = idx(1, [], 20)
    return Media(pre.blocks, pre.primary, pre.mirror, tuple(slots))


def boundary_fixture() -> Media:
    pre = base_fixture()
    slots = list(pre.slots)
    slots[2] = idx(1, [(0, 0, 128), (1, 0, 128)], 20)
    return Media(pre.blocks, pre.primary, pre.mirror, tuple(slots))


def staged_fixture() -> Media:
    """Reachable/mountable §9.3.3 row-1 shape: A == B == {S,0,N}."""
    chunks = derived_total_chunks(60)
    staged = bytearray(sb(generation=7, high=4, chunks=chunks, stage=1))
    struct.pack_into("<I", staged, 128, 3)  # S = 3, len = 1, H = 4
    struct.pack_into("<I", staged, 508, zlib.crc32(staged[:508]))
    pre = base_fixture()
    slots = list(pre.slots)
    slots[0] = idx(0, [(3, 0, 128)], 10)
    # Preserve A1's structurally-valid sequence 700 so next_sequence remains 701.
    slots[2] = idx(1, [(3, 0, 128)], 20)
    return Media(pre.blocks, bytes(staged), bytes(staged), tuple(slots))


def extra_cases():
    pre = base_fixture()
    empty_b = empty_b_fixture()
    boundary = boundary_fixture()
    staged = staged_fixture()
    feed_n = CF + 64
    return [
        ("WP09-OW-MULTICHUNK", pre, "overwrite", "B", 0, feed_n, "happy"),
        ("WP09-SP-EMPTY-B", empty_b, "splice", "B", 0, 64, "happy"),
        ("WP09-SP-BOUNDARY", boundary, "splice", "B", 128, 64, "happy"),
        ("WP09-EMPTY-OW-START", pre, "overwrite", "B", 0, 0, "empty"),
        ("WP09-EMPTY-OW-END", pre, "overwrite", "B", 256, 0, "empty"),
        ("WP09-EMPTY-OD-START", pre, "overdub", "B", 0, 0, "empty"),
        ("WP09-EMPTY-OD", pre, "overdub", "B", 128, 0, "empty"),
        ("WP09-EMPTY-OD-END", pre, "overdub", "B", 256, 0, "empty"),
        ("WP09-EMPTY-SP-START", pre, "splice", "B", 0, 0, "empty"),
        ("WP09-EMPTY-SP", pre, "splice", "B", 128, 0, "empty"),
        ("WP09-EMPTY-SP-END", pre, "splice", "B", 256, 0, "empty"),
        ("WP09-STAGE-CLEAR", staged, "overwrite", "B", 64, 64, "stage"),
    ]


def fixture_ok(cid, pre):
    err = []
    if cid == "WP09-SP-EMPTY-B":
        if parse_entries(pre.slots[2]) != []:
            err.append("empty-B fixture not empty")
        if live_slot(pre, 1) != 2:
            err.append("empty-B lost live B")
    if cid == "WP09-SP-BOUNDARY":
        if parse_entries(pre.slots[2]) != [(0, 0, 128), (1, 0, 128)]:
            err.append("boundary fixture does not contain the required run boundary")
        if live_slot(pre, 1) != 2 or free_next(pre) != 3:
            err.append("boundary fixture selection/allocation drift")
    if cid == "WP09-STAGE-CLEAR":
        selected = select_sb(pre)
        if struct.unpack_from("<I", selected, 124)[0] != 1:
            err.append("stage-clear fixture promote_stage is not 1")
        if struct.unpack_from("<I", selected, 128)[0] != 3:
            err.append("stage-clear fixture staging chunk is not 3")
        if struct.unpack_from("<I", selected, 56)[0] != 4:
            err.append("stage-clear fixture H is not S+len")
        if live_slot(pre, 0) != 0 or live_slot(pre, 1) != 2:
            err.append("stage-clear fixture lost live A/B")
        if parse_entries(pre.slots[0]) != [(3, 0, 128)] or parse_entries(pre.slots[2]) != [(3, 0, 128)]:
            err.append("stage-clear fixture does not match §9.3.3 row 1")
        if free_next(pre) != 4:
            err.append("stage-clear fixture free_next is not H")
    if cid == "WP09-OW-MULTICHUNK" and free_next(pre) != 3:
        err.append("multi-chunk fixture free_next drift")
    return err


def cleared_sb(pre: Media) -> bytes:
    b = bytearray(select_sb(pre))
    gen = struct.unpack_from("<I", b, 12)[0]
    struct.pack_into("<I", b, 12, gen + 1)
    struct.pack_into("<I", b, 124, 0)
    struct.pack_into("<I", b, 128, 0)
    struct.pack_into("<I", b, 508, zlib.crc32(b[:508]))
    return bytes(b)


def _check_tail_probe(seek, calls, events, err):
    probe = min(seek, 255)
    tail_seek = [c for c in calls if c.get("fn") == "tape_seek" and c.get("phase") == "tail-seek"]
    tail_rate = [c for c in calls if c.get("fn") == "tape_set_rate" and c.get("phase") == "tail-rate"]
    tail_service = [c for c in calls if c.get("fn") == "tape_service" and c.get("phase") == "tail-service"]
    tail_render = [c for c in calls if c.get("fn") == "tape_render" and c.get("phase") == "tail-render"]
    if not (len(tail_seek) == 1 and tail_seek[0].get("result") == "TAPE_OK" and tail_seek[0].get("frame") == probe):
        err.append("empty commit tail seek missing")
    if not (tail_rate and tail_rate[0].get("result") == "TAPE_OK" and tail_rate[0].get("rate_q16_16") == 65536):
        err.append("empty commit tail rate missing")
    if not (tail_service and all(x.get("result") == "TAPE_OK" for x in tail_service) and tail_service[-1].get("more_work") is False):
        err.append("empty commit tail service did not complete")
    if not (
        len(tail_render) == 1
        and tail_render[0].get("result") == "TAPE_OK"
        and tail_render[0].get("requested") == 1
        and tail_render[0].get("rendered") == 1
        and "events_from_call" in tail_render[0]
        and tail_render[0].get("events_from_call") == 0
    ):
        err.append("empty commit tail did not render one frame without block I/O")
    if any(e.get("phase") == "tail-render" for e in events):
        err.append("tape_render issued block I/O")


def check_extra(cid, pre, mode, mount_side, seek, feed, kind, post, events, calls):
    err = []

    def req(cond, msg):
        if not cond:
            err.append(msg)

    mounts = [c for c in calls if c.get("fn") == "tape_mount"]
    req(bool(mounts) and mounts[0].get("result") == "TAPE_OK" and mounts[0].get("side") == mount_side, "mount failed or wrong side")
    scripted_seek = [c for c in calls if c.get("fn") == "tape_seek" and c.get("phase") == "seek"]
    req(len(scripted_seek) == 1 and scripted_seek[0].get("result") == "TAPE_OK" and scripted_seek[0].get("frame") == seek, "scripted seek mismatch")
    arms = [c for c in calls if c.get("fn") == "tape_arm"]
    req(len(arms) == 1 and arms[0].get("result") == "TAPE_OK" and arms[0].get("mode") == mode, "arm mismatch")

    unmounts = [c for c in calls if c.get("fn") == "tape_unmount"]
    remounts = [c for c in calls if c.get("fn") == "tape_mount" and c.get("phase") == "remount"]
    req(len(unmounts) == 1 and unmounts[0].get("result") == "TAPE_OK", "unmount failed")
    req(len(remounts) == 1 and remounts[0].get("result") == "TAPE_OK" and remounts[0].get("side") == "B", "remount failed")

    if kind == "empty":
        req(not _writes(events) and not _flushes(events), "empty commit/tail probe wrote or flushed")
        req(post.encode() == pre.encode(), "empty commit changed media")
        commits = [c for c in calls if c.get("fn") == "tape_commit"]
        req(len(commits) == 1 and commits[0].get("result") == "TAPE_OK", "empty commit not OK")
        _check_tail_probe(seek, calls, events, err)
        return err

    feeds = [c for c in calls if c.get("fn") == "tape_feed"]
    req(
        len(feeds) == 1
        and feeds[0].get("requested") == feed
        and feeds[0].get("accepted") == feed
        and feeds[0].get("result") == "TAPE_OK",
        "feed request/accepted-count mismatch",
    )
    req(len(feeds) == 1 and "events_from_call" in feeds[0] and feeds[0].get("events_from_call") == 0,
        "feed callback count missing or nonzero")
    req(not any(e.get("phase") == "feed" for e in events), "tape_feed issued raw block I/O")
    services = [c for c in calls if c.get("fn") == "tape_service" and c.get("phase") == "service"]
    req(bool(services) and all(x.get("result") == "TAPE_OK" for x in services) and services[-1].get("more_work") is False,
        "service did not run to completion")
    commits = [c for c in calls if c.get("fn") == "tape_commit"]
    req(len(commits) == 1 and commits[0].get("result") == "TAPE_OK", "commit not OK")
    req(semantic_valid(post.slots[3], 1, select_sb(post)), "post B1 invalid")
    req(structural_sequence(post.slots[3]) == 701, "sequence not 701")
    req(live_slot(post, 1) == 3, "B1 not live")
    req(post.slots[0] == pre.slots[0] and post.slots[1] == pre.slots[1] and post.slots[2] == pre.slots[2],
        "record changed a source slot")
    err.extend(_commit_trace_errors(events))

    service_writes = _writes(events, "service")

    if cid == "WP09-OW-MULTICHUNK":
        req(parse_entries(post.slots[3]) == [(3, 0, feed)], "multi-chunk index shape")
        req(free_next(post) == 5, "multi-chunk free_next")
        req(any(_chunk_lo(3) <= e.get("lba", -1) < _chunk_lo(4) for e in service_writes), "missing chunk-3 write")
        req(any(_chunk_lo(4) <= e.get("lba", -1) < _chunk_lo(5) for e in service_writes), "missing chunk-4 write")
        for e in service_writes:
            req(
                (_chunk_lo(3) <= e.get("lba", -1) and e.get("lba", -1) + e.get("count", 0) <= _chunk_lo(4))
                or (_chunk_lo(4) <= e.get("lba", -1) and e.get("lba", -1) + e.get("count", 0) <= _chunk_lo(5)),
                "multi-chunk service wrote outside chunks 3-4",
            )
    elif cid == "WP09-SP-EMPTY-B":
        req(parse_entries(post.slots[3]) == [(3, 0, 64)], "empty-B splice shape")
        req(struct.unpack_from("<Q", post.slots[3], 20)[0] == 64, "empty-B total")
        for e in service_writes:
            req(_chunk_lo(3) <= e.get("lba", -1) and e.get("lba", -1) + e.get("count", 0) <= _chunk_lo(4),
                "empty-B splice wrote outside chunk 3")
    elif cid == "WP09-SP-BOUNDARY":
        req(parse_entries(post.slots[3]) == [(0, 0, 128), (3, 0, 64), (1, 0, 128)],
            "exact-boundary splice shape")
        req(struct.unpack_from("<Q", post.slots[3], 20)[0] == 320, "exact-boundary splice total")
        for e in service_writes:
            req(_chunk_lo(3) <= e.get("lba", -1) and e.get("lba", -1) + e.get("count", 0) <= _chunk_lo(4),
                "exact-boundary splice wrote outside chunk 3")
    elif cid == "WP09-STAGE-CLEAR":
        req(struct.unpack_from("<I", post.primary, 124)[0] == 0, "stage not cleared")
        req(struct.unpack_from("<I", post.primary, 128)[0] == 0, "staging chunk not cleared")
        req(struct.unpack_from("<I", post.primary, 12)[0] == 8, "generation not +1")
        req(struct.unpack_from("<I", post.primary, 56)[0] == 4, "H moved during stage clear")
        req(post.primary == post.mirror, "cleared copies diverged")
        arm_events = [e for e in events if e.get("phase") == "arm"]
        req(
            len(arm_events) == 4
            and arm_events[0].get("op") == "write" and arm_events[0].get("lba") == pre.blocks - 1 and arm_events[0].get("count") == 1
            and arm_events[1].get("op") == "flush"
            and arm_events[2].get("op") == "write" and arm_events[2].get("lba") == 0 and arm_events[2].get("count") == 1
            and arm_events[3].get("op") == "flush",
            "stage-clear order is not partner -> flush -> candidate -> flush",
        )
        req(parse_entries(post.slots[3]) == [(3, 0, 64), (4, 0, 64)], "stage-clear record shape")
        req(struct.unpack_from("<Q", post.slots[3], 20)[0] == 128, "stage-clear total")
        for e in service_writes:
            req(_chunk_lo(4) <= e.get("lba", -1) and e.get("lba", -1) + e.get("count", 0) <= _chunk_lo(5),
                "stage-clear recording wrote outside chunk 4")
        last_arm = max((i for i, e in enumerate(events) if e.get("phase") == "arm"), default=-1)
        first_record_write = min(
            (i for i, e in enumerate(events) if e.get("op") == "write" and e.get("phase") in ("service", "commit")),
            default=10**9,
        )
        req(last_arm < first_record_write, "record write occurred before stage clear completed")

    if cid != "WP09-STAGE-CLEAR":
        for e in _writes(events):
            req(not _touches(e, 0) and not _touches(e, pre.blocks - 1), "ordinary record issued superblock write")
        req(post.primary == pre.primary and post.mirror == pre.mirror, "ordinary record changed superblock bytes")
    return err


def synth_extra(cid, pre, mode, mount_side, seek, feed, kind):
    calls = [
        {"phase": "mount", "fn": "tape_mount", "result": "TAPE_OK", "side": mount_side},
        {"phase": "seek", "fn": "tape_seek", "result": "TAPE_OK", "frame": seek},
        {"phase": "arm", "fn": "tape_arm", "result": "TAPE_OK", "mode": mode},
    ]
    events = []
    post = pre

    if kind == "empty":
        calls.append({"phase": "commit", "fn": "tape_commit", "result": "TAPE_OK"})
        probe = min(seek, 255)
        calls.extend(
            [
                {"phase": "tail-seek", "fn": "tape_seek", "result": "TAPE_OK", "frame": probe},
                {"phase": "tail-rate", "fn": "tape_set_rate", "result": "TAPE_OK", "rate_q16_16": 65536},
                {"phase": "tail-service", "fn": "tape_service", "result": "TAPE_OK", "more_work": False},
                {"phase": "tail-render", "fn": "tape_render", "result": "TAPE_OK", "requested": 1, "rendered": 1, "events_from_call": 0},
                {"phase": "tail-stop", "fn": "tape_set_rate", "result": "TAPE_OK", "rate_q16_16": 0},
            ]
        )
    else:
        calls.append(
            {
                "phase": "feed",
                "fn": "tape_feed",
                "result": "TAPE_OK",
                "requested": feed,
                "accepted": feed,
                "events_from_call": 0,
            }
        )
        calls.append({"phase": "service", "fn": "tape_service", "result": "TAPE_OK", "more_work": False})
        calls.append({"phase": "commit", "fn": "tape_commit", "result": "TAPE_OK"})

        slots = list(pre.slots)
        if cid == "WP09-OW-MULTICHUNK":
            slots[3] = idx(1, [(3, 0, feed)], 701)
            post = Media(pre.blocks, pre.primary, pre.mirror, tuple(slots))
            events = [
                {"phase": "service", "op": "write", "lba": _chunk_lo(3), "count": 1},
                {"phase": "service", "op": "flush"},
                {"phase": "service", "op": "write", "lba": _chunk_lo(4), "count": 1},
                {"phase": "service", "op": "flush"},
            ] + _record_commit_events()
        elif cid == "WP09-SP-EMPTY-B":
            slots[3] = idx(1, [(3, 0, 64)], 701)
            post = Media(pre.blocks, pre.primary, pre.mirror, tuple(slots))
            events = [
                {"phase": "service", "op": "write", "lba": _chunk_lo(3), "count": 1},
                {"phase": "service", "op": "flush"},
            ] + _record_commit_events()
        elif cid == "WP09-SP-BOUNDARY":
            slots[3] = idx(1, [(0, 0, 128), (3, 0, 64), (1, 0, 128)], 701)
            post = Media(pre.blocks, pre.primary, pre.mirror, tuple(slots))
            events = [
                {"phase": "service", "op": "write", "lba": _chunk_lo(3), "count": 1},
                {"phase": "service", "op": "flush"},
            ] + _record_commit_events()
        elif cid == "WP09-STAGE-CLEAR":
            new_sb = cleared_sb(pre)
            slots[3] = idx(1, [(3, 0, 64), (4, 0, 64)], 701)
            post = Media(pre.blocks, new_sb, new_sb, tuple(slots))
            events = [
                {"phase": "arm", "op": "write", "lba": pre.blocks - 1, "count": 1},
                {"phase": "arm", "op": "flush"},
                {"phase": "arm", "op": "write", "lba": 0, "count": 1},
                {"phase": "arm", "op": "flush"},
                {"phase": "service", "op": "write", "lba": _chunk_lo(4), "count": 1},
                {"phase": "service", "op": "flush"},
            ] + _record_commit_events()

    calls.append({"phase": "unmount", "fn": "tape_unmount", "result": "TAPE_OK"})
    calls.append({"phase": "remount", "fn": "tape_mount", "result": "TAPE_OK", "side": "B"})
    return post, events, calls
