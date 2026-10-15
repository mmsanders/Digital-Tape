#!/usr/bin/env python3
"""The shipping `ingest` binary carries no test observation seam (src/observe.rs).

usage: check_seam.py SHIPPING_BIN OBSERVE_BIN
Fails if any seam marker string is in the shipping binary, and -- the negative
control -- if the observation build does NOT contain them (the check could
otherwise pass by looking for strings that never exist).
"""
import sys

MARKERS = [b"INGEST_OBSERVE_DIR", b"INGEST_KILL_AT", b"INGEST_FAULT", b"INGEST_PAUSE_AT",
           b"INGEST_PAUSE_FILE", b"INGEST_HEAP_LIMIT", b"injected test fault", b"events.jsonl"]


def found(path):
    data = open(path, "rb").read()
    return [m.decode() for m in MARKERS if m in data]


def main():
    ship, obs = sys.argv[1], sys.argv[2]
    bad = found(ship)
    control = found(obs)
    print("shipping seam markers:", bad or "none")
    print("observe-build seam markers (control):", control)
    if bad:
        print("FAIL: the shipping binary contains the observation seam")
        return 1
    if set(control) != {m.decode() for m in MARKERS}:
        print("FAIL: negative control -- the observe build lacks seam markers, so this check proves nothing")
        return 1
    print("PASS: shipping binary has no observation seam; control build has all markers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
