#!/usr/bin/env python3
"""Independent raw-superblock selection and identity parser for the R29 package."""
from __future__ import annotations
import struct, zlib
from fixture import (
    BLOCK, CHUNK_FRAMES, CHUNK_BLOCKS, LBA_CHUNK_BASE, LBA_A0, LBA_A1,
    LBA_B0, LBA_B1, MAGIC_SB, MAGIC_IDX, FRESH_FORMAT_UUID, FRESH_DUP_UUID,
    FORMAT_A0, FORMAT_B0, DUP_A0, DUP_B0,
)

class MediaError(RuntimeError):
    pass

def need(c, m):
    if not c:
        raise MediaError(m)

def _raw(snapshot, key):
    v = snapshot.get(key)
    need(isinstance(v, str), key + " missing")
    try:
        b = bytes.fromhex(v)
    except ValueError as e:
        raise MediaError(key + " malformed") from e
    need(len(b) == BLOCK, key + " length")
    return b

def parse_superblock(raw):
    structural = (
        raw[:8] == MAGIC_SB
        and (zlib.crc32(raw[:508]) & 0xffffffff) == struct.unpack_from("<I", raw, 508)[0]
    )
    if not structural:
        return {"structural_valid": False, "raw": raw}
    return {
        "structural_valid": True,
        "raw": raw,
        "version_major": struct.unpack_from("<H", raw, 8)[0],
        "generation": struct.unpack_from("<I", raw, 12)[0],
        "state": raw[16],
        "uuid": raw[20:36],
        "sample_rate": struct.unpack_from("<I", raw, 36)[0],
        "channels": struct.unpack_from("<H", raw, 40)[0],
        "bits_per_sample": struct.unpack_from("<H", raw, 42)[0],
        "chunk_bytes": struct.unpack_from("<I", raw, 44)[0],
        "nominal_length_s": struct.unpack_from("<I", raw, 48)[0],
        "total_chunks": struct.unpack_from("<I", raw, 52)[0],
        "a_high_water": struct.unpack_from("<I", raw, 56)[0],
        "index_slot_bytes": struct.unpack_from("<I", raw, 60)[0],
        "lba_index_a0": struct.unpack_from("<I", raw, 64)[0],
        "lba_index_a1": struct.unpack_from("<I", raw, 68)[0],
        "lba_index_b0": struct.unpack_from("<I", raw, 72)[0],
        "lba_index_b1": struct.unpack_from("<I", raw, 76)[0],
        "lba_chunk_base": struct.unpack_from("<I", raw, 80)[0],
        "lba_superblock_mirror": struct.unpack_from("<I", raw, 84)[0],
        "promote_stage": struct.unpack_from("<I", raw, 124)[0],
    }

def select_superblock(snapshot):
    p = parse_superblock(_raw(snapshot, "primary_hex"))
    m = parse_superblock(_raw(snapshot, "mirror_hex"))
    valid = [(n, s) for n, s in (("primary", p), ("mirror", m)) if s["structural_valid"]]
    if not valid:
        return {"result": "TAPE_ERR_BAD_MAGIC", "copies": {"primary": p, "mirror": m}}
    if len(valid) == 1:
        name, sb = valid[0]
    else:
        if p["generation"] == m["generation"]:
            if p["raw"] != m["raw"]:
                return {"result": "TAPE_ERR_INCONSISTENT", "copies": {"primary": p, "mirror": m}}
            name, sb = "primary", p
        elif p["generation"] > m["generation"]:
            name, sb = "primary", p
        else:
            name, sb = "mirror", m
    return {
        "result": "TAPE_OK",
        "selected_copy": name,
        "selected": sb,
        "copies": {"primary": p, "mirror": m},
    }

def _head(snapshot, key):
    raw = _raw(snapshot, key)
    if raw[:8] != MAGIC_IDX:
        return {"valid": False}
    return {
        "valid": True,
        "sequence": struct.unpack_from("<I", raw, 8)[0],
        "side": raw[12],
        "entry_count": struct.unpack_from("<I", raw, 16)[0],
        "total_frames": struct.unpack_from("<Q", raw, 20)[0],
        "raw": raw,
    }

def inspect_snapshot(snapshot):
    need(snapshot.get("format") == "FMTDUP-ID-RAW-1", "snapshot format")
    block_count = snapshot.get("block_count")
    if not isinstance(block_count, int) or isinstance(block_count, bool) or block_count <= LBA_CHUNK_BASE:
        return {"mount_result": "TAPE_ERR_GEOMETRY", "phase": 0}
    sel = select_superblock(snapshot)
    if sel["result"] != "TAPE_OK":
        return {"mount_result": sel["result"], "superblock": sel}
    sb = sel["selected"]
    if sb["version_major"] != 1:
        return {"mount_result": "TAPE_ERR_VERSION", "superblock": sel}
    if sb["state"] not in (0, 1) or sb["promote_stage"] not in (0, 1):
        return {"mount_result": "TAPE_ERR_UNSUPPORTED_STATE", "superblock": sel}
    if sb["state"] == 1:
        return {"mount_result": "TAPE_ERR_INCOMPLETE", "superblock": sel}

    nominal = sb["nominal_length_s"]
    frames = nominal * 44100
    derived_chunks = (frames + CHUNK_FRAMES - 1) // CHUNK_FRAMES if nominal else 0
    fixed = (
        sb["sample_rate"] == 44100 and sb["channels"] == 2
        and sb["bits_per_sample"] == 16 and sb["chunk_bytes"] == 524288
        and sb["index_slot_bytes"] == 65536
        and (sb["lba_index_a0"], sb["lba_index_a1"], sb["lba_index_b0"], sb["lba_index_b1"])
            == (LBA_A0, LBA_A1, LBA_B0, LBA_B1)
        and sb["lba_chunk_base"] == LBA_CHUNK_BASE
        and sb["lba_superblock_mirror"] == block_count - 1
    )
    capacity_fits = (
        nominal > 0 and frames <= 0xFFFFFFFF and 0 < derived_chunks <= 0xFFFFFFFF
        and LBA_CHUNK_BASE + derived_chunks * CHUNK_BLOCKS <= block_count - 1
    )
    if (
        not fixed or not capacity_fits or sb["total_chunks"] != derived_chunks
        or sb["a_high_water"] > sb["total_chunks"]
    ):
        return {"mount_result": "TAPE_ERR_GEOMETRY", "superblock": sel}

    a = _head(snapshot, "a0_head_hex")
    b = _head(snapshot, "b0_head_hex")
    if sb["uuid"] == FRESH_FORMAT_UUID:
        if a.get("raw") != FORMAT_A0 or b.get("raw") != FORMAT_B0:
            return {"mount_result": "TAPE_ERR_NO_VALID_INDEX", "superblock": sel, "a0": a, "b0": b}
    if sb["uuid"] == FRESH_DUP_UUID:
        if a.get("raw") != DUP_A0 or b.get("raw") != DUP_B0:
            return {"mount_result": "TAPE_ERR_NO_VALID_INDEX", "superblock": sel, "a0": a, "b0": b}

    return {
        "mount_result": "TAPE_OK",
        "superblock": sel,
        "selected_uuid": sb["uuid"].hex(),
        "sb_generation": sb["generation"],
        "a0": a,
        "b0": b,
    }

def identity_tuple(snapshot):
    state = inspect_snapshot(snapshot)
    if state["mount_result"] != "TAPE_OK":
        return None
    return (
        state["selected_uuid"],
        state["sb_generation"],
        state["a0"].get("sequence"),
        state["b0"].get("sequence"),
    )
