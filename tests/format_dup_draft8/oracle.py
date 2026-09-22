#!/usr/bin/env python3
"""Independent DRAFT-8 format / duplicate / empty-promote refusal oracle.

Covers TapeFS §9.5 items 1–4 and §9.6 preconditions (zero-write refusals),
Engine API invariant 18 / 22 / 30 empty-promote. Does not encode WP-10 crash
tables or identity-assignment success paths.
"""
from __future__ import annotations

import hashlib
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

CF = 131072
SAMPLE_RATE = 44100
NOMINAL_LENGTH_S = 60
CHUNK_BYTES = 524288
BLOCK = 512
BLOCKS_PER_CHUNK = CHUNK_BYTES // BLOCK
SLOT_BYTES = 65536
LBA_A0, LBA_A1, LBA_B0, LBA_B1, LBA_CHUNK_BASE = 8, 136, 264, 392, 2048

STRICT_NO_CALLBACK_IDS = frozenset({
    "FMT-GEOM-0", "FMT-GEOM-1", "FMT-GEOM-BASE",
    "DUP-GEOM-0", "DUP-GEOM-1", "DUP-GEOM-BASE",
})


class VerificationError(Exception):
    pass


def req(cond, msg):
    if not cond:
        raise VerificationError(msg)


def shafile(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass(frozen=True)
class Media:
    blocks: int
    primary: bytes
    mirror: bytes
    slots: tuple[bytes, bytes, bytes, bytes]

    def encode(self) -> bytes:
        return b"VO08" + struct.pack("<I", self.blocks) + self.primary + self.mirror + b"".join(self.slots)

    @staticmethod
    def decode(data: bytes) -> "Media":
        need = 8 + 2 * BLOCK + 4 * SLOT_BYTES
        if len(data) != need or data[:4] != b"VO08":
            raise ValueError("bad VO08")
        blocks = struct.unpack_from("<I", data, 4)[0]
        p = 8
        primary = data[p : p + BLOCK]
        p += BLOCK
        mirror = data[p : p + BLOCK]
        p += BLOCK
        slots = [data[p + i * SLOT_BYTES : p + (i + 1) * SLOT_BYTES] for i in range(4)]
        return Media(blocks, primary, mirror, tuple(slots))


@dataclass(frozen=True)
class Case:
    id: str
    kind: str
    pre: Media
    dest_blocks: int
    dest_nominal: int
    dest_writable: bool
    dest_aliases: bool
    expect: str
    expect_more_work: bool | None


def derived_total_chunks(nominal=NOMINAL_LENGTH_S) -> int:
    return (nominal * SAMPLE_RATE + CF - 1) // CF


def min_blocks_for_nominal(nominal=NOMINAL_LENGTH_S) -> int:
    return LBA_CHUNK_BASE + derived_total_chunks(nominal) * BLOCKS_PER_CHUNK + 1


def sb(*, generation=7, high=3, chunks=None, blocks=None, nominal=NOMINAL_LENGTH_S, stage=0) -> bytes:
    if chunks is None:
        chunks = derived_total_chunks(nominal)
    if blocks is None:
        blocks = min_blocks_for_nominal(nominal)
    b = bytearray(BLOCK)
    b[:8] = b"TAPEFS\0\x01"
    struct.pack_into("<H", b, 8, 1)
    struct.pack_into("<H", b, 10, 0)
    struct.pack_into("<I", b, 12, generation)
    b[20:36] = bytes(range(16))
    struct.pack_into("<I", b, 36, SAMPLE_RATE)
    struct.pack_into("<H", b, 40, 2)
    struct.pack_into("<H", b, 42, 16)
    struct.pack_into("<I", b, 44, CHUNK_BYTES)
    struct.pack_into("<I", b, 48, nominal)
    struct.pack_into("<I", b, 52, chunks)
    struct.pack_into("<I", b, 56, high)
    struct.pack_into("<I", b, 60, SLOT_BYTES)
    struct.pack_into("<I", b, 64, LBA_A0)
    struct.pack_into("<I", b, 68, LBA_A1)
    struct.pack_into("<I", b, 72, LBA_B0)
    struct.pack_into("<I", b, 76, LBA_B1)
    struct.pack_into("<I", b, 80, LBA_CHUNK_BASE)
    struct.pack_into("<I", b, 84, blocks - 1)
    struct.pack_into("<I", b, 124, stage)
    struct.pack_into("<I", b, 508, zlib.crc32(b[:508]))
    return bytes(b)


def idx(side: int, entries, sequence: int) -> bytes:
    b = bytearray(SLOT_BYTES)
    b[:8] = b"TAPEIDX\x01"
    total = sum(e[2] for e in entries)
    struct.pack_into("<IB3xIQ", b, 8, sequence, side, len(entries), total)
    for i, e in enumerate(entries):
        struct.pack_into("<III", b, 512 + 12 * i, *e)
    crc = zlib.crc32(b[:60] + b[512 : 512 + 12 * len(entries)])
    struct.pack_into("<I", b, 60, crc)
    return bytes(b)


def invalid_slot() -> bytes:
    return bytes(SLOT_BYTES)


def source_media(*, a_frames=256, b_entries=None) -> Media:
    chunks = derived_total_chunks(NOMINAL_LENGTH_S)
    blocks = LBA_CHUNK_BASE + chunks * BLOCKS_PER_CHUNK + 1
    s = sb(chunks=chunks, blocks=blocks, high=max(3, (a_frames + CF - 1) // CF))
    if b_entries is None:
        b_entries = [(0, 0, a_frames)]
    return Media(
        blocks,
        s,
        s,
        (
            idx(0, [(0, 0, a_frames)] if a_frames else [], 10 if a_frames else 1),
            invalid_slot(),
            idx(1, b_entries, 20) if b_entries else idx(1, [], 20),
            invalid_slot(),
        ),
    )


def empty_b_media() -> Media:
    chunks = derived_total_chunks(NOMINAL_LENGTH_S)
    blocks = LBA_CHUNK_BASE + chunks * BLOCKS_PER_CHUNK + 1
    s = sb(chunks=chunks, blocks=blocks, high=3)
    return Media(
        blocks,
        s,
        s,
        (
            idx(0, [(0, 0, 128)], 10),
            invalid_slot(),
            idx(1, [], 20),
            invalid_slot(),
        ),
    )


def make_cases() -> list[Case]:
    src = source_media()
    src_long = source_media(a_frames=CF + 1)
    empty_b = empty_b_media()
    dest_ok_blocks = src.blocks
    fit_minus_one = min_blocks_for_nominal(NOMINAL_LENGTH_S) - 1
    return [
        Case("FMT-RO", "format", src, dest_ok_blocks, NOMINAL_LENGTH_S, False, False, "TAPE_ERR_READ_ONLY", None),
        Case("FMT-GEOM-0", "format", src, 0, NOMINAL_LENGTH_S, True, False, "TAPE_ERR_GEOMETRY", None),
        Case("FMT-GEOM-1", "format", src, 1, NOMINAL_LENGTH_S, True, False, "TAPE_ERR_GEOMETRY", None),
        Case("FMT-GEOM-BASE", "format", src, LBA_CHUNK_BASE, NOMINAL_LENGTH_S, True, False, "TAPE_ERR_GEOMETRY", None),
        Case("FMT-GEOM-FIT", "format", src, fit_minus_one, NOMINAL_LENGTH_S, True, False, "TAPE_ERR_GEOMETRY", None),
        Case("FMT-ORDER-RO", "format", src, 0, NOMINAL_LENGTH_S, False, False, "TAPE_ERR_READ_ONLY", None),
        Case("DUP-ALIAS", "dup", src, dest_ok_blocks, NOMINAL_LENGTH_S, True, True, "TAPE_ERR_INVALID_ARG", False),
        Case("DUP-RO", "dup", src, dest_ok_blocks, NOMINAL_LENGTH_S, False, False, "TAPE_ERR_READ_ONLY", False),
        Case("DUP-GEOM-0", "dup", src, 0, NOMINAL_LENGTH_S, True, False, "TAPE_ERR_GEOMETRY", False),
        Case("DUP-GEOM-1", "dup", src, 1, NOMINAL_LENGTH_S, True, False, "TAPE_ERR_GEOMETRY", False),
        Case("DUP-GEOM-BASE", "dup", src, LBA_CHUNK_BASE, NOMINAL_LENGTH_S, True, False, "TAPE_ERR_GEOMETRY", False),
        Case("DUP-GEOM-FIT", "dup", src, fit_minus_one, NOMINAL_LENGTH_S, True, False, "TAPE_ERR_GEOMETRY", False),
        Case("DUP-TOO-SMALL", "dup", src_long, LBA_CHUNK_BASE + BLOCKS_PER_CHUNK + 2, 1, True, False, "TAPE_ERR_DEST_TOO_SMALL", False),
        Case("DUP-ORDER-ALIAS", "dup", src_long, 0, 1, False, True, "TAPE_ERR_INVALID_ARG", False),
        Case("DUP-ORDER-RO", "dup", src_long, LBA_CHUNK_BASE, 1, False, False, "TAPE_ERR_READ_ONLY", False),
        Case("DUP-ORDER-GEOM", "dup", src_long, LBA_CHUNK_BASE, 1, True, False, "TAPE_ERR_GEOMETRY", False),
        Case("PROMOTE-EMPTY", "promote", empty_b, empty_b.blocks, NOMINAL_LENGTH_S, True, False, "TAPE_ERR_INVALID_ARG", False),
    ]


def _writes(events):
    return [e for e in events if e.get("op") == "write"]


def _touches_lba(event, lba: int) -> bool:
    if event.get("op") != "read":
        return False
    try:
        first = int(event["lba"])
        count = int(event.get("count", 1))
    except (KeyError, TypeError, ValueError):
        return False
    return count > 0 and first <= lba < first + count


def _destination_superblock_reads(case: Case, events):
    mirror = case.dest_blocks - 1 if case.dest_blocks > 0 else None
    out = []
    for e in events:
        if e.get("device") != "destination":
            continue
        if _touches_lba(e, 0) or (mirror is not None and _touches_lba(e, mirror)):
            out.append(e)
    return out


def check(case: Case, post: Media, events: list[dict], calls: list[dict]) -> list[str]:
    err = []

    def need(cond, msg):
        if not cond:
            err.append(msg)

    need(post.encode() == case.pre.encode(), "refusal changed tracked media")
    need(not _writes(events), "refusal issued a write")

    if case.id in STRICT_NO_CALLBACK_IDS:
        need(events == [], "DEVICE_ADDRESSABLE geometry refusal issued a callback")

    if case.kind in ("format", "dup"):
        need(not _destination_superblock_reads(case, events), "refusal read destination superblock")

    if case.kind == "format":
        hits = [c for c in calls if c.get("fn") == "tape_format"]
        need(bool(hits), "missing tape_format call")
        if hits:
            need(hits[0].get("result") == case.expect, "format result mismatch")
    elif case.kind == "dup":
        hits = [c for c in calls if c.get("fn") == "tape_dup"]
        need(bool(hits), "missing tape_dup call")
        if hits:
            need(hits[0].get("result") == case.expect, "dup result mismatch")
            need(hits[0].get("more_work") is False, "dup refusal left more_work true")
            if case.dest_aliases:
                need(hits[0].get("aliased") is True, "alias case did not record dest alias")
    elif case.kind == "promote":
        mounts = [c for c in calls if c.get("fn") == "tape_mount"]
        need(bool(mounts), "missing promote setup mount")
        if mounts:
            need(mounts[0].get("result") == "TAPE_OK", "promote case failed to mount")
        hits = [c for c in calls if c.get("fn") == "tape_promote"]
        need(bool(hits), "missing tape_promote call")
        if hits:
            need(hits[0].get("result") == case.expect, "empty promote result mismatch")
            need(hits[0].get("more_work") is False, "empty promote left more_work true")
    else:
        need(False, "unknown case kind")
    return err


def validate_observation(case: Case, post_bytes: bytes, observation: dict) -> list[str]:
    err = []
    if observation.get("format") != "WP-FMTDUP-OBSERVATION-1":
        err.append("observation format mismatch")
    if observation.get("case_id") != case.id:
        err.append("observation case_id mismatch")
    if observation.get("adapter_kind") not in ("synthetic", "product"):
        err.append("invalid adapter_kind")
    if not isinstance(observation.get("adapter_id"), str) or not observation.get("adapter_id", "").strip():
        err.append("missing adapter_id")
    calls = observation.get("calls")
    events = observation.get("events")
    if not isinstance(calls, list):
        err.append("calls is not a list")
        calls = []
    if not isinstance(events, list):
        err.append("events is not a list")
        events = []
    try:
        post = Media.decode(post_bytes)
    except (ValueError, struct.error) as e:
        return err + [f"bad output media: {e}"]
    return err + check(case, post, events, calls)


def synth_observation(case: Case):
    if case.kind == "format":
        calls = [
            {
                "phase": "format",
                "fn": "tape_format",
                "result": case.expect,
                "block_count": case.dest_blocks,
                "writable": case.dest_writable,
                "events_from_call": 0,
            }
        ]
    elif case.kind == "dup":
        calls = [
            {"phase": "mount", "fn": "tape_mount", "result": "TAPE_OK", "side": "A"},
            {
                "phase": "dup",
                "fn": "tape_dup",
                "result": case.expect,
                "more_work": False,
                "block_count": case.dest_blocks,
                "writable": case.dest_writable,
                "aliased": case.dest_aliases,
                "dst_nominal_length_s": case.dest_nominal,
                "events_from_call": 0,
            },
            {"phase": "unmount", "fn": "tape_unmount", "result": "TAPE_OK"},
        ]
    else:
        calls = [
            {"phase": "mount", "fn": "tape_mount", "result": "TAPE_OK", "side": "B"},
            {
                "phase": "promote",
                "fn": "tape_promote",
                "result": case.expect,
                "more_work": False,
                "block_budget": 64,
                "events_from_call": 0,
            },
            {"phase": "unmount", "fn": "tape_unmount", "result": "TAPE_OK"},
        ]
    return case.pre, [], calls
