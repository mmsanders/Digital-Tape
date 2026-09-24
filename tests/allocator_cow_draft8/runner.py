#!/usr/bin/env python3
"""Fail-closed streaming runner for the verifier-owned WP-07 10k campaign."""
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

from fixture import build_fuzz_fixture, build_reset_stress_fixture, fixture_digests
from generator import (
    EXPECTED_PLAN_SHA256,
    MASTER_SEED,
    RNG_ALGORITHM,
    SEQUENCE_COUNT,
    census_and_digest,
    generate_sequence,
    validate_generator_census,
)
from oracle import (
    ADAPTER_FORMAT,
    EVIDENCE_FORMAT,
    EvidenceError,
    validate_acceptance_summary,
    validate_reset_stress,
    validate_sequence,
)

SPEC_SHA256 = {
    "tapefs-v1.md": "3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb",
    "engine-api.md": "537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1",
    "acceptance.md": "7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7",
}


class RunFailure(RuntimeError):
    def __init__(self, message: str, *, plan: dict | None = None, observation=None):
        super().__init__(message)
        self.plan = plan
        self.observation = observation


def _readline(stream: TextIO, timeout_s: float) -> str:
    ready, _, _ = select.select([stream], [], [], timeout_s)
    if not ready:
        raise RunFailure("adapter response timeout")
    line = stream.readline()
    if line == "":
        raise RunFailure("adapter stdout closed unexpectedly")
    return line.rstrip("\n")


def _parse_json_line(line: str, label: str) -> dict:
    try:
        obj = json.loads(line)
    except json.JSONDecodeError as exc:
        raise RunFailure(f"malformed {label} JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise RunFailure(f"{label} is not a JSON object")
    return obj


def parse_handshake(line: str) -> dict:
    obj = _parse_json_line(line, "handshake")
    if obj.get("type") != "hello" or obj.get("format") != ADAPTER_FORMAT:
        raise RunFailure("wrong adapter handshake")
    if obj.get("adapter_kind") != "product":
        raise RunFailure("non-product adapter refused")
    digests = fixture_digests()
    if obj.get("fuzz_fixture_sha256") != digests["fuzz_sha256"]:
        raise RunFailure("adapter fuzz fixture identity mismatch")
    if obj.get("reset_stress_fixture_sha256") != digests["reset_stress_sha256"]:
        raise RunFailure("adapter reset-stress fixture identity mismatch")
    return obj


def _retain_failure(evidence: Path, failure: RunFailure) -> None:
    payload = {
        "error": str(failure),
        "plan": failure.plan,
        "observation": failure.observation,
    }
    (evidence / "failure-reproducer.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_session(
    adapter: Path,
    evidence: Path,
    *,
    sequence_count: int = SEQUENCE_COUNT,
    acceptance: bool = True,
    response_timeout_s: float = 10.0,
) -> dict:
    evidence.mkdir(parents=True, exist_ok=True)
    fuzz_bytes = build_fuzz_fixture()
    reset_bytes = build_reset_stress_fixture()
    digests = fixture_digests()

    current_plan = None
    current_obs = None
    stderr_path = evidence / "adapter.stderr.txt"

    with tempfile.TemporaryDirectory(prefix="wp07-cow-") as td:
        td = Path(td)
        fuzz_path = td / "fuzz.vo08"
        reset_path = td / "reset-stress.vo08"
        fuzz_path.write_bytes(fuzz_bytes)
        reset_path.write_bytes(reset_bytes)

        with stderr_path.open("w", encoding="utf-8") as err:
            proc = subprocess.Popen(
                [
                    str(adapter),
                    "--fuzz-fixture",
                    str(fuzz_path),
                    "--reset-stress-fixture",
                    str(reset_path),
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=err,
                text=True,
                bufsize=1,
            )
            assert proc.stdin is not None and proc.stdout is not None

            completed = 0
            observed = Counter()
            stress_result = None
            try:
                handshake = parse_handshake(_readline(proc.stdout, response_timeout_s))

                proc.stdin.write(json.dumps({"command": "reset_stress"}, separators=(",", ":")) + "\n")
                proc.stdin.flush()
                stress_obs = _parse_json_line(
                    _readline(proc.stdout, response_timeout_s), "reset stress"
                )
                try:
                    stress_result = validate_reset_stress(stress_obs)
                except EvidenceError as exc:
                    raise RunFailure(f"reset stress failed: {exc}", observation=stress_obs) from exc

                for i in range(sequence_count):
                    current_plan = generate_sequence(i)
                    current_obs = None
                    proc.stdin.write(
                        json.dumps(
                            {"command": "sequence", "plan": current_plan},
                            separators=(",", ":"),
                            sort_keys=True,
                        )
                        + "\n"
                    )
                    proc.stdin.flush()
                    current_obs = _parse_json_line(
                        _readline(proc.stdout, response_timeout_s), "sequence result"
                    )
                    try:
                        stats = validate_sequence(current_plan, current_obs)
                    except EvidenceError as exc:
                        raise RunFailure(
                            f"sequence {i} failed oracle: {exc}",
                            plan=current_plan,
                            observation=current_obs,
                        ) from exc
                    completed += 1
                    observed.update(stats)

                proc.stdin.write(json.dumps({"command": "done"}, separators=(",", ":")) + "\n")
                proc.stdin.flush()
                proc.stdin.close()
                rc = proc.wait(timeout=response_timeout_s)
                if rc != 0:
                    raise RunFailure(
                        f"adapter exited nonzero after campaign: {rc}",
                        plan=current_plan,
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
                    str(exc), plan=current_plan, observation=current_obs
                )
                _retain_failure(evidence, failure)
                raise failure

    census, digest = census_and_digest(sequence_count)
    census_errors = validate_generator_census(census) if sequence_count == SEQUENCE_COUNT else []
    if census_errors:
        raise RunFailure("generator census invalid: " + "; ".join(census_errors))

    summary = {
        "format": EVIDENCE_FORMAT,
        "spec_sha256": SPEC_SHA256,
        "fixtures": digests,
        "generator": {
            "rng_algorithm": RNG_ALGORITHM,
            "master_seed": f"{MASTER_SEED:016x}",
            "sequence_count": sequence_count,
            "plan_sha256": digest,
        },
        "coverage_census": census,
        "observed_census": dict(sorted(observed.items())),
        "adapter_handshake": handshake,
        "reset_stress": {
            "passed": True,
            **stress_result,
        },
        "completed_sequences": completed,
        "normal_exit": True,
        "failure_reproducer": None,
    }

    if acceptance:
        errors = validate_acceptance_summary(summary)
        if errors:
            raise RunFailure("acceptance summary invalid: " + "; ".join(errors))
        if digest != EXPECTED_PLAN_SHA256:
            raise RunFailure("canonical 10000-sequence plan digest drift")

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
        p.error("adapter executable does not exist")

    try:
        summary = run_session(
            a.adapter.resolve(),
            a.evidence,
            sequence_count=SEQUENCE_COUNT,
            acceptance=True,
            response_timeout_s=a.timeout,
        )
    except RunFailure as exc:
        print("FAIL", exc, file=sys.stderr)
        return 1

    print("PASS WP-07 allocator/COW 10000-sequence harness")
    print(f"sequences={summary['completed_sequences']}")
    print(f"rng={RNG_ALGORITHM}")
    print(f"seed={MASTER_SEED:016x}")
    print(f"plan_sha256={summary['generator']['plan_sha256']}")
    print(f"actions={summary['coverage_census']['total_actions']}")
    print(f"reset_stress_ns={summary['reset_stress']['elapsed_ns']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
