#!/usr/bin/env python3
"""Per-vector outcomes and red controls on the Product streams. NOT canonical.

The canonical verdict is oracle.parse_jsonl over the byte-identical stream
(run_product.py). This script prints oracle.check's outcome per vector, then
requires the oracle to reject single-fact mutations of this Product's own
records (including the R53 mount/service read rules), and requires a one-byte
cross-toolchain divergence to be detected.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "portability_wp08_r52"))
import oracle  # noqa: E402
from vectors import vectors  # noqa: E402

GOLDEN = "reverse-end-acceptance-0-1000-2000"


def outcome(v, o):
    try:
        oracle.check(v, o)
        return None
    except (AssertionError, KeyError, TypeError, IndexError) as e:
        return str(e)


def flip_pcm(o):
    h = o["pcm_hex"]
    o["pcm_hex"] = ("1" if h[0] == "0" else "0") + h[1:]


def tell_drift(o):
    o["tell"] += 1
    o["trace"][5]["value"] += 1


def start_flag(o):
    o["at_start"] = not o["at_start"]
    o["trace"][6]["at_start"] = o["at_start"]


def short_render(o):
    o["rendered"] -= 1
    o["trace"][4]["rendered"] -= 1
    o["pcm_hex"] = o["pcm_hex"][:-8]


def render_io(o):
    o["trace"][4]["block_events"] = [{"op": "read", "lba": 2048, "count": 1, "rc": 0}]


def land_and_stop(o):                     # the d5772c8 defect: frame 0 never emitted
    short_render(o)
    o["at_start"] = True


def mount_writes(o):                      # R53: playback setup never writes
    o["trace"][0]["block_events"].append({"op": "write", "lba": 0, "count": 1, "rc": 0})


def service_flushes(o):
    o["trace"][3]["block_events"].append({"op": "flush", "rc": 0})


def mount_skips_mirror(o):                # tapefs §4.1 phase 1 reads both superblocks
    last = o["block_count"] - 1
    o["trace"][0]["block_events"] = [e for e in o["trace"][0]["block_events"]
                                     if not e["lba"] <= last < e["lba"] + e["count"]]


def service_reads_outside(o):
    o["trace"][3]["block_events"].append({"op": "read", "lba": o["block_count"], "count": 1, "rc": 0})


def seek_reads(o):                        # seek/set_rate/render stay callback-free
    o["trace"][1]["block_events"] = [{"op": "read", "lba": 0, "count": 1, "rc": 0}]


def block_count_not_addressable(o):
    o["block_count"] = 2048


CONTROLS = [("flip_pcm", flip_pcm, None), ("tell_drift", tell_drift, None),
            ("start_flag", start_flag, None), ("short_render", short_render, None),
            ("render_io", render_io, None), ("golden_land_and_stop", land_and_stop, GOLDEN),
            ("mount_writes", mount_writes, None), ("service_flushes", service_flushes, None),
            ("mount_skips_mirror", mount_skips_mirror, None),
            ("service_reads_outside", service_reads_outside, None),
            ("seek_reads", seek_reads, None),
            ("block_count_not_addressable", block_count_not_addressable, None)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("evidence", type=Path, help="directory holding gcc.jsonl.gz and clang.jsonl.gz")
    a = ap.parse_args()
    gcc = gzip.decompress((a.evidence / "gcc.jsonl.gz").read_bytes())
    clang = gzip.decompress((a.evidence / "clang.jsonl.gz").read_bytes())
    records = [json.loads(line) for line in gcc.splitlines()]
    plan = vectors()
    by_id = {v.id: v for v in plan}

    canon = [outcome(v, o) for v, o in zip(plan, records)]
    reasons = sorted({c for c in canon if c})
    print(f"oracle.check per vector: {canon.count(None)}/{len(plan)} pass; failure reasons: {reasons}")

    calls_with_io = {}
    for o in records:
        for t in o["trace"]:
            if t.get("block_events"):
                calls_with_io[t["fn"]] = calls_with_io.get(t["fn"], 0) + 1
    print(f"calls that made device callbacks (vectors): {calls_with_io}")

    survived = []
    target = records[9] if records[9]["case"] == GOLDEN else next(o for o in records if o["case"] == GOLDEN)
    for name, fn, only in CONTROLS:
        o = copy.deepcopy(target if only else records[13])
        fn(o)
        why = outcome(by_id[o["case"]], o)
        print(("killed   " if why else "SURVIVED ") + f"{name}: {why}")
        if not why:
            survived.append(name)
    bad = bytearray(clang)
    bad[len(bad) // 2] ^= 1
    divergent = bytes(bad) != gcc
    print(("killed   " if divergent else "SURVIVED ") + "cross_toolchain_byte: one flipped Clang byte is detected")
    if not divergent:
        survived.append("cross_toolchain_byte")
    print(f"GCC/Clang retained streams byte-identical: {gcc == clang}")
    print(f"{len(CONTROLS) + 1 - len(survived)}/{len(CONTROLS) + 1} controls killed")
    return 1 if survived or gcc != clang or reasons else 0


if __name__ == "__main__":
    raise SystemExit(main())
