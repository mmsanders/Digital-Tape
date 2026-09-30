#!/usr/bin/env python3
"""Synthetic public-observation emitter for the R53 WP-12 closure package.

Validates the verifier only; it is never Product evidence.  Render bytes come
from this module's own chunk store after its own re-spool copy, not from the
oracle's entry walk.  MUTANTS reproduce concrete defects for causal controls.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import sys

import fixtures as F
from oracle import SCHEMA, load_plan

MUTANTS = {
    "drop_last_frame": "re-spool copy omits the timeline's final frame",
    "ignore_entry_start": "re-spool copy reads each entry from frame 0 of its first chunk",
    "flush_failure_not_faulted": "promote flush failure returns IO but leaves the instance mutable",
    "arm_after_header_flush": "V5-001: arm+feed permitted after pass-1 header flush failure",
    "service_touches_media": "tape_service performs a device read while FAULTED",
    "failure_keeps_more_work": "failing continuation leaves more_work set",
}
CF = F.CF


def _render_layout(entries, store, mutant=None):
    parts = []
    for first, start, count in entries:
        pos = 0 if mutant == "ignore_entry_start" else start
        for j in range(count):
            p = pos + j
            chunk, frame = first + p // CF, p % CF
            parts.append(store[chunk][frame * 4:frame * 4 + 4])
    return b"".join(parts)


def _lowest_run(length, high, total_chunks, live):
    for start in range(high, total_chunks - length + 1):
        if not any(c in live for c in range(start, start + length)):
            return start
    return None


def _respool(pre, store, mutant):
    high, entries = pre
    total = sum(e[2] for e in entries)
    length = -(-total // CF)
    timeline = _render_layout(entries, store, mutant if mutant == "ignore_entry_start" else None)
    if mutant == "drop_last_frame":
        timeline = timeline[:-4] + bytes(4)
    padded = timeline + bytes(length * CF * 4 - len(timeline))
    live_a = {0}
    total_chunks = F.RS.derived_total_chunks()
    live = live_a | set(F.RS.entry_chunks(entries))
    d1 = _lowest_run(length, high, total_chunks, live)
    placements = [d1]
    live = live_a | set(range(d1, d1 + length))
    d2 = _lowest_run(length, high, total_chunks, live)
    if d2 is not None and d2 < d1:
        placements.append(d2)
    for d in placements:
        for k in range(length):
            store[d + k] = padded[k * CF * 4:(k + 1) * CF * 4]
    return placements, [(placements[-1], 0, total)]


def _render_phase(layout, store, per_call, rate):
    pcm = _render_layout(layout, store)
    total = len(pcm) // 4
    renders, done = [], 0
    while True:
        n = min(per_call, total - done)
        renders.append({"requested": per_call, "rendered": n, "result": "TAPE_OK", "block_events": []})
        done += n
        if n < per_call:
            break
    return {"seek": {"fn": "tape_seek", "frame": 0, "result": "TAPE_OK"},
            "set_rate": {"fn": "tape_set_rate", "rate_q16_16": rate, "result": "TAPE_OK"},
            "renders": renders, "pcm_bytes": len(pcm), "pcm_sha256": hashlib.sha256(pcm).hexdigest(),
            "tell": total, "at_end": True,
            "stop": {"fn": "tape_set_rate", "rate_q16_16": 0, "result": "TAPE_OK"}}


def render_observation(case, plan, mutant=None):
    rp = plan["render"]
    high, entries = F.RENDER_FIXTURES[case["fixture"]]
    store = {c: F.chunk_audio(c) for c in F.referenced_chunks(entries)}
    pre = F.render_media(case["fixture"])
    obs = {"schema": SCHEMA, "case": case["id"],
           "fixture_metadata_sha256": F.fixture_metadata_sha256(case["fixture"]),
           "mount": {"fn": "tape_mount", "side": "B", "result": "TAPE_OK"},
           "pre": _render_phase(entries, store, rp["render_frames_per_call"], rp["rate_q16_16"])}
    placements, layout = _respool((high, entries), store, mutant)
    total = sum(e[2] for e in entries)
    blocks_needed = len(placements) * -(-total // CF) * F.RS.BLOCKS_PER_CHUNK + 8
    calls = -(-blocks_needed // rp["respool_block_budget"])
    obs["respool"] = [{"fn": "tape_respool", "block_budget": rp["respool_block_budget"],
                       "result": "TAPE_OK", "more_work": i != calls - 1} for i in range(calls)]
    obs["post_same_session"] = _render_phase(layout, store, rp["render_frames_per_call"], rp["rate_q16_16"])
    seq = F.RS.cartridge_sequence(pre)
    slots = list(pre.slots)
    for n, d in enumerate(placements):
        slot = 3 if n == 0 else 2
        slots[slot] = F.RS.idx(1, [(d, 0, total)], seq + 1 + n)
    obs["post_b_slots"] = {"B0": slots[2].hex(), "B1": slots[3].hex()}
    obs["unmount"] = {"fn": "tape_unmount", "result": "TAPE_OK"}
    obs["remount"] = {"fn": "tape_mount", "side": "B", "result": "TAPE_OK"}
    post = F.RS.Media(pre.blocks, pre.primary, pre.mirror, tuple(slots))
    remount_layout = F.RS.parse_entries(post.slots[F.RS.live_slot(post, 1)])
    obs["post_remount"] = _render_phase(remount_layout, store, rp["render_frames_per_call"],
                                        rp["rate_q16_16"])
    return obs


def _ev(op, lba=None, rc=0):
    return {"op": op, "rc": rc} if op == "flush" else {"op": op, "lba": lba, "count": 1, "rc": rc}


def _respool_calls(case):
    budget = case["block_budget"]
    src, dst = 2048 + 10 * 1024, 2048 + 12 * 1024
    calls = [[e for k in range(i, i + budget) for e in (_ev("read", src + k), _ev("write", dst + k))]
             for i in range(0, 2048, budget)]
    calls.append([_ev("flush"), _ev("write", F.LBA_B1 + 1), _ev("flush"), _ev("write", F.LBA_B1), _ev("flush")])
    return calls


def _promote_calls():
    return [[_ev("write", w["lba"]), _ev("flush")] for w in F.PF.transaction("fresh_alloc_full")]


def _fail(case, schedule):
    rule = case["inject"]
    if rule["rule"] == "first_of_call":
        call = schedule[rule["call"]]
        idx = next(i for i, e in enumerate(call) if e["op"] == rule["op"])
        call[idx] = dict(call[idx], rc=5)
        return rule["call"], idx
    for ci, call in enumerate(schedule):
        for i, e in enumerate(call):
            if e["op"] == "write" and e["lba"] == rule["lba"]:
                j = next(k for k in range(i + 1, len(call)) if call[k]["op"] == "flush")
                call[j] = dict(call[j], rc=5)
                return ci, j
    raise AssertionError("synthetic schedule lacks injection point")


def fault_observation(case, plan, mutant=None):
    op = case["op"]
    schedule = _respool_calls(case) if op == "respool" else _promote_calls()
    ci, ei = _fail(case, schedule)
    calls = []
    for i, events in enumerate(schedule[:ci + 1]):
        last = i == ci
        calls.append({"fn": "tape_" + op, "block_budget": case["block_budget"],
                      "result": "TAPE_ERR_IO" if last else "TAPE_OK",
                      "more_work": (mutant == "failure_keeps_more_work") if last else True,
                      "events": events[:ei + 1] if last else events})
    digest = hashlib.sha256((case["id"] + F.fixture_metadata_sha256(case["fixture"])).encode()).hexdigest()
    after = digest
    probe = []
    fns = {"seek": ["tape_seek"], "set_rate": ["tape_set_rate"], "render": ["tape_render"],
           "service": ["tape_service"], "status_info_tell": ["tape_status", "tape_get_info", "tape_tell"],
           "arm": ["tape_arm"], "feed": ["tape_feed"], "commit": ["tape_commit"], "abort": ["tape_abort"],
           "set_side": ["tape_set_side"], "reset_b": ["tape_reset_side_b"], "promote": ["tape_promote"],
           "respool": ["tape_respool"], "dup": ["tape_dup"], "unmount": ["tape_unmount"]}
    allowed = {"render", "status_info_tell", "abort", "unmount"}
    for col in plan["fault_probe_order"]:
        result = "TAPE_OK" if col in allowed else "TAPE_ERR_FAULTED"
        events = []
        if mutant == "flush_failure_not_faulted" and col not in allowed:
            result = "TAPE_ERR_BUSY" if col in ("feed", "commit", "abort") else "TAPE_OK"
            if col in ("service", "promote"):
                events = [_ev("read", 2048)]
        if mutant == "arm_after_header_flush" and col in ("arm", "feed"):
            result = "TAPE_OK"
            if col == "feed":
                events = [_ev("write", 2048 + 12 * 1024)]
                after = hashlib.sha256(b"overwritten" + digest.encode()).hexdigest()
        if mutant == "service_touches_media" and col == "service":
            events = [_ev("read", 0)]
        cell = {"column": col, "calls": [{"fn": fn, "result": result} for fn in fns[col]],
                "block_events": events}
        if col == "dup":
            cell["dst_block_events"] = []
        probe.append(cell)
    return {"schema": SCHEMA, "case": case["id"],
            "fixture_metadata_sha256": F.fixture_metadata_sha256(case["fixture"]),
            "mount": {"fn": "tape_mount", "side": case["mount_side"], "result": "TAPE_OK"},
            "calls": calls, "device_sha256_at_fault": digest,
            "device_sha256_before_unmount": after, "probe": probe}


def observation(case, plan, mutant=None):
    if case["kind"] == "render":
        return render_observation(case, plan, mutant)
    return fault_observation(case, plan, mutant)


def all_observations(mutant=None):
    plan = load_plan()
    return [observation(c, plan, mutant) for c in plan["cases"]]


if __name__ == "__main__":
    out = b"".join((json.dumps(o, sort_keys=True, separators=(",", ":")) + "\n").encode()
                   for o in all_observations())
    sys.stdout.buffer.write(gzip.compress(out, compresslevel=9, mtime=0))
