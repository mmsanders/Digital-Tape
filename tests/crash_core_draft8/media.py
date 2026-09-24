#!/usr/bin/env python3
"""Raw-media parser/oracle primitives for the bounded DRAFT-8 WP-10 core package."""
from __future__ import annotations

import hashlib
import struct
import zlib
from typing import Any

from fixture import (
    BLOCK,
    BLOCK_COUNT,
    CHUNK_BLOCKS,
    CHUNK_BYTES,
    CHUNK_FRAMES,
    LBA_A0,
    LBA_A1,
    LBA_B0,
    LBA_B1,
    LBA_CHUNK_BASE,
    LBA_MIRROR,
    MAGIC_IDX,
    MAGIC_SB,
    SLOT_BYTES,
    TOTAL_CHUNKS,
)

SLOT_LBAS = {"A0": LBA_A0, "A1": LBA_A1, "B0": LBA_B0, "B1": LBA_B1}


class MediaError(RuntimeError):
    pass


def _need(cond: bool, msg: str) -> None:
    if not cond:
        raise MediaError(msg)


def _u16(b: bytes, off: int) -> int:
    return struct.unpack_from("<H", b, off)[0]


def _u32(b: bytes, off: int) -> int:
    return struct.unpack_from("<I", b, off)[0]


def _u64(b: bytes, off: int) -> int:
    return struct.unpack_from("<Q", b, off)[0]


def _crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def _block(image: bytes, lba: int) -> bytes:
    _need(len(image) == BLOCK_COUNT * BLOCK, "wrong raw image size")
    start = lba * BLOCK
    return image[start : start + BLOCK]


def compact_snapshot(image: bytes) -> dict:
    """
    Compact raw facts sufficient for this bounded tranche.

    Every fixture/index used here has at most two entries, so retaining the first
    two blocks of each slot contains the complete CRC-covered entry array. The
    product binding must use this verifier-owned routine (or byte-identical output)
    over the durable image *before* remount/repair.
    """
    _need(len(image) == BLOCK_COUNT * BLOCK, "wrong raw image size")
    slots = {}
    for name, lba in SLOT_LBAS.items():
        start = lba * BLOCK
        slots[name] = image[start : start + 2 * BLOCK].hex()
    chunks = {}
    for chunk in range(TOTAL_CHUNKS):
        start = (LBA_CHUNK_BASE + chunk * CHUNK_BLOCKS) * BLOCK
        payload = image[start : start + CHUNK_BYTES]
        chunks[str(chunk)] = hashlib.sha256(payload).hexdigest()
    return {
        "format": "WP10-CORE-SNAPSHOT-1",
        "image_sha256": hashlib.sha256(image).hexdigest(),
        "primary_hex": _block(image, 0).hex(),
        "mirror_hex": _block(image, LBA_MIRROR).hex(),
        "slots": slots,
        "chunk_sha256": chunks,
    }


def _bytes_hex(value: Any, exact: int, label: str) -> bytes:
    _need(isinstance(value, str), f"{label} not hex text")
    try:
        b = bytes.fromhex(value)
    except ValueError as exc:
        raise MediaError(f"{label} malformed hex") from exc
    _need(len(b) == exact, f"{label} length {len(b)} != {exact}")
    return b


def parse_superblock(raw: bytes) -> dict:
    _need(len(raw) == BLOCK, "superblock raw length")
    structural = raw[:8] == MAGIC_SB and _crc32(raw[:508]) == _u32(raw, 508)
    if not structural:
        return {"structural_valid": False}
    return {
        "structural_valid": True,
        "raw": raw,
        "version_major": _u16(raw, 8),
        "version_minor": _u16(raw, 10),
        "generation": _u32(raw, 12),
        "state": raw[16],
        "total_chunks": _u32(raw, 52),
        "a_high_water": _u32(raw, 56),
        "lba_mirror": _u32(raw, 84),
        "promote_stage": _u32(raw, 124),
        "promote_staging_chunk": _u32(raw, 128),
    }


