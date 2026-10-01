#!/usr/bin/env python3
"""Independent oracle for the #130 rows (Verification #130, DRAFT-9).

Row 1: public calls only; the remounted Side B must render exactly rows.expected_timeline(at).
Row 2: the #118 row-3 observation, unchanged, must still pass the pinned #118 check, and its clean re-spool
trace must meet the floor tapefs §8 and §9.4 force (V-R55-01). Not pinned (#115): chunk write partitioning
beyond the floor, extra flushes, read traffic, pass-1 placement.
"""
from __future__ import annotations

import functools
import hashlib
import json

import pins
import rows as R

SCHEMA = "wp09-gaps-r56-observation-v1"
FORBIDDEN_KEYS = {"verdict", "passed", "expected", "expected_pcm", "outcome_ok", "row_ok", "floor_ok",
                  "commit_count", "saturated"}
W10 = pins.W10
C69 = R.C69


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


# ------------------------------------------------------------------ row 1: full-scale overdub saturation

@functools.lru_cache(maxsize=None)
def overdub_image_sha():
    return R.sha(R.overdub_image())


class Calls:
    def __init__(self, calls):
        need(isinstance(calls, list), "calls")
        self.calls, self.i = calls, 0

    def take(self, fn, **args):
        need(self.i < len(self.calls), f"missing call {fn}")
        c = self.calls[self.i]
        self.i += 1
        need(isinstance(c, dict) and c.get("fn") == fn, f"call {self.i - 1}: expected {fn}, got {c.get('fn')}")
        for k, v in args.items():
            need(c.get(k) == v, f"{fn} {k}={c.get(k)!r}, expected {v!r}")
        need(c.get("result") == "TAPE_OK", f"{fn} returned {c.get('result')}")
        return c

    def service(self):
        while True:
            c = self.take("tape_service", block_budget=R.SERVICE_BUDGET)
            if c.get("more_work") is False:
                return
            need(c.get("more_work") is True, "tape_service more_work")


def check_row1(case, obs):
    at = R.POSITIONS[case["position"]]
    need(obs.get("image_sha256") == overdub_image_sha(), "fixture image differs from rows.overdub_image()")
    s = Calls(obs.get("calls"))
    s.take("tape_mount", side="B", resume_frame=0, warm=None)
    s.take("tape_seek", frame=at)
    s.take("tape_arm", mode="TAPE_REC_OVERDUB")
    f = s.take("tape_feed", frames=R.INPUT_FRAMES, pcm_hex=R.pcm(R.input_frames(at)).hex())
    need(f.get("accepted") == R.INPUT_FRAMES, f"tape_feed accepted {f.get('accepted')}")
    s.service()
    s.take("tape_commit")
    s.take("tape_unmount")
    s.take("tape_mount", side="B", resume_frame=0, warm=None)
    s.take("tape_seek", frame=0)
    s.take("tape_set_rate", rate=R.ONE)
    got = b""
    while True:
        s.service()
        r = s.take("tape_render", requested=R.RENDER)
        chunk = bytes.fromhex(r.get("pcm_hex", ""))
        need(len(chunk) == 4 * r.get("rendered", -1), "render pcm length")
        got += chunk
        if r["rendered"] < R.RENDER:
            break
    need(s.i == len(s.calls), "unexpected trailing calls")
    want = R.expected_timeline(at)
    need(len(got) == 4 * len(want), f"remounted Side B rendered {len(got) // 4} frames, expected {len(want)}")
    if got != R.pcm(want):
        for p, w in enumerate(want):
            g = R.pcm([w])
            if got[4 * p:4 * p + 4] != g:
                import struct
                gl, gr = struct.unpack_from("<hh", got, 4 * p)
                raise AssertionError(f"frame {p}: got ({gl}, {gr}), expected {w} (engine-api §8 clamp, §11 append)")


# ------------------------------------------------------------------ row 2: V-R55-01 trace floor

def _slot_of(lba):
    for name, base in R.B_SLOTS.items():
        if base <= lba < base + C69.SLOT_BLOCKS:
            return name, lba - base
    return None, None


