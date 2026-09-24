#!/usr/bin/env python3
"""Synthetic stand-in used only to self-test WP-07 verifier plumbing."""
from __future__ import annotations

import json
import platform
import sys

from fixture import (
    CHUNK_BLOCKS,
    CHUNK_FRAMES,
    LBA_B1,
    LBA_CHUNK_BASE,
    SLOT_BYTES,
    fuzz_entries_a,
    fuzz_initial_b_slots,
    fixture_digests,
    make_index,
    reset_initial_b_slots,
    reset_stress_entries_a,
    slot_snapshot,
)
from generator import resolve_selector
from oracle import ADAPTER_FORMAT, RESULT_FORMAT


def _chunk_write(chunk: int) -> list[dict]:
    return [{"lba": LBA_CHUNK_BASE + chunk * CHUNK_BLOCKS, "count": 1}]


def _probe(chunk: int = 3) -> dict:
    return {
        "event_overflow": False,
        "seek_result": "TAPE_OK",
        "arm_result": "TAPE_OK",
        "feed_result": "TAPE_OK",
        "accepted_frames": 1,
        "service_terminal_result": "TAPE_OK",
        "abort_result": "TAPE_OK",
        "unmount_result": "TAPE_OK",
        "remount_result": "TAPE_OK",
        "write_events": _chunk_write(chunk),
    }


def reset_slots() -> list[dict]:
    return [
        fuzz_initial_b_slots()[0],
        slot_snapshot(make_index(1, 21, fuzz_entries_a())),
    ]


def good_sequence_observation(plan: dict) -> dict:
    current = fuzz_initial_b_slots()
    total_frames = 3 * CHUNK_FRAMES
    actions = []

    for want in plan["actions"]:
        if want["kind"] == "edit":
            got = {
                "kind": "edit",
                "mode": want["mode"],
                "selector": want["selector"],
                "frames": want["frames"],
                "service_budget": want["service_budget"],
                "pre_b_slots": current,
                "pre_total_frames": total_frames,
                "resolved_seek": resolve_selector(want["selector"], total_frames),
                "seek_result": "TAPE_OK",
                "arm_result": "TAPE_OK",
                "feed_result": "TAPE_OK",
                "accepted_frames": want["frames"],
                "service_terminal_result": "TAPE_OK",
                "commit_result": "TAPE_OK",
                "unmount_result": "TAPE_OK",
                "remount_result": "TAPE_OK",
                "event_overflow": False,
                "write_events": _chunk_write(3),
                # Synthetic stand-in intentionally leaves the valid index unchanged.
                # WP-09, not this plumbing self-test, owns edit functional semantics.
                "post_b_slots": current,
                "post_info_total_frames": total_frames,
                "allocation_probe": _probe(3),
            }
        else:
            current = reset_slots()
            got = {
                "kind": "reset",
                "pre_b_slots": actions[-1]["post_b_slots"] if actions else fuzz_initial_b_slots(),
                "result": "TAPE_OK",
                "timed_out": False,
                "elapsed_ns": 100_000,
                "event_overflow": False,
                "write_events": [{"lba": LBA_B1, "count": 1}],
                "post_b_slots": current,
                "post_info_total_frames": total_frames,
                "allocation_probe": _probe(3),
            }
        actions.append(got)

    # Repair continuity in the synthetic transcript after a reset: each following
    # action's pre snapshot is the immediately preceding post snapshot.
    previous = fuzz_initial_b_slots()
    for got in actions:
        got["pre_b_slots"] = previous
        previous = got["post_b_slots"]

    return {
        "format": RESULT_FORMAT,
        "seq_index": plan["seq_index"],
        "seq_seed": plan["seq_seed"],
        "event_overflow": False,
        "normal_exit": True,
        "initial_b_slots": fuzz_initial_b_slots(),
        "actions": actions,
    }


def reset_stress_observation() -> dict:
    live = slot_snapshot(make_index(1, 102, reset_stress_entries_a()))
    return {
        "format": "WP07-RESET-STRESS-1",
        "result": "TAPE_OK",
        "timed_out": False,
        "elapsed_ns": 250_000,
        "event_overflow": False,
        "write_events": [{"lba": LBA_B1, "count": 97}],
        "post_b_slots": [reset_initial_b_slots()[0], live],
        "timing_environment": {
            "clock": "CLOCK_MONOTONIC",
            "platform": platform.platform() or "synthetic",
            "kernel": platform.release() or "synthetic",
            "cpu_model": "synthetic-cpu",
            "timer_resolution_ns": 1,
        },
    }


def main(argv=None) -> int:
    if len(sys.argv) != 5 or sys.argv[1] != "--fuzz-fixture" or sys.argv[3] != "--reset-stress-fixture":
        print("bad synthetic arguments", file=sys.stderr)
        return 2

    digests = fixture_digests()
    print(
        json.dumps(
            {
                "type": "hello",
                "format": ADAPTER_FORMAT,
                "adapter_kind": "product",
                "fuzz_fixture_sha256": digests["fuzz_sha256"],
                "reset_stress_fixture_sha256": digests["reset_stress_sha256"],
            },
            separators=(",", ":"),
        ),
        flush=True,
    )

    for line in sys.stdin:
        try:
            cmd = json.loads(line)
        except json.JSONDecodeError:
            return 2
        if cmd.get("command") == "done":
            return 0
        if cmd.get("command") == "reset_stress":
            print(json.dumps(reset_stress_observation(), separators=(",", ":")), flush=True)
            continue
        if cmd.get("command") == "sequence":
            plan = cmd.get("plan")
            if not isinstance(plan, dict):
                return 2
            print(json.dumps(good_sequence_observation(plan), separators=(",", ":")), flush=True)
            continue
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
