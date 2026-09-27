"""DRAFT-9 WP-06 sequential observations; no Product implementation dependency.

An adapter emits one JSON object per case.  Raw 512-byte blocks are hex strings;
parsed fields supplied by an adapter are deliberately ignored by this oracle.
"""
from __future__ import annotations

import hashlib
import json
import struct
import zlib
from dataclasses import dataclass

BLOCK = 512
CHUNK_FRAMES = 131072
SLOTS = {"A0": 8, "A1": 136, "B0": 264, "B1": 392}


def require(ok, why):
    if not ok:
        raise AssertionError(why)


def block(value):
    require(isinstance(value, str) and len(value) == 1024, "missing raw 512-byte block")
    return bytes.fromhex(value)


def sb(value):
    b = block(value)
    if b[:8] != b"TAPEFS\0\x01" or zlib.crc32(b[:508]) != struct.unpack_from("<I", b, 508)[0]:
        return None
    return {"raw": b, "generation": struct.unpack_from("<I", b, 12)[0],
            "state": b[16], "uuid": b[20:36], "high": struct.unpack_from("<I", b, 56)[0],
            "chunks": struct.unpack_from("<I", b, 52)[0],
            "stage": struct.unpack_from("<I", b, 124)[0]}


def index(image):
    require(isinstance(image, str) and len(image) == 65536 * 2, "missing full raw index slot")
    data = bytes.fromhex(image)
    h = data[:BLOCK]
    count = struct.unpack_from("<I", h, 16)[0]
    if count > 4096:
        return None
    e = data[BLOCK:BLOCK + count * 12]
    if h[:8] != b"TAPEIDX\x01" or count > 4096 or zlib.crc32(h[:60] + e) != struct.unpack_from("<I", h, 60)[0]:
        return None
    runs = [struct.unpack_from("<III", e, 12 * i) for i in range(count)]
    return {"sequence": struct.unpack_from("<I", h, 8)[0], "side": h[12],
            "total": struct.unpack_from("<Q", h, 20)[0], "runs": runs, "raw": h + e}


def media(snapshot):
    require(set(snapshot) == {"primary", "mirror", "A0", "A1", "B0", "B1"}, "snapshot keys")
    s = {k: sb(snapshot[k]) for k in ("primary", "mirror")}
    for k in SLOTS:
        s[k] = index(snapshot[k])
    return s


def raw_media(snapshot):
    """Compare every captured byte, including blocks that fail structural parsing."""
    require(set(snapshot) == {"primary", "mirror", *SLOTS}, "raw snapshot keys")
    return {k: bytes.fromhex(v) for k, v in snapshot.items()}


def select_sb(m):
    p, q = m["primary"], m["mirror"]
    if p is None:
        return "mirror" if q else None
    if q is None:
        return "primary"
    if p["generation"] == q["generation"]:
        require(p["raw"] == q["raw"], "equal-generation divergent superblocks")
        return "primary"
    return "primary" if p["generation"] > q["generation"] else "mirror"


def select_index(m, side):
    names = (side + "0", side + "1")
    candidate = m[select_sb(m)]
    def valid(k):
        s = m[k]
        if s is None or s["side"] != (0 if side == "A" else 1):
            return False
        runs = s["runs"]
        if s["total"] != sum(x[2] for x in runs) or s["total"] > 0xFFFFFFFF:
            return False
        intervals = []
        for first, start, count in runs:
            if count == 0 or start >= CHUNK_FRAMES:
                return False
            last = first + (start + count - 1) // CHUNK_FRAMES
            if last >= candidate["chunks"] or (side == "A" and last >= candidate["high"]):
                return False
            lo = first * CHUNK_FRAMES + start
            intervals.append((lo, lo + count))
        intervals.sort()
        return all(a[1] <= b[0] for a, b in zip(intervals, intervals[1:]))
    slots = [(k, m[k]) for k in names if valid(k)]
    if not slots:
        return None
    if len(slots) == 2:
        if slots[0][1]["sequence"] == slots[1][1]["sequence"]:
            return None
    return max(slots, key=lambda x: x[1]["sequence"])


def free_next(m):
    candidate = m[select_sb(m)]
    high = candidate["high"]
    live = select_index(m, "B")
    if live is None:
        return high
    return max([high] + [first + (start + count - 1) // CHUNK_FRAMES + 1
                         for first, start, count in live[1]["runs"]])


@dataclass(frozen=True)
class Case:
    id: str
    family: str
    variant: str
    expected: str


