#!/usr/bin/env python3
"""Verifier-owned compact virtual-media fixtures for WP-07."""
from __future__ import annotations

import hashlib
import struct
import zlib

CHUNK_FRAMES = 131_072
SAMPLE_RATE = 44_100
NOMINAL_LENGTH_S = 60
CHUNK_BYTES = 524_288
BLOCK = 512
CHUNK_BLOCKS = CHUNK_BYTES // BLOCK
SLOT_BYTES = 65_536
LBA_A0, LBA_A1, LBA_B0, LBA_B1, LBA_CHUNK_BASE = 8, 136, 264, 392, 2048
TOTAL_CHUNKS = (NOMINAL_LENGTH_S * SAMPLE_RATE + CHUNK_FRAMES - 1) // CHUNK_FRAMES
BLOCK_COUNT = LBA_CHUNK_BASE + TOTAL_CHUNKS * CHUNK_BLOCKS + 1
FUZZ_A_HIGH_WATER = 3
RESET_A_HIGH_WATER = 1


def _superblock(a_high_water: int, generation: int = 7) -> bytes:
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
    struct.pack_into("<I", b, 48, NOMINAL_LENGTH_S)
    struct.pack_into("<I", b, 52, TOTAL_CHUNKS)
    struct.pack_into("<I", b, 56, a_high_water)
    struct.pack_into("<I", b, 60, SLOT_BYTES)
    struct.pack_into("<I", b, 64, LBA_A0)
    struct.pack_into("<I", b, 68, LBA_A1)
    struct.pack_into("<I", b, 72, LBA_B0)
    struct.pack_into("<I", b, 76, LBA_B1)
    struct.pack_into("<I", b, 80, LBA_CHUNK_BASE)
    struct.pack_into("<I", b, 84, BLOCK_COUNT - 1)
    b[88:104] = b"WP07-VERIFIER\0\0\0"
    struct.pack_into("<I", b, 508, zlib.crc32(b[:508]))
    return bytes(b)


def make_index(side: int, sequence: int, entries: list[tuple[int, int, int]]) -> bytes:
    if side not in (0, 1):
        raise ValueError("invalid side")
    if len(entries) > 4096:
        raise ValueError("too many entries")
    b = bytearray(SLOT_BYTES)
    b[:8] = b"TAPEIDX\x01"
    total = sum(frame_count for _, _, frame_count in entries)
    struct.pack_into("<IB3xIQ", b, 8, sequence, side, len(entries), total)
    off = 512
    for first, start, count in entries:
        struct.pack_into("<III", b, off, first, start, count)
        off += 12
    payload = b[:60] + b[512 : 512 + 12 * len(entries)]
    struct.pack_into("<I", b, 60, zlib.crc32(payload))
    return bytes(b)


def _vo08(sb: bytes, a0: bytes, a1: bytes, b0: bytes, b1: bytes) -> bytes:
    return (
        b"VO08"
        + struct.pack("<I", BLOCK_COUNT)
        + sb
        + sb
        + a0
        + a1
        + b0
        + b1
    )


def fuzz_entries_a() -> list[tuple[int, int, int]]:
    return [(0, 0, 3 * CHUNK_FRAMES)]


def fuzz_entries_b() -> list[tuple[int, int, int]]:
    # Two legal entries share chunk 0 but occupy adjacent, disjoint frame ranges.
    return [
        (0, 0, CHUNK_FRAMES // 2),
        (0, CHUNK_FRAMES // 2, CHUNK_FRAMES // 2),
        (1, 0, CHUNK_FRAMES),
        (2, 0, CHUNK_FRAMES),
    ]


def reset_stress_entries_a() -> list[tuple[int, int, int]]:
    # Maximal entry count while staying entirely inside one A-owned chunk.
    # Every interval is one physical frame, so the 4096 entries are disjoint.
    return [(0, i, 1) for i in range(4096)]


def build_fuzz_fixture() -> bytes:
    sb = _superblock(FUZZ_A_HIGH_WATER)
    return _vo08(
        sb,
        make_index(0, 10, fuzz_entries_a()),
        bytes(SLOT_BYTES),
        make_index(1, 20, fuzz_entries_b()),
        bytes(SLOT_BYTES),
    )


def build_reset_stress_fixture() -> bytes:
    sb = _superblock(RESET_A_HIGH_WATER, generation=11)
    return _vo08(
        sb,
        make_index(0, 100, reset_stress_entries_a()),
        bytes(SLOT_BYTES),
        make_index(1, 101, [(0, 0, 4096)]),
        bytes(SLOT_BYTES),
    )


def slot_snapshot(slot: bytes) -> dict:
    if len(slot) != SLOT_BYTES:
        raise ValueError("wrong slot size")
    count = struct.unpack_from("<I", slot, 16)[0] if slot[:8] == b"TAPEIDX\x01" else 0
    entry_bytes = slot[512 : 512 + min(count, 4096) * 12]
    return {"header_hex": slot[:64].hex(), "entries_hex": entry_bytes.hex()}


def fuzz_initial_b_slots() -> list[dict]:
    return [
        slot_snapshot(make_index(1, 20, fuzz_entries_b())),
        slot_snapshot(bytes(SLOT_BYTES)),
    ]


def reset_initial_b_slots() -> list[dict]:
    return [
        slot_snapshot(make_index(1, 101, [(0, 0, 4096)])),
        slot_snapshot(bytes(SLOT_BYTES)),
    ]


def fixture_digests() -> dict:
    return {
        "fuzz_sha256": hashlib.sha256(build_fuzz_fixture()).hexdigest(),
        "reset_stress_sha256": hashlib.sha256(build_reset_stress_fixture()).hexdigest(),
    }
