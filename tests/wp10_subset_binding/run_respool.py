#!/usr/bin/env python3
"""Any-subset campaign through the existing WP-10 respool worker (respool_full_adapter):
v3_003 pass 1 and pass 2, and the no-lower-run decline. Product #440; see subset_driver.py
for what is and is not done here.

    python3 tests/wp10_subset_binding/run_respool.py --evidence DIR [--shard I/N] [--jobs J]

The raw images are the existing adapter's (media_image.build_raw_image, from the
verifier's fixture). rf_subset mounts side B and respools to completion or to the cut,
transporting every callback; rf_subset_remount is the existing fresh side-B remount on a
projection's bytes only (the virtual device does not let a remount change them).
"""
from __future__ import annotations

import ctypes as C
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tests" / "respool_full_adapter"))
import subset_driver as sd  # noqa: E402
import run_shard as rs  # noqa: E402  (the existing Product binding: ctypes structs, names)
from media_image import build_raw_image  # noqa: E402

NAME = "respool_full"
worker_path = rs.LIB
FIXTURES = [("v3_003", "pass1"), ("v3_003", "pass2"), ("no_lower_run", "pass1")]


class SubResult(C.Structure):
    _fields_ = [("mount_result", C.c_int32), ("op_result", C.c_int32), ("respool_calls", C.c_int32),
                ("cut_fired", C.c_int32), ("error_fired", C.c_int32),
                ("units", C.c_uint32), ("calls", C.c_uint32), ("barriers", C.c_uint32),
                ("op_units", C.c_uint32), ("op_calls", C.c_uint32), ("op_barriers", C.c_uint32)]


def scenarios(only=None):
    return [k for k in FIXTURES if only is None or "/".join(k).startswith(only)]


def remount_key(key) -> str:
    return "B"


class W:
    def __init__(self, tmp: Path):
        self.lib = rs.load_lib()
        self.lib.rf_subset.argtypes = [C.c_char_p, C.c_long, C.c_long, C.c_long, C.c_long, C.c_char_p,
                                       C.POINTER(SubResult)]
        self.lib.rf_subset.restype = C.c_int
        self.lib.rf_subset_remount.argtypes = [C.c_char_p, C.POINTER(rs.Info), C.POINTER(rs.Snapshot),
                                               C.POINTER(C.c_int32), C.POINTER(C.c_int32)]
        self.lib.rf_subset_remount.restype = C.c_int
        self.images = {}
        for k in FIXTURES:
            p = tmp / f"{k[0]}-{k[1]}.img"
            build_raw_image(k[0], k[1], p)
            self.images[k] = p

    def close(self) -> int:
        self.lib.rf_close()
        return 0


def make_worker(tmp: Path) -> W:
    return W(tmp)


def _arg(v) -> int:
    return -1 if v == "-" else int(v)


def s_run(w, tmp, key, base, cut_unit, cut_flush, err_call, err_flush):
    path = w.images[key] if base is None else Path(base)
    tr = tmp / "trace.jsonl"
    r = SubResult()
    rc = w.lib.rf_subset(str(path).encode(), _arg(cut_unit), _arg(cut_flush), _arg(err_call), _arg(err_flush),
                         str(tr).encode(), C.byref(r))
    if rc != 0:
        raise RuntimeError(f"rf_subset returned {rc}")
    res = {f: int(getattr(r, f)) for f, _ in SubResult._fields_}
    res["format"] = "WP10-SUBSET-RUN-1"
    res["mount_result"] = rs.result_name(res["mount_result"])
    res["operation_result"] = rs.result_name(res.pop("op_result")) if res["mount_result"] == "TAPE_OK" else "NOT_RUN"
    res["setup_ok"] = res["mount_result"] == "TAPE_OK"
    return res, sd.read_trace(tr), path.read_bytes()


def remount(w, tmp, key, image: bytes) -> dict:
    p = tmp / "proj.img"
    p.write_bytes(image)
    info, post, rr, wr = rs.Info(), rs.Snapshot(), C.c_int32(), C.c_int32()
    rc = w.lib.rf_subset_remount(str(p).encode(), C.byref(info), C.byref(post), C.byref(rr), C.byref(wr))
    if rc != 0:
        raise RuntimeError(f"rf_subset_remount returned {rc}")
    snap = rs.snapshot_dict(post)
    if bytes.fromhex(snap["primary_hex"]) != image[:sd.BLOCK] or bytes.fromhex(snap["mirror_hex"]) != image[-sd.BLOCK:]:
        raise RuntimeError("remount saw different bytes than the projection")
    return {"format": "WP10-SUBSET-REMOUNT-1", "remount_side": "B",
            "actual_remount_result": rs.result_name(int(rr.value)), "remount_writes": int(wr.value),
            "remount_info": {"uuid_hex": rs.bhex(info.uuid), "total_chunks": int(info.total_chunks),
                             "free_chunks": int(info.free_chunks), "entry_count": int(info.entry_count),
                             "total_frames": int(info.total_frames), "side_b_valid": bool(info.side_b_valid)},
            "image_snapshot": snap}


if __name__ == "__main__":
    sys.exit(sd.campaign_main(sys.modules[__name__]))
