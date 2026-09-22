#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "tests" / "respool_draft8"
sys.path.insert(0, str(PKG))

from oracle import Media, check, fixture_contract_errors, make_cases  # noqa: E402

BLOCKED_CASE = "WP12-EMPTY"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", default=str(ROOT / "tests/respool_adapter/build/wp12_respool_probe"))
    ap.add_argument("--evidence")
    args = ap.parse_args()

    probe = Path(args.probe)
    if not probe.exists():
        raise SystemExit(f"probe not found: {probe}")

    product_commit = os.environ.get("PRODUCT_COMMIT") or git("rev-parse", "HEAD")
    package_tree = git("rev-parse", "HEAD:tests/respool_draft8")
    rows = []
    failures = 0
    cases = [case for case in make_cases() if case.id != BLOCKED_CASE]

    with tempfile.TemporaryDirectory(prefix="respool-product-") as td:
        tmp = Path(td)
        for case in cases:
            errors = list(fixture_contract_errors(case))
            pre = case.pre.encode()
            inp = tmp / f"{case.id}.in.vo08"
            out = tmp / f"{case.id}.out.vo08"
            inp.write_bytes(pre)

            proc = subprocess.run(
                [str(probe), case.id, str(inp), str(out)],
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
            )

            obs = None
            post = None
            if proc.returncode != 0:
                errors.append(f"adapter exit {proc.returncode}")
            try:
                obs = json.loads(proc.stdout)
            except Exception as exc:
                errors.append(f"observation parse failed: {exc}")

            if not out.exists():
                errors.append("adapter did not produce OUTPUT.vo08")
            else:
                try:
                    post = Media.decode(out.read_bytes())
                except Exception as exc:
                    errors.append(f"output media decode failed: {exc}")

            if isinstance(obs, dict):
                if obs.get("format") != "WP12-RESPOOL-OBSERVATION-1":
                    errors.append(f"observation format {obs.get('format')!r}")
                if obs.get("adapter_kind") != "product":
                    errors.append(f"adapter_kind {obs.get('adapter_kind')!r}")
                if obs.get("event_overflow") is not False:
                    errors.append("event trace overflowed")
                calls = obs.get("calls")
                events = obs.get("events")
                if not isinstance(calls, list):
                    errors.append("calls is not a list")
                if not isinstance(events, list):
                    errors.append("events is not a list")
                if post is not None and isinstance(calls, list) and isinstance(events, list):
                    errors.extend(check(case, post, events, calls))

            record = {
                "case": case.id,
                "argv": ["wp12_respool_probe", case.id],
                "exit": proc.returncode,
                "input_sha256": sha256(pre),
                "output_sha256": sha256(out.read_bytes()) if out.exists() else None,
                "observation": obs,
                "stderr": proc.stderr,
                "errors": errors,
            }
            rows.append(record)
            status = "PASS" if not errors else "FAIL"
            print(f"{status} {case.id}")
            for error in errors:
                print(f"  {error}")
            failures += bool(errors)

    evidence_bytes = b"".join(
        (json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode()
        for row in rows
    )
    evidence_hash = sha256(evidence_bytes)

    if args.evidence:
        evidence_dir = Path(args.evidence)
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "observations.partial.jsonl").write_bytes(evidence_bytes)
        (evidence_dir / "PROVENANCE.md").write_text(
            "# P1-R25 respool partial product evidence\n\n"
            f"- Product commit: {product_commit}\n"
            f"- Imported respool verifier tree: {package_tree}\n"
            "- Verifier source publication: 6519220f161254c0453a30858eb3e7073e2eb82b\n"
            f"- observations.partial.jsonl SHA-256: {evidence_hash}\n"
            "- Adapter: tests/respool_adapter/wp12_respool_probe.c\n"
            "- Verdict source: unchanged tests/respool_draft8/oracle.py\n"
            "- Scope: seven cases whose verifier scripts call tape_respool only.\n"
            "- Blocker: WP12-EMPTY also calls tape_promote; authoritative promote behavior belongs to Software #155 and is not emulated here.\n"
        )

    passed = len(rows) - failures
    print()
    print(f"product_commit={product_commit}")
    print(f"respool_verifier_tree={package_tree}")
    print(f"partial_evidence_sha256={evidence_hash}")
    print(f"{passed}/{len(rows)} non-promote respool cases pass against the product engine.")
    print(f"BLOCKED {BLOCKED_CASE}: requires authoritative product tape_promote from Software #155.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
