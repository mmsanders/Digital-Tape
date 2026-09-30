#!/usr/bin/env python3
"""DRAFT-9 WP-08 exact playback arithmetic oracle."""
from __future__ import annotations

import hashlib
import json
import struct

from vectors import Vector, vectors

ONE = 1 << 32
SPEC_HASHES = {
    "spec/tapefs-v1.md": "3f08ec6d11070c1e10edcf7cacbcd93ff694257f042b71b53200e158621fa19d",
    "spec/engine-api.md": "383817326705d98bda6a96480f8185e911113927d35c53c02d1458adb72baea6",
    "spec/acceptance.md": "ae77d13c868fd39a882b5bd3ebf459557792432ce895bc7bf58be7fc2c33825d",
}


def need(ok, why):
    if not ok:
        raise AssertionError(why)


def pcm_hex(frames):
    return b"".join(struct.pack("<hh", *frame) for frame in frames).hex()


def interpolate(a, b, fraction):
    return tuple(a[ch] + ((b[ch] - a[ch]) * fraction // ONE) for ch in (0, 1))


def model(vector: Vector):
    frames = vector.frames
    max_pos = len(frames) * ONE
    position = min(vector.seek, len(frames)) * ONE
    step = vector.rate * 65536
    at_start = at_end = False
    emitted = []
    if not frames:
        at_end = True
    elif step != 0:
        if step < 0 and position >= max_pos:
            position = (len(frames) - 1) * ONE
        for _ in range(vector.requested):
            if step > 0 and position >= max_pos:
                at_end = True
                break
            if step < 0 and at_start:
                break
            i, fraction = divmod(position, ONE)
            a = frames[i]
            b = frames[i + 1] if i + 1 < len(frames) else a
            emitted.append(interpolate(a, b, fraction))
            if step > 0:
                at_start = False
                if position >= max_pos or step >= max_pos - position:
                    position, at_end = max_pos, True
                else:
                    position += step
            else:
                at_end = False
                if position == 0:
                    at_start = True
                else:
                    position = max(0, position + step)
    return emitted, position >> 32, at_start, at_end


# Hand-written from acceptance.md WP-08 (V5-005); never derived from model().
LITERAL_GOLDENS = {
    "reverse-end-acceptance-0-1000-2000": {
        "pcm_hex": pcm_hex([(2000, 2000), (1000, 1000), (0, 0)]),
        "rendered": 3, "tell": 0, "at_start": True, "at_end": False,
    },
}


def check(vector: Vector, observation):
    need(observation.get("schema") == "wp08-portability-r52-v1", "schema")
    need(observation.get("case") == vector.id, "case identity")
    need(observation.get("fixture_sha256") == vector.fixture_sha256(), "fixture identity")
    trace = observation.get("trace")
    need(isinstance(trace, list) and len(trace) == 7, "public trace census")
    expected_prefix = [
        {"fn": "tape_mount", "result": "TAPE_OK", "block_events": []},
        {"fn": "tape_seek", "frame": vector.seek, "result": "TAPE_OK", "block_events": []},
        {"fn": "tape_set_rate", "rate_q16_16": vector.rate,
         "result": "TAPE_OK", "block_events": []},
        {"fn": "tape_service", "budget": 7, "result": "TAPE_OK",
         "more_work": False, "block_events": []},
    ]
    need(trace[:4] == expected_prefix, "setup trace")
    expected_pcm, tell, at_start, at_end = model(vector)
    rendered = len(expected_pcm)
    need(trace[4] == {"fn": "tape_render", "requested": vector.requested,
                      "result": "TAPE_OK", "rendered": rendered,
                      "block_events": []}, "render trace")
    need(trace[5] == {"fn": "tape_tell", "value": tell}, "tell trace")
    need(trace[6] == {"fn": "tape_status", "result": "TAPE_OK",
                      "at_start": at_start, "at_end": at_end}, "status trace")
    need(observation.get("rendered") == rendered, "rendered count")
    need(observation.get("pcm_hex") == pcm_hex(expected_pcm), "exact PCM")
    need(observation.get("tell") == tell, "tell")
    need(observation.get("at_start") is at_start and observation.get("at_end") is at_end,
         "endpoint flags")
    literal = LITERAL_GOLDENS.get(vector.id)
    if literal is not None:
        for key, value in literal.items():
            need(observation.get(key) == value and type(observation.get(key)) is type(value),
                 "literal acceptance golden: " + key)
    return True


def parse_jsonl(raw):
    records = [json.loads(line) for line in raw.splitlines() if line.strip()]
    plan = vectors()
    need(len(records) == len(plan), "case census")
    need([r.get("case") for r in records] == [v.id for v in plan], "case order")
    need(set(LITERAL_GOLDENS) <= {v.id for v in plan}, "literal golden census")
    for vector, observation in zip(plan, records):
        check(vector, observation)
    return records


def observations_sha256(raw):
    parse_jsonl(raw)
    return hashlib.sha256(raw).hexdigest()
