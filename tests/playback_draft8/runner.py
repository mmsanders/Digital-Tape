#!/usr/bin/env python3
"""Run a playback adapter against the independent DRAFT-8 three-family package."""
from __future__ import annotations

import argparse
import gzip
import json
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

from oracle import (
    VerificationError, check_run, expected_outputs, load_package, sha256_file,
    write_difference_wav,
)

PACKAGE_DIR = Path(__file__).resolve().parent
OUTPUT_NAMES = {
    "forward_1x": "forward-1x.pcm",
    "seek_boundaries": "seek-boundaries.pcm",
    "reverse_neg1x": "reverse-neg1x.pcm",
}


def copy_inputs(dst: Path) -> None:
    (dst / "input/spec").mkdir(parents=True, exist_ok=True)
    (dst / "input/fixtures").mkdir(parents=True, exist_ok=True)
    (dst / "input/golden").mkdir(parents=True, exist_ok=True)
    shutil.copy2(PACKAGE_DIR / "package.json", dst / "input/package.json")
    for name in ("tapefs-v1.md", "engine-api.md", "acceptance.md"):
        shutil.copy2(PACKAGE_DIR / "spec" / name, dst / "input/spec" / name)
    shutil.copy2(PACKAGE_DIR / "fixtures/playback-three-run.vo08.gz",
                 dst / "input/fixtures/playback-three-run.vo08.gz")
    shutil.copy2(PACKAGE_DIR / "fixtures/fixture.json", dst / "input/fixtures/fixture.json")
    for name in ("forward-1x.pcm", "seek-boundaries.pcm", "reverse-neg1x.pcm"):
        shutil.copy2(PACKAGE_DIR / "golden" / name, dst / "input/golden" / name)


def file_hash_map(root: Path) -> dict[str, str]:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            out[p.relative_to(root).as_posix()] = sha256_file(p)
    return out


def fresh_evidence_dir(path: Path) -> None:
    """Create or reuse an empty evidence directory without deleting any bytes."""
    if path.exists():
        if not path.is_dir():
            raise VerificationError(f"evidence destination is not a directory: {path}")
        if any(path.iterdir()):
            raise VerificationError(f"evidence directory is not empty: {path}")
    else:
        path.mkdir(parents=True)


