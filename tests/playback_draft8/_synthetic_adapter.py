#!/usr/bin/env python3
"""Deterministic synthetic adapter used only to prove the verifier package plumbing.

This is not product execution and must never be cited as product acceptance.
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

from oracle import (
    BLOCK, CHUNK_FRAMES, FRAME_BYTES, LBA_A0, LBA_A1, LBA_B0, LBA_B1,
    LBA_CHUNK_BASE, EXPECTED_ENTRIES, EXPECTED_SEEK_TARGETS,
    decode_vo08, expected_outputs, sha256_bytes, verify_fixture,
)

MOUNT_READS = (0, LBA_A0, LBA_A1, LBA_B0, LBA_B1)


def mount_callbacks(call_index: int, blocks: int) -> list[dict]:
    out = [{"call_index": call_index, "op": "read", "lba": 0, "count": 1, "rc": 0},
           {"call_index": call_index, "op": "read", "lba": blocks - 1, "count": 1, "rc": 0}]
    for lba in (LBA_A0, LBA_A1, LBA_B0, LBA_B1):
        out.append({"call_index": call_index, "op": "read", "lba": lba, "count": 128, "rc": 0})
    return out


def timeline_physical_frame(n: int) -> int:
    cursor = 0
    for first, start, count in EXPECTED_ENTRIES:
        if cursor <= n < cursor + count:
            return first * CHUNK_FRAMES + start + (n - cursor)
        cursor += count
    raise ValueError(n)


def service_callback(call_index: int, timeline_frame: int) -> dict:
    physical = timeline_physical_frame(timeline_frame)
    byte_off = physical * FRAME_BYTES
    lba = LBA_CHUNK_BASE + byte_off // BLOCK
    return {"call_index": call_index, "op": "read", "lba": lba, "count": 1, "rc": 0}


def mount_call() -> dict:
    return {"call": "tape_mount", "side": "A", "resume_frame": 0, "warm": None, "result": 0}


def rate_call(rate: int) -> dict:
    return {"call": "tape_set_rate", "rate_q16_16": rate, "result": 0}


def service_call() -> dict:
    return {"call": "tape_service", "block_budget": 1024, "more_work": False, "result": 0}


def render_call(frames: int) -> dict:
    return {"call": "tape_render", "requested": frames, "rendered": frames, "result": 0}


def unmount_call() -> dict:
    return {"call": "tape_unmount", "result": 0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    raw = Path(args.fixture).read_bytes()
    fx = verify_fixture(raw)
    blocks = fx["blocks"]
    exp = expected_outputs(raw)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    names = {
        "forward_1x": "forward-1x.pcm",
        "seek_boundaries": "seek-boundaries.pcm",
        "reverse_neg1x": "reverse-neg1x.pcm",
    }
    for family, name in names.items():
        (out / name).write_bytes(exp[family])

    cases = {}

    calls = [mount_call(), rate_call(65536), service_call(), render_call(15), unmount_call()]
    callbacks = mount_callbacks(0, blocks) + [service_callback(2, 0)]
    cases["forward_1x"] = {"calls": calls, "callbacks": callbacks, "output": names["forward_1x"]}

    calls = [mount_call(), rate_call(65536)]
    callbacks = mount_callbacks(0, blocks)
    for target in EXPECTED_SEEK_TARGETS:
        calls.append({"call": "tape_seek", "frame": target, "result": 0})
        svc_i = len(calls)
        calls.append(service_call())
        callbacks.append(service_callback(svc_i, target))
        calls.append(render_call(1))
    calls.append(unmount_call())
    cases["seek_boundaries"] = {"calls": calls, "callbacks": callbacks, "output": names["seek_boundaries"]}

    calls = [mount_call(),
             {"call": "tape_seek", "frame": 15, "result": 0},
             rate_call(-65536),
             service_call(), render_call(15), unmount_call()]
    callbacks = mount_callbacks(0, blocks) + [service_callback(3, 14)]
    cases["reverse_neg1x"] = {"calls": calls, "callbacks": callbacks, "output": names["reverse_neg1x"]}

    observation = {
        "schema": "playback-draft8-observation-v1",
        "fixture_sha256": sha256_bytes(raw),
        "adapter": {"kind": "synthetic", "id": "verifier-synthetic-public-api-model-v1"},
        "cases": cases,
    }
    (out / "observation.json").write_text(json.dumps(observation, indent=2, sort_keys=True) + "\n")
    print("synthetic adapter: wrote three DRAFT-8 playback observation families")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
