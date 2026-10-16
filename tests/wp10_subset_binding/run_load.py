#!/usr/bin/env python3
"""Any-subset campaign through the existing host load route (tapectl load: the public
arm/feed/service/commit transaction, WP-11/WP-14), via the tapectl-test observation seam
(host/port/tseam.h, ADR-164). Product #440; see subset_driver.py for what is and is not done
here. There is no tape_load API and none is invented.

    python3 tests/wp10_subset_binding/run_load.py --evidence DIR [--shard I/N] [--jobs J]

Scenario: the accepted golden source tests/golden/src/voice.wav loaded onto a freshly
provisioned 32 MiB, 5 s image. The seam's TAPECTL_TEST_TRACE with TAPECTL_TEST_PAYLOADS=1
records every actual port write (absolute offset, bytes, payload, result) and barrier result
of the unchanged tapectl-test; each 512-byte unit becomes one event at LBA offset/512.

Coordinates. The route is deterministic, so a power cut at op unit k (or at the entry of
barrier j) leaves exactly the complete run's actual history up to that point; the other
bindings' real cut runs were each checked to be such a prefix. Error at a barrier is the
seam's existing native-flush-error fault (a real failed OS barrier); it fails every barrier,
so only "error at barrier 0" is reachable. The seam has no write-error fault, so error-write
coordinates are recorded as not reachable on this route without changing the test binary.

Remount: on a copy of the projection, tapectl-test verify (its trace: engine_mount and
engine_info results) and dump of side A and side B (the rendered PCM, hashed), each a fresh
process from those bytes only; the copy's hash after the three commands is recorded.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import subset_driver as sd  # noqa: E402

NAME = "host_load"
TAPECTL = ROOT / "build" / "host" / "tapectl-test"
worker_path = TAPECTL
SOURCE = ROOT / "tests" / "golden" / "src" / "voice.wav"
IMAGE_BYTES, LENGTH_S = 33554432, 5
PROVISION = ["--label", "SUBSET", "--length-s", str(LENGTH_S), "--uuid", "00112233445566778899aabbccddeeff",
             "--epoch", "1760000000", "--image-bytes", str(IMAGE_BYTES)]


def scenarios(only=None):
    keys = [("load", "voice.wav")]
    return [k for k in keys if only is None or "/".join(k).startswith(only)]


def remount_key(key) -> str:
    return "verify+dump A,B"


def unreachable(key, kind, x):
    if kind == "error_write":
        return "the existing tapectl-test seam has no write-error fault"
    if kind == "error_barrier" and x != 0:
        return "native-flush-error fails every barrier; only barrier 0 can be the first failure"
    return None


def tapectl(args, env=None, cwd=None):
    e = {k: v for k, v in os.environ.items() if not k.startswith("TAPECTL_TEST")}
    e.update(env or {})
    return subprocess.run([str(TAPECTL)] + args, env=e, cwd=cwd, capture_output=True, text=True)


class W:
    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.base = tmp / "provisioned.img"
        r = tapectl(["provision", str(self.base)] + PROVISION)
        if r.returncode != 0:
            raise RuntimeError("provision failed: " + r.stderr)
        self.complete = {}           # base image sha -> (trace rows, result)

    def close(self) -> int:
        return 0


def make_worker(tmp: Path) -> W:
    return W(tmp)


def _load(w, image: Path, fault=None):
    work = w.tmp / "load.img"
    shutil.copyfile(image, work)
    tr = w.tmp / "load-trace.json"
    env = {"TAPECTL_TEST_TRACE": str(tr), "TAPECTL_TEST_PAYLOADS": "1"}
    if fault:
        env["TAPECTL_TEST_FAULT"] = fault
    r = tapectl(["load", str(work), str(SOURCE)], env)
    seam = json.loads(tr.read_text())
    rows, call, nid, fl = [], 0, 0, 0
    for e in seam["events"]:
        if e["kind"] == "write":
            data = bytes.fromhex(e["data_hex"])
            if e["offset"] % sd.BLOCK or len(data) != e["bytes"] or e["bytes"] % sd.BLOCK:
                raise RuntimeError("seam write is not whole 512-byte units")
            for i in range(e["bytes"] // sd.BLOCK):
                rows.append({"t": "W", "id": nid, "call": call, "lba": e["offset"] // sd.BLOCK + i,
                             "ack": bool(e["ok"]), "phase": "op",
                             "hex": data[i * sd.BLOCK:(i + 1) * sd.BLOCK].hex()})
                nid += 1
            call += 1
        elif e["kind"] == "flush":
            rows.append({"t": "F", "ord": fl, "ok": bool(e["success"]), "phase": "op"})
            fl += 1
    res = {"format": "WP10-SUBSET-RUN-1", "route": "tapectl-test load", "exit": r.returncode,
           "stdout": r.stdout, "stderr": r.stderr, "seam_success": seam.get("success"),
           "fault": fault, "setup_ok": True, "operation_result": "exit %d" % r.returncode,
           "op_units": nid, "op_calls": call, "op_barriers": fl, "seam_trace_sha256": sd.sha_file(tr)}
    return rows, res


def s_run(w, tmp, key, base, cut_unit, cut_flush, err_call, err_flush):
    image = w.base if base is None else Path(base)
    initial = image.read_bytes()
    if err_flush != "-":
        rows, res = _load(w, image, fault="native-flush-error")
        return dict(res, error_fired=True), rows, initial
    h = sd.sha(initial)
    if h not in w.complete:
        w.complete[h] = _load(w, image)
    rows, res = w.complete[h]
    res = dict(res, cut_fired=False)
    if cut_unit != "-" or cut_flush != "-":
        out, units, bars = [], 0, 0
        for r in rows:
            if r["t"] == "W" and cut_unit != "-" and units >= int(cut_unit):
                out.append({"t": "CUT", "at": "unit", "op_unit": int(cut_unit), "call": r["call"],
                            "units_in_call": sum(1 for x in out if x["t"] == "W" and x["call"] == r["call"])})
                res["cut_fired"] = True
                break
            if r["t"] == "F" and cut_flush != "-" and bars == int(cut_flush):
                out.append({"t": "CUT", "at": "flush_entry", "op_flush": int(cut_flush)})
                res["cut_fired"] = True
                break
            out.append(r)
            units += r["t"] == "W"
            bars += r["t"] == "F"
        # single-unit calls on this route: a cut never splits a call
        res["history"] = "complete run's actual history up to the coordinate"
        return res, out, initial
    return res, rows, initial


def remount(w, tmp, key, image: bytes) -> dict:
    p = tmp / "remount.img"
    p.write_bytes(image)
    tr = tmp / "verify-trace.json"
    v = tapectl(["verify", str(p)], {"TAPECTL_TEST_TRACE": str(tr)})
    seam = json.loads(tr.read_text()) if tr.exists() else {"events": []}
    obs = {"format": "WP10-SUBSET-REMOUNT-1", "verify_exit": v.returncode, "verify_stdout": v.stdout,
           "verify_stderr": v.stderr,
           "engine": [e for e in seam["events"] if e["kind"] in ("engine_mount", "engine_info", "engine_bind")]}
    for side in ("A", "B"):
        out = tmp / f"dump-{side}.wav"
        if out.exists():
            out.unlink()
        d = tapectl(["dump", str(p), "--side", side, "-o", str(out)])
        obs[f"dump_{side}"] = {"exit": d.returncode, "stderr": d.stderr,
                               "wav_sha256": sd.sha_file(out) if out.exists() else None}
    obs["image_sha256_after"] = sd.sha_file(p)
    return obs


if __name__ == "__main__":
    sys.exit(sd.campaign_main(sys.modules[__name__]))
