#!/usr/bin/env python3
"""Synthetic stand-in used only to self-test the WP-10 core verifier package."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

from fixture import all_fixture_digests, fixture_bytes
from media import compact_snapshot, inspect_snapshot
from oracle import _transaction, expected_snapshot
from planner import EXPECTED_CASESET_SHA256


def _baseline(case: dict) -> dict:
    tx = _transaction(case)
    out = {
        "writes": [
            {
                "ordinal": i,
                "lba": op["lba"],
                "count": 1,
                "sha256": hashlib.sha256(op["data"]).hexdigest(),
                "role": op["role"],
            }
            for i, op in enumerate(tx)
        ],
        "flushes": [{"ordinal": 0}, {"ordinal": 1}],
    }
    if case["family"] == "stage_clear":
        out.update(
            {
                "post_clear_reached": True,
                "post_clear_next_kind": "index" if case["variant"] == "reset_b" else "chunk",
                "post_clear_write_landed": False,
            }
        )
    return out


def _pre_snapshot(case: dict) -> dict:
    snap = compact_snapshot(
        fixture_bytes(
            case["family"],
            case["variant"],
            seed=case.get("seed"),
        )
    )
    if case["family"] == "record_commit":
        # A clean service-to-completion step has made the pending COW chunk
        # durable before tape_commit begins. Synthetic plumbing represents that
        # solely as a changed chunk-2 digest.
        snap = copy.deepcopy(snap)
        snap["chunk_sha256"]["2"] = hashlib.sha256(
            ("prepared-" + case["variant"]).encode("ascii")
        ).hexdigest()
        snap["image_sha256"] = hashlib.sha256(
            ("synthetic-pre-" + case["variant"]).encode("ascii")
        ).hexdigest()
    return snap


def _observation(case: dict) -> dict:
    pre = _pre_snapshot(case)
    post = expected_snapshot(case, pre)
    side = "A" if case["family"] == "reset_b" and case["variant"] == "degraded_equal" else "B"
    predicted = inspect_snapshot(post, requested_side=side)["mount_result"]
    out = {
        "format": "WP10-CORE-OBSERVATION-1",
        "case_index": case["case_index"],
        "scope": case["scope"],
        "family": case["family"],
        "variant": case["variant"],
        "mode": case["mode"],
        "pre_snapshot": pre,
        "post_snapshot": post,
        "target_baseline": _baseline(case),
        "injection_fired": True,
        "fired_at": case["injection"],
        "remount_side": side,
        "actual_remount_result": predicted,
    }
    if "seed" in case:
        out.update(
            {
                "seed": case["seed"],
                "setup_mount_result": "TAPE_OK",
                "setup_needs_repair": True,
                "setup_repair_fault_fired": True,
            }
        )
    return out


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] != "--fixture-manifest":
        return 2
    manifest = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    if manifest.get("sha256") != all_fixture_digests():
        return 2

    print(
        json.dumps(
            {
                "format": "WP10-CORE-ADAPTER-1",
                "adapter_kind": "product",
                "caseset_sha256": EXPECTED_CASESET_SHA256,
                "fixture_sha256": all_fixture_digests(),
            },
            sort_keys=True,
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
        if cmd.get("command") != "case" or not isinstance(cmd.get("case"), dict):
            return 2
        print(
            json.dumps(_observation(cmd["case"]), sort_keys=True, separators=(",", ":")),
            flush=True,
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
