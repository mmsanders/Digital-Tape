#!/usr/bin/env python3
"""Synthetic public-observation emitter for the #126 strengthening rows. Verifier self-test only.

Row 1 copies real image bytes block by block and renders from them; row 2 runs a spec-following re-spool on
the C69-layout image and logs every write with metadata bytes; row 3 wraps the maintained #99 synthetic
observation with the A-slot raw bytes the fixture carries. Mutants model the defects each row must catch.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
import sys
import zlib

import oracle as O
import pins
import rows as R

MUTANTS = {
    "copy_only_first_block": 1,          # V-R54-02: the defect the #116 row could not see
    "copy_skips_second_block": 1,
    "copy_skips_last_block": 1,
    "pass2_onto_then_live_chunk": 2,     # #121 control: pass 2 lands on the pass-1 layout it is replacing
    "pass2_declines": 2,
    "pass1_below_floor": 2,
    "a0_at_sequence_3": 3,
    "a1_structurally_valid": 3,
    "a_slots_not_snapshotted": 3,
}
BLOCK = R.BLOCK
C69 = R.C69


# ------------------------------------------------------------------ row 1

def dup_copy(src, dst, frames, mutant):
    out = bytearray(dst)
    base = R.B.LBA_CHUNK_BASE * BLOCK
    n_blocks = -(-frames * R.FRAME // BLOCK)
    skip = set()
    if mutant == "copy_only_first_block":
        skip = set(range(1, n_blocks))
    elif mutant == "copy_skips_second_block" and n_blocks > 1:
        skip = {1}
    elif mutant == "copy_skips_last_block" and n_blocks > 1:
        skip = {n_blocks - 1}
    for k in range(n_blocks):
        if k not in skip:
            out[base + k * BLOCK:base + (k + 1) * BLOCK] = src[base + k * BLOCK:base + (k + 1) * BLOCK]
    return bytes(out)


def row1(case, mutant):
    frames, dest = case["frames"], case["destination"]
    src, dst = R.dup_source_image(frames), R.dup_destination_image(dest)
    base = R.B.LBA_CHUNK_BASE * BLOCK
    copied = dup_copy(src, dst, frames, mutant)
    pcm = R.sha(copied[base:base + frames * R.FRAME])
    return {"frames": frames, "destination": dest, "source_image_sha256": R.sha(src),
            "destination_image_sha256_before": R.sha(dst),
            "call": {"fn": "tape_dup", "result": "TAPE_OK", "more_work": False},
            "source_pcm_sha256": R.sha(src[base:base + frames * R.FRAME]), "copy_raw_sha256": pcm,
            "mount_A": {"result": "TAPE_OK", "info": {"total_frames": frames, "entry_count": 1}, "pcm_sha256": pcm},
            "mount_B": {"result": "TAPE_OK", "info": {"total_frames": frames, "entry_count": 1}, "pcm_sha256": pcm}}


# ------------------------------------------------------------------ row 2

def row2(case, mutant):
    image = bytearray(R.pass2_image())
    events, total = [], sum(e[2] for e in R.PASS2_B)
    data = R.FINAL.render(bytes(image), R.PASS2_B)

    def write(lba, payload, meta):
        image[lba * BLOCK:(lba + 1) * BLOCK] = payload
        events.append({"op": "write", "lba": lba, "count": 1, **({"data": payload.hex()} if meta else {})})

    def flush():
        events.append({"op": "flush"})

    def copy_pass(dest, slot, seq):
        base = C69.LBA_CHUNK_BASE + dest * C69.CHUNK_BLOCKS
        for k in range(-(-len(data) // BLOCK)):
            write(base + k, data[k * BLOCK:(k + 1) * BLOCK].ljust(BLOCK, b"\0"), False)
        flush()
        raw = C69.build_index(1, seq, [(dest, 0, total)])
        write(O.SLOT_LBA[slot] + 1, raw[BLOCK:2 * BLOCK], True)
        flush()
        write(O.SLOT_LBA[slot], raw[:BLOCK], True)
        flush()

    d1 = 2 if mutant == "pass1_below_floor" else 4
    copy_pass(d1, "B1", 21)
    if mutant != "pass2_declines":
        copy_pass(d1 if mutant == "pass2_onto_then_live_chunk" else 2, "B0", 22)
    slots = {n: O._slot_from_bytes(bytes(image[lba * BLOCK:(lba + C69.SLOT_BLOCKS) * BLOCK]))
             for n, lba in O.SLOT_LBA.items()}
    live = O._live(slots, "B")[1]["entries"]
    return {"fixture": case["fixture"], "image_sha256_before": R.sha(R.pass2_image()),
            "mount": {"fn": "tape_mount", "side": "A", "result": "TAPE_OK"},
            "calls": [{"fn": "tape_respool", "block_budget": R.RS_BUDGET, "result": "TAPE_OK", "more_work": False}],
            "events": events,
            "mount_B_after": {"result": "TAPE_OK", "info": {"total_frames": total, "entry_count": len(live)},
                              "pcm_sha256": R.sha(R.FINAL.render(bytes(image), live))}}


# ------------------------------------------------------------------ row 3

def _valid_a1():
    h = bytearray(bytes.fromhex(R.a0_empty_slot()["header"]))
    h[8:12] = (2).to_bytes(4, "little")
    h[60:64] = zlib.crc32(bytes(h[:60])).to_bytes(4, "little")
    return {"header": bytes(h).hex(), "entries": ""}


def row3(case, mutant):
    cap_case = O.capacity_cases()[case["capacity_case"]]
    obs = pins.CAP_SYNTH.observation(cap_case)
    raw = dict(obs["raw_before"])
    a0 = R.a0_empty_slot()
    if mutant == "a0_at_sequence_3":
        h = bytearray(bytes.fromhex(a0["header"]))
        h[8:12] = (3).to_bytes(4, "little")
        h[60:64] = zlib.crc32(bytes(h[:60])).to_bytes(4, "little")
        a0 = {"header": bytes(h).hex(), "entries": ""}
    if mutant != "a_slots_not_snapshotted":
        raw["A0"] = a0
        raw["A1"] = _valid_a1() if mutant == "a1_structurally_valid" else R.invalid_slot()
    obs["raw_before"] = raw
    obs["fixture_sha256"] = hashlib.sha256(O.canonical(raw).encode()).hexdigest()
    obs["capacity_case"] = case["capacity_case"]
    return obs


def observation(case, mutant=None):
    if mutant and MUTANTS[mutant] != case["row"]:
        mutant = None
    body = (row1, row2, row3)[case["row"] - 1](case, mutant)
    return {**body, "schema": O.SCHEMA, "index": case["index"], "row": case["row"], "kind": case["kind"]}


def lines(mutant=None):
    for case in O.iter_cases():
        yield json.dumps(observation(case, mutant), sort_keys=True, separators=(",", ":"))


if __name__ == "__main__":
    raw = "".join(line + "\n" for line in lines()).encode("utf-8")
    sys.stdout.buffer.write(gzip.compress(raw, compresslevel=9, mtime=0))