REPAIRS = (
    ("invalid-primary-write", "invalid-primary", "write"),
    ("invalid-primary-flush", "invalid-primary", "flush"),
    ("invalid-mirror-write", "invalid-mirror", "write"),
    ("invalid-mirror-flush", "invalid-mirror", "flush"),
    ("stale-primary-write", "stale-primary", "write"),
    ("stale-primary-flush", "stale-primary", "flush"),
    ("stale-mirror-write", "stale-mirror", "write"),
    ("stale-mirror-flush", "stale-mirror", "flush"),
    ("invalid-primary-success", "invalid-primary", "success"),
    ("stale-mirror-success", "stale-mirror", "success"),
)
DEGRADED_CALLS = (
    "seek", "set_rate", "render", "service", "status_info_tell", "arm", "feed",
    "commit", "abort", "set_side_A", "set_side_B", "reset_b", "promote",
    "respool", "dup_source", "unmount",
)
REFUSALS = {"arm": "TAPE_ERR_READ_ONLY", "feed": "TAPE_ERR_BUSY",
            "commit": "TAPE_ERR_BUSY", "abort": "TAPE_ERR_BUSY",
            "set_side_B": "TAPE_ERR_NO_VALID_INDEX", "promote": "TAPE_ERR_NO_VALID_INDEX",
            "respool": "TAPE_ERR_NO_VALID_INDEX"}


def cases():
    out = [Case("repair-" + n, "repair", shape, failure) for n, shape, failure in REPAIRS]
    # Fifteen matrix columns: set_side has two independently observable branches.
    out += [Case("degraded-invalid-" + op, "degraded", "invalid", op)
            for op in DEGRADED_CALLS]
    out += [Case("degraded-divergent-" + op, "degraded", "divergent", op)
            for op in ("mount_B", "reset_b", "set_side_B", "promote", "respool")]
    out += [Case("roundtrip-" + n, "roundtrip", n, "TAPE_OK") for n in
            ("one-frame", "chunk-boundary", "entry-block-boundary", "max-entries", "empty-commit")]
    out += [Case("refusal-" + n, "refusal", n, "TAPE_ERR_INCONSISTENT") for n in
            ("bad-A-with-partner", "bad-stage-with-partner")]
    require(len(out) == len({c.id for c in out}) and len(out) >= 25, "case inventory")
    return out


def events_for(obs, step):
    return [e for e in obs["events"] if e.get("step") == step]


