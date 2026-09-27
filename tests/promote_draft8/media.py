#!/usr/bin/env python3
"""Independent raw-media parser/oracle for the R29-A promote package."""
from __future__ import annotations
import hashlib
import struct
import zlib

from fixture import (
    BLOCK, CHUNK_FRAMES, FRAME_BYTES, CHUNK_BLOCKS, LBA_CHUNK_BASE,
    LBA_A0, LBA_A1, LBA_B0, LBA_B1, MAGIC_SB, MAGIC_IDX,
)

class MediaError(RuntimeError):
    pass


def _need(c, m):
    if not c:
        raise MediaError(m)


def _raw(snapshot, key):
    v = snapshot.get(key)
    _need(isinstance(v, str), f"missing {key}")
    try:
        b = bytes.fromhex(v)
    except ValueError as e:
        raise MediaError(f"bad hex {key}") from e
    _need(len(b) == BLOCK, f"{key} length")
    return b


def _crc32(data):
    return zlib.crc32(data) & 0xFFFFFFFF


def parse_superblock(raw):
    structural = len(raw) == BLOCK and raw[:8] == MAGIC_SB
    if structural:
        structural = struct.unpack_from("<I", raw, 508)[0] == _crc32(raw[:508])
    if not structural:
        return {"structural": False, "raw": raw}
    return {
        "structural": True,
        "raw": raw,
        "version_major": struct.unpack_from("<H", raw, 8)[0],
        "version_minor": struct.unpack_from("<H", raw, 10)[0],
        "sb_generation": struct.unpack_from("<I", raw, 12)[0],
        "state": raw[16],
        "uuid": raw[20:36].hex(),
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
        "promote_staging_chunk": struct.unpack_from("<I", raw, 128)[0],
    }


def select_superblock(snapshot):
    p = parse_superblock(_raw(snapshot, "primary_hex"))
    m = parse_superblock(_raw(snapshot, "mirror_hex"))
    if not p["structural"] and not m["structural"]:
        return {"result": "TAPE_ERR_BAD_MAGIC", "primary": p, "mirror": m}
    if p["structural"] and not m["structural"]:
        return {"result": "TAPE_OK", "selected_copy": "primary", "selected": p, "primary": p, "mirror": m}
    if m["structural"] and not p["structural"]:
        return {"result": "TAPE_OK", "selected_copy": "mirror", "selected": m, "primary": p, "mirror": m}
    if p["sb_generation"] > m["sb_generation"]:
        return {"result": "TAPE_OK", "selected_copy": "primary", "selected": p, "primary": p, "mirror": m}
    if m["sb_generation"] > p["sb_generation"]:
        return {"result": "TAPE_OK", "selected_copy": "mirror", "selected": m, "primary": p, "mirror": m}
    if p["raw"] != m["raw"]:
        return {"result": "TAPE_ERR_INCONSISTENT", "primary": p, "mirror": m}
    return {"result": "TAPE_OK", "selected_copy": "primary", "selected": p, "primary": p, "mirror": m}


def _slot_raw(snapshot, name):
    return _raw(snapshot, name.lower() + "_header_hex"), _raw(snapshot, name.lower() + "_entries_hex")


def parse_slot(snapshot, name, sb):
    header, entry_block = _slot_raw(snapshot, name)
    structural = header[:8] == MAGIC_IDX
    if not structural:
        return {"name": name, "structural": False}
    sequence = struct.unpack_from("<I", header, 8)[0]
    side = header[12]
    entry_count = struct.unpack_from("<I", header, 16)[0]
    total_frames = struct.unpack_from("<Q", header, 20)[0]
    if entry_count > 4096:
        return {"name": name, "structural": False}
    raw_entries = entry_block[:12 * entry_count]
    expected_crc = struct.unpack_from("<I", header, 60)[0]
    if expected_crc != _crc32(header[:60] + raw_entries):
        return {"name": name, "structural": False}

    entries = [
        struct.unpack_from("<III", raw_entries, i * 12)
        for i in range(entry_count)
    ]
    structural_info = {
        "name": name,
        "structural": True,
        "sequence": sequence,
        "side": side,
        "entry_count": entry_count,
        "total_frames": total_frames,
        "entries": entries,
    }

    assigned_side = 0 if name.startswith("A") else 1
    valid = side == assigned_side
    valid = valid and total_frames == sum(e[2] for e in entries)
    intervals = []
    for first, start, frames in entries:
        if frames < 1 or start >= CHUNK_FRAMES:
            valid = False
            continue
        span = start + frames - 1
        last = first + span // CHUNK_FRAMES
        if last >= sb["total_chunks"]:
            valid = False
        if assigned_side == 0 and last >= sb["a_high_water"]:
            valid = False
        base = first * CHUNK_FRAMES + start
        end = base + frames
        intervals.append((base, end))
    intervals.sort()
    for a, b in zip(intervals, intervals[1:]):
        if a[1] > b[0]:
            valid = False

    structural_info["valid"] = valid
    return structural_info


