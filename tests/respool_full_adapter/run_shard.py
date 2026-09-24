#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ctypes as C
import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "tests" / "respool_full_draft8"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(PKG))
sys.path.insert(0, str(HERE))

from fixture import from_compact, layout_name  # noqa: E402
from oracle import OracleError, case_id, validate_crash_observation  # noqa: E402
from planner import canonical_json, iter_cases  # noqa: E402
from reproducer import retain_failure  # noqa: E402
from media_image import build_raw_image  # noqa: E402

LIB = HERE / "build" / "librespool_full.so"
EXPECTED_TREE = "5637fbd3e89316889b4bbd52d2a72c95e3c278e1"
EXPECTED_IMPORT = "895351d17de9332e0804140858049d3608eeecd4"
EXPECTED_BASE = "8276d8f22da34a53f9f52dae8d3bd1acb3c763d9"

RESULT_NAMES = [
    "TAPE_OK", "TAPE_ERR_IO", "TAPE_ERR_BAD_MAGIC", "TAPE_ERR_CRC",
    "TAPE_ERR_VERSION", "TAPE_ERR_UNSUPPORTED_STATE", "TAPE_ERR_GEOMETRY",
    "TAPE_ERR_INCOMPLETE", "TAPE_ERR_INCONSISTENT", "TAPE_ERR_NO_VALID_INDEX",
    "TAPE_ERR_READ_ONLY", "TAPE_ERR_CARTRIDGE_FULL", "TAPE_ERR_INDEX_FULL",
    "TAPE_ERR_DEST_TOO_SMALL", "TAPE_ERR_SEQUENCE_EXHAUSTED",
    "TAPE_ERR_FAULTED", "TAPE_ERR_NOT_MOUNTED", "TAPE_ERR_BUSY",
    "TAPE_ERR_UNDERRUN", "TAPE_ERR_INVALID_ARG",
]

TARGET = {
    "chunk_copy": 1,
    "chunk_flush": 2,
    "entry_block": 3,
    "entry_block_flush": 4,
    "header_block": 5,
    "header_block_flush": 6,
}
INJECTION = {"before_write": 0, "torn_write": 1, "after_write": 2, "at_flush": 3}
FIXTURE = {("v3_003", "pass1"): 1, ("v3_003", "pass2"): 2, ("no_lower_run", "pass1"): 3}
MODE = {"flush_required": 0, "write_through": 1}
GROUP_TOTAL = {("v3_003", "pass1"): 1_051_653, ("v3_003", "pass2"): 1_051_653,
               ("no_lower_run", "pass1"): 1_542}


class Snapshot(C.Structure):
    _fields_ = [
        ("block_count", C.c_uint32),
        ("primary", C.c_ubyte * 512),
        ("mirror", C.c_ubyte * 512),
        ("slots", (C.c_ubyte * 1024) * 4),
    ]


class Info(C.Structure):
    _fields_ = [
        ("uuid", C.c_ubyte * 16),
        ("total_chunks", C.c_uint32),
        ("free_chunks", C.c_uint32),
        ("entry_count", C.c_uint32),
        ("total_frames", C.c_uint64),
        ("side_b_valid", C.c_uint8),
    ]


class Hashes(C.Structure):
    _fields_ = [
        ("live_a", C.c_ubyte * 32),
        ("source", C.c_ubyte * 32),
        ("copy", C.c_ubyte * 32),
    ]


class Result(C.Structure):
    _fields_ = [
        ("injection_fired", C.c_int32),
        ("remount_result", C.c_int32),
        ("remount_writes", C.c_int32),
        ("event_op", C.c_int32),
        ("event_lba", C.c_uint32),
        ("event_count", C.c_uint32),
        ("has_target_block", C.c_int32),
        ("metadata_changed", C.c_int32),
        ("info", Info),
        ("before", C.c_ubyte * 512),
        ("intended", C.c_ubyte * 512),
        ("durable", C.c_ubyte * 512),
        ("post", Snapshot),
    ]


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def bhex(value) -> str:
    return bytes(value).hex()


def snapshot_dict(s: Snapshot) -> dict:
    return {
        "block_count": int(s.block_count),
        "primary_hex": bhex(s.primary),
        "mirror_hex": bhex(s.mirror),
        "slot_prefix_hex": [bhex(s.slots[i]) for i in range(4)],
    }


