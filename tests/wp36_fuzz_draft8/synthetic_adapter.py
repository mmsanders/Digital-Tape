#!/usr/bin/env python3
"""Synthetic streaming adapter used only by verifier harness self-tests."""
from __future__ import annotations

import argparse
import os
import sys

HANDSHAKE = "WP36-FUZZ-ADAPTER-1"
RESULT = "WP36-FUZZ-RESULT-1"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--fixture", required=True)
    p.parse_args()

    mode = os.environ.get("WP36_SYNTH_MODE", "ok")
    binding = "NON_NULL" if mode == "nonnull" else "NULL"
    assertion = "release" if mode == "release" else "debug"

    if mode == "malformed_handshake":
        print("HELLO\tBROKEN", flush=True)
    else:
        print(f"HELLO\t{HANDSHAKE}\tproduct\t{binding}\t{assertion}", flush=True)

    if mode in ("nonnull", "release", "malformed_handshake"):
        for _ in sys.stdin:
            pass
        return 0

    crash_at = int(os.environ.get("WP36_SYNTH_CRASH_AT", "-1"))
    for raw in sys.stdin:
        line = raw.rstrip("\n")
        if line == "DONE":
            return 0
        parts = line.split("\t")
        if len(parts) != 6 or parts[0] != "SEQ":
            return 2
        idx = int(parts[1])
        seed = parts[2]
        nops = int(parts[4])
        if idx == crash_at:
            os.abort()
        print(
            f"RES\t{RESULT}\t{idx}\t{seed}\t{nops}\t1\t0\t0\t"
            f"TAPE_OK\tTAPE_OK\t{nops}\t0,0",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
