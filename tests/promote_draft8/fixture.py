#!/usr/bin/env python3
"""Verifier-owned byte fixtures and exact promote write plans for DRAFT-8."""
from __future__ import annotations
import hashlib
import struct
import zlib

BLOCK = 512
CHUNK_FRAMES = 131072
FRAME_BYTES = 4
CHUNK_BLOCKS = 1024
LBA_CHUNK_BASE = 2048
LBA_A0 = 8
LBA_A1 = 136
LBA_B0 = 264
LBA_B1 = 392
MAGIC_SB = b"TAPEFS\x00\x01"
MAGIC_IDX = b"TAPEIDX\x01"
UUID = bytes.fromhex("70726f6d6f74652d76382d6669787472")  # "promote-v8-fixtr"

OLD_A_BLOCK = bytes(((i * 17 + 3) & 0xFF) for i in range(BLOCK))
B_LEFT = bytes(((i * 5 + 11) & 0xFF) for i in range(BLOCK // 2))
B_RIGHT = bytes(((i * 7 + 29) & 0xFF) for i in range(BLOCK // 2))
PROMOTED_BLOCK = B_LEFT + B_RIGHT
ZERO_BLOCK = bytes(BLOCK)

SLOT_BASE = {"A0": LBA_A0, "A1": LBA_A1, "B0": LBA_B0, "B1": LBA_B1}


def crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def block_count(total_chunks: int) -> int:
    return LBA_CHUNK_BASE + total_chunks * CHUNK_BLOCKS + 1


def mirror_lba(total_chunks: int) -> int:
    return block_count(total_chunks) - 1


def superblock(
    generation: int,
    h: int,
    stage: int,
    staging: int,
    *,
    total_chunks: int,
) -> bytes:
    b = bytearray(BLOCK)
    b[0:8] = MAGIC_SB
    struct.pack_into("<HHI", b, 8, 1, 0, generation)
    b[16] = 0
    b[20:36] = UUID
    struct.pack_into("<I", b, 36, 44100)
    struct.pack_into("<H", b, 40, 2)
    struct.pack_into("<H", b, 42, 16)
    struct.pack_into("<I", b, 44, 524288)
    # These compact verifier fixtures carry a truthful label.  Nine seconds
    # derives four chunks; twenty-one seconds derives eight chunks under the
    # frozen ceiling formula in TapeFS section 2.
    nominal_length_s = {4: 9, 8: 21}[total_chunks]
    struct.pack_into("<I", b, 48, nominal_length_s)
    struct.pack_into("<I", b, 52, total_chunks)
    struct.pack_into("<I", b, 56, h)
    struct.pack_into("<I", b, 60, 65536)
    struct.pack_into("<IIIII", b, 64, LBA_A0, LBA_A1, LBA_B0, LBA_B1, LBA_CHUNK_BASE)
    struct.pack_into("<I", b, 84, mirror_lba(total_chunks))
    b[88:120] = b"R29-A PROMOTE FIXTURE".ljust(32, b"\0")
    struct.pack_into("<I", b, 120, 29)
    struct.pack_into("<II", b, 124, stage, staging)
    struct.pack_into("<I", b, 508, crc32(bytes(b[:508])))
    return bytes(b)


def entry_bytes(entries):
    return b"".join(struct.pack("<III", *e) for e in entries)


def index_blocks(sequence: int, side: int, entries):
    raw_entries = entry_bytes(entries)
    total_frames = sum(e[2] for e in entries)
    header = bytearray(BLOCK)
    header[:8] = MAGIC_IDX
    struct.pack_into("<I", header, 8, sequence)
    header[12] = side
    struct.pack_into("<I", header, 16, len(entries))
    struct.pack_into("<Q", header, 20, total_frames)
    struct.pack_into("<I", header, 60, crc32(bytes(header[:60]) + raw_entries))
    ent = bytearray(BLOCK)
    ent[:len(raw_entries)] = raw_entries
    return bytes(header), bytes(ent)


def invalid_slot():
    return ZERO_BLOCK, ZERO_BLOCK


def _put_slot(blocks, name, sequence, entries):
    side = 0 if name.startswith("A") else 1
    h, e = index_blocks(sequence, side, entries)
    base = SLOT_BASE[name]
    blocks[base] = h
    blocks[base + 1] = e


def _put_invalid_slot(blocks, name):
    h, e = invalid_slot()
    base = SLOT_BASE[name]
    blocks[base] = h
    blocks[base + 1] = e


def _chunk_lba(chunk_id):
    return LBA_CHUNK_BASE + chunk_id * CHUNK_BLOCKS


def _base_blocks(total_chunks, sb):
    blocks = {
        0: sb,
        mirror_lba(total_chunks): sb,
    }
    for base in SLOT_BASE.values():
        blocks[base] = ZERO_BLOCK
        blocks[base + 1] = ZERO_BLOCK
    for chunk in range(total_chunks):
        blocks[_chunk_lba(chunk)] = ZERO_BLOCK
    return blocks


def scenario_initial(scenario: str):
    if scenario == "fresh_alloc_full":
        total = 8
        blocks = _base_blocks(total, superblock(10, 2, 0, 0, total_chunks=total))
        _put_slot(blocks, "A0", 10, [(0, 0, 128)])
        _put_slot(blocks, "A1", 8, [(0, 0, 128)])
        _put_slot(blocks, "B0", 500, [(1, 0, 64), (2, 0, 64)])
        _put_slot(blocks, "B1", 499, [(1, 0, 64), (2, 0, 64)])
        blocks[_chunk_lba(0)] = OLD_A_BLOCK
        blocks[_chunk_lba(1)] = B_LEFT + bytes(BLOCK // 2)
        blocks[_chunk_lba(2)] = B_RIGHT + bytes(BLOCK // 2)
        return {"total_chunks": total, "blocks": blocks, "initial_generation": 10}

    if scenario == "fresh_adopt_full":
        total = 4
        blocks = _base_blocks(total, superblock(10, 2, 0, 0, total_chunks=total))
        _put_slot(blocks, "A0", 10, [(0, 0, 128)])
        _put_slot(blocks, "A1", 8, [(0, 0, 128)])
        _put_slot(blocks, "B0", 500, [(3, 0, 128)])
        _put_slot(blocks, "B1", 499, [(3, 0, 128)])
        blocks[_chunk_lba(0)] = OLD_A_BLOCK
        blocks[_chunk_lba(3)] = PROMOTED_BLOCK
        return {"total_chunks": total, "blocks": blocks, "initial_generation": 10}

    if scenario == "first_use_s0":
        total = 4
        blocks = _base_blocks(total, superblock(1, 0, 0, 0, total_chunks=total))
        _put_slot(blocks, "A0", 1, [])
        _put_invalid_slot(blocks, "A1")
        _put_slot(blocks, "B0", 2, [])
        _put_slot(blocks, "B1", 3, [(0, 0, 128)])
        blocks[_chunk_lba(0)] = PROMOTED_BLOCK
        return {"total_chunks": total, "blocks": blocks, "initial_generation": 1}

    raise KeyError(scenario)


def _write(phase, kind, lba, data):
    return {"phase": phase, "kind": kind, "lba": lba, "data": data}


def _index_commit(phase_prefix, slot, sequence, entries):
    side = 0 if slot.startswith("A") else 1
    header, ent = index_blocks(sequence, side, entries)
    base = SLOT_BASE[slot]
    return [
        _write(phase_prefix + "_entries", "index_entries", base + 1, ent),
        _write(phase_prefix + "_header", "index_header", base, header),
    ]


def _sb_update(phase_prefix, generation, h, stage, staging, total_chunks):
    b = superblock(generation, h, stage, staging, total_chunks=total_chunks)
    return [
        _write(phase_prefix + "_partner", "superblock", mirror_lba(total_chunks), b),
        _write(phase_prefix + "_candidate", "superblock", 0, b),
    ]


def transaction(scenario: str):
    if scenario == "fresh_alloc_full":
        total = 8
        out = [_write("phase1_copy", "audio", _chunk_lba(3), PROMOTED_BLOCK)]
        out += _index_commit("step2_a", "A1", 501, [(3, 0, 128)])
        out += _index_commit("step3_b", "B1", 502, [(3, 0, 128)])
        out += _sb_update("step4_sb", 11, 4, 1, 3, total)
        out += [_write("phase2_copy", "audio", _chunk_lba(0), PROMOTED_BLOCK)]
        out += _index_commit("step7_a", "A0", 503, [(0, 0, 128)])
        out += _index_commit("step8_b", "B0", 504, [(0, 0, 128)])
        out += _sb_update("step9_sb", 12, 1, 0, 0, total)
        return out

    if scenario == "fresh_adopt_full":
        total = 4
        out = _index_commit("step2_a", "A1", 501, [(3, 0, 128)])
        out += _sb_update("step4_sb", 11, 4, 1, 3, total)
        out += [_write("phase2_copy", "audio", _chunk_lba(0), PROMOTED_BLOCK)]
        out += _index_commit("step7_a", "A0", 502, [(0, 0, 128)])
        out += _index_commit("step8_b", "B1", 503, [(0, 0, 128)])
        out += _sb_update("step9_sb", 12, 1, 0, 0, total)
        return out

    if scenario == "first_use_s0":
        total = 4
        out = _index_commit("step2_a", "A1", 4, [(0, 0, 128)])
        out += _sb_update("step4_sb", 2, 1, 1, 0, total)
        out += _sb_update("step5_decline_sb", 3, 1, 0, 0, total)
        return out

    raise KeyError(scenario)


def target_baseline(scenario: str):
    result = []
    for i, w in enumerate(transaction(scenario)):
        result.append({
            "ordinal": i,
            "phase": w["phase"],
            "kind": w["kind"],
            "lba": w["lba"],
            "count": 1,
            "sha256": hashlib.sha256(w["data"]).hexdigest(),
            "flush_ordinal": i,
        })
    return result


def snapshot(media):
    total = media["total_chunks"]
    b = media["blocks"]
    out = {
        "format": "PROMOTE-RAW-SNAPSHOT-1",
        "total_chunks": total,
        "block_count": block_count(total),
        "primary_hex": b[0].hex(),
        "mirror_hex": b[mirror_lba(total)].hex(),
    }
    for name, base in SLOT_BASE.items():
        out[name.lower() + "_header_hex"] = b[base].hex()
        out[name.lower() + "_entries_hex"] = b[base + 1].hex()
    out["chunk0_hex"] = {
        str(i): b[_chunk_lba(i)].hex()
        for i in range(total)
    }
    return out


def clone_media(media):
    return {
        "total_chunks": media["total_chunks"],
        "blocks": {k: bytearray(v) for k, v in media["blocks"].items()},
    }


def freeze_media(media):
    return {
        "total_chunks": media["total_chunks"],
        "blocks": {k: bytes(v) for k, v in media["blocks"].items()},
    }


def stage_fixture(variant: str):
    total = 8
    if variant == "row1":
        h, s, a, b = 4, 3, [(3, 0, 128)], [(3, 0, 128)]
    elif variant == "row2":
        h, s, a, b = 4, 3, [(0, 0, 128)], [(3, 0, 128)]
    elif variant == "row3":
        h, s, a, b = 4, 3, [(0, 0, 128)], [(0, 0, 128)]
    elif variant == "row1_s0":
        h, s, a, b = 1, 0, [(0, 0, 128)], [(0, 0, 128)]
    elif variant == "unmatched":
        h, s, a, b = 4, 3, [(3, 0, 128)], [(0, 0, 128)]
    else:
        raise KeyError(variant)
    blocks = _base_blocks(total, superblock(20, h, 1, s, total_chunks=total))
    _put_slot(blocks, "A0", 600, a)
    _put_invalid_slot(blocks, "A1")
    _put_slot(blocks, "B0", 601, b)
    _put_invalid_slot(blocks, "B1")
    blocks[_chunk_lba(0)] = PROMOTED_BLOCK
    blocks[_chunk_lba(3)] = PROMOTED_BLOCK
    return {"total_chunks": total, "blocks": blocks}


def closure_initial(phase: str, seed: str):
    if phase == "step4":
        media = scenario_initial("fresh_alloc_full")
        blocks = clone_media(media)["blocks"]
        # Land phase-1 copy and steps 2/3 completely; leave the old SB selected.
        for w in transaction("fresh_alloc_full")[:5]:
            blocks[w["lba"]][:] = w["data"]
        total = 8
        current = superblock(10, 2, 0, 0, total_chunks=total)
        target = superblock(11, 4, 1, 3, total_chunks=total)
    elif phase == "step5_decline":
        media = scenario_initial("first_use_s0")
        blocks = clone_media(media)["blocks"]
        for w in transaction("first_use_s0")[:4]:
            blocks[w["lba"]][:] = w["data"]
        total = 4
        current = superblock(2, 1, 1, 0, total_chunks=total)
        target = superblock(3, 1, 0, 0, total_chunks=total)
    elif phase == "step9":
        media = scenario_initial("fresh_alloc_full")
        blocks = clone_media(media)["blocks"]
        for w in transaction("fresh_alloc_full")[:12]:
            blocks[w["lba"]][:] = w["data"]
        total = 8
        current = superblock(11, 4, 1, 3, total_chunks=total)
        target = superblock(12, 1, 0, 0, total_chunks=total)
    else:
        raise KeyError(phase)

    stale = superblock(max(1, struct.unpack_from("<I", current, 12)[0] - 2), 0, 0, 0, total_chunks=total)
    primary = 0
    mirror = mirror_lba(total)

    if seed == "primary_only":
        blocks[primary][:] = current
        blocks[mirror][:] = ZERO_BLOCK
        partner = mirror
    elif seed == "mirror_only":
        blocks[mirror][:] = current
        blocks[primary][:] = ZERO_BLOCK
        partner = primary
    elif seed == "primary_current_mirror_stale":
        blocks[primary][:] = current
        blocks[mirror][:] = stale
        partner = mirror
    elif seed == "mirror_current_primary_stale":
        blocks[mirror][:] = current
        blocks[primary][:] = stale
        partner = primary
    else:
        raise KeyError(seed)

    return {
        "media": freeze_media({"total_chunks": total, "blocks": blocks}),
        "target": _write(phase + "_partner", "superblock", partner, target),
        "current_generation": struct.unpack_from("<I", current, 12)[0],
        "target_generation": struct.unpack_from("<I", target, 12)[0],
    }


def promoted_audio_sha256():
    return hashlib.sha256(PROMOTED_BLOCK).hexdigest()


def old_a_audio_sha256():
    return hashlib.sha256(OLD_A_BLOCK).hexdigest()
