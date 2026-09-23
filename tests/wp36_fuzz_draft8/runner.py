#!/usr/bin/env python3
"""Fail-closed streaming runner for the verifier-owned WP-36 fuzz plan."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import select
import subprocess
import sys
import tempfile
from typing import TextIO

from fixture import build_fixture
from generator import (
    MASTER_SEED,
    RNG_ALGORITHM,
    SEQUENCE_COUNT,
    census_and_digest,
    generate_sequence,
    plan_line,
)

HANDSHAKE_FORMAT = "WP36-FUZZ-ADAPTER-1"
RESULT_FORMAT = "WP36-FUZZ-RESULT-1"
EVIDENCE_FORMAT = "WP36-FUZZ-EVIDENCE-1"
SPEC_SHA256 = {
    "tapefs-v1.md": "3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb",
    "engine-api.md": "537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1",
    "acceptance.md": "7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7",
}


class RunFailure(RuntimeError):
    def __init__(self, message: str, plan: dict | None = None):
        super().__init__(message)
        self.plan = plan


def _readline(stream: TextIO, timeout_s: float) -> str:
    ready, _, _ = select.select([stream], [], [], timeout_s)
    if not ready:
        raise RunFailure("adapter response timeout")
    line = stream.readline()
    if line == "":
        raise RunFailure("adapter stdout closed unexpectedly")
    return line.rstrip("\n")


def parse_handshake(line: str) -> dict:
    parts = line.split("\t")
    if len(parts) != 5 or parts[0] != "HELLO":
        raise RunFailure("malformed adapter handshake")
    handshake = {
        "format": parts[1],
        "adapter_kind": parts[2],
        "source_write_binding": parts[3],
        "assertion_mode": parts[4],
    }
    if handshake["format"] != HANDSHAKE_FORMAT:
        raise RunFailure("wrong adapter handshake format")
    if handshake["adapter_kind"] != "product":
        raise RunFailure("non-product adapter refused")
    if handshake["source_write_binding"] != "NULL":
        raise RunFailure("source write binding is not literal NULL")
    if handshake["assertion_mode"] != "debug":
        raise RunFailure("debug assertion mode not active")
    return handshake


def parse_result(line: str, plan: dict) -> dict:
    parts = line.split("\t")
    if len(parts) != 12 or parts[0] != "RES":
        raise RunFailure("malformed adapter sequence result", plan)
    try:
        out = {
            "format": parts[1],
            "seq_index": int(parts[2]),
            "seq_seed": parts[3],
            "ops_executed": int(parts[4]),
            "read_callbacks": int(parts[5]),
            "flush_callbacks": int(parts[6]),
            "event_overflow": int(parts[7]),
            "mount_result": parts[8],
            "unmount_result": parts[9],
            "ok_results": int(parts[10]),
            "underrun_results": int(parts[11].split(",", 1)[0]),
        }
        suffix = parts[11].split(",", 1)
        out["other_results"] = int(suffix[1]) if len(suffix) == 2 else 0
    except ValueError as exc:
        raise RunFailure(f"non-numeric adapter result field: {exc}", plan) from exc

    if out["format"] != RESULT_FORMAT:
        raise RunFailure("wrong adapter result format", plan)
    if out["seq_index"] != plan["seq_index"] or out["seq_seed"] != plan["seq_seed"]:
        raise RunFailure("adapter sequence identity mismatch", plan)
    if out["ops_executed"] != len(plan["ops"]):
        raise RunFailure("adapter did not execute the complete sequence", plan)
    if out["event_overflow"] != 0:
        raise RunFailure("adapter callback trace/counter overflow", plan)
    if out["mount_result"] != "TAPE_OK" or out["unmount_result"] != "TAPE_OK":
        raise RunFailure("sequence mount/unmount failed", plan)
    if out["other_results"] != 0:
        raise RunFailure("transport sequence returned an unexpected result code", plan)
    if out["ok_results"] + out["underrun_results"] != len(plan["ops"]):
        raise RunFailure("adapter result census does not equal operation count", plan)
    for k in ("read_callbacks", "flush_callbacks", "ok_results", "underrun_results"):
        if out[k] < 0:
            raise RunFailure(f"negative adapter counter {k}", plan)
    return out


def validate_acceptance_summary(summary: dict) -> list[str]:
    errors = []

    def need(cond: bool, msg: str) -> None:
        if not cond:
            errors.append(msg)

    need(summary.get("format") == EVIDENCE_FORMAT, "wrong evidence format")
    gen = summary.get("generator")
    need(isinstance(gen, dict), "missing generator provenance")
    if isinstance(gen, dict):
        need(gen.get("rng_algorithm") == RNG_ALGORITHM, "wrong/missing RNG algorithm")
        need(gen.get("master_seed") == f"{MASTER_SEED:016x}", "wrong/missing master seed")
        need(gen.get("sequence_count") == SEQUENCE_COUNT, "run did not contain exactly 100000 sequences")
        need(isinstance(gen.get("plan_sha256"), str) and len(gen.get("plan_sha256", "")) == 64, "missing plan digest")
    need(summary.get("completed_sequences") == SEQUENCE_COUNT, "fewer than 100000 sequences completed")
    need(summary.get("normal_exit") is True, "adapter did not exit normally")
    need(summary.get("assertion_or_crash") is False, "assertion/crash observed")
    hs = summary.get("adapter_handshake")
    need(isinstance(hs, dict), "missing adapter handshake provenance")
    if isinstance(hs, dict):
        need(hs.get("source_write_binding") == "NULL", "source write binding not NULL")
        need(hs.get("assertion_mode") == "debug", "debug assertion mode missing")
        need(hs.get("adapter_kind") == "product", "non-product adapter")
    return errors


def run_session(
    adapter: Path,
    evidence_dir: Path,
    *,
    sequence_count: int,
    timeout_s: float = 5.0,
    acceptance: bool = True,
) -> dict:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    fixture_bytes = build_fixture()
    with tempfile.TemporaryDirectory(prefix="wp36-fuzz-") as td:
        fixture = Path(td) / "source.vo08"
        fixture.write_bytes(fixture_bytes)
        stderr_path = evidence_dir / "adapter.stderr.txt"
        with stderr_path.open("w", encoding="utf-8") as err:
            proc = subprocess.Popen(
                [str(adapter), "--fixture", str(fixture)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=err,
                text=True,
                bufsize=1,
            )
            assert proc.stdin is not None and proc.stdout is not None
            completed = 0
            totals = {
                "read_callbacks": 0,
                "flush_callbacks": 0,
                "ok_results": 0,
                "underrun_results": 0,
            }
            current_plan = None
            try:
                handshake = parse_handshake(_readline(proc.stdout, timeout_s))
                for i in range(sequence_count):
                    current_plan = generate_sequence(i)
                    proc.stdin.write(plan_line(current_plan) + "\n")
                    proc.stdin.flush()
                    result = parse_result(_readline(proc.stdout, timeout_s), current_plan)
                    completed += 1
                    for k in totals:
                        totals[k] += int(result[k])
                proc.stdin.write("DONE\n")
                proc.stdin.flush()
                proc.stdin.close()
                rc = proc.wait(timeout=timeout_s)
                if rc != 0:
                    raise RunFailure(f"adapter exited nonzero after stream: {rc}", current_plan)
            except Exception as exc:
                try:
                    proc.kill()
                except OSError:
                    pass
                try:
                    proc.wait(timeout=1)
                except Exception:
                    pass
                if isinstance(exc, RunFailure):
                    failure = exc if exc.plan is not None else RunFailure(str(exc), current_plan)
                else:
                    failure = RunFailure(str(exc), current_plan)
                if failure.plan is not None:
                    (evidence_dir / "failure-reproducer.json").write_text(
                        json.dumps(failure.plan, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    (evidence_dir / "failure-reproducer.plan").write_text(
                        plan_line(failure.plan) + "\n",
                        encoding="utf-8",
                    )
                raise failure

    census, digest = census_and_digest(sequence_count)
    summary = {
        "format": EVIDENCE_FORMAT,
        "spec_sha256": SPEC_SHA256,
        "fixture_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
        "generator": {
            "rng_algorithm": RNG_ALGORITHM,
            "master_seed": f"{MASTER_SEED:016x}",
            "sequence_count": sequence_count,
            "plan_sha256": digest,
        },
        "coverage_census": census,
        "adapter_handshake": handshake,
        "completed_sequences": completed,
        "normal_exit": True,
        "assertion_or_crash": False,
        "adapter_totals": totals,
    }
    if acceptance:
        errors = validate_acceptance_summary(summary)
        if errors:
            raise RunFailure("acceptance summary invalid: " + "; ".join(errors))
    (evidence_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--adapter", type=Path, required=True)
    p.add_argument("--evidence", type=Path, required=True)
    p.add_argument("--timeout", type=float, default=5.0)
    a = p.parse_args(argv)
    if not a.adapter.is_file():
        p.error("adapter executable does not exist")
    try:
        summary = run_session(
            a.adapter.resolve(),
            a.evidence,
            sequence_count=SEQUENCE_COUNT,
            timeout_s=a.timeout,
            acceptance=True,
        )
    except RunFailure as exc:
        print("FAIL", exc, file=sys.stderr)
        return 1
    print("PASS WP-36 source-slot fuzz harness")
    print(f"sequences={summary['completed_sequences']}")
    print(f"rng={RNG_ALGORITHM}")
    print(f"seed={MASTER_SEED:016x}")
    print(f"plan_sha256={summary['generator']['plan_sha256']}")
    print(f"total_ops={summary['coverage_census']['total_ops']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
