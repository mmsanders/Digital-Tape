#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
WORKER = HERE / "build" / "wp07_product_worker"
ADAPTER_FORMAT = "WP07-COW-ADAPTER-1"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def cpu_model() -> str:
    p = Path("/proc/cpuinfo")
    if p.is_file():
        for line in p.read_text(errors="replace").splitlines():
            if ":" in line and line.split(":", 1)[0].strip().lower() in {
                "model name",
                "hardware",
                "processor",
            }:
                value = line.split(":", 1)[1].strip()
                if value:
                    return value
    return platform.processor() or platform.machine() or "unknown-cpu"


def timing_environment() -> dict:
    info = time.get_clock_info("monotonic")
    return {
        "clock": "CLOCK_MONOTONIC",
        "timer_resolution_ns": max(1, int(round(info.resolution * 1_000_000_000))),
        "platform": platform.platform() or sys.platform,
        "kernel": platform.release() or "unknown-kernel",
        "cpu_model": cpu_model(),
    }


def need_int(value, name: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} invalid")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} too large")
    return value


def worker_sequence(plan: dict, fixture: Path) -> dict:
    idx = need_int(plan.get("seq_index"), "seq_index")
    seed = plan.get("seq_seed")
    actions = plan.get("actions")
    if not isinstance(seed, str) or len(seed) != 16:
        raise ValueError("seq_seed invalid")
    int(seed, 16)
    if not isinstance(actions, list) or not actions:
        raise ValueError("actions invalid")

    lines = [f"SEQ {idx} {seed} {len(actions)}"]
    for n, action in enumerate(actions):
        if not isinstance(action, dict):
            raise ValueError(f"action {n} invalid")
        kind = action.get("kind")
        if kind == "reset":
            if set(action) != {"kind"}:
                raise ValueError(f"reset action {n} has unexpected fields")
            lines.append("R")
            continue
        if kind != "edit":
            raise ValueError(f"action {n} kind invalid")
        mode = action.get("mode")
        selector = action.get("selector")
        frames = need_int(action.get("frames"), f"action {n} frames", minimum=1)
        budget = need_int(action.get("service_budget"), f"action {n} budget", minimum=1)
        if mode not in {"overwrite", "overdub", "splice"}:
            raise ValueError(f"action {n} mode invalid")
        if selector not in {
            "start",
            "mid",
            "end",
            "q1",
            "q3",
            "cf_half",
            "cf_boundary",
            "cf_boundary_minus",
            "cf_boundary_plus",
        }:
            raise ValueError(f"action {n} selector invalid")
        lines.append(f"E {mode} {selector} {frames} {budget}")

    script = "\n".join(lines) + "\n"
    try:
        proc = subprocess.run(
            [str(WORKER), "sequence", str(fixture)],
            input=script,
            text=True,
            capture_output=True,
            timeout=9.0,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("product sequence worker timeout") from exc
    if proc.stderr:
        sys.stderr.write(proc.stderr)
        sys.stderr.flush()
    if proc.returncode != 0:
        raise RuntimeError(f"product sequence worker exit {proc.returncode}")
    text = proc.stdout.strip()
    if "\n" in text:
        raise RuntimeError("product sequence worker emitted multiple lines")
    obs = json.loads(text)
    if not isinstance(obs, dict):
        raise RuntimeError("product sequence worker observation is not an object")
    return obs


def worker_reset_stress(fixture: Path) -> dict:
    try:
        proc = subprocess.run(
            [str(WORKER), "reset-stress", str(fixture)],
            text=True,
            capture_output=True,
            timeout=3.0,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("reset-stress worker exceeded outer watchdog") from exc
    if proc.stderr:
        sys.stderr.write(proc.stderr)
        sys.stderr.flush()
    if proc.returncode == 124:
        return {
            "format": "WP07-RESET-STRESS-1",
            "result": "TAPE_ERR_UNKNOWN",
            "timed_out": True,
            "elapsed_ns": 1_000_000_000,
            "event_overflow": False,
            "write_events": [],
            "post_b_slots": [],
            "timing_environment": timing_environment(),
        }
    if proc.returncode != 0:
        raise RuntimeError(f"reset-stress worker exit {proc.returncode}")
    text = proc.stdout.strip()
    if "\n" in text:
        raise RuntimeError("reset-stress worker emitted multiple lines")
    obs = json.loads(text)
    if not isinstance(obs, dict):
        raise RuntimeError("reset-stress observation is not an object")
    obs["timing_environment"] = timing_environment()
    return obs


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--fuzz-fixture", type=Path, required=True)
    p.add_argument("--reset-stress-fixture", type=Path, required=True)
    a = p.parse_args()

    if not WORKER.is_file() or not os.access(WORKER, os.X_OK):
        print(f"worker missing/not executable: {WORKER}", file=sys.stderr)
        return 2
    if not a.fuzz_fixture.is_file() or not a.reset_stress_fixture.is_file():
        print("verifier fixture missing", file=sys.stderr)
        return 2

    hello = {
        "type": "hello",
        "format": ADAPTER_FORMAT,
        "adapter_kind": "product",
        "fuzz_fixture_sha256": sha256_file(a.fuzz_fixture),
        "reset_stress_fixture_sha256": sha256_file(a.reset_stress_fixture),
    }
    print(json.dumps(hello, separators=(",", ":")), flush=True)

    for raw in sys.stdin:
        try:
            cmd = json.loads(raw)
            if not isinstance(cmd, dict):
                raise ValueError("command is not an object")
            kind = cmd.get("command")
            if kind == "done":
                return 0
            if kind == "reset_stress":
                obs = worker_reset_stress(a.reset_stress_fixture)
            elif kind == "sequence":
                plan = cmd.get("plan")
                if not isinstance(plan, dict):
                    raise ValueError("sequence plan missing")
                obs = worker_sequence(plan, a.fuzz_fixture)
            else:
                raise ValueError(f"unknown command {kind!r}")
            print(json.dumps(obs, separators=(",", ":"), sort_keys=True), flush=True)
        except Exception as exc:
            print(f"adapter protocol failure: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2

    print("adapter stdin closed before done", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
