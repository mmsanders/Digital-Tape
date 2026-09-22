#!/usr/bin/env python3
"""Run the unchanged transport_draft8 verifier against the real product engine."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent / "transport_draft8"
sys.path.insert(0, str(PKG))

from oracle import Media, check, fixture_contract_errors, make_cases  # noqa: E402

OBS_FORMAT = "WP-TRANSPORT-OBSERVATION-1"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(adapter: Path, workdir: Path, evidence: Path | None) -> int:
    workdir.mkdir(parents=True, exist_ok=True)
    if evidence is not None:
        evidence.mkdir(parents=True, exist_ok=True)

    records = []
    failures = 0
    for case in make_cases():
        errors = list(fixture_contract_errors(case))
        inp = workdir / f"{case.id}.in.vo08"
        out = workdir / f"{case.id}.out.vo08"
        inp.write_bytes(case.pre.encode())
        if out.exists():
            out.unlink()

        proc = subprocess.run(
            [str(adapter), case.id, str(inp), str(out)],
            capture_output=True,
            text=True,
            timeout=600,
        )
        rec = {
            "case": case.id,
            "argv": [adapter.name, case.id],
            "exit": proc.returncode,
            "input_sha256": sha256(inp.read_bytes()),
            "stderr": proc.stderr.strip(),
        }
        if proc.returncode != 0:
            errors.append(f"adapter exit {proc.returncode}")
        if not out.exists():
            errors.append("adapter wrote no output media")
        else:
            rec["output_sha256"] = sha256(out.read_bytes())

        obs = None
        try:
            obs = json.loads(proc.stdout)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"adapter stdout is not one JSON object: {exc}")

        if obs is not None:
            rec["observation"] = obs
            if obs.get("format") != OBS_FORMAT:
                errors.append(f"observation format {obs.get('format')!r}")
            if obs.get("adapter_kind") != "product":
                errors.append(f"adapter_kind {obs.get('adapter_kind')!r} is not product")
            if obs.get("event_overflow"):
                errors.append("adapter event trace overflowed")

        if obs is not None and out.exists():
            post = Media.decode(out.read_bytes())
            errors.extend(check(case, post, obs.get("events", []), obs.get("calls", [])))

        rec["errors"] = errors
        records.append(rec)
        if errors:
            failures += 1
            print(f"FAIL {case.id}")
            for error in errors:
                print(f"       {error}")
        else:
            print(f"PASS {case.id}")

    total = len(records)
    print(f"\n{total - failures}/{total} transport/warm cases pass against the product engine.")
    print("Product observation only. Independent Verification owns disposition.")

    if evidence is not None:
        path = evidence / "observations.jsonl"
        with path.open("w") as f:
            for rec in records:
                f.write(json.dumps(rec, sort_keys=True) + "\n")
        print(f"evidence: {path} sha256={sha256(path.read_bytes())}")

    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", default=str(HERE / "build" / "wp_transport_probe"))
    ap.add_argument("--workdir", default=str(HERE / "build" / "media"))
    ap.add_argument("--evidence", default=None)
    args = ap.parse_args()
    adapter = Path(args.adapter).resolve()
    if not adapter.exists():
        print(f"adapter not built: {adapter}", file=sys.stderr)
        return 2
    return run(
        adapter,
        Path(args.workdir),
        Path(args.evidence) if args.evidence else None,
    )


if __name__ == "__main__":
    raise SystemExit(main())
