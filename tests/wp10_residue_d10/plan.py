#!/usr/bin/env python3
"""Planner for the DRAFT-10 residue-destination rows (Verification #138, V10-001).

Rows (acceptance WP-10 "Residue destinations"; tapefs §9.5 item 5, §9.5 step 1, §9.6 step 1):

- R1: shape (a). Each of the four generation-exhausted shapes is run until the fallback's last zero
  tears after L1 = 1…511 landed bytes. That residue is the precondition. The re-run on the same
  device is injected at every residue-zeroing boundary, at every landed length of both fresh
  superblock writes, and at every flush.
- R2: shapes (b)–(d), crafted residue, with the same re-run injections. Every residue-zeroing
  interruption is also followed by an uninterrupted re-run (the observed two-interruption closure).
- R3: an all-zero blank destination takes no step-1 write.

Each row runs for both `tape_dup` (tapefs §9.5) and `tape_format` (tapefs §9.6), in both §8.1
durability modes.
"""
from __future__ import annotations

import hashlib
import json

from pins import M

B = M.B
ZERO = M.ZERO
OPS = ("dup", "format")
MODES = ("flush_required", "write_through")
L1 = range(1, 512)
PREVIOUS_LABEL = b"Previous tape"
FRESH = {"dup": B.FRESH_DUP_UUID, "format": B.FRESH_FORMAT_UUID}
FINAL_SB = {"dup": M.with_label(B.superblock(generation=1, state=0, uuid=B.FRESH_DUP_UUID, high=1), b""),
            "format": B.final_superblock("format")}
FOREIGN = bytes((i * 89 + 7) & 0xFF for i in range(M.BLOCK))


def _crc_broken(sb):
    b = bytearray(sb)
    b[200] ^= 0x01                      # body byte: magic intact, CRC no longer matches
    return bytes(b)


_raw = B.raw_shapes()
_EXH = B.superblock(generation=0xFFFFFFFD, uuid=M.OLD_UUID, high=1)
_EXH_LOW = B.superblock(generation=0xFFFFFFFC, uuid=M.OLD_UUID, high=1)
_OLD = M.with_label(M.OLD_SB, PREVIOUS_LABEL)

# Shape (a): the fallback zeroes the non-selectable copy first and the candidate last (§9.5 step 1,
# V6-008), so the residue lies in the primary in the first two shapes and in the mirror in the last two.
EXHAUSTION_SHAPES = {
    "exhaustion_candidate": (_raw["exhaustion_candidate"].primary, _raw["exhaustion_candidate"].mirror),
    "exhaustion_equal_divergent": (_raw["exhaustion_equal_divergent"].primary,
                                   _raw["exhaustion_equal_divergent"].mirror),
    "exhaustion_mirror_only": (ZERO, M.with_label(_EXH, PREVIOUS_LABEL)),
    "exhaustion_mirror_candidate": (_EXH_LOW, M.with_label(_EXH, PREVIOUS_LABEL)),
}
RESIDUE_COPY = {"exhaustion_candidate": "P", "exhaustion_equal_divergent": "P",
                "exhaustion_mirror_only": "M", "exhaustion_mirror_candidate": "M"}

# Shapes (b)-(d): crafted residue over an old cartridge's index and audio blocks.
RESIDUE_SHAPES = {
    "b_torn_primary": (ZERO[:1] + _OLD[1:], ZERO),       # a torn zero broke the magic; bytes 1-511 old
    "b_torn_mirror": (ZERO, ZERO[:1] + _OLD[1:]),
    "b_crc_primary": (_crc_broken(_OLD), ZERO),          # magic intact, CRC broken
    "b_crc_mirror": (ZERO, _crc_broken(_OLD)),
    "c_foreign": (FOREIGN, FOREIGN[::-1]),
    "d_ff": (b"\xff" * M.BLOCK, b"\xff" * M.BLOCK),
}
BLANK_VARIANTS = ("zero_device", "zero_superblocks")


def base(p, m):
    return M.cartridge(p, m)


def blank(variant):
    if variant == "zero_device":
        return {name: ZERO for name in M.TRACKED}
    return M.cartridge(ZERO, ZERO)


def op_ops(op, img):
    """tapefs §9.5 / §9.6 write order for a raw destination img (item 5 classification, DRAFT-10)."""
    if op == "dup":
        return M.dup_ops(img)
    return M.step1_ops(img) + [("w", "A1h", ZERO), ("w", "B1h", ZERO), ("f",),
                               ("w", "A0h", B.FORMAT_A0), ("w", "B0h", B.FORMAT_B0), ("f",),
                               ("w", "M", FINAL_SB["format"]), ("f",), ("w", "P", FINAL_SB["format"]), ("f",)]


