#!/usr/bin/env python3
"""Fail-closed streaming runner for the bounded DRAFT-8 WP-10 core crash tranche."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import select
import subprocess
import sys
import tempfile
from typing import TextIO

from fixture import all_fixture_digests, fixture_bytes
from oracle import OracleError, expected_snapshot, validate_case
from planner import (
    EXPECTED_CASESET_SHA256,
    EXPECTED_TOTAL_CASES,
    case_counts,
    caseset_digest,
    iter_cases,
    validate_planner,
)

ADAPTER_FORMAT = "WP10-CORE-ADAPTER-1"
EVIDENCE_FORMAT = "WP10-CORE-EVIDENCE-1"
SPEC_SHA256 = {
    "tapefs-v1.md": "3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb",
    "engine-api.md": "537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1",
    "acceptance.md": "7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7",
}


class RunFailure(RuntimeError):
    def __init__(self, message: str, *, case=None, observation=None, expected=None):
        super().__init__(message)
        self.case = case
        self.observation = observation
        self.expected = expected


def _readline(stream: TextIO, timeout_s: float) -> str:
    ready, _, _ = select.select([stream], [], [], timeout_s)
    if not ready:
        raise RunFailure("adapter response timeout")
    line = stream.readline()
    if line == "":
        raise RunFailure("adapter stdout closed unexpectedly")
    return line.rstrip("\n")


def _parse_json(line: str, label: str) -> dict:
    try:
        obj = json.loads(line)
    except json.JSONDecodeError as exc:
        raise RunFailure(f"malformed {label}: {exc}") from exc
    if not isinstance(obj, dict):
        raise RunFailure(f"{label} is not an object")
    return obj


def validate_handshake(hello: dict) -> list[str]:
    errors = []
    if not isinstance(hello, dict):
        return ["handshake is not an object"]
    if hello.get("format") != ADAPTER_FORMAT:
        errors.append("wrong adapter handshake format")
    if hello.get("adapter_kind") != "product":
        errors.append("non-product adapter")
    if hello.get("caseset_sha256") != EXPECTED_CASESET_SHA256:
        errors.append("case-set identity mismatch")
    if hello.get("fixture_sha256") != all_fixture_digests():
        errors.append("fixture identities mismatch")
    return errors


def _baseline_key(case: dict) -> str:
    key = f"{case['scope']}:{case['family']}:{case['variant']}"
    if "seed" in case:
        key += ":" + case["seed"]
    return key


def _write_fixtures(directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    mapping = {}

    def put(name: str, family: str, variant: str, seed=None):
        path = directory / (name + ".img")
        path.write_bytes(fixture_bytes(family, variant, seed=seed))
        mapping[name] = str(path)

    put("record_commit", "record_commit", "overwrite")
    put("reset_healthy", "reset_b", "healthy")
    put("reset_degraded_equal", "reset_b", "degraded_equal")
    put("stage_healthy", "stage_clear", "arm")
    for seed in (
        "primary_only",
        "mirror_only",
        "primary_newer_mirror_stale",
        "mirror_newer_primary_stale",
    ):
        put("stage_" + seed, "stage_clear", "arm", seed=seed)
    return mapping


def _retain_failure(evidence: Path, failure: RunFailure) -> None:
    payload = {
        "error": str(failure),
        "case": failure.case,
        "observation": failure.observation,
        "expected": failure.expected,
    }
    (evidence / "failure-reproducer.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_session(
    adapter: Path,
    evidence: Path,
    *,
    case_limit: int | None = None,
    acceptance: bool = True,
    timeout_s: float = 10.0,
) -> dict:
    evidence.mkdir(parents=True, exist_ok=True)
    planner_errors = validate_planner()
    if planner_errors:
        raise RunFailure("planner invalid: " + "; ".join(planner_errors))

    counts = case_counts()
    if caseset_digest() != EXPECTED_CASESET_SHA256:
        raise RunFailure("case-set digest drift")

    stderr_path = evidence / "adapter.stderr.txt"
    current_case = None
    current_obs = None
    baseline_canonical: dict[str, str] = {}
    outcome_census = Counter()

    with tempfile.TemporaryDirectory(prefix="wp10-core-") as td:
        fixture_dir = Path(td) / "fixtures"
        fixture_paths = _write_fixtures(fixture_dir)
        manifest = Path(td) / "fixtures.json"
        manifest.write_text(
            json.dumps(
                {
                    "format": "WP10-CORE-FIXTURE-MANIFEST-1",
                    "paths": fixture_paths,
                    "sha256": all_fixture_digests(),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        with stderr_path.open("w", encoding="utf-8") as err:
            proc = subprocess.Popen(
                [str(adapter), "--fixture-manifest", str(manifest)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=err,
                text=True,
                bufsize=1,
            )
            assert proc.stdin is not None and proc.stdout is not None
            completed = 0
            try:
                hello = _parse_json(_readline(proc.stdout, timeout_s), "adapter handshake")
                handshake_errors = validate_handshake(hello)
                if handshake_errors:
                    raise RunFailure("adapter handshake invalid: " + "; ".join(handshake_errors))

                for current_case in iter_cases():
                    if case_limit is not None and completed >= case_limit:
                        break

                    proc.stdin.write(
                        json.dumps(
                            {"command": "case", "case": current_case},
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                        + "\n"
                    )
                    proc.stdin.flush()
                    current_obs = _parse_json(
                        _readline(proc.stdout, timeout_s), "case observation"
                    )

                    try:
                        result = validate_case(current_case, current_obs)
                    except OracleError as exc:
                        expected = None
                        try:
                            pre = current_obs.get("pre_snapshot")
                            if isinstance(pre, dict):
                                expected = expected_snapshot(current_case, pre)
                        except Exception:
                            expected = None
                        raise RunFailure(
                            f"case {current_case['case_index']} failed oracle: {exc}",
                            case=current_case,
                            observation=current_obs,
                            expected=expected,
                        ) from exc

                    baseline = current_obs.get("target_baseline")
                    bkey = _baseline_key(current_case)
                    bcanon = json.dumps(baseline, sort_keys=True, separators=(",", ":"))
                    old = baseline_canonical.get(bkey)
                    if old is None:
                        baseline_canonical[bkey] = bcanon
                    elif old != bcanon:
                        raise RunFailure(
                            f"baseline trace drift for {bkey}",
                            case=current_case,
                            observation=current_obs,
                        )

                    fp = result["logical_fingerprint"]
                    outcome_census[
                        json.dumps(fp, sort_keys=True, separators=(",", ":"))
                    ] += 1
                    completed += 1

                proc.stdin.write('{"command":"done"}\n')
                proc.stdin.flush()
                proc.stdin.close()
                rc = proc.wait(timeout=timeout_s)
                if rc != 0:
                    raise RunFailure(
                        f"adapter exited nonzero after stream: {rc}",
                        case=current_case,
                        observation=current_obs,
                    )
            except Exception as exc:
                try:
                    proc.kill()
                except OSError:
                    pass
                try:
                    proc.wait(timeout=1)
                except Exception:
                    pass
                failure = exc if isinstance(exc, RunFailure) else RunFailure(
                    str(exc), case=current_case, observation=current_obs
                )
                _retain_failure(evidence, failure)
                raise failure

    summary = {
        "format": EVIDENCE_FORMAT,
        "spec_sha256": SPEC_SHA256,
        "caseset_sha256": EXPECTED_CASESET_SHA256,
        "fixture_sha256": all_fixture_digests(),
        "planned_counts": counts,
        "completed_injection_cases": completed,
        "normal_exit": True,
        "baseline_trace_sha256": {
            key: hashlib.sha256(value.encode("utf-8")).hexdigest()
            for key, value in sorted(baseline_canonical.items())
        },
        "logical_outcome_census": dict(sorted(outcome_census.items())),
        "failure_reproducer": None,
    }

    if acceptance:
        if completed != EXPECTED_TOTAL_CASES:
            raise RunFailure(f"completed {completed} != {EXPECTED_TOTAL_CASES}")
        if counts["total_injection_cases"] != EXPECTED_TOTAL_CASES:
            raise RunFailure("planned count mismatch")
        if len(baseline_canonical) != 20:
            raise RunFailure(
                f"expected 20 stable baseline/seed traces, saw {len(baseline_canonical)}"
            )

    (evidence / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--adapter", required=True, type=Path)
    p.add_argument("--evidence", required=True, type=Path)
    p.add_argument("--timeout", type=float, default=10.0)
    a = p.parse_args(argv)
    if not a.adapter.is_file():
        p.error("adapter does not exist")

    try:
        summary = run_session(
            a.adapter.resolve(),
            a.evidence,
            case_limit=None,
            acceptance=True,
            timeout_s=a.timeout,
        )
    except RunFailure as exc:
        print("FAIL", exc, file=sys.stderr)
        return 1

    print("PASS WP-10 core crash tranche")
    print(f"cases={summary['completed_injection_cases']}")
    print(f"caseset_sha256={summary['caseset_sha256']}")
    print(
        "first_interruption_cases="
        + str(summary["planned_counts"]["first_interruption_cases"])
    )
    print(
        "two_interruption_closure_cases="
        + str(summary["planned_counts"]["two_interruption_closure_cases"])
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
