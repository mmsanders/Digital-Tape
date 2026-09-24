#!/usr/bin/env python3
"""Verifier-owned raw TAPEFS fixtures for the bounded DRAFT-8 WP-10 core tranche."""
from __future__ import annotations

import hashlib
import struct
import zlib

BLOCK = 512
CHUNK_FRAMES = 131_072
CHUNK_BLOCKS = 1_024
CHUNK_BYTES = BLOCK * CHUNK_BLOCKS
SLOT_BLOCKS = 128
SLOT_BYTES = BLOCK * SLOT_BLOCKS

LBA_PRIMARY = 0
LBA_A0 = 8
LBA_A1 = 136
LBA_B0 = 264
LBA_B1 = 392
LBA_CHUNK_BASE = 2_048

NOMINAL_LENGTH_S = 12
SAMPLE_RATE = 44_100
TOTAL_CHUNKS = (NOMINAL_LENGTH_S * SAMPLE_RATE + CHUNK_FRAMES - 1) // CHUNK_FRAMES
BLOCK_COUNT = LBA_CHUNK_BASE + TOTAL_CHUNKS * CHUNK_BLOCKS + 1
LBA_MIRROR = BLOCK_COUNT - 1

assert TOTAL_CHUNKS == 5

MAGIC_SB = b"TAPEFS\0\x01"
MAGIC_IDX = b"TAPEIDX\x01"


def crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def build_superblock(
    *,
    generation: int,
    a_high_water: int,
    promote_stage: int = 0,
    promote_staging_chunk: int = 0,
) -> bytes:
    b = bytearray(BLOCK)
    b[:8] = MAGIC_SB
    struct.pack_into("<H", b, 8, 1)
    struct.pack_into("<H", b, 10, 0)
    struct.pack_into("<I", b, 12, generation)
    b[16] = 0  # VALID
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
    struct.pack_into("<I", b, 84, LBA_MIRROR)
    b[88:105] = b"WP10-CORE-DRAFT8\0"
    struct.pack_into("<I", b, 120, 0x10203040)
    struct.pack_into("<I", b, 124, promote_stage)
    struct.pack_into("<I", b, 128, promote_staging_chunk)
    struct.pack_into("<I", b, 508, crc32(b[:508]))
    return bytes(b)


def build_index(
    side: int,
    sequence: int,
    entries: list[tuple[int, int, int]],
) -> bytes:
    b = bytearray(SLOT_BYTES)
    b[:8] = MAGIC_IDX
    total_frames = sum(int(e[2]) for e in entries)
    struct.pack_into("<IB3xIQ", b, 8, sequence, side, len(entries), total_frames)
    off = BLOCK
    for first, start, count in entries:
        struct.pack_into("<III", b, off, first, start, count)
        off += 12
    covered = b[:60] + b[BLOCK : BLOCK + 12 * len(entries)]
    struct.pack_into("<I", b, 60, crc32(covered))
    return bytes(b)


