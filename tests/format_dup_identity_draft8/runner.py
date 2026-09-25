#!/usr/bin/env python3
"""Production evidence runner for the independent R29 format/dup verifier package."""
from __future__ import annotations
import argparse, hashlib, json, selectors, shlex, subprocess
from pathlib import Path

from oracle import VerificationError, failure_reproducer, validate_case
from planner import EXPECTED_CASESET_SHA256, EXPECTED_TOTAL_CASES, counts, iter_cases

HERE = Path(__file__).resolve().parent
PACKAGE_FILES = (
    "ADAPTER.md", "COVERAGE.md", "README.md", "fixture.py", "media.py",
    "oracle.py", "planner.py", "runner.py", "selftest.py", "synthetic_adapter.py",
)

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def fresh_dir(path: Path) -> None:
    if path.exists():
        if not path.is_dir() or any(path.iterdir()):
            raise VerificationError("evidence directory must be empty")
    else:
        path.mkdir(parents=True)

def read_json_line(proc, selector, timeout_s: float):
    events = selector.select(timeout_s)
    if not events:
        raise VerificationError("adapter timeout")
    line = proc.stdout.readline()
    if line == "":
        raise VerificationError("adapter EOF")
    try:
        return json.loads(line)
    except json.JSONDecodeError as e:
        raise VerificationError("adapter emitted malformed JSON") from e

def run_session(adapter_cmd: str, evidence_dir: Path, *, adapter_id: str,
                timeout_s: float, provenance: dict, expected_kind: str = "product"):
    fresh_dir(evidence_dir)
    stderr_path = evidence_dir / "adapter-stderr.txt"
    errf = stderr_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        shlex.split(adapter_cmd), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=errf, text=True, bufsize=1,
    )
    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ)
    summary = {
        "format": "FMTDUP-ID-SUMMARY-1", "pass": False,
        "expected_injection_and_contract_cases": EXPECTED_TOTAL_CASES,
        "completed_cases": 0, "counts": counts(),
        "caseset_sha256": EXPECTED_CASESET_SHA256,
    }
    try:
        hello = read_json_line(proc, selector, timeout_s)
        if hello.get("format") != "FMTDUP-ID-ADAPTER-1":
            raise VerificationError("adapter handshake format")
        if hello.get("adapter_kind") != expected_kind:
            raise VerificationError("adapter kind")
        if hello.get("adapter_id") != adapter_id:
            raise VerificationError("adapter id")
        if hello.get("caseset_sha256") != EXPECTED_CASESET_SHA256:
            raise VerificationError("adapter case-set digest")
        if hello.get("raw_observation_only") is not True:
            raise VerificationError("adapter did not attest raw-observation-only contract")

        for case in iter_cases():
            proc.stdin.write(json.dumps(case, sort_keys=True, separators=(",", ":")) + "\n")
            proc.stdin.flush()
            obs = read_json_line(proc, selector, timeout_s)
            try:
                validate_case(case, obs)
            except Exception as e:
                repro = failure_reproducer(case, obs if isinstance(obs, dict) else {}, e)
                (evidence_dir / "failure-reproducer.json").write_text(
                    json.dumps(repro, indent=2, sort_keys=True) + "\n", encoding="utf-8"
                )
                raise
            summary["completed_cases"] += 1

        proc.stdin.write('{"command":"done"}\n')
        proc.stdin.flush()
        proc.stdin.close()
        try:
            rc = proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired as e:
            raise VerificationError("adapter did not terminate") from e
        if rc != 0:
            raise VerificationError(f"adapter exit {rc}")
        summary["pass"] = True
        return summary
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        selector.close()
        errf.close()
        (evidence_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        manifest = {
            "format": "FMTDUP-ID-EVIDENCE-MANIFEST-1", **provenance,
            "adapter_id": adapter_id, "adapter_command": adapter_cmd,
            "caseset_sha256": EXPECTED_CASESET_SHA256,
            "package_files": {
                name: sha256_file(HERE / name)
                for name in PACKAGE_FILES if (HERE / name).is_file()
            },
        }
        (evidence_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter-cmd", required=True)
    ap.add_argument("--adapter-id", required=True)
    ap.add_argument("--adapter-source", required=True)
    ap.add_argument("--adapter-build", required=True)
    ap.add_argument("--source-commit", required=True)
    ap.add_argument("--source-tree", required=True)
    ap.add_argument("--publication-commit", required=True)
    ap.add_argument("--publication-tree", required=True)
    ap.add_argument("--evidence-dir", required=True)
    ap.add_argument("--timeout-seconds", type=float, default=30.0)
    a = ap.parse_args()
    if a.timeout_seconds <= 0:
        print("RUNNER FAIL: timeout must be positive")
        return 2
    adapter_source = Path(a.adapter_source)
    provenance = {
        "source_commit": a.source_commit, "source_tree": a.source_tree,
        "publication_commit": a.publication_commit, "publication_tree": a.publication_tree,
        "adapter_source": a.adapter_source,
        "adapter_source_sha256": sha256_file(adapter_source) if adapter_source.is_file() else None,
        "adapter_build": a.adapter_build,
    }
    try:
        summary = run_session(
            a.adapter_cmd, Path(a.evidence_dir), adapter_id=a.adapter_id,
            timeout_s=a.timeout_seconds, provenance=provenance, expected_kind="product",
        )
    except Exception as e:
        print("RUNNER FAIL:", e)
        return 1
    print("PASS format/duplicate identity + duplicate long-op evidence",
          summary["completed_cases"], summary["caseset_sha256"])
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
