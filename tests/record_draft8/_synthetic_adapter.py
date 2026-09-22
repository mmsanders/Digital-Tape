#!/usr/bin/env python3
"""Synthetic adapter used only to prove the verifier package can observe itself."""
import json
import sys
from pathlib import Path

from extra import extra_cases, synth_extra
from oracle import Media, make_cases, synth_observation
from refusals import refusal_cases, synth_refusal

cid, inp, out = sys.argv[1:4]
happy = {c.id: c for c in make_cases()}
extras = {row[0]: row for row in extra_cases()}

if cid in happy:
    case = happy[cid]
    if Media.decode(Path(inp).read_bytes()) != case.pre:
        raise SystemExit(3)
    post, events, calls = synth_observation(case)
elif cid in extras:
    _, pre, mode, side, seek, feed, kind = extras[cid]
    if Media.decode(Path(inp).read_bytes()) != pre:
        raise SystemExit(3)
    post, events, calls = synth_extra(cid, pre, mode, side, seek, feed, kind)
else:
    row = next(r for r in refusal_cases() if r[0] == cid)
    _, pre, mode, side, expect = row
    if Media.decode(Path(inp).read_bytes()) != pre:
        raise SystemExit(3)
    post, events, calls = synth_refusal(cid, pre, mode, side, expect)

Path(out).write_bytes(post.encode())
print(
    json.dumps(
        {
            "format": "WP09-REC-OBSERVATION-1",
            "adapter_kind": "synthetic",
            "calls": calls,
            "events": events,
        },
        sort_keys=True,
    )
)
