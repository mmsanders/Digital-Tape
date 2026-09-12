#!/usr/bin/env python3
"""Synthetic adapter used only to prove the verifier package can observe/replay itself."""
import json
import sys
from pathlib import Path
from hardened import Media, make_cases, synth_observation

cid, inp, out = sys.argv[1:4]
case = next(c for c in make_cases() if c.id == cid)
if Media.decode(Path(inp).read_bytes()) != case.pre:
    raise SystemExit(3)
post, events, calls = synth_observation(case)
Path(out).write_bytes(post.encode())
print(json.dumps({'format':'VT8-OPS-OBSERVATION-1', 'adapter_kind':'synthetic',
                  'calls':calls, 'events':events}, sort_keys=True))
