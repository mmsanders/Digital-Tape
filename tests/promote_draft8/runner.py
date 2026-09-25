#!/usr/bin/env python3
"""Production evidence runner for the immutable R29-A promote verifier."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from oracle import VerificationError, failure_reproducer, validate_case
from planner import (
    EXPECTED_CASESET_SHA256, EXPECTED_TOTAL_CASES, counts, iter_cases, validate_planner,
)

HANDSHAKE = "PROMOTE-ADAPTER-1"
OBSERVATION = "PROMOTE-OBSERVATION-1"


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--adapter", required=True)
    p.add_argument("--adapter-arg", action="append", default=[])
    p.add_argument("--adapter-source-sha256", required=True)
    p.add_argument("--adapter-build-sha256", required=True)
    p.add_argument("--source-commit", required=True)
    p.add_argument("--source-tree", required=True)
    p.add_argument("--publication-commit", required=True)
    p.add_argument("--publication-tree", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--timeout-s", type=float, default=20.0)
    return p.parse_args()


def read_line(proc, timeout_s):
    # Adapters are line-oriented. communicate-style timeout is not usable while
    # streaming tens of thousands of cases, so enforce wall time per line by
    # polling and a small sleep.
    start = time.monotonic()
    while True:
        line = proc.stdout.readline()
        if line:
            return line
        if proc.poll() is not None:
            raise RuntimeError(f"adapter exited {proc.returncode}")
        if time.monotonic() - start > timeout_s:
            raise RuntimeError("adapter response timeout")
        time.sleep(0.01)


def main():
    args = parse_args()
    problems = validate_planner()
    if problems:
        raise SystemExit("planner invalid: " + "; ".join(problems))

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stderr_path = out / "adapter-stderr.txt"

    cmd = [args.adapter, *args.adapter_arg]
    with stderr_path.open("wb") as err:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=err,
            text=True,
            bufsize=1,
        )
        try:
            hello = json.loads(read_line(proc, args.timeout_s))
            if hello.get("format") != HANDSHAKE:
                raise RuntimeError("adapter handshake format")
            if hello.get("adapter_kind") != "product":
                raise RuntimeError("non-product adapter refused")
            if hello.get("caseset_sha256") != EXPECTED_CASESET_SHA256:
                raise RuntimeError("adapter planner digest mismatch")
            if hello.get("raw_observation_only") is not True:
                raise RuntimeError("adapter did not assert raw-observation-only boundary")
            adapter_id = hello.get("adapter_id")
            if not isinstance(adapter_id, str) or not adapter_id:
                raise RuntimeError("adapter_id missing")

            passed = 0
            failure = None
            for case in iter_cases():
                proc.stdin.write(canonical(case) + "\n")
                proc.stdin.flush()
                raw = read_line(proc, args.timeout_s)
                try:
                    obs = json.loads(raw)
                    validate_case(case, obs)
                except Exception as e:
                    failure = failure_reproducer(
                        case,
                        obs if "obs" in locals() and isinstance(obs, dict) else {},
                        e,
                    )
                    (out / "failure-reproducer.json").write_text(
                        json.dumps(failure, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    raise
                passed += 1

            proc.stdin.write(canonical({"done": True}) + "\n")
            proc.stdin.flush()
            proc.stdin.close()
            rc = proc.wait(timeout=args.timeout_s)
            if rc != 0:
                raise RuntimeError(f"adapter final exit {rc}")

        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()

    census = counts()
    summary = {
        "format": "PROMOTE-RUN-SUMMARY-1",
        "caseset_sha256": EXPECTED_CASESET_SHA256,
        "expected_cases": EXPECTED_TOTAL_CASES,
        "completed_cases": passed,
        "census": {
            "crash": census["crash"],
            "contract": census["contract"],
            "total": census["total"],
            "crash_by_scenario_mode": {
                f"{k[0]}:{k[1]}": v for k, v in sorted(census["crash_by_scenario_mode"].items())
            },
            "contract_families": census["contract_families"],
        },
        "adapter": {
            "id": adapter_id,
            "source_sha256": args.adapter_source_sha256,
            "build_sha256": args.adapter_build_sha256,
        },
        "source": {"commit": args.source_commit, "tree": args.source_tree},
        "verifier": {
            "publication_commit": args.publication_commit,
            "publication_tree": args.publication_tree,
        },
        "failure": failure,
    }
    summary_bytes = (json.dumps(summary, indent=2, sort_keys=True) + "\n").encode()
    (out / "summary.json").write_bytes(summary_bytes)
    (out / "summary.sha256").write_text(hashlib.sha256(summary_bytes).hexdigest() + "\n")
    print(f"PASS {passed}/{EXPECTED_TOTAL_CASES} promote verifier cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
