#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "tests" / "respool_full_draft8"
sys.path.insert(0, str(PKG))

from fixture import (  # noqa: E402
    BASE, pattern_block, pattern_bytes, transaction_media,
)

BLOCK = BASE.BLOCK
CHUNK_BYTES = BASE.CHUNK_BYTES
BPC = BASE.BLOCKS_PER_CHUNK
CHUNK_BASE = BASE.LBA_CHUNK_BASE
SLOT_LBAS = (BASE.LBA_A0, BASE.LBA_A1, BASE.LBA_B0, BASE.LBA_B1)


def _put(image: bytearray, lba: int, data: bytes) -> None:
    off = lba * BLOCK
    image[off:off + len(data)] = data


def build_raw_image(fixture_name: str, pass_name: str, path: Path) -> None:
    probe_case = {
        "case_index": 0,
        "fixture": fixture_name,
        "pass": pass_name,
        "mode": "flush_required",
        "target": "chunk_copy",
        "injection": {"kind": "before_write", "write_ordinal": 0, "landed_bytes": 0},
    }
    pre, _ = transaction_media(probe_case)
    image = bytearray(pre.blocks * BLOCK)
    _put(image, 0, pre.primary)
    _put(image, pre.blocks - 1, pre.mirror)
    for lba, slot in zip(SLOT_LBAS, pre.slots):
        _put(image, lba, slot)

    # Verifier-designated Side-A control bytes. Side A's fixture references
    # chunk 0 frame 0, so its first block is the independent control region.
    _put(image, CHUNK_BASE, pattern_bytes(77, BLOCK))

    if fixture_name == "v3_003":
        timeline = pattern_bytes(10, 2 * CHUNK_BYTES)
        _put(image, CHUNK_BASE + 10 * BPC, timeline)
        if pass_name == "pass1":
            # Verifier-owned unallocated destination preimage.
            dest = b"".join(pattern_block(90, i) for i in range(2 * BPC))
            _put(image, CHUNK_BASE + 12 * BPC, dest)
        elif pass_name == "pass2":
            # Pass 2 begins from the committed pass-1 durable image. The sole
            # live copy at [12,14) is bit-identical to the original timeline.
            _put(image, CHUNK_BASE + 12 * BPC, timeline)
        else:
            raise ValueError("unknown v3_003 pass")
    elif fixture_name == "no_lower_run" and pass_name == "pass1":
        logical = pattern_bytes(31, 40)
        for i in range(10):
            _put(image, CHUNK_BASE + (11 + i) * BPC, logical[i * 4:(i + 1) * 4])
        _put(image, CHUNK_BASE + 10 * BPC, pattern_block(91, 0))
    else:
        raise ValueError("unknown full-respool fixture/pass")

    path.write_bytes(image)