def result_name(value: int) -> str:
    return RESULT_NAMES[value] if 0 <= value < len(RESULT_NAMES) else f"TAPE_RESULT_{value}"


def load_lib():
    if not LIB.is_file():
        raise RuntimeError(f"worker library missing: {LIB}")
    lib = C.CDLL(str(LIB))
    lib.rf_open.argtypes = [C.c_char_p, C.c_int, C.c_int]
    lib.rf_open.restype = C.c_int
    lib.rf_close.argtypes = []
    lib.rf_close.restype = None
    lib.rf_get_pre_snapshot.argtypes = [C.POINTER(Snapshot)]
    lib.rf_get_pre_snapshot.restype = C.c_int
    lib.rf_get_hashes.argtypes = [C.POINTER(Hashes)]
    lib.rf_get_hashes.restype = C.c_int
    lib.rf_case.argtypes = [
        C.c_int, C.c_uint32, C.c_int, C.c_uint32, C.POINTER(Result)
    ]
    lib.rf_case.restype = C.c_int
    return lib


def case_stream(fixture: str, pass_name: str, mode: str, start: int, end: int):
    selected = (
        c for c in iter_cases()
        if c["fixture"] == fixture and c["pass"] == pass_name and c["mode"] == mode
    )
    yield from itertools.islice(selected, start, end)


def raw_hashes(fixture: str, pass_name: str, post: dict, hashes: Hashes) -> dict:
    live = bhex(hashes.live_a)
    source = bhex(hashes.source)
    copy = bhex(hashes.copy)
    out = {"live_a": live}
    layout = layout_name(fixture, from_compact(post))
    if fixture == "v3_003" and pass_name == "pass1":
        out["source_10_12"] = source
        if layout == "post_pass1":
            out["copy_12_14"] = copy
    elif fixture == "v3_003" and pass_name == "pass2":
        out["pass1_12_14"] = source
        if layout == "post_pass2":
            out["copy_10_12"] = copy
    else:
        out["source_fragments"] = source
        if layout == "post_pass1":
            out["copy_10_frames"] = copy
    return out