def check(case, obs):
    require(obs.get("schema") == "wp06-r44-v1" and obs.get("case") == case.id, "schema/case")
    require(isinstance(obs.get("events"), list) and isinstance(obs.get("calls"), list), "missing raw trace")
    require(isinstance(obs.get("snapshots"), dict), "missing raw snapshots")
    snapshots = {k: media(v) for k, v in obs["snapshots"].items()}
    calls = obs["calls"]
    require(all(set(e) >= {"step", "op"} for e in obs["events"]), "event shape")
    require(all(set(c) >= {"step", "fn", "result"} for c in calls), "call shape")
    writes = lambda step: [e for e in events_for(obs, step) if e["op"] == "write"]
    flushes = lambda step: [e for e in events_for(obs, step) if e["op"] == "flush"]
    call = lambda step, fn: next((c for c in calls if c["step"] == step and c["fn"] == fn), None)
    need_call = lambda step, fn, result: require(call(step, fn) is not None and call(step, fn)["result"] == result,
                                         f"{step} {fn} result")

    if case.family == "repair":
        pre, post, retry = (snapshots[x] for x in ("before", "after_mount", "after_retry"))
        source = select_sb(pre)
        require(source is not None, "no candidate")
        target = "mirror" if source == "primary" else "primary"
        require(target in case.variant, "repair target mismatch")
        require(pre[source] is not None, "repair source invalid")
        if case.variant.startswith("invalid"):
            require(pre[target] is None, "partner not corrupt")
        else:
            require(pre[target] is not None and pre[target]["generation"] < pre[source]["generation"],
                    "partner not stale")
        need_call("mount", "tape_mount", "TAPE_OK")
        need_call("mount", "tape_get_info", "TAPE_OK")
        require(call("mount", "tape_get_info").get("needs_repair") == (case.expected != "success"), "repair indicator")
        require([e.get("lba") for e in writes("mount")] == [0 if target == "primary" else obs["block_count"] - 1],
                "repair outside phase 4 or wrong partner")
        mount_events = events_for(obs, "mount")
        first_write = mount_events.index(writes("mount")[0])
        prior_reads = {e.get("lba") for e in mount_events[:first_write] if e["op"] == "read"}
        require({0, obs["block_count"] - 1, *SLOTS.values()} <= prior_reads,
                "repair preceded both-side index validation reads")
        require(len(flushes("mount")) == (0 if case.expected == "write" else 1), "repair flush count")
        require(post[source]["raw"] == pre[source]["raw"], "candidate mutated by repair")
        need_call("retry", "tape_mount", "TAPE_OK")
        need_call("retry", "tape_get_info", "TAPE_OK")
        require(select_sb(retry) is not None, "retry lost candidate")
        require(retry["primary"]["raw"] == retry["mirror"]["raw"] == pre[source]["raw"], "retry did not converge")
        require(call("retry", "tape_get_info").get("needs_repair") is False, "retry repair indicator")
        require(all(e["op"] != "write" or e.get("lba") in (0, obs["block_count"] - 1)
                    for e in events_for(obs, "mount") + events_for(obs, "retry")), "repair wrote outside partner")
    elif case.family == "degraded":
        pre = snapshots["before"]
        require(select_index(pre, "A") is not None, "Side A must be live")
        if case.variant == "invalid":
            require(pre["B0"] is None and pre["B1"] is None, "B slots not invalid")
        else:
            require(pre["B0"] and pre["B1"] and pre["B0"]["sequence"] == pre["B1"]["sequence"]
                    and pre["B0"]["raw"] != pre["B1"]["raw"], "B not divergent")
        if case.expected == "mount_B":
            need_call("probe", "tape_mount", "TAPE_ERR_INCONSISTENT")
            require(not writes("probe"), "refused mount wrote")
        else:
            need_call("mount", "tape_mount", "TAPE_OK")
            need_call("mount", "tape_get_info", "TAPE_OK")
            info = call("mount", "tape_get_info")
            require(info.get("side_b_valid") is False and
                    info.get("free_chunks") == pre[select_sb(pre)]["chunks"] - free_next(pre),
                    "degraded public info/free-chunks")
            op = case.expected
            result = REFUSALS.get(op, "TAPE_OK")
            fn = {"set_side_A": "tape_set_side", "set_side_B": "tape_set_side",
                  "status_info_tell": "tape_get_info", "dup_source": "tape_dup"}.get(op, "tape_" + op)
            need_call("exercise", fn, result)
            if op in REFUSALS or op in ("set_side_A", "seek", "set_rate", "render", "status_info_tell"):
                require(not writes("exercise"), "read/refusal wrote")
            if op == "render":
                require(not events_for(obs, "exercise"), "render issued block callback")
            if op == "reset_b":
                after = snapshots["after_reset"]
                b0 = after["B0"]
                require(b0 is not None and b0["side"] == 1, "reset did not target B0")
                require(b0["runs"] == pre[select_index(pre, "A")[0]]["runs"], "reset did not copy A")
                base = max(x["sequence"] for x in (pre[k] for k in SLOTS) if x is not None)
                require(b0["sequence"] == base + 1, "reset sequence not global + 1")
                require(select_index(after, "B")[0] == "B0", "stale B won")
                need_call("remount", "tape_mount", "TAPE_OK")
                need_call("remount", "tape_get_info", "TAPE_OK")
                remount = snapshots["after_remount"]
                require(select_index(remount, "B")[0] == "B0", "stale B won on remount")
                need_call("switch", "tape_set_side", "TAPE_OK")
                need_call("exercise", "tape_get_info", "TAPE_OK")
                require(call("exercise", "tape_get_info").get("side_b_valid") is True,
                        "degraded state not cleared")
                require(call("remount", "tape_get_info").get("free_chunks") ==
                        remount[select_sb(remount)]["chunks"] - free_next(remount),
                        "remount free-chunks disagrees with raw live B")
    elif case.family == "roundtrip":
        for step, fn in (("format", "tape_format"), ("mount1", "tape_mount"),
                         ("commit", "tape_commit"), ("unmount", "tape_unmount"), ("mount2", "tape_mount")):
            need_call(step, fn, "TAPE_OK")
        need_call("mount2", "tape_get_info", "TAPE_OK")
        pre = snapshots["after_format"]
        post = snapshots["after_remount"]
        for k in ("primary", "mirror"):
            require(pre[k]["uuid"] == post[k]["uuid"], "identity changed")
        require(select_index(post, "A") is not None and select_index(post, "B") is not None,
                "roundtrip lost side")
        if case.variant == "empty-commit":
            require(not writes("commit") and not flushes("commit"), "empty commit I/O")
        else:
            cw, cf = writes("commit"), flushes("commit")
            require(len(cw) <= 97 and len(cf) == 2, "commit budget/final flush")
            require(cw and cw[-1].get("lba") in SLOTS.values(), "header must commit last")
            require(cf[-1].get("ordinal", -1) > cw[-1].get("ordinal", 0), "no final flush after header")
            require(all(e.get("lba") != 0 and e.get("lba") != obs["block_count"] - 1 for e in cw),
                    "commit wrote superblock")
            if case.variant == "max-entries":
                require(len(cw) == 97, "maximal commit not exercised")
            live = select_index(post, "B")
            expected_shape = {"one-frame": (1, 1, 2), "chunk-boundary": (1, 131073, 2),
                              "entry-block-boundary": (43, 43, 3), "max-entries": (4096, 4096, 97)}
            count, total, blocks = expected_shape[case.variant]
            require(len(live[1]["runs"]) == count and live[1]["total"] == total and len(cw) == blocks,
                    "boundary fixture/commit block count")
            require(live[1]["total"] == call("mount2", "tape_get_info").get("total_frames"), "timeline mismatch")
        require(call("mount2", "tape_get_info").get("uuid") == pre[select_sb(pre)]["uuid"].hex(), "info identity")
    else:
        need_call("mount", "tape_mount", case.expected)
        require(not writes("mount"), "refused mount wrote")
        require(raw_media(obs["snapshots"]["before"]) == raw_media(obs["snapshots"]["after_mount"]),
                "refused mount mutated raw media")
    return True


def digest_plan():
    return hashlib.sha256(json.dumps([c.__dict__ for c in cases()], sort_keys=True).encode()).hexdigest()
