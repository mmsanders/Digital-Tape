#!/usr/bin/env python3
"""Any-subset campaign through the existing WP-10 format/dup worker
(format_dup_identity_adapter): tape_format and tape_dup onto every accepted raw
destination shape. Product #440; see subset_driver.py for what is and is not done here.

    python3 tests/wp10_subset_binding/run_dup.py --evidence DIR [--shard I/N] [--jobs J]

Sources and shapes are the existing adapter's (write_source, write_shape, from the
verifier's fixture). The whole format/dup call is the operation; every destination
callback is transported. Verification applies the DRAFT-10 identity/residue predicates
(tapefs §9.5/§9.6, wp10_residue_d10 / wp10_backlog_r54 supersession) to the projections;
this binding carries no DRAFT-9 fixed-identity expectation.
"""
from __future__ import annotations

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tests" / "format_dup_identity_adapter"))
import subset_driver as sd  # noqa: E402
import adapter as fd  # noqa: E402  (the existing Product binding: sources, shapes, worker)
from planner import OPERATIONS, RAW_SHAPES  # noqa: E402

NAME = "format_dup"
worker_path = fd.WORKER


def scenarios(only=None):
    keys = [(op, shape) for op in OPERATIONS for shape in RAW_SHAPES]
    return [k for k in keys if only is None or "/".join(k).startswith(only)]


def remount_key(key) -> str:
    return "A"


def make_worker(tmp: Path) -> sd.Worker:
    src, big = tmp / "source.bin", tmp / "source_big.bin"
    fd.write_source(src)
    fd.write_source_big(big)
    shapes = []
    for name in fd.raw_shapes():
        p = tmp / f"{name}.bin"
        fd.write_shape(p, name)
        shapes.append(str(p))
    return sd.Worker([str(fd.WORKER), str(src), str(big)] + shapes)


def s_run(w, tmp, key, base, cut_unit, cut_flush, err_call, err_flush):
    tr, init = tmp / "trace.jsonl", tmp / "initial.img"
    res = w.ask("S", key[0], key[1], "-" if base is None else "@" + str(base), str(cut_unit), str(cut_flush),
                str(err_call), str(err_flush), str(tr), str(init))
    return res, sd.read_trace(tr), init.read_bytes()


def remount(w, tmp, key, image: bytes) -> dict:
    p = tmp / "proj.img"
    p.write_bytes(image)
    obs = w.ask("R", str(p))
    snap = obs["image_snapshot"]
    if bytes.fromhex(snap["primary_hex"]) != image[:sd.BLOCK] or bytes.fromhex(snap["mirror_hex"]) != image[-sd.BLOCK:]:
        raise RuntimeError("worker remounted different bytes than the projection")
    return obs


if __name__ == "__main__":
    sys.exit(sd.campaign_main(sys.modules[__name__]))
