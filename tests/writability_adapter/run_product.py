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
PKG = ROOT / "tests" / "writability_draft8"
EXPECTED_TREE = "786221daaf80d15406d9cccf19691c2337ff5908"
VERIFIER_PUBLICATION = "d875730ee5cedc6b88e40fcfe30aa4d81918f549"


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
        default=str(ROOT / "tests" / "writability_adapter" / "build" / "wp06a_probe"),
    )
    ap.add_argument("--evidence", required=True)
    args = ap.parse_args()

    probe = Path(args.probe).resolve()
    if not probe.is_file():
        raise SystemExit(f"probe not found: {probe}")

    package_tree = git("rev-parse", "HEAD:tests/writability_draft8")
    if package_tree != EXPECTED_TREE:
        raise SystemExit(
            f"writability verifier tree mismatch: {package_tree} != {EXPECTED_TREE}"
        )

    product_commit = os.environ.get("PRODUCT_COMMIT") or git("rev-parse", "HEAD")
    evidence = Path(args.evidence)
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

    (evidence / "PROVENANCE.md").write_text(
        "# P1-R25 writability product evidence\n\n"
        f"- Product commit: {product_commit}\n"
        f"- Imported writability verifier tree: {package_tree}\n"
        f"- Verifier source publication: {VERIFIER_PUBLICATION}\n"
        f"- Verifier probe: tests/writability_draft8/wp06a_probe.c (unchanged)\n"
        f"- Verifier runner/oracle: tests/writability_draft8/runner.py + oracle.py (unchanged)\n"
        f"- Linked product probe SHA-256: {probe_hash}\n"
        f"- observations.jsonl SHA-256: {observations_hash}\n"
        f"- Verifier runner exit: {proc.returncode}\n"
        "- Scope: all eight published WP-06a v1.1 effective-writability cases.\n"
    )

    print()
    print(f"product_commit={product_commit}")
    print(f"writability_verifier_tree={package_tree}")
    print(f"probe_sha256={probe_hash}")
    print(f"observations_sha256={observations_hash}")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