def nonempty(value: str, label: str) -> str:
    value = value.strip()
    if not value:
        raise VerificationError(f"missing required provenance: {label}")
    return value


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter-cmd", required=True,
                    help="command string; runner appends --fixture and --out-dir")
    ap.add_argument("--adapter-kind", choices=("synthetic", "product"), required=True)
    ap.add_argument("--adapter-id", required=True)
    ap.add_argument("--adapter-source", required=True,
                    help="declared immutable adapter source identity")
    ap.add_argument("--adapter-build", required=True,
                    help="declared adapter build command/artifact provenance")
    ap.add_argument("--adapter-timeout-seconds", type=float, default=60.0)
    ap.add_argument("--source-commit", required=True)
    ap.add_argument("--source-tree", required=True)
    ap.add_argument("--evidence-dir", required=True)
    args = ap.parse_args()

    try:
        package = load_package(PACKAGE_DIR)
        adapter_cmd = nonempty(args.adapter_cmd, "adapter command")
        adapter_id = nonempty(args.adapter_id, "adapter id")
        adapter_source = nonempty(args.adapter_source, "adapter source")
        adapter_build = nonempty(args.adapter_build, "adapter build")
        source_commit = nonempty(args.source_commit, "verifier source commit")
        source_tree = nonempty(args.source_tree, "verifier source tree")
        if args.adapter_timeout_seconds <= 0:
            raise VerificationError("adapter timeout must be greater than zero")
        evidence = Path(args.evidence_dir)
        fresh_evidence_dir(evidence)
    except (VerificationError, OSError) as exc:
        print(f"RUNNER FAIL: {exc}")
        return 2

    (evidence / "output").mkdir(parents=True)
    copy_inputs(evidence)

    fixture_gz = PACKAGE_DIR / package["fixture"]["archive"]
    raw = gzip.decompress(fixture_gz.read_bytes())

    with tempfile.TemporaryDirectory(prefix="playback-draft8-") as td:
        td = Path(td)
        raw_path = td / "playback-three-run.vo08"
        out_dir = td / "adapter-output"
        out_dir.mkdir()
        raw_path.write_bytes(raw)
        cmd = shlex.split(adapter_cmd) + ["--fixture", str(raw_path), "--out-dir", str(out_dir)]
        execution = {
            "outcome": "exited",
            "exit_code": None,
            "timeout_seconds": args.adapter_timeout_seconds,
        }
        try:
            proc = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
                timeout=args.adapter_timeout_seconds,
            )
            stdout = proc.stdout
            stderr = proc.stderr
            execution["exit_code"] = proc.returncode
            exit_record = str(proc.returncode) + "\n"
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or b""
            stderr = exc.stderr or b""
            execution["outcome"] = "timeout"
            exit_record = "TIMEOUT\n"
        (evidence / "output/stdout.txt").write_bytes(stdout)
        (evidence / "output/stderr.txt").write_bytes(stderr)
        (evidence / "output/adapter-exit.txt").write_text(exit_record)
        if execution["outcome"] == "timeout":
            result = {
                "pass": False,
                "error": f"adapter timeout after {args.adapter_timeout_seconds:g} seconds",
                "families": {},
            }
            (evidence / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        elif execution["exit_code"] != 0:
            result = {"pass": False, "error": f"adapter exit {execution['exit_code']}", "families": {}}
            (evidence / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        else:
            required = ["observation.json", *OUTPUT_NAMES.values()]
            missing = [name for name in required if not (out_dir / name).is_file()]
            if missing:
                result = {"pass": False, "error": "missing adapter outputs: " + ", ".join(missing), "families": {}}
                (evidence / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
            else:
                for name in required:
                    shutil.copy2(out_dir / name, evidence / "output" / name)
                try:
                    obs = json.loads((out_dir / "observation.json").read_text())
                    if obs.get("adapter", {}).get("kind") != args.adapter_kind:
                        raise VerificationError("observation adapter kind disagrees with runner")
                    if obs.get("adapter", {}).get("id") != args.adapter_id:
                        raise VerificationError("observation adapter id disagrees with runner")
                    outputs = {
                        family: (out_dir / name).read_bytes()
                        for family, name in OUTPUT_NAMES.items()
                    }
                    result = check_run(raw, obs, outputs)
                    result["error"] = None
                    if not result["pass"]:
                        exp = expected_outputs(raw)
                        for family, rec in result["families"].items():
                            if not rec["match"]:
                                write_difference_wav(exp[family], outputs[family],
                                                     evidence / f"output/{family}.diff.wav")
                except (VerificationError, ValueError, KeyError, json.JSONDecodeError) as exc:
                    result = {"pass": False, "error": str(exc), "families": {}}
                (evidence / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")

    adapter_source_file = None
    p = Path(args.adapter_source)
    if p.is_file():
        adapter_source_file = {"path": str(p), "sha256": sha256_file(p)}

    manifest = {
        "schema": "playback-draft8-evidence-v2",
        "assignment": "P1-R4-V",
        "source_commit": source_commit,
        "source_tree": source_tree,
        "package_manifest_sha256": sha256_file(PACKAGE_DIR / "package.json"),
        "generator_sha256": sha256_file(PACKAGE_DIR / "generate_fixture.py"),
        "oracle_sha256": sha256_file(PACKAGE_DIR / "oracle.py"),
        "runner_sha256": sha256_file(PACKAGE_DIR / "runner.py"),
        "replay_sha256": sha256_file(PACKAGE_DIR / "replay.py"),
        "adapter": {
            "kind": args.adapter_kind,
            "id": adapter_id,
            "command": adapter_cmd,
            "source": adapter_source,
            "source_file": adapter_source_file,
            "build": adapter_build,
        },
        "execution": execution,
        "files": file_hash_map(evidence),
    }
    (evidence / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    final = json.loads((evidence / "result.json").read_text())
    print("PASS" if final.get("pass") else "FAIL", "playback DRAFT-8 evidence", evidence)
    return 0 if final.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
