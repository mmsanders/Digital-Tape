#!/usr/bin/env python3
"""Red controls on the Product evidence itself. NOT the canonical run.

The package's selftest.py kills seven controls on its synthetic observations. A
green Product replay also needs to show that the same oracle rejects *this
adapter's* observations once one observed fact is wrong. Each control mutates
one fact in a copy of the Product JSONL and requires the verifier's own
oracle.check (or, for the census, replay.py's census rule) to reject it; the
unmutated evidence must pass. Exits non-zero if any control survives.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "capacity_wp09_r52"))
from oracle import cases, check  # noqa: E402

ROW = 13   # overdub-middle-two-free-seventeen-left: mid-timeline, multi-chunk


def row(records):
    return records[ROW]


def dropped_case(r):                      # C01 census
    del r[-1]


def wrong_accepted(r):                    # C02 positive short accept
    row(r)["calls"]["feed_steps"][-1]["accepted"] -= 1


def feed_io(r):                           # C03 feed reserves without I/O
    row(r)["events"].append({"step": "feed-final", "op": "read", "lba": 0, "count": 1,
                             "ordinal": len(row(r)["events"]) + 1, "rc": 0})


def premature_commit_ok(r):               # C04 owed prefix makes commit BUSY
    row(r)["calls"]["premature_commit"]["result"] = "TAPE_OK"


def illegal_allocation(r):                # C06 allocation floor
    ev = next(e for e in row(r)["events"] if e["step"].startswith("service-") and e["op"] == "write")
    ev["lba"] = 2048 + 1 * 1024


def missing_commit_flush(r):              # C08 durability order
    ev = row(r)["events"]
    last = max(i for i, e in enumerate(ev) if e["step"] == "commit" and e["op"] == "flush")
    del ev[last]
    for i, e in enumerate(ev):
        e["ordinal"] = i + 1


def missing_remount_read(r):              # C09 fresh remount reads both B candidates
    ev = [e for e in row(r)["events"] if not (e["step"] == "remount" and e.get("lba") == 392)]
    for i, e in enumerate(ev):
        e["ordinal"] = i + 1
    row(r)["events"] = ev


def corrupt_pcm(r):                       # C11 exact remounted PCM
    import base64
    import zlib
    render = row(r)["calls"]["render"]
    pcm = bytearray(zlib.decompress(base64.b64decode(render["pcm_zlib_b64"])))
    pcm[4 * 7] ^= 1
    render["pcm_zlib_b64"] = base64.b64encode(zlib.compress(bytes(pcm), 9)).decode()


def stale_free_chunks(r):                 # C12 public/raw cross-check
    row(r)["calls"]["info_after"]["free_chunks"] = 1


def spoofed_label(r):                     # C13 adapter labels carry no authority
    corrupt_pcm(r)
    row(r)["verdict"] = "PASS"


CONTROLS = [dropped_case, wrong_accepted, feed_io, premature_commit_ok, illegal_allocation,
            missing_commit_flush, missing_remount_read, corrupt_pcm, stale_free_chunks, spoofed_label]


def check_all(records) -> None:
    expected = cases()
    if [x.get("case") for x in records] != [c.id for c in expected]:
        raise AssertionError("evidence case census")
    for c, x in zip(expected, records):
        check(c, x)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("observations", type=Path, help="observations.jsonl or .jsonl.gz")
    a = ap.parse_args()
    raw = a.observations.read_bytes()
    if a.observations.suffix == ".gz":
        raw = gzip.decompress(raw)
    records = [json.loads(line) for line in raw.decode().splitlines()]
    check_all(copy.deepcopy(records))
    survived = []
    for control in CONTROLS:
        mutated = copy.deepcopy(records)
        control(mutated)
        try:
            check_all(mutated)
            survived.append(control.__name__)
            print(f"SURVIVED {control.__name__}")
        except (AssertionError, KeyError, TypeError, ValueError, IndexError) as e:
            print(f"killed   {control.__name__}: {e}")
    print(f"{len(CONTROLS) - len(survived)}/{len(CONTROLS)} Product-evidence controls killed")
    return 1 if survived else 0


if __name__ == "__main__":
    raise SystemExit(main())
