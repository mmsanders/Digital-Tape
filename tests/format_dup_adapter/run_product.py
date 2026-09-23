#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "tests" / "format_dup_draft8"
EXPECTED_TREE = "83a6d03942d59ecbf6d0c2d0ad646c92d2da0459"
VERIFIER_COMMIT = "982bac2cfb63ca3037d59be3887b2d66de065a34"
ADAPTER_ID = "p1-r25-format-dup-product-v1"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--probe",
        default=str(ROOT / "tests/format_dup_adapter/build/wp_fmt_dup_probe"),
    )
    ap.add_argument("--evidence", required=True)
    args = ap.parse_args()

    probe = Path(args.probe)
    if not probe.is_file():
        raise SystemExit(f"probe not found: {probe}")

    package_tree = git("rev-parse", "HEAD:tests/format_dup_draft8")
    if package_tree != EXPECTED_TREE:
        raise SystemExit(
            f"format/dup verifier tree mismatch: {package_tree} != {EXPECTED_TREE}"
        )

    product_commit = os.environ.get("PRODUCT_COMMIT") or git("rev-parse", "HEAD")
    product_tree = git("rev-parse", "HEAD^{tree}")

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
        str(ROOT / "tests/format_dup_adapter/wp_fmt_dup_probe.c"),
        "--adapter-build",
        "make -C engine all && make -C tests/format_dup_adapter all",
        "--source-commit",
        product_commit,
        "--source-tree",
        product_tree,
        "--evidence-dir",
        args.evidence,
    ]
    print(f"product_commit={product_commit}")
    print(f"product_tree={product_tree}")
    print(f"format_dup_verifier_tree={package_tree}")
    print(f"verifier_publication={VERIFIER_COMMIT}")
    return subprocess.call(cmd, cwd=PKG)


if __name__ == "__main__":
    raise SystemExit(main())
