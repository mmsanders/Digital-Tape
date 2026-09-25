#!/usr/bin/env python3
"""Verifier-owned raw destination fixtures for DRAFT-8 format/duplicate identity tests."""
from __future__ import annotations
import hashlib, struct, zlib
from dataclasses import dataclass

BLOCK = 512
SLOT_BYTES = 65536
CHUNK_BYTES = 524288
CHUNK_FRAMES = 131072
CHUNK_BLOCKS = CHUNK_BYTES // BLOCK
LBA_A0, LBA_A1, LBA_B0, LBA_B1, LBA_CHUNK_BASE = 8, 136, 264, 392, 2048
TOTAL_CHUNKS = 4
BLOCK_COUNT = LBA_CHUNK_BASE + TOTAL_CHUNKS * CHUNK_BLOCKS + 1
LBA_MIRROR = BLOCK_COUNT - 1
MAGIC_SB = b"TAPEFS\0\x01"
MAGIC_IDX = b"TAPEIDX\x01"
OLD_UUID_A = bytes.fromhex("101112131415161718191a1b1c1d1e1f")
OLD_UUID_B = bytes.fromhex("202122232425262728292a2b2c2d2e2f")
FRESH_FORMAT_UUID = bytes.fromhex("a0a1a2a3a4a5a6a7a8a9aaabacadaeaf")
FRESH_DUP_UUID = bytes.fromhex("b0b1b2b3b4b5b6b7b8b9babbbcbdbebf")

def crc32(b):
    return zlib.crc32(b) & 0xffffffff

def superblock(*, generation=1, state=0, version_major=1, uuid=OLD_UUID_A,
               high=1, nominal=60, promote_stage=0, promote_chunk=0, salt=0):
    b = bytearray(BLOCK)
    b[:8] = MAGIC_SB
    struct.pack_into("<H", b, 8, version_major)
    struct.pack_into("<H", b, 10, 0)
    struct.pack_into("<I", b, 12, generation)
    b[16] = state
    b[20:36] = uuid
    struct.pack_into("<I", b, 36, 44100)
    struct.pack_into("<H", b, 40, 2)
    struct.pack_into("<H", b, 42, 16)
    struct.pack_into("<I", b, 44, CHUNK_BYTES)
    struct.pack_into("<I", b, 48, nominal)
    struct.pack_into("<I", b, 52, TOTAL_CHUNKS)
    struct.pack_into("<I", b, 56, high)
    struct.pack_into("<I", b, 60, SLOT_BYTES)
    struct.pack_into("<I", b, 64, LBA_A0)
    struct.pack_into("<I", b, 68, LBA_A1)
    struct.pack_into("<I", b, 72, LBA_B0)
    struct.pack_into("<I", b, 76, LBA_B1)
    struct.pack_into("<I", b, 80, LBA_CHUNK_BASE)
    struct.pack_into("<I", b, 84, LBA_MIRROR)
    struct.pack_into("<I", b, 112, salt)
    struct.pack_into("<I", b, 124, promote_stage)
    struct.pack_into("<I", b, 128, promote_chunk)
    struct.pack_into("<I", b, 508, crc32(b[:508]))
    return bytes(b)

def wip_template(candidate: bytes | None, *, existing_generation: int):
    if candidate is None:
        b = bytearray(BLOCK)
        b[:8] = MAGIC_SB
        struct.pack_into("<H", b, 8, 1)
        struct.pack_into("<H", b, 10, 0)
        struct.pack_into("<I", b, 12, max(existing_generation, 1) + 1)
        b[16] = 1
        struct.pack_into("<I", b, 124, 0)
        struct.pack_into("<I", b, 128, 0)
        struct.pack_into("<I", b, 508, crc32(b[:508]))
        return bytes(b)
    b = bytearray(candidate)
    struct.pack_into("<H", b, 8, 1)
    struct.pack_into("<H", b, 10, 0)
    struct.pack_into("<I", b, 12, max(existing_generation, 1) + 1)
    b[16] = 1
    struct.pack_into("<I", b, 124, 0)
    struct.pack_into("<I", b, 128, 0)
    struct.pack_into("<I", b, 508, crc32(b[:508]))
    return bytes(b)

def index_head(*, side: int, sequence: int, frames: int):
    b = bytearray(BLOCK)
    b[:8] = MAGIC_IDX
    struct.pack_into("<I", b, 8, sequence)
    b[12] = side
    count = 0 if frames == 0 else 1
    struct.pack_into("<I", b, 16, count)
    struct.pack_into("<Q", b, 20, frames)
    entries = b"" if count == 0 else struct.pack("<III", 0, 0, frames)
    struct.pack_into("<I", b, 60, crc32(bytes(b[:60]) + entries))
    return bytes(b)

