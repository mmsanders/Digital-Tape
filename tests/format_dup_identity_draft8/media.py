#!/usr/bin/env python3
"""Independent raw-superblock selection and identity parser for the R29 package."""
from __future__ import annotations
import struct, zlib
from fixture import (
    BLOCK, MAGIC_SB, MAGIC_IDX, FRESH_FORMAT_UUID, FRESH_DUP_UUID,
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
        "total_chunks": struct.unpack_from("<I", raw, 52)[0],
        "a_high_water": struct.unpack_from("<I", raw, 56)[0],
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
    sel = select_superblock(snapshot)
    if sel["result"] != "TAPE_OK":
        return {"mount_result": sel["result"], "superblock": sel}
    sb = sel["selected"]
    if sb["version_major"] != 1:
        return {"mount_result": "TAPE_ERR_VERSION", "superblock": sel}
    if sb["state"] not in (0, 1):
        return {"mount_result": "TAPE_ERR_UNSUPPORTED_STATE", "superblock": sel}
    if sb["state"] == 1:
        return {"mount_result": "TAPE_ERR_INCOMPLETE", "superblock": sel}

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
