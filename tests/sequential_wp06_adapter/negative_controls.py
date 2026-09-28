#!/usr/bin/env python3
"""Red controls on the Product evidence itself. NOT the canonical run.

The package's selftest.py kills its red controls on synthetic observations. A
green Product replay also needs to show that the same oracle rejects *this
adapter's* output once one observed fact is wrong. Each control mutates one
field of one case in a copy of the Product JSONL and requires the verifier's
own oracle.check to reject that case; the unmutated case must pass. Exits
non-zero if any control survives.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "sequential_wp06_r44"))
from oracle import cases, check  # noqa: E402


def commit_writes(o):
    return [e for e in o["events"] if e["step"] == "commit" and e["op"] == "write"]


def wrong_reset_symbol(o):
    for c in o["calls"]:
        if c["fn"] == "tape_reset_side_b":
            c["fn"] = "tape_reset_b"


def entry_blocks_over_budget(o):
    commit_writes(o)[0]["count"] += 1


def entry_blocks_short(o):
    commit_writes(o)[0]["count"] -= 1


def header_multi_block(o):
    commit_writes(o)[-1]["count"] = 2


def missing_final_flush(o):
    flushes = [e for e in o["events"] if e["step"] == "commit" and e["op"] == "flush"]
    o["events"].remove(flushes[-1])


def repair_wrong_partner(o):
    w = [e for e in o["events"] if e["step"] == "mount" and e["op"] == "write"][0]
    w["lba"] = 0 if w["lba"] != 0 else o["block_count"] - 1


def repair_indicator(o):
    for c in o["calls"]:
        if c["step"] == "mount" and c["fn"] == "tape_get_info":
            c["needs_repair"] = not c["needs_repair"]


def refusal_wrote(o):
    o["snapshots"]["after_mount"]["B1"] = "ff" + o["snapshots"]["after_mount"]["B1"][2:]


def degraded_not_cleared(o):
    for c in o["calls"]:
        if c["step"] == "exercise" and c["fn"] == "tape_get_info":
            c["side_b_valid"] = False


CONTROLS = [
    ("degraded-divergent-reset_b", wrong_reset_symbol),
    ("degraded-invalid-reset_b", degraded_not_cleared),
    ("roundtrip-max-entries", entry_blocks_over_budget),
    ("roundtrip-max-entries", entry_blocks_short),
    ("roundtrip-entry-block-boundary", header_multi_block),
    ("roundtrip-one-frame", missing_final_flush),
    ("repair-stale-mirror-success", repair_wrong_partner),
    ("repair-invalid-primary-write", repair_indicator),
    ("refusal-bad-A-with-partner", refusal_wrote),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("observations", type=Path, help="observations.jsonl or .jsonl.gz")
    a = ap.parse_args()
    raw = a.observations.read_bytes()
    if a.observations.suffix == ".gz":
        raw = gzip.decompress(raw)
    by_id = {json.loads(line)["case"]: json.loads(line) for line in raw.decode().splitlines()}
    plan = {c.id: c for c in cases()}
    survived = []
    for case_id, control in CONTROLS:
        check(plan[case_id], copy.deepcopy(by_id[case_id]))
        obs = copy.deepcopy(by_id[case_id])
        control(obs)
        try:
            check(plan[case_id], obs)
            survived.append(control.__name__)
            print(f"SURVIVED {control.__name__} on {case_id}")
        except (AssertionError, KeyError, TypeError, ValueError, IndexError, OverflowError) as e:
            print(f"killed   {control.__name__} on {case_id}: {e}")
    print(f"{len(CONTROLS) - len(survived)}/{len(CONTROLS)} Product-evidence controls killed")
    return 1 if survived else 0


if __name__ == "__main__":
    raise SystemExit(main())
