#!/usr/bin/env python3
"""Verifier-owned fixtures for the WP-12/WP-12a R53 closure gaps.

Metadata builders are imported from two already-accepted verifier packages and
pinned by Git blob identity (CRLF-normalised) so a silent edit goes red.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import struct
import sys
from array import array
from pathlib import Path

HERE = Path(__file__).resolve().parent
PINNED = {
    "respool_draft8/oracle.py": "3c63f190e87915f410a199128e1a08590b8ee6bd",
    "promote_draft8/fixture.py": "51c676bf4d788216d239da071c0679c600a811ce",
}
SPEC_SHA256 = {
    "tapefs": "3f08ec6d11070c1e10edcf7cacbcd93ff694257f042b71b53200e158621fa19d",
    "engine_api": "383817326705d98bda6a96480f8185e911113927d35c53c02d1458adb72baea6",
    "acceptance": "ae77d13c868fd39a882b5bd3ebf459557792432ce895bc7bf58be7fc2c33825d",
}


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _load(rel: str, name: str):
    path = HERE.parent / rel
    actual = git_blob_sha(path)
    if actual != PINNED[rel]:
        raise AssertionError(f"pinned verifier dependency drifted: {rel} {actual}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


RS = _load("respool_draft8/oracle.py", "wp12r53_respool_base")
PF = _load("promote_draft8/fixture.py", "wp12r53_promote_base")

CF = RS.CF
FRAME_BYTES = 4
LBA_B1 = RS.LBA_B1


def frame_bytes(chunk: int, frame: int) -> bytes:
    """Stored s16le stereo frame at physical (chunk, frame); unique per coordinate."""
    left = (chunk * 7919 + frame * 31 + 1) & 0xFFFF
    right = (chunk * 104729 + frame * 17 + 12345) & 0xFFFF
    return struct.pack("<HH", left, right)


def chunk_audio(chunk: int) -> bytes:
    out = array("H")
    for frame in range(CF):
        out.append((chunk * 7919 + frame * 31 + 1) & 0xFFFF)
        out.append((chunk * 104729 + frame * 17 + 12345) & 0xFFFF)
    if out.itemsize != 2:
        raise AssertionError("array('H') is not 16-bit")
    if sys.byteorder != "little":
        out.byteswap()
    return out.tobytes()


# Render-identity fixtures: (H, live Side-B entries).  Entries are
# (first_chunk, start_frame, frame_count) exactly as TapeFS §5.2 stores them.
RENDER_FIXTURES = {
    "RENDER-TWOPASS": (10, ((10, 0, 2 * CF),)),
    "RENDER-DECLINE": (10, tuple((x, 0, 1) for x in range(11, 21))),
    "RENDER-FRAGMENTED": (10, ((15, 7, 20), (12, CF - 3, 5), (13, 100, 3))),
}


def render_media(case_id: str):
    high, entries = RENDER_FIXTURES[case_id]
    return RS.media(high, list(entries))


def referenced_chunks(entries) -> list[int]:
    return sorted(RS.entry_chunks(entries))


def logical_pcm(entries) -> bytes:
    """Expected render of the whole side at 1.0x, derived only from entries."""
    parts = []
    for first, start, count in entries:
        for j in range(count):
            position = start + j
            parts.append(frame_bytes(first + position // CF, position % CF))
    return b"".join(parts)


def media_metadata(m) -> bytes:
    return m.primary + m.mirror + b"".join(m.slots)


def promote_metadata(scenario: str = "fresh_alloc_full") -> bytes:
    initial = PF.scenario_initial(scenario)
    blocks, total = initial["blocks"], initial["total_chunks"]
    out = [blocks[0], blocks[PF.mirror_lba(total)]]
    for base in (PF.LBA_A0, PF.LBA_A1, PF.LBA_B0, PF.LBA_B1):
        out.append(b"".join(blocks.get(base + i, PF.ZERO_BLOCK) for i in range(128)))
    return b"".join(out)


def respool_fault_media():
    return RS.media(10, [(10, 0, 2 * CF)])


def fixture_metadata(fixture: str) -> bytes:
    if fixture in RENDER_FIXTURES:
        return media_metadata(render_media(fixture))
    if fixture == "respool_v3_003":
        return media_metadata(respool_fault_media())
    if fixture == "promote_fresh_alloc_full":
        return promote_metadata("fresh_alloc_full")
    raise KeyError(fixture)


def fixture_metadata_sha256(fixture: str) -> str:
    return hashlib.sha256(fixture_metadata(fixture)).hexdigest()


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
