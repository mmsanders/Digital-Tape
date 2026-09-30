#!/usr/bin/env python3
"""Verifier-owned model for the final WP-10 backlog rows (Verification #118, DRAFT-9).

Rows 1-3 use the accepted C69 geometry and builders (`crash_core_draft8/fixture.py`, pinned in deps.py):
5 chunks, 12 s, superblock/index byte layout identical to the accepted campaign. Row 4 reuses the #116
duplicate model (`dupmodel.py`, byte-identical to #116 `model.py`, pinned by blob below).
"""
from __future__ import annotations

import hashlib
import struct
from pathlib import Path

import deps
import dupmodel as DM

F = deps.C69.fixture
HERE = Path(__file__).resolve().parent
DUPMODEL_BLOB = "53d0b75e83b7a76b539a4d895dc477366a5b3ea2"   # #116 dea9b521 tests/wp10_backlog_r54/model.py
if deps.git_blob_sha(HERE / "dupmodel.py") != DUPMODEL_BLOB:
    raise AssertionError("dupmodel.py drifted from the #116 publication")

N = F.CHUNK_FRAMES
BLOCK = F.BLOCK
FRAME_BYTES = 4
MAX_WRITABLE = 0xFFFFFFFD            # tapefs §4.5 / §10: the largest value a counter may be written as
SLOT_LBA = {"A0": F.LBA_A0, "A1": F.LBA_A1, "B0": F.LBA_B0, "B1": F.LBA_B1}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ------------------------------------------------------------------ media helpers (C69 byte layout)

def put(image: bytearray, lba: int, payload: bytes) -> None:
    image[lba * BLOCK:lba * BLOCK + len(payload)] = payload


def block(image: bytes, lba: int, n: int = 1) -> bytes:
    return bytes(image[lba * BLOCK:(lba + n) * BLOCK])


def frame_bytes(chunk: int, frame: int) -> bytes:
    """Coordinate-unique stereo s16 frame: no two (chunk, frame) pairs on the cartridge share bytes."""
    v = (chunk << 17) | frame
    return struct.pack("<HH", v & 0xFFFF, (v >> 16) | 0x5A00)


def chunk_audio(chunk: int) -> bytes:
    return b"".join(frame_bytes(chunk, f) for f in range(N))


def cartridge(*, generation=10, high=2, stage=0, staging=0, slots=(), audio_chunks=()):
    """C69-layout image: both superblocks identical; `slots` = [(name, side, sequence, entries)]."""
    sb = F.build_superblock(generation=generation, a_high_water=high, promote_stage=stage,
                            promote_staging_chunk=staging)
    image = F.blank_image()
    put(image, F.LBA_PRIMARY, sb)
    put(image, F.LBA_MIRROR, sb)
    for name, side, seq, entries in slots:
        put(image, SLOT_LBA[name], F.build_index(side, seq, entries))
    for c in audio_chunks:
        put(image, F.LBA_CHUNK_BASE + c * F.CHUNK_BLOCKS, chunk_audio(c))
    return bytes(image)


def parse_slot(raw: bytes):
    """tapefs §5.2 structural validity of one slot (header + entry array), or None."""
    if raw[:8] != F.MAGIC_IDX:
        return None
    seq, side, count, total = struct.unpack_from("<IB3xIQ", raw, 8)
    if count * 12 > len(raw) - BLOCK:
        return None
    entries = [struct.unpack_from("<III", raw, BLOCK + 12 * i) for i in range(count)]
    covered = raw[:60] + raw[BLOCK:BLOCK + 12 * count]
    if F.crc32(covered) != struct.unpack_from("<I", raw, 60)[0] or total != sum(e[2] for e in entries):
        return None
    return {"sequence": seq, "side": side, "entries": entries}


