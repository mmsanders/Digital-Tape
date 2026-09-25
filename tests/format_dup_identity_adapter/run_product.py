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
PKG = ROOT / "tests" / "format_dup_identity_draft8"
ADAPTER = HERE / "adapter.py"
WORKER = HERE / "build" / "r29_format_dup_worker"
VERIFIER_TREE = "bd81f66d515c4f71e03efc6edd55f70d1d0383da"
VERIFIER_PUBLICATION = "db3569b6f99bf009ed74680e02ff03d4cdbc8689"
IMPORT_COMMIT = "9f2ff3efaa40e367a5b3633211333c7bfcc2e539"
ADAPTER_ID = "digital-tape-r29-format-dup-product"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", required=True, type=Path)
    a = ap.parse_args()
    evidence = a.evidence if a.evidence.is_absolute() else ROOT / a.evidence
    if evidence.exists():
        shutil.rmtree(evidence)

    head = git("rev-parse", "HEAD")
    tree = git("rev-parse", "HEAD^{tree}")
    product_commit = os.environ.get("PRODUCT_COMMIT") or head
    if product_commit != head:
        raise SystemExit(f"workspace/head mismatch {head} != {product_commit}")
    verifier_tree = git("rev-parse", "HEAD:tests/format_dup_identity_draft8")
    if verifier_tree != VERIFIER_TREE:
        raise SystemExit(f"verifier tree mismatch {verifier_tree}")
    if not ADAPTER.is_file() or not WORKER.is_file():
        raise SystemExit("adapter build products missing")

    cmd = [
        sys.executable, str(PKG / "runner.py"),
        "--adapter-cmd", f"{sys.executable} {ADAPTER}",
        "--adapter-id", ADAPTER_ID,
        "--adapter-source", str(ADAPTER),
        "--adapter-build", str(WORKER),
        "--source-commit", product_commit,
        "--source-tree", tree,
        "--publication-commit", VERIFIER_PUBLICATION,
        "--publication-tree", verifier_tree,
        "--evidence-dir", str(evidence),
    ]
    proc = subprocess.run(cmd, cwd=ROOT)

    evidence.mkdir(parents=True, exist_ok=True)
    for name in ("adapter.py", "r29_format_dup_worker.c", "Makefile"):
        shutil.copy2(HERE / name, evidence / name)
    build_log = HERE / "build.log"
    if build_log.is_file():
        shutil.copy2(build_log, evidence / "build.log")

    provenance = {
        "product_base": "8276d8f22da34a53f9f52dae8d3bd1acb3c763d9",
        "verifier_import_commit": IMPORT_COMMIT,
        "product_commit": product_commit,
        "product_tree": tree,
        "verifier_publication": VERIFIER_PUBLICATION,
        "verifier_tree": verifier_tree,
        "adapter_source_sha256": sha256_file(ADAPTER),
        "worker_source_sha256": sha256_file(HERE / "r29_format_dup_worker.c"),
        "worker_binary_sha256": sha256_file(WORKER),
        "engine_archive_sha256": sha256_file(ROOT / "build/engine/libtape.a"),
        "build_log_sha256": sha256_file(build_log) if build_log.is_file() else None,
        "runner_exit": proc.returncode,
    }
    for name in ("summary.json", "failure-reproducer.json", "adapter-stderr.txt", "manifest.json"):
        p = evidence / name
        provenance[name + "_sha256"] = sha256_file(p) if p.is_file() else None
    (evidence / "SOFTWARE-PROVENANCE.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(provenance, indent=2, sort_keys=True))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
