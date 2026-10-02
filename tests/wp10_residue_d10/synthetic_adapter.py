#!/usr/bin/env python3
"""Synthetic public-observation emitter for the DRAFT-10 residue rows (#138). Verifier self-test only.

It plays a conforming engine (the planned tapefs §9.5/§9.6 order) on its own fault-injecting device
emulator. It chooses injection coordinates the way ADAPTER.md requires a Product adapter to: from its
own uninterrupted trace, never from the planner. MUTANTS are causal controls.
"""
from __future__ import annotations

import gzip
import json
import sys

import plan as P
from pins import M

MUTANTS = {
    # DRAFT-9 behaviour: residue classified blank, step 1 skipped (red on trace and on outcome)
    "skip_residue_zeroing": ("R1", "R2"),
    # primary zeroed before mirror (red on trace only: every residue state is unmountable either way)
    "residue_zero_order": ("R1", "R2"),
    # only the copy holding non-zero bytes is zeroed (red on trace only)
    "residue_zeroes_nonzero_copy_only": ("R1", "R2"),
    # an all-zero blank destination is zeroed as if residue (red on R3 and on R2 closure re-runs from blank)
    "zero_blank_as_residue": ("R2", "R3"),
}
SB_LBAS = {M.TRACKED["P"], M.TRACKED["M"]}


def engine_ops(op, img, mutant):
    """The engine under test: the planned order, or a mutant of it."""
    ops = P.op_ops(op, img)
    residue = M.is_residue(img)
    if residue and mutant == "skip_residue_zeroing":
        ops = ops[4:]
    elif residue and mutant == "residue_zero_order":
        ops = [("w", "P", M.ZERO), ("f",), ("w", "M", M.ZERO), ("f",)] + ops[4:]
    elif residue and mutant == "residue_zeroes_nonzero_copy_only":
        keep = [c for c in ("M", "P") if any(img[c])]
        ops = [x for c in keep for x in (("w", c, M.ZERO), ("f",))] + ops[4:]
    elif mutant == "zero_blank_as_residue" and not any(img["P"]) and not any(img["M"]):
        ops = [("w", "M", M.ZERO), ("f",), ("w", "P", M.ZERO), ("f",)] + ops
    return ops


class Device:
    """Fault-injecting block device (tapefs §8.1): writes may tear at any landed byte count; in
    flush-required mode a completed write is durable only after the next flush, and a crash leaves any
    subset of the unflushed writes durable; in write-through mode a completed write is durable at once."""

    def __init__(self, img, mode):
        self.durable, self.pending, self.mode = dict(img), {}, mode
        self.trace, self.lbas = [], []

    def run(self, ops, cut=None, pick=0):
        """Issue ops; cut = ("write", k, landed) or ("flush", j). Returns the durable image after power loss
        (or after completion), choosing which unflushed writes survived from the bits of pick."""
        wk = fk = 0
        for o in ops:
            if o[0] == "w":
                self.trace.append(o)
                self.lbas.append(M.TRACKED[o[1]])
                if cut and cut[0] == "write" and cut[1] == wk:
                    landed = cut[2]
                    if landed == M.BLOCK:
                        self._complete(o)
                        return self._crash(pick)
                    img = self._crash(pick)
                    if landed:
                        img[o[1]] = o[2][:landed] + self.durable[o[1]][landed:]
                    return img
                self._complete(o)
                wk += 1
            else:
                self.trace.append(o)
                if cut and cut[0] == "flush" and cut[1] == fk:
                    return self._crash(pick)           # the flush may or may not have taken effect
                self.durable.update(self.pending)
                self.pending = {}
                fk += 1
        assert cut is None, "injection did not fire"
        self.durable.update(self.pending)
        return dict(self.durable)

    def _complete(self, o):
        if self.mode == "write_through":
            self.durable[o[1]] = o[2]
        else:
            self.pending[o[1]] = o[2]

    def _crash(self, pick):
        img = dict(self.durable)
        for bit, (name, data) in enumerate(sorted(self.pending.items())):
            if pick >> bit & 1:
                img[name] = data
        return img


