#!/usr/bin/env python3
"""Synthetic public-observation emitter for WP-10 backlog rows (#116). Verifier self-test only."""
from __future__ import annotations

import gzip
import json
import struct
import sys

import model as M
import oracle as O

MUTANTS = {
    "repair_rewrites_candidate": 1,   # phase 4 writes the candidate copy instead of the partner
    "repair_bumps_generation": 1,     # repair writes the partner at sb_generation + 1
    "rerun_noop_when_incomplete": 2,  # re-run returns OK without work on WRITE_IN_PROGRESS media
    "rerun_skips_barrier": 2,         # re-run skips step 1 on media with a valid superblock
    "rerun_skips_residue_zeroing": 2, # DRAFT-9 behaviour: residue treated as blank (V10-001 regression)
    "label_not_copied": 3,
    "b0_written_side_a": 3,
    "high_water_floor": 3,
}


def _mount(img, side, writable, label=None):
    exp = O.mount_expectation(img, side, writable)
    out = {"result": exp["results"][0], "repair_events": exp.get("repair_events", [])}
    if out["result"] == "TAPE_OK":
        out["info"] = dict(exp["info"])
        if "pcm_sha256" in exp:
            out["pcm_sha256"] = exp["pcm_sha256"]
    return out, exp.get("after", img)


def _repair_ops(base, mutant):
    ops = M.repair_ops(base)
    if mutant == "repair_rewrites_candidate":
        c = M.classify(base, "A", True)["repair"]
        ops = [("w", "P" if c[0] == M.MIRROR else "M", M.ZERO[:8] + c[1][8:]), ("f",)]
    elif mutant == "repair_bumps_generation":
        b = bytearray(ops[0][2])
        struct.pack_into("<I", b, 12, M.gen(ops[0][2]) + 1)
        struct.pack_into("<I", b, 508, M.crc32(bytes(b[:508])))
        ops = [("w", ops[0][1], bytes(b)), ("f",)]
    return ops


def row1(case, mutant):
    base = M.cartridge(*M.REPAIR_SHAPES[case["shape"]])
    ops = _repair_ops(base, mutant)
    inject = tuple(case["inject"])
    images = M.possible_images(base, ops, inject, case["mode"])
    img = images[case["index"] % len(images)]
    ro, _ = _mount(img, "A", False)
    rw, after = _mount(img, "A", True)
    return {"fired": True, "repair_trace_sha256": O.trace_sha256(M.prefix(ops, inject)),
            "durable_sha256": M.digest(img), "ro_A": ro, "rw_A": rw, "durable_after_rw_sha256": M.digest(after)}


def row2(case, mutant):
    base = M.rerun_destination(case["shape"])
    ops = M.dup_ops(base)
    inject = tuple(case["inject"])
    images = M.possible_images(base, ops, inject, case["mode"])
    img = images[case["index"] % len(images)]
    rerun_ops = M.dup_ops(img)
    incomplete = M.classify(img, "A", False)["result"] == ("TAPE_ERR_INCOMPLETE",)
    if mutant == "rerun_noop_when_incomplete" and incomplete:
        rerun_ops = []
    if mutant == "rerun_skips_barrier" and (M.sb_valid(img["P"]) or M.sb_valid(img["M"])):
        rerun_ops = rerun_ops[4:]
    if mutant == "rerun_skips_residue_zeroing" and M.is_residue(img):
        rerun_ops = rerun_ops[4:]
    final = M.apply(img, rerun_ops)
    rw_a, _ = _mount(final, "A", True)
    rw_b, _ = _mount(final, "B", True)
    return {"fired": True, "trace_sha256": O.trace_sha256(M.prefix(ops, inject)), "durable_sha256": M.digest(img),
            "rerun": {"call": {"fn": "tape_dup", "result": "TAPE_OK", "more_work": False},
                      "trace_sha256": O.trace_sha256(rerun_ops),
                      "dst_chunk_lbas": sorted({M.TRACKED[o[1]] for o in rerun_ops if o[0] == "w" and o[1] == "C0"}),
                      "durable_sha256": M.digest(final)},
            "rw_A": rw_a, "rw_B": rw_b}


def row3(case, mutant):
    frames, lab, final = O.row3_expected(case["source"], case["destination"])
    final = dict(final)
    if mutant == "label_not_copied":
        final["P"] = final["M"] = M.with_label(final["P"], b"")
    if mutant == "b0_written_side_a":
        h = bytearray(final["B0h"]); h[12] = 0; final["B0h"] = bytes(h)
    if mutant == "high_water_floor" and frames % M.CF:
        b = bytearray(final["P"]); struct.pack_into("<I", b, 56, frames // M.CF)
        struct.pack_into("<I", b, 508, M.crc32(bytes(b[:508]))); final["P"] = final["M"] = bytes(b)
    src_pcm = M.sha(("source:" + case["source"]).encode())
    mounts = {}
    for side in ("A", "B"):
        sb = final["P"]
        b0_ok = final["B0h"][12] == 1
        high_ok = int.from_bytes(sb[56:60], "little") * M.CF >= frames
        ok = (side == "A" and high_ok) or (side == "B" and b0_ok and high_ok)
        if not ok:
            mounts[side] = {"result": "TAPE_ERR_NO_VALID_INDEX"}
            continue
        label = sb[M.LABEL_OFFSET:M.LABEL_OFFSET + M.LABEL_BYTES].rstrip(b"\0").decode("utf-8")
        mounts[side] = {"result": "TAPE_OK", "info": {"total_frames": frames, "side_b_valid": b0_ok, "label": label}}
    mounts["A"]["pcm_sha256"] = src_pcm
    return {"source_label_hex": lab.ljust(M.LABEL_BYTES, b"\0").hex(), "source_pcm_sha256": src_pcm,
            "call": {"fn": "tape_dup", "result": "TAPE_OK", "more_work": False},
            "raw_after": {k: final[k].hex() for k in ("P", "M", "A0h", "B0h")},
            "mount_A": mounts["A"], "mount_B": mounts["B"]}


def observation(case, mutant=None):
    if mutant and MUTANTS[mutant] != case["row"]:
        mutant = None
    body = (row1, row2, row3)[case["row"] - 1](case, mutant)
    ident = {k: case[k] for k in ("shape", "mode", "inject", "source", "destination") if k in case}
    return {"schema": O.SCHEMA, "index": case["index"], "row": case["row"], **ident, **body}


def lines(mutant=None):
    for case in O.iter_cases():
        yield json.dumps(observation(case, mutant), sort_keys=True, separators=(",", ":"))


if __name__ == "__main__":
    raw = "".join(line + "\n" for line in lines()).encode("utf-8")
    sys.stdout.buffer.write(gzip.compress(raw, compresslevel=9, mtime=0))
