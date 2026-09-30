#!/usr/bin/env python3
"""Red controls on the Product evidence itself. NOT the canonical run.

The package self-test kills seven controls on synthetic evidence. This
requires the verifier's own oracle.check to reject one single-fact mutation of
a real Product observation per assertion family: trace order, durable bytes,
remount info, phase-4 repair events, rendered audio, the source device, the
injection having fired, and the empty-copy family. The unmutated cases used
must pass.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "wp10_closure_r53"))
import oracle  # noqa: E402


def first(records, pred):
    return next(i for i, o in enumerate(records) if pred(o))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("observations", type=Path, help="observations.jsonl.gz")
    a = ap.parse_args()
    records = [json.loads(line) for line in gzip.decompress(a.observations.read_bytes()).splitlines()]
    cases = list(oracle.iter_cases())

    ok_mount = first(records, lambda o: o["kind"] == "crash" and o.get("rw_A", {}).get("result") == "TAPE_OK")
    repair = first(records, lambda o: o["kind"] == "crash" and o.get("rw_A", {}).get("repair_events"))
    audio = first(records, lambda o: o["kind"] == "crash" and o["scenario"] == "DUP-BLANK"
                  and o.get("rw_A", {}).get("info", {}).get("total_frames") == 128)
    dup = first(records, lambda o: o["scenario"].startswith("DUP") and o["kind"] == "crash")
    family = first(records, lambda o: o["kind"] == "empty_family")

    def m_trace(o): o["trace_sha256"] = "0" * 64
    def m_durable(o): o["durable_sha256"] = "0" * 64
    def m_info(o): o["rw_A"]["info"]["free_chunks"] += 1
    def m_repair(o): o["rw_A"]["repair_events"] = []
    def m_audio(o): o["rw_A"]["pcm_sha256"] = "0" * 64
    def m_source(o): o["source_sha256_after"] = "0" * 64
    def m_fired(o): o["fired"] = False
    def m_family(o): o["family"][0]["result"] = "TAPE_OK"

    controls = [("trace_order", ok_mount, m_trace), ("durable_bytes", ok_mount, m_durable),
                ("remount_info", ok_mount, m_info), ("phase4_repair", repair, m_repair),
                ("rendered_audio", audio, m_audio), ("source_written", dup, m_source),
                ("injection_not_fired", dup, m_fired), ("empty_promote_accepts", family, m_family)]
    survived = []
    for name, i, mutate in controls:
        findings = oracle.new_findings()
        oracle.check(cases[i], copy.deepcopy(records[i]), findings)
        bad = copy.deepcopy(records[i])
        mutate(bad)
        try:
            oracle.check(cases[i], bad, oracle.new_findings())
            survived.append(name)
            print(f"SURVIVED {name} (case {i})")
        except AssertionError as e:
            print(f"killed   {name} (case {i}): {e}")
    print(f"{len(controls) - len(survived)}/{len(controls)} Product-evidence controls killed")
    return 1 if survived else 0


if __name__ == "__main__":
    raise SystemExit(main())
