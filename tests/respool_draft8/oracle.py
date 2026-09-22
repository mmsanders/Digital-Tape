#!/usr/bin/env python3
"""Independent DRAFT-8 WP-12 re-spool oracle.

Authored from frozen TapeFS §§4.2, 4.5, 5, 7, 8, 9.4 and Engine API §9.
No product implementation imports.
"""
from __future__ import annotations

import math
import struct
import zlib
from dataclasses import dataclass

CF = 131072
SAMPLE_RATE = 44100
NOMINAL_LENGTH_S = 60
CHUNK_BYTES = 524288
BLOCK = 512
BLOCKS_PER_CHUNK = CHUNK_BYTES // BLOCK
SLOT_BYTES = 65536
SLOT_BLOCKS = SLOT_BYTES // BLOCK
TAPE_MAX_ENTRIES = 4096
LBA_A0, LBA_A1, LBA_B0, LBA_B1, LBA_CHUNK_BASE = 8, 136, 264, 392, 2048
SEQ_CAP = 0xFFFFFFFD
SEMANTIC_BUDGET = 65535
HASHES = {
    "tapefs-v1.md": "3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb",
    "engine-api.md": "537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1",
    "acceptance.md": "7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7",
}


@dataclass(frozen=True)
class Media:
    blocks: int
    primary: bytes
    mirror: bytes
    slots: tuple[bytes, bytes, bytes, bytes]

    def encode(self) -> bytes:
        assert len(self.primary) == BLOCK and len(self.mirror) == BLOCK
        assert all(len(x) == SLOT_BYTES for x in self.slots)
        return b"VO08" + struct.pack("<I", self.blocks) + self.primary + self.mirror + b"".join(self.slots)

    @staticmethod
    def decode(data: bytes) -> "Media":
        need = 8 + 2 * BLOCK + 4 * SLOT_BYTES
        if len(data) != need or data[:4] != b"VO08":
            raise ValueError("bad VO08")
        blocks = struct.unpack_from("<I", data, 4)[0]
        p = 8
        primary = data[p : p + BLOCK]
        p += BLOCK
        mirror = data[p : p + BLOCK]
        p += BLOCK
        slots = [data[p + i * SLOT_BYTES : p + (i + 1) * SLOT_BYTES] for i in range(4)]
        return Media(blocks, primary, mirror, tuple(slots))


@dataclass(frozen=True)
class PassPlan:
    start_chunk: int
    end_chunk: int
    slot: int
    sequence: int
    entries: tuple[tuple[int, int, int], ...]
    require_full_timeline_blocks: bool = False


@dataclass(frozen=True)
class Case:
    id: str
    pre: Media
    mount_side: str
    expect_result: str
    expect_promote: str | None
    passes: tuple[PassPlan, ...]
    expect_stage_clear: bool
    expected_post: Media | None


def derived_total_chunks(nominal=NOMINAL_LENGTH_S) -> int:
    return (nominal * SAMPLE_RATE + CF - 1) // CF


def sb(*, generation=7, high=3, chunks=None, blocks=None, stage=0, staging=0) -> bytes:
    if chunks is None:
        chunks = derived_total_chunks()
    if blocks is None:
        blocks = LBA_CHUNK_BASE + chunks * BLOCKS_PER_CHUNK + 1
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
    struct.pack_into("<I", b, 52, chunks)
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
    for i, e in enumerate(entries):
        struct.pack_into("<III", b, 512 + 12 * i, *e)
    struct.pack_into("<I", b, 60, zlib.crc32(b[:60] + b[512 : 512 + 12 * len(entries)]))
    return bytes(b)


def invalid_slot() -> bytes:
    return bytes(SLOT_BYTES)


def sb_valid(b: bytes) -> bool:
    return len(b) == BLOCK and b[:8] == b"TAPEFS\0\x01" and struct.unpack_from("<I", b, 508)[0] == zlib.crc32(b[:508])