def trace_floor(fid, events):
    """tapefs §8 per commit, segmented at each B header write:
       chunk data >= ceil(4T/512) blocks -> flush -> entry block(s) 1..ceil(12E/512) of the inactive slot ->
       flush -> exactly one header block of that slot -> flush; and the §9.4 commit count for the fixture."""
    chunk_lo, chunk_hi = C69.LBA_CHUNK_BASE, C69.LBA_MIRROR
    headers = [i for i, e in enumerate(events) if e.get("op") == "write" and _slot_of(e["lba"])[1] == 0]
    need(len(headers) in R.COMMITS_ALLOWED[fid],
         f"{fid}: {len(headers)} index commit(s); tapefs §9.4 allows {R.COMMITS_ALLOWED[fid]}")
    live, start = "B0", 0
    for n, h in enumerate(headers):
        slot, _ = _slot_of(events[h]["lba"])
        need(events[h].get("count") == 1, f"{fid} commit {n + 1}: header write of {events[h].get('count')} blocks")
        need(slot != live, f"{fid} commit {n + 1}: header written to the live slot {slot} (§8 inactive slot)")
        seg = events[start:h]
        idx = [k for k, e in enumerate(seg) if e.get("op") == "write"]
        ent = [k for k in idx if _slot_of(seg[k]["lba"])[0] == slot and seg[k]["lba"] > R.B_SLOTS[slot]]
        covered = {seg[k]["lba"] + j - R.B_SLOTS[slot] for k in ent for j in range(seg[k]["count"])}
        need(1 in covered, f"{fid} commit {n + 1}: entry block 1 of {slot} never written (§8 step 3)")
        data = [k for k in idx if chunk_lo <= seg[k]["lba"] < chunk_hi]
        blocks = sum(seg[k]["count"] for k in data)
        need(blocks >= R.data_floor_blocks(fid),
             f"{fid} commit {n + 1}: {blocks} chunk block(s) written, floor {R.data_floor_blocks(fid)} (§8 step 1)")
        need(max(data) < min(ent), f"{fid} commit {n + 1}: chunk write after the entry array")
        flush = lambda a, b: any(seg[k].get("op") == "flush" for k in range(a + 1, b))
        need(flush(max(data), min(ent)), f"{fid} commit {n + 1}: no flush between chunk data and entries (§8 step 2)")
        need(flush(max(ent), len(seg)), f"{fid} commit {n + 1}: no flush between entries and header (§8 step 4)")
        nxt = next((k for k in range(h + 1, len(events)) if events[k].get("op") in ("write", "flush")), None)
        need(nxt is not None and events[nxt]["op"] == "flush",
             f"{fid} commit {n + 1}: header not followed by a flush (§8 step 6)")
        need(sum(1 for e in events[start:nxt + 1] if e.get("op") == "flush") >= 3,
             f"{fid} commit {n + 1}: fewer than three flushes")
        live, start = slot, nxt + 1
    need(not any(e.get("op") == "write" for e in events[start:]), f"{fid}: write after the last commit")


def check_row2(case, obs):
    rec = obs.get("wp10_final_record")
    need(isinstance(rec, dict), "wp10_final_record")
    w10case = next(c for c in W10.iter_cases() if c["row"] == 3 and c["fixture"] == case["fixture"])
    need(rec.get("index") == w10case["index"] and rec.get("fixture") == case["fixture"], "#118 record identity")
    W10.check(w10case, rec)                          # the accepted #118 row-3 check, unchanged
    trace_floor(case["fixture"], rec["clean"]["events"])


# ------------------------------------------------------------------ planning

def iter_cases():
    idx = 0
    for pos in R.POSITIONS:
        yield {"index": idx, "row": 1, "kind": "overdub_saturation", "position": pos}
        idx += 1
    for fid in R.FIXTURES:
        yield {"index": idx, "row": 2, "kind": "respool_floor", "fixture": fid}
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
    _no_verdicts({k: v for k, v in obs.items() if k != "wp10_final_record"})
    need(obs.get("schema") == SCHEMA and obs.get("index") == case["index"] and obs.get("row") == case["row"]
         and obs.get("kind") == case["kind"], "schema/case identity")
    for k in ("position", "fixture"):
        if k in case:
            need(obs.get(k) == case[k], f"case identity: {k}")
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
