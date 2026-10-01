#!/usr/bin/env python3
"""Synthetic public-observation emitter for the #130 rows. Verifier self-test only.

Row 1 models a spec-following overdub (engine-api §8 clamp, §11 append) behind the public call sequence.
Row 2 wraps the #118 row-3 records from that package's committed synthetic evidence (pinned by blob), which
sit exactly at the tapefs §8/§9.4 floor. Row-2 mutants model an *adapter* that under-reports its trace: the
dropped event and every injection it planned are removed and the rest renumbered, so the pinned #118 row-3
oracle still accepts the record - that is V-R55-01 - and only this package's floor can see it.
"""
from __future__ import annotations

import copy
import functools
import gzip
import json
import sys

import oracle as O
import pins
import rows as R

ROW1_MUTANTS = {
    "overdub_wraps": "int16 wrap instead of the §8 clamp",
    "negative_rail_32767": "negative clamp at -32767 (a symmetric clamp)",
    "positive_overflow_wraps": "only the negative side is clamped",
    "append_mixed_with_last_frame": "frames past the end are mixed with the last frame (§11 says pass through)",
}


def _mix(e, x, mutant):
    s = e + x
    if mutant == "overdub_wraps" or (mutant == "positive_overflow_wraps" and s > 32767):
        return ((s + 32768) & 0xFFFF) - 32768
    if mutant == "negative_rail_32767":
        return max(-32767, min(32767, s))
    return R.sat16(s)


def overdub_timeline(at, mutant):
    base = [R.base_frame(p) for p in range(R.BASE_FRAMES)]
    out = list(base)
    for k, f in enumerate(R.input_frames(at)):
        p = at + k
        if p < len(base):
            out[p] = (_mix(base[p][0], f[0], mutant), _mix(base[p][1], f[1], mutant))
        elif mutant == "append_mixed_with_last_frame":
            out.append((_mix(base[-1][0], f[0], None), _mix(base[-1][1], f[1], None)))
        else:
            out.append(f)
    return out


def row1(case, mutant):
    at = R.POSITIONS[case["position"]]
    tl = overdub_timeline(at, mutant)
    ok = {"result": "TAPE_OK"}
    calls = [{"fn": "tape_mount", "side": "B", "resume_frame": 0, "warm": None, **ok},
             {"fn": "tape_seek", "frame": at, **ok},
             {"fn": "tape_arm", "mode": "TAPE_REC_OVERDUB", **ok},
             {"fn": "tape_feed", "frames": R.INPUT_FRAMES, "pcm_hex": R.pcm(R.input_frames(at)).hex(),
              "accepted": R.INPUT_FRAMES, **ok},
             {"fn": "tape_service", "block_budget": R.SERVICE_BUDGET, "more_work": False, **ok},
             {"fn": "tape_commit", **ok}, {"fn": "tape_unmount", **ok},
             {"fn": "tape_mount", "side": "B", "resume_frame": 0, "warm": None, **ok},
             {"fn": "tape_seek", "frame": 0, **ok}, {"fn": "tape_set_rate", "rate": R.ONE, **ok}]
    pos = 0
    while True:
        calls.append({"fn": "tape_service", "block_budget": R.SERVICE_BUDGET, "more_work": False, **ok})
        part = tl[pos:pos + R.RENDER]
        calls.append({"fn": "tape_render", "requested": R.RENDER, "rendered": len(part),
                      "pcm_hex": R.pcm(part).hex(), **ok})
        pos += len(part)
        if len(part) < R.RENDER:
            break
    return {"image_sha256": O.overdub_image_sha(), "calls": calls}


# ------------------------------------------------------------------ row 2

@functools.lru_cache(maxsize=None)
def w10_row3_records():
    out = {}
    with gzip.open(pins.W10_SYNTHETIC, "rt", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec.get("row") == 3:
                out[rec["fixture"]] = rec
    assert set(out) == set(R.FIXTURES)
    return out


def under_report(rec, drop):
    """An adapter that omits clean event `drop` (an index into the write/flush events) and enumerates from the
    shrunken trace, reusing the crash results of the surviving injection points."""
    rec = copy.deepcopy(rec)
    ev = rec["clean"]["events"]
    old_plan = O.W10.row3_injections(ev)
    by_point = {(m, tuple(i)): c for (m, i, _), c in zip(old_plan, rec["crashes"])}
    op = ev[drop]["op"]
    rank = sum(1 for e in ev[:drop] if e["op"] == op)
    new_ev = ev[:drop] + ev[drop + 1:]
    crashes = []
    for mode, inject, prefix_len in O.W10.row3_injections(new_ev):
        kind, k = inject[0], inject[1]
        old_k = k + 1 if kind == op and k >= rank else k
        old = by_point[(mode, tuple([kind, old_k] + inject[2:]))]
        crashes.append({**old, "inject": inject, "prefix_len": prefix_len})
    rec["clean"]["events"], rec["crashes"] = new_ev, crashes
    return rec


def drop_second_commit(rec):
    """An adapter that reports only pass 1: the trace ends at the first commit's final flush."""
    ev = [e for e in rec["clean"]["events"]]
    heads = [i for i, e in enumerate(ev) if e["op"] == "write" and O._slot_of(e["lba"])[1] == 0]
    if len(heads) < 2:
        return rec
    end = next(k for k in range(heads[0] + 1, len(ev)) if ev[k]["op"] == "flush")
    rec = copy.deepcopy(rec)
    for drop in range(len(ev) - 1, end, -1):
        if ev[drop]["op"] in ("write", "flush"):
            rec = under_report(rec, drop)
    return rec


def row2(case, mutant):
    rec = w10_row3_records()[case["fixture"]]
    if mutant is not None:
        kind, arg = mutant
        rec = under_report(rec, arg) if kind == "drop_event" else drop_second_commit(rec)
    return {"wp10_final_record": rec}


def observation(case, mutant=None):
    body = row1(case, mutant) if case["row"] == 1 else row2(case, mutant)
    obs = {"schema": O.SCHEMA, "index": case["index"], "row": case["row"], "kind": case["kind"], **body}
    for k in ("position", "fixture"):
        if k in case:
            obs[k] = case[k]
    return obs


def lines(mutant=None):
    for case in O.iter_cases():
        yield json.dumps(observation(case, mutant), sort_keys=True, separators=(",", ":"))


if __name__ == "__main__":
    raw = "".join(line + "\n" for line in lines()).encode()
    sys.stdout.buffer.write(gzip.compress(raw, compresslevel=9, mtime=0))