def select_superblock(snapshot: dict) -> dict:
    _need(snapshot.get("format") == "WP10-CORE-SNAPSHOT-1", "wrong snapshot format")
    primary = parse_superblock(_bytes_hex(snapshot.get("primary_hex"), BLOCK, "primary"))
    mirror = parse_superblock(_bytes_hex(snapshot.get("mirror_hex"), BLOCK, "mirror"))
    valid = [("primary", primary), ("mirror", mirror)]
    valid = [(name, sb) for name, sb in valid if sb["structural_valid"]]
    if not valid:
        return {"result": "TAPE_ERR_BAD_MAGIC", "copies": {"primary": primary, "mirror": mirror}}
    if len(valid) == 1:
        name, selected = valid[0]
    else:
        (_, p), (_, m) = valid
        if p["generation"] == m["generation"]:
            if p["raw"] != m["raw"]:
                return {
                    "result": "TAPE_ERR_INCONSISTENT",
                    "copies": {"primary": primary, "mirror": mirror},
                }
            name, selected = "primary", p
        elif p["generation"] > m["generation"]:
            name, selected = "primary", p
        else:
            name, selected = "mirror", m
    return {
        "result": "TAPE_OK",
        "selected_copy": name,
        "selected": selected,
        "copies": {"primary": primary, "mirror": mirror},
    }


def parse_index(raw2: bytes, *, expected_side: int, sb: dict) -> dict:
    _need(len(raw2) == 2 * BLOCK, "index compact raw length")
    header = raw2[:BLOCK]
    if header[:8] != MAGIC_IDX:
        return {"structural_valid": False, "valid": False, "reason": "bad magic"}
    entry_count = _u32(header, 16)
    if entry_count > 4096:
        return {"structural_valid": False, "valid": False, "reason": "entry_count"}
    _need(entry_count <= 2, "bounded fixture unexpectedly needs >2 retained entries")
    entries_raw = raw2[BLOCK : BLOCK + 12 * entry_count]
    structural = _crc32(header[:60] + entries_raw) == _u32(header, 60)
    if not structural:
        return {"structural_valid": False, "valid": False, "reason": "crc"}

    side = header[12]
    total_frames = _u64(header, 20)
    sequence = _u32(header, 8)
    entries = []
    errors = []
    total = 0
    intervals = []
    for i in range(entry_count):
        first, start, count = struct.unpack_from("<III", entries_raw, 12 * i)
        total += count
        if count == 0:
            errors.append(f"entry {i} count zero")
            last = first
        else:
            span = int(start) + int(count) - 1
            last = int(first) + span // CHUNK_FRAMES
        if start >= CHUNK_FRAMES:
            errors.append(f"entry {i} start out of range")
        if last >= sb["total_chunks"]:
            errors.append(f"entry {i} extent out of range")
        base = int(first) * CHUNK_FRAMES + int(start)
        end = base + int(count)
        intervals.append((base, end, i))
        entries.append((first, start, count))

    if side != expected_side:
        errors.append("side mismatch")
    if total != total_frames:
        errors.append("total_frames mismatch")
    if total_frames > 0xFFFFFFFF:
        errors.append("total_frames cap")

    ordered = sorted(intervals)
    for left, right in zip(ordered, ordered[1:]):
        if left[1] > right[0]:
            errors.append(f"physical overlap {left[2]}/{right[2]}")

    if expected_side == 0:
        for i, (first, start, count) in enumerate(entries):
            if count:
                last = int(first) + (int(start) + int(count) - 1) // CHUNK_FRAMES
                if last >= sb["a_high_water"]:
                    errors.append(f"Side A entry {i} crosses high water")

    return {
        "structural_valid": True,
        "valid": not errors,
        "reason": "; ".join(errors),
        "sequence": sequence,
        "side": side,
        "total_frames": total_frames,
        "entries": entries,
    }


def _slot(snapshot: dict, name: str, side: int, sb: dict) -> dict:
    slots = snapshot.get("slots")
    _need(isinstance(slots, dict), "missing slots")
    raw = _bytes_hex(slots.get(name), 2 * BLOCK, name)
    return parse_index(raw, expected_side=side, sb=sb)


def select_side(snapshot: dict, side: int, sb: dict) -> dict:
    names = ("A0", "A1") if side == 0 else ("B0", "B1")
    rows = [(name, _slot(snapshot, name, side, sb)) for name in names]

    # Every structurally valid committed slot must itself satisfy §5.2.
    for name, row in rows:
        if row["structural_valid"] and not row["valid"]:
            raise MediaError(f"{name} structurally valid but §5.2-invalid: {row['reason']}")

    valid = [(name, row) for name, row in rows if row["valid"]]
    if not valid:
        return {"result": "TAPE_ERR_NO_VALID_INDEX", "slots": dict(rows)}
    if len(valid) == 1:
        name, selected = valid[0]
    else:
        (n0, r0), (n1, r1) = valid
        if r0["sequence"] == r1["sequence"]:
            return {"result": "TAPE_ERR_INCONSISTENT", "slots": dict(rows)}
        name, selected = (n0, r0) if r0["sequence"] > r1["sequence"] else (n1, r1)
    return {"result": "TAPE_OK", "selected_slot": name, "selected": selected, "slots": dict(rows)}


