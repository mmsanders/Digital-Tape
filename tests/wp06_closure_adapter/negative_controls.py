#!/usr/bin/env python3
"""Per-case oracle outcomes and red controls on the Product evidence. NOT canonical.

replay.py stops at the first failing case. This script runs the verifier's own
oracle.check on every case separately and prints each outcome, so the whole
7-case census is visible. Then, for every case whose Product observation passes,
it mutates one causal fact in a copy and requires oracle.check to reject it.

Exit status: 1 if any control survives. A failing Product case is reported, not
counted here; replay.py's exit status is the canonical verdict.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "wp06_closure_r52"))
from oracle import check, load_plan  # noqa: E402


def renumber(o):
    for i, e in enumerate(o["events"]):
        e["ordinal"] = i + 1


def sidea_refusal_wrote(o):               # zero writes on the READ_ONLY refusal
    o["events"].append({"step": "exercise", "op": "write", "lba": 0, "count": 1, "ordinal": 0, "result": 0})
    renumber(o)


def respool_full_accepted(o):             # CARTRIDGE_FULL, not OK
    next(c for c in o["calls"] if c["fn"] == "tape_respool")["result"] = "TAPE_OK"


def arm_did_not_clear(o):                 # stage clear before the record's first write
    o["events"] = [e for e in o["events"] if not (e["step"] == "arm" and e["op"] == "write" and e["lba"] == 0)]
    renumber(o)


def reset_left_degraded(o):               # remount must see a live B
    next(c for c in o["calls"] if c["step"] == "remount" and c["fn"] == "tape_get_info")["side_b_valid"] = False


def remount_selected_stale_b(o):          # the reset's B must win on remount
    o["snapshots"]["after_remount"] = copy.deepcopy(o["snapshots"]["before"])


CHUNK_BASE = 2048


def _is_chunk_write(o, e):
    return (e["step"] == "exercise" and e["op"] == "write"
            and CHUNK_BASE <= e["lba"] < o["block_count"] - 1)


def phase1_onto_live_b(o):                # invariant 10: first copy lands on live-B chunk 3
    e = next(e for e in o["events"] if _is_chunk_write(o, e))
    e["lba"] = CHUNK_BASE + 3 * 1024 + (e["lba"] - CHUNK_BASE) % 1024


def phase2_missing(o):                    # promote must copy [0, len) after the step-4 superblock
    first_sb = next(i for i, e in enumerate(o["events"]) if e["step"] == "exercise"
                    and e["op"] == "write" and e["lba"] in (0, o["block_count"] - 1))
    o["events"] = [e for i, e in enumerate(o["events"]) if not (i > first_sb and _is_chunk_write(o, e))]
    renumber(o)


def index_commit_without_data(o):         # R53: every metadata write carries its bytes
    e = next(e for e in o["events"] if e["step"] == "exercise" and e["op"] == "write"
             and 0 < e["lba"] < CHUNK_BASE)
    del e["data"]


CONTROLS = {
    "E-SIDEA-REFUSE": [sidea_refusal_wrote],
    "E-RESPOOL-FULL": [respool_full_accepted],
    "E-RECORD-PROMOTE": [arm_did_not_clear],
    "F-STAGE-DEGRADED-ABSENT": [reset_left_degraded],
    "F-STAGE-DEGRADED-DIVERGENT": [remount_selected_stale_b],
    "F-LIVEB-PROMOTE-FLOOR": [phase1_onto_live_b, phase2_missing],
    "F-LIVEB-RESPOOL-FLOOR": [phase1_onto_live_b, index_commit_without_data],
}


def outcome(case, obs):
    try:
        check(case, obs)
        return None
    except (AssertionError, KeyError, TypeError, ValueError, IndexError, StopIteration) as e:
        return str(e) or type(e).__name__


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("observations", type=Path, help="observations.jsonl or .jsonl.gz")
    a = ap.parse_args()
    raw = a.observations.read_bytes()
    if a.observations.suffix == ".gz":
        raw = gzip.decompress(raw)
    by_id = {o["case"]: o for o in map(json.loads, raw.decode().splitlines())}
    plan = load_plan()["cases"]

    passing = []
    for case in plan:
        why = outcome(case, copy.deepcopy(by_id[case["id"]]))
        print(f"{'PASS' if why is None else 'FAIL'}  {case['id']}" + ("" if why is None else f": {why}"))
        if why is None:
            passing.append(case)
    print(f"{len(passing)}/{len(plan)} Product cases pass oracle.check")

    survived, total = [], 0
    for case in passing:
        for control in CONTROLS[case["id"]]:
            total += 1
            mutated = copy.deepcopy(by_id[case["id"]])
            control(mutated)
            why = outcome(case, mutated)
            if why is None:
                survived.append(control.__name__)
                print(f"SURVIVED {control.__name__} on {case['id']}")
            else:
                print(f"killed   {control.__name__} on {case['id']}: {why}")
    print(f"{total - len(survived)}/{total} Product-evidence controls killed")
    return 1 if survived else 0


if __name__ == "__main__":
    raise SystemExit(main())
