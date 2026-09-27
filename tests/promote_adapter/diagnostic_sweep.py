#!/usr/bin/env python3
"""Diagnostic sweep for the R29-A promote package. NOT the canonical run.

The verifier's runner.py stops at the first failing case, which is the
canonical result. This sweep sends every one of the 44,307 canonical cases to
the same product adapter, validates each with the verifier's own
oracle.validate_case, and records every failure, so one round shows the whole
picture instead of only the first red case. It changes no case, tolerance or
order and decides nothing the oracle does not; it exits non-zero if any case
fails.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tests" / "promote_draft8"))

from oracle import validate_case  # noqa: E402
from planner import EXPECTED_CASESET_SHA256, EXPECTED_TOTAL_CASES, iter_cases  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    out = a.out if a.out.is_absolute() else ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)

    p = subprocess.Popen([sys.executable, str(HERE / "adapter.py")], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, text=True, bufsize=1)
    assert p.stdin is not None and p.stdout is not None
    hello = json.loads(p.stdout.readline())
    if hello.get("caseset_sha256") != EXPECTED_CASESET_SHA256:
        raise SystemExit("adapter digest mismatch")

    ran = 0
    failures = []
    by_bucket: collections.Counter = collections.Counter()
    for case in iter_cases():
        p.stdin.write(json.dumps(case, sort_keys=True, separators=(",", ":")) + "\n")
        p.stdin.flush()
        line = p.stdout.readline()
        if not line:
            raise SystemExit(f"adapter exited at case {case['case_index']}")
        obs = json.loads(line)
        ran += 1
        try:
            validate_case(case, obs)
        except Exception as e:  # noqa: BLE001 - every failure is recorded
            failures.append({"case": case, "error": str(e)})
            by_bucket[case.get("family") or case.get("scenario")] += 1
    p.stdin.write('{"done":true}\n')
    p.stdin.flush()
    rc = p.wait(timeout=30)

    report = {
        "format": "PROMOTE-DIAGNOSTIC-SWEEP-1",
        "canonical": False,
        "caseset_sha256": EXPECTED_CASESET_SHA256,
        "expected_cases": EXPECTED_TOTAL_CASES,
        "ran": ran,
        "validated": ran - len(failures),
        "failed": len(failures),
        "failed_by_bucket": dict(sorted(by_bucket.items())),
        "failures": failures,
        "adapter_exit": rc,
    }
    data = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
    (out / "diagnostic-sweep.json").write_bytes(data)
    (out / "diagnostic-sweep.sha256").write_text(hashlib.sha256(data).hexdigest() + "\n")
    print(f"diagnostic sweep: ran {ran}/{EXPECTED_TOTAL_CASES}, validated {ran - len(failures)}, failed {len(failures)}")
    for f in failures:
        print(f"  FAIL case {f['case']['case_index']} {f['case'].get('family') or f['case'].get('scenario')}: {f['error']}")
    return 0 if (ran == EXPECTED_TOTAL_CASES and not failures and rc == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
