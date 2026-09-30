#!/usr/bin/env python3
"""Per-case outcomes, red controls and one labelled diagnostic. NOT canonical.

1. Runs the package's oracle.check on every retained case (replay.py stops at
   the first failure) and prints each outcome.
2. For every passing case, requires oracle.check to reject one causal mutation
   of its Product observation.
3. Diagnostic, only when --adapter is given: the two promote fault cases plan
   their failure at the first write/flush of continuation call 1, which the
   Product never reaches at block_budget 1 (see README). This re-runs them with
   the injection moved to call 2, the first continuation that writes, and
   reports what oracle.check concludes. That result is information for
   Verification, never a verdict: the plan is unchanged and so is the
   canonical FAIL.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "wp12_closure_r53"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
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


CONTROLS = {
    "RENDER-TWOPASS": pcm_differs,
    "RENDER-DECLINE": drop_last_frame,
    "RENDER-FRAGMENTED": render_io,
    "F-RESPOOL-WRITE": service_touches_media,
    "F-RESPOOL-HEADER-FLUSH": arm_after_fault,
    "F-PROMOTE-WRITE": service_touches_media,
    "F-PROMOTE-FLUSH": arm_after_fault,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("observations", type=Path, help="observations.jsonl.gz")
    ap.add_argument("--adapter", action="store_true", help="also run the call-2 promote diagnostic")
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

    survived = []
    for case in passing:
        control = CONTROLS[case["id"]]
        mutated = copy.deepcopy(by_id[case["id"]])
        control(mutated)
        why = outcome(case, mutated, plan)
        print(("killed   " if why else "SURVIVED ") + f"{case['id']}/{control.__name__}: {why}")
        if why is None:
            survived.append(control.__name__)
    print(f"{len(passing) - len(survived)}/{len(passing)} Product-evidence controls killed")

    if a.adapter:
        import run_product as rp
        print("DIAGNOSTIC (not canonical): promote fault cases with the injection moved to call 2")
        with tempfile.TemporaryDirectory() as tmp:
            for case in plan["cases"]:
                if case.get("op") != "promote":
                    continue
                moved = copy.deepcopy(case)
                moved["inject"]["call"] = 2
                _, obs = rp.observe(moved, Path(tmp))
                why = outcome(moved, obs, plan)
                calls = [(c["result"], c["more_work"]) for c in obs["calls"]]
                cells = {p["column"]: [c["result"] for c in p["calls"]] for p in obs["probe"]}
                print(f"  {case['id']} @call 2: {'PASS' if why is None else 'FAIL: ' + why}; calls {calls}; "
                      f"arm {cells['arm']} feed {cells['feed']} service {cells['service']}; "
                      f"media unchanged {obs['device_sha256_at_fault'] == obs['device_sha256_before_unmount']}")
    return 1 if survived else 0


if __name__ == "__main__":
    raise SystemExit(main())
