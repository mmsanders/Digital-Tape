"""Transport between a WP-10 worker's S/R commands and Verification's any-subset model.

Product #440 (tests/wp10_subset_r1/ADAPTER.md). Software transports actual callbacks and
raw observations only:

  * a worker S run returns the actual event history: every 512-byte write unit (absolute
    ID, call ID, LBA, bytes, acknowledgement) and every barrier result, from the initial
    durable image on, ending at a cut coordinate or at the operation's own end;
  * that history is replayed, call by call, into tests/wp10_subset_r1/model.py's Device,
    imported unchanged; the model's own exhaustive/sampled planners choose the masks and
    landing orders, and Device.crash_image materializes each durable projection;
  * each distinct projection is remounted by a worker R command from those bytes only
    (fresh engine instance and rings, no volatile state), and its raw output is kept.

Nothing here classifies an outcome. Verification compares the projections with model.py
and judges each operation with its own permitted crash-state predicates.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "tests" / "wp10_subset_r1" / "model.py"
BLOCK = 512
SEEDS = (1, 183, 3647685189)       # the package's recorded seeds (README: 67 records/seed)


def load_model():
    spec = importlib.util.spec_from_file_location("wp10_subset_model", MODEL_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MODEL = load_model()


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_file(p: Path) -> str:
    return sha(Path(p).read_bytes())


class Worker:
    """One persistent worker process speaking the tab-delimited protocol."""

    def __init__(self, argv: list[str]):
        self.proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)

    def ask(self, *fields: str) -> dict:
        self.proc.stdin.write("\t".join(fields) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError(f"worker ended on {fields[0]} (exit {self.proc.poll()})")
        return json.loads(line)

    def close(self) -> int:
        try:
            self.proc.stdin.write("D\n")
            self.proc.stdin.flush()
        except BrokenPipeError:
            pass
        return self.proc.wait()


def read_trace(path: Path) -> list[dict]:
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def image_blocks(image: bytes) -> dict:
    return {i: image[i * BLOCK:(i + 1) * BLOCK] for i in range(len(image) // BLOCK)}


def replay(initial: bytes, trace: list[dict]):
    """Feed the actual history into the model, one actual call at a time. A failed or cut
    call is attempted (every logged unit eligible to persist) and visible nowhere, which
    is what the worker's working image did."""
    dev = MODEL.Device(image_blocks(initial))
    i = 0
    while i < len(trace):
        r = trace[i]
        if r["t"] == "W":
            call = [r]
            while i + 1 < len(trace) and trace[i + 1]["t"] == "W" and trace[i + 1]["call"] == r["call"]:
                i += 1
                call.append(trace[i])
            lbas = [u["lba"] for u in call]
            if lbas != list(range(lbas[0], lbas[0] + len(lbas))) or len({u["ack"] for u in call}) != 1:
                raise ValueError(f"call {r['call']}: units are not one contiguous, uniformly acknowledged call")
            ids = [u["id"] for u in call]
            if ids[0] != dev.next_id or ids != list(range(ids[0], ids[0] + len(ids))):
                raise ValueError(f"call {r['call']}: event IDs {ids} do not continue the model's {dev.next_id}")
            data = b"".join(bytes.fromhex(u["hex"]) for u in call)
            if call[0]["ack"]:
                dev.write(lbas[0], data, acknowledged=True)
            else:
                dev.write(lbas[0], data, acknowledged=False, visible=[])
        elif r["t"] == "F":
            dev.flush(successful=r["ok"])
        i += 1
    return dev


def plans(events: list) -> tuple[str, list[dict]]:
    if len(events) <= MODEL.EXHAUSTIVE_LIMIT:
        return "exhaustive", list(MODEL.exhaustive(events))
    out = []
    for s in SEEDS:
        out.extend(MODEL.sampled(events, s))
    return "sampled", out


def materialize(dev, order: list[int], nblocks: int) -> bytes:
    img = dev.crash_image(order)
    return b"".join(img.get(i, bytes(BLOCK)) for i in range(nblocks))
