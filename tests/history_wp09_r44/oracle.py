"""Seeded 10,000-edit record history, derived only from DRAFT-9 public semantics."""
from __future__ import annotations

import hashlib
import json
import struct
import zlib

SEED = 0x9E3779B9
EDITS = 10000
INTERVAL = 400
CHUNK_FRAMES = 131072
SLOT_LBAS = (264, 392)


def need(ok, why):
    if not ok:
        raise AssertionError(why)


def rng(seed):
    while True:
        seed ^= seed << 13 & 0xFFFFFFFF
        seed ^= seed >> 17
        seed ^= seed << 5 & 0xFFFFFFFF
        seed &= 0xFFFFFFFF
        yield seed


def clamp(n):
    return max(-32768, min(32767, n))


def pcm(frames):
    return b"".join(struct.pack("<hh", *f) for f in frames)


def edits():
    rand = rng(SEED)
    length = 0
    for i in range(EDITS):
        mode = ("overwrite", "overdub", "splice")[i % 3]
        r = next(rand)
        at = (0 if i % 17 == 0 else length if i % 19 == 0 else r % (length + 1))
        count = 1 + (next(rand) % 7)
        frames = []
        for j in range(count):
            x = next(rand)
            # Full-scale sentinels repeatedly exercise saturating overdub.
            frames.append(((32767 if i % 23 == 0 else -32768 if i % 29 == 0 else (x & 65535) - 32768),
                           -32768 if i % 31 == 0 else 32767 if i % 37 == 0 else ((x >> 16) & 65535) - 32768))
        yield {"id": i + 1, "mode": mode, "at": at, "frames": frames}
        if mode == "overwrite":
            length = at + count
        elif mode == "splice":
            length += count
        else:
            length = max(length, at + count)


def apply(timeline, edit):
    at, inp, mode = edit["at"], edit["frames"], edit["mode"]
    need(at <= len(timeline), "plan seek beyond timeline")
    if mode == "overwrite":
        return timeline[:at] + inp
    if mode == "splice":
        return timeline[:at] + inp + timeline[at:]
    out = list(timeline)
    for j, f in enumerate(inp):
        p = at + j
        if p < len(out):
            a = out[p]
            out[p] = (clamp(a[0] + f[0]), clamp(a[1] + f[1]))
        else:
            out.append(f)
    return out


