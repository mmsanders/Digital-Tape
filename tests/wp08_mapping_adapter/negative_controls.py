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
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "wp08_mapping_r56"))
import oracle as O  # noqa: E402


def outcome(case, obs):
    try:
        O.check(case, obs)
        return None
    except (AssertionError, KeyError, TypeError, ValueError, IndexError) as e:
        return str(e) or type(e).__name__


def _first(o, fn):
    return next(c for c in o["calls"] if c["fn"] == fn)


def wrong_frame(o):
    r = _first(o, "tape_render")
    h = r["pcm_hex"]
    r["pcm_hex"] = h[:8] + ("0" if h[8] != "0" else "1") + h[9:]


def frames_swapped(o):
    r = _first(o, "tape_render")
    h = r["pcm_hex"]
    r["pcm_hex"] = h[8:16] + h[:8] + h[16:]


def tell_off_by_one(o):
    _first(o, "tape_tell")["frame"] += 1


def render_reads_device(o):
    _first(o, "tape_render")["events"] = [{"op": "read", "lba": 2048, "count": 1, "rc": 0}]


def service_writes(o):
    _first(o, "tape_service")["events"].append({"op": "write", "lba": 2048, "count": 1, "rc": 0})


def at_start_flag(o):
    s = [c for c in o["calls"] if c["fn"] == "tape_status"][-1]
    s["at_start"] = not s["at_start"]


CONTROLS = {
    1: [wrong_frame, frames_swapped, tell_off_by_one, render_reads_device, service_writes],
    2: [wrong_frame, at_start_flag, tell_off_by_one],
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
