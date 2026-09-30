#!/usr/bin/env python3
"""Per-case outcomes and red controls on the Product evidence. NOT canonical.

1. Runs the package's oracle.check on every retained case (replay.py stops at
   the first failure) and prints each outcome.
2. For every passing case, requires oracle.check to reject each causal
   mutation of its Product observation, including (R53) a fault_call_index
   that does not name the failing continuation.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "wp12_closure_r53"))
import oracle  # noqa: E402


def outcome(case, obs, plan):
    try:
        oracle.check(case, obs, plan)
        return None
    except (AssertionError, KeyError, TypeError, ValueError, IndexError) as e:
        return str(e) or type(e).__name__


def drop_last_frame(o):                   # render identity after re-spool
    ph = o["post_same_session"]
    ph["pcm_bytes"] -= 4
    ph["renders"][-1]["rendered"] -= 1


def render_io(o):                         # renders never touch the device
    o["post_remount"]["renders"][0]["block_events"] = [{"op": "read", "lba": 2048, "count": 1, "rc": 0}]


def pcm_differs(o):
    o["pre"]["pcm_sha256"] = "0" * 64


def arm_after_fault(o):                   # V5-001: arm must be refused FAULTED
    o["probe"][0]["calls"][0]["result"] = "TAPE_OK"


def service_touches_media(o):             # Faulted row: service does no I/O
    cell = next(p for p in o["probe"] if p["column"] == "service")
    cell["block_events"] = [{"op": "read", "lba": 264, "count": 1, "rc": 0}]


def fault_index_mislabelled(o):           # R53: fault_call_index names the failing continuation
    o["fault_call_index"] -= 1


CONTROLS = {
    "RENDER-TWOPASS": [pcm_differs],
    "RENDER-DECLINE": [drop_last_frame],
    "RENDER-FRAGMENTED": [render_io],
    "F-RESPOOL-WRITE": [service_touches_media, fault_index_mislabelled],
    "F-RESPOOL-HEADER-FLUSH": [arm_after_fault, fault_index_mislabelled],
    "F-PROMOTE-WRITE": [service_touches_media, fault_index_mislabelled],
    "F-PROMOTE-FLUSH": [arm_after_fault, fault_index_mislabelled],
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("observations", type=Path, help="observations.jsonl.gz")
    a = ap.parse_args()
    raw = gzip.decompress(a.observations.read_bytes())
    by_id = {o["case"]: o for o in map(json.loads, raw.decode().splitlines())}
    plan = oracle.load_plan()

    passing = []
    for case in plan["cases"]:
        why = outcome(case, copy.deepcopy(by_id[case["id"]]), plan)
        print(f"{'PASS' if why is None else 'FAIL'}  {case['id']}" + ("" if why is None else f": {why}"))
        if why is None:
            passing.append(case)
    print(f"{len(passing)}/{len(plan['cases'])} Product cases pass oracle.check")

    survived, total = [], 0
    for case in passing:
        for control in CONTROLS[case["id"]]:
            total += 1
            mutated = copy.deepcopy(by_id[case["id"]])
            control(mutated)
            why = outcome(case, mutated, plan)
            print(("killed   " if why else "SURVIVED ") + f"{case['id']}/{control.__name__}: {why}")
            if why is None:
                survived.append(control.__name__)
    print(f"{total - len(survived)}/{total} Product-evidence controls killed")
    return 1 if survived else 0


if __name__ == "__main__":
    raise SystemExit(main())
