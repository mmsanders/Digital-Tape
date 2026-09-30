#!/usr/bin/env python3
"""Per-case outcomes and red controls on the Product evidence. NOT canonical.

replay.py stops at the first failing case. This script runs the package's own
oracle.check on every case of the retained stream and prints the census of
outcomes per row; then, on passing Product observations, requires oracle.check
to reject single-fact mutations of them. Exit status 1 if any case fails or any
control survives.
"""
from __future__ import annotations

import argparse
import collections
import copy
import gzip
import json
from pathlib import Path
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "wp10_backlog_r54"))
import oracle as O  # noqa: E402


def outcome(case, obs):
    try:
        O.check(case, obs)
        return None
    except (AssertionError, KeyError, TypeError, ValueError, IndexError) as e:
        return str(e) or type(e).__name__


def _resealed(hexblock, edit):
    b = bytearray(bytes.fromhex(hexblock))
    edit(b)
    struct.pack_into("<I", b, 508, zlib.crc32(bytes(b[:508])) & 0xFFFFFFFF)
    return bytes(b).hex()


# row 1: phase-4 repair crash
def row1_repair_trace_changed(o):
    o["repair_trace_sha256"] = "0" * 64


def row1_repair_writes_candidate(o):
    ev = o["rw_A"]["repair_events"][0]
    ev["lba"] = 0 if ev["lba"] else 6144


def row1_read_only_not_flagged(o):
    o["ro_A"]["info"]["needs_repair"] = False


def row1_repair_not_finished(o):
    o["durable_after_rw_sha256"] = o["durable_sha256"]


# row 2: dup re-run on the same destination
def row2_rerun_incomplete(o):
    o["rerun"]["call"]["more_work"] = True


def row2_rerun_other_chunk(o):
    o["rerun"]["dst_chunk_lbas"] = sorted(o["rerun"]["dst_chunk_lbas"] + [2048 + 1024])


def row2_rerun_other_media(o):
    o["rerun"]["durable_sha256"] = o["durable_sha256"]


def row2_side_b_invalid(o):
    o["rw_B"]["info"]["side_b_valid"] = False


# row 3: completed copy shape
def row3_label_not_copied(o):
    for k in ("P", "M"):
        o["raw_after"][k] = _resealed(o["raw_after"][k], lambda b: b.__setitem__(slice(88, 120), bytes(32)))


def row3_high_water_floor(o):
    for k in ("P", "M"):
        o["raw_after"][k] = _resealed(o["raw_after"][k],
                                      lambda b: struct.pack_into("<I", b, 56, struct.unpack_from("<I", b, 56)[0] - 1))


def row3_b0_written_side_a(o):
    h = bytearray(bytes.fromhex(o["raw_after"]["B0h"]))
    h[12] = 0
    o["raw_after"]["B0h"] = bytes(h).hex()


def row3_other_audio(o):
    o["mount_A"]["pcm_sha256"] = "0" * 64


CONTROLS = {1: [row1_repair_trace_changed, row1_repair_writes_candidate, row1_read_only_not_flagged,
                row1_repair_not_finished],
            2: [row2_rerun_incomplete, row2_rerun_other_chunk, row2_rerun_other_media, row2_side_b_invalid],
            3: [row3_label_not_copied, row3_high_water_floor, row3_b0_written_side_a, row3_other_audio]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("observations", type=Path, help="observations.jsonl.gz")
    a = ap.parse_args()
    census: collections.Counter = collections.Counter()
    reasons: collections.Counter = collections.Counter()
    pick = {}
    with gzip.open(a.observations, "rt", encoding="utf-8") as f:
        for case, line in zip(O.iter_cases(), f):
            obs = json.loads(line)
            why = outcome(case, obs)
            census[(f"row{case['row']}", "PASS" if why is None else "FAIL")] += 1
            if why is not None:
                reasons[(case["row"], why[:120])] += 1
                continue
            # Row 1: the first repair-writing case. Row 2: the first case whose
            # re-run starts on WRITE_IN_PROGRESS media (its call writes the chunk).
            # Row 3: the last case (CHUNK-PLUS-ONE, a_high_water 2).
            if case["row"] == 1 and 1 not in pick and obs["rw_A"]["repair_events"]:
                pick[1] = (case, obs)
            elif case["row"] == 2 and 2 not in pick and obs["rerun"]["dst_chunk_lbas"] \
                    and obs["durable_sha256"] != obs["rerun"]["durable_sha256"]:
                pick[2] = (case, obs)
            elif case["row"] == 3:
                pick[3] = (case, obs)
    for k, v in sorted(census.items()):
        print(f"{k[0]:<5} {k[1]} {v}")
    for (row, why), v in sorted(reasons.items()):
        print(f"  row{row}: {v} x {why}")

    survived, total = [], 0
    for row, fns in CONTROLS.items():
        case, obs = pick[row]
        for fn in fns:
            total += 1
            m = copy.deepcopy(obs)
            fn(m)
            why = outcome(case, m)
            print(("killed   " if why else "SURVIVED ") + f"row{row} case {case['index']}/{fn.__name__}: {why}")
            if why is None:
                survived.append(fn.__name__)
    print(f"{total - len(survived)}/{total} Product-evidence controls killed")
    return 1 if survived or reasons else 0


if __name__ == "__main__":
    raise SystemExit(main())
