#!/usr/bin/env python3
"""Fixtures and expectations for the three #126 strengthening rows (DRAFT-9)."""
from __future__ import annotations

import hashlib
import struct
import zlib

import pins

DM, B, C69, FINAL, CAP = pins.DM, pins.R29B, pins.C69, pins.FINAL, pins.CAP
BLOCK = 512
FRAME = 4


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ------------------------------------------------------------------ row 1: dup copies every audio block

ROW1 = "WP10.dup.destination_shape.copied_audio_every_block"
CF = DM.CF
DUP_FRAMES = (128, 129, 1000, CF, CF + 1, 2 * CF + 77)   # one block, a block boundary, many blocks, a whole
DUP_DESTS = ("blank", "healthy_pair")                     # chunk, a chunk boundary, three chunks
TOTAL_CHUNKS = B.TOTAL_CHUNKS                             # R29-B geometry: 4 chunks / 9 s


def source_frame(chunk: int, frame: int) -> bytes:
    """Coordinate-unique, non-zero source PCM (FINAL.frame_bytes, #118)."""
    return FINAL.frame_bytes(chunk, frame)


def old_frame(chunk: int, frame: int) -> bytes:
    """Coordinate-unique destination pre-image, disjoint from every source frame (high byte tag 0x3C)."""
    v = (chunk << 17) | frame
    return struct.pack("<HH", v & 0xFFFF, (v >> 16) | 0x3C00)


def _chunk(fn, c):
    return b"".join(fn(c, f) for f in range(CF))


def dup_len(frames):
    return -(-frames // CF)


def dup_source_image(frames):
    """Separate source device on the R29-B geometry: Side A {0,0,frames}, Side B a valid empty index,
    every frame of chunks [0, len_A) the coordinate-unique source pattern."""
    img = bytearray(B.BLOCK_COUNT * BLOCK)
    sb = B.superblock(generation=1, uuid=B.OLD_UUID_B, high=dup_len(frames))
    img[0:BLOCK] = sb
    img[B.LBA_MIRROR * BLOCK:(B.LBA_MIRROR + 1) * BLOCK] = sb
    a_h, a_e = DM.index_blocks(0, 1, [(0, 0, frames)])
    b_h, _ = DM.index_blocks(1, 2, [])
    img[B.LBA_A0 * BLOCK:(B.LBA_A0 + 2) * BLOCK] = a_h + a_e
    img[B.LBA_B0 * BLOCK:(B.LBA_B0 + 1) * BLOCK] = b_h
    for c in range(dup_len(frames)):
        base = (B.LBA_CHUNK_BASE + c * 1024) * BLOCK
        img[base:base + 1024 * BLOCK] = _chunk(source_frame, c)
    return bytes(img)


def dup_destination_image(shape):
    """#116 destination shapes; a reusable destination carries a non-zero pre-image in every chunk."""
    img = bytearray(B.BLOCK_COUNT * BLOCK)
    for name, data in DM.rerun_destination(shape).items():
        lba = DM.TRACKED[name]
        img[lba * BLOCK:(lba + 1) * BLOCK] = data
    if shape != "blank":
        for c in range(TOTAL_CHUNKS):
            base = (B.LBA_CHUNK_BASE + c * 1024) * BLOCK
            img[base:base + 1024 * BLOCK] = _chunk(old_frame, c)
    return bytes(img)


def dup_expected_timeline(frames):
    """Source Side A rendered from the pattern alone (never from an image)."""
    return b"".join(source_frame(k // CF, k % CF) for k in range(frames))


# ------------------------------------------------------------------ row 2: WP-06f re-spool pass-2 run branch

ROW2 = "WP06f.sideA_liveB.respool_pass2_run"
N = C69.CHUNK_FRAMES
PASS2_HIGH = 2
PASS2_A = [(0, 0, 10)]
PASS2_B = [(2, 0, 10), (3, 0, 10)]           # dense over [a_high_water, floor) = [2, 4); len 1 <= floor - H = 2
RS_BUDGET = 64


def pass2_image():
    return FINAL.cartridge(high=PASS2_HIGH, slots=[("A0", 0, 10, PASS2_A), ("B0", 1, 20, PASS2_B)],
                           audio_chunks=(0, 2, 3))


def pass2_floor():
    return max(f + (s + n - 1) // N + 1 for f, s, n in PASS2_B)


def pass2_len():
    return -(-sum(e[2] for e in PASS2_B) // N)


# ------------------------------------------------------------------ row 3: #99 capacity A-slot premise

ROW3 = "WP09.capacity.fixture_a_slot_premise"


def a0_empty_slot():
    """The fixture ADAPTER.md specifies: a structurally valid, empty Side-A index at sequence 1."""
    h = bytearray(BLOCK)
    h[:8] = b"TAPEIDX\x01"
    struct.pack_into("<I", h, 8, 1)
    h[12] = 0
    struct.pack_into("<I", h, 16, 0)
    struct.pack_into("<Q", h, 20, 0)
    struct.pack_into("<I", h, 60, zlib.crc32(bytes(h[:60])))
    return {"header": bytes(h).hex(), "entries": ""}


def invalid_slot():
    return {"header": bytes(BLOCK).hex(), "entries": ""}
