#!/usr/bin/env python3
"""Synthetic protocol probes, including multi-block callback red controls."""
import copy
import struct
import zlib

from oracle import BLOCK, DEGRADED_CALLS, REFUSALS, SLOTS, cases, check, digest_plan

N = 25000


def superblock(generation=7, high=3, uuid=bytes(range(16))):
    b = bytearray(BLOCK)
    b[:8] = b"TAPEFS\0\x01"
    struct.pack_into("<HHI", b, 8, 1, 0, generation)
    b[20:36] = uuid
    struct.pack_into("<I", b, 52, 100)
    struct.pack_into("<I", b, 56, high)
    struct.pack_into("<I", b, 508, zlib.crc32(b[:508]))
    return b.hex()


def slot(side, seq, runs=()):
    h = bytearray(65536)
    h[:8] = b"TAPEIDX\x01"
    struct.pack_into("<IB3xIQ", h, 8, seq, side, len(runs), sum(x[2] for x in runs))
    e = b"".join(struct.pack("<III", *r) for r in runs)
    struct.pack_into("<I", h, 60, zlib.crc32(h[:60] + e))
    h[512:512 + len(e)] = e
    return h.hex()


def blank():
    return bytes(65536).hex()


def base():
    s = superblock()
    return {"primary": s, "mirror": s, "A0": slot(0, 10, [(0, 0, 17)]),
            "A1": blank(), "B0": slot(1, 20, [(1, 0, 31)]), "B1": blank()}


