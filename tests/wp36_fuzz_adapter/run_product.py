#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "tests" / "wp36_fuzz_draft8"
EXPECTED_TREE = "9ac9c43962b49c98f7007983921be9500a51cb5a"
VERIFIER_PUBLICATION = "c65df73abaf2624e99ac3c06b8c864a445d81ec2"
IMPORT_COMMIT = "c9c8a107a365ffefe5be2d87fad292b09a879723"
EXPECTED_PLAN = "6a6637336eff798e6c7824af76e3d4f227eefcd9ff35e7850a14fd14a1d22bae"
EXPECTED_SEED = "5730365a5eed2026"
EXPECTED_SEQUENCES = 100_000
EXPECTED_OPS = 1_997_914


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
        "--adapter",
        default=str(
            ROOT / "tests/wp36_fuzz_adapter/build/wp36_fuzz_product_adapter"
        ),
    )
    ap.add_argument("--evidence", required=True)
    args = ap.parse_args()

    adapter = Path(args.adapter).resolve()
    if not adapter.is_file():
        raise SystemExit(f"adapter not found: {adapter}")

    package_tree = git("rev-parse", "HEAD:tests/wp36_fuzz_draft8")
    if package_tree != EXPECTED_TREE:
        raise SystemExit(
            f"WP-36 fuzz verifier tree mismatch: {package_tree} != {EXPECTED_TREE}"
        )

    product_commit = os.environ.get("PRODUCT_COMMIT") or git("rev-parse", "HEAD")
    product_tree = git("rev-parse", "HEAD^{tree}")
    source = ROOT / "tests/wp36_fuzz_adapter/wp36_fuzz_product_adapter.c"
    evidence = Path(args.evidence)
    if not evidence.is_absolute():
        evidence = ROOT / evidence
    if evidence.exists():
        shutil.rmtree(evidence)
    evidence.mkdir(parents=True)

    cmd = [
        sys.executable,
        str(PKG / "runner.py"),
        "--adapter",
        str(adapter),
        "--evidence",
        str(evidence),
    ]
    proc = subprocess.run(cmd, cwd=ROOT)
    runner_exit = proc.returncode

    summary_path = evidence / "summary.json"
    summary_hash = sha256_file(summary_path) if summary_path.is_file() else "MISSING"
    summary = None
    provenance_ok = False
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        gen = summary.get("generator", {})
        census = summary.get("coverage_census", {})
        hs = summary.get("adapter_handshake", {})
        provenance_ok = (
            summary.get("completed_sequences") == EXPECTED_SEQUENCES
            and gen.get("rng_algorithm") == "splitmix64-v1"
            and gen.get("master_seed") == EXPECTED_SEED
            and gen.get("sequence_count") == EXPECTED_SEQUENCES
            and gen.get("plan_sha256") == EXPECTED_PLAN
            and census.get("total_ops") == EXPECTED_OPS
            and hs.get("adapter_kind") == "product"
            and hs.get("source_write_binding") == "NULL"
            and hs.get("assertion_mode") == "debug"
            and summary.get("normal_exit") is True
            and summary.get("assertion_or_crash") is False
        )

    source_hash = sha256_file(source)
    binary_hash = sha256_file(adapter)
    repro_json = evidence / "failure-reproducer.json"
    repro_plan = evidence / "failure-reproducer.plan"

    lines = [
        "# P1-R26 WP-36 100k source-slot product evidence",
        "",
        f"- Product base: 482eb864036d6221fda2936429addd3189254aa5",
        f"- Verifier import commit (commit 1): {IMPORT_COMMIT}",
        f"- Product binding head (commit 2): {product_commit}",
        f"- Product binding tree: {product_tree}",
        f"- Verifier publication: {VERIFIER_PUBLICATION}",
        f"- Imported verifier tree: {package_tree}",
        "- Engine assertion build: clean engine rebuild with CFLAGS=-UNDEBUG.",
        "- Adapter assertion build: -UNDEBUG and compile-time failure if NDEBUG is defined.",
        "- Source write binding: literal tape_dev.write = NULL.",
        f"- Adapter source SHA-256: {source_hash}",
        f"- Linked adapter SHA-256: {binary_hash}",
        f"- Verifier runner exit: {runner_exit}",
        f"- summary.json SHA-256: {summary_hash}",
        f"- Exact provenance validation: {'PASS' if provenance_ok else 'FAIL'}",
    ]
    if summary is not None:
        lines += [
            f"- Completed sequences: {summary.get('completed_sequences')}",
            f"- RNG: {summary.get('generator', {}).get('rng_algorithm')}",
            f"- Master seed: {summary.get('generator', {}).get('master_seed')}",
            f"- Plan SHA-256: {summary.get('generator', {}).get('plan_sha256')}",
            f"- Operation census: {summary.get('coverage_census', {}).get('total_ops')}",
            f"- Normal exit: {summary.get('normal_exit')}",
            f"- Assertion/crash: {summary.get('assertion_or_crash')}",
            f"- Adapter handshake: {json.dumps(summary.get('adapter_handshake', {}), sort_keys=True)}",
        ]
    if repro_json.is_file():
        lines.append(f"- Failure reproducer JSON SHA-256: {sha256_file(repro_json)}")
    if repro_plan.is_file():
        lines.append(f"- Failure reproducer plan SHA-256: {sha256_file(repro_plan)}")
    (evidence / "PROVENANCE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"product_commit={product_commit}")
    print(f"product_tree={product_tree}")
    print(f"verifier_import_commit={IMPORT_COMMIT}")
    print(f"wp36_fuzz_verifier_tree={package_tree}")
    print(f"adapter_source_sha256={source_hash}")
    print(f"adapter_binary_sha256={binary_hash}")
    print(f"runner_exit={runner_exit}")
    print(f"summary_sha256={summary_hash}")
    print(f"provenance_validation={'PASS' if provenance_ok else 'FAIL'}")

    if runner_exit != 0:
        return runner_exit
    return 0 if provenance_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
