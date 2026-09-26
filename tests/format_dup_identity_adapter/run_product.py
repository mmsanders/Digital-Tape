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
VERIFIER_TREE = "f76ab23d17beb9212f8ee1d17d3d1875b74abc7d"
VERIFIER_PUBLICATION = "50c47c1b9087de52f66d831ef2fe00cc02273087"
IMPORT_COMMIT = "69496d184761a1b66d3d921e420f9725bdc6c5d1"
PRODUCT_BASE = "7910ae3701fbfd94b5ea0558a69a29955da1dd5c"
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
    # The declared identities are checked against history before any case
    # runs, so evidence cannot cite a base or import this branch does not have
    # (the R29-C provenance finding, Verification PR #79 / #244).
    if subprocess.run(["git", "merge-base", "--is-ancestor", IMPORT_COMMIT, "HEAD"],
                      cwd=ROOT).returncode != 0:
        raise SystemExit(f"verifier import {IMPORT_COMMIT} is not an ancestor of HEAD")
    if git("rev-parse", f"{IMPORT_COMMIT}^") != PRODUCT_BASE:
        raise SystemExit(f"import parent is not the declared product base {PRODUCT_BASE}")
    if git("rev-parse", f"{IMPORT_COMMIT}:tests/format_dup_identity_draft8") != VERIFIER_TREE:
        raise SystemExit(f"verifier import {IMPORT_COMMIT} does not carry tree {VERIFIER_TREE}")
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
        "product_base": PRODUCT_BASE,
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