def mount_code(img, pick=0):
    c = M.classify(img, "A", True)
    r = c["result"]
    if r == ("TAPE_OK",):
        return "OK." + c["uuid"][:8]
    return r[pick % len(r)]                    # §4.1 phase 1 leaves BAD_MAGIC/CRC to the engine


def coordinates(op, img, mode, mutant, scope):
    """ADAPTER.md: every flush, and every landed length of every superblock-LBA write (scope
    "superblock_writes") or of every write ("all_writes"), in call order, taken from the engine's own
    uninterrupted trace on a copy of the destination."""
    d = Device(img, mode)
    d.run(engine_ops(op, img, mutant))
    out, wk, fk = [], 0, 0
    for o in d.trace:
        if o[0] == "w":
            if scope == "all_writes" or M.TRACKED[o[1]] in SB_LBAS:
                out += [("write", wk, landed) for landed in range(M.BLOCK + 1)]
            wk += 1
        else:
            out.append(("flush", fk))
            fk += 1
    return out, d


def residue_phase(d):
    """From a clean run: (writes, flushes) issued before the engine's first non-superblock write."""
    first = next(i for i, x in enumerate(d.lbas) if x not in SB_LBAS)
    at = [i for i, o in enumerate(d.trace) if o[0] == "w"][first]
    return first, sum(o[0] == "f" for o in d.trace[:at])


def observation(g, mutant=None):
    if mutant and g["row"] not in MUTANTS[mutant]:
        mutant = None
    op, mode = g["op"], g["mode"]
    ident = {k: g[k] for k in P.IDENT if k in g}
    out = {"schema": "wp10-residue-d10-observation-v1", **ident}
    call = {"fn": "tape_dup" if op == "dup" else "tape_format", "result": "TAPE_OK", "more_work": False}
    if g["row"] == "R3":
        img = P.blank(g["variant"])
        d = Device(img, mode)
        final = d.run(engine_ops(op, img, mutant))
        return {**out, "call": call, "trace_sha256": P.trace_sha256(d.trace), "write_lbas": d.lbas,
                "durable_sha256": M.digest(final), "mount": mount_code(final)}
    if g["row"] == "R1":
        start = P.base(*P.EXHAUSTION_SHAPES[g["shape"]])
        d = Device(start, mode)
        pre = d.run(engine_ops(op, start, mutant), ("write", 1, g["l1"]))
        out["first_run"] = {"trace_sha256": P.trace_sha256(d.trace), "durable_sha256": M.digest(pre),
                            "mount": mount_code(pre, g["l1"])}
    else:
        pre = P.base(*P.RESIDUE_SHAPES[g["shape"]])
        out["precondition"] = {"durable_sha256": M.digest(pre), "mount": mount_code(pre, g["index"])}
    cuts, clean = coordinates(op, pre, mode, mutant, g["scope"])
    final = dict(clean.durable)
    nw, nf = residue_phase(clean)
    out["rerun"] = {"call": call, "trace_sha256": P.trace_sha256(clean.trace), "durable_sha256": M.digest(final),
                    "mount": mount_code(final)}
    inj, closure = [], []
    ops = engine_ops(op, pre, mutant)
    for i, cut in enumerate(cuts):
        img = Device(pre, mode).run(ops, cut, pick=g["index"] + i)
        inj.append(M.digest(img)[:16] + " " + mount_code(img, g["index"] + i))
        if g["row"] == "R2" and cut[1] < (nw if cut[0] == "write" else nf):
            xd = Device(img, mode)
            xfinal = xd.run(engine_ops(op, img, mutant))
            closure.append(P.trace_sha256(xd.trace)[:16] + " " + M.digest(xfinal)[:16] + " " + mount_code(xfinal))
    out["injections"] = inj
    if g["row"] == "R2":
        out["closure"] = closure
    return out


def lines(mutant=None, groups=None):
    for g in groups if groups is not None else P.iter_groups():
        yield json.dumps(observation(g, mutant), sort_keys=True, separators=(",", ":"))


if __name__ == "__main__":
    if "--gzip" in sys.argv:
        raw = "".join(line + "\n" for line in lines()).encode("utf-8")
        sys.stdout.buffer.write(gzip.compress(raw, compresslevel=9, mtime=0))
    else:
        out = sys.stdout.buffer
        for line in lines():
            out.write(line.encode("utf-8") + b"\n")
