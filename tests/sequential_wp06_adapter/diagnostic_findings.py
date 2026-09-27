#!/usr/bin/env python3
"""Diagnostic for the two WP-06 R44 findings. NOT the canonical run, and not evidence.

The canonical result is run_product.py's manifest. This script checks whether the
two findings reported to PM/Verification are the *only* reasons the canonical
replay fails. It applies each translation to a copy of the retained JSONL and
re-checks every case with the verifier's own oracle.check:

  F1  the public function is `tape_reset_side_b`; the oracle's op-to-fn map
      derives `tape_reset_b`, which the API does not declare.
  F2  spec counts commit *blocks* (tapefs §8, engine-api invariant 24); the
      device contract passes a block `count` per callback, and the engine writes
      the entry array with one multi-block callback. The oracle counts callbacks.
      The translation splits each commit-step write into `count` one-block events.

Translated observations are never written to the evidence directory or passed to
runner.py. The committed engine and the retained JSONL are unchanged.
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


def f1(obs: dict) -> dict:
    for c in obs["calls"]:
        if c["fn"] == "tape_reset_side_b":
            c["fn"] = "tape_reset_b"
    return obs


def f2(obs: dict) -> dict:
    events = []
    for e in obs["events"]:
        if e["step"] == "commit" and e["op"] == "write" and e.get("count", 1) > 1:
            for k in range(e["count"]):
                events.append(dict(e, lba=e["lba"] + k, count=1))
        else:
            events.append(e)
    for i, e in enumerate(events):
        e["ordinal"] = i
    obs["events"] = events
    return obs


def failures(by_id: dict, transform) -> dict:
    out = {}
    for c in cases():
        try:
            check(c, transform(copy.deepcopy(by_id[c.id])))
        except (AssertionError, KeyError, TypeError, ValueError, OverflowError) as e:
            out[c.id] = str(e)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("observations", type=Path, help="observations.jsonl or .jsonl.gz")
    a = ap.parse_args()
    raw = a.observations.read_bytes()
    if a.observations.suffix == ".gz":
        raw = gzip.decompress(raw)
    by_id = {json.loads(line)["case"]: json.loads(line) for line in raw.decode().splitlines()}
    rows = {
        "as retained": failures(by_id, lambda o: o),
        "F1 only": failures(by_id, f1),
        "F2 only": failures(by_id, f2),
        "F1 and F2": failures(by_id, lambda o: f2(f1(o))),
    }
    print(json.dumps({"canonical": False, "cases": len(by_id), "failures": rows}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