def select_sb(m: Media) -> bytes:
    vp, vm = sb_valid(m.primary), sb_valid(m.mirror)
    if not vp and not vm:
        raise ValueError("no sb")
    if vp and not vm:
        return m.primary
    if vm and not vp:
        return m.mirror
    gp = struct.unpack_from("<I", m.primary, 12)[0]
    gm = struct.unpack_from("<I", m.mirror, 12)[0]
    if gp == gm:
        if m.primary != m.mirror:
            raise ValueError("divergent")
        return m.primary
    return m.primary if gp > gm else m.mirror


def parse_entries(s: bytes):
    count = struct.unpack_from("<I", s, 16)[0]
    return [struct.unpack_from("<III", s, 512 + 12 * i) for i in range(count)]


def structural_sequence(s: bytes):
    if len(s) != SLOT_BYTES or s[:8] != b"TAPEIDX\x01":
        return None
    count = struct.unpack_from("<I", s, 16)[0]
    if count > TAPE_MAX_ENTRIES:
        return None
    stored = struct.unpack_from("<I", s, 60)[0]
    if stored != zlib.crc32(s[:60] + s[512 : 512 + 12 * count]):
        return None
    return struct.unpack_from("<I", s, 8)[0]


def semantic_valid(s: bytes, side: int, superblock: bytes) -> bool:
    if structural_sequence(s) is None or s[12] != side:
        return False
    entries = parse_entries(s)
    if struct.unpack_from("<Q", s, 20)[0] != sum(e[2] for e in entries):
        return False
    chunks = struct.unpack_from("<I", superblock, 52)[0]
    high = struct.unpack_from("<I", superblock, 56)[0]
    intervals = []
    for first, start, n in entries:
        if n < 1 or start >= CF:
            return False
        last = first + (start + n - 1) // CF
        if last >= chunks or (side == 0 and last >= high):
            return False
        lo = first * CF + start
        intervals.append((lo, lo + n))
    intervals.sort()
    return not any(intervals[i][1] > intervals[i + 1][0] for i in range(len(intervals) - 1))


def live_slot(m: Media, side: int):
    sbx = select_sb(m)
    ids = (0, 1) if side == 0 else (2, 3)
    valid = [i for i in ids if semantic_valid(m.slots[i], side, sbx)]
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
    seq = [structural_sequence(s) for s in m.slots]
    seq = [x for x in seq if x is not None]
    if not seq:
        raise ValueError("no structural index")
    return max(seq)


def entry_chunks(entries) -> set[int]:
    out = set()
    for first, start, n in entries:
        last = first + (start + n - 1) // CF
        out.update(range(first, last + 1))
    return out


def free_next(m: Media) -> int:
    high = struct.unpack_from("<I", select_sb(m), 56)[0]
    b = live_slot(m, 1)
    if b is None:
        return high
    chunks = entry_chunks(parse_entries(m.slots[b]))
    return max([high] + [x + 1 for x in chunks])


def media(high: int, b_entries, *, b_seq=20, a_entries=((0, 0, 128),), a_seq=10, partner_seq=700, b1=None, stage=0, staging=0) -> Media:
    chunks = derived_total_chunks()
    blocks = LBA_CHUNK_BASE + chunks * BLOCKS_PER_CHUNK + 1
    s = sb(high=high, chunks=chunks, blocks=blocks, stage=stage, staging=staging)
    b1s = invalid_slot() if b1 is None else idx(1, b1[0], b1[1])
    return Media(
        blocks,
        s,
        s,
        (
            idx(0, list(a_entries), a_seq),
            idx(1, [(1, 0, 64)], partner_seq),  # structurally valid; wrong side for A
            idx(1, list(b_entries), b_seq),
            b1s,
        ),
    )


def with_slot(m: Media, slot: int, data: bytes) -> Media:
    slots = list(m.slots)
    slots[slot] = data
    return Media(m.blocks, m.primary, m.mirror, tuple(slots))


