#!/usr/bin/env python3
"""Independent DRAFT-8 promote classification + uninterrupted metadata-path oracle.

Covers TapeFS §4.5 and §9.3.0–§9.3.2 without product implementation imports.
RESUME/crash behavior, copied-audio byte identity, stored-position integration,
and WP-12a continuation identity remain separate coverage.
"""
from __future__ import annotations

import hashlib
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

CF = 131072
SAMPLE_RATE = 44100
NOMINAL_LENGTH_S = 60
CHUNK_BYTES = 524288
BLOCK = 512
BLOCKS_PER_CHUNK = CHUNK_BYTES // BLOCK
SLOT_BYTES = 65536
TAPE_MAX_ENTRIES = 4096
LBA_A0, LBA_A1, LBA_B0, LBA_B1, LBA_CHUNK_BASE = 8, 136, 264, 392, 2048
SLOT_LBAS = (LBA_A0, LBA_A1, LBA_B0, LBA_B1)
MAX_COUNTER = 0xFFFFFFFD
SPEC_HASHES = {
    "tapefs-v1.md": "3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb",
    "engine-api.md": "537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1",
    "acceptance.md": "7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7",
}


class VerificationError(Exception):
    pass


def req(cond, msg):
    if not cond:
        raise VerificationError(msg)