def chunks_of(entries):
    out = set()
    for first, start, n in entries:
        out.update(range(first, first + (start + n - 1) // N + 1))
    return out


def render(image: bytes, entries) -> bytes:
    """The side's timeline at 1.0x from frame 0, read straight from chunk bytes (independent of any engine)."""
    out = bytearray()
    for first, start, n in entries:
        base = (F.LBA_CHUNK_BASE + first * F.CHUNK_BLOCKS) * BLOCK + start * FRAME_BYTES
        out += image[base:base + n * FRAME_BYTES]
    return bytes(out)


def timeline(entries) -> bytes:
    """Expected PCM from the fixture's coordinate pattern alone (never reads an image)."""
    out = bytearray()
    for first, start, n in entries:
        for k in range(n):
            abs_frame = first * N + start + k
            out += frame_bytes(abs_frame // N, abs_frame % N)
    return bytes(out)


# ------------------------------------------------------------------ row 1: counters one short (V5-015)

FD, FC = MAX_WRITABLE, MAX_WRITABLE - 1
A_REC = [(0, 0, N)]
STAGE_ENTRY = [(2, 0, N)]


def _reset(seq_b):
    return cartridge(slots=[("A0", 0, 10, A_REC), ("B0", 1, seq_b, [(1, 0, N)])], audio_chunks=(0, 1))


def _reset_degraded(seq_b):
    return cartridge(slots=[("A0", 0, 10, A_REC), ("B0", 1, seq_b, [(1, 0, N)]), ("B1", 1, seq_b, A_REC)],
                     audio_chunks=(0, 1))


def _stage(gen, seq_b):
    """C69 stage-1 fixture (tapefs §9.3.3 RESUME row 1, S = 2, H = 3) with crafted counters."""
    return cartridge(generation=gen, high=3, stage=1, staging=2,
                     slots=[("A0", 0, 100, STAGE_ENTRY), ("B0", 1, seq_b, STAGE_ENTRY)], audio_chunks=(2,))


# id: (fixture builder args, mount side, call, expected result, expectation extras)
ROW1 = {
    "RB-HEALTHY-SEQ-SHORT": (("reset", FD), "B", "tape_reset_side_b", "TAPE_ERR_SEQUENCE_EXHAUSTED", {}),
    "RB-HEALTHY-SEQ-THRESHOLD": (("reset", FC), "B", "tape_reset_side_b", "TAPE_OK",
                                 {"slot": ("B1", FD, A_REC)}),
    "RB-DEGRADED-SEQ-SHORT": (("degraded", FD), "A", "tape_reset_side_b", "TAPE_ERR_SEQUENCE_EXHAUSTED", {}),
    "RB-DEGRADED-SEQ-THRESHOLD": (("degraded", FC), "A", "tape_reset_side_b", "TAPE_OK",
                                  {"slot": ("B0", FD, A_REC)}),
    "SC-RESETB-GEN-SHORT": (("stage", FD, 101), "B", "tape_reset_side_b", "TAPE_ERR_SEQUENCE_EXHAUSTED", {}),
    "SC-RESETB-SEQ-SHORT": (("stage", 10, FD), "B", "tape_reset_side_b", "TAPE_ERR_SEQUENCE_EXHAUSTED", {}),
    "SC-RESETB-THRESHOLD": (("stage", FC, FC), "B", "tape_reset_side_b", "TAPE_OK",
                            {"cleared": FD, "slot": ("B1", FD, STAGE_ENTRY)}),
    "SC-ARM-GEN-SHORT": (("stage", FD, 101), "B", "tape_arm", "TAPE_ERR_SEQUENCE_EXHAUSTED", {}),
    "SC-ARM-SEQ-SHORT": (("stage", 10, FD), "B", "tape_arm", "TAPE_ERR_SEQUENCE_EXHAUSTED", {}),
    "SC-ARM-THRESHOLD": (("stage", FC, FC), "B", "tape_arm", "TAPE_OK", {"cleared": FD, "slots_unchanged": True}),
    "SC-RESPOOL-GEN-SHORT": (("stage", FD, 101), "B", "tape_respool", "TAPE_ERR_SEQUENCE_EXHAUSTED", {}),
    "SC-RESPOOL-SEQ-SHORT": (("stage", 10, FD), "B", "tape_respool", "TAPE_ERR_SEQUENCE_EXHAUSTED", {}),
    # Pass 2 could run from a pass-1 destination at chunk 4, but headroom allows one commit, so §9.4 skips it.
    "SC-RESPOOL-THRESHOLD": (("stage", FC, FC), "B", "tape_respool", "TAPE_OK",
                             {"cleared": FD, "respooled": ("B1", FD, N, 3)}),
}


def row1_image(spec):
    kind, *args = spec
    return {"reset": _reset, "degraded": _reset_degraded, "stage": _stage}[kind](*args)


# ------------------------------------------------------------------ row 2: zero-needed reserved cells

A_SHORT = [(0, 0, 40)]
B_NONEMPTY = [(1, 0, 10)]


def _zn(gen, seq_b, b_entries):
    return cartridge(generation=gen, high=1, slots=[("A0", 0, 10, A_SHORT), ("B0", 1, seq_b, b_entries)],
                     audio_chunks=(0, 1))


ROW2 = {
    # Empty Side B: §9.4 zero-write TAPE_OK; §4.5 a counter whose `needed` is 0 is not consulted (V7-002).
    "ZN-EMPTY-SEQ-FFFFFFFE": ((10, 0xFFFFFFFE, []), "TAPE_OK", {"zero_write": True}),
    "ZN-EMPTY-SEQ-FFFFFFFF": ((10, 0xFFFFFFFF, []), "TAPE_OK", {"zero_write": True}),
    "ZN-EMPTY-GEN-FFFFFFFE": ((0xFFFFFFFE, 20, []), "TAPE_OK", {"zero_write": True}),
    "ZN-EMPTY-GEN-FFFFFFFF": ((0xFFFFFFFF, 20, []), "TAPE_OK", {"zero_write": True}),
    # Converses: the cells pass because `needed` is 0, not because counters are ignored.
    "ZN-NONEMPTY-SEQ-FFFFFFFE": ((10, 0xFFFFFFFE, B_NONEMPTY), "TAPE_ERR_SEQUENCE_EXHAUSTED", {}),
    "ZN-NONEMPTY-GEN-FFFFFFFF": ((0xFFFFFFFF, 20, B_NONEMPTY), "TAPE_OK",
                                 {"respooled_index_only": (21, 22, 10, 1)}),
}


def row2_image(args):
    return _zn(*args)


# ------------------------------------------------------------------ row 3: post-crash re-spool render

A_RS = [(0, 0, 40)]
ROW3 = {
    # id: (a_high_water, live B entries, B0 sequence)
    "RS-TWOPASS": (2, [(2, 0, 40)], 20),
    "RS-REFERENCES-A": (2, [(0, 0, 40)], 20),
    "RS-FRAGMENTED": (1, [(3, 120, 12), (1, 5, 9), (0, 20, 7)], 20),
    "RS-CHUNK-CROSSING": (2, [(2, N - 5, 10)], 20),
    "RS-ONE-COMMIT": (2, [(2, 0, 40)], FC),
}
RS_BUDGET = 64


def row3_image(fid):
    high, b_entries, seq_b = ROW3[fid]
    audio = sorted(chunks_of(A_RS) | chunks_of(b_entries))
    return cartridge(high=high, slots=[("A0", 0, 10, A_RS), ("B0", 1, seq_b, b_entries)], audio_chunks=audio)


# ------------------------------------------------------------------ row 4: crashes inside the dup re-run

OLD_UUID = DM.OLD_UUID.hex()
NEW_UUID = DM.B.FRESH_DUP_UUID.hex()


def interruption_class(img):
    c = DM.classify(img, "A", False)
    kind = None if c["result"] != ("TAPE_OK",) else ("new" if c["uuid"] == NEW_UUID else "old")
    return c["result"][0], kind


def rerun_representatives():
    """One deterministic crashed destination per (shape, tapefs §9.5 interruption class): the first first-run
    injection in plan order whose durable image is unique, so every conforming adapter holds the same bytes."""
    reps = []
    for shape in DM.RERUN_SHAPES:
        base = DM.rerun_destination(shape)
        ops = DM.dup_ops(base)
        seen = set()
        for mode, inject in DM.injections(ops):
            imgs = DM.possible_images(base, ops, inject, mode)
            if len(imgs) != 1:
                continue
            key = interruption_class(imgs[0])
            if key in seen:
                continue
            seen.add(key)
            reps.append({"shape": shape, "class": list(key), "first_mode": mode, "first_inject": list(inject),
                         "crashed": imgs[0]})
    return reps
