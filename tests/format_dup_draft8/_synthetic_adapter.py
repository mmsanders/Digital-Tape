#!/usr/bin/env python3
import json
import sys
from pathlib import Path

from oracle import Media, make_cases, synth_observation

ADAPTER_ID = "format-dup-draft8-synthetic-v1"

cid, inp, out = sys.argv[1:4]
case = next(c for c in make_cases() if c.id == cid)
if Media.decode(Path(inp).read_bytes()) != case.pre:
    raise SystemExit(3)
post, events, calls = synth_observation(case)
Path(out).write_bytes(post.encode())
print(json.dumps({
    "format": "WP-FMTDUP-OBSERVATION-1",
    "case_id": case.id,
    "adapter_kind": "synthetic",
    "adapter_id": ADAPTER_ID,
    "calls": calls,
    "events": events,
}, sort_keys=True))