def cleared_superblocks(m: Media) -> Media:
    b = bytearray(select_sb(m))
    struct.pack_into("<I", b, 12, struct.unpack_from("<I", b, 12)[0] + 1)
    struct.pack_into("<I", b, 124, 0)
    struct.pack_into("<I", b, 128, 0)
    struct.pack_into("<I", b, 508, zlib.crc32(b[:508]))
    bb = bytes(b)
    return Media(m.blocks, bb, bb, m.slots)


def _post_after_passes(pre: Media, passes: tuple[PassPlan, ...], stage_clear=False) -> Media:
    post = cleared_superblocks(pre) if stage_clear else pre
    slots = list(post.slots)
    for p in passes:
        slots[p.slot] = idx(1, list(p.entries), p.sequence)
    return Media(post.blocks, post.primary, post.mirror, tuple(slots))


def make_cases() -> list[Case]:
    # Empty branch deliberately carries a structurally-valid 0xFFFFFFFF sequence:
    # zero-consumption branches must not consult sequence headroom.
    empty = media(3, [], partner_seq=0xFFFFFFFF)

    # Acceptance V3-003: old B is [10,12), pass 1 must be [12,14), then
    # pass 2 can safely reclaim [10,12) only after pass 1 commits.
    two = media(10, [(10, 0, 2 * CF)])
    two_passes = (
        PassPlan(12, 14, 3, 701, ((12, 0, 2 * CF),), True),
        PassPlan(10, 12, 2, 702, ((10, 0, 2 * CF),), True),
    )

    # Exactly one one-chunk pass-1 destination exists: chunk 10. B currently
    # references every chunk 11..20, but only ten frames total, so len == 1.
    # After pass 1 lands at H there is no strictly-lower qualifying run.
    decline_entries = [(x, 0, 1) for x in range(11, 21)]
    decline = media(10, decline_entries)
    decline_pass = (PassPlan(10, 11, 3, 701, ((10, 0, 10),), False),)

    # No two-chunk destination disjoint from live B exists at/above H.
    full = media(19, [(19, 0, 2 * CF)])

    # Equal-sequence divergent B slots: Side-A mount enters degraded-B;
    # a Side-B mount would itself refuse and never reach tape_respool.
    degraded = media(3, [(0, 0, 256)], b_seq=500, b1=([(1, 0, 128)], 500))

    exhausted = media(10, [(10, 0, 2 * CF)], partner_seq=SEQ_CAP)

    # Exactly one sequence remains. Pass 1 is required; pass 2 is optional and
    # therefore skipped even though the V3-003 lower destination would exist.
    one_commit = media(10, [(10, 0, 2 * CF)], partner_seq=0xFFFFFFFC)
    one_pass = (PassPlan(12, 14, 3, SEQ_CAP, ((12, 0, 2 * CF),), True),)

    # Mountable §9.3.3 row-1 stage state. H=S+len=4; A == B at S=3.
    staged = media(
        4,
        [(3, 0, 128)],
        a_entries=((3, 0, 128),),
        stage=1,
        staging=3,
    )
    stage_pass = (PassPlan(4, 5, 3, 701, ((4, 0, 128),), False),)

    return [
        Case("WP12-EMPTY", empty, "B", "TAPE_OK", "TAPE_ERR_INVALID_ARG", (), False, empty),
        Case("WP12-TWOPASS", two, "B", "TAPE_OK", None, two_passes, False, _post_after_passes(two, two_passes)),
        Case("WP12-DECLINE", decline, "B", "TAPE_OK", None, decline_pass, False, _post_after_passes(decline, decline_pass)),
        Case("WP12-FULL", full, "B", "TAPE_ERR_CARTRIDGE_FULL", None, (), False, full),
        Case("WP12-DEGRADED", degraded, "A", "TAPE_ERR_NO_VALID_INDEX", None, (), False, degraded),
        Case("WP12-SEQ-EXHAUSTED", exhausted, "B", "TAPE_ERR_SEQUENCE_EXHAUSTED", None, (), False, exhausted),
        Case("WP12-ONE-COMMIT", one_commit, "B", "TAPE_OK", None, one_pass, False, _post_after_passes(one_commit, one_pass)),
        Case("WP12-STAGE-CLEAR", staged, "B", "TAPE_OK", None, stage_pass, True, _post_after_passes(staged, stage_pass, True)),
    ]


