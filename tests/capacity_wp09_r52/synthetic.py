#!/usr/bin/env python3
"""Deterministic non-Product observations for the WP-09 R52 oracle."""
from __future__ import annotations

import hashlib
import json
import struct
import zlib

from oracle import (
    BLOCK,
    BLOCKS_PER_CHUNK,
    CHUNK_FRAMES,
    INITIAL_FREE_NEXT,
    INITIAL_SEQUENCE,
    LBA_B0,
    LBA_B1,
    LBA_CHUNK_BASE,
    SEED_FRAMES,
    cases,
    encode_pcm,
    expected_entries,
    expected_pcm,
    prefill_requests,
)


CHUNK_BYTES = BLOCK * BLOCKS_PER_CHUNK
# nominal_length_s whose tapefs §2 ceiling derives exactly total_chunks 4 / 5 / 6 (GEOMETRY_OK).
NOMINAL_LENGTH_S = {4: 9, 5: 12, 6: 15}


def superblock(case):
    """A complete tapefs §4 superblock (ADAPTER.md "Fixture"), primary and mirror identical.

    #126: the earlier synthetic wrote block_count as a u64 at offset 36, where §4 places sample_rate,
    channels and bits_per_sample; the mirror LBA belongs at offset 84.  The oracle never parsed those
    bytes, so no verdict changes; the synthetic fixture now matches the fixture ADAPTER.md specifies."""
    block_count = LBA_CHUNK_BASE + case.total_chunks * BLOCKS_PER_CHUNK + 1
    b = bytearray(BLOCK)
    b[:8] = b"TAPEFS\0\x01"
    struct.pack_into("<HH", b, 8, 1, 0)                      # version 1.0
    struct.pack_into("<I", b, 12, 7)                         # sb_generation
    b[16] = 0                                                # VALID
    b[20:36] = bytes.fromhex("52525252525252525252525252525252")
    struct.pack_into("<IHHI", b, 36, 44100, 2, 16, CHUNK_BYTES)
    struct.pack_into("<I", b, 48, NOMINAL_LENGTH_S[case.total_chunks])
    struct.pack_into("<I", b, 52, case.total_chunks)
    struct.pack_into("<I", b, 56, 2)                         # a_high_water
    struct.pack_into("<I", b, 60, 128 * BLOCK)               # index slot bytes
    struct.pack_into("<IIIIII", b, 64, 8, 136, LBA_B0, LBA_B1, LBA_CHUNK_BASE, block_count - 1)
    struct.pack_into("<I", b, 508, zlib.crc32(b[:508]))
    return b.hex()


def slot(sequence, entries):
    h = bytearray(BLOCK)
    h[:8] = b"TAPEIDX\x01"
    struct.pack_into("<I", h, 8, sequence)
    h[12] = 1
    struct.pack_into("<I", h, 16, len(entries))
    struct.pack_into("<Q", h, 20, sum(entry[2] for entry in entries))
    raw_entries = b"".join(struct.pack("<III", *entry) for entry in entries)
    struct.pack_into("<I", h, 60, zlib.crc32(h[:60] + raw_entries))
    return {"header": h.hex(), "entries": raw_entries.hex()}


def invalid_slot():
    return {"header": bytes(BLOCK).hex(), "entries": ""}


def raw_media(case, after=False):
    sb = superblock(case)
    return {
        "primary": sb,
        "mirror": sb,
        "B0": slot(INITIAL_SEQUENCE, [(2, 0, SEED_FRAMES)]),
        "B1": slot(INITIAL_SEQUENCE + 1, expected_entries(case)) if after else invalid_slot(),
    }


