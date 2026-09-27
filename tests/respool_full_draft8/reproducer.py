#!/usr/bin/env python3
"""Retain an exact, replayable failure record for a product-binding run."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

WRITE_TARGETS = {"chunk_copy", "entry_block", "header_block"}

def canonical(obj) -> bytes:
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")

def retain_failure(path: str | Path, case: dict, observation: dict, reason: str) -> str:
    required = (
        "pre_snapshot", "post_snapshot", "target_event", "raw_region_sha256",
        "remount_side", "remount_info",
    )
    missing = [x for x in required if x not in observation]
    if case.get("target") in WRITE_TARGETS and "target_block" not in observation:
        missing.append("target_block")
    if missing:
        raise ValueError("observation missing exact failure material: " + ",".join(missing))

    tb = observation.get("target_block")
    if tb is not None:
        for name in ("before_hex", "intended_hex", "durable_hex"):
            try:
                raw = bytes.fromhex(tb[name])
            except (KeyError, ValueError, TypeError) as exc:
                raise ValueError("malformed target-block failure material") from exc
            if len(raw) != 512:
                raise ValueError("target-block failure material is not 512 bytes")

    record = {
        "format": "WP10-RESPOOL-FAILURE-1",
        "reason": reason,
        "case": case,
        "observation": observation,
    }
    data = canonical(record)
    Path(path).write_bytes(data)
    return hashlib.sha256(data).hexdigest()
