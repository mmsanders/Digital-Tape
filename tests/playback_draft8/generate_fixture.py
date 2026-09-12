#!/usr/bin/env python3
"""Deterministically construct the P1-R2-V VO08 fixture and candidate PCM."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import struct
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
BLOCK_BYTES = 512
INDEX_SLOT_BYTES = 65536
CHUNK_FRAMES = 131072
FRAME_BYTES = 4
CHUNK_BYTES = CHUNK_FRAMES * FRAME_BYTES
BLOCK_COUNT = 6145
PARTITION_BYTES = BLOCK_COUNT * BLOCK_BYTES
LBA_A0, LBA_A1, LBA_B0, LBA_B1 = 8, 136, 264, 392
LBA_CHUNK_BASE = 2048
ENTRIES = ((0, 10, 5), (2, 20, 4), (1, 30, 6))
SEEK_TARGETS = (0, 1, 4, 5, 6, 8, 9, 10)
TIMELINE = (
    (100, -101),
    (1000, -1001),
    (2000, -2001),
    (3000, -3001),
    (4000, -4001),
    (-5000, 5001),
    (-4000, 4001),
    (-3000, 3001),
    (-2000, 2001),
    (31000, -31001),
    (12345, -23456),
    (-12345, 23456),
    (32767, -32768),
    (-32768, 32767),
    (777, -888),
)


def pcm_bytes(frames: tuple[tuple[int, int], ...]) -> bytes:
    return b"".join(struct.pack("<hh", *frame) for frame in frames)


def index_slot(sequence: int, side: int,
               entries: tuple[tuple[int, int, int], ...]) -> bytes:
    slot = bytearray(INDEX_SLOT_BYTES)
    slot[:8] = b"TAPEIDX\x01"
    struct.pack_into("<IB3xIQ", slot, 8, sequence, side, len(entries),
                     sum(entry[2] for entry in entries))
    for number, entry in enumerate(entries):
        struct.pack_into("<III", slot, 512 + 12 * number, *entry)
    covered_entries = slot[512:512 + 12 * len(entries)]
    struct.pack_into("<I", slot, 60,
                     zlib.crc32(slot[:60] + covered_entries))
    return bytes(slot)


def superblock() -> bytes:
    block = bytearray(BLOCK_BYTES)
    block[:8] = b"TAPEFS\x00\x01"
    struct.pack_into(
        "<HHIB3x16sIHHIIIII",
        block,
        8,
        1,
        0,
        7,
        0,
        bytes(range(16)),
        44100,
        2,
        16,
        CHUNK_BYTES,
        10,
        4,
        3,
        INDEX_SLOT_BYTES,
    )
    struct.pack_into(
        "<IIIIII",
        block,
        64,
        LBA_A0,
        LBA_A1,
        LBA_B0,
        LBA_B1,
        LBA_CHUNK_BASE,
        BLOCK_COUNT - 1,
    )
    block[88:98] = b"PlaybackR2"
    struct.pack_into("<III", block, 120, 0, 0, 0)
    struct.pack_into("<I", block, 508, zlib.crc32(block[:508]))
    return bytes(block)


def raw_vo08() -> bytes:
    raw = bytearray(8 + PARTITION_BYTES)
    raw[:4] = b"VO08"
    struct.pack_into("<I", raw, 4, BLOCK_COUNT)
    partition = memoryview(raw)[8:]
    sb = superblock()
    partition[:BLOCK_BYTES] = sb
    partition[-BLOCK_BYTES:] = sb
    for lba, sequence, side, entries in (
        (LBA_A0, 10, 0, ENTRIES),
        (LBA_A1, 9, 0, ENTRIES),
        (LBA_B0, 20, 1, ()),
        (LBA_B1, 19, 1, ()),
    ):
        start = lba * BLOCK_BYTES
        partition[start:start + INDEX_SLOT_BYTES] = index_slot(
            sequence, side, entries
        )

    timeline = pcm_bytes(TIMELINE)
    cursor = 0
    for first_chunk, start_frame, frame_count in ENTRIES:
        start = (LBA_CHUNK_BASE * BLOCK_BYTES
                 + (first_chunk * CHUNK_FRAMES + start_frame) * FRAME_BYTES)
        count = frame_count * FRAME_BYTES
        partition[start:start + count] = timeline[cursor:cursor + count]
        cursor += count
    assert cursor == len(timeline)
    return bytes(raw)


def deterministic_gzip(data: bytes) -> bytes:
    output = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=output,
                       compresslevel=9, mtime=0) as archive:
        archive.write(data)
    return output.getvalue()


def metadata_bytes() -> bytes:
    metadata = {
        "block_count": BLOCK_COUNT,
        "block_size": BLOCK_BYTES,
        "channels": 2,
        "fixture": "playback-three-run.vo08.gz",
        "index_entries": [
            {
                "first_chunk_id": first,
                "frame_count": count,
                "start_frame": start,
            }
            for first, start, count in ENTRIES
        ],
        "partition_bytes": PARTITION_BYTES,
        "run_boundaries": [0, 5, 9],
        "sample_format": "s16le",
        "sample_rate_hz": 44100,
        "schema": "playback-draft8-fixture-v1",
        "seek_targets": list(SEEK_TARGETS),
        "side": "A",
        "timeline_frames": len(TIMELINE),
        "uuid_hex": bytes(range(16)).hex(),
        "vo08_raw_bytes": 8 + PARTITION_BYTES,
    }
    return (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode()


def generated_files() -> tuple[bytes, dict[str, bytes]]:
    forward = pcm_bytes(TIMELINE)
    raw = raw_vo08()
    files = {
        "fixtures/playback-three-run.vo08.gz": deterministic_gzip(raw),
        "fixtures/fixture.json": metadata_bytes(),
        "golden/forward-1x.pcm": forward,
        "golden/seek-boundaries.pcm": pcm_bytes(
            tuple(TIMELINE[target] for target in SEEK_TARGETS)
        ),
        "golden/reverse-neg1x.pcm": pcm_bytes(tuple(reversed(TIMELINE))),
    }
    return raw, files


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_manifest(raw: bytes, files: dict[str, bytes]) -> None:
    manifest = json.loads((HERE / "package.json").read_text())
    fixture = manifest["fixture"]
    if len(raw) != fixture["raw_bytes"] or sha256(raw) != fixture["raw_sha256"]:
        raise ValueError("generated raw VO08 disagrees with package.json")
    expected = {
        fixture["archive"]: fixture["archive_sha256"],
        fixture["metadata"]: fixture["metadata_sha256"],
        **{record["path"]: record["sha256"]
           for record in manifest["goldens"].values()},
    }
    for relative, wanted in expected.items():
        if relative not in files or sha256(files[relative]) != wanted:
            raise ValueError(f"generated bytes disagree with package.json: {relative}")


def check_checked_in(raw: bytes | None = None,
                     files: dict[str, bytes] | None = None) -> None:
    if raw is None or files is None:
        raw, files = generated_files()
    verify_manifest(raw, files)
    for relative, expected in files.items():
        path = HERE / relative
        if not path.is_file():
            raise ValueError(f"missing generated artifact: {relative}")
        if path.read_bytes() != expected:
            raise ValueError(f"checked-in artifact differs from generator: {relative}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        action="store_true",
        help="replace the five generated fixture/candidate-PCM artifacts",
    )
    args = parser.parse_args()
    raw, files = generated_files()
    verify_manifest(raw, files)
    if args.write:
        for relative, data in files.items():
            path = HERE / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        print("WROTE deterministic fixture and candidate PCM")
    else:
        check_checked_in(raw, files)
        print("PASS checked-in fixture and candidate PCM equal deterministic generator")
    print("raw VO08", len(raw), sha256(raw))
    for relative, data in sorted(files.items()):
        print(relative, len(data), sha256(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