def select_side(snapshot, side, sb):
    names = ("A0", "A1") if side == "A" else ("B0", "B1")
    slots = [parse_slot(snapshot, n, sb) for n in names]
    valid = [s for s in slots if s.get("valid")]
    if not valid:
        return {"result": "TAPE_ERR_NO_VALID_INDEX", "slots": slots}
    if len(valid) == 1:
        return {"result": "TAPE_OK", "selected": valid[0], "slots": slots}
    if valid[0]["sequence"] == valid[1]["sequence"]:
        return {"result": "TAPE_ERR_INCONSISTENT", "slots": slots}
    selected = max(valid, key=lambda s: s["sequence"])
    return {"result": "TAPE_OK", "selected": selected, "slots": slots}


def _single(slot, first=None):
    if slot is None or slot["entry_count"] != 1:
        return False
    e = slot["entries"][0]
    if e[1] != 0:
        return False
    return first is None or e[0] == first


def resume_rows(snapshot):
    sbs = select_superblock(snapshot)
    if sbs["result"] != "TAPE_OK":
        return []
    sb = sbs["selected"]
    if sb["promote_stage"] != 1:
        return []
    a = select_side(snapshot, "A", sb)
    b = select_side(snapshot, "B", sb)
    if a["result"] != "TAPE_OK" or b["result"] != "TAPE_OK":
        return []
    A, B = a["selected"], b["selected"]
    S = sb["promote_staging_chunk"]
    N = B["total_frames"]
    length = (N + CHUNK_FRAMES - 1) // CHUNK_FRAMES
    rows = []

    if _single(A, S) and A["entries"] == B["entries"] and A["total_frames"] == B["total_frames"]:
        rows.append(1)
    if (
        S > 0 and _single(A, 0) and _single(B, S)
        and A["total_frames"] == B["total_frames"]
    ):
        rows.append(2)
    if (
        S > 0 and _single(A, 0)
        and A["entries"] == B["entries"]
        and A["total_frames"] == B["total_frames"]
        and sb["a_high_water"] > length
    ):
        rows.append(3)
    return rows


def inspect_snapshot(snapshot, requested_side="A"):
    block_count = snapshot.get("block_count")
    if not isinstance(block_count, int) or isinstance(block_count, bool) or block_count <= LBA_CHUNK_BASE:
        return {"mount_result": "TAPE_ERR_GEOMETRY", "phase": 0}
    sbsel = select_superblock(snapshot)
    if sbsel["result"] != "TAPE_OK":
        return {"mount_result": sbsel["result"], "sb": sbsel}
    sb = sbsel["selected"]
    if sb["version_major"] != 1:
        return {"mount_result": "TAPE_ERR_VERSION", "sb": sbsel}
    if sb["state"] not in (0, 1) or sb["promote_stage"] not in (0, 1):
        return {"mount_result": "TAPE_ERR_UNSUPPORTED_STATE", "sb": sbsel}
    if sb["state"] == 1:
        return {"mount_result": "TAPE_ERR_INCOMPLETE", "sb": sbsel}
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
        return {"mount_result": "TAPE_ERR_GEOMETRY", "sb": sbsel}

    a = select_side(snapshot, "A", sb)
    b = select_side(snapshot, "B", sb)
    if a["result"] != "TAPE_OK":
        return {"mount_result": a["result"], "sb": sbsel, "A": a, "B": b}
    if b["result"] != "TAPE_OK":
        if requested_side == "B":
            return {"mount_result": b["result"], "sb": sbsel, "A": a, "B": b}
        return {
            "mount_result": "TAPE_OK", "degraded_b": True,
            "sb": sbsel, "A": a, "B": b, "resume_rows": [],
        }

    rows = resume_rows(snapshot) if sb["promote_stage"] == 1 else []
    if sb["promote_stage"] == 1 and len(rows) != 1:
        return {
            "mount_result": "TAPE_ERR_INCONSISTENT",
            "sb": sbsel, "A": a, "B": b, "resume_rows": rows,
        }

    return {
        "mount_result": "TAPE_OK",
        "sb": sbsel,
        "A": a,
        "B": b,
        "resume_rows": rows,
        "degraded_b": False,
    }


