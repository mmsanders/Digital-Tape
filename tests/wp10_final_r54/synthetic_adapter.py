#!/usr/bin/env python3
"""Synthetic public-observation emitter for the final WP-10 backlog rows (#118). Verifier self-test only.

Rows 1-3 run a small spec-following engine model on real image bytes and a fault-injecting device; its
remount renders straight from durable bytes, a different path from the oracle's pattern-derived timeline.
Row 4 uses the pinned #116 duplicate model. Mutants model the defects each row exists to catch.
"""
from __future__ import annotations

import gzip
import json
import struct
import sys

import dupmodel as DM
import model as M
import oracle as O

F = M.F
MUTANTS = {
    # row 1
    "reset_b_ignores_sequence_headroom": 1,
    "stage_clear_before_headroom": 1,
    "stage_clear_generation_not_counted": 1,
    # row 2
    "zero_needed_consults_counters": 2,
    "respool_ignores_sequence_headroom": 2,
    # row 3
    "respool_commits_before_copying": 3,
    "respool_pass1_onto_live_b": 3,
    # row 4
    "rerun_skips_barrier": 4,
    "rerun_final_keeps_old_uuid": 4,
}


class Cut(Exception):
    pass


class Device:
    """Caller-owned device: `cur` is what reads see, `dur` what survives a power cut (tapefs §8.1)."""

    def __init__(self, image, mode="write_through", inject=None, ordinal=0):
        self.cur, self.dur = bytearray(image), bytearray(image)
        self.mode, self.inject, self.ordinal = mode, inject, ordinal
        self.pending, self.events, self.nw, self.nf, self.fired, self.torn = [], [], 0, 0, False, None

    def read(self, lba, n=1):
        self.events.append({"op": "read", "lba": lba, "count": n})
        return M.block(self.cur, lba, n)

    def write(self, lba, data):
        self.events.append({"op": "write", "lba": lba, "count": 1})
        if self.inject and self.inject[0] == "write" and self.inject[1] == self.nw:
            self.fired, landed = True, self.inject[2]
            if landed == M.BLOCK:
                (self._durable if self.mode == "write_through" else self.pending.append)((lba, data))
            elif landed:
                self.torn = (lba, data[:landed] + M.block(self.dur, lba)[landed:])
            raise Cut
        self.nw += 1
        M.put(self.cur, lba, data)
        (self._durable if self.mode == "write_through" else self.pending.append)((lba, data))

    def _durable(self, item):
        M.put(self.dur, *item)

    def flush(self):
        self.events.append({"op": "flush"})
        if self.inject and self.inject[0] == "flush" and self.inject[1] == self.nf:
            self.fired = True
            raise Cut
        self.nf += 1
        for item in self.pending:
            self._durable(item)
        self.pending = []

    def settle(self):
        """At the cut: pending write i survives iff bit (n-1-i) of (ordinal mod 2^n) is set; torn block last."""
        n = len(self.pending)
        pick = self.ordinal % (1 << n) if n < 63 else self.ordinal
        for i, item in enumerate(self.pending):
            if (pick >> (n - 1 - i)) & 1:
                self._durable(item)
        if self.torn:
            M.put(self.dur, *self.torn)
        return bytes(self.dur)


# ------------------------------------------------------------------ minimal spec engine (rows 1-3)

def slots(img):
    return {n: M.parse_slot(M.block(img, lba, F.SLOT_BLOCKS)) for n, lba in M.SLOT_LBA.items()}


def live(slot_map, side):
    names = ("A0", "A1") if side == "A" else ("B0", "B1")
    valid = [(n, slot_map[n]) for n in names if slot_map[n]]
    if not valid or (len(valid) == 2 and valid[0][1]["sequence"] == valid[1][1]["sequence"]):
        return None
    return max(valid, key=lambda v: v[1]["sequence"])


def sb_fields(img):
    sb = M.block(img, 0)
    return {"gen": struct.unpack_from("<I", sb, 12)[0], "high": struct.unpack_from("<I", sb, 56)[0],
            "stage": struct.unpack_from("<I", sb, 124)[0]}


