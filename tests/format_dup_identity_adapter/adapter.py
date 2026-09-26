#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
PKG = HERE.parent / "format_dup_identity_draft8"
sys.path.insert(0, str(PKG))

from fixture import (  # noqa: E402
    BLOCK, OLD_A0, OLD_B0, OLD_UUID_A, index_head, initial_snapshot, raw_shapes,
    superblock,
)
from planner import EXPECTED_CASESET_SHA256  # noqa: E402

WORKER = HERE / "build" / "r29_format_dup_worker"
ADAPTER_ID = "digital-tape-r29-format-dup-product"


def need(c: bool, m: str) -> None:
    if not c:
        raise RuntimeError(m)


def write_shape(path: Path, shape: str) -> None:
    s = initial_snapshot(shape)
    path.write_bytes(
        bytes.fromhex(s["primary_hex"])
        + bytes.fromhex(s["mirror_hex"])
        + bytes.fromhex(s["a0_head_hex"])
        + bytes.fromhex(s["b0_head_hex"])
    )


def _audio_block() -> bytes:
    audio = bytearray(BLOCK)
    for i in range(100):
        struct.pack_into("<hh", audio, i * 4, i + 1, 100 - i)
    return bytes(audio)


def write_source(path: Path) -> None:
    # Product setup only. Ten seconds derives exactly the verifier fixture's four
    # chunks at BLOCK_COUNT=6145; the published destination snapshots stay untouched.
    # Side A is 100 non-silent frames in chunk 0; Side B references the same run.
    sb = superblock(generation=1, uuid=OLD_UUID_A, high=1, nominal=10)
    entry = bytearray(BLOCK)
    struct.pack_into("<III", entry, 0, 0, 0, 100)
    path.write_bytes(sb + sb + OLD_A0 + bytes(entry) + OLD_B0 + _audio_block())


def write_source_big(path: Path) -> None:
    # Product setup for the dup_capacity refusal only: Side A is 131,073 frames,
    # so it needs two chunks, and a one-second destination derives one.
    frames = 131_073
    sb = superblock(generation=1, uuid=OLD_UUID_A, high=2, nominal=10)
    entry = bytearray(BLOCK)
    struct.pack_into("<III", entry, 0, 0, 0, frames)
    a0 = index_head(side=0, sequence=100, frames=frames)
    path.write_bytes(sb + sb + a0 + bytes(entry) + OLD_B0 + _audio_block())


CONTRACT_PARAM = {
    "equal_divergent_refusal": "variant",
    "dup_in_progress_row": "column",
    "zero_budget": "variant",
    "changed_argument": "argument",
    "destination_failure_playing": None,
    "callback_reentry": "column",
    "faulted_source": "variant",
    "small_budget_completion": "variant",
}


def send(proc: subprocess.Popen[str], line: str) -> None:
    assert proc.stdin is not None
    proc.stdin.write(line + "\n")
    proc.stdin.flush()


def recv(proc: subprocess.Popen[str]) -> dict:
    assert proc.stdout is not None
    line = proc.stdout.readline()
    if line == "":
        raise RuntimeError("product worker stdout closed")
    obj = json.loads(line)
    need(isinstance(obj, dict), "worker response is not object")
    return obj


def observed_baseline(raw: dict) -> list[dict]:
    out = []
    for i, t in enumerate(raw.get("targets", [])):
        lba = t["lba"]
        out.append(
            {
                "phase": "step1" if i < 2 else "identity",
                "copy": "primary" if lba == 0 else "mirror",
                "lba": lba,
                "sha256": t["sha256"],
            }
        )
    return out


def main() -> int:
    need(WORKER.is_file(), f"worker missing: {WORKER}")
    with tempfile.TemporaryDirectory(prefix="r29-fmtdup-") as td:
        d = Path(td)
        source = d / "source.bin"
        write_source(source)
        source_big = d / "source_big.bin"
        write_source_big(source_big)
        shape_paths = {}
        for name in raw_shapes():
            p = d / f"{name}.bin"
            write_shape(p, name)
            shape_paths[name] = p

        argv = [str(WORKER), str(source), str(source_big)] + [str(shape_paths[n]) for n in raw_shapes()]
        proc = subprocess.Popen(
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr,
            text=True, bufsize=1,
        )

        print(
            json.dumps(
                {
                    "format": "FMTDUP-ID-ADAPTER-2",
                    "adapter_kind": "product",
                    "adapter_id": ADAPTER_ID,
                    "caseset_sha256": EXPECTED_CASESET_SHA256,
                    "raw_observation_only": True,
                },
                sort_keys=True, separators=(",", ":"),
            ),
            flush=True,
        )

        baselines: dict[tuple[str, str], list[dict]] = {}
        try:
            for line in sys.stdin:
                case = json.loads(line)
                need(isinstance(case, dict), "runner case is not object")
                if case.get("command") == "done":
                    send(proc, "D")
                    assert proc.stdin is not None
                    proc.stdin.close()
                    return 0 if proc.wait(timeout=5) == 0 else 2

                if case.get("scope") == "contract":
                    fam = case["family"]
                    need(fam in CONTRACT_PARAM, f"unknown contract family {fam}")
                    key_name = CONTRACT_PARAM[fam]
                    param = case[key_name] if key_name else "-"
                    send(proc, "\t".join(["K", str(case["case_index"]), fam, param]))
                    raw = recv(proc)
                    need(raw.get("case_index") == case["case_index"], "worker case drift")
                    obs = {
                        "format": "FMTDUP-ID-OBSERVATION-2",
                        "scope": "contract",
                        "family": fam,
                        **raw,
                    }
                    print(json.dumps(obs, sort_keys=True, separators=(",", ":")), flush=True)
                    continue

                need(case.get("scope") == "crash", "unknown case scope")
                op = case["operation"]
                shape = case["shape"]
                key = (op, shape)
                if key not in baselines:
                    send(proc, f"B\t{op}\t{shape}")
                    baselines[key] = observed_baseline(recv(proc))

                inj = case["injection"]
                ordinal = inj.get("write_ordinal", inj.get("flush_ordinal", 0))
                landed = inj.get("landed_bytes", 0)
                send(
                    proc,
                    "\t".join(
                        [
                            "C", str(case["case_index"]), op, shape, case["mode"],
                            inj["kind"], str(ordinal), str(landed),
                        ]
                    ),
                )
                raw = recv(proc)
                obs = {
                    "format": "FMTDUP-ID-OBSERVATION-2",
                    "case_index": case["case_index"],
                    "scope": "crash",
                    "injection_fired": raw["injection_fired"],
                    "pre_snapshot": initial_snapshot(shape),
                    "post_snapshot": raw["post_snapshot"],
                    "target_baseline": baselines[key],
                    "actual_remount_result": raw["actual_remount_result"],
                }
                if "actual_selected_uuid" in raw:
                    obs["actual_selected_uuid"] = raw["actual_selected_uuid"]
                print(json.dumps(obs, sort_keys=True, separators=(",", ":")), flush=True)
        except Exception as exc:
            try:
                proc.kill()
            except OSError:
                pass
            print(f"adapter failure: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
