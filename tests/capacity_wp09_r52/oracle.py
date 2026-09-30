#!/usr/bin/env python3
"""Independent DRAFT-9 WP-09 positive capacity-short-accept oracle.

Authored from the public DRAFT-9 bundle only.  Product implementation details
and adapter-provided verdict labels are deliberately outside this module.
"""
from __future__ import annotations

import base64
import hashlib
import json
import struct
import zlib
from dataclasses import asdict, dataclass

BLOCK = 512
CHUNK_FRAMES = 131072
BLOCKS_PER_CHUNK = 1024
LBA_B0, LBA_B1, LBA_CHUNK_BASE = 264, 392, 2048
SEED_FRAMES = 12
A_HIGH_WATER = 2
INITIAL_FREE_NEXT = 3
INITIAL_SEQUENCE = 3

SPEC_HASHES = {
    "spec/tapefs-v1.md": "3f08ec6d11070c1e10edcf7cacbcd93ff694257f042b71b53200e158621fa19d",
    "spec/engine-api.md": "383817326705d98bda6a96480f8185e911113927d35c53c02d1458adb72baea6",
    "spec/acceptance.md": "ae77d13c868fd39a882b5bd3ebf459557792432ce895bc7bf58be7fc2c33825d",
}

MODES = ("overwrite", "overdub", "splice")
POSITIONS = (("start", 0), ("middle", 6), ("end", 12))
SHAPES = (
    ("one-free-one-left", 4, 1, 64, 1),
    ("two-free-seventeen-left", 5, 17, 64, 17),
    ("three-free-4095-left", 6, 4095, 4096, 64),
)


def require(ok, why):
    if not ok:
        raise AssertionError(why)


@dataclass(frozen=True)
class Case:
    id: str
    mode: str
    position: str
    at: int
    shape: str
    total_chunks: int
    final_accepted: int
    final_requested: int
    service_budget: int

    @property
    def free_chunks(self):
        return self.total_chunks - INITIAL_FREE_NEXT

    @property
    def capacity_frames(self):
        return self.free_chunks * CHUNK_FRAMES

    @property
    def prefill_frames(self):
        return self.capacity_frames - self.final_accepted


def cases():
    out = []
    for mode in MODES:
        for position, at in POSITIONS:
            for shape, chunks, accepted, requested, budget in SHAPES:
                out.append(Case(
                    f"capacity-{mode}-{position}-{shape}", mode, position, at,
                    shape, chunks, accepted, requested, budget,
                ))
    require(len(out) == 27 and len({c.id for c in out}) == 27, "case census")
    return out