def structural_sequences(snapshot):
    sbsel = select_superblock(snapshot)
    if sbsel["result"] != "TAPE_OK":
        return []
    sb = sbsel["selected"]
    out = []
    for name in ("A0", "A1", "B0", "B1"):
        slot = parse_slot(snapshot, name, sb)
        if slot.get("structural"):
            out.append((name, slot["sequence"]))
    return out


def require_unique_structural_sequences(snapshot):
    pairs = structural_sequences(snapshot)
    seqs = [x[1] for x in pairs]
    _need(len(seqs) == len(set(seqs)), f"duplicate structurally-valid sequence: {pairs}")
    return True


def free_next(snapshot):
    ins = inspect_snapshot(snapshot, "A")
    _need(ins["mount_result"] == "TAPE_OK", "free_next on unmountable media")
    sb = ins["sb"]["selected"]
    value = sb["a_high_water"]
    b = ins.get("B", {})
    if b.get("result") == "TAPE_OK":
        for first, start, frames in b["selected"]["entries"]:
            last = first + (start + frames - 1) // CHUNK_FRAMES
            value = max(value, last + 1)
    return value


def render_bytes(snapshot, side):
    ins = inspect_snapshot(snapshot, side)
    _need(ins["mount_result"] == "TAPE_OK", f"{side} not mountable")
    selected = ins[side]["selected"]
    chunks = snapshot.get("chunk0_hex")
    _need(isinstance(chunks, dict), "missing chunk0_hex")
    out = bytearray()
    for first, start, frames in selected["entries"]:
        # Verifier fixtures intentionally keep every referenced run inside the
        # first 512-byte block of a chunk. Tail bytes are undefined by §6.
        _need(start + frames <= BLOCK // FRAME_BYTES, "fixture exceeds retained raw audio block")
        raw = bytes.fromhex(chunks[str(first)])
        out += raw[start * FRAME_BYTES:(start + frames) * FRAME_BYTES]
    return bytes(out)


def render_sha256(snapshot, side):
    return hashlib.sha256(render_bytes(snapshot, side)).hexdigest()


def logical_fingerprint(snapshot):
    ins = inspect_snapshot(snapshot, "A")
    fp = {"mount_result": ins["mount_result"]}
    if ins["mount_result"] != "TAPE_OK":
        return fp
    sb = ins["sb"]["selected"]
    fp.update({
        "selected_sb_copy": ins["sb"]["selected_copy"],
        "sb_generation": sb["sb_generation"],
        "a_high_water": sb["a_high_water"],
        "promote_stage": sb["promote_stage"],
        "promote_staging_chunk": sb["promote_staging_chunk"],
        "resume_rows": ins.get("resume_rows", []),
        "a_sequence": ins["A"]["selected"]["sequence"],
        "a_entries": ins["A"]["selected"]["entries"],
        "degraded_b": ins.get("degraded_b", False),
    })
    if ins["B"]["result"] == "TAPE_OK":
        fp["b_sequence"] = ins["B"]["selected"]["sequence"]
        fp["b_entries"] = ins["B"]["selected"]["entries"]
    return fp
