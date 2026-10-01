#!/usr/bin/env python3
"""Per-case outcomes and red controls on the Product evidence. NOT canonical.

replay.py stops at the first failing case. This script runs the package's own
oracle.check on every case of the retained stream, prints the census of
outcomes per row (and per campaign for row 2), and then, for passing cases,
requires oracle.check to reject single-fact mutations of this Product's own
observations. Exit status: 1 if any control survives or any case fails.
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
sys.path.insert(0, str(ROOT / "tests" / "wp10_backlog_r53"))
import oracle as O  # noqa: E402



def outcome(case, obs):
    try:
        O.check(case, obs)
        return None
    except (AssertionError, KeyError, TypeError, ValueError, IndexError) as e:
        return str(e) or type(e).__name__


# row 1
def row1_chunk_beyond_destination(o):
    o["dst_chunk_lbas"] = sorted(o["dst_chunk_lbas"] + [2048 + 4 * 1024])


def row1_layout_preserving(o):
    o["dst_chunk_lbas"] = sorted(o["dst_chunk_lbas"] + [2048 + 6 * 1024])


def row1_source_changed(o):
    o["source_sha256_after"] = "0" * 64


def row1_wrong_free_chunks(o):
    o["rw_B"]["info"]["free_chunks"] += 1


# row 2
def row2_frontier_off_by_one(o):
    o["remount"]["free_chunks"] -= 1


def row2_other_state(o):
    key = "post_metadata_sha256" if o["campaign"] == "C69" else "post_snapshot_sha256"
    o[key] = "0" * 64


def row2_chunk_store_changed(o):
    if o["campaign"] == "C69":
        chunk = sorted(o["post_chunk_sha256"])[0]
        o["post_chunk_sha256"][chunk] = "0" * 64
    else:
        o["post_snapshot_sha256"] = "1" * 64


# row 3
def row3_service_commits_index(o):
    o["crashes"][0]["meta_sha256"] = "0" * 64


def row3_wrong_remount(o):
    o["crashes"][-1]["remount"]["info"]["free_chunks"] -= 1


def row3_extra_service_write(o):
    ev = o["clean"]["events"]
    i = max(k for k, e in enumerate(ev) if e["op"] == "write")
    ev.insert(i + 1, dict(ev[i], lba=ev[i]["lba"] + 1))


CONTROLS = {1: [row1_chunk_beyond_destination, row1_layout_preserving, row1_source_changed, row1_wrong_free_chunks],
            2: [row2_frontier_off_by_one, row2_other_state, row2_chunk_store_changed],
            3: [row3_service_commits_index, row3_wrong_remount, row3_extra_service_write]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("observations", type=Path, help="observations.jsonl.gz")
    a = ap.parse_args()
    census: collections.Counter = collections.Counter()
    reasons: collections.Counter = collections.Counter()
    first_pass = {}
    outside = 0
    with gzip.open(a.observations, "rt", encoding="utf-8") as f:
        for case, line in zip(O.iter_cases(), f):
            obs = json.loads(line)
            why = outcome(case, obs)
            group = f"row{case['row']}" + (f"/{case['campaign']}" if case["row"] == 2 else "")
            census[(group, "PASS" if why is None else "FAIL")] += 1
            if why is not None:
                reasons[(group, why[:120])] += 1
                outside += 1
            elif case["row"] not in first_pass or (case["row"] == 1 and case["kind"] == "complete"):
                first_pass[case["row"]] = (case, obs)
    for k, v in sorted(census.items()):
        print(f"{k[0]:<10} {k[1]} {v}")
    for (g, why), v in sorted(reasons.items()):
        print(f"  {g}: {v} x {why}")
    print(f"failing cases: {outside}")

    survived, total = [], 0
    for row, fns in CONTROLS.items():
        case, obs = first_pass[row]
        for fn in fns:
            total += 1
            m = copy.deepcopy(obs)
            fn(m)
            why = outcome(case, m)
            print(("killed   " if why else "SURVIVED ") + f"row{row} case {case['index']}/{fn.__name__}: {why}")
            if why is None:
                survived.append(fn.__name__)
    print(f"{total - len(survived)}/{total} Product-evidence controls killed")
    return 1 if survived or outside else 0


if __name__ == "__main__":
    raise SystemExit(main())
