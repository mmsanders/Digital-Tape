#!/usr/bin/env python3
"""Execute promote tranche adapters and retain hash-bound DRAFT-8 evidence."""
from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

import oracle

HERE = Path(__file__).resolve().parent
DEFAULT_SPEC_DIR = HERE.parent / "mount_draft8" / "spec"
PACKAGE_FILES = (
    "oracle.py", "runner.py", "replay.py", "selftest.py",
    "_synthetic_adapter.py", "ADAPTER.md", "COVERAGE.md", "README.md",
)


def hashes(root):
    return {
        p.relative_to(root).as_posix(): oracle.shafile(p)
        for p in sorted(root.rglob("*"))
        if p.is_file() and p.name != "manifest.json"
    }


def fresh(path):
    if path.exists():
        if not path.is_dir() or any(path.iterdir()):
            raise oracle.VerificationError("evidence destination is nonempty or not a directory")
    else:
        path.mkdir(parents=True)


def copy_package(dst):
    dst.mkdir(parents=True)
    for name in PACKAGE_FILES:
        shutil.copy2(HERE / name, dst / name)


def copy_specs(spec_dir, dst):
    verified = oracle.verify_spec_dir(spec_dir)
    dst.mkdir(parents=True)
    for name in verified:
        shutil.copy2(Path(spec_dir) / name, dst / name)
    return verified


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter-cmd", required=True)
    ap.add_argument("--adapter-kind", choices=("synthetic", "product"), required=True)
    ap.add_argument("--adapter-id", required=True)
    ap.add_argument("--adapter-source", required=True)
    ap.add_argument("--adapter-build", required=True)
    ap.add_argument("--product-commit", required=True)
    ap.add_argument("--verifier-commit", required=True)
    ap.add_argument("--spec-dir", default=str(DEFAULT_SPEC_DIR))
    ap.add_argument("--adapter-timeout-seconds", type=float, default=30)
    ap.add_argument("--evidence-dir", required=True)
    a = ap.parse_args()

    try:
        ev = Path(a.evidence_dir)
        fresh(ev)
        for label, value in (
            ("adapter command", a.adapter_cmd),
            ("adapter id", a.adapter_id),
            ("adapter source", a.adapter_source),
            ("adapter build", a.adapter_build),
            ("product commit", a.product_commit),
            ("verifier commit", a.verifier_commit),
        ):
            oracle.req(value.strip(), "missing " + label)
        oracle.req(a.adapter_timeout_seconds > 0, "bad timeout")
        specs = copy_specs(Path(a.spec_dir), ev / "input" / "spec")
    except (oracle.VerificationError, OSError) as e:
        print("RUNNER FAIL:", e)
        return 2

    (ev / "output").mkdir()
    copy_package(ev / "input" / "package")
    results = {"pass": True, "cases": {}}
    executions = {}

    with tempfile.TemporaryDirectory(prefix="promote-draft8-") as td_s:
        td = Path(td_s)
        for case in oracle.make_cases():
            ctmp = td / case.id
            ctmp.mkdir()
            inp = ctmp / "input.vo08"
            out = ctmp / "output.vo08"
            inp.write_bytes(case.pre.encode())
            cmd = shlex.split(a.adapter_cmd) + [case.id, str(inp), str(out)]
            execution = {
                "outcome": "exited",
                "exit_code": None,
                "timeout_seconds": a.adapter_timeout_seconds,
            }
            try:
                p = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=a.adapter_timeout_seconds,
                )
                execution["exit_code"] = p.returncode
                stdout, stderr = p.stdout, p.stderr
            except subprocess.TimeoutExpired as e:
                execution["outcome"] = "timeout"
                stdout, stderr = e.stdout or b"", e.stderr or b""
            executions[case.id] = execution

            cev = ev / "output" / case.id
            cev.mkdir()
            shutil.copy2(inp, cev / "input.vo08")
            (cev / "stdout.txt").write_bytes(stdout)
            (cev / "stderr.txt").write_bytes(stderr)
            (cev / "adapter-exit.txt").write_text(
                "TIMEOUT\n" if execution["outcome"] == "timeout"
                else f"{execution['exit_code']}\n"
            )

            errors = []
            if execution["outcome"] == "timeout":
                errors.append("adapter timeout")
            elif execution["exit_code"] != 0:
                errors.append(f"adapter exit {execution['exit_code']}")
            elif not out.is_file():
                errors.append("missing output.vo08")
            else:
                shutil.copy2(out, cev / "output.vo08")
                try:
                    obs = json.loads(stdout.decode("utf-8"))
                    (cev / "observation.json").write_text(
                        json.dumps(obs, indent=2, sort_keys=True) + "\n"
                    )
                    if obs.get("adapter_kind") != a.adapter_kind:
                        errors.append("adapter kind mismatch")
                    if obs.get("adapter_id") != a.adapter_id:
                        errors.append("adapter id mismatch")
                    errors.extend(oracle.validate_observation(case, out.read_bytes(), obs))
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as e:
                    errors.append("invalid observation: " + str(e))

            results["cases"][case.id] = {"pass": not errors, "errors": errors}
            if errors:
                results["pass"] = False

    (ev / "result.json").write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    sf = Path(a.adapter_source)
    source_file = {"path": str(sf), "sha256": oracle.shafile(sf)} if sf.is_file() else None
    manifest = {
        "schema": "promote-draft8-evidence-v1",
        "product_commit": a.product_commit,
        "verifier_commit": a.verifier_commit,
        "spec_hashes": specs,
        "oracle_sha256": oracle.shafile(HERE / "oracle.py"),
        "runner_sha256": oracle.shafile(HERE / "runner.py"),
        "replay_sha256": oracle.shafile(HERE / "replay.py"),
        "adapter": {
            "kind": a.adapter_kind,
            "id": a.adapter_id,
            "command": a.adapter_cmd,
            "source": a.adapter_source,
            "source_file": source_file,
            "build": a.adapter_build,
        },
        "executions": executions,
        "files": hashes(ev),
    }
    (ev / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print("PASS" if results["pass"] else "FAIL", "promote evidence", ev)
    return 0 if results["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
