#!/usr/bin/env python3
"""Independent oracle for the WP-08 mapped-run rows (Verification #129, DRAFT-9).

Authorities: engine-api §6 (seek clamps; seek/set_rate clear both flags), §6.1-§6.3 (fetch, emit, then
advance; reverse snap to (total_frames-1)<<32; at_start set only from position 0; render touches no device;
service does all I/O, at most block_budget blocks per call), §5 (mount); tapefs §5.1 (entry mapping, frames
contiguous across a run); acceptance WP-08 (V4-010 seek-then-render at every run boundary +/-1; V5-005
reverse-from-end multi-frame golden). Rates are exactly +/-1.0x from grid-aligned positions, so §8 interpolation
is the identity (f == 0) and no engine arithmetic beyond §6.2's integral advance is modelled.

Not pinned (#115): which blocks service reads, in what order, how many per call within the budget, or how
many service calls complete the fill.
"""
from __future__ import annotations

import functools
import hashlib
import json

import rows as R

SCHEMA = "wp08-mapping-r56-observation-v1"
FORBIDDEN_KEYS = {"verdict", "passed", "expected", "expected_pcm", "outcome_ok", "row_ok", "timeline",
                  "physical", "chunk", "mapping"}
BLOCK_COUNT = R.C69.LBA_MIRROR + 1