def plan_digest():
    body = json.dumps([asdict(c) for c in cases()], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()


def prefill_requests(case):
    full, tail = divmod(case.prefill_frames, 4096)
    return [4096] * full + ([tail] if tail else [])


def seed_pcm():
    return [(100 + i, -200 - i) for i in range(SEED_FRAMES)]


def input_sample(case):
    mi = MODES.index(case.mode)
    pi = next(i for i, x in enumerate(POSITIONS) if x[0] == case.position)
    si = next(i for i, x in enumerate(SHAPES) if x[0] == case.shape)
    return 1000 + 100 * mi + 10 * pi + si, -1000 - 100 * mi - 10 * pi - si


def sat16(value):
    return min(32767, max(-32768, value))


def expected_pcm(case):
    seed = seed_pcm()
    sample = input_sample(case)
    incoming = [sample] * case.capacity_frames
    if case.mode == "overwrite":
        return seed[:case.at] + incoming
    if case.mode == "splice":
        return seed[:case.at] + incoming + seed[case.at:]
    overlap = min(len(seed) - case.at, len(incoming))
    mixed = [
        (sat16(seed[case.at + i][0] + sample[0]),
         sat16(seed[case.at + i][1] + sample[1]))
        for i in range(overlap)
    ]
    return seed[:case.at] + mixed + incoming[overlap:]


def encode_pcm(frames):
    raw = bytearray()
    for left, right in frames:
        raw += struct.pack("<hh", left, right)
    return base64.b64encode(zlib.compress(bytes(raw), 9)).decode()


def decode_pcm(value):
    require(isinstance(value, str), "missing exact rendered PCM")
    try:
        raw = zlib.decompress(base64.b64decode(value, validate=True))
    except (ValueError, zlib.error) as exc:
        raise AssertionError("invalid rendered PCM encoding") from exc
    require(len(raw) % 4 == 0, "rendered PCM byte length")
    return [struct.unpack_from("<hh", raw, i) for i in range(0, len(raw), 4)]


def expected_entries(case):
    new = (INITIAL_FREE_NEXT, 0, case.capacity_frames)
    prefix = (2, 0, case.at)
    suffix = (2, case.at, SEED_FRAMES - case.at)
    if case.mode in ("overwrite", "overdub"):
        return ([prefix] if case.at else []) + [new]
    return ([prefix] if case.at else []) + [new] + ([suffix] if case.at < SEED_FRAMES else [])


def parse_superblock(value):
    require(isinstance(value, str) and len(value) == 2 * BLOCK, "raw superblock")
    b = bytes.fromhex(value)
    require(b[:8] == b"TAPEFS\0\x01", "superblock magic")
    require(struct.unpack_from("<I", b, 508)[0] == zlib.crc32(b[:508]), "superblock crc")
    return {
        "raw": b,
        "generation": struct.unpack_from("<I", b, 12)[0],
        "uuid": b[20:36],
        "total_chunks": struct.unpack_from("<I", b, 52)[0],
        "high": struct.unpack_from("<I", b, 56)[0],
    }


def parse_slot(obj):
    require(isinstance(obj, dict) and set(obj) == {"header", "entries"}, "raw B slot shape")
    require(isinstance(obj["header"], str) and len(obj["header"]) == 2 * BLOCK, "raw B header")
    h = bytes.fromhex(obj["header"])
    if h[:8] != b"TAPEIDX\x01":
        require(obj["entries"] == "", "invalid slot carried entries")
        return None
    count = struct.unpack_from("<I", h, 16)[0]
    require(count <= 4096 and isinstance(obj["entries"], str), "entry count")
    e = bytes.fromhex(obj["entries"])
    require(len(e) == 12 * count, "raw entry byte count")
    require(struct.unpack_from("<I", h, 60)[0] == zlib.crc32(h[:60] + e), "index crc")
    entries = [struct.unpack_from("<III", e, 12 * i) for i in range(count)]
    require(struct.unpack_from("<Q", h, 20)[0] == sum(x[2] for x in entries), "index total")
    return {"raw_header": h, "raw_entries": e, "sequence": struct.unpack_from("<I", h, 8)[0],
            "side": h[12], "entries": entries}


def raw_state(obj):
    require(isinstance(obj, dict) and set(obj) == {"primary", "mirror", "B0", "B1"}, "raw state keys")
    primary, mirror = parse_superblock(obj["primary"]), parse_superblock(obj["mirror"])
    require(primary["raw"] == mirror["raw"], "superblock copies diverge")
    slots = {name: parse_slot(obj[name]) for name in ("B0", "B1")}
    valid = [(name, slot) for name, slot in slots.items() if slot is not None and slot["side"] == 1]
    require(valid, "no raw Side B index")
    if len(valid) == 2:
        require(valid[0][1]["sequence"] != valid[1][1]["sequence"], "ambiguous raw Side B index")
    live = max(valid, key=lambda item: item[1]["sequence"])
    return primary, slots, live


def derived_free_next(superblock, entries):
    out = superblock["high"]
    for first, start, count in entries:
        require(count > 0 and start < CHUNK_FRAMES, "invalid entry")
        last = first + (start + count - 1) // CHUNK_FRAMES
        require(last < superblock["total_chunks"], "entry outside cartridge")
        out = max(out, last + 1)
    return out


def events_for(obs, step):
    return [e for e in obs["events"] if e.get("step") == step]


def event_blocks(event):
    count = event.get("count")
    require(isinstance(count, int) and not isinstance(count, bool) and count > 0, "callback count")
    return count


def check(case, obs):
    require(obs.get("schema") == "wp09-capacity-r52-v1" and obs.get("case") == case.id, "schema/case")
    require(isinstance(obs.get("calls"), dict) and isinstance(obs.get("events"), list), "observation shape")
    require(all(isinstance(e.get("ordinal"), int) and set(e) >= {"step", "op", "ordinal", "rc"}
                for e in obs["events"]), "event shape")
    require([e["ordinal"] for e in obs["events"]] == list(range(1, len(obs["events"]) + 1)), "event ordinals")

    pre_sb, pre_slots, pre_live = raw_state(obs.get("raw_before"))
    post_sb, post_slots, post_live = raw_state(obs.get("raw_after"))
    require(pre_sb["raw"] == post_sb["raw"], "ordinary record changed superblock")
    require(pre_sb["high"] == A_HIGH_WATER and pre_sb["total_chunks"] == case.total_chunks, "fixture geometry")
    require(pre_live[0] == "B0" and pre_live[1]["sequence"] == INITIAL_SEQUENCE
            and pre_live[1]["entries"] == [(2, 0, SEED_FRAMES)], "seed index")
    require(derived_free_next(pre_sb, pre_live[1]["entries"]) == INITIAL_FREE_NEXT, "fixture free_next")
    require(post_live[0] == "B1" and post_live[1]["sequence"] == INITIAL_SEQUENCE + 1, "committed slot/sequence")
    require(post_live[1]["entries"] == expected_entries(case), "committed entry array")
    require(derived_free_next(post_sb, post_live[1]["entries"]) == case.total_chunks, "capacity not exhausted")
    require(pre_slots["B0"]["raw_header"] == post_slots["B0"]["raw_header"]
            and pre_slots["B0"]["raw_entries"] == post_slots["B0"]["raw_entries"], "old B generation changed")

    calls = obs["calls"]
    require(calls.get("mount", {}).get("result") == "TAPE_OK", "mount result")
    before_info = calls.get("info_before", {})
    require(before_info.get("result") == "TAPE_OK" and before_info.get("total_frames") == SEED_FRAMES
            and before_info.get("entry_count") == 1
            and before_info.get("total_chunks") == case.total_chunks
            and before_info.get("free_chunks") == case.free_chunks, "public info before")
    require(calls.get("seek", {}) == {"frame": case.at, "result": "TAPE_OK"}, "seek")
    require(calls.get("arm", {}) == {"mode": case.mode, "result": "TAPE_OK"}, "arm")

    steps = calls.get("feed_steps")
    requests = prefill_requests(case)
    require(isinstance(steps, list) and len(steps) == len(requests) + 1, "feed census")
    for i, requested in enumerate(requests):
        feed = steps[i]
        require(feed.get("requested") == requested and feed.get("accepted") == requested
                and feed.get("result") == "TAPE_OK" and feed.get("events_from_call") == 0,
                "prefill feed")
        require(not events_for(obs, feed.get("label", "")), "tape_feed performed I/O")
        service = feed.get("service")
        require(isinstance(service, list) and service and service[-1].get("more_work") is False,
                "prefill service completion")
    final = steps[-1]
    require(final.get("requested") == case.final_requested and final.get("accepted") == case.final_accepted
            and final.get("result") == "TAPE_ERR_CARTRIDGE_FULL" and final.get("accepted") > 0
            and final.get("accepted") < final.get("requested") and final.get("events_from_call") == 0,
            "positive capacity short accept")
    require(not events_for(obs, final.get("label", "")), "final tape_feed performed I/O")

    premature = calls.get("premature_commit", {})
    require(premature.get("result") == "TAPE_ERR_BUSY" and premature.get("events_from_call") == 0,
            "commit did not wait for owed frames")
    require(not events_for(obs, "premature-commit"), "premature commit I/O")
    final_service = final.get("service")
    require(isinstance(final_service, list) and final_service and final_service[-1].get("more_work") is False,
            "final accepted prefix not serviced")
    require(calls.get("status_after_service", {}).get("result") == "TAPE_OK"
            and calls["status_after_service"].get("frames_owed") is False, "frames still owed")

    service_calls = [svc for feed in steps for svc in feed.get("service", [])]
    require(service_calls and all(s.get("result") == "TAPE_OK" and s.get("budget") == case.service_budget
                                  for s in service_calls), "service result/budget")
    service_labels = {s.get("label") for s in service_calls}
    service_events = [e for e in obs["events"] if e.get("step") in service_labels]
    writes = [e for e in service_events if e["op"] == "write"]
    require(writes, "accepted frames were not durably written")
    touched = set()
    for e in writes:
        count = event_blocks(e)
        require(e.get("rc") == 0 and count <= case.service_budget, "service write budget")
        require(isinstance(e.get("lba"), int) and e["lba"] >= LBA_CHUNK_BASE, "illegal service allocation")
        first = (e["lba"] - LBA_CHUNK_BASE) // BLOCKS_PER_CHUNK
        last = (e["lba"] + count - 1 - LBA_CHUNK_BASE) // BLOCKS_PER_CHUNK
        require(first >= A_HIGH_WATER and last < case.total_chunks, "service allocation outside lawful range")
        touched.update(range(first, last + 1))
    require(touched == set(range(INITIAL_FREE_NEXT, case.total_chunks)), "service allocation census")
    flushes = [e for e in service_events if e["op"] == "flush" and e.get("rc") == 0]
    require(flushes and flushes[-1]["ordinal"] > writes[-1]["ordinal"], "accepted prefix not durably flushed")

    require(calls.get("commit", {}).get("result") == "TAPE_OK", "commit result")
    commit_events = events_for(obs, "commit")
    commit_writes = [e for e in commit_events if e["op"] == "write"]
    commit_flushes = [e for e in commit_events if e["op"] == "flush"]
    require(len(commit_writes) == 2 and len(commit_flushes) == 2, "commit write/flush count")
    require(commit_writes[0].get("lba") == LBA_B1 + 1 and event_blocks(commit_writes[0]) == 1,
            "entry array commit")
    require(commit_writes[1].get("lba") == LBA_B1 and event_blocks(commit_writes[1]) == 1,
            "header must commit last")
    require(commit_writes[0]["ordinal"] < commit_flushes[0]["ordinal"] < commit_writes[1]["ordinal"]
            < commit_flushes[1]["ordinal"] and commit_events[-1] is commit_flushes[-1], "commit durability order")
    require(all(e.get("rc") == 0 for e in commit_events), "commit callback failure")

    require(calls.get("unmount", {}).get("result") == "TAPE_OK"
            and calls.get("remount", {}).get("result") == "TAPE_OK", "fresh remount")
    remount_reads = {e.get("lba") for e in events_for(obs, "remount") if e["op"] == "read"}
    block_count = LBA_CHUNK_BASE + case.total_chunks * BLOCKS_PER_CHUNK + 1
    require({0, block_count - 1, LBA_B0, LBA_B1} <= remount_reads, "remount did not read raw candidates")
    after_info = calls.get("info_after", {})
    pcm = decode_pcm(calls.get("render", {}).get("pcm_zlib_b64"))
    expected = expected_pcm(case)
    require(after_info.get("result") == "TAPE_OK" and after_info.get("total_frames") == len(expected)
            and after_info.get("entry_count") == len(expected_entries(case))
            and after_info.get("total_chunks") == case.total_chunks and after_info.get("free_chunks") == 0,
            "public info after")
    render = calls.get("render", {})
    require(render.get("result") == "TAPE_OK" and render.get("rendered") == len(expected)
            and render.get("events_from_call") == 0 and pcm == expected, "exact remounted PCM")
    require(not events_for(obs, "render"), "render performed device I/O")

    claimed_fixture = obs.get("fixture_sha256")
    actual_fixture = hashlib.sha256(json.dumps(obs["raw_before"], sort_keys=True,
                                                separators=(",", ":")).encode()).hexdigest()
    require(claimed_fixture == actual_fixture, "fixture identity")
    return True
