#!/usr/bin/env python3
"""Per-row census and red controls on the Product evidence. NOT canonical.

Runs the package's own oracle.check on every case of the Product stream and
prints the per-row outcome census, then requires oracle.check to reject
single-fact mutations of this Product's own passing observations, a few per
row. Exit status: 1 if any case fails or any control survives.
"""
from __future__ import annotations

import argparse
import collections
import copy
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "strengthen_r55"))
import oracle as O  # noqa: E402

C69 = O.C69


def outcome(case, obs):
    try:
        O.check(case, obs)
        return None
    except (AssertionError, KeyError, TypeError, ValueError, IndexError) as e:
        return str(e) or type(e).__name__


# row 1: the copy carries every audio block
def row1_block_not_copied(o):
    o["copy_raw_sha256"] = "0" * 64


def row1_side_a_wrong_audio(o):
    o["mount_A"]["pcm_sha256"] = "0" * 64


def row1_side_b_extra_entry(o):
    o["mount_B"]["info"]["entry_count"] = 2


# row 2: pass 2 runs, lands lower, never onto the then-live set
def _b_commits(o):
    return [i for i, e in enumerate(o["events"]) if e.get("op") == "write" and e["lba"] in (C69.LBA_B0, C69.LBA_B1)]


def row2_pass2_declines(o):
    o["events"] = o["events"][:_b_commits(o)[0] + 1]


def row2_pass2_onto_live(o):
    first = _b_commits(o)[0]
    pass1 = min((e["lba"] for e in o["events"][:first]
                 if e.get("op") == "write" and C69.LBA_CHUNK_BASE <= e["lba"] < C69.LBA_MIRROR))
    for e in o["events"][first + 1:]:
        if e.get("op") == "write" and C69.LBA_CHUNK_BASE <= e["lba"] < C69.LBA_MIRROR:
            e["lba"] = pass1
            return


def row2_remount_wrong_audio(o):
    o["mount_B_after"]["pcm_sha256"] = "0" * 64


# row 3: the A-slot premise, read from raw media
def _reseal(o):
    o["fixture_sha256"] = hashlib.sha256(O.canonical(o["raw_before"]).encode()).hexdigest()


def row3_a0_at_sequence_3(o):
    h = bytearray(bytes.fromhex(o["raw_before"]["A0"]["header"]))
    h[8:12] = (3).to_bytes(4, "little")
    struct.pack_into("<I", h, 60, zlib.crc32(bytes(h[:60])))
    o["raw_before"]["A0"]["header"] = bytes(h).hex()
    _reseal(o)


def row3_a1_valid(o):
    h = bytearray(bytes.fromhex(o["raw_before"]["A0"]["header"]))
    h[8:12] = (2).to_bytes(4, "little")
    struct.pack_into("<I", h, 60, zlib.crc32(bytes(h[:60])))
    o["raw_before"]["A1"] = {"header": bytes(h).hex(), "entries": ""}
    _reseal(o)


def row3_a_slots_missing(o):
    del o["raw_before"]["A0"], o["raw_before"]["A1"]
    _reseal(o)


CONTROLS = {
    1: [row1_block_not_copied, row1_side_a_wrong_audio, row1_side_b_extra_entry],
    2: [row2_pass2_declines, row2_pass2_onto_live, row2_remount_wrong_audio],
    3: [row3_a0_at_sequence_3, row3_a1_valid, row3_a_slots_missing],
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("observations", type=Path, help="observations.jsonl.gz")
    a = ap.parse_args()
    census: collections.Counter = collections.Counter()
    reasons: collections.Counter = collections.Counter()
    first = {}
    failing = 0
    with gzip.open(a.observations, "rt", encoding="utf-8") as f:
        for case, line in zip(O.iter_cases(), f):
            obs = json.loads(line)
            why = outcome(case, obs)
            census[(case["row"], "PASS" if why is None else "FAIL")] += 1
            if why is not None:
                failing += 1
                reasons[(case["row"], why[:120])] += 1
            elif case["row"] not in first:
                first[case["row"]] = (case, obs)
    for k, v in sorted(census.items()):
        print(f"row{k[0]} {k[1]} {v}")
    for (row, why), v in sorted(reasons.items()):
        print(f"  row{row}: {v} x {why}")
    print(f"failing cases: {failing}")

    survived, total = [], 0
    for row, fns in CONTROLS.items():
        if row not in first:
            print(f"no passing row-{row} case to mutate")
            survived.append(f"row{row}")
            continue
        case, obs = first[row]
        for fn in fns:
            total += 1
            m = copy.deepcopy(obs)
            fn(m)
            why = outcome(case, m)
            print(("killed   " if why else "SURVIVED ") + f"case {case['index']}/{fn.__name__}: {why}")
            if why is None:
                survived.append(fn.__name__)
    print(f"{total - len(survived)}/{total} Product-evidence controls killed")
    return 1 if survived or failing else 0


if __name__ == "__main__":
    raise SystemExit(main())
