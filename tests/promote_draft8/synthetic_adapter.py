#!/usr/bin/env python3
"""Synthetic-only adapter for verifier self-development. Never product evidence."""
from __future__ import annotations
import json
import sys

from oracle import expected_observation
from planner import EXPECTED_CASESET_SHA256

print(json.dumps({
    "format": "PROMOTE-ADAPTER-1",
    "adapter_kind": "synthetic",
    "adapter_id": "verifier-synthetic-only",
    "caseset_sha256": EXPECTED_CASESET_SHA256,
    "raw_observation_only": True,
}), flush=True)

for line in sys.stdin:
    obj = json.loads(line)
    if obj.get("done") is True:
        break
    print(json.dumps(expected_observation(obj), sort_keys=True), flush=True)
