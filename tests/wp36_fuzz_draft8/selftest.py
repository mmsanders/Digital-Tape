#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import sys
import tempfile

from generator import (
    EXPECTED_PLAN_SHA256,
    EXPECTED_TOTAL_OPS,
    SEQUENCE_COUNT,
    census_and_digest,
    generate_sequence,
    plan_line,
    validate_generator_census,
)
from runner import EVIDENCE_FORMAT, RunFailure, run_session, validate_acceptance_summary

ROOT = Path(__file__).resolve().parent
SYNTH = ROOT / "synthetic_adapter.py"


def need(cond, msg):
    if not cond:
        raise AssertionError(msg)


def synth_proxy(directory: Path) -> Path:
    """Create an executable proxy without requiring an executable git file mode."""
    proxy = directory / "synthetic-adapter"
    proxy.write_text(
        "#!/bin/sh\nexec "
        + shlex.quote(sys.executable)
        + " "
        + shlex.quote(str(SYNTH))
        + ' "$@"\n',
        encoding="utf-8",
    )
    proxy.chmod(0o700)
    return proxy


def main() -> None:
    census, digest = census_and_digest()
    errors = validate_generator_census(census)
    need(not errors, "generator coverage invalid: " + "; ".join(errors))
    need(census["sequence_count"] == 100_000, "generator did not produce exactly 100000 sequences")
    need(census["total_ops"] == EXPECTED_TOTAL_OPS, "total operation census drift")
    need(digest == EXPECTED_PLAN_SHA256, "100000-sequence plan digest drift")
    print("PASS deterministic 100000-sequence generator", digest, census["total_ops"])

    a = generate_sequence(12345)
    b = generate_sequence(12345)
    need(a == b and plan_line(a) == plan_line(b), "sequence reproduction by index/seed failed")
    print("PASS sequence reproducer determinism")

    with tempfile.TemporaryDirectory(prefix="wp36-self-ok-") as td:
        path = Path(td)
        adapter = synth_proxy(path)
        summary = run_session(adapter, path / "evidence", sequence_count=32, acceptance=False)
        need(summary["completed_sequences"] == 32, "protocol smoke did not complete")
    print("PASS streaming protocol smoke")

    old = os.environ.get("WP36_SYNTH_CRASH_AT")
    os.environ["WP36_SYNTH_CRASH_AT"] = "7"
    try:
        with tempfile.TemporaryDirectory(prefix="wp36-self-crash-") as td:
            path = Path(td)
            adapter = synth_proxy(path)
            evidence = path / "evidence"
            try:
                run_session(adapter, evidence, sequence_count=16, acceptance=False)
                raise AssertionError("runner accepted assertion/crash")
            except RunFailure:
                repro = evidence / "failure-reproducer.json"
                need(repro.is_file(), "crash did not retain a failure reproducer")
                need(json.loads(repro.read_text())["seq_index"] == 7, "wrong crash reproducer sequence")
    finally:
        if old is None:
            os.environ.pop("WP36_SYNTH_CRASH_AT", None)
        else:
            os.environ["WP36_SYNTH_CRASH_AT"] = old
    print("PASS assertion/crash negative control")

    old_mode = os.environ.get("WP36_SYNTH_MODE")
    os.environ["WP36_SYNTH_MODE"] = "nonnull"
    try:
        with tempfile.TemporaryDirectory(prefix="wp36-self-null-") as td:
            path = Path(td)
            adapter = synth_proxy(path)
            try:
                run_session(adapter, path / "evidence", sequence_count=1, acceptance=False)
                raise AssertionError("runner accepted non-NULL source binding")
            except RunFailure as exc:
                need("not literal NULL" in str(exc), "wrong non-NULL rejection")
    finally:
        if old_mode is None:
            os.environ.pop("WP36_SYNTH_MODE", None)
        else:
            os.environ["WP36_SYNTH_MODE"] = old_mode
    print("PASS non-NULL source-binding negative control")

    good = {
        "format": EVIDENCE_FORMAT,
        "generator": {
            "rng_algorithm": "splitmix64-v1",
            "master_seed": "5730365a5eed2026",
            "sequence_count": SEQUENCE_COUNT,
            "plan_sha256": "0" * 64,
        },
        "completed_sequences": SEQUENCE_COUNT,
        "normal_exit": True,
        "assertion_or_crash": False,
        "adapter_handshake": {
            "adapter_kind": "product",
            "source_write_binding": "NULL",
            "assertion_mode": "debug",
        },
    }
    need(not validate_acceptance_summary(good), "conforming summary rejected")

    short = json.loads(json.dumps(good))
    short["generator"]["sequence_count"] = 99_999
    short["completed_sequences"] = 99_999
    need(validate_acceptance_summary(short), "fewer-than-100000 summary escaped")
    print("PASS fewer-than-100000 negative control")

    malformed = json.loads(json.dumps(good))
    del malformed["generator"]["master_seed"]
    need(validate_acceptance_summary(malformed), "missing provenance escaped")
    print("PASS malformed provenance negative control")

    wrong_binding = json.loads(json.dumps(good))
    wrong_binding["adapter_handshake"]["source_write_binding"] = "NON_NULL"
    need(validate_acceptance_summary(wrong_binding), "non-NULL evidence binding escaped")
    print("PASS summary source-binding negative control")

    print("PASS all WP-36 fuzz package self-tests")


if __name__ == "__main__":
    main()