def headroom(cs, gen, seq_needed, gen_needed, mutant):
    if mutant == "zero_needed_consults_counters":
        return cs + seq_needed <= M.MAX_WRITABLE and gen + gen_needed <= M.MAX_WRITABLE
    ok = True
    if seq_needed:
        ok &= cs + seq_needed <= M.MAX_WRITABLE
    if gen_needed:
        ok &= gen + gen_needed <= M.MAX_WRITABLE
    return ok


def stage_clear(dev, sb):
    new = F.build_superblock(generation=sb["gen"] + 1, a_high_water=sb["high"])
    dev.write(F.LBA_MIRROR, new)
    dev.flush()
    dev.write(F.LBA_PRIMARY, new)
    dev.flush()


def commit(dev, slot_name, side, seq, entries):
    raw = F.build_index(side, seq & 0xFFFFFFFF, entries)   # a u32 engine wraps; only a defect gets here
    for k in range(1, 1 + -(-12 * len(entries) // M.BLOCK)):
        dev.write(M.SLOT_LBA[slot_name] + k, raw[k * M.BLOCK:(k + 1) * M.BLOCK])
    dev.flush()
    dev.write(M.SLOT_LBA[slot_name], raw[:M.BLOCK])
    dev.flush()


def respool_plan(img, a_entries, b_entries, high, mutant):
    used = M.chunks_of(a_entries) | M.chunks_of(b_entries)
    total = sum(e[2] for e in b_entries)
    length = -(-total // M.N)
    if mutant == "respool_pass1_onto_live_b" and any(c >= high for c in M.chunks_of(b_entries)):
        d1 = min(c for c in M.chunks_of(b_entries) if c >= high)
    else:
        d1 = next(d for d in range(high, F.TOTAL_CHUNKS - length + 1) if not set(range(d, d + length)) & used)
    used2 = M.chunks_of(a_entries) | set(range(d1, d1 + length))
    d2 = next((d for d in range(high, d1) if not set(range(d, d + length)) & used2 and d + length <= d1 + length),
              None)
    return d1, d2, total


def copy_pass(dev, src_entries, dest, total, slot_name, seq, mutant):
    data = M.render(bytes(dev.cur), src_entries)
    base = F.LBA_CHUNK_BASE + dest * F.CHUNK_BLOCKS
    if mutant == "respool_commits_before_copying":      # violates tapefs §8 steps 1-2 before 3-5
        commit(dev, slot_name, 1, seq, [(dest, 0, total)])
    for k in range(-(-len(data) // M.BLOCK)):
        dev.write(base + k, data[k * M.BLOCK:(k + 1) * M.BLOCK].ljust(M.BLOCK, b"\0"))
    dev.flush()
    if mutant != "respool_commits_before_copying":
        commit(dev, slot_name, 1, seq, [(dest, 0, total)])
    return [(dest, 0, total)]


def run_call(dev, fn, mutant):
    img = bytes(dev.cur)
    sm, sb = slots(img), sb_fields(img)
    cs = max(s["sequence"] for s in sm.values() if s)
    stage = sb["stage"] == 1
    a = live(sm, "A")
    b = live(sm, "B")
    if fn == "tape_respool":
        if b is None:
            return {"fn": fn, "result": "TAPE_ERR_NO_VALID_INDEX"}
        if not b[1]["entries"]:
            if not headroom(cs, sb["gen"], 0, 0, mutant):
                return {"fn": fn, "result": "TAPE_ERR_SEQUENCE_EXHAUSTED"}
            return {"fn": fn, "result": "TAPE_OK", "more_work": False}
        d1, d2, total = respool_plan(img, a[1]["entries"], b[1]["entries"], sb["high"], mutant)
        seq_needed = 2 if d2 is not None else 1
        gen_needed = 1 if stage and mutant != "stage_clear_generation_not_counted" else 0
        if mutant == "respool_ignores_sequence_headroom":
            seq_needed = 0
        if stage and mutant == "stage_clear_before_headroom":
            stage_clear(dev, sb)
            stage = False
        if not headroom(cs, sb["gen"], seq_needed, gen_needed, mutant):
            if d2 is not None and headroom(cs, sb["gen"], 1, gen_needed, mutant):
                d2 = None               # tapefs §9.4: pass 2 skipped when headroom allows only one commit
            else:
                return {"fn": fn, "result": "TAPE_ERR_SEQUENCE_EXHAUSTED"}
        if stage:
            stage_clear(dev, sb)
        inactive = "B1" if b[0] == "B0" else "B0"
        layout = copy_pass(dev, b[1]["entries"], d1, total, inactive, cs + 1, mutant)
        if d2 is not None:
            copy_pass(dev, layout, d2, total, b[0], cs + 2, mutant)
        return {"fn": fn, "result": "TAPE_OK", "more_work": False}
    seq_needed = 1
    gen_needed = 1 if stage and mutant != "stage_clear_generation_not_counted" else 0
    if mutant == "reset_b_ignores_sequence_headroom" and fn == "tape_reset_side_b":
        seq_needed = 0
    if stage and mutant == "stage_clear_before_headroom":
        stage_clear(dev, sb)
        stage = False
    if not headroom(cs, sb["gen"], seq_needed, gen_needed, mutant):
        return {"fn": fn, "result": "TAPE_ERR_SEQUENCE_EXHAUSTED"}
    if stage:
        stage_clear(dev, sb)
    if fn == "tape_reset_side_b":
        dest = "B0" if b is None else ("B1" if b[0] == "B0" else "B0")
        commit(dev, dest, 1, cs + 1, a[1]["entries"])
    return {"fn": fn, "result": "TAPE_OK"}


def mount_view(img, side):
    sm = slots(img)
    got = live(sm, side)
    if got is None:
        return {"result": "TAPE_ERR_NO_VALID_INDEX"}
    entries = got[1]["entries"]
    return {"result": "TAPE_OK", "entries": entries,
            "info": {"total_frames": sum(e[2] for e in entries), "entry_count": len(entries),
                     "side_b_valid": live(sm, "B") is not None},
            "pcm_sha256": M.sha(M.render(img, entries))}


RAW_NAMES = {"P": (F.LBA_PRIMARY, 1), "M": (F.LBA_MIRROR, 1), "A0": (F.LBA_A0, 2), "A1": (F.LBA_A1, 2),
             "B0": (F.LBA_B0, 2), "B1": (F.LBA_B1, 2)}


def contract(case, mutant):
    if case["row"] == 1:
        spec, side, fn, _, _ = M.ROW1[case["case"]]
        image = M.row1_image(spec)
    else:
        args, _, _ = M.ROW2[case["case"]]
        side, fn, image = "B", "tape_respool", M.row2_image(args)
    dev = Device(image)
    call = run_call(dev, fn, mutant)
    after = bytes(dev.cur)
    return {"case": case["case"], "image_sha256_before": M.sha(image),
            "mount": {"fn": "tape_mount", "side": side, "result": "TAPE_OK"}, "call": call,
            "events": [e for e in dev.events if e["op"] != "read"], "image_sha256_after": M.sha(after),
            "after_raw": {k: M.block(after, lba, n).hex() for k, (lba, n) in RAW_NAMES.items()}}


def respool_to_end(dev, mutant):
    try:
        run_call(dev, "tape_respool", mutant)
    except Cut:
        pass


def row3(case, mutant):
    fid = case["fixture"]
    image = M.row3_image(fid)
    pre_b, pre_a = mount_view(image, "B"), mount_view(image, "A")
    clean = Device(image)
    run_call(clean, "tape_respool", mutant)
    post = mount_view(bytes(clean.cur), "B")
    events = [e for e in clean.events if e["op"] != "read"]
    crashes = []
    for ordinal, (mode, inject, prefix_len) in enumerate(O.row3_injections(events)):
        dev = Device(image, mode, inject, ordinal)
        respool_to_end(dev, mutant)
        durable = dev.settle()
        b, a = mount_view(durable, "B"), mount_view(durable, "A")
        crashes.append({"mode": mode, "inject": inject, "fired": dev.fired, "prefix_len": prefix_len,
                        "remount_B": {k: b[k] for k in ("result", "info", "pcm_sha256") if k in b},
                        "remount_A": {"result": a["result"], "pcm_sha256": a.get("pcm_sha256")}})
    return {"fixture": fid, "image_sha256": M.sha(image),
            "pre": {"mount_B": {k: pre_b[k] for k in ("result", "info", "pcm_sha256")},
                    "a_pcm_sha256": pre_a["pcm_sha256"]},
            "clean": {"calls": [{"fn": "tape_respool", "block_budget": M.RS_BUDGET, "result": "TAPE_OK",
                                 "more_work": False}],
                      "events": events,
                      "post_mount_B": {k: post[k] for k in ("result", "info", "pcm_sha256")}},
            "crashes": crashes}


def _dm_mount(img, side, writable):
    exp = O.mount_expectation(img, side, writable)
    out = {"result": exp["results"][0], "repair_events": exp.get("repair_events", [])}
    if out["result"] == "TAPE_OK":
        out["info"] = dict(exp["info"])
        if "pcm_sha256" in exp:
            out["pcm_sha256"] = exp["pcm_sha256"]
    return out


def row4(case, mutant):
    rep = O._rep(case["shape"], case["first_mode"], tuple(case["first_inject"]))
    crashed = rep["crashed"]
    ops = DM.dup_ops(crashed)
    if mutant == "rerun_skips_barrier" and (DM.sb_valid(crashed["P"]) or DM.sb_valid(crashed["M"])):
        ops = ops[4:]
    if mutant == "rerun_final_keeps_old_uuid":
        old = crashed["P"] if DM.sb_valid(crashed["P"]) else crashed["M"]
        if DM.sb_valid(old):
            final = bytearray(ops[-2][2])
            final[20:36] = old[20:36]
            struct.pack_into("<I", final, 508, DM.crc32(bytes(final[:508])))
            ops = ops[:-4] + [("w", "M", bytes(final)), ("f",), ("w", "P", bytes(final)), ("f",)]
    inject = tuple(case["inject"])
    nw, nf = sum(o[0] == "w" for o in ops), sum(o[0] == "f" for o in ops)
    fired = (inject[0] == "write" and inject[1] < nw) or (inject[0] == "flush" and inject[1] < nf)
    if fired:
        images = DM.possible_images(crashed, ops, inject, case["mode"])
        img = images[case["index"] % len(images)]
        trace = O.dm_trace_sha256(DM.prefix(ops, inject))
    else:
        img, trace = DM.apply(crashed, ops), O.dm_trace_sha256(ops)
    src = DM.sha(b"synthetic 128-frame source device")
    return {"shape": case["shape"], "first_mode": case["first_mode"], "first_inject": case["first_inject"],
            "mode": case["mode"], "inject": case["inject"], "first_durable_sha256": DM.digest(crashed),
            "source_sha256_before": src, "source_sha256_after": src, "fired": fired, "trace_sha256": trace,
            "durable_sha256": DM.digest(img),
            "ro_A": _dm_mount(img, "A", False), "rw_A": _dm_mount(img, "A", True), "rw_B": _dm_mount(img, "B", True)}


def observation(case, mutant=None):
    if mutant and MUTANTS[mutant] != case["row"]:
        mutant = None
    body = (contract if case["row"] in (1, 2) else row3 if case["row"] == 3 else row4)(case, mutant)
    return {"schema": O.SCHEMA, "index": case["index"], "row": case["row"], "kind": case["kind"], **body}


def lines(mutant=None, rows=None):
    for case in O.iter_cases():
        if rows and case["row"] not in rows:
            continue
        yield json.dumps(observation(case, mutant), sort_keys=True, separators=(",", ":"))


if __name__ == "__main__":
    raw = "".join(line + "\n" for line in lines()).encode("utf-8")
    sys.stdout.buffer.write(gzip.compress(raw, compresslevel=9, mtime=0))