def parse_index(raw, total_chunks=None):
    need(set(raw) == {"header", "entries"}, "raw index fields")
    h = bytes.fromhex(raw["header"])
    need(len(h) == 512 and h[:8] == b"TAPEIDX\x01", "index header")
    count = struct.unpack_from("<I", h, 16)[0]
    need(count <= 4096, "index count")
    ent = bytes.fromhex(raw["entries"])
    need(len(ent) == count * 12, "index entry bytes")
    need(zlib.crc32(h[:60] + ent) == struct.unpack_from("<I", h, 60)[0], "index CRC")
    runs = [struct.unpack_from("<III", ent, i * 12) for i in range(count)]
    intervals = []
    for first, start, frames in runs:
        need(frames > 0 and start < CHUNK_FRAMES, "index run bound")
        if total_chunks is not None:
            need(first + (start + frames - 1) // CHUNK_FRAMES < total_chunks, "index chunk bound")
        intervals.append((first * CHUNK_FRAMES + start, first * CHUNK_FRAMES + start + frames))
    intervals.sort()
    need(all(a[1] <= b[0] for a, b in zip(intervals, intervals[1:])), "index interval overlap")
    total = struct.unpack_from("<Q", h, 20)[0]
    need(total == sum(x[2] for x in runs), "index total mismatch")
    return h[12], struct.unpack_from("<I", h, 8)[0], total, runs


def parse_superblock(raw):
    b = bytes.fromhex(raw)
    need(len(b) == 512 and b[:8] == b"TAPEFS\0\x01", "raw superblock")
    need(zlib.crc32(b[:508]) == struct.unpack_from("<I", b, 508)[0], "superblock CRC")
    return struct.unpack_from("<I", b, 52)[0], struct.unpack_from("<I", b, 56)[0]


def live_b(raw_slots, total_chunks):
    need(set(raw_slots) == {"B0", "B1"}, "both raw B slots required")
    valid = []
    for name in ("B0", "B1"):
        try:
            parsed = parse_index(raw_slots[name], total_chunks)
        except (AssertionError, ValueError):
            continue
        if parsed[0] == 1:
            valid.append((name, parsed))
    need(bool(valid), "no selectable B slot")
    if len(valid) == 2:
        need(valid[0][1][1] != valid[1][1][1], "equal-sequence B slots")
    return max(valid, key=lambda item: item[1][1])


def plan_digest():
    h = hashlib.sha256()
    for edit in edits():
        h.update(json.dumps(edit, separators=(",", ":")).encode() + b"\n")
    return h.hexdigest()


def check(records):
    timeline = []
    seq = None
    checkpoint_count = 0
    census = {m: 0 for m in ("overwrite", "overdub", "splice")}
    for expected in edits():
        try:
            obs = next(records)
        except StopIteration:
            raise AssertionError("silent early restart / fewer than 10,000 edits")
        i, mode, at, frames = expected["id"], expected["mode"], expected["at"], expected["frames"]
        need(obs.get("schema") == "wp09-r44-v1" and obs.get("id") == i, "edit id continuity")
        need(obs.get("mode") == mode and obs.get("at") == at, "edit schedule drift")
        need(obs.get("input_sha256") == hashlib.sha256(pcm(frames)).hexdigest(), "input mismatch")
        need(obs.get("accepted") == len(frames), "short acceptance: no positive branch assumed")
        calls = obs.get("calls")
        need(calls == {"seek": "TAPE_OK", "arm": "TAPE_OK", "feed": "TAPE_OK",
                       "service": "TAPE_OK", "commit": "TAPE_OK"}, "call result / silent restart")
        events = obs.get("events")
        need(isinstance(events, list), "missing public block trace")
        commit = [e for e in events if e.get("step") == "commit"]
        cw = [e for e in commit if e.get("op") == "write"]
        cf = [e for e in commit if e.get("op") == "flush"]
        need(1 <= len(cw) <= 97 and len(cf) == 2, "commit budget/flush count")
        need(cw[-1].get("lba") in SLOT_LBAS, "index header not last write")
        need(cf[-1].get("ordinal", -1) > cw[-1].get("ordinal", 0), "commit final flush order")
        need(all(e.get("lba", 0) < 2048 for e in cw), "chunk write during commit")
        need(any(e.get("step") == "service" and e.get("op") == "flush" for e in events),
             "accepted chunks not durable before commit")
        timeline = apply(timeline, expected)
        census[mode] += 1
        if i % INTERVAL == 0:
            checkpoint_count += 1
            cp = obs.get("checkpoint")
            need(isinstance(cp, dict) and cp.get("id") == i, "missing checkpoint")
            need(cp.get("after_remount") is (i % (2 * INTERVAL) == 0), "remount schedule")
            need(cp.get("render_pcm") == pcm(timeline).hex(), "stale/wrong rendered PCM")
            need(cp.get("render_block_events") == [], "render performed block I/O")
            chunks, high = parse_superblock(cp["raw_superblock"])
            selected, (side, observed_seq, total, runs) = live_b(cp["raw_slots"], chunks)
            need(side == 1 and total == len(timeline), "raw live B index/timeline mismatch")
            public = cp.get("public_info")
            need(isinstance(public, dict) and public.get("total_frames") == total and
                 public.get("entry_count") == len(runs), "public info disagrees with selected raw B")
            if seq is not None:
                need(observed_seq == seq + INTERVAL, "commit sequence gap/restart")
            seq = observed_seq
            next_from_raw = max([high] + [a + (s + n - 1) // CHUNK_FRAMES + 1 for a, s, n in runs])
            need(public.get("total_chunks") == chunks and 0 <= public.get("free_chunks", -1) <= chunks - next_from_raw,
                 "public free space exceeds raw live index bound")
            if cp["after_remount"]:
                need(public["free_chunks"] == chunks - next_from_raw, "remount did not rederive free_next")
                reads = cp.get("mount_events")
                need(isinstance(reads, list) and {264, 392} <=
                     {e.get("lba") for e in reads if e.get("op") == "read"},
                     "remount lacks both raw B-slot reads")
            else:
                need(cp.get("mount_events") == [], "unexpected remount trace")
            need(cp.get("pcm_sha256") == hashlib.sha256(pcm(timeline)).hexdigest(), "checkpoint digest")
        else:
            need("checkpoint" not in obs, "unexpected checkpoint")
    try:
        next(records)
    except StopIteration:
        pass
    else:
        raise AssertionError("extra edit evidence")
    need(checkpoint_count == 25 and sum(census.values()) == EDITS, "census")
    return {"edits": EDITS, "checkpoints": checkpoint_count, "modes": census,
            "plan_sha256": plan_digest(), "final_pcm_sha256": hashlib.sha256(pcm(timeline)).hexdigest()}
