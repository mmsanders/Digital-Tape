#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PKG = ROOT / "tests" / "crash_core_draft8"
sys.path.insert(0, str(PKG))
from planner import EXPECTED_CASESET_SHA256, case_counts, iter_cases  # noqa: E402
ADAPTER = HERE / "adapter.py"
WORKER = HERE / "build" / "wp10_core_worker"
PRODUCT_BASE = "92d6a3402d4908322c191bd3464011ae97f94114"
IMPORT_COMMIT = "01850817c2f0b3c3f5f2ce47c77ea5f5da92c9c9"
VERIFIER_PUBLICATION = "18ff453e80fa245ad2d10066a1df262b443905b7"
VERIFIER_TREE = "d99aa7d095ea9ee7228d6bddddd682848dfb8a55"


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
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", required=True, type=Path)
    args = ap.parse_args()
    evidence = args.evidence if args.evidence.is_absolute() else ROOT / args.evidence
    if evidence.exists():
        shutil.rmtree(evidence)
    evidence.mkdir(parents=True)

    head = git("rev-parse", "HEAD")
    tree = git("rev-parse", "HEAD^{tree}")
    product_commit = os.environ.get("PRODUCT_COMMIT") or head
    if product_commit != head:
        raise SystemExit(f"workspace/head mismatch {head} != {product_commit}")
    verifier_tree = git("rev-parse", "HEAD:tests/crash_core_draft8")
    if verifier_tree != VERIFIER_TREE:
        raise SystemExit(f"verifier tree mismatch {verifier_tree}")

    build_log = HERE / "build.log"
    if not WORKER.is_file() or not ADAPTER.is_file() or not build_log.is_file():
        raise SystemExit("adapter build products missing")

    cmd = [
        sys.executable,
        str(PKG / "runner.py"),
        "--adapter",
        str(ADAPTER),
        "--evidence",
        str(evidence),
    ]
    baseline_path = evidence / "baselines.json"
    run_env = os.environ.copy()
    run_env["WP10_BASELINE_EVIDENCE"] = str(baseline_path)
    proc = subprocess.run(cmd, cwd=ROOT, env=run_env)

    for src in ("adapter.py", "wp10_core_worker.c", "Makefile"):
        shutil.copy2(HERE / src, evidence / src)
    shutil.copy2(build_log, evidence / "build.log")

    summary = evidence / "summary.json"
    failure = evidence / "failure-reproducer.json"
    stderr = evidence / "adapter.stderr.txt"

    failed_payload = json.loads(failure.read_text(encoding="utf-8")) if failure.is_file() else None
    failed_index = (
        failed_payload.get("case", {}).get("case_index")
        if isinstance(failed_payload, dict)
        else None
    )
    completed = failed_index if isinstance(failed_index, int) else case_counts()["total_injection_cases"]
    by_mode = Counter()
    by_family_variant = Counter()
    by_scope = Counter()
    for i, case in enumerate(iter_cases()):
        if i >= completed:
            break
        by_mode[case["mode"]] += 1
        by_family_variant[f'{case["family"]}:{case["variant"]}'] += 1
        by_scope[case["scope"]] += 1

    software_summary = {
        "format": "WP10-CORE-SOFTWARE-PARTIAL-SUMMARY-1",
        "runner_exit": proc.returncode,
        "caseset_sha256": EXPECTED_CASESET_SHA256,
        "planned_counts": case_counts(),
        "completed_injection_cases": completed,
        "completed_census": {
            "by_mode": dict(sorted(by_mode.items())),
            "by_family_variant": dict(sorted(by_family_variant.items())),
            "by_scope": dict(sorted(by_scope.items())),
        },
        "failed_case": failed_payload.get("case") if isinstance(failed_payload, dict) else None,
        "failure_error": failed_payload.get("error") if isinstance(failed_payload, dict) else None,
        "v7_closure_completed": int(by_scope.get("closure", 0)),
        "baseline_keys": (
            sorted(json.loads(baseline_path.read_text(encoding="utf-8")).get("baselines", {}))
            if baseline_path.is_file()
            else []
        ),
    }
    software_summary_path = evidence / "software-summary.json"
    software_summary_path.write_text(
        json.dumps(software_summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    provenance = {
        "product_base": PRODUCT_BASE,
        "verifier_import_commit": IMPORT_COMMIT,
        "product_commit": product_commit,
        "product_tree": tree,
        "verifier_publication": VERIFIER_PUBLICATION,
        "verifier_tree": verifier_tree,
        "adapter_source_sha256": sha256_file(ADAPTER),
        "worker_source_sha256": sha256_file(HERE / "wp10_core_worker.c"),
        "worker_binary_sha256": sha256_file(WORKER),
        "engine_archive_sha256": sha256_file(ROOT / "build/engine/libtape.a"),
        "build_log_sha256": sha256_file(build_log),
        "summary_sha256": sha256_file(summary) if summary.is_file() else None,
        "software_summary_sha256": sha256_file(software_summary_path),
        "baselines_sha256": sha256_file(baseline_path) if baseline_path.is_file() else None,
        "failure_reproducer_sha256": sha256_file(failure) if failure.is_file() else None,
        "adapter_stderr_sha256": sha256_file(stderr) if stderr.is_file() else None,
        "runner_exit": proc.returncode,
        "tool_versions": {
            "cc": version([os.environ.get("CC", "cc"), "--version"]),
            "make": version(["make", "--version"]),
            "python": sys.version.splitlines()[0],
            "openssl": version(["openssl", "version"]),
        },
        "build_command": "make -C tests/crash_core_adapter clean all",
    }
    (evidence / "PROVENANCE.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"product_commit={product_commit}")
    print(f"product_tree={tree}")
    print(f"verifier_import_commit={IMPORT_COMMIT}")
    print(f"verifier_tree={verifier_tree}")
    print(f"adapter_source_sha256={provenance['adapter_source_sha256']}")
    print(f"worker_source_sha256={provenance['worker_source_sha256']}")
    print(f"worker_binary_sha256={provenance['worker_binary_sha256']}")
    print(f"completed_injection_cases={completed}")
    print(f"software_summary_sha256={provenance['software_summary_sha256']}")
    print(f"baselines_sha256={provenance['baselines_sha256']}")
    print(f"failure_reproducer_sha256={provenance['failure_reproducer_sha256']}")
    print(f"adapter_stderr_sha256={provenance['adapter_stderr_sha256']}")
    print(f"runner_exit={proc.returncode}")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
