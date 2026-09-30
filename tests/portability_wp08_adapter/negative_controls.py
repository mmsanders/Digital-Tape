#!/usr/bin/env python3
"""Diagnostics and red controls on the Product streams. NOT canonical.

The canonical verdict is oracle.parse_jsonl over the byte-identical stream
(run_product.py). That verdict is FAIL on every vector for one reason: the
oracle's "setup trace" requires tape_mount and tape_service to make zero
device callbacks, which a device-backed engine cannot do (see README).

To show what the rest of the oracle concludes about this Product stream, this
script also runs oracle.check on a copy whose four setup-call callback lists are
blanked. Nothing else is touched, and that relaxed result is labelled as such:
it is information for Verification, never a substitute verdict. It then
requires the relaxed check to reject single-fact mutations, and requires a
one-byte cross-toolchain divergence to be detected.
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


def relaxed(o):
    m = copy.deepcopy(o)
    for t in m["trace"][:4]:
        t["block_events"] = []
    return m


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


CONTROLS = [("flip_pcm", flip_pcm, None), ("tell_drift", tell_drift, None),
            ("start_flag", start_flag, None), ("short_render", short_render, None),
            ("render_io", render_io, None), ("golden_land_and_stop", land_and_stop, GOLDEN)]


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
    print(f"canonical oracle.check: {canon.count(None)}/{len(plan)} pass; failure reasons: {reasons}")

    calls_with_io = {}
    for o in records:
        for t in o["trace"]:
            if t.get("block_events"):
                calls_with_io[t["fn"]] = calls_with_io.get(t["fn"], 0) + 1
    print(f"calls that made device callbacks (vectors): {calls_with_io}")

    rel = [outcome(v, relaxed(o)) for v, o in zip(plan, records)]
    for v, why in zip(plan, rel):
        if why:
            print(f"  relaxed FAIL {v.id}: {why}")
    print(f"relaxed (setup callback lists blanked, NOT canonical): {rel.count(None)}/{len(plan)} pass")

    survived = []
    target = records[9] if records[9]["case"] == GOLDEN else next(o for o in records if o["case"] == GOLDEN)
    for name, fn, only in CONTROLS:
        o = relaxed(target if only else records[13])
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
    return 1 if survived or gcc != clang else 0


if __name__ == "__main__":
    raise SystemExit(main())
