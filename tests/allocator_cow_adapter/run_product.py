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
HERE = Path(__file__).resolve().parent
PKG = ROOT / "tests" / "allocator_cow_draft8"
ADAPTER = HERE / "adapter.py"
WORKER = HERE / "build" / "wp07_product_worker"
EXPECTED_TREE = "41d07601186856afccde00107a85f27e2423bb2a"
VERIFIER_PUBLICATION = "b0271d0805e1193de354f9244d1830bc163c7054"
IMPORT_COMMIT = "7ac78154a4024288ef34c21b8fd0d5c95b3bace2"
PRODUCT_BASE = "92d6a3402d4908322c191bd3464011ae97f94114"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def version(cmd: list[str]) -> str:
    p = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    text = (p.stdout or p.stderr).strip()
    return text.splitlines()[0] if text else f"{cmd[0]} version unavailable"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--evidence", type=Path, required=True)
    args = p.parse_args()

    evidence = args.evidence if args.evidence.is_absolute() else ROOT / args.evidence
    if evidence.exists():
        shutil.rmtree(evidence)
    evidence.mkdir(parents=True)

    if not ADAPTER.is_file() or not WORKER.is_file():
        raise SystemExit("WP-07 adapter/worker missing")
    verifier_tree = git("rev-parse", "HEAD:tests/allocator_cow_draft8")
    if verifier_tree != EXPECTED_TREE:
        raise SystemExit(f"verifier tree mismatch: {verifier_tree}")
    head = git("rev-parse", "HEAD")
    product_commit = os.environ.get("PRODUCT_COMMIT") or head
    if product_commit != head:
        raise SystemExit(f"workspace/head mismatch: {head} != {product_commit}")
    product_tree = git("rev-parse", "HEAD^{tree}")

    build_log = HERE / "build.log"
    if not build_log.is_file():
        raise SystemExit("retained adapter build.log missing")

    cmd = [
        sys.executable,
        str(PKG / "runner.py"),
        "--adapter",
        str(ADAPTER),
        "--evidence",
        str(evidence),
    ]
    proc = subprocess.run(cmd, cwd=ROOT)

    for src in ("adapter.py", "wp07_product_worker.c", "Makefile"):
        shutil.copy2(HERE / src, evidence / src)
    shutil.copy2(build_log, evidence / "build.log")

    summary = evidence / "summary.json"
    failure = evidence / "failure-reproducer.json"
    tools = {
        "cc": version([os.environ.get("CC", "cc"), "--version"]),
        "python": sys.version.splitlines()[0],
        "make": version(["make", "--version"]),
    }
    provenance = {
        "product_base": PRODUCT_BASE,
        "verifier_import_commit": IMPORT_COMMIT,
        "product_commit": product_commit,
        "product_tree": product_tree,
        "verifier_publication": VERIFIER_PUBLICATION,
        "verifier_tree": verifier_tree,
        "adapter_source_sha256": sha256_file(ADAPTER),
        "worker_source_sha256": sha256_file(HERE / "wp07_product_worker.c"),
        "worker_binary_sha256": sha256_file(WORKER),
        "engine_archive_sha256": sha256_file(ROOT / "build/engine/libtape.a"),
        "build_log_sha256": sha256_file(build_log),
        "summary_sha256": sha256_file(summary) if summary.is_file() else "MISSING",
        "failure_reproducer_sha256": sha256_file(failure) if failure.is_file() else None,
        "runner_exit": proc.returncode,
        "tool_versions": tools,
    }
    (evidence / "PROVENANCE.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"product_commit={product_commit}")
    print(f"product_tree={product_tree}")
    print(f"verifier_import_commit={IMPORT_COMMIT}")
    print(f"verifier_tree={verifier_tree}")
    print(f"adapter_source_sha256={provenance['adapter_source_sha256']}")
    print(f"worker_source_sha256={provenance['worker_source_sha256']}")
    print(f"worker_binary_sha256={provenance['worker_binary_sha256']}")
    print(f"summary_sha256={provenance['summary_sha256']}")
    print(f"failure_reproducer_sha256={provenance['failure_reproducer_sha256']}")
    print(f"runner_exit={proc.returncode}")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
