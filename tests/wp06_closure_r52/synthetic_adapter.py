#!/usr/bin/env python3
"""Deterministic fake adapter used only to self-test the blind oracle."""
from __future__ import annotations

import copy
import json
import struct
import sys
import zlib

from oracle import BLOCK, CHUNK_BASE, SLOT_BYTES, load_plan

N = CHUNK_BASE + 64 * 1024 + 1


def superblock(stage=0, staging=0, high=2, chunks=64, generation=10):
    b = bytearray(BLOCK)
    b[:8] = b"TAPEFS\0\x01"
    struct.pack_into("<HHI", b, 8, 1, 0, generation)
    b[20:36] = bytes(range(16))
    struct.pack_into("<I", b, 52, chunks)
    struct.pack_into("<I", b, 56, high)
    struct.pack_into("<II", b, 124, stage, staging)
    struct.pack_into("<I", b, 508, zlib.crc32(b[:508]))
    return b.hex()


def slot(side, sequence, runs):
    b = bytearray(SLOT_BYTES)
    b[:8] = b"TAPEIDX\x01"
    struct.pack_into("<IB3xIQ", b, 8, sequence, side, len(runs), sum(x[2] for x in runs))
    entries = b"".join(struct.pack("<III", *x) for x in runs)
    struct.pack_into("<I", b, 60, zlib.crc32(b[:60] + entries))
    b[BLOCK:BLOCK+len(entries)] = entries
    return b.hex()


def blank():
    return bytes(SLOT_BYTES).hex()


def base(stage=0, high=2, b_runs=((4, 0, 131072),), divergent=False, absent=False):
    sb = superblock(stage=stage, staging=4 if stage else 0, high=high)
    m = {"primary": sb, "mirror": sb, "A0": slot(0, 20, [(0, 0, 131072)]),
         "A1": blank(), "B0": slot(1, 21, list(b_runs)), "B1": blank()}
    if absent:
        m["B0"] = blank()
    if divergent:
        m["B1"] = slot(1, 21, [(5, 0, 131072)])
    return m


def observation(case):
    cid = case["id"]
    o = {"schema":"wp06-r52-observation-v1", "case":cid, "block_count":N,
         "calls":[], "events":[], "snapshots":{}}
    def call(step, fn, result="TAPE_OK", **extra):
        o["calls"].append({"step":step, "fn":fn, "result":result, **extra})
    def event(step, op, **extra):
        o["events"].append({"step":step, "op":op, "ordinal":len(o["events"])+1, **extra})
    def clear(step):
        event(step, "write", lba=N-1); event(step, "flush")
        event(step, "write", lba=0); event(step, "flush")

    if cid == "F-STAGE-DEGRADED-ABSENT":
        m = base(stage=1, absent=True)
    elif cid == "F-STAGE-DEGRADED-DIVERGENT":
        m = base(stage=1, divergent=True)
    elif cid == "E-RESPOOL-FULL":
        m = base(stage=1, high=2, b_runs=((4, 0, 60*131072),))
    else:
        m = base(stage=1 if cid.startswith("E-") else 0)
    o["snapshots"]["before"] = copy.deepcopy(m)
    mount_side = "A" if cid == "E-SIDEA-REFUSE" or cid.startswith("F-") else "B"
    call("mount", "tape_mount", side=mount_side)

    if cid == "E-SIDEA-REFUSE":
        call("exercise", "tape_arm", "TAPE_ERR_READ_ONLY")
        o["snapshots"]["after"] = copy.deepcopy(m)
    elif cid == "E-RESPOOL-FULL":
        call("exercise", "tape_respool", "TAPE_ERR_CARTRIDGE_FULL", more_work=False)
        o["snapshots"]["after"] = copy.deepcopy(m)
    elif cid == "E-RECORD-PROMOTE":
        clear("arm")
        m["primary"] = m["mirror"] = superblock(stage=0, high=2, generation=11)
        call("arm", "tape_arm")
        o["snapshots"]["after_arm"] = copy.deepcopy(m)
        call("record", "tape_feed", accepted=10)
        event("record", "write", lba=CHUNK_BASE + 8*1024)
        call("record", "tape_service", more_work=False)
        event("commit", "write", lba=393); event("commit", "flush"); event("commit", "write", lba=392); event("commit", "flush")
        m["B1"] = slot(1, 22, [(4,0,131072),(8,0,10)])
        call("commit", "tape_commit")
        event("promote", "write", lba=CHUNK_BASE + 9*1024)
        m["A1"] = slot(0, 23, [(9,0,131082)]); m["B0"] = slot(1, 24, [(9,0,131082)])
        call("promote", "tape_promote", more_work=False)
        o["snapshots"]["after_promote"] = copy.deepcopy(m)
        call("remount", "tape_mount")
    elif cid.startswith("F-STAGE-DEGRADED-"):
        call("mount", "tape_get_info", side_b_valid=False)
        clear("reset")
        m["primary"] = m["mirror"] = superblock(stage=0, high=2, generation=11)
        event("reset", "write", lba=264); event("reset", "flush")
        m["B0"] = slot(1, 22, [(0,0,131072)])
        call("reset", "tape_reset_side_b")
        o["snapshots"]["after_reset"] = copy.deepcopy(m)
        call("remount", "tape_mount"); call("remount", "tape_get_info", side_b_valid=True)
        o["snapshots"]["after_remount"] = copy.deepcopy(m)
        call("switch", "tape_set_side")
    else:
        call("exercise", "tape_promote" if "PROMOTE" in cid else "tape_respool", more_work=False)
        event("exercise", "write", lba=CHUNK_BASE + 5*1024)
    return o


def all_observations():
    return [observation(c) for c in load_plan()["cases"]]


if __name__ == "__main__":
    for item in all_observations():
        print(json.dumps(item, sort_keys=True, separators=(",", ":")))
