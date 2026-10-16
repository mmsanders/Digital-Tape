#!/usr/bin/env python3
"""Any-subset campaign through the existing WP-10 core worker (crash_core_adapter):
record/commit, reset-b and stage-clear with its closure seeds. Product #440; see
subset_driver.py for what is and is not done here.

    python3 tests/wp10_subset_binding/run_core.py --evidence DIR [--shard I/N] [--jobs J]

For each accepted crash_core_draft8 scenario (family, variant, seed), from its fixture:
the complete operation (successful-operation control, crash at its end); a cut at every
operation write-unit boundary 0..units (including inside a multi-block call) and at the
entry of every operation barrier; an error at every operation write call and barrier
(crash at end); and, for the first --second-cut distinct first-cut images, a fresh run of
the same operation after actual recovery from those bytes, cut at every unit boundary
again. Each run's actual history is replayed into model.py; every planned projection is
materialized and every distinct image is remounted. Evidence: runs.jsonl, remounts.jsonl,
traces/, initial/, summary-*.json. No outcome verdict is produced.
"""
from __future__ import annotations

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tests" / "crash_core_draft8"))
import subset_driver as sd  # noqa: E402
import runner as core_runner  # noqa: E402  (verifier package: its own fixture writer)
from planner import iter_cases  # noqa: E402

NAME = "crash_core"
WORKER = ROOT / "tests" / "crash_core_adapter" / "build" / "wp10_core_worker"
worker_path = WORKER
FIXTURES = ["record_commit", "reset_healthy", "reset_degraded_equal", "stage_healthy",
            "stage_primary_only", "stage_mirror_only", "stage_primary_newer_mirror_stale",
            "stage_mirror_newer_primary_stale"]


def remount_side(family: str, variant: str) -> str:
    # the existing run_injected rule, unchanged
    return "A" if family == "reset_b" and variant == "degraded_equal" else "B"


def remount_key(key) -> str:
    return remount_side(key[0], key[1])


def scenarios(only=None):
    out = sorted({(c["family"], c["variant"], c.get("seed") or "-") for c in iter_cases()})
    return [s for s in out if only is None or "/".join(s).startswith(only)]


def make_worker(tmp: Path) -> sd.Worker:
    paths = core_runner._write_fixtures(tmp / "fixtures")
    return sd.Worker([str(WORKER)] + [str(paths[n]) for n in FIXTURES])


fixture_worker = make_worker


def s_run(w, tmp, key, base, cut_unit, cut_flush, err_call, err_flush):
    tr, init = tmp / "trace.jsonl", tmp / "initial.img"
    res = w.ask("S", *key, "-" if base is None else "@" + str(base), str(cut_unit), str(cut_flush),
                str(err_call), str(err_flush), str(tr), str(init))
    return res, sd.read_trace(tr), init.read_bytes()


def remount(w, tmp, key, image: bytes) -> dict:
    p = tmp / "proj.img"
    p.write_bytes(image)
    obs = w.ask("R", str(p), remount_key(key))
    if obs["image_snapshot"]["image_sha256"] != sd.sha(image):
        raise RuntimeError("worker remounted different bytes than the projection")
    return obs


if __name__ == "__main__":
    sys.exit(sd.campaign_main(sys.modules[__name__]))
