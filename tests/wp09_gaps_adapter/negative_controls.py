#!/usr/bin/env python3
"""Per-row census and red controls on the Product evidence. NOT canonical.

Runs the package's own oracle.check on every case of the Product stream and
prints the per-row outcome census, then requires oracle.check to reject
single-fact mutations of this Product's own passing observations. Exit status:
1 if any case fails or any control survives.
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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "wp09_gaps_r56"))
import oracle as O  # noqa: E402


def outcome(case, obs):
    try:
        O.check(case, obs)
        return None
    except (AssertionError, KeyError, TypeError, ValueError, IndexError) as e:
        return str(e) or type(e).__name__


def _renders(o):
    return [c for c in o["calls"] if c["fn"] == "tape_render"]


# row 1: the remounted render must carry the clamp and the append
def wrapped_not_clamped(o):
    """Replace the first +32767 left sample with the wrap of the overflowing sum."""
    for r in _renders(o):
        pcm = bytearray(bytes.fromhex(r["pcm_hex"]))
        for k in range(0, len(pcm), 4):
            if struct.unpack_from("<h", pcm, k)[0] == 32767:
                struct.pack_into("<h", pcm, k, -32767)
                r["pcm_hex"] = pcm.hex()
                return


def last_frame_dropped(o):
    r = _renders(o)[-1]
    r["pcm_hex"] = r["pcm_hex"][:-8]
    r["rendered"] -= 1


def feed_short(o):
    next(c for c in o["calls"] if c["fn"] == "tape_feed")["accepted"] -= 1


# row 2: the #118 record's clean trace must meet the tapefs §8 floor
def _clean(o):
    return o["wp10_final_record"]["clean"]["events"]


def flush_dropped(o):
    ev = _clean(o)
    i = next(k for k, e in enumerate(ev) if e.get("op") == "flush")
    del ev[i]


def second_commit_dropped(o):
    ev = _clean(o)
    heads = [k for k, e in enumerate(ev) if e.get("op") == "write" and e["lba"] in (264, 392)]
    del ev[heads[-1]:]


CONTROLS = {
    1: [wrapped_not_clamped, last_frame_dropped, feed_short],
    2: [flush_dropped, second_commit_dropped],
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("observations", type=Path, help="observations.jsonl.gz")
    a = ap.parse_args()
    census: collections.Counter = collections.Counter()
    first, failing = {}, 0
    with gzip.open(a.observations, "rt", encoding="utf-8") as f:
        for case, line in zip(O.iter_cases(), f):
            obs = json.loads(line)
            why = outcome(case, obs)
            census[(case["row"], "PASS" if why is None else "FAIL")] += 1
            if why is not None:
                failing += 1
                print(f"  row{case['row']} case {case['index']}: {why[:160]}")
            elif case["row"] not in first:
                first[case["row"]] = (case, obs)
    for k, v in sorted(census.items()):
        print(f"row{k[0]} {k[1]} {v}")
    print(f"failing cases: {failing}")
    survived, total = [], 0
    for row, fns in CONTROLS.items():
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