def observation(case):
    events = []

    def event(step, op, **fields):
        item = {"step": step, "op": op, "ordinal": len(events) + 1, "rc": 0}
        item.update(fields)
        events.append(item)

    completed_chunks = 0
    service_counter = 0

    def service_after_feed(total_accepted):
        nonlocal completed_chunks, service_counter
        now_complete = total_accepted // CHUNK_FRAMES
        out = []
        if now_complete == completed_chunks:
            label = f"service-{service_counter:04d}"
            service_counter += 1
            out.append({"label": label, "budget": case.service_budget,
                        "result": "TAPE_OK", "more_work": False})
            return out
        if now_complete != completed_chunks + 1:
            raise AssertionError("a feed completed more than one chunk")
        chunk = INITIAL_FREE_NEXT + completed_chunks
        offset = 0
        while offset < BLOCKS_PER_CHUNK:
            count = min(case.service_budget, BLOCKS_PER_CHUNK - offset)
            label = f"service-{service_counter:04d}"
            service_counter += 1
            event(label, "write", lba=LBA_CHUNK_BASE + chunk * BLOCKS_PER_CHUNK + offset,
                  count=count)
            offset += count
            more = offset < BLOCKS_PER_CHUNK
            if not more:
                event(label, "flush")
            out.append({"label": label, "budget": case.service_budget,
                        "result": "TAPE_OK", "more_work": more})
        completed_chunks = now_complete
        return out

    feed_steps = []
    total_accepted = 0
    for index, requested in enumerate(prefill_requests(case)):
        label = f"feed-{index:04d}"
        total_accepted += requested
        feed_steps.append({
            "label": label,
            "requested": requested,
            "accepted": requested,
            "result": "TAPE_OK",
            "events_from_call": 0,
            "service": service_after_feed(total_accepted),
        })

    total_accepted += case.final_accepted
    feed_steps.append({
        "label": "feed-final",
        "requested": case.final_requested,
        "accepted": case.final_accepted,
        "result": "TAPE_ERR_CARTRIDGE_FULL",
        "events_from_call": 0,
        "service": service_after_feed(total_accepted),
    })
    if total_accepted != case.capacity_frames or completed_chunks != case.free_chunks:
        raise AssertionError("synthetic capacity arithmetic")

    event("commit", "write", lba=LBA_B1 + 1, count=1)
    event("commit", "flush")
    event("commit", "write", lba=LBA_B1, count=1)
    event("commit", "flush")

    block_count = LBA_CHUNK_BASE + case.total_chunks * BLOCKS_PER_CHUNK + 1
    for lba in (0, block_count - 1, LBA_B0, LBA_B1):
        event("remount", "read", lba=lba, count=1)

    before = raw_media(case)
    expected = expected_pcm(case)
    obs = {
        "schema": "wp09-capacity-r52-v1",
        "case": case.id,
        "fixture_sha256": hashlib.sha256(json.dumps(
            before, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "raw_before": before,
        "raw_after": raw_media(case, after=True),
        "calls": {
            "mount": {"result": "TAPE_OK"},
            "info_before": {"result": "TAPE_OK", "total_frames": SEED_FRAMES,
                            "entry_count": 1, "total_chunks": case.total_chunks,
                            "free_chunks": case.free_chunks},
            "seek": {"frame": case.at, "result": "TAPE_OK"},
            "arm": {"mode": case.mode, "result": "TAPE_OK"},
            "feed_steps": feed_steps,
            "premature_commit": {"result": "TAPE_ERR_BUSY", "events_from_call": 0},
            "status_after_service": {"result": "TAPE_OK", "frames_owed": False},
            "commit": {"result": "TAPE_OK"},
            "unmount": {"result": "TAPE_OK"},
            "remount": {"result": "TAPE_OK"},
            "info_after": {"result": "TAPE_OK", "total_frames": len(expected),
                           "entry_count": len(expected_entries(case)),
                           "total_chunks": case.total_chunks, "free_chunks": 0},
            "render": {"result": "TAPE_OK", "rendered": len(expected),
                       "events_from_call": 0, "pcm_zlib_b64": encode_pcm(expected)},
        },
        "events": events,
    }
    return obs


def observations_bytes():
    return b"".join((json.dumps(observation(case), sort_keys=True,
                                separators=(",", ":")) + "\n").encode()
                    for case in cases())