def _stage_row(sb: dict, a: dict, b: dict) -> str | None:
    if sb["promote_stage"] != 1:
        return None
    ae = a["entries"]
    be = b["entries"]
    S = sb["promote_staging_chunk"]
    H = sb["a_high_water"]
    if len(ae) == 1 and ae[0][0] == S and ae[0][1] == 0 and be == ae:
        return "step5"
    if (
        len(ae) == 1
        and ae[0][0] == 0
        and ae[0][1] == 0
        and len(be) == 1
        and be[0][0] == S
        and be[0][1] == 0
        and ae[0][2] == be[0][2]
        and S > 0
    ):
        return "step8"
    if (
        len(ae) == 1
        and ae[0][0] == 0
        and ae[0][1] == 0
        and be == ae
        and S > 0
        and H > ((ae[0][2] + CHUNK_FRAMES - 1) // CHUNK_FRAMES)
    ):
        return "step9"
    return "invalid"


def inspect_snapshot(snapshot: dict, *, requested_side: str = "A") -> dict:
    sbsel = select_superblock(snapshot)
    if sbsel["result"] != "TAPE_OK":
        return {"mount_result": sbsel["result"], "superblock": sbsel}

    sb = sbsel["selected"]
    if sb["version_major"] != 1:
        return {"mount_result": "TAPE_ERR_VERSION", "superblock": sbsel}
    if sb["state"] == 1:
        return {"mount_result": "TAPE_ERR_INCOMPLETE", "superblock": sbsel}
    if (
        sb["total_chunks"] != TOTAL_CHUNKS
        or sb["lba_mirror"] != LBA_MIRROR
        or not (0 <= sb["a_high_water"] <= TOTAL_CHUNKS)
    ):
        return {"mount_result": "TAPE_ERR_GEOMETRY", "superblock": sbsel}

    try:
        a = select_side(snapshot, 0, sb)
    except MediaError as exc:
        return {"mount_result": "TAPE_ERR_NO_VALID_INDEX", "media_error": str(exc), "superblock": sbsel}
    if a["result"] != "TAPE_OK":
        return {"mount_result": a["result"], "superblock": sbsel, "side_a": a}

    try:
        b = select_side(snapshot, 1, sb)
    except MediaError as exc:
        return {"mount_result": "TAPE_ERR_NO_VALID_INDEX", "media_error": str(exc), "superblock": sbsel, "side_a": a}

    degraded = b["result"] != "TAPE_OK"
    if requested_side == "B" and degraded:
        return {
            "mount_result": b["result"],
            "superblock": sbsel,
            "side_a": a,
            "side_b": b,
            "degraded_b": True,
        }

    if not degraded and sb["promote_stage"] == 1:
        row = _stage_row(sb, a["selected"], b["selected"])
        if row == "invalid":
            return {
                "mount_result": "TAPE_ERR_INCONSISTENT",
                "superblock": sbsel,
                "side_a": a,
                "side_b": b,
                "degraded_b": False,
                "stage_row": row,
            }
    else:
        row = None

    return {
        "mount_result": "TAPE_OK",
        "superblock": sbsel,
        "side_a": a,
        "side_b": b,
        "degraded_b": degraded,
        "stage_row": row,
    }


def logical_fingerprint(snapshot: dict, *, requested_side: str = "A") -> dict:
    state = inspect_snapshot(snapshot, requested_side=requested_side)
    out = {
        "mount_result": state["mount_result"],
        "degraded_b": bool(state.get("degraded_b", False)),
    }
    if state["mount_result"] != "TAPE_OK":
        return out
    sb = state["superblock"]["selected"]
    out.update(
        {
            "sb_generation": sb["generation"],
            "a_high_water": sb["a_high_water"],
            "promote_stage": sb["promote_stage"],
            "promote_staging_chunk": sb["promote_staging_chunk"],
            "stage_row": state.get("stage_row"),
            "a_sequence": state["side_a"]["selected"]["sequence"],
            "a_entries": state["side_a"]["selected"]["entries"],
        }
    )
    if not state["degraded_b"]:
        out.update(
            {
                "b_sequence": state["side_b"]["selected"]["sequence"],
                "b_entries": state["side_b"]["selected"]["entries"],
            }
        )
    else:
        out["b_error"] = state["side_b"]["result"]
    return out


def require_chunk_hashes_equal(left: dict, right: dict) -> None:
    _need(
        left.get("chunk_sha256") == right.get("chunk_sha256"),
        "chunk-store digest set changed during metadata-scoped crash",
    )
