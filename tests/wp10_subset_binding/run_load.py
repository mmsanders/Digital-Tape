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

Cut histories are projections of the COMPLETE run's actual trace at each coordinate, not
interrupted host executions (the route is deterministic; see Coordinates above).

Remount (V186-01): tapectl-test verify (its trace: engine_mount and engine_info results), and
dump of side A and of side B (the rendered PCM, hashed), each a fresh process on its own fresh
copy of the projection. Each command's image hash before and after, its trace and its output
are recorded; a command that changed its image is listed in mutated_by. No command's output
image is ever another command's input.
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


def _fresh(tmp: Path, image: bytes, name: str) -> Path:
    p = tmp / name
    p.write_bytes(image)
    return p


def remount(w, tmp, key, image: bytes) -> dict:
    """Each command is its own fresh process on its OWN pristine copy of the projection
    (Verification #186 V186-01): a command that repairs or otherwise writes its image can
    never supply another command's starting bytes. Every command records its image hash
    before and after, its own seam trace and its output; a changed image is reported as
    mutated (lawful repair is judged by the operation's own oracle, not here)."""
    want = sd.sha(image)
    obs = {"format": "WP10-SUBSET-REMOUNT-2", "projection_sha256": want, "fresh_image_per_command": True}
    for cmd in ("verify", "dump_A", "dump_B"):
        p = _fresh(tmp, image, f"remount-{cmd}.img")
        before = sd.sha_file(p)
        if before != want:
            raise RuntimeError("the fresh copy is not the projection")
        tr = tmp / f"{cmd}-trace.json"
        if tr.exists():
            tr.unlink()
        if cmd == "verify":
            r = tapectl(["verify", str(p)], {"TAPECTL_TEST_TRACE": str(tr)})
        else:
            out = tmp / f"{cmd}.wav"
            if out.exists():
                out.unlink()
            r = tapectl(["dump", str(p), "--side", cmd[-1], "-o", str(out)], {"TAPECTL_TEST_TRACE": str(tr)})
        seam = json.loads(tr.read_text()) if tr.exists() else {"events": []}
        after = sd.sha_file(p)
        rec = {"exit": r.returncode, "stdout": r.stdout, "stderr": r.stderr,
               "image_sha256_before": before, "image_sha256_after": after, "image_mutated": after != before,
               "seam_trace_sha256": sd.sha_file(tr) if tr.exists() else None,
               "engine": [e for e in seam["events"] if e["kind"] in ("engine_mount", "engine_info", "engine_bind")],
               "seam_writes": sum(1 for e in seam["events"] if e["kind"] == "write"),
               "seam_flushes": sum(1 for e in seam["events"] if e["kind"] == "flush")}
        if cmd != "verify":
            rec["wav_sha256"] = sd.sha_file(out) if out.exists() else None
        obs[cmd] = rec
    # the earlier single-copy fields, kept for readers of REMOUNT-1, now per command
    obs["verify_exit"], obs["verify_stdout"], obs["verify_stderr"] = (
        obs["verify"]["exit"], obs["verify"]["stdout"], obs["verify"]["stderr"])
    obs["mutated_by"] = [c for c in ("verify", "dump_A", "dump_B") if obs[c]["image_mutated"]]
    return obs


if __name__ == "__main__":
    sys.exit(sd.campaign_main(sys.modules[__name__]))