def first_run_inject():
    return ("write", 1, None)            # the fallback's last zero; landed = L1


def precondition(group):
    """(image, first-run ops or None, first-run inject or None)."""
    if group["row"] == "R1":
        start = base(*EXHAUSTION_SHAPES[group["shape"]])
        ops = op_ops(group["op"], start)
        inject = ("write", 1, group["l1"])
        images = M.possible_images(start, ops, inject, group["mode"])
        assert len(images) == 1, "the first zero is flushed before the last zero is written"
        return images[0], ops, inject
    return base(*RESIDUE_SHAPES[group["shape"]]), None, None


def rerun_injections(ops, n_step1, scope):
    """(inject, phase) in transaction order: every flush, and every landed length 0…512 of the n_step1
    step-1 writes and both fresh superblock writes ("superblock_writes"), or of every write ("all_writes").
    Phases map onto the §9.5/§9.6 residue and blank rows."""
    writes = [i for i, o in enumerate(ops) if o[0] == "w"]
    sb_mirror, sb_primary = len(writes) - 2, len(writes) - 1
    assert ops[writes[sb_mirror]][1] == "M" and ops[writes[sb_primary]][1] == "P"
    out, wk, fk, last = [], 0, 0, None
    for o in ops:
        if o[0] == "w":
            phase = ("residue" if wk < n_step1 else "sb_mirror" if wk == sb_mirror
                     else "sb_primary" if wk == sb_primary else "steps23")
            if phase != "steps23" or scope == "all_writes":
                out += [(("write", wk, landed), phase) for landed in range(M.BLOCK + 1)]
            last = phase
            wk += 1
        else:
            out.append((("flush", fk), "after" if last == "sb_primary" else last))
            fk += 1
    return out


def step1_writes(img):
    return sum(o[0] == "w" for o in M.step1_ops(img))


def iter_groups():
    i = 0
    for op in OPS:
        for shape in EXHAUSTION_SHAPES:
            for mode in MODES:
                for l1 in L1:
                    yield {"index": i, "row": "R1", "op": op, "shape": shape, "mode": mode, "l1": l1,
                           "scope": "all_writes" if l1 == 1 else "superblock_writes"}
                    i += 1
    for op in OPS:
        for shape in RESIDUE_SHAPES:
            for mode in MODES:
                yield {"index": i, "row": "R2", "op": op, "shape": shape, "mode": mode, "scope": "all_writes"}
                i += 1
    for op in OPS:
        for variant in BLANK_VARIANTS:
            for mode in MODES:
                yield {"index": i, "row": "R3", "op": op, "variant": variant, "mode": mode}
                i += 1


IDENT = ("index", "row", "op", "shape", "mode", "l1", "scope", "variant")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def trace(ops):
    return [{"op": "write", "lba": M.TRACKED[o[1]], "count": 1, "data_sha256": M.sha(o[2])}
            if o[0] == "w" else {"op": "flush"} for o in ops]


def trace_sha256(ops):
    return M.sha(canonical(trace(ops)).encode())


def census():
    """Group and injection counts, and a digest binding every group's identity and planned re-run."""
    h = hashlib.sha256()
    out = {"groups": {}, "injections": {}, "closure_reruns": 0}
    plan_cache = {}
    for g in iter_groups():
        key = (g["row"], g["op"])
        out["groups"][key] = out["groups"].get(key, 0) + 1
        ident = {k: g[k] for k in IDENT if k in g}
        if g["row"] == "R3":
            ops = op_ops(g["op"], blank(g["variant"]))
            h.update((canonical({**ident, "plan": trace_sha256(ops)}) + "\n").encode())
            continue
        pre, _, _ = precondition(g)
        ops = op_ops(g["op"], pre)
        pk = trace_sha256(ops)
        if (pk, g["scope"]) not in plan_cache:
            plan_cache[(pk, g["scope"])] = rerun_injections(ops, step1_writes(pre), g["scope"])
        inj = plan_cache[(pk, g["scope"])]
        out["injections"][key] = out["injections"].get(key, 0) + len(inj)
        if g["row"] == "R2":
            out["closure_reruns"] += sum(ph == "residue" for _, ph in inj)
        h.update((canonical({**ident, "precondition": M.digest(pre), "plan": pk, "injections": len(inj)})
                  + "\n").encode())
    out["caseset_sha256"] = h.hexdigest()
    return {"groups": {f"{r}.{o}": n for (r, o), n in out["groups"].items()},
            "injections": {f"{r}.{o}": n for (r, o), n in out["injections"].items()},
            "injections_total": sum(out["injections"].values()),
            "closure_reruns": out["closure_reruns"], "caseset_sha256": out["caseset_sha256"]}


if __name__ == "__main__":
    print(canonical(census()))