def fixture_contract_errors(case: Case) -> list[str]:
    err = []
    if derived_total_chunks() != 21:
        err.append("geometry drift")
    if case.pre.primary != case.pre.mirror:
        err.append("fixture superblocks differ")

    if case.id == "WP12-EMPTY":
        if live_slot(case.pre, 1) != 2 or parse_entries(case.pre.slots[2]) != []:
            err.append("empty B premise")
        if cartridge_sequence(case.pre) != 0xFFFFFFFF:
            err.append("empty branch does not exercise zero-needed high sequence")

    if case.id in ("WP12-TWOPASS", "WP12-ONE-COMMIT"):
        if struct.unpack_from("<I", select_sb(case.pre), 56)[0] != 10:
            err.append("H!=10")
        if parse_entries(case.pre.slots[2]) != [(10, 0, 2 * CF)] or free_next(case.pre) != 12:
            err.append("V3-003 B/free_next premise")
        if live_slot(case.pre, 1) != 2:
            err.append("V3-003 live B")

    if case.id == "WP12-DECLINE":
        if struct.unpack_from("<I", select_sb(case.pre), 56)[0] != 10:
            err.append("decline H!=10")
        if entry_chunks(parse_entries(case.pre.slots[2])) != set(range(11, 21)):
            err.append("decline fixture does not occupy chunks 11..20")
        if sum(x[2] for x in parse_entries(case.pre.slots[2])) != 10:
            err.append("decline fixture len is not one chunk")

    if case.id == "WP12-FULL":
        if free_next(case.pre) != 21 or entry_chunks(parse_entries(case.pre.slots[2])) != {19, 20}:
            err.append("full fixture premise")

    if case.id == "WP12-DEGRADED":
        if live_slot(case.pre, 0) != 0:
            err.append("degraded fixture lost Side A")
        if live_slot(case.pre, 1) is not None:
            err.append("degraded fixture unexpectedly has live B")

    if case.id == "WP12-SEQ-EXHAUSTED" and cartridge_sequence(case.pre) != SEQ_CAP:
        err.append("sequence-exhausted fixture not at cap")

    if case.id == "WP12-ONE-COMMIT" and cartridge_sequence(case.pre) != 0xFFFFFFFC:
        err.append("one-commit fixture does not have exactly one sequence remaining")

    if case.id == "WP12-STAGE-CLEAR":
        sbx = select_sb(case.pre)
        if struct.unpack_from("<I", sbx, 124)[0] != 1 or struct.unpack_from("<I", sbx, 128)[0] != 3:
            err.append("stage fixture fields")
        if struct.unpack_from("<I", sbx, 56)[0] != 4:
            err.append("stage fixture H!=S+len")
        if live_slot(case.pre, 0) != 0 or live_slot(case.pre, 1) != 2:
            err.append("stage fixture lost live A/B")
        if parse_entries(case.pre.slots[0]) != [(3, 0, 128)] or parse_entries(case.pre.slots[2]) != [(3, 0, 128)]:
            err.append("stage fixture is not §9.3.3 row 1")
    return err


def _writes(events):
    return [e for e in events if e.get("op") == "write"]


def _flushes(events):
    return [e for e in events if e.get("op") == "flush"]


def _touches_lba(e, lba: int) -> bool:
    return (
        e.get("op") == "write"
        and isinstance(e.get("lba"), int)
        and isinstance(e.get("count"), int)
        and e["lba"] <= lba < e["lba"] + e["count"]
    )


def _chunks_touched(e) -> set[int]:
    if e.get("op") != "write" or e.get("lba", -1) < LBA_CHUNK_BASE:
        return set()
    start = (e["lba"] - LBA_CHUNK_BASE) // BLOCKS_PER_CHUNK
    end_lba = e["lba"] + e["count"] - 1
    end = (end_lba - LBA_CHUNK_BASE) // BLOCKS_PER_CHUNK
    return set(range(start, end + 1))