def shafile(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_spec_dir(spec_dir: Path) -> dict[str, str]:
    out = {}
    for name, want in SPEC_HASHES.items():
        p = Path(spec_dir) / name
        if not p.is_file():
            raise VerificationError("missing spec byte source: " + str(p))
        got = shafile(p)
        if got != want:
            raise VerificationError(f"spec hash mismatch for {name}: got {got}, want {want}")
        out[name] = got
    return out


@dataclass(frozen=True)
class Media:
    blocks: int
    primary: bytes
    mirror: bytes
    slots: tuple[bytes, bytes, bytes, bytes]

    def encode(self) -> bytes:
        return b"VO08" + struct.pack("<I", self.blocks) + self.primary + self.mirror + b"".join(self.slots)

    @staticmethod
    def decode(data: bytes) -> "Media":
        need = 8 + 2 * BLOCK + 4 * SLOT_BYTES
        if len(data) != need or data[:4] != b"VO08":
            raise ValueError("bad VO08")
        blocks = struct.unpack_from("<I", data, 4)[0]
        p = 8
        primary = data[p:p + BLOCK]; p += BLOCK
        mirror = data[p:p + BLOCK]; p += BLOCK
        slots = tuple(data[p + i * SLOT_BYTES:p + (i + 1) * SLOT_BYTES] for i in range(4))
        return Media(blocks, primary, mirror, slots)


@dataclass(frozen=True)
class Case:
    id: str
    pre: Media
    mount_side: str
    expect: str
    path: str | None
    seq_needed: int
    gen_needed: int
    s: int | None = None
    length: int | None = None


def derived_total_chunks() -> int:
    return (NOMINAL_LENGTH_S * SAMPLE_RATE + CF - 1) // CF


def media_blocks() -> int:
    return LBA_CHUNK_BASE + derived_total_chunks() * BLOCKS_PER_CHUNK + 1


def sb(*, generation=7, high=3, stage=0, staging=0) -> bytes:
    blocks = media_blocks()
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
    struct.pack_into("<I", b, 52, derived_total_chunks())
    struct.pack_into("<I", b, 56, high)
    struct.pack_into("<I", b, 60, SLOT_BYTES)
    struct.pack_into("<I", b, 64, LBA_A0)
    struct.pack_into("<I", b, 68, LBA_A1)
    struct.pack_into("<I", b, 72, LBA_B0)
    struct.pack_into("<I", b, 76, LBA_B1)
    struct.pack_into("<I", b, 80, LBA_CHUNK_BASE)
    struct.pack_into("<I", b, 84, blocks - 1)
    struct.pack_into("<I", b, 124, stage)
    struct.pack_into("<I", b, 128, staging)
    struct.pack_into("<I", b, 508, zlib.crc32(b[:508]))
    return bytes(b)


def idx(side: int, entries, sequence: int) -> bytes:
    b = bytearray(SLOT_BYTES)
    b[:8] = b"TAPEIDX\x01"
    total = sum(e[2] for e in entries)
    struct.pack_into("<IB3xIQ", b, 8, sequence, side, len(entries), total)
    for i, entry in enumerate(entries):
        struct.pack_into("<III", b, 512 + 12 * i, *entry)
    struct.pack_into("<I", b, 60, zlib.crc32(b[:60] + b[512:512 + 12 * len(entries)]))
    return bytes(b)


def invalid_slot() -> bytes:
    return bytes(SLOT_BYTES)


def sb_valid(b: bytes) -> bool:
    return (
        len(b) == BLOCK
        and b[:8] == b"TAPEFS\0\x01"
        and struct.unpack_from("<I", b, 508)[0] == zlib.crc32(b[:508])
    )


def select_sb(m: Media) -> bytes:
    pv, mv = sb_valid(m.primary), sb_valid(m.mirror)
    if pv and mv:
        gp = struct.unpack_from("<I", m.primary, 12)[0]
        gm = struct.unpack_from("<I", m.mirror, 12)[0]
        if gp == gm and m.primary != m.mirror:
            raise ValueError("equal-generation divergent superblocks")
        return m.primary if gp >= gm else m.mirror
    if pv:
        return m.primary
    if mv:
        return m.mirror
    raise ValueError("no selectable superblock")


def parse_entries(slot: bytes):
    count = struct.unpack_from("<I", slot, 16)[0]
    return [struct.unpack_from("<III", slot, 512 + 12 * i) for i in range(count)]


def total_frames(slot: bytes) -> int:
    return struct.unpack_from("<Q", slot, 20)[0]


def structural_sequence(slot: bytes):
    if len(slot) != SLOT_BYTES or slot[:8] != b"TAPEIDX\x01":
        return None
    count = struct.unpack_from("<I", slot, 16)[0]
    if count > TAPE_MAX_ENTRIES:
        return None
    if struct.unpack_from("<I", slot, 60)[0] != zlib.crc32(slot[:60] + slot[512:512 + 12 * count]):
        return None
    return struct.unpack_from("<I", slot, 8)[0]


def semantic_valid(slot: bytes, side: int, superblock: bytes) -> bool:
    if structural_sequence(slot) is None or slot[12] != side:
        return False
    entries = parse_entries(slot)
    if total_frames(slot) != sum(e[2] for e in entries):
        return False
    chunks = struct.unpack_from("<I", superblock, 52)[0]
    high = struct.unpack_from("<I", superblock, 56)[0]
    intervals = []
    for first, start, frames in entries:
        if frames < 1 or start >= CF:
            return False
        last = first + (start + frames - 1) // CF
        if last >= chunks or (side == 0 and last >= high):
            return False
        lo = first * CF + start
        intervals.append((lo, lo + frames))
    intervals.sort()
    return not any(intervals[i][1] > intervals[i + 1][0] for i in range(len(intervals) - 1))


def live_slot(m: Media, side: int):
    superblock = select_sb(m)
    ids = (0, 1) if side == 0 else (2, 3)
    valid = [i for i in ids if semantic_valid(m.slots[i], side, superblock)]
    if not valid:
        return None
    if len(valid) == 1:
        return valid[0]
    a, b = valid
    sa, sbq = structural_sequence(m.slots[a]), structural_sequence(m.slots[b])
    if sa == sbq:
        return None
    return a if sa > sbq else b


def cartridge_sequence(m: Media) -> int:
    vals = [structural_sequence(slot) for slot in m.slots]
    vals = [v for v in vals if v is not None]
    return max(vals)


def entry_last(entry) -> int:
    first, start, frames = entry
    return first + (start + frames - 1) // CF


def free_next(m: Media) -> int:
    superblock = select_sb(m)
    high = struct.unpack_from("<I", superblock, 56)[0]
    b = live_slot(m, 1)
    if b is None:
        return high
    entries = parse_entries(m.slots[b])
    return max([high] + [entry_last(e) + 1 for e in entries])


def timeline_len(m: Media) -> int:
    b = live_slot(m, 1)
    if b is None:
        raise ValueError("no live B")
    frames = total_frames(m.slots[b])
    return (frames + CF - 1) // CF


def make_media(
    *,
    high,
    a_entries,
    b_entries,
    a_seq=10,
    b_seq=20,
    partner_seq=700,
    b1=None,
    generation=7,
) -> Media:
    superblock = sb(generation=generation, high=high)
    # A1 is deliberately structurally valid but semantically invalid for Side A:
    # its first chunk equals H. This lets cartridge_sequence include partner_seq
    # without stealing liveness from the intended A0 fixture.
    if partner_seq is None:
        a1 = invalid_slot()
    else:
        invalid_for_a_chunk = high
        if invalid_for_a_chunk >= derived_total_chunks():
            raise ValueError("fixture high leaves no semantically-invalid A partner")
        a1 = idx(0, [(invalid_for_a_chunk, 0, 64)], partner_seq)
    b1s = invalid_slot() if b1 is None else idx(1, b1[0], b1[1])
    return Media(
        media_blocks(),
        superblock,
        superblock,
        (
            idx(0, a_entries, a_seq),
            a1,
            idx(1, b_entries, b_seq),
            b1s,
        ),
    )


def make_cases() -> list[Case]:
    empty = make_media(high=3, a_entries=[(0, 0, 128)], b_entries=[])
    empty_high = make_media(
        high=3, a_entries=[(0, 0, 128)], b_entries=[],
        partner_seq=0xFFFFFFFF, generation=0xFFFFFFFF,
    )
    degraded = make_media(
        high=3, a_entries=[(0, 0, 128)], b_entries=[(0, 0, 64)],
        b_seq=500, b1=([(1, 0, 32)], 500),
    )
    nothing = make_media(high=3, a_entries=[(0, 0, 128)], b_entries=[(0, 0, 128)])
    nothing_high = make_media(
        high=3, a_entries=[(0, 0, 128)], b_entries=[(0, 0, 128)],
        partner_seq=0xFFFFFFFF, generation=0xFFFFFFFF,
    )

    adopt_complete = make_media(
        high=10, a_entries=[(0, 0, 128)], b_entries=[(10, 0, 2 * CF)],
        partner_seq=0xFFFFFFFA, generation=0xFFFFFFFB,
    )
    adopt_seq_exhausted = make_media(
        high=10, a_entries=[(0, 0, 128)], b_entries=[(10, 0, 2 * CF)],
        partner_seq=0xFFFFFFFB, generation=7,
    )
    adopt_gen_exhausted = make_media(
        high=10, a_entries=[(0, 0, 128)], b_entries=[(10, 0, 2 * CF)],
        partner_seq=700, generation=0xFFFFFFFC,
    )

    adopt_decline = make_media(
        high=2, a_entries=[(0, 0, 128)], b_entries=[(2, 0, 10 * CF)],
        partner_seq=0xFFFFFFFC, generation=0xFFFFFFFB,
    )
    decline_seq_exhausted = make_media(
        high=2, a_entries=[(0, 0, 128)], b_entries=[(2, 0, 10 * CF)],
        partner_seq=0xFFFFFFFD, generation=7,
    )
    decline_gen_exhausted = make_media(
        high=2, a_entries=[(0, 0, 128)], b_entries=[(2, 0, 10 * CF)],
        partner_seq=700, generation=0xFFFFFFFC,
    )

    alloc_complete = make_media(
        high=3, a_entries=[(0, 0, 128)], b_entries=[(3, 1, CF)],
        partner_seq=0xFFFFFFF9, generation=0xFFFFFFFB,
    )
    alloc_seq_exhausted = make_media(
        high=3, a_entries=[(0, 0, 128)], b_entries=[(3, 1, CF)],
        partner_seq=0xFFFFFFFA, generation=7,
    )
    alloc_gen_exhausted = make_media(
        high=3, a_entries=[(0, 0, 128)], b_entries=[(3, 1, CF)],
        partner_seq=700, generation=0xFFFFFFFC,
    )

    full = make_media(high=19, a_entries=[(0, 0, 128)], b_entries=[(19, 10, CF)])
    full_headroom_first = make_media(
        high=19, a_entries=[(0, 0, 128)], b_entries=[(19, 10, CF)],
        partner_seq=0xFFFFFFFA,
    )

    return [
        Case("PR-EMPTY", empty, "B", "TAPE_ERR_INVALID_ARG", None, 0, 0),
        Case("PR-EMPTY-HIGH-COUNTERS", empty_high, "B", "TAPE_ERR_INVALID_ARG", None, 0, 0),
        Case("PR-DEGRADED", degraded, "A", "TAPE_ERR_NO_VALID_INDEX", None, 0, 0),
        Case("PR-NOTHING", nothing, "B", "TAPE_OK", None, 0, 0),
        Case("PR-NOTHING-HIGH-COUNTERS", nothing_high, "B", "TAPE_OK", None, 0, 0),

        Case("PR-ADOPT-COMPLETE", adopt_complete, "B", "TAPE_OK", "adopt-complete", 3, 2, 10, 2),
        Case("PR-ADOPT-SEQ-EXHAUSTED", adopt_seq_exhausted, "B", "TAPE_ERR_SEQUENCE_EXHAUSTED", None, 3, 2, 10, 2),
        Case("PR-ADOPT-GEN-EXHAUSTED", adopt_gen_exhausted, "B", "TAPE_ERR_SEQUENCE_EXHAUSTED", None, 3, 2, 10, 2),

        Case("PR-ADOPT-DECLINE", adopt_decline, "B", "TAPE_OK", "adopt-decline", 1, 2, 2, 10),
        Case("PR-DECLINE-SEQ-EXHAUSTED", decline_seq_exhausted, "B", "TAPE_ERR_SEQUENCE_EXHAUSTED", None, 1, 2, 2, 10),
        Case("PR-DECLINE-GEN-EXHAUSTED", decline_gen_exhausted, "B", "TAPE_ERR_SEQUENCE_EXHAUSTED", None, 1, 2, 2, 10),

        Case("PR-ALLOC-COMPLETE", alloc_complete, "B", "TAPE_OK", "alloc-complete", 4, 2, 5, 1),
        Case("PR-ALLOC-SEQ-EXHAUSTED", alloc_seq_exhausted, "B", "TAPE_ERR_SEQUENCE_EXHAUSTED", None, 4, 2, 5, 1),
        Case("PR-ALLOC-GEN-EXHAUSTED", alloc_gen_exhausted, "B", "TAPE_ERR_SEQUENCE_EXHAUSTED", None, 4, 2, 5, 1),

        Case("PR-FULL", full, "B", "TAPE_ERR_CARTRIDGE_FULL", None, 4, 2, 21, 1),
        Case("PR-FULL-HEADROOM-FIRST", full_headroom_first, "B", "TAPE_ERR_SEQUENCE_EXHAUSTED", None, 4, 2, 21, 1),
    ]


def headroom_available(case: Case) -> bool:
    if case.seq_needed:
        if cartridge_sequence(case.pre) + case.seq_needed > MAX_COUNTER:
            return False
    if case.gen_needed:
        generation = struct.unpack_from("<I", select_sb(case.pre), 12)[0]
        if generation + case.gen_needed > MAX_COUNTER:
            return False
    return True


def fixture_contract_errors(case: Case) -> list[str]:
    err = []
    if derived_total_chunks() != 21 or case.pre.blocks != media_blocks():
        err.append("geometry drift")
    if case.pre.primary != case.pre.mirror:
        err.append("fixture superblocks differ")
    if live_slot(case.pre, 0) != 0:
        err.append("A0 is not the live Side A slot")
    if case.id == "PR-DEGRADED":
        if live_slot(case.pre, 1) is not None:
            err.append("degraded-B premise")
    elif live_slot(case.pre, 1) != 2:
        err.append("B0 is not the live Side B slot")

    if case.id.startswith("PR-EMPTY"):
        if total_frames(case.pre.slots[2]) != 0 or parse_entries(case.pre.slots[2]):
            err.append("empty-B premise")
    if case.id.startswith("PR-NOTHING"):
        if parse_entries(case.pre.slots[0]) != parse_entries(case.pre.slots[2]):
            err.append("NOTHING TO DO entry arrays differ")
    if case.path and case.s is not None and case.length is not None:
        if timeline_len(case.pre) != case.length:
            err.append("timeline len premise")
        b = parse_entries(case.pre.slots[2])
        adopt = len(b) == 1 and b[0][1] == 0 and b[0][0] >= struct.unpack_from("<I", select_sb(case.pre), 56)[0]
        if case.path.startswith("adopt") and not adopt:
            err.append("adopt-in-place premise")
        if case.path == "alloc-complete" and adopt:
            err.append("allocating path accidentally adopts")
        if case.path == "alloc-complete" and free_next(case.pre) != case.s:
            err.append("allocating S/free_next premise")
        if case.path == "adopt-complete" and not (case.s >= case.length):
            err.append("complete disjointness premise")
        if case.path == "adopt-decline" and not (case.s < case.length):
            err.append("decline overlap premise")

    if case.id == "PR-FULL":
        if not headroom_available(case):
            err.append("FULL case lacks counter headroom")
        if derived_total_chunks() - free_next(case.pre) >= timeline_len(case.pre):
            err.append("FULL case has staging room")
    if case.id == "PR-FULL-HEADROOM-FIRST":
        if headroom_available(case):
            err.append("headroom-first case unexpectedly has headroom")
        if derived_total_chunks() - free_next(case.pre) >= timeline_len(case.pre):
            err.append("headroom-first case is not also full")

    if "EXHAUSTED" in case.id or case.id == "PR-FULL-HEADROOM-FIRST":
        if case.seq_needed or case.gen_needed:
            if headroom_available(case):
                err.append("exhaustion premise has enough headroom")
    if case.path and not headroom_available(case):
        err.append("successful path lacks exact branch headroom")
    return err


def chunk_lba(chunk: int) -> int:
    return LBA_CHUNK_BASE + chunk * BLOCKS_PER_CHUNK


def _commit_events(lba: int) -> list[dict]:
    return [
        {"phase": "promote", "op": "write", "lba": lba + 1, "count": 1},
        {"phase": "promote", "op": "flush"},
        {"phase": "promote", "op": "write", "lba": lba, "count": 1},
        {"phase": "promote", "op": "flush"},
    ]


def _sb_events(blocks: int) -> list[dict]:
    return [
        {"phase": "promote", "op": "write", "lba": blocks - 1, "count": 1},
        {"phase": "promote", "op": "flush"},
        {"phase": "promote", "op": "write", "lba": 0, "count": 1},
        {"phase": "promote", "op": "flush"},
    ]


def _chunk_events(start: int, length: int) -> list[dict]:
    return [
        {"phase": "promote", "op": "write", "lba": chunk_lba(start), "count": length * BLOCKS_PER_CHUNK},
        {"phase": "promote", "op": "flush"},
    ]


def expected_post(case: Case) -> Media:
    if case.path is None:
        return case.pre
    p = case.pre
    slots = list(p.slots)
    base = cartridge_sequence(p)
    gen0 = struct.unpack_from("<I", select_sb(p), 12)[0]
    n = total_frames(p.slots[2])
    s = case.s
    length = case.length
    staging_entries = [(s, 0, n)]
    final_entries = [(0, 0, n)]

    if case.path == "adopt-complete":
        slots[1] = idx(0, staging_entries, base + 1)
        slots[0] = idx(0, final_entries, base + 2)
        slots[3] = idx(1, final_entries, base + 3)
        final = sb(generation=gen0 + 2, high=length, stage=0, staging=0)
    elif case.path == "adopt-decline":
        slots[1] = idx(0, staging_entries, base + 1)
        final = sb(generation=gen0 + 2, high=s + length, stage=0, staging=0)
    elif case.path == "alloc-complete":
        slots[1] = idx(0, staging_entries, base + 1)
        slots[3] = idx(1, staging_entries, base + 2)
        slots[0] = idx(0, final_entries, base + 3)
        slots[2] = idx(1, final_entries, base + 4)
        final = sb(generation=gen0 + 2, high=length, stage=0, staging=0)
    else:
        raise ValueError("unknown success path")
    return Media(p.blocks, final, final, tuple(slots))


def synth_events(case: Case) -> list[dict]:
    if case.path is None:
        return []
    ev = []
    if case.path == "alloc-complete":
        ev += _chunk_events(case.s, case.length)
        ev += _commit_events(LBA_A1)
        ev += _commit_events(LBA_B1)
        ev += _sb_events(case.pre.blocks)
        ev += _chunk_events(0, case.length)
        ev += _commit_events(LBA_A0)
        ev += _commit_events(LBA_B0)
        ev += _sb_events(case.pre.blocks)
    elif case.path == "adopt-complete":
        ev += _commit_events(LBA_A1)
        ev += _sb_events(case.pre.blocks)
        ev += _chunk_events(0, case.length)
        ev += _commit_events(LBA_A0)
        ev += _commit_events(LBA_B1)
        ev += _sb_events(case.pre.blocks)
    elif case.path == "adopt-decline":
        ev += _commit_events(LBA_A1)
        ev += _sb_events(case.pre.blocks)
        ev += _sb_events(case.pre.blocks)
    return ev


def _writes(events):
    return [e for e in events if e.get("op") == "write"]


def _write_blocks(events, start: int, stop: int) -> set[int]:
    out = set()
    for e in _writes(events):
        try:
            first = int(e["lba"])
            count = int(e.get("count", 1))
        except (KeyError, TypeError, ValueError):
            continue
        lo, hi = max(first, start), min(first + max(count, 0), stop)
        if lo < hi:
            out.update(range(lo, hi))
    return out


def expected_chunk_blocks(case: Case) -> set[int]:
    if case.path is None or case.path == "adopt-decline":
        return set()
    runs = [(0, case.length)]
    if case.path == "alloc-complete":
        runs.insert(0, (case.s, case.length))
    out = set()
    for start, length in runs:
        out.update(range(chunk_lba(start), chunk_lba(start + length)))
    return out


def expected_metadata_lbas(case: Case) -> list[int]:
    mirror = case.pre.blocks - 1
    if case.path == "adopt-complete":
        return [LBA_A1 + 1, LBA_A1, mirror, 0, LBA_A0 + 1, LBA_A0, LBA_B1 + 1, LBA_B1, mirror, 0]
    if case.path == "adopt-decline":
        return [LBA_A1 + 1, LBA_A1, mirror, 0, mirror, 0]
    if case.path == "alloc-complete":
        return [
            LBA_A1 + 1, LBA_A1, LBA_B1 + 1, LBA_B1, mirror, 0,
            LBA_A0 + 1, LBA_A0, LBA_B0 + 1, LBA_B0, mirror, 0,
        ]
    return []


def trace_errors(case: Case, events: list[dict]) -> list[str]:
    err = []
    if case.path is None:
        if _writes(events):
            err.append("zero-write outcome issued a write")
        return err

    mirror = case.pre.blocks - 1
    chunk_blocks = _write_blocks(events, LBA_CHUNK_BASE, mirror)
    if chunk_blocks != expected_chunk_blocks(case):
        err.append("chunk write coverage/order branch mismatch")

    metadata_set = {
        0, mirror, LBA_A0, LBA_A0 + 1, LBA_A1, LBA_A1 + 1,
        LBA_B0, LBA_B0 + 1, LBA_B1, LBA_B1 + 1,
    }
    actual_meta = []
    meta_event_indexes = []
    for i, e in enumerate(events):
        if e.get("op") != "write":
            continue
        try:
            lba = int(e["lba"])
            count = int(e.get("count", 1))
        except (KeyError, TypeError, ValueError):
            err.append("malformed write event")
            continue
        if lba in metadata_set:
            if count != 1:
                err.append("metadata write is not one block")
            actual_meta.append(lba)
            meta_event_indexes.append(i)
    if actual_meta != expected_metadata_lbas(case):
        err.append("metadata commit/superblock write order mismatch")

    # Every metadata block write is followed by a flush before another write.
    for pos in meta_event_indexes:
        saw_flush = False
        for later in events[pos + 1:]:
            if later.get("op") == "flush":
                saw_flush = True
                break
            if later.get("op") == "write":
                break
        if not saw_flush:
            err.append("metadata write lacks immediate durability barrier")
            break

    # Invariant 21: no below-H chunk write until phase 1's stage=1 superblock
    # has completed partner-first/candidate-last.
    high0 = struct.unpack_from("<I", select_sb(case.pre), 56)[0]
    first_primary = next(
        (i for i, e in enumerate(events) if e.get("op") == "write" and e.get("lba") == 0),
        None,
    )
    if first_primary is None:
        err.append("missing phase-1 superblock candidate write")
    else:
        for e in events[:first_primary + 1]:
            if e.get("op") == "write":
                try:
                    lba = int(e["lba"])
                    count = int(e.get("count", 1))
                except (KeyError, TypeError, ValueError):
                    continue
                if lba < chunk_lba(high0) and lba + count > LBA_CHUNK_BASE:
                    err.append("promote wrote below original a_high_water before phase 2")
                    break
    return err


def check(case: Case, post: Media, events: list[dict], calls: list[dict]) -> list[str]:
    err = []

    def need(cond, msg):
        if not cond:
            err.append(msg)

    ferr = fixture_contract_errors(case)
    need(not ferr, "fixture contract: " + ",".join(ferr))

    mounts = [c for c in calls if c.get("fn") == "tape_mount"]
    need(bool(mounts), "missing tape_mount")
    if mounts:
        need(mounts[0].get("result") == "TAPE_OK", "mount failed")
        need(mounts[0].get("side") == case.mount_side, "wrong mount side for case")

    promotes = [c for c in calls if c.get("fn") == "tape_promote"]
    need(bool(promotes), "missing tape_promote")
    if promotes:
        for c in promotes[:-1]:
            need(c.get("result") == "TAPE_OK", "non-terminal promote result")
            need(c.get("more_work") is True, "non-terminal promote did not continue")
            need(int(c.get("block_budget", 0)) > 0, "non-positive promote budget")
        last = promotes[-1]
        need(last.get("result") == case.expect, "terminal promote result")
        need(last.get("more_work") is False, "terminal more_work not false")
        need(int(last.get("block_budget", 0)) > 0, "non-positive terminal budget")
        if case.path is None:
            need(len(promotes) == 1, "classification/refusal took continuation calls")

    unmounts = [c for c in calls if c.get("fn") == "tape_unmount"]
    need(bool(unmounts) and unmounts[-1].get("result") == "TAPE_OK", "unmount result")

    expected = expected_post(case)
    need(post.encode() == expected.encode(), "post-media bytes differ from DRAFT-8 oracle")
    err.extend(trace_errors(case, events))
    return err


def validate_observation(case: Case, post_bytes: bytes, observation: dict) -> list[str]:
    err = []
    if observation.get("format") != "WP-PROMOTE-OBSERVATION-1":
        err.append("observation format mismatch")
    if observation.get("case_id") != case.id:
        err.append("observation case_id mismatch")
    if observation.get("adapter_kind") not in ("synthetic", "product"):
        err.append("invalid adapter_kind")
    if not isinstance(observation.get("adapter_id"), str) or not observation.get("adapter_id", "").strip():
        err.append("missing adapter_id")
    calls = observation.get("calls")
    events = observation.get("events")
    if not isinstance(calls, list):
        err.append("calls is not a list"); calls = []
    if not isinstance(events, list):
        err.append("events is not a list"); events = []
    try:
        post = Media.decode(post_bytes)
    except (ValueError, struct.error) as exc:
        return err + ["bad output media: " + str(exc)]
    return err + check(case, post, events, calls)


def synth_calls(case: Case) -> list[dict]:
    calls = [{"phase": "mount", "fn": "tape_mount", "result": "TAPE_OK", "side": case.mount_side}]
    if case.path is not None:
        calls.append({
            "phase": "promote", "fn": "tape_promote", "result": "TAPE_OK",
            "more_work": True, "block_budget": 64,
        })
        calls.append({
            "phase": "promote", "fn": "tape_promote", "result": "TAPE_OK",
            "more_work": False, "block_budget": 64,
        })
    else:
        calls.append({
            "phase": "promote", "fn": "tape_promote", "result": case.expect,
            "more_work": False, "block_budget": 64,
        })
    calls.append({"phase": "unmount", "fn": "tape_unmount", "result": "TAPE_OK"})
    return calls


def synth_observation(case: Case):
    return expected_post(case), synth_events(case), synth_calls(case)
