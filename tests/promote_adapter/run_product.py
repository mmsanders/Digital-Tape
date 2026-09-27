#!/usr/bin/env python3
"""Run the imported R29-A promote verifier against the real engine.

Checks the declared base, import and verifier tree against git history before
any case runs, then hands the verifier's own runner.py the product adapter.
The runner stops at the first failing case and retains failure-reproducer.json;
a green run is retained evidence, not acceptance.
"""
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
PKG = ROOT / "tests" / "promote_draft8"
ADAPTER = HERE / "adapter.py"
WORKER_SRC = HERE / "r29a_promote_worker.c"
WORKER = HERE / "build" / "r29a_promote_worker"
VERIFIER_TREE = "2eb707d7e8ea721085164b85f5e2f397e115a036"
VERIFIER_PUBLICATION = "91c39358c2c40ef3a06b3571211cf65e03b7fd28"
IMPORT_COMMIT = "8886aa39868b006e057380b94befa818349a188d"
PRODUCT_BASE = "867fd4ab3a447aca0a2b7bcc37aae444edce5e15"


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
    verifier_tree = git("rev-parse", "HEAD:tests/promote_draft8")
    if verifier_tree != VERIFIER_TREE:
        raise SystemExit(f"verifier tree mismatch {verifier_tree}")
    if subprocess.run(["git", "merge-base", "--is-ancestor", IMPORT_COMMIT, "HEAD"],
                      cwd=ROOT).returncode != 0:
        raise SystemExit(f"verifier import {IMPORT_COMMIT} is not an ancestor of HEAD")
    if git("rev-parse", f"{IMPORT_COMMIT}^") != PRODUCT_BASE:
        raise SystemExit(f"import parent is not the declared product base {PRODUCT_BASE}")
    if git("rev-parse", f"{IMPORT_COMMIT}:tests/promote_draft8") != VERIFIER_TREE:
        raise SystemExit(f"verifier import {IMPORT_COMMIT} does not carry tree {VERIFIER_TREE}")
    if not WORKER.is_file():
        raise SystemExit("worker build product missing")

    adapter_source = hashlib.sha256(ADAPTER.read_bytes() + WORKER_SRC.read_bytes()).hexdigest()
    cmd = [
        sys.executable, str(PKG / "runner.py"),
        "--adapter", sys.executable,
        "--adapter-arg", str(ADAPTER),
        "--adapter-source-sha256", adapter_source,
        "--adapter-build-sha256", sha256_file(WORKER),
        "--source-commit", product_commit,
        "--source-tree", tree,
        "--publication-commit", VERIFIER_PUBLICATION,
        "--publication-tree", verifier_tree,
        "--out-dir", str(evidence),
        "--timeout-s", "60",
    ]
    proc = subprocess.run(cmd, cwd=ROOT)

    evidence.mkdir(parents=True, exist_ok=True)
    for name in ("adapter.py", "r29a_promote_worker.c", "Makefile", "diagnostic_sweep.py"):
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
        "worker_source_sha256": sha256_file(WORKER_SRC),
        "adapter_plus_worker_source_sha256": adapter_source,
        "worker_binary_sha256": sha256_file(WORKER),
        "engine_archive_sha256": sha256_file(ROOT / "build/engine/libtape.a"),
        "build_log_sha256": sha256_file(build_log) if build_log.is_file() else None,
        "runner_exit": proc.returncode,
    }
    for name in ("summary.json", "summary.sha256", "failure-reproducer.json", "adapter-stderr.txt"):
        p = evidence / name
        provenance[name + "_sha256"] = sha256_file(p) if p.is_file() else None
    (evidence / "SOFTWARE-PROVENANCE.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(provenance, indent=2, sort_keys=True))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
