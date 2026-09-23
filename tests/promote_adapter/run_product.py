#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "tests" / "promote_draft8"
EXPECTED_TREE = "2b79e0b07016da3521917c5a276e36994ccccfa6"
VERIFIER_COMMIT = "e5e06b06f1aa0755a3b0b15133f1ce680e17f7af"
ADAPTER_ID = "p1-r25-promote-product-v1"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--probe",
        default=str(ROOT / "tests/promote_adapter/build/wp_promote_probe"),
    )
    ap.add_argument("--evidence", required=True)
    args = ap.parse_args()

    probe = Path(args.probe)
    if not probe.is_file():
        raise SystemExit(f"probe not found: {probe}")

    package_tree = git("rev-parse", "HEAD:tests/promote_draft8")
    if package_tree != EXPECTED_TREE:
        raise SystemExit(
            f"promote verifier tree mismatch: {package_tree} != {EXPECTED_TREE}"
        )

    product_commit = os.environ.get("PRODUCT_COMMIT") or git("rev-parse", "HEAD")
    cmd = [
        sys.executable,
        str(PKG / "runner.py"),
        "--adapter-cmd",
        str(probe),
        "--adapter-kind",
        "product",
        "--adapter-id",
        ADAPTER_ID,
        "--adapter-source",
        str(ROOT / "tests/promote_adapter/wp_promote_probe.c"),
        "--adapter-build",
        "make -C engine all && make -C tests/promote_adapter all",
        "--product-commit",
        product_commit,
        "--verifier-commit",
        VERIFIER_COMMIT,
        "--evidence-dir",
        args.evidence,
    ]
    print(f"product_commit={product_commit}")
    print(f"promote_verifier_tree={package_tree}")
    print(f"verifier_publication={VERIFIER_COMMIT}")
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
