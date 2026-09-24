#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PKG = HERE.parent / "crash_core_draft8"
sys.path.insert(0, str(PKG))

from fixture import all_fixture_digests  # noqa: E402
from planner import EXPECTED_CASESET_SHA256  # noqa: E402

WORKER = HERE / "build" / "wp10_core_worker"


def need(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def fixture_path(paths: dict, name: str) -> str:
    value = paths.get(name)
    need(isinstance(value, str) and Path(value).is_file(), f"missing fixture {name}")
    return value


def bkey(case: dict) -> str:
    key = f"{case['scope']}:{case['family']}:{case['variant']}"
    if "seed" in case:
        key += ":" + case["seed"]
    return key


def worker_line(proc: subprocess.Popen[str]) -> dict:
    assert proc.stdout is not None
    line = proc.stdout.readline()
    if line == "":
        raise RuntimeError("product worker stdout closed")
    obj = json.loads(line)
    need(isinstance(obj, dict), "product worker response not object")
    return obj


def send(proc: subprocess.Popen[str], line: str) -> None:
    assert proc.stdin is not None
    proc.stdin.write(line + "\n")
    proc.stdin.flush()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture-manifest", required=True, type=Path)
    args = ap.parse_args()

    manifest = json.loads(args.fixture_manifest.read_text(encoding="utf-8"))
    need(manifest.get("format") == "WP10-CORE-FIXTURE-MANIFEST-1", "wrong fixture manifest")
    need(manifest.get("sha256") == all_fixture_digests(), "fixture manifest digest drift")
    paths = manifest.get("paths")
    need(isinstance(paths, dict), "fixture manifest paths missing")

    argv = [
        str(WORKER),
        fixture_path(paths, "record_commit"),
        fixture_path(paths, "reset_healthy"),
        fixture_path(paths, "reset_degraded_equal"),
        fixture_path(paths, "stage_healthy"),
        fixture_path(paths, "stage_primary_only"),
        fixture_path(paths, "stage_mirror_only"),
        fixture_path(paths, "stage_primary_newer_mirror_stale"),
        fixture_path(paths, "stage_mirror_newer_primary_stale"),
    ]
    proc = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=None,
        text=True,
        bufsize=1,
    )

    print(
        json.dumps(
            {
                "format": "WP10-CORE-ADAPTER-1",
                "adapter_kind": "product",
                "caseset_sha256": EXPECTED_CASESET_SHA256,
                "fixture_sha256": all_fixture_digests(),
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        flush=True,
    )

    baselines: dict[str, dict] = {}

    try:
        for raw in sys.stdin:
            cmd = json.loads(raw)
            need(isinstance(cmd, dict), "runner command not object")
            if cmd.get("command") == "done":
                send(proc, "D")
                assert proc.stdin is not None
                proc.stdin.close()
                rc = proc.wait(timeout=5)
                return 0 if rc == 0 else 2

            need(cmd.get("command") == "case", "unknown runner command")
            case = cmd.get("case")
            need(isinstance(case, dict), "case missing")

            key = bkey(case)
            if key not in baselines:
                seed = case.get("seed", "-")
                send(proc, "\t".join(["B", case["family"], case["variant"], seed]))
                baselines[key] = worker_line(proc)
                baseline_path = os.environ.get("WP10_BASELINE_EVIDENCE")
                if baseline_path:
                    Path(baseline_path).write_text(
                        json.dumps(
                            {
                                "format": "WP10-CORE-BASELINES-1",
                                "baselines": baselines,
                            },
                            indent=2,
                            sort_keys=True,
                        )
                        + "\n",
                        encoding="utf-8",
                    )

            inj = case["injection"]
            if "flush_ordinal" in inj:
                ordinal = inj["flush_ordinal"]
                landed = 0
            else:
                ordinal = inj["write_ordinal"]
                landed = inj["landed_bytes"]
            seed = case.get("seed", "-")
            fields = [
                "C",
                str(case["case_index"]),
                case["scope"],
                case["family"],
                case["variant"],
                case["mode"],
                inj["kind"],
                str(ordinal),
                str(landed),
                seed,
            ]
            send(proc, "\t".join(fields))
            obs = worker_line(proc)
            obs["target_baseline"] = baselines[key]
            print(json.dumps(obs, sort_keys=True, separators=(",", ":")), flush=True)
    except Exception as exc:
        try:
            proc.kill()
        except OSError:
            pass
        try:
            proc.wait(timeout=1)
        except Exception:
            pass
        print(f"adapter failure: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    try:
        proc.kill()
    except OSError:
        pass
    print("runner stdin closed before done", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
