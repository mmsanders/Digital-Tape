#!/usr/bin/env python3
"""Synthetic public-observation emitter for the WP-08 mapped-run rows. Verifier self-test only.

A small spec-following playback engine over the real fixture image: mount parses the selected slot from raw
bytes, service fills a ring by reading whole blocks (at most block_budget per call) in the rate's direction,
and render follows engine-api §6.2/§6.3 at +/-1.0x from the ring only. Mutants model the defects each row must
catch; none of them is visible to an accepted WP-08 fixture (start_frame 0, one run per chunk, ascending
chunks, Side B only).
"""
from __future__ import annotations

import gzip
import json
import struct
import sys

import oracle as O
import rows as R

C69, FINAL, N, BLOCK = R.C69, R.FINAL, R.N, R.BLOCK
FPB = BLOCK // 4                      # frames per block
WINDOW = 64                            # frames the synthetic ring keeps ahead of the playhead

MUTANTS = {
    "ignore_start_frame": "every run read from frame 0 of its first chunk",
    "chunk_crossing_wraps": "a run that reaches the end of a chunk wraps within that chunk",
    "sort_entries_by_physical": "entries put in physical order (an in-place disjointness sort)",
    "side_a_plays_b_index": "a Side-A mount plays the Side-B entry array",
    "reverse_crossing_stale": "reverse play into the previous chunk of a run repeats the last frame",
    "render_reads_device": "render performs one block read",
}


