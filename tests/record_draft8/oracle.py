#!/usr/bin/env python3
"""Independent DRAFT-8 WP-09 record-mode oracle.

Authored from frozen TapeFS §5, §7–§8, §9.1 and Engine API §§7, §8, §10, §11.
No product implementation imports.
"""
from __future__ import annotations

import hashlib
import struct
import zlib
from dataclasses import dataclass

CF = 131072
SAMPLE_RATE = 44100
NOMINAL_LENGTH_S = 60
CHUNK_BYTES = 524288
TAPE_MAX_ENTRIES = 4096
BLOCK = 512
BLOCKS_PER_CHUNK = CHUNK_BYTES // BLOCK
SLOT_BYTES = 65536
LBA_A0, LBA_A1, LBA_B0, LBA_B1, LBA_CHUNK_BASE = 8, 136, 264, 392, 2048
HASHES = {
    "tapefs-v1.md": "3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb",
    "engine-api.md": "537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1",
    "acceptance.md": "7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7",
}
SLOT_LBAS = [LBA_A0, LBA_A1, LBA_B0, LBA_B1]
MODES = {
    "WP09-OW-MID": "overwrite",
    "WP09-OW-END": "overwrite",
    "WP09-OD-MID": "overdub",
    "WP09-SP-T0": "splice",
    "WP09-SP-MID": "splice",
    "WP09-SP-END": "splice",
    "WP09-EMPTY-COMMIT": "overwrite",
    "WP09-ARMED-BUSY": "overwrite",
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
            raise ValueError("bad VO08 media envelope")
        blocks = struct.unpack_from("<I", data, 4)[0]
        p = 8
        primary = data[p : p + BLOCK]
        p += BLOCK
        mirror = data[p : p + BLOCK]
        p += BLOCK
        slots = []
        for _ in range(4):
            slots.append(data[p : p + SLOT_BYTES])
            p += SLOT_BYTES
        return Media(blocks, primary, mirror, tuple(slots))


@dataclass(frozen=True)
class Case:
    id: str
    operation: str
    pre: Media
    seek: int
    feed: int
    expected_entries: list[tuple[int, int, int]] | None
    expected_total: int | None
    expect_commit_io: bool
    busy_calls: tuple[str, ...]


def derived_total_chunks(nominal_length_s: int) -> int:
    return (nominal_length_s * SAMPLE_RATE + CF - 1) // CF


def sb(*, generation=7, high=3, chunks=None, nominal_length_s=NOMINAL_LENGTH_S, stage=0, blocks=None) -> bytes:
    if chunks is None:
        chunks = derived_total_chunks(nominal_length_s)
    if blocks is None:
        blocks = LBA_CHUNK_BASE + chunks * BLOCKS_PER_CHUNK + 1
    b = bytearray(BLOCK)
    b[:8] = b"TAPEFS\0\x01"
    struct.pack_into("<H", b, 8, 1)
    struct.pack_into("<H", b, 10, 0)
    struct.pack_into("<I", b, 12, generation)
    struct.pack_into("<B", b, 16, 0)
    b[20:36] = bytes(range(16))
    struct.pack_into("<I", b, 36, SAMPLE_RATE)
    struct.pack_into("<H", b, 40, 2)
    struct.pack_into("<H", b, 42, 16)
    struct.pack_into("<I", b, 44, CHUNK_BYTES)
    struct.pack_into("<I", b, 48, nominal_length_s)
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
    struct.pack_into("<I", b, 508, zlib.crc32(b[:508]))
    return bytes(b)


def idx(side: int, entries, sequence: int) -> bytes:
    b = bytearray(SLOT_BYTES)
    b[:8] = b"TAPEIDX\x01"
    total = sum(e[2] for e in entries)
    struct.pack_into("<IB3xIQ", b, 8, sequence, side, len(entries), total)
    for i, e in enumerate(entries):
        struct.pack_into("<III", b, 512 + 12 * i, *e)
    crc = zlib.crc32(b[:60] + b[512 : 512 + 12 * len(entries)])
    struct.pack_into("<I", b, 60, crc)
    return bytes(b)


def invalid_slot() -> bytes:
    return bytes(SLOT_BYTES)


def sb_valid(b: bytes) -> bool:
    return len(b) == BLOCK and b[:8] == b"TAPEFS\0\x01" and struct.unpack_from("<I", b, 508)[0] == zlib.crc32(b[:508])


def select_sb(m: Media) -> bytes:
    vv = [sb_valid(m.primary), sb_valid(m.mirror)]
    if vv == [False, False]:
        raise ValueError("no valid superblock")
    if vv == [True, False]:
        return m.primary
    if vv == [False, True]:
        return m.mirror
    gp = struct.unpack_from("<I", m.primary, 12)[0]
    gm = struct.unpack_from("<I", m.mirror, 12)[0]
    if gp == gm:
        if m.primary != m.mirror:
            raise ValueError("equal-generation divergent superblocks")
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
    calc = zlib.crc32(s[:60] + s[512 : 512 + 12 * count])
    if stored != calc:
        return None
    return struct.unpack_from("<I", s, 8)[0]


def semantic_valid(s: bytes, assigned_side: int, superblock: bytes) -> bool:
    seq = structural_sequence(s)
    if seq is None:
        return False
    side = s[12]
    count = struct.unpack_from("<I", s, 16)[0]
    total = struct.unpack_from("<Q", s, 20)[0]
    if side != assigned_side:
        return False
    entries = parse_entries(s)
    if total != sum(e[2] for e in entries):
        return False
    chunks = struct.unpack_from("<I", superblock, 52)[0]
    high = struct.unpack_from("<I", superblock, 56)[0]
    intervals = []
    for first, start, n in entries:
        if n < 1 or start >= CF:
            return False
        span = start + n - 1
        last = first + span // CF
        if last >= chunks:
            return False
        if assigned_side == 0 and last >= high:
            return False
        lo = first * CF + start
        hi = lo + n
        intervals.append((lo, hi))
    intervals.sort()
    if any(intervals[i][1] > intervals[i + 1][0] for i in range(len(intervals) - 1)):
        return False
    return True


def live_slot(m: Media, side: int):
    sbx = select_sb(m)
    ids = (0, 1) if side == 0 else (2, 3)
    valid = [i for i in ids if semantic_valid(m.slots[i], side, sbx)]
    if not valid:
        return None
    if len(valid) == 1:
        return valid[0]
    a, b = valid
    sa = structural_sequence(m.slots[a])
    sbq = structural_sequence(m.slots[b])
    if sa == sbq:
        return None
    return a if sa > sbq else b


def cartridge_sequence(m: Media) -> int:
    seq = [structural_sequence(s) for s in m.slots]
    seq = [x for x in seq if x is not None]
    if not seq:
        raise ValueError("no structurally valid slot")
    return max(seq)


def free_next(m: Media) -> int:
    sbx = select_sb(m)
    high = struct.unpack_from("<I", sbx, 56)[0]
    b = live_slot(m, 1)
    if b is None:
        return high
    mx = high
    for first, start, n in parse_entries(m.slots[b]):
        last = first + (start + n - 1) // CF
        mx = max(mx, last + 1)
    return mx


def overdub_saturate(existing: int, incoming: int) -> int:
    s = int(existing) + int(incoming)
    if s > 32767:
        s = 32767
    if s < -32768:
        s = -32768
    return s


def base_fixture() -> Media:
    chunks = derived_total_chunks(NOMINAL_LENGTH_S)
    blocks = LBA_CHUNK_BASE + chunks * BLOCKS_PER_CHUNK + 1
    s = sb(chunks=chunks, blocks=blocks)
    return Media(
        blocks,
        s,
        s,
        (
            idx(0, [(0, 0, 128)], 10),
            idx(1, [(1, 0, 64)], 700),
            idx(1, [(0, 0, 256)], 20),
            invalid_slot(),
        ),
    )


def make_cases() -> list[Case]:
    pre = base_fixture()
    fn = 3
    cases = [
        Case("WP09-OW-MID", "overwrite_mid", pre, 128, 64, [(0, 0, 128), (fn, 0, 64)], 192, True, ()),
        Case("WP09-OW-END", "overwrite_end", pre, 256, 64, [(0, 0, 256), (fn, 0, 64)], 320, True, ()),
        Case("WP09-OD-MID", "overdub_mid", pre, 128, 64, [(0, 0, 128), (fn, 0, 64), (0, 192, 64)], 256, True, ()),
        Case("WP09-SP-T0", "splice_t0", pre, 0, 64, [(fn, 0, 64), (0, 0, 256)], 320, True, ()),
        Case("WP09-SP-MID", "splice_mid", pre, 128, 64, [(0, 0, 128), (fn, 0, 64), (0, 128, 128)], 320, True, ()),
        Case("WP09-SP-END", "splice_end", pre, 256, 64, [(0, 0, 256), (fn, 0, 64)], 320, True, ()),
        Case("WP09-EMPTY-COMMIT", "empty_commit", pre, 128, 0, [(0, 0, 256)], 256, False, ()),
        Case("WP09-ARMED-BUSY", "armed_busy", pre, 128, 0, [(0, 0, 256)], 256, False, ("tape_seek", "tape_set_rate")),
    ]
    for case in cases:
        errors = fixture_contract_errors(case)
        if errors:
            raise ValueError(case.id + ": " + "; ".join(errors))
    return cases


def fixture_contract_errors(case: Case) -> list[str]:
    errors = []
    media = case.pre
    if media.primary != media.mirror:
        errors.append("fixture superblock copies differ")
        return errors
    try:
        superblock = select_sb(media)
    except Exception as exc:
        return [f"fixture has no selectable superblock: {exc}"]
    stored_chunks = struct.unpack_from("<I", superblock, 52)[0]
    derived = derived_total_chunks(NOMINAL_LENGTH_S)
    if stored_chunks != derived:
        errors.append("fixture stored total_chunks differs from frozen derivation")
    if [structural_sequence(slot) for slot in media.slots] != [10, 700, 20, None]:
        errors.append("record fixture exact sequence premises drift")
    if cartridge_sequence(media) != 700:
        errors.append("record fixture all-slot sequence premise drift")
    if live_slot(media, 1) != 2:
        errors.append("record fixture live-B premise drift")
    if struct.unpack_from("<I", superblock, 56)[0] != 3 or free_next(media) != 3:
        errors.append("record fixture H/free_next premise drift")
    if parse_entries(media.slots[2]) != [(0, 0, 256)]:
        errors.append("record fixture source-entry premise drift")
    if case.id not in MODES:
        errors.append("unknown fixture case")
    return errors


def _writes(events, phase=None):
    return [e for e in events if e.get("op") == "write" and (phase is None or e.get("phase") == phase)]


def _chunk_bounds(m: Media, chunk: int):
    base = struct.unpack_from("<I", select_sb(m), 80)[0]
    return base + chunk * BLOCKS_PER_CHUNK, base + (chunk + 1) * BLOCKS_PER_CHUNK


def call_named(calls, name):
    return [c for c in calls if c.get("fn") == name]


def check(case: Case, post: Media, events: list[dict], calls: list[dict]) -> list[str]:
    err = []

    def req(x, msg):
        if not x:
            err.append(msg)

    def touches(e, lba):
        return (
            e.get("op") == "write"
            and isinstance(e.get("lba"), int)
            and isinstance(e.get("count"), int)
            and e["lba"] <= lba < e["lba"] + e["count"]
        )

    pre = case.pre
    req(pre.blocks == post.blocks, "block_count changed")
    req(cartridge_sequence(pre) == 700, "fixture lost high structural sequence")
    req(live_slot(pre, 1) == 2, "fixture B0 not live")
    req(post.primary == pre.primary and post.mirror == pre.mirror, "ordinary recording changed superblock")
    req(post.slots[0] == pre.slots[0] and post.slots[1] == pre.slots[1], "record changed Side A slots")

    # Ordinary stage-0 recording must not even issue a superblock write. Comparing
    # final bytes alone would miss a redundant same-byte write.
    for e in _writes(events):
        req(not touches(e, 0) and not touches(e, pre.blocks - 1), "ordinary recording issued superblock write")

    mounts = call_named(calls, "tape_mount")
    req(bool(mounts) and mounts[0].get("result") == "TAPE_OK" and mounts[0].get("side") == "B", "mount did not succeed on Side B")
    seeks = call_named(calls, "tape_seek")
    req(bool(seeks) and seeks[0].get("frame") == case.seek and seeks[0].get("result") == "TAPE_OK", "scripted seek mismatch")
    arms = call_named(calls, "tape_arm")
    req(bool(arms) and arms[0].get("result") == "TAPE_OK" and arms[0].get("mode") == MODES[case.id], "arm mismatch")

    if case.id == "WP09-ARMED-BUSY":
        armed_seek = [c for c in calls if c.get("fn") == "tape_seek" and c.get("phase") == "armed"]
        armed_rate = [c for c in calls if c.get("fn") == "tape_set_rate" and c.get("phase") == "armed"]
        req(len(armed_seek) == 1 and armed_seek[0].get("result") == "TAPE_ERR_BUSY" and armed_seek[0].get("frame") == 0,
            "armed seek probe missing or not BUSY")
        req(len(armed_rate) == 1 and armed_rate[0].get("result") == "TAPE_ERR_BUSY" and armed_rate[0].get("rate_q16_16") == 65536,
            "armed set_rate probe missing or not BUSY")
        req(not events, "armed BUSY/abort path issued block I/O")
        req(post.slots == pre.slots, "armed BUSY changed an index slot")
        aborts = call_named(calls, "tape_abort")
        req(len(aborts) == 1 and aborts[0].get("result") == "TAPE_OK", "armed BUSY abort failed")
        unmounts = call_named(calls, "tape_unmount")
        req(len(unmounts) == 1 and unmounts[0].get("result") == "TAPE_OK", "armed BUSY abort did not disarm for unmount")
        return err

    if not case.expect_commit_io:
        req(not _writes(events) and not any(e.get("op") == "flush" for e in events), "empty commit/tail probe performed write or flush")
        req(post.encode() == pre.encode(), "empty commit changed media bytes")
        req(cartridge_sequence(post) == 700, "empty commit advanced sequence")
        commits = call_named(calls, "tape_commit")
        req(len(commits) == 1 and commits[0].get("result") == "TAPE_OK", "empty commit was not TAPE_OK")
        probe = min(case.seek, case.expected_total - 1) if case.expected_total else 0
        tail_seek = [c for c in calls if c.get("fn") == "tape_seek" and c.get("phase") == "tail-seek"]
        tail_rate = [c for c in calls if c.get("fn") == "tape_set_rate" and c.get("phase") == "tail-rate"]
        tail_service = [c for c in calls if c.get("fn") == "tape_service" and c.get("phase") == "tail-service"]
        tail_render = [c for c in calls if c.get("fn") == "tape_render" and c.get("phase") == "tail-render"]
        req(len(tail_seek) == 1 and tail_seek[0].get("result") == "TAPE_OK" and tail_seek[0].get("frame") == probe,
            "empty commit tail seek missing")
        req(bool(tail_rate) and tail_rate[0].get("result") == "TAPE_OK" and tail_rate[0].get("rate_q16_16") == 65536,
            "empty commit tail rate missing")
        req(bool(tail_service) and all(x.get("result") == "TAPE_OK" for x in tail_service) and tail_service[-1].get("more_work") is False,
            "empty commit tail service did not complete")
        req(len(tail_render) == 1 and tail_render[0].get("result") == "TAPE_OK"
            and tail_render[0].get("requested") == 1 and tail_render[0].get("rendered") == 1
            and "events_from_call" in tail_render[0] and tail_render[0].get("events_from_call") == 0,
            "empty commit tail did not render one frame without block I/O")
        req(not any(e.get("phase") == "tail-render" for e in events), "tape_render issued block I/O")
        unmounts = call_named(calls, "tape_unmount")
        remounts = [c for c in mounts[1:] if c.get("phase") == "remount"]
        req(len(unmounts) == 1 and unmounts[0].get("result") == "TAPE_OK", "empty commit unmount failed")
        req(len(remounts) == 1 and remounts[0].get("result") == "TAPE_OK" and remounts[0].get("side") == "B", "empty commit remount failed")
        return err

    feeds = call_named(calls, "tape_feed")
    req(len(feeds) == 1 and feeds[0].get("requested") == case.feed and feeds[0].get("accepted") == case.feed
        and feeds[0].get("result") == "TAPE_OK", "feed request/accepted-count mismatch")
    req(len(feeds) == 1 and "events_from_call" in feeds[0] and feeds[0].get("events_from_call") == 0,
        "tape_feed callback count missing or nonzero")
    req(not any(e.get("phase") == "feed" for e in events), "tape_feed issued raw block I/O")
    services = call_named(calls, "tape_service")
    req(bool(services) and all(x.get("result") == "TAPE_OK" for x in services) and services[-1].get("more_work") is False,
        "tape_service did not run to completion")
    commits = call_named(calls, "tape_commit")
    req(len(commits) == 1 and commits[0].get("result") == "TAPE_OK", "non-empty commit was not TAPE_OK")

    req(post.slots[2] == pre.slots[2], "record changed live-B source slot instead of inactive B1")
    req(structural_sequence(post.slots[3]) == 701, "record commit did not consume all-slot max + 1")
    req(semantic_valid(post.slots[3], 1, select_sb(post)), "record B1 result invalid")
    req(parse_entries(post.slots[3]) == case.expected_entries, "record index shape mismatch")
    req(struct.unpack_from("<Q", post.slots[3], 20)[0] == case.expected_total, "record total_frames mismatch")
    req(live_slot(post, 1) == 3, "record commit not live")
    req(free_next(post) == 4, "post-record free_next not advanced to 4")

    lo, hi = _chunk_bounds(pre, 3)
    svc = _writes(events, "service")
    req(bool(svc), "record service produced no audio write observation")
    for e in svc:
        req(e["lba"] >= lo and e["lba"] + e["count"] <= hi, "record audio write outside derived allocation chunk")

    commit_events = [(i, e) for i, e in enumerate(events) if e.get("phase") == "commit"]
    commit_writes = [(i, e) for i, e in commit_events if e.get("op") == "write"]
    flush_pos = [i for i, e in commit_events if e.get("op") == "flush"]
    req(len(flush_pos) == 2, "non-empty commit did not perform exactly two flushes")
    for _, e in commit_writes:
        req(e.get("lba", -1) >= LBA_B1 and e.get("lba", -1) + e.get("count", 0) <= LBA_B1 + SLOT_BYTES // BLOCK,
            "commit wrote outside inactive B1 slot")
    ent_pos = [i for i, e in commit_writes if touches(e, LBA_B1 + 1) and not touches(e, LBA_B1)]
    hdr_pos = [i for i, e in commit_writes if e.get("lba") == LBA_B1 and e.get("count") == 1]
    req(bool(ent_pos) and len(hdr_pos) == 1, "record commit missing entry/header writes")
    if len(flush_pos) == 2 and ent_pos and len(hdr_pos) == 1:
        req(max(ent_pos) < flush_pos[0] < hdr_pos[0] < flush_pos[1],
            "record commit order is not entries -> flush -> header -> flush")
        req(all(i < flush_pos[1] for i, _ in commit_writes), "record commit wrote after final flush")

    ss = [structural_sequence(x) for x in post.slots]
    ss = [x for x in ss if x is not None]
    req(len(ss) == len(set(ss)), "post-record structurally valid slots share sequence")

    unmounts = call_named(calls, "tape_unmount")
    remounts = [c for c in mounts[1:] if c.get("phase") == "remount"]
    req(len(unmounts) == 1 and unmounts[0].get("result") == "TAPE_OK", "record unmount failed")
    req(len(remounts) == 1 and remounts[0].get("result") == "TAPE_OK" and remounts[0].get("side") == "B", "record remount failed")
    return err

def synth_calls(case: Case) -> list[dict]:
    calls = [
        {"phase": "mount", "fn": "tape_mount", "result": "TAPE_OK", "side": "B"},
        {"phase": "seek", "fn": "tape_seek", "result": "TAPE_OK", "frame": case.seek},
        {"phase": "arm", "fn": "tape_arm", "result": "TAPE_OK", "mode": MODES[case.id]},
    ]
    if case.id == "WP09-ARMED-BUSY":
        calls.extend(
            [
                {"phase": "armed", "fn": "tape_seek", "result": "TAPE_ERR_BUSY", "frame": 0},
                {"phase": "armed", "fn": "tape_set_rate", "result": "TAPE_ERR_BUSY", "rate_q16_16": 65536},
                {"phase": "abort", "fn": "tape_abort", "result": "TAPE_OK"},
                {"phase": "unmount", "fn": "tape_unmount", "result": "TAPE_OK"},
            ]
        )
        return calls
    if case.feed:
        calls.append(
            {
                "phase": "feed",
                "fn": "tape_feed",
                "result": "TAPE_OK",
                "requested": case.feed,
                "accepted": case.feed,
                "events_from_call": 0,
            }
        )
        calls.append({"phase": "service", "fn": "tape_service", "result": "TAPE_OK", "more_work": False})
    calls.append({"phase": "commit", "fn": "tape_commit", "result": "TAPE_OK"})
    if not case.expect_commit_io:
        probe = min(case.seek, case.expected_total - 1) if case.expected_total else 0
        calls.extend(
            [
                {"phase": "tail-seek", "fn": "tape_seek", "result": "TAPE_OK", "frame": probe},
                {"phase": "tail-rate", "fn": "tape_set_rate", "result": "TAPE_OK", "rate_q16_16": 65536},
                {"phase": "tail-service", "fn": "tape_service", "result": "TAPE_OK", "more_work": False},
                {"phase": "tail-render", "fn": "tape_render", "result": "TAPE_OK", "requested": 1, "rendered": 1, "events_from_call": 0},
                {"phase": "tail-stop", "fn": "tape_set_rate", "result": "TAPE_OK", "rate_q16_16": 0},
            ]
        )
    calls.append({"phase": "unmount", "fn": "tape_unmount", "result": "TAPE_OK"})
    calls.append({"phase": "remount", "fn": "tape_mount", "result": "TAPE_OK", "side": "B"})
    return calls

def synth_post(case: Case):
    p = case.pre
    if not case.expect_commit_io:
        return p, []
    slots = list(p.slots)
    slots[3] = idx(1, case.expected_entries, 701)
    post = Media(p.blocks, p.primary, p.mirror, tuple(slots))
    lo, _ = _chunk_bounds(p, 3)
    ev = [
        {"phase": "service", "op": "write", "lba": lo, "count": 1},
        {"phase": "service", "op": "flush"},
        {"phase": "commit", "op": "write", "lba": LBA_B1 + 1, "count": 1},
        {"phase": "commit", "op": "flush"},
        {"phase": "commit", "op": "write", "lba": LBA_B1, "count": 1},
        {"phase": "commit", "op": "flush"},
    ]
    return post, ev


def synth_observation(case: Case):
    post, events = synth_post(case)
    return post, events, synth_calls(case)
