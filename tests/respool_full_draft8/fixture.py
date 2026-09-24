#!/usr/bin/env python3
"""Verifier-owned respool fixtures and pinned dependency on the narrow WP-12 oracle."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import struct
import sys
import zlib

HERE = Path(__file__).resolve().parent
BASE_PATH = HERE.parent / "respool_draft8" / "oracle.py"
BASE_ORACLE_BLOB_SHA = "3c63f190e87915f410a199128e1a08590b8ee6bd"

FROZEN_PRODUCT = "45c08bd7e25aeb6ca858faf4d30d139999f8dbd7"
FROZEN_VERIFICATION = "fe432ffac622b9d9e9c68e566d2cb9881f2aee62"
SPEC_HASHES = {
    "tapefs-v1.md": "3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb",
    "engine-api.md": "537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1",
    "acceptance.md": "7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7",
}

def _git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()

if _git_blob_sha(BASE_PATH) != BASE_ORACLE_BLOB_SHA:
    raise RuntimeError("respool_draft8/oracle.py dependency drift")

_spec = importlib.util.spec_from_file_location("respool_base_oracle_pinned", BASE_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError("cannot load pinned respool oracle")
BASE = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = BASE
_spec.loader.exec_module(BASE)

def pattern_bytes(tag: int, size: int) -> bytes:
    return bytes(((tag + i * 17 + (i >> 8) * 29) & 0xFF) for i in range(size))

def pattern_block(tag: int, block_ordinal: int) -> bytes:
    """512 bytes from the same deterministic stream at a block offset."""
    base = block_ordinal * BASE.BLOCK
    return bytes(
        ((tag + (base + i) * 17 + ((base + i) >> 8) * 29) & 0xFF)
        for i in range(BASE.BLOCK)
    )

def target_before_block(case: dict) -> bytes:
    """Verifier-owned raw destination bytes immediately before a targeted copy write."""
    ordinal = case["injection"]["write_ordinal"]
    if case["fixture"] == "v3_003" and case["pass"] == "pass1":
        # Pass-1 destination [12,14) is unallocated and deliberately non-audio.
        return pattern_block(90, ordinal)
    if case["fixture"] == "v3_003" and case["pass"] == "pass2":
        # Reclaimed [10,12) still contains the old timeline bytes.
        return pattern_block(10, ordinal)
    if case["fixture"] == "no_lower_run" and case["pass"] == "pass1":
        return pattern_block(91, ordinal)
    raise ValueError("no canonical target block for case")

def source_block_known(case: dict) -> tuple[bytes | None, bytes]:
    """Return (whole expected block when normative, known logical prefix).

    The V3-003 timeline fills whole chunks, so every copied block is independently
    known. The no-lower-run fixture has only 10 stereo frames (40 bytes); bytes
    after that logical payload in its sole destination block are intentionally
    unspecified by TapeFS, so only the prefix is normative.
    """
    ordinal = case["injection"]["write_ordinal"]
    if case["fixture"] == "v3_003":
        block = pattern_block(10, ordinal)
        return block, block
    if case["fixture"] == "no_lower_run" and ordinal == 0:
        return None, pattern_bytes(31, 40)
    raise ValueError("no canonical source block for case")

V3_AUDIO_SHA256 = hashlib.sha256(pattern_bytes(10, 2 * BASE.CHUNK_BYTES)).hexdigest()
LIVE_A_SHA256 = hashlib.sha256(pattern_bytes(77, 512)).hexdigest()
DECLINE_AUDIO_SHA256 = hashlib.sha256(pattern_bytes(31, 40)).hexdigest()

def base_cases() -> dict:
    return {c.id: c for c in BASE.make_cases()}

def v3_case():
    return base_cases()["WP12-TWOPASS"]

def decline_case():
    return base_cases()["WP12-DECLINE"]

def clean_cases():
    ids = (
        "WP12-EMPTY", "WP12-TWOPASS", "WP12-DECLINE", "WP12-FULL",
        "WP12-SEQ-EXHAUSTED", "WP12-ONE-COMMIT",
    )
    by_id = base_cases()
    return [by_id[x] for x in ids]

def _sb_with_generation(template: bytes, generation: int) -> bytes:
    b = bytearray(template)
    struct.pack_into("<I", b, 12, generation)
    struct.pack_into("<I", b, 508, zlib.crc32(b[:508]))
    return bytes(b)

def empty_at(sequence: int, generation: int):
    m = BASE.media(3, [], partner_seq=sequence)
    sb = _sb_with_generation(m.primary, generation)
    return BASE.Media(m.blocks, sb, sb, m.slots)

def compact(m) -> dict:
    return {
        "block_count": m.blocks,
        "primary_hex": m.primary.hex(),
        "mirror_hex": m.mirror.hex(),
        "slot_prefix_hex": [x[:1024].hex() for x in m.slots],
    }

def from_compact(raw: dict):
    slots = []
    for prefix in raw["slot_prefix_hex"]:
        p = bytes.fromhex(prefix)
        if len(p) != 1024:
            raise ValueError("slot prefix must be exactly two blocks")
        slots.append(p + bytes(BASE.SLOT_BYTES - len(p)))
    return BASE.Media(
        int(raw["block_count"]),
        bytes.fromhex(raw["primary_hex"]),
        bytes.fromhex(raw["mirror_hex"]),
        tuple(slots),
    )

def layout_name(fixture_name: str, m) -> str | None:
    live = BASE.live_slot(m, 1)
    if live is None:
        return None
    ent = BASE.parse_entries(m.slots[live])
    seq = BASE.structural_sequence(m.slots[live])
    if fixture_name == "v3_003":
        if ent == [(10, 0, 2 * BASE.CF)] and seq == 20:
            return "pre"
        if ent == [(12, 0, 2 * BASE.CF)] and seq == 701:
            return "post_pass1"
        if ent == [(10, 0, 2 * BASE.CF)] and seq == 702:
            return "post_pass2"
    elif fixture_name == "no_lower_run":
        old = [(x, 0, 1) for x in range(11, 21)]
        if ent == old and seq == 20:
            return "pre"
        if ent == [(10, 0, 10)] and seq == 701:
            return "post_pass1"
    return None

def functional_fixture_errors() -> list[str]:
    errors = []
    for c in clean_cases():
        errors.extend(f"{c.id}: {x}" for x in BASE.fixture_contract_errors(c))
    v3 = v3_case()
    if BASE.free_next(v3.pre) != 12:
        errors.append("V3-003 free_next drift")
    if BASE.entry_chunks(BASE.parse_entries(v3.pre.slots[2])) != {10, 11}:
        errors.append("V3-003 live set drift")
    if v3.passes[0].start_chunk != 12 or v3.passes[1].start_chunk != 10:
        errors.append("V3-003 pass destinations drift")
    hi = empty_at(0xFFFFFFFF, 0xFFFFFFFF)
    if BASE.cartridge_sequence(hi) != 0xFFFFFFFF:
        errors.append("reserved-sequence empty fixture drift")
    if struct.unpack_from("<I", BASE.select_sb(hi), 12)[0] != 0xFFFFFFFF:
        errors.append("reserved-generation empty fixture drift")
    return errors