def observation(case: dict, r: Result, pre: dict, hashes: Hashes) -> dict:
    post = snapshot_dict(r.post) if r.metadata_changed else pre
    target = {"target": case["target"]}
    if r.event_op == 1:
        target.update({"op": "write", "lba": int(r.event_lba), "count": int(r.event_count)})
    else:
        target["op"] = "flush"

    obs = {
        "format": "WP10-RESPOOL-OBSERVATION-1",
        "case_id": case_id(case),
        "injection_fired": bool(r.injection_fired),
        "fresh_remount_from_durable_only": True,
        "actual_remount_result": result_name(int(r.remount_result)),
        "remount_side": "B",
        "remount_info": {
            "uuid_hex": bhex(r.info.uuid),
            "total_chunks": int(r.info.total_chunks),
            "free_chunks": int(r.info.free_chunks),
            "entry_count": int(r.info.entry_count),
            "total_frames": int(r.info.total_frames),
            "side_b_valid": bool(r.info.side_b_valid),
        },
        "pre_snapshot": pre,
        "post_snapshot": post,
        "target_event": target,
        "live_a_sha256": bhex(hashes.live_a),
        "raw_region_sha256": raw_hashes(case["fixture"], case["pass"], post, hashes),
    }
    if r.has_target_block:
        obs["target_block"] = {
            "before_hex": bhex(r.before),
            "intended_hex": bhex(r.intended),
            "durable_hex": bhex(r.durable),
        }
    return obs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", choices=("v3_003", "no_lower_run"), required=True)
    ap.add_argument("--pass-name", choices=("pass1", "pass2"), required=True)
    ap.add_argument("--mode", choices=("flush_required", "write_through"), required=True)
    ap.add_argument("--part", type=int, required=True)
    ap.add_argument("--parts", type=int, required=True)
    ap.add_argument("--evidence", type=Path, required=True)
    args = ap.parse_args()

    key = (args.fixture, args.pass_name)
    if key not in FIXTURE:
        raise SystemExit("invalid fixture/pass")
    if args.part < 0 or args.parts < 1 or args.part >= args.parts:
        raise SystemExit("invalid shard part")

    head = git("rev-parse", "HEAD")
    tree = git("rev-parse", "HEAD^{tree}")
    product_commit = os.environ.get("PRODUCT_COMMIT") or head
    if head != product_commit:
        raise SystemExit(f"workspace/head mismatch {head} != {product_commit}")
    verifier_tree = git("rev-parse", "HEAD:tests/respool_full_draft8")
    if verifier_tree != EXPECTED_TREE:
        raise SystemExit(f"verifier tree mismatch {verifier_tree}")

    total = GROUP_TOTAL[key]
    start = total * args.part // args.parts
    end = total * (args.part + 1) // args.parts
    evidence = args.evidence if args.evidence.is_absolute() else ROOT / args.evidence
    evidence.mkdir(parents=True, exist_ok=True)
    failure_path = evidence / "failure-reproducer.json"

    digest = hashlib.sha256()
    by_target: dict[str, int] = {}
    count = 0
    first_index = None
    last_index = None

    with tempfile.TemporaryDirectory(prefix="respool-full-") as td:
        raw_path = Path(td) / "fixture.raw"
        build_raw_image(args.fixture, args.pass_name, raw_path)
        lib = load_lib()
        rc = lib.rf_open(
            os.fsencode(raw_path),
            FIXTURE[key],
            MODE[args.mode],
        )
        if rc != 0:
            raise SystemExit(f"worker initialization failed: {rc}")

        pre_s = Snapshot()
        hashes = Hashes()
        if lib.rf_get_pre_snapshot(C.byref(pre_s)) != 0:
            raise SystemExit("worker pre-snapshot unavailable")
        if lib.rf_get_hashes(C.byref(hashes)) != 0:
            raise SystemExit("worker region hashes unavailable")
        pre = snapshot_dict(pre_s)

        try:
            for case in case_stream(args.fixture, args.pass_name, args.mode, start, end):
                inj = case["injection"]
                ordinal = int(inj.get("write_ordinal", 0))
                landed = int(inj.get("landed_bytes", 0))
                r = Result()
                call_rc = lib.rf_case(
                    TARGET[case["target"]],
                    ordinal,
                    INJECTION[inj["kind"]],
                    landed,
                    C.byref(r),
                )
                if call_rc != 0:
                    raise RuntimeError(f"worker case protocol failure {call_rc}")

                obs = observation(case, r, pre, hashes)
                try:
                    if r.remount_writes:
                        raise OracleError(
                            f"fresh crash remount unexpectedly issued {r.remount_writes} writes"
                        )
                    validate_crash_observation(case, obs)
                except Exception as exc:
                    repro_sha = retain_failure(failure_path, case, obs, str(exc))
                    summary = {
                        "format": "WP10-RESPOOL-SHARD-1",
                        "status": "FAIL",
                        "fixture": args.fixture,
                        "pass": args.pass_name,
                        "mode": args.mode,
                        "part": args.part,
                        "parts": args.parts,
                        "range": [start, end],
                        "completed": count,
                        "failed_case_index": case["case_index"],
                        "failure_reproducer_sha256": repro_sha,
                        "product_commit": product_commit,
                        "product_tree": tree,
                        "verifier_import_commit": EXPECTED_IMPORT,
                        "verifier_tree": verifier_tree,
                    }
                    (evidence / "summary.json").write_text(
                        json.dumps(summary, indent=2, sort_keys=True) + "\n"
                    )
                    print(f"FAIL case={case['case_index']} reason={exc}")
                    return 1

                digest.update((canonical_json(case) + "\n").encode("ascii"))
                by_target[case["target"]] = by_target.get(case["target"], 0) + 1
                count += 1
                if first_index is None:
                    first_index = case["case_index"]
                last_index = case["case_index"]
        finally:
            lib.rf_close()

    summary = {
        "format": "WP10-RESPOOL-SHARD-1",
        "status": "PASS",
        "fixture": args.fixture,
        "pass": args.pass_name,
        "mode": args.mode,
        "part": args.part,
        "parts": args.parts,
        "range": [start, end],
        "completed": count,
        "first_case_index": first_index,
        "last_case_index": last_index,
        "canonical_subset_sha256": digest.hexdigest(),
        "by_target": dict(sorted(by_target.items())),
        "product_base": EXPECTED_BASE,
        "product_commit": product_commit,
        "product_tree": tree,
        "verifier_import_commit": EXPECTED_IMPORT,
        "verifier_tree": verifier_tree,
        "failure_reproducer_sha256": None,
    }
    (evidence / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(
        f"PASS {args.fixture}:{args.pass_name}:{args.mode} "
        f"part={args.part}/{args.parts} cases={count} range={start}:{end}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
