#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "tests" / "slot_draft8"
EXPECTED_TREE = "14860665f297d03867cc1098a02d3f6495a6d935"
VERIFIER_PUBLICATION = "6fc4014a4afa088cbba49c8306f72a77bd3291d8"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--probe",
        default=str(ROOT / "tests/slot_adapter/build/wp36_slot_probe"),
    )
    ap.add_argument("--evidence", required=True)
    args = ap.parse_args()

    probe = Path(args.probe).resolve()
    if not probe.is_file():
        raise SystemExit(f"probe not found: {probe}")

    package_tree = git("rev-parse", "HEAD:tests/slot_draft8")
    if package_tree != EXPECTED_TREE:
        raise SystemExit(
            f"slot verifier tree mismatch: {package_tree} != {EXPECTED_TREE}"
        )

    product_commit = os.environ.get("PRODUCT_COMMIT") or git("rev-parse", "HEAD")
    product_tree = git("rev-parse", "HEAD^{tree}")
    evidence = Path(args.evidence)
    if not evidence.is_absolute():
        evidence = ROOT / evidence
    if evidence.exists():
        shutil.rmtree(evidence)
    evidence.mkdir(parents=True)

    observations = evidence / "observations.jsonl"
    cmd = [
        sys.executable,
        str(PKG / "runner.py"),
        "--adapter",
        str(probe),
        "--log",
        str(observations),
    ]
    proc = subprocess.run(cmd, cwd=ROOT)

    observations_hash = (
        sha256_file(observations) if observations.is_file() else "MISSING"
    )
    probe_hash = sha256_file(probe)
    source_hash = sha256_file(ROOT / "tests/slot_adapter/wp36_slot_probe.c")

    (evidence / "PROVENANCE.md").write_text(
        "# P1-R25 WP-36 deterministic source-slot product evidence\n\n"
        f"- Product commit: {product_commit}\n"
        f"- Product tree: {product_tree}\n"
        f"- Imported slot verifier tree: {package_tree}\n"
        f"- Verifier publication: {VERIFIER_PUBLICATION}\n"
        "- Source device binding: literal tape_dev.write = NULL in "
        "tests/slot_adapter/wp36_slot_probe.c.\n"
        "- Debug assertion build: engine and adapter compiled with -UNDEBUG; "
        "adapter compilation fails if NDEBUG is defined.\n"
        f"- Adapter source SHA-256: {source_hash}\n"
        f"- Linked product probe SHA-256: {probe_hash}\n"
        f"- observations.jsonl SHA-256: {observations_hash}\n"
        f"- Verifier runner exit: {proc.returncode}\n"
        "- Scope: all five deterministic published WP-36 precursor cases; "
        "the separate 100,000-sequence acceptance run is excluded.\n"
    )

    print()
    print(f"product_commit={product_commit}")
    print(f"product_tree={product_tree}")
    print(f"slot_verifier_tree={package_tree}")
    print(f"adapter_source_sha256={source_hash}")
    print(f"probe_sha256={probe_hash}")
    print(f"observations_sha256={observations_hash}")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
