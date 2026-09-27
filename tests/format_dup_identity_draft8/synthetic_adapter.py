#!/usr/bin/env python3
"""Synthetic protocol peer for verifier plumbing only; never product evidence."""
from __future__ import annotations
import json, sys
from oracle import expected_observation
from planner import EXPECTED_CASESET_SHA256

def main():
    print(json.dumps({
        "format": "FMTDUP-ID-ADAPTER-2",
        "adapter_kind": "synthetic",
        "adapter_id": "verifier-synthetic-r29",
        "caseset_sha256": EXPECTED_CASESET_SHA256,
        "raw_observation_only": True,
    }, sort_keys=True), flush=True)
    for line in sys.stdin:
        msg = json.loads(line)
        if msg.get("command") == "done":
            return 0
        print(json.dumps(expected_observation(msg), sort_keys=True), flush=True)
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