def _slot_lba(slot: int) -> int:
    return (LBA_A0, LBA_A1, LBA_B0, LBA_B1)[slot]


def _verify_passes(case: Case, events: list[dict], err: list[str]) -> None:
    """Validate each copy+commit while updating the live-set at commit points."""
    ops = [e for e in events if e.get("op") in ("write", "flush")]
    cursor = 0
    sbx = select_sb(case.pre)
    high = struct.unpack_from("<I", sbx, 56)[0]
    total_chunks = struct.unpack_from("<I", sbx, 52)[0]

    live_a_slot = live_slot(case.pre, 0)
    live_b_slot = live_slot(case.pre, 1)
    live_a = entry_chunks(parse_entries(case.pre.slots[live_a_slot])) if live_a_slot is not None else set()
    live_b = entry_chunks(parse_entries(case.pre.slots[live_b_slot])) if live_b_slot is not None else set()

    def req(cond, msg):
        if not cond:
            err.append(msg)

    if case.expect_stage_clear:
        prefix = ops[:4]
        req(
            len(prefix) == 4
            and prefix[0].get("op") == "write" and prefix[0].get("lba") == case.pre.blocks - 1 and prefix[0].get("count") == 1
            and prefix[1].get("op") == "flush"
            and prefix[2].get("op") == "write" and prefix[2].get("lba") == 0 and prefix[2].get("count") == 1
            and prefix[3].get("op") == "flush",
            "stage clear is not partner -> flush -> candidate -> flush",
        )
        cursor = 4
    else:
        for e in _writes(events):
            req(not _touches_lba(e, 0) and not _touches_lba(e, case.pre.blocks - 1),
                "ordinary stage-0 respool issued a superblock write")

    for pass_no, plan in enumerate(case.passes, 1):
        slot_lba = _slot_lba(plan.slot)
        header_candidates = [
            i for i in range(cursor, len(ops))
            if ops[i].get("op") == "write" and ops[i].get("lba") == slot_lba and ops[i].get("count") == 1
        ]
        if not header_candidates:
            err.append(f"pass {pass_no} missing header commit to slot {plan.slot}")
            return
        header_i = header_candidates[0]

        # A header commit must be followed by a durability flush before the next pass.
        flush_after_header = next((i for i in range(header_i + 1, len(ops)) if ops[i].get("op") == "flush"), None)
        if flush_after_header is None:
            err.append(f"pass {pass_no} missing header flush")
            return

        seg = ops[cursor : flush_after_header + 1]
        seg_offset = cursor
        data_writes = []
        entry_writes = []
        for local_i, e in enumerate(seg):
            gi = seg_offset + local_i
            if e.get("op") != "write":
                continue
            if e.get("lba", -1) >= LBA_CHUNK_BASE:
                data_writes.append((gi, e))
            elif e.get("lba") == slot_lba + 1 and e.get("count") == 1:
                entry_writes.append((gi, e))
            elif e.get("lba") == slot_lba and e.get("count") == 1:
                pass  # expected commit header
            else:
                err.append(f"pass {pass_no} wrote unexpected metadata LBA {e.get('lba')}")

        req(bool(data_writes), f"pass {pass_no} copied no timeline blocks")
        req(bool(entry_writes), f"pass {pass_no} wrote no entry array")

        dest_lo = LBA_CHUNK_BASE + plan.start_chunk * BLOCKS_PER_CHUNK
        dest_hi = LBA_CHUNK_BASE + plan.end_chunk * BLOCKS_PER_CHUNK
        covered = set()
        for gi, e in data_writes:
            req(dest_lo <= e.get("lba", -1) and e.get("lba", -1) + e.get("count", 0) <= dest_hi,
                f"pass {pass_no} chunk write outside expected destination")
            chunks = _chunks_touched(e)
            req(all(high <= x < total_chunks for x in chunks), f"pass {pass_no} write violates H/geometry")
            req(chunks.isdisjoint(live_a), f"pass {pass_no} write intersects live Side A")
            req(chunks.isdisjoint(live_b), f"pass {pass_no} write intersects live Side B before commit")
            covered.update(range(e.get("lba", 0), e.get("lba", 0) + e.get("count", 0)))

        if plan.require_full_timeline_blocks:
            req(len(covered) == dest_hi - dest_lo and min(covered, default=dest_lo) == dest_lo and max(covered, default=dest_hi - 1) == dest_hi - 1,
                f"pass {pass_no} did not cover the full two-chunk timeline destination")

        last_data = max((i for i, _ in data_writes), default=-1)
        first_entry = min((i for i, _ in entry_writes), default=10**9)
        last_entry = max((i for i, _ in entry_writes), default=-1)
        between_data_entries = any(ops[i].get("op") == "flush" for i in range(last_data + 1, first_entry))
        between_entries_header = any(ops[i].get("op") == "flush" for i in range(last_entry + 1, header_i))
        req(last_data < first_entry < header_i, f"pass {pass_no} write ordering is not data -> entries -> header")
        req(between_data_entries, f"pass {pass_no} missing data flush before entries")
        req(between_entries_header, f"pass {pass_no} missing entry flush before header")
        req(ops[flush_after_header].get("op") == "flush", f"pass {pass_no} missing header flush")

        # Header is the commit point: only now may the next pass reuse the old live-B chunks.
        live_b = entry_chunks(plan.entries)
        cursor = flush_after_header + 1

    # No unexpected writes after the final pass.
    for e in ops[cursor:]:
        if e.get("op") == "write":
            err.append("write occurred after final expected pass")