class Engine:
    def __init__(self, image, mutant):
        self.img, self.mutant = image, mutant
        self.events = []

    def _read(self, lba, count=1):
        self.events.append({"op": "read", "lba": lba, "count": count, "rc": 0})
        return self.img[lba * BLOCK:(lba + count) * BLOCK]

    def _slot(self, name):
        lba = R.pins.FINAL.SLOT_LBA[name]
        head = self._read(lba)
        count = struct.unpack_from("<I", head, 16)[0] if head[:8] == C69.MAGIC_IDX else 0
        raw = head + (self._read(lba + 1, -(-count * 12 // BLOCK)) if count else b"")
        raw += b"\0" * max(0, 2 * BLOCK - len(raw))
        return FINAL.parse_slot(raw)

    def mount(self, side):
        self._read(C69.LBA_PRIMARY)
        self._read(C69.LBA_MIRROR)
        slots = {n: self._slot(n) for n in ("A0", "A1", "B0", "B1")}
        pick = lambda a, b: max((s for s in (slots[a], slots[b]) if s), key=lambda s: s["sequence"])
        live = {"A": pick("A0", "A1"), "B": pick("B0", "B1")}
        use = "B" if (side == "A" and self.mutant == "side_a_plays_b_index") else side
        self.entries = [tuple(e) for e in live[use]["entries"]]
        if self.mutant == "sort_entries_by_physical":
            self.entries.sort(key=lambda e: e[0] * N + e[1])
        self.total = sum(e[2] for e in self.entries)
        self.pos, self.rate, self.at_start, self.at_end, self.ring = 0, 0, False, False, {}

    def where(self, t):
        for (first, start, n), s in zip(self.entries, R.run_starts(self.entries)):
            if s <= t < s + n:
                if self.mutant == "ignore_start_frame":
                    start = 0
                p = start + (t - s)
                if self.mutant == "chunk_crossing_wraps":
                    return first, p % N
                return first + p // N, p % N
        raise IndexError(t)

    def seek(self, frame):
        self.pos = min(frame, self.total)
        self.at_start = self.at_end = False
        self.ring = {}

    def set_rate(self, rate):
        self.rate, self.at_start, self.at_end = rate, False, False
        self.ring = {}

    def _wanted(self):
        if self.rate > 0:
            return [t for t in range(self.pos, min(self.total, self.pos + WINDOW))]
        p = self.total - 1 if self.pos >= self.total else self.pos
        return [t for t in range(p, max(-1, p - WINDOW), -1)]

    def service(self, budget):
        missing = [t for t in self._wanted() if t not in self.ring]
        blocks = []
        for t in missing:
            c, f = self.where(t)
            lba = C69.LBA_CHUNK_BASE + c * C69.CHUNK_BLOCKS + f // FPB
            if lba not in blocks:
                blocks.append(lba)
        for lba in blocks[:budget]:
            data = self._read(lba)
            for t in missing:
                c, f = self.where(t)
                if C69.LBA_CHUNK_BASE + c * C69.CHUNK_BLOCKS + f // FPB == lba:
                    o = (f % FPB) * 4
                    self.ring[t] = data[o:o + 4]
        return len(blocks) > budget

    def render(self, frames):
        if self.mutant == "render_reads_device":
            self._read(C69.LBA_CHUNK_BASE)
        out, step = [], (1 if self.rate > 0 else -1)
        if step < 0 and self.pos >= self.total:
            self.pos = self.total - 1
        while len(out) < frames:
            if step > 0 and self.pos >= self.total:
                self.at_end = True
                break
            if step < 0 and self.at_start:
                break
            if self.pos not in self.ring:
                return "TAPE_ERR_UNDERRUN", out
            frame = self.ring[self.pos]
            if (self.mutant == "reverse_crossing_stale" and step < 0 and out and self.pos + 1 < self.total
                    and self.where(self.pos)[0] != self.where(self.pos + 1)[0]
                    and self._same_entry(self.pos, self.pos + 1)):
                frame = out[-1]
            out.append(frame)
            if step > 0:
                self.pos += 1
                if self.pos >= self.total:
                    self.pos, self.at_end = self.total, True
            elif self.pos == 0:
                self.at_start = True
            else:
                self.pos -= 1
        return "TAPE_OK", out

    def _same_entry(self, a, b):
        starts = R.run_starts(self.entries)
        idx = lambda t: max(i for i, s in enumerate(starts) if s <= t)
        return idx(a) == idx(b)


def run(case, mutant=None):
    eng = Engine(R.image(), mutant)
    calls = []

    def call(fn, body, **fields):
        eng.events = []
        out = body() or {}
        calls.append({"fn": fn, **fields, **out, "events": eng.events})

    call("tape_mount", lambda: (eng.mount(case["side"]), {"result": "TAPE_OK"})[1], side=case["side"],
         resume_frame=0, warm=None)

    def service_loop():
        while True:
            holder = {}

            def body():
                more = eng.service(R.SERVICE_BUDGET)
                holder["more"] = more
                return {"result": "TAPE_OK", "more_work": more}
            call("tape_service", body, block_budget=R.SERVICE_BUDGET)
            if not holder["more"]:
                return

    def render_tell_status(n):
        def body():
            res, out = eng.render(n)
            return {"result": res, "rendered": len(out), "pcm_hex": b"".join(out).hex()}
        call("tape_render", body, requested=n)
        call("tape_tell", lambda: {"result": "TAPE_OK", "frame": eng.pos})
        call("tape_status", lambda: {"result": "TAPE_OK", "at_start": eng.at_start, "at_end": eng.at_end})
        return calls[-3]["rendered"]

    if case["row"] == 1:
        call("tape_seek", lambda: (eng.seek(case["seek"]), {"result": "TAPE_OK"})[1], frame=case["seek"])
        call("tape_set_rate", lambda: (eng.set_rate(case["rate"]), {"result": "TAPE_OK"})[1], rate=case["rate"])
        service_loop()
        render_tell_status(R.ROW1_RENDER)
    else:
        call("tape_seek", lambda: (eng.seek(R.TOTAL), {"result": "TAPE_OK"})[1], frame=R.TOTAL)
        call("tape_set_rate", lambda: (eng.set_rate(-R.ONE), {"result": "TAPE_OK"})[1], rate=-R.ONE)
        for _ in range(1000):
            service_loop()
            if render_tell_status(R.ROW2_RENDER) < R.ROW2_RENDER:
                break
    obs = {"schema": O.SCHEMA, "index": case["index"], "row": case["row"], "kind": case["kind"],
           "side": case["side"], "image_sha256": O.image_sha(), "block_count": O.BLOCK_COUNT, "calls": calls}
    for k in ("crossing", "seek", "rate"):
        if k in case:
            obs[k] = case[k]
    return obs


def observation(case, mutant=None):
    return run(case, mutant)


def lines(mutant=None):
    for case in O.iter_cases():
        yield json.dumps(observation(case, mutant), sort_keys=True, separators=(",", ":"))


if __name__ == "__main__":
    raw = "".join(line + "\n" for line in lines()).encode()
    sys.stdout.buffer.write(gzip.compress(raw, compresslevel=9, mtime=0))
