#!/usr/bin/env python3
"""Synthetic public-observation emitter for the WP-10 R53 package.

Validates the verifier only; it is never Product evidence.  For flush-required
pending writes it picks one permitted durable image deterministically per case.
MUTANTS reproduce concrete engine defects for the causal controls.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import sys

import model as M
from oracle import SCHEMA, canonical, durable_digest, iter_cases, sha, trace_events

MUTANTS = {
    "empty_source_zero_frame_entry": ("DUP-EMPTY-BLANK", "DUP-EMPTY-REUSABLE"),
    "empty_family_promote_accepts": ("DUP-EMPTY-BLANK",),
    "slot1_not_zeroed": ("DUP-REUSABLE-STALE", "FMT-REUSABLE-STALE"),
    "template_flush_skipped": ("DUP-REUSABLE-STALE", "FMT-REUSABLE-STALE", "DUP-EMPTY-REUSABLE"),
    "primary_before_mirror": ("FMT-BLANK", "DUP-BLANK"),
    "needs_repair_hidden": ("FMT-BLANK", "DUP-BLANK"),
    "source_written": ("DUP-EMPTY-BLANK", "DUP-REUSABLE-STALE", "DUP-BLANK"),
}
TX_MUTANTS = {"empty_source_zero_frame_entry", "slot1_not_zeroed", "template_flush_skipped",
              "primary_before_mirror"}


def _crash_image(scenario, inject, mode, mutant, index):
    tx_mutant = mutant if mutant in TX_MUTANTS else None
    choices = M.possible_images(scenario, inject, mode, tx_mutant)
    return choices[index % len(choices)]


def _prefix(scenario, inject, mutant):
    ops = M.transaction(scenario, mutant if mutant in TX_MUTANTS else None)
    out, wk, fk = [], 0, 0
    for o in ops:
        out.append(o)
        if o[0] == "w":
            if inject and inject[0] == "write" and inject[1] == wk:
                return out
            wk += 1
        else:
            if inject and inject[0] == "flush" and inject[1] == fk:
                return out
            fk += 1
    return out


def _mount(img, side, writable, mutant):
    c = M.classify(img, side, writable)
    result = c["result"][0]
    out = {"result": result, "repair_events": []}
    if result != "TAPE_OK":
        return out
    out["info"] = {"uuid": c["uuid"], "free_chunks": c["free_chunks"], "total_frames": c["total_frames"], "entry_count": c["entry_count"],
                   "side_b_valid": c["side_b_valid"], "needs_repair": c["needs_repair"]}
    if mutant == "needs_repair_hidden" and not writable:
        out["info"]["needs_repair"] = False
    if c["repair"]:
        out["repair_events"] = [{"op": "write", "lba": c["repair"][0], "count": 1,
                                 "data_sha256": sha(c["repair"][1])}, {"op": "flush"}]
    if side == "A" and writable:
        out["pcm_sha256"] = M.rendered_sha256(img, c["layout"])
    return out


def observation(case, mutant=None):
    scenario = case["scenario"]
    if mutant and scenario not in MUTANTS[mutant]:
        mutant = None
    op = M.SCENARIOS[scenario][0]
    obs = {"schema": SCHEMA, "index": case["index"], "kind": case["kind"], "scenario": scenario}
    if op == "dup":
        src = hashlib.sha256(b"synthetic source device " + scenario.encode()).hexdigest()
        obs["source_sha256_before"] = src
        obs["source_sha256_after"] = (hashlib.sha256(src.encode()).hexdigest()
                                      if mutant == "source_written" else src)
    if case["kind"] == "crash":
        inject = tuple(case["inject"])
        img = _crash_image(scenario, inject, case["mode"], mutant, case["index"])
        obs.update(mode=case["mode"], inject=case["inject"], fired=True)
        prefix = _prefix(scenario, inject, mutant)
    else:
        img = M.completed_image(scenario, mutant if mutant in TX_MUTANTS else None)
        prefix = _prefix(scenario, None, mutant)
        obs["call"] = {"fn": "tape_" + op, "result": "TAPE_OK"} | ({"more_work": False} if op == "dup" else {})
    obs["trace_sha256"] = sha(canonical(trace_events(prefix)).encode())
    obs["durable_sha256"] = durable_digest(img)
    if case["kind"] == "empty_family":
        obs["mount_B"] = {"fn": "tape_mount", "side": "B", "result": "TAPE_OK"}
        promote = "TAPE_OK" if mutant == "empty_family_promote_accepts" else "TAPE_ERR_INVALID_ARG"
        obs["family"] = [{"fn": "tape_promote", "result": promote, "more_work": False, "block_events": []},
                         {"fn": "tape_respool", "result": "TAPE_OK", "more_work": False, "block_events": []},
                         {"fn": "tape_arm", "result": "TAPE_OK", "block_events": []},
                         {"fn": "tape_commit", "result": "TAPE_OK", "block_events": []}]
        return obs
    obs["ro_A"] = _mount(img, "A", False, mutant)
    obs["rw_A"] = _mount(img, "A", True, mutant)
    obs["rw_B"] = _mount(img, "B", True, mutant)
    return obs


def lines(mutant=None, scenarios=None):
    for case in iter_cases():
        if scenarios and case["scenario"] not in scenarios:
            continue
        yield json.dumps(observation(case, mutant), sort_keys=True, separators=(",", ":"))


if __name__ == "__main__":
    raw = "".join(line + "\n" for line in lines()).encode()
    sys.stdout.buffer.write(gzip.compress(raw, compresslevel=9, mtime=0))