def check(case: Case, post: Media, events: list[dict], calls: list[dict]) -> list[str]:
    err = []

    def req(cond, msg):
        if not cond:
            err.append(msg)

    req(post.blocks == case.pre.blocks, "block_count changed")

    mounts = [c for c in calls if c.get("fn") == "tape_mount"]
    req(
        len(mounts) == 1
        and mounts[0].get("result") == "TAPE_OK"
        and mounts[0].get("side") == case.mount_side,
        "mount did not succeed on scripted side",
    )

    if case.expect_promote is not None:
        prom = [c for c in calls if c.get("fn") == "tape_promote"]
        req(
            len(prom) == 1
            and prom[0].get("result") == case.expect_promote
            and prom[0].get("more_work") is False,
            "empty promote asymmetry/result",
        )

    res = [c for c in calls if c.get("fn") == "tape_respool"]
    req(len(res) == 1, "semantic tranche must use one generously-budgeted respool call")
    if res:
        req(res[0].get("block_budget") == SEMANTIC_BUDGET, "unexpected semantic tranche budget")
        req(res[0].get("result") == case.expect_result, "respool result")
        req(res[0].get("more_work") is False, "terminal more_work not false")

    unmounts = [c for c in calls if c.get("fn") == "tape_unmount"]
    req(len(unmounts) == 1 and unmounts[0].get("result") == "TAPE_OK", "unmount failed")

    if not case.passes:
        req(not _writes(events), "zero-write branch wrote")
        req(not _flushes(events), "zero-write branch flushed")
        req(post.encode() == case.pre.encode(), "zero-write branch changed media")
        return err

    req(case.expected_post is not None, "success case missing expected post")
    if case.expected_post is not None:
        req(post.encode() == case.expected_post.encode(), "post-media bytes differ from expected pass commits")

    # Side A indices never change under re-spool.
    req(post.slots[0] == case.pre.slots[0] and post.slots[1] == case.pre.slots[1], "respool changed Side A slots")

    live = live_slot(post, 1)
    req(live is not None, "post B not live")
    if live is not None:
        req(parse_entries(post.slots[live]) == list(case.passes[-1].entries), "final B is not expected one-entry compacted layout")
        req(structural_sequence(post.slots[live]) == case.passes[-1].sequence, "final B sequence mismatch")

    if case.expect_stage_clear:
        req(struct.unpack_from("<I", post.primary, 124)[0] == 0 and struct.unpack_from("<I", post.primary, 128)[0] == 0,
            "stage was not cleared")
        req(struct.unpack_from("<I", post.primary, 12)[0] == 8 and post.primary == post.mirror,
            "stage clear generation/copies wrong")
        req(struct.unpack_from("<I", post.primary, 56)[0] == struct.unpack_from("<I", case.pre.primary, 56)[0],
            "stage clear moved a_high_water")
    else:
        req(post.primary == case.pre.primary and post.mirror == case.pre.mirror, "ordinary respool changed superblock bytes")

    _verify_passes(case, events, err)

    # V3-003 specifically must leave both committed generations visible:
    # pass 1 in B1 at 701, pass 2 in B0 at 702.
    if case.id == "WP12-TWOPASS":
        req(structural_sequence(post.slots[3]) == 701 and parse_entries(post.slots[3]) == [(12, 0, 2 * CF)],
            "two-pass intermediate B1 commit missing")
        req(structural_sequence(post.slots[2]) == 702 and parse_entries(post.slots[2]) == [(10, 0, 2 * CF)],
            "two-pass final B0 commit missing")
        req(cartridge_sequence(post) == 702, "two-pass sequence base/result wrong")

    if case.id == "WP12-DECLINE":
        req(len(case.passes) == 1 and live == 3, "decline case did not stop after pass 1")

    if case.id == "WP12-ONE-COMMIT":
        req(cartridge_sequence(post) == SEQ_CAP and live == 3, "one-commit headroom case did not stop after pass 1")

    return err


