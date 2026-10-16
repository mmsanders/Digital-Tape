#!/usr/bin/env python3
"""Any-subset campaign through the existing WP-10 promote worker (promote_adapter):
fresh allocation, fresh adoption and first-use S0 scenarios, the partner/candidate
closure starts (phase x seed), and the decline/resume re-run seeds. Product #440; see
subset_driver.py for what is and is not done here.

    python3 tests/wp10_subset_binding/run_promote.py --evidence DIR [--shard I/N] [--jobs J]

Every medium is the existing adapter's own (adapter.build_media, from the verifier's
fixture and oracle encoders). S mounts side A (closure starts: mount writes refused exactly
as the old Z command does) and promotes to completion or to the cut; every own-device
callback is transported. Projections are remounted by R: the worker's existing
remount-and-render facts for both sides, from the projection's bytes only.
"""
from __future__ import annotations

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tests" / "promote_adapter"))
import subset_driver as sd  # noqa: E402
import adapter as promote  # noqa: E402  (the existing Product binding: media and worker)
from planner import CLOSURE_PHASES, CLOSURE_SEEDS, SCENARIO_PHASES  # noqa: E402
from oracle import RERUN_SEEDS  # noqa: E402

NAME = "promote"
worker_path = promote.WORKER
BLOCK = sd.BLOCK
_MEDIA = None


def media():
    global _MEDIA
    if _MEDIA is None:
        _MEDIA = promote.build_media()
    return _MEDIA


def scenarios(only=None):
    keys = [(s, "0") for s in SCENARIO_PHASES]
    keys += [(f"closure_{p}_{s}", "1") for p in CLOSURE_PHASES for s in CLOSURE_SEEDS]
    keys += [(f"seed_{r}", "0") for r in RERUN_SEEDS]
    return [k for k in keys if only is None or k[0].startswith(only)]


def remount_key(key) -> str:
    return "A+B"


def nblocks(total_chunks: int) -> int:
    return promote.LBA_CHUNK_BASE + total_chunks * promote.CHUNK_BLOCKS + 1


def full_image(m) -> bytes:
    img = bytearray(nblocks(m["total_chunks"]) * BLOCK)
    for lba, data in m["blocks"].items():
        img[lba * BLOCK:(lba + 1) * BLOCK] = bytes(data)
    return bytes(img)


def sparse(image: bytes, total_chunks: int) -> dict:
    blocks = {}
    for lba in range(len(image) // BLOCK):
        b = image[lba * BLOCK:(lba + 1) * BLOCK]
        if any(b):
            blocks[lba] = b
    return {"total_chunks": total_chunks, "blocks": blocks}


class W:
    def __init__(self):
        self.w = promote.Worker()
        for name, m in media().items():
            self.w.load(name, m)

    def ask(self, *fields):
        return self.w.ask("\t".join(fields))

    def close(self) -> int:
        self.w.send("D")
        self.w.p.stdin.close()
        return self.w.p.wait(timeout=60)


def make_worker(tmp: Path) -> W:
    return W()


def s_run(w, tmp, key, base, cut_unit, cut_flush, err_call, err_flush):
    name, closure = key
    m = media()[name]
    if base is None:
        initial, mname = full_image(m), name
    else:
        initial, mname = Path(base).read_bytes(), "subset:base"
        w.w.load(mname, sparse(initial, m["total_chunks"]))
    tr = tmp / "trace.jsonl"
    res = w.ask("S", mname, closure, str(cut_unit), str(cut_flush), str(err_call), str(err_flush), str(tr))
    res["setup_ok"] = res["mount_result"] == "TAPE_OK"
    return res, sd.read_trace(tr), initial


def remount(w, tmp, key, image: bytes) -> dict:
    m = media()[key[0]]
    w.w.load("subset:proj", sparse(image, m["total_chunks"]))
    obs = w.ask("R", "subset:proj")
    if bytes.fromhex(obs["image_snapshot"]["primary_hex"]) != image[:BLOCK] or \
            bytes.fromhex(obs["image_snapshot"]["mirror_hex"]) != image[-BLOCK:]:
        raise RuntimeError("worker remounted different bytes than the projection")
    return obs


if __name__ == "__main__":
    sys.exit(sd.campaign_main(sys.modules[__name__]))