OLD_A0 = index_head(side=0, sequence=100, frames=100)
OLD_B0 = index_head(side=1, sequence=101, frames=100)
FORMAT_A0 = index_head(side=0, sequence=1, frames=0)
FORMAT_B0 = index_head(side=1, sequence=2, frames=0)
DUP_A0 = index_head(side=0, sequence=1, frames=100)
DUP_B0 = index_head(side=1, sequence=2, frames=100)

def final_superblock(operation: str):
    if operation == "format":
        return superblock(generation=1, state=0, uuid=FRESH_FORMAT_UUID, high=0)
    if operation == "dup":
        return superblock(generation=1, state=0, uuid=FRESH_DUP_UUID, high=1)
    raise ValueError(operation)

@dataclass(frozen=True)
class RawShape:
    name: str
    primary: bytes
    mirror: bytes
    candidate_copy: str | None
    partner_copy: str
    headroom: bool
    previous_uuid: bytes | None
    step1_bytes: bytes

def _shape(name, primary, mirror, candidate, partner, headroom, previous_uuid):
    gens = []
    for raw in (primary, mirror):
        if raw[:8] == MAGIC_SB and crc32(raw[:508]) == struct.unpack_from("<I", raw, 508)[0]:
            gens.append(struct.unpack_from("<I", raw, 12)[0])
    maxg = max(gens) if gens else 0
    cand_bytes = primary if candidate == "primary" else mirror if candidate == "mirror" else None
    step = bytes(BLOCK) if not headroom else wip_template(cand_bytes, existing_generation=maxg)
    return RawShape(name, primary, mirror, candidate, partner, headroom, previous_uuid, step)

def raw_shapes():
    healthy = superblock(generation=1, uuid=OLD_UUID_A)
    mirror_only = superblock(generation=7, uuid=OLD_UUID_A)
    gen0 = superblock(generation=0, uuid=OLD_UUID_A)
    v2 = superblock(generation=7, version_major=2, uuid=OLD_UUID_A)
    eqp = superblock(generation=7, uuid=OLD_UUID_A, salt=1)
    eqm = superblock(generation=7, uuid=OLD_UUID_B, salt=2)
    exp = superblock(generation=0xFFFFFFFD, uuid=OLD_UUID_A)
    exm = superblock(generation=0xFFFFFFFC, uuid=OLD_UUID_A)
    exeqp = superblock(generation=0xFFFFFFFD, uuid=OLD_UUID_A, salt=3)
    exeqm = superblock(generation=0xFFFFFFFD, uuid=OLD_UUID_B, salt=4)
    zero = bytes(BLOCK)
    return {
        "healthy_pair": _shape("healthy_pair", healthy, healthy, "primary", "mirror", True, OLD_UUID_A),
        "mirror_only": _shape("mirror_only", zero, mirror_only, "mirror", "primary", True, OLD_UUID_A),
        "generation_zero": _shape("generation_zero", gen0, zero, "primary", "mirror", True, OLD_UUID_A),
        "v2_only": _shape("v2_only", v2, zero, "primary", "mirror", True, OLD_UUID_A),
        "equal_divergent": _shape("equal_divergent", eqp, eqm, None, "mirror", True, None),
        "exhaustion_candidate": _shape("exhaustion_candidate", exp, exm, "primary", "mirror", False, OLD_UUID_A),
        "exhaustion_equal_divergent": _shape("exhaustion_equal_divergent", exeqp, exeqm, None, "mirror", False, None),
    }

def initial_snapshot(shape_name: str):
    s = raw_shapes()[shape_name]
    return {
        "format": "FMTDUP-ID-RAW-1",
        "primary_hex": s.primary.hex(),
        "mirror_hex": s.mirror.hex(),
        "a0_head_hex": OLD_A0.hex(),
        "b0_head_hex": OLD_B0.hex(),
    }

def final_index_heads(operation: str):
    return (FORMAT_A0, FORMAT_B0) if operation == "format" else (DUP_A0, DUP_B0)

def target_writes(operation: str, shape_name: str):
    s = raw_shapes()[shape_name]
    first = s.partner_copy
    second = "primary" if first == "mirror" else "mirror"
    lba = {"primary": 0, "mirror": LBA_MIRROR}
    final = final_superblock(operation)
    return [
        {"phase": "step1", "copy": first, "lba": lba[first], "bytes": s.step1_bytes},
        {"phase": "step1", "copy": second, "lba": lba[second], "bytes": s.step1_bytes},
        {"phase": "identity", "copy": "mirror", "lba": LBA_MIRROR, "bytes": final},
        {"phase": "identity", "copy": "primary", "lba": 0, "bytes": final},
    ]

def target_baseline(operation: str, shape_name: str):
    return [
        {"phase": x["phase"], "copy": x["copy"], "lba": x["lba"],
         "sha256": hashlib.sha256(x["bytes"]).hexdigest()}
        for x in target_writes(operation, shape_name)
    ]
