"""Blind DRAFT-9 WP-06e/f closure oracle over public calls and raw media."""
from __future__ import annotations

import hashlib
import json
import struct
import zlib
from pathlib import Path

BLOCK = 512
SLOT_BYTES = 65536
CHUNK_FRAMES = 131072
CHUNK_BASE = 2048
SLOT_LBA = {"A0": 8, "A1": 136, "B0": 264, "B1": 392}
ROOT = Path(__file__).resolve().parent


def require(value, message):
    if not value:
        raise AssertionError(message)


def load_plan():
    return json.loads((ROOT / "gap_plan.json").read_text())


def plan_sha256():
    return hashlib.sha256((ROOT / "gap_plan.json").read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def raw(value, size):
    require(isinstance(value, str) and len(value) == size * 2, f"raw{size} missing")
    return bytes.fromhex(value)


def parse_sb(value):
    b = raw(value, BLOCK)
    require(b[:8] == b"TAPEFS\0\x01", "superblock magic")
    require(zlib.crc32(b[:508]) == struct.unpack_from("<I", b, 508)[0], "superblock crc")
    return {"raw": b, "generation": struct.unpack_from("<I", b, 12)[0],
            "chunks": struct.unpack_from("<I", b, 52)[0],
            "high": struct.unpack_from("<I", b, 56)[0],
            "stage": struct.unpack_from("<I", b, 124)[0],
            "staging": struct.unpack_from("<I", b, 128)[0]}


def parse_slot(value):
    b = raw(value, SLOT_BYTES)
    if b[:8] != b"TAPEIDX\x01":
        return None
    count = struct.unpack_from("<I", b, 16)[0]
    require(count <= 4096, "entry_count")
    entries = b[BLOCK:BLOCK + count * 12]
    require(zlib.crc32(b[:60] + entries) == struct.unpack_from("<I", b, 60)[0], "index crc")
    return {"raw": b[:BLOCK] + entries, "sequence": struct.unpack_from("<I", b, 8)[0],
            "side": b[12], "total": struct.unpack_from("<Q", b, 20)[0],
            "runs": [struct.unpack_from("<III", entries, 12*i) for i in range(count)]}


def media(snapshot):
    require(set(snapshot) == {"primary", "mirror", *SLOT_LBA}, "snapshot keys")
    out = {"primary": parse_sb(snapshot["primary"]), "mirror": parse_sb(snapshot["mirror"])}
    out.update({k: parse_slot(snapshot[k]) for k in SLOT_LBA})
    return out


def select_slot(m, side):
    names = (side + "0", side + "1")
    valid = [(name, m[name]) for name in names if m[name] is not None]
    if not valid:
        return None
    if len(valid) == 2 and valid[0][1]["sequence"] == valid[1][1]["sequence"]:
        return None
    return max(valid, key=lambda item: item[1]["sequence"])


def high_water(slot):
    return max((first + (start + count - 1)//CHUNK_FRAMES + 1
                for first, start, count in slot["runs"]), default=0)


def calls(obs, fn=None, step=None):
    return [c for c in obs["calls"] if (fn is None or c["fn"] == fn) and
            (step is None or c["step"] == step)]


def need_call(obs, step, fn, result):
    found = calls(obs, fn, step)
    require(len(found) == 1 and found[0]["result"] == result, f"{step} {fn} {result}")
    return found[0]


def writes(obs, step=None):
    return [e for e in obs["events"] if e["op"] == "write" and
            (step is None or e["step"] == step)]


def stage_cleared_before_mutation(obs, step):
    ev = [e for e in obs["events"] if e["step"] == step and e["op"] in ("write", "flush")]
    first_mut = next((i for i, e in enumerate(ev) if e["op"] == "write" and
                      e.get("lba") not in (0, obs["block_count"]-1)), None)
    require(first_mut is not None, "no index/chunk write")
    prefix = ev[:first_mut]
    require([e["lba"] for e in prefix if e["op"] == "write"] ==
            [obs["block_count"]-1, 0], "stage clear not partner-first/candidate-last")
    require(sum(e["op"] == "flush" for e in prefix) == 2, "stage-clear flushes")


def stage_clear_only(obs, step):
    ev = [e for e in obs["events"] if e["step"] == step and e["op"] in ("write", "flush")]
    require([(e["op"], e.get("lba")) for e in ev] ==
            [("write", obs["block_count"]-1), ("flush", None),
             ("write", 0), ("flush", None)], "stage-clear sequence")


def check(case, obs):
    require(obs.get("schema") == "wp06-r52-observation-v1", "schema")
    require(obs.get("case") == case["id"], "case id")
    require(isinstance(obs.get("block_count"), int) and obs["block_count"] > CHUNK_BASE, "geometry")
    require(all(set(c) >= {"step", "fn", "result"} for c in obs.get("calls", [])), "calls")
    require(all(set(e) >= {"step", "op", "ordinal"} for e in obs.get("events", [])), "events")
    require([e["ordinal"] for e in obs["events"]] == list(range(1, len(obs["events"])+1)), "ordinals")
    snaps = {k: media(v) for k, v in obs.get("snapshots", {}).items()}
    before = snaps["before"]
    sb = before["primary"]
    require(before["mirror"]["raw"] == sb["raw"], "fixture superblock pair")

    cid = case["id"]
    if cid.startswith("E-"):
        require(sb["stage"] == 1, "stage fixture")
    if cid == "E-SIDEA-REFUSE":
        require(need_call(obs, "mount", "tape_mount", "TAPE_OK").get("side") == "A", "not mounted A")
        need_call(obs, "exercise", "tape_arm", "TAPE_ERR_READ_ONLY")
        require(not writes(obs), "refusal wrote")
        require(obs["snapshots"]["after"] == obs["snapshots"]["before"], "refusal changed media")
    elif cid == "E-RESPOOL-FULL":
        require(need_call(obs, "mount", "tape_mount", "TAPE_OK").get("side") == "B", "not mounted B")
        need_call(obs, "exercise", "tape_respool", "TAPE_ERR_CARTRIDGE_FULL")
        require(not writes(obs, "exercise"), "full refusal wrote")
        require(obs["snapshots"]["after"] == obs["snapshots"]["before"], "full refusal changed media")
    elif cid == "E-RECORD-PROMOTE":
        for step, fn in (("mount","tape_mount"),("arm","tape_arm"),("record","tape_feed"),
                         ("record","tape_service"),("commit","tape_commit"),
                         ("promote","tape_promote"),("remount","tape_mount")):
            need_call(obs, step, fn, "TAPE_OK")
        require(calls(obs, "tape_mount", "mount")[0].get("side") == "B", "not mounted B")
        require(calls(obs, "tape_feed", "record")[0].get("accepted", 0) > 0, "no accepted frames")
        stage_clear_only(obs, "arm")
        first_media_write_after_clear = min(e["ordinal"] for e in obs["events"]
                                            if e["op"] == "write" and e.get("lba") not in (0, obs["block_count"]-1))
        require(first_media_write_after_clear > max(e["ordinal"] for e in obs["events"] if e["step"] == "arm"),
                "record/index write preceded stage clear")
        require(snaps["after_arm"]["primary"]["stage"] == 0, "arm did not clear stage")
        require(snaps["after_promote"]["primary"]["stage"] == 0, "promote left stage")
        a = select_slot(snaps["after_promote"], "A")[1]
        b = select_slot(snaps["after_promote"], "B")[1]
        require(a["runs"] == b["runs"], "promote incomplete")
    elif cid.startswith("F-STAGE-DEGRADED-"):
        require(sb["stage"] == 1 and select_slot(before, "B") is None, "not stage+degraded")
        if cid.endswith("DIVERGENT"):
            require(before["B0"] and before["B1"] and
                    before["B0"]["sequence"] == before["B1"]["sequence"] and
                    before["B0"]["raw"] != before["B1"]["raw"], "not equal-divergent")
        require(need_call(obs, "mount", "tape_mount", "TAPE_OK").get("side") == "A", "not mounted A")
        info0 = need_call(obs, "mount", "tape_get_info", "TAPE_OK")
        require(info0.get("side_b_valid") is False, "not publicly degraded")
        need_call(obs, "reset", "tape_reset_side_b", "TAPE_OK")
        stage_cleared_before_mutation(obs, "reset")
        need_call(obs, "remount", "tape_mount", "TAPE_OK")
        info1 = need_call(obs, "remount", "tape_get_info", "TAPE_OK")
        require(info1.get("side_b_valid") is True, "reset not live")
        need_call(obs, "switch", "tape_set_side", "TAPE_OK")
        after = snaps["after_reset"]
        require(after["primary"]["stage"] == 0 and select_slot(after, "B") is not None, "recovery media")
        remounted_b = select_slot(snaps["after_remount"], "B")
        require(remounted_b is not None, "remount has no live B")
        require(remounted_b[1]["raw"] == select_slot(after, "B")[1]["raw"], "remount selected another B")
    else:
        check_floor_row(case, obs, before, sb)

SLOT_HEADERS = {lba: name for name, lba in SLOT_LBA.items()}


def slot_from_bytes(b):
    if b[:8] != b"TAPEIDX":
        return None
    count = struct.unpack_from("<I", b, 16)[0]
    if count > 4096:
        return None
    entries = b[BLOCK:BLOCK + count * 12]
    if zlib.crc32(b[:60] + entries) != struct.unpack_from("<I", b, 60)[0]:
        return None
    return {"raw": b[:BLOCK] + entries, "sequence": struct.unpack_from("<I", b, 8)[0], "side": b[12],
            "runs": [struct.unpack_from("<III", entries, 12 * i) for i in range(count)]}


def run_chunks(slot):
    out = set()
    for first, start, count in (slot["runs"] if slot else []):
        out.update(range(first, first + (start + count - 1) // CHUNK_FRAMES + 1))
    return out


def live_set(slots):
    live = set()
    for side in ("A", "B"):
        chosen = select_slot(slots, side)
        if chosen:
            live |= run_chunks(chosen[1])
    return live


def write_chunks(e):
    first = (e["lba"] - CHUNK_BASE) // 1024
    last = (e["lba"] + e.get("count", 1) - 1 - CHUNK_BASE) // 1024
    return set(range(first, last + 1))


def check_floor_row(case, obs, before, sb):
    """WP-06f live-B floor, per PM ruling on #108 (tapefs §9.3.1-§9.3.2, §9.4; invariant 10)."""
    cid = case["id"]
    live_b = select_slot(before, "B")
    require(live_b is not None and high_water(live_b[1]) > sb["high"], "fixture lacks recorded B")
    floor = high_water(live_b[1])
    # §9.4 lets pass 1 land on any run >= a_high_water disjoint from the live set; "allocates above"
    # the live-B frontier is then forced only when live B occupies every chunk in [a_high_water, floor).
    require(set(range(sb["high"], floor)) <= run_chunks(live_b[1]),
            "fixture: live B must densely occupy [a_high_water, floor) so the floor is spec-forced")
    total = sum(r[2] for r in live_b[1]["runs"])
    length = -(-total // CHUNK_FRAMES)
    require(need_call(obs, "mount", "tape_mount", "TAPE_OK").get("side") == "A", "not mounted A")
    promote = "PROMOTE" in cid
    if promote:
        require(not (len(live_b[1]["runs"]) == 1 and live_b[1]["runs"][0][1] == 0),
                "fixture must take the allocating (non-adopt) phase-1 path")
    need_call(obs, "exercise", "tape_promote" if promote else "tape_respool", "TAPE_OK")

    slots = {name: bytearray(bytes.fromhex(obs["snapshots"]["before"][name])) for name in SLOT_LBA}
    parsed = {name: slot_from_bytes(bytes(b)) for name, b in slots.items()}
    events = [e for e in obs["events"] if e["step"] == "exercise" and e["op"] == "write"]
    commits, chunk_log, sb_writes = [], [], []
    for e in events:
        lba = e["lba"]
        if lba >= CHUNK_BASE and lba != obs["block_count"] - 1:
            touched = write_chunks(e)
            require(not (touched & live_set(parsed)),
                    f"write to chunks {sorted(touched)} intersects the then-live set (invariant 10)")
            chunk_log.append((len(commits), len(sb_writes), touched))
            continue
        if lba in (0, obs["block_count"] - 1):
            sb_writes.append((len(commits), lba))
            continue
        name = next((n for n, base in SLOT_LBA.items() if base <= lba < base + SLOT_BYTES // BLOCK), None)
        require(name is not None, f"write at LBA {lba} outside superblocks, index slots and chunks")
        data = raw(e.get("data"), BLOCK)
        off = (lba - SLOT_LBA[name]) * BLOCK
        slots[name][off:off + BLOCK] = data
        parsed[name] = slot_from_bytes(bytes(slots[name]))
        if lba in SLOT_HEADERS:
            require(parsed[name] is not None, f"index header write to {name} is not a valid commit")
            commits.append(name[0])

    require(commits, "operation committed no index")
    phase1 = [c for n, _, c in chunk_log if n == 0]
    require(phase1, "no phase-1/pass-1 allocation before the first index commit")
    p1 = set().union(*phase1)
    require(min(p1) >= floor, f"phase-1/pass-1 allocation at chunk {min(p1)} below live-B floor {floor}")
    require(p1 == set(range(min(p1), min(p1) + length)), "phase-1/pass-1 destination is not one run of len")
    later = [(n, k, c) for n, k, c in chunk_log if n > 0]
    if promote:
        require(commits[:2] == ["A", "B"], "phase 1 must commit A then B before phase 2")
        require(later, "promote performed no phase 2")
        require(all(n >= 2 and k >= 2 for n, k, _ in later),
                "phase-2 write before phase-1 A/B commits and step-4 superblock")
        p2 = set().union(*(c for _, _, c in later))
        require(p2 == set(range(length)), f"phase-2 destination {sorted(p2)} is not [0, {length})")
    else:
        require(all(ch >= sb["high"] for _, _, c in later for ch in c), "pass-2 write below a_high_water")
        if later:
            p2 = set().union(*(c for _, _, c in later))
            require(p2 == set(range(min(p2), min(p2) + length)) and min(p2) < min(p1),
                    "pass-2 destination is not a strictly lower run of len")


def check_all(observations):
    plan = load_plan()["cases"]
    by_id = {o.get("case"): o for o in observations}
    require(len(by_id) == len(observations), "duplicate cases")
    require(set(by_id) == {c["id"] for c in plan}, "missing/extra cases")
    for case in plan:
        check(case, by_id[case["id"]])
    return len(plan)
