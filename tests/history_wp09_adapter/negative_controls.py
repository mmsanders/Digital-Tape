#!/usr/bin/env python3
"""Red controls on the Product evidence itself. NOT the canonical run.

The package's selftest.py kills nine controls on its synthetic history. A green
Product replay also needs to show that the same oracle rejects *this adapter's*
history once one observed fact is wrong. Each control mutates one record in a
copy of the Product JSONL and requires the verifier's own oracle.check to reject
the whole history; the unmutated history must pass. Exits non-zero if any
control survives.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "history_wp09_r44"))
from oracle import check  # noqa: E402


def at(records, i):
    return records[i - 1]


def checkpoint_pcm(r):
    cp = at(r, 4000)["checkpoint"]
    h = cp["render_pcm"]
    cp["render_pcm"] = ("0" if h[0] != "0" else "1") + h[1:]


def dropped_suffix(r):
    del r[-1]


def short_accept(r):
    at(r, 1234)["accepted"] -= 1


def restart(r):
    at(r, 5001)["id"] = 1


def missing_final_flush(r):
    ev = at(r, 777)["events"]
    last = max(i for i, e in enumerate(ev) if e["step"] == "commit" and e["op"] == "flush")
    del ev[last]


def stale_free_chunks(r):
    at(r, 1600)["checkpoint"]["public_info"]["free_chunks"] += 1


def missing_slot_read(r):
    cp = at(r, 2400)["checkpoint"]
    cp["mount_events"] = [e for e in cp["mount_events"] if not (e["op"] == "read" and e.get("lba") == 392)]


def render_io(r):
    at(r, 400)["checkpoint"]["render_block_events"] = [{"step": "render", "op": "read", "lba": 3072}]


CONTROLS = [checkpoint_pcm, dropped_suffix, short_accept, restart, missing_final_flush,
            stale_free_chunks, missing_slot_read, render_io]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("observations", type=Path, help="observations.jsonl or .jsonl.gz")
    a = ap.parse_args()
    raw = a.observations.read_bytes()
    if a.observations.suffix == ".gz":
        raw = gzip.decompress(raw)
    records = [json.loads(line) for line in raw.decode().splitlines()]
    check(iter(copy.deepcopy(records)))
    survived = []
    for control in CONTROLS:
        mutated = copy.deepcopy(records)
        control(mutated)
        try:
            check(iter(mutated))
            survived.append(control.__name__)
            print(f"SURVIVED {control.__name__}")
        except (AssertionError, KeyError, TypeError, ValueError, IndexError) as e:
            print(f"killed   {control.__name__}: {e}")
    print(f"{len(CONTROLS) - len(survived)}/{len(CONTROLS)} Product-evidence controls killed")
    return 1 if survived else 0


if __name__ == "__main__":
    raise SystemExit(main())