def synth_calls(case: Case) -> list[dict]:
    calls = [{"phase": "mount", "fn": "tape_mount", "result": "TAPE_OK", "side": case.mount_side}]
    if case.expect_promote is not None:
        calls.append(
            {
                "phase": "promote",
                "fn": "tape_promote",
                "result": case.expect_promote,
                "more_work": False,
                "block_budget": SEMANTIC_BUDGET,
            }
        )
    calls.append(
        {
            "phase": "respool",
            "fn": "tape_respool",
            "result": case.expect_result,
            "more_work": False,
            "block_budget": SEMANTIC_BUDGET,
        }
    )
    calls.append({"phase": "unmount", "fn": "tape_unmount", "result": "TAPE_OK"})
    return calls


def _pass_events(plan: PassPlan) -> list[dict]:
    lo = LBA_CHUNK_BASE + plan.start_chunk * BLOCKS_PER_CHUNK
    hi = LBA_CHUNK_BASE + plan.end_chunk * BLOCKS_PER_CHUNK
    slot_lba = _slot_lba(plan.slot)
    if plan.require_full_timeline_blocks:
        data_count = hi - lo
    else:
        # At least the blocks containing referenced timeline bytes. Tail bytes in
        # a partial chunk are undefined, so the verifier does not require writing
        # the whole chunk in these small synthetic cases.
        frames = sum(e[2] for e in plan.entries)
        data_count = max(1, math.ceil(frames * 4 / BLOCK))
    return [
        {"phase": "respool", "op": "write", "lba": lo, "count": data_count},
        {"phase": "respool", "op": "flush"},
        {"phase": "respool", "op": "write", "lba": slot_lba + 1, "count": 1},
        {"phase": "respool", "op": "flush"},
        {"phase": "respool", "op": "write", "lba": slot_lba, "count": 1},
        {"phase": "respool", "op": "flush"},
    ]


def synth_post(case: Case):
    if not case.passes:
        return case.pre, []
    events = []
    if case.expect_stage_clear:
        events.extend(
            [
                {"phase": "respool", "op": "write", "lba": case.pre.blocks - 1, "count": 1},
                {"phase": "respool", "op": "flush"},
                {"phase": "respool", "op": "write", "lba": 0, "count": 1},
                {"phase": "respool", "op": "flush"},
            ]
        )
    for p in case.passes:
        events.extend(_pass_events(p))
    return case.expected_post, events


def synth_observation(case: Case):
    post, ev = synth_post(case)
    return post, ev, synth_calls(case)
