#!/usr/bin/env python3
"""Fixtures and expectations for the #130 rows (Verification #130, DRAFT-9).

Row 1  WP09.overdub.full_scale_saturation   acceptance WP-09; engine-api §8 overdub clamp, §11 overdub at end.
Row 2  WP10.respool_render.trace_floor     V-R55-01 (#128): the tapefs §8 / §9.4 floor of the #118 row-3
                                           clean re-spool trace, so an adapter cannot shrink the enumeration.
"""
from __future__ import annotations

import functools
import hashlib
import struct

import pins

FINAL, C69 = pins.FINAL, pins.C69
BLOCK = C69.BLOCK
ONE = 0x10000

ROW1 = "WP09.overdub.full_scale_saturation"
ROW2 = "WP10.respool_render.trace_floor"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sat16(v: int) -> int:
    """engine-api §8, verbatim semantics: int32 sum, clamp to [-32768, 32767]."""
    return 32767 if v > 32767 else -32768 if v < -32768 else v


# ------------------------------------------------------------------ row 1: full-scale overdub

# (existing, incoming) pairs. Every pair the criterion names is here, on both signs, plus the one-off-the-rail
# neighbours that separate a clamp from a wrap, an off-by-one rail and a one-sided clamp.
COMBOS = (
    (32767, 32767), (-32768, -32768),    # full scale against full scale: the criterion's case, both signs
    (32767, 1), (-32768, -1),            # one LSB past each rail
    (32766, 1), (-32767, -1),            # land exactly on each rail without saturating
    (32767, -32768), (-32768, 32767),    # opposite full scale: -1, no saturation
    (16384, 16384), (-16384, -16385),    # overflow from mid-scale
    (32000, 800), (-32000, -800),
    (1, -1), (0, 0), (-1, -32768), (32767, 0),
)
PERIOD = len(COMBOS)                     # 16
BASE_FRAMES = 3 * PERIOD                 # Side B: one run {2, 0, 48}
BASE_ENTRY = (2, 0, BASE_FRAMES)
HIGH = 2
INPUT_FRAMES = PERIOD
POSITIONS = {"start": 0, "middle": PERIOD, "straddle_end": BASE_FRAMES - PERIOD // 2}
SERVICE_BUDGET = 64
RENDER = 32


def base_frame(p):
    """Left channel walks COMBOS forward, right channel walks them backwards with the roles swapped."""
    j = p % PERIOD
    return COMBOS[j][0], COMBOS[PERIOD - 1 - j][1]


def input_frames(at):
    out = []
    for k in range(INPUT_FRAMES):
        j = (at + k) % PERIOD
        out.append((COMBOS[j][1], COMBOS[PERIOD - 1 - j][0]))
    return out


def pcm(frames):
    return b"".join(struct.pack("<hh", *f) for f in frames)


def expected_timeline(at):
    """tapefs §9.1 overdub; engine-api §8 clamp; §11 'overdub at end: append, input passes through unchanged'."""
    base = [base_frame(p) for p in range(BASE_FRAMES)]
    out = list(base)
    for k, f in enumerate(input_frames(at)):
        p = at + k
        if p < len(base):
            out[p] = (sat16(base[p][0] + f[0]), sat16(base[p][1] + f[1]))
        else:
            out.append(f)
    return out


@functools.lru_cache(maxsize=None)
def overdub_image() -> bytes:
    img = bytearray(FINAL.cartridge(generation=10, high=HIGH,
                                    slots=[("A0", 0, 1, []), ("B0", 1, 2, [BASE_ENTRY])], audio_chunks=()))
    off = (C69.LBA_CHUNK_BASE + BASE_ENTRY[0] * C69.CHUNK_BLOCKS) * BLOCK
    data = pcm(base_frame(p) for p in range(BASE_FRAMES))
    img[off:off + len(data)] = data
    return bytes(img)


# ------------------------------------------------------------------ row 2: V-R55-01 trace floor

FIXTURES = tuple(FINAL.ROW3)                       # RS-TWOPASS ... RS-ONE-COMMIT, the #118 order
# tapefs §9.4: pass 2 runs iff a lawful strictly-lower run exists after pass 1; §4.5 headroom can skip it.
# RS-REFERENCES-A admits one or two because pass-1 placement is not pinned (#115) - see #128 V-R55-01.
COMMITS_ALLOWED = {"RS-TWOPASS": (2,), "RS-REFERENCES-A": (1, 2), "RS-FRAGMENTED": (2,),
                   "RS-CHUNK-CROSSING": (2,), "RS-ONE-COMMIT": (1,)}
B_SLOTS = {"B0": C69.LBA_B0, "B1": C69.LBA_B1}


def fixture_frames(fid):
    return sum(e[2] for e in FINAL.ROW3[fid][1])


def data_floor_blocks(fid):
    """tapefs §8 step 1 for a compacted single entry {S, 0, T}: ceil(T * 4 / 512) chunk blocks."""
    return -(-fixture_frames(fid) * 4 // BLOCK)


def _validate():
    assert set(COMMITS_ALLOWED) == set(FIXTURES)
    for a, b in COMBOS:
        assert -32768 <= a <= 32767 and -32768 <= b <= 32767
    for at in POSITIONS.values():
        exp = expected_timeline(at)
        assert all(-32768 <= s <= 32767 for f in exp for s in f)
    # the criterion's two cells really saturate in the start and middle cases, on both channels
    for at in (POSITIONS["start"], POSITIONS["middle"]):
        exp = expected_timeline(at)
        assert exp[at][0] == 32767 and exp[at + 1][0] == -32768
        assert exp[at + PERIOD - 1][1] == 32767 and exp[at + PERIOD - 2][1] == -32768


_validate()