def need(ok, why):
    if not ok:
        raise AssertionError(why)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _no_verdicts(value, where="observation"):
    if isinstance(value, dict):
        bad = FORBIDDEN_KEYS & set(value)
        need(not bad, f"{where} carries adapter-derived field(s) {sorted(bad)}")
        for k, v in value.items():
            _no_verdicts(v, f"{where}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _no_verdicts(v, f"{where}[{i}]")


@functools.lru_cache(maxsize=None)
def image_sha():
    return R.sha(R.image())


@functools.lru_cache(maxsize=None)
def timeline(side):
    return tuple(R.timeline(side))


# ------------------------------------------------------------------ call-stream walker

class Stream:
    def __init__(self, calls):
        need(isinstance(calls, list), "calls")
        self.calls, self.i = calls, 0

    def take(self, fn, **args):
        need(self.i < len(self.calls), f"missing call {fn}")
        c = self.calls[self.i]
        self.i += 1
        need(isinstance(c, dict) and c.get("fn") == fn, f"call {self.i - 1}: expected {fn}, got {c.get('fn')}")
        for k, v in args.items():
            need(c.get(k) == v, f"{fn} argument {k}={c.get(k)!r}, expected {v!r}")
        ev = c.get("events")
        need(isinstance(ev, list), f"{fn} events")
        if fn in ("tape_mount", "tape_service"):
            for e in ev:
                need(e.get("op") == "read", f"{fn} performed a {e.get('op')} (playback writes nothing)")
                need(isinstance(e.get("lba"), int) and isinstance(e.get("count"), int) and e["count"] >= 1
                     and 0 <= e["lba"] and e["lba"] + e["count"] <= BLOCK_COUNT, f"{fn} read out of range {e}")
                need(e.get("rc", 0) == 0, f"{fn} read callback failed {e}")
        else:
            # §6.3: render never touches the block device; seek/rate/tell/status are pure state calls.
            need(ev == [], f"{fn} made block-device callbacks {ev[:3]}")
        return c

    def service_to_completion(self):
        n = 0
        while True:
            c = self.take("tape_service", block_budget=R.SERVICE_BUDGET)
            need(c.get("result") == "TAPE_OK", f"tape_service result {c.get('result')}")
            need(sum(e["count"] for e in c["events"]) <= R.SERVICE_BUDGET,
                 "tape_service read more than block_budget blocks (§6.3)")
            n += 1
            if c.get("more_work") is False:
                return n
            need(c.get("more_work") is True, "tape_service more_work")

    def done(self):
        need(self.i == len(self.calls), f"{len(self.calls) - self.i} unexpected trailing call(s)")


def _render_check(s, side, requested, want_frames, tell, at_start, at_end, label):
    c = s.take("tape_render", requested=requested)
    need(c.get("result") == "TAPE_OK", f"{label}: render result {c.get('result')} (ring filled by service)")
    got = bytes.fromhex(c.get("pcm_hex", ""))
    need(c.get("rendered") == len(want_frames) and len(got) == 4 * len(want_frames),
         f"{label}: rendered {c.get('rendered')}, expected {len(want_frames)}")
    want = b"".join(want_frames)
    if got != want:
        tl = timeline(side)
        for k in range(len(want_frames)):
            if got[4 * k:4 * k + 4] != want_frames[k]:
                frame = got[4 * k:4 * k + 4]
                where = tl.index(frame) if frame in tl else "not on this side's timeline"
                raise AssertionError(f"{label}: output frame {k} is timeline frame {where}, "
                                     f"expected the frame at the mapped position")
    t = s.take("tape_tell")
    need(t.get("result") == "TAPE_OK" and t.get("frame") == tell, f"{label}: tell {t.get('frame')} != {tell}")
    st = s.take("tape_status")
    need(st.get("result") == "TAPE_OK" and st.get("at_start") is at_start and st.get("at_end") is at_end,
         f"{label}: flags at_start={st.get('at_start')} at_end={st.get('at_end')}")


def _open(s, side):
    m = s.take("tape_mount", side=side, resume_frame=0, warm=None)
    need(m.get("result") == "TAPE_OK", f"mount Side {side}: {m.get('result')}")


# ------------------------------------------------------------------ row 1: V4-010 at mapped boundaries

def check_row1(case, obs):
    side, n, rate = case["side"], case["seek"], case["rate"]
    s = Stream(obs.get("calls"))
    _open(s, side)
    need(s.take("tape_seek", frame=n).get("result") == "TAPE_OK", "seek result")
    r = s.take("tape_set_rate", rate=rate)
    need(r.get("result") == "TAPE_OK", "set_rate result")
    s.service_to_completion()
    d = 1 if rate > 0 else -1
    tl = timeline(side)
    want = [tl[n + d * k] for k in range(R.ROW1_RENDER)]
    _render_check(s, side, R.ROW1_RENDER, want, n + d * R.ROW1_RENDER, False, False,
                  f"Side {side} seek {n} rate {'+' if d > 0 else '-'}1.0x")
    s.done()


# ------------------------------------------------------------------ row 2: V5-005 reverse-from-end golden

def check_row2(case, obs):
    side = case["side"]
    s = Stream(obs.get("calls"))
    _open(s, side)
    need(s.take("tape_seek", frame=R.TOTAL).get("result") == "TAPE_OK", "seek result")   # clamps to max_pos
    need(s.take("tape_set_rate", rate=-R.ONE).get("result") == "TAPE_OK", "set_rate result")
    rev = list(reversed(timeline(side)))          # §6.3 snap to the last frame, then exact reverse order
    pos, at_start, k, renders = R.TOTAL - 1, False, 0, 0
    while True:
        s.service_to_completion()
        want = []
        while len(want) < R.ROW2_RENDER and not at_start:   # §6.2 at -1.0x from a grid position
            want.append(rev[k])
            k += 1
            if pos == 0:
                at_start = True
            else:
                pos -= 1
        renders += 1
        _render_check(s, side, R.ROW2_RENDER, want, pos, at_start, False, f"Side {side} reverse render {renders}")
        if len(want) < R.ROW2_RENDER:
            break
    need(k == R.TOTAL and renders == -(-R.TOTAL // R.ROW2_RENDER), "reverse traversal length")
    s.done()


# ------------------------------------------------------------------ planning

def iter_cases():
    idx = 0
    for side in R.SIDES:
        for b in R.crossings(side):
            for off in R.OFFSETS:
                for rate in R.RATES:
                    yield {"index": idx, "row": 1, "kind": "seek_boundary", "side": side, "crossing": b,
                           "seek": b + off, "rate": rate}
                    idx += 1
    for side in R.SIDES:
        yield {"index": idx, "row": 2, "kind": "reverse_end", "side": side}
        idx += 1


@functools.lru_cache(maxsize=None)
def plan_census():
    h = hashlib.sha256()
    census = {"row1": 0, "row2": 0}
    for c in iter_cases():
        h.update((canonical(c) + "\n").encode())
        census[f"row{c['row']}"] += 1
    census["caseset_sha256"] = h.hexdigest()
    return census


def check(case, obs):
    _no_verdicts(obs)
    need(obs.get("schema") == SCHEMA and obs.get("index") == case["index"] and obs.get("row") == case["row"]
         and obs.get("kind") == case["kind"], "schema/case identity")
    for k in ("side", "crossing", "seek", "rate"):
        if k in case:
            need(obs.get(k) == case[k], f"case identity: {k}")
    need(obs.get("image_sha256") == image_sha(), "fixture image differs from rows.image()")
    need(obs.get("block_count") == BLOCK_COUNT, "device block_count")
    (check_row1, check_row2)[case["row"] - 1](case, obs)


def check_stream(lines):
    cases = iter_cases()
    n = 0
    for line in lines:
        case = next(cases, None)
        need(case is not None, "more observations than planned cases")
        check(case, json.loads(line))
        n += 1
    need(next(cases, None) is None, f"only {n} observations; plan has more cases")
    return n