def _chunk_bytes(chunk_id: int) -> bytes:
    # Distinct deterministic payload per chunk; no audio/golden meaning is claimed.
    seed = hashlib.sha256(f"WP10-CORE-CHUNK-{chunk_id}".encode("ascii")).digest()
    return (seed * (CHUNK_BYTES // len(seed) + 1))[:CHUNK_BYTES]


def blank_image() -> bytearray:
    return bytearray(BLOCK_COUNT * BLOCK)


def _put(image: bytearray, lba: int, payload: bytes) -> None:
    start = lba * BLOCK
    image[start : start + len(payload)] = payload


def _base_image(primary: bytes, mirror: bytes) -> bytearray:
    image = blank_image()
    _put(image, LBA_PRIMARY, primary)
    _put(image, LBA_MIRROR, mirror)
    for chunk in range(TOTAL_CHUNKS):
        _put(image, LBA_CHUNK_BASE + chunk * CHUNK_BLOCKS, _chunk_bytes(chunk))
    return image


def record_fixture() -> bytes:
    sb = build_superblock(generation=10, a_high_water=2)
    image = _base_image(sb, sb)
    _put(image, LBA_A0, build_index(0, 10, [(0, 0, CHUNK_FRAMES)]))
    _put(image, LBA_B0, build_index(1, 20, [(0, 0, CHUNK_FRAMES)]))
    return bytes(image)


def expected_record_post_entries(mode: str) -> list[tuple[int, int, int]]:
    if mode == "overwrite":
        return [(2, 0, 1)]
    if mode == "overdub":
        return [(2, 0, 1), (0, 1, CHUNK_FRAMES - 1)]
    if mode == "splice":
        return [(2, 0, 1), (0, 0, CHUNK_FRAMES)]
    raise ValueError(f"unknown record mode {mode!r}")


def expected_record_post_slot(mode: str) -> bytes:
    return build_index(1, 21, expected_record_post_entries(mode))


def reset_healthy_fixture() -> bytes:
    sb = build_superblock(generation=10, a_high_water=2)
    image = _base_image(sb, sb)
    _put(image, LBA_A0, build_index(0, 10, [(0, 0, CHUNK_FRAMES)]))
    _put(image, LBA_B0, build_index(1, 20, [(1, 0, CHUNK_FRAMES)]))
    return bytes(image)


def expected_reset_healthy_post_slot() -> bytes:
    return build_index(1, 21, [(0, 0, CHUNK_FRAMES)])


def reset_degraded_equal_fixture() -> bytes:
    sb = build_superblock(generation=10, a_high_water=2)
    image = _base_image(sb, sb)
    _put(image, LBA_A0, build_index(0, 10, [(0, 0, CHUNK_FRAMES)]))
    # Both B slots are individually valid, same sequence, different entries.
    # Mount Side A is degraded-B. Reset writes B0 directly at sequence 501.
    _put(image, LBA_B0, build_index(1, 500, [(1, 0, CHUNK_FRAMES)]))
    _put(image, LBA_B1, build_index(1, 500, [(0, 0, CHUNK_FRAMES)]))
    return bytes(image)


def expected_reset_degraded_post_slot() -> bytes:
    return build_index(1, 501, [(0, 0, CHUNK_FRAMES)])


def stage_current_superblock() -> bytes:
    # RESUME row 1: A == B == {S,0,N}, H=S+len.
    return build_superblock(
        generation=10,
        a_high_water=3,
        promote_stage=1,
        promote_staging_chunk=2,
    )


def stage_cleared_superblock() -> bytes:
    return build_superblock(
        generation=11,
        a_high_water=3,
        promote_stage=0,
        promote_staging_chunk=0,
    )


def stage_stale_superblock() -> bytes:
    # Deliberately stale water line: if this ever becomes the only selected
    # copy, live Side A at chunk 2 fails last < a_high_water.
    return build_superblock(
        generation=9,
        a_high_water=1,
        promote_stage=0,
        promote_staging_chunk=0,
    )


def _stage_image(primary: bytes, mirror: bytes) -> bytes:
    image = _base_image(primary, mirror)
    entry = [(2, 0, CHUNK_FRAMES)]
    _put(image, LBA_A0, build_index(0, 100, entry))
    _put(image, LBA_B0, build_index(1, 101, entry))
    return bytes(image)


def stage_healthy_fixture() -> bytes:
    sb = stage_current_superblock()
    return _stage_image(sb, sb)


def stage_closure_fixture(seed: str) -> bytes:
    current = stage_current_superblock()
    stale = stage_stale_superblock()
    invalid = bytes(BLOCK)
    if seed == "primary_only":
        return _stage_image(current, invalid)
    if seed == "mirror_only":
        return _stage_image(invalid, current)
    if seed == "primary_newer_mirror_stale":
        return _stage_image(current, stale)
    if seed == "mirror_newer_primary_stale":
        return _stage_image(stale, current)
    raise ValueError(f"unknown closure seed {seed!r}")


def fixture_bytes(family: str, variant: str, *, seed: str | None = None) -> bytes:
    if family == "record_commit":
        return record_fixture()
    if family == "reset_b" and variant == "healthy":
        return reset_healthy_fixture()
    if family == "reset_b" and variant == "degraded_equal":
        return reset_degraded_equal_fixture()
    if family == "stage_clear":
        return stage_closure_fixture(seed) if seed is not None else stage_healthy_fixture()
    raise ValueError((family, variant, seed))


def fixture_digest(family: str, variant: str, *, seed: str | None = None) -> str:
    return hashlib.sha256(fixture_bytes(family, variant, seed=seed)).hexdigest()


def all_fixture_digests() -> dict:
    out = {
        "record_commit": fixture_digest("record_commit", "overwrite"),
        "reset_b:healthy": fixture_digest("reset_b", "healthy"),
        "reset_b:degraded_equal": fixture_digest("reset_b", "degraded_equal"),
        "stage_clear:healthy": fixture_digest("stage_clear", "arm"),
    }
    for seed in (
        "primary_only",
        "mirror_only",
        "primary_newer_mirror_stale",
        "mirror_newer_primary_stale",
    ):
        out[f"stage_clear:{seed}"] = fixture_digest(
            "stage_clear", "arm", seed=seed
        )
    return out
