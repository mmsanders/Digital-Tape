#!/usr/bin/env python3
"""Fixture and expectations for the WP-08 mapped-run rows (Verification #129, DRAFT-9).

One C69-layout cartridge (5 chunks, 12 s; tapefs §4/§5 byte layout of the accepted campaign) carries the same
five physical runs on both sides, in different timeline orders. Every run exercises a mapping rule that no
accepted WP-08 fixture reaches, because every accepted WP-08 fixture put each run at start_frame 0 of its own
chunk, in ascending chunk order, on Side B only:

  E0 {3, 1000, 300}    non-zero, block-unaligned start; spans four blocks
  E1 {3,  100,  50}    shares chunk 3 with E0 at a LOWER offset (splice-trim shape, §5.1)
  E2 {1, 131000, 200}  spans the chunk 1 -> 2 boundary inside one run (§5.1 "frames lie contiguously")
  E3 {4,  127,    3}   starts on the last frame of a block
  E4 {0,    5,    6}   lowest chunk, odd offset

a_high_water = 5, so every run is Side-A owned (§5.2 Side-A bound) and Side B references them (Rule 3).
Audio is the #118 coordinate-unique pattern in every frame of every chunk, so any wrong mapping reads a
different, non-zero frame.
"""
from __future__ import annotations

import functools
import hashlib

import pins

FINAL, C69 = pins.FINAL, pins.C69
N = C69.CHUNK_FRAMES
BLOCK = C69.BLOCK
ONE = 0x10000                       # 1.0x in Q16.16
HIGH = 5
E0, E1, E2, E3, E4 = (3, 1000, 300), (3, 100, 50), (1, 131000, 200), (4, 127, 3), (0, 5, 6)
SIDES = {
    "A": {"slot": "A0", "side": 0, "sequence": 1, "entries": (E2, E0, E4, E3, E1)},
    "B": {"slot": "B0", "side": 1, "sequence": 2, "entries": (E0, E1, E2, E3, E4)},
}
TOTAL = 559
OFFSETS = (-1, 0, 1)
RATES = (ONE, -ONE)
ROW1_RENDER = 4
ROW2_RENDER = 32
SERVICE_BUDGET = 64

ROW1 = "WP08.seek_boundary.mapped_runs"
ROW2 = "WP08.reverse_end.mapped_timeline"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_starts(entries):
    out, pos = [], 0
    for e in entries:
        out.append(pos)
        pos += e[2]
    return out


def crossings(side):
    """Every interior run boundary, plus each intra-run chunk crossing (timeline frame of the first frame in
    the next chunk). Both are places where the frame -> (chunk, frame) mapping changes discontinuously."""
    entries = SIDES[side]["entries"]
    starts = run_starts(entries)
    out = set(starts[1:])
    for (first, start, n), s in zip(entries, starts):
        k = N - start
        while k < n:
            out.add(s + k)
            k += N
    return tuple(sorted(out))


def physical(entries, t):
    """tapefs §5.1: timeline frame t -> (chunk, frame in chunk)."""
    for (first, start, n), s in zip(entries, run_starts(entries)):
        if s <= t < s + n:
            p = start + (t - s)
            return first + p // N, p % N
    raise IndexError(t)


def timeline(side):
    """The side's frames in timeline order, from the audio pattern alone (never from an image or engine)."""
    entries = SIDES[side]["entries"]
    return [FINAL.frame_bytes(*physical(entries, t)) for t in range(TOTAL)]


@functools.lru_cache(maxsize=None)
def image() -> bytes:
    slots = [(v["slot"], v["side"], v["sequence"], list(v["entries"])) for v in SIDES.values()]
    return FINAL.cartridge(generation=10, high=HIGH, slots=slots, audio_chunks=range(C69.TOTAL_CHUNKS))


def _validate():
    """The fixture is §5.2-valid on both sides; checked here so a builder change cannot go unnoticed."""
    assert C69.TOTAL_CHUNKS == 5 and HIGH <= C69.TOTAL_CHUNKS
    for side, v in SIDES.items():
        es = v["entries"]
        assert sum(e[2] for e in es) == TOTAL
        iv = sorted((f * N + s, f * N + s + n) for f, s, n in es)
        assert all(a[1] <= b[0] for a, b in zip(iv, iv[1:])), "intervals overlap"
        for f, s, n in es:
            last = f + (s + n - 1) // N
            assert n >= 1 and s < N and last < C69.TOTAL_CHUNKS and last < HIGH
        assert sorted(es) == sorted(SIDES["A"]["entries"])
    assert crossings("B") == (300, 350, 422, 550, 553)
    assert crossings("A") == (72, 200, 500, 506, 509)
    for side in SIDES:
        tl = timeline(side)
        assert len(set(tl)) == TOTAL and all(f != b"\0\0\0\0" for f in tl)


_validate()