def observation(case):
    o = {"schema": "wp06-r44-v1", "case": case.id, "block_count": N,
         "calls": [], "events": [], "snapshots": {}}
    def c(step, fn, result="TAPE_OK", **extra):
        o["calls"].append({"step": step, "fn": fn, "result": result, **extra})
    def e(step, op, **extra):
        o["events"].append({"step": step, "op": op, "ordinal": len(o["events"]) + 1, **extra})
    if case.family == "repair":
        s = base()
        target = "primary" if "primary" in case.variant else "mirror"
        source = "mirror" if target == "primary" else "primary"
        if "invalid" in case.variant:
            s[target] = bytes(BLOCK).hex()
        else:
            s[target] = superblock(generation=6)
        o["snapshots"]["before"] = copy.deepcopy(s)
        for lba in (0, N - 1, *SLOTS.values()):
            e("mount", "read", lba=lba)
        e("mount", "write", lba=0 if target == "primary" else N - 1,
          result="error" if case.expected == "write" else "ok")
        if case.expected != "write":
            e("mount", "flush", result="error" if case.expected == "flush" else "ok")
        c("mount", "tape_mount")
        c("mount", "tape_get_info", needs_repair=case.expected != "success")
        if case.expected == "success":
            s[target] = s[source]
        o["snapshots"]["after_mount"] = copy.deepcopy(s)
        if case.expected != "success":
            e("retry", "write", lba=0 if target == "primary" else N - 1)
            e("retry", "flush")
            s[target] = s[source]
        c("retry", "tape_mount")
        c("retry", "tape_get_info", needs_repair=False)
        o["snapshots"]["after_retry"] = copy.deepcopy(s)
    elif case.family == "degraded":
        s = base()
        if case.variant == "invalid":
            s["B0"] = blank()
        else:
            s["B1"] = slot(1, 20, [(1, 1, 31)])
        o["snapshots"]["before"] = copy.deepcopy(s)
        if case.expected == "mount_B":
            c("probe", "tape_mount", "TAPE_ERR_INCONSISTENT")
            return o
        c("mount", "tape_mount")
        c("mount", "tape_get_info", side_b_valid=False, free_chunks=97)
        op = case.expected
        fn = {"set_side_A": "tape_set_side", "set_side_B": "tape_set_side",
              "status_info_tell": "tape_get_info", "dup_source": "tape_dup",
              "reset_b": "tape_reset_side_b"}.get(op, "tape_" + op)
        c("exercise", fn, REFUSALS.get(op, "TAPE_OK"))
        if op == "reset_b":
            seq = 11 if case.variant == "invalid" else 21
            s["B0"] = slot(1, seq, [(0, 0, 17)])
            o["snapshots"]["after_reset"] = copy.deepcopy(s)
            o["snapshots"]["after_remount"] = copy.deepcopy(s)
            c("remount", "tape_mount")
            c("remount", "tape_get_info", free_chunks=97)
            c("exercise", "tape_get_info", side_b_valid=True)
            c("switch", "tape_set_side")
    elif case.family == "roundtrip":
        s = base()
        s["A0"] = slot(0, 1)
        s["B0"] = slot(1, 2)
        o["snapshots"]["after_format"] = copy.deepcopy(s)
        c("format", "tape_format")
        c("mount1", "tape_mount")
        if case.variant != "empty-commit":
            runs = ([(i // 131072, i % 131072, 1) for i in range(4096)]
                    if case.variant == "max-entries" else
                    [(i // 131072, i % 131072, 1) for i in range(43)]
                    if case.variant == "entry-block-boundary" else
                    [(0, 0, 1 if case.variant == "one-frame" else 131073)])
            s["B1"] = slot(1, 3, runs)
            count = 97 if case.variant == "max-entries" else 3 if case.variant == "entry-block-boundary" else 2
            # Entry arrays are intentionally one multi-block device callback.
            e("commit", "write", lba=393, count=count - 1)
            e("commit", "flush")
            e("commit", "write", lba=392)
            e("commit", "flush")
            c("commit", "tape_commit")
        else:
            c("commit", "tape_commit")
        c("unmount", "tape_unmount")
        c("mount2", "tape_mount")
        c("mount2", "tape_get_info", uuid=bytes(range(16)).hex(),
          total_frames=sum(r[2] for r in runs) if case.variant != "empty-commit" else 0)
        o["snapshots"]["after_remount"] = copy.deepcopy(s)
    else:
        s = base()
        s["mirror"] = superblock(generation=6)
        o["snapshots"]["before"] = copy.deepcopy(s)
        o["snapshots"]["after_mount"] = copy.deepcopy(s)
        c("mount", "tape_mount", case.expected)
    return o


def run():
    plan = cases()
    for case in plan:
        check(case, observation(case))
    # Private adapter labels are deliberately immaterial to a valid observation.
    spoofed = observation(next(c for c in plan if c.id == "repair-stale-mirror-success"))
    spoofed["calls"][1].update(candidate="mirror", phase=1, free_next=0, selected_b="B1")
    check(next(c for c in plan if c.id == "repair-stale-mirror-success"), spoofed)
    def invalid_byte_and_spoof(o):
        o["snapshots"]["after_mount"]["A1"] = "01" + o["snapshots"]["after_mount"]["A1"][2:]
        o["calls"][0].update(candidate="primary", phase=4, selected_b="B0")
    by_id = {c.id: c for c in plan}
    def wrong_reset_function(o):
        call = next(c for c in o["calls"] if c["step"] == "exercise"
                    and c["fn"] == "tape_reset_side_b")
        call["fn"] = "tape_reset_b"
    def over_budget_multiblock(o):
        write = next(e for e in o["events"] if e["step"] == "commit" and e["op"] == "write")
        write["count"] += 1
    controls = [
        ("repair-invalid-primary-write", lambda o: o["events"].insert(0, {"step":"mount", "op":"write", "lba":0, "ordinal":0})),
        ("degraded-divergent-reset_b", lambda o: o["snapshots"]["after_remount"].update(B0=blank())),
        ("roundtrip-one-frame", lambda o: o["events"].pop()),
        ("roundtrip-max-entries", over_budget_multiblock),
        ("refusal-bad-A-with-partner", lambda o: o["events"].append({"step":"mount", "op":"write", "lba":0, "ordinal":1})),
        ("refusal-bad-stage-with-partner", lambda o: o["snapshots"]["after_mount"].update(primary=("00" + o["snapshots"]["after_mount"]["primary"][2:]))),
        ("refusal-bad-A-with-partner", invalid_byte_and_spoof),
        ("degraded-invalid-reset_b", wrong_reset_function),
    ]
    for key, mutate in controls:
        obs = observation(by_id[key])
        mutate(obs)
        try:
            check(by_id[key], obs)
        except AssertionError:
            pass
        else:
            raise AssertionError("red control survived: " + key)
    print("PASS", len(plan), "positive synthetic cases;", len(controls),
          "red controls killed; spoofed private labels ignored; plan", digest_plan())


if __name__ == "__main__":
    run()
