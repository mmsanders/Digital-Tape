#!/usr/bin/env python3
"""Partition adapter for Verification's published FW-1 partition test.

Protocol (digital-tape-verification tests/p3_r1_r374/README.md, published by
merge 41995965): one JSON request per process on stdin with `image`,
`sectors`, `reads` and `writes` in view LBAs; JSON on stdout with `accepted`,
`start`, `blocks`, `read_hex`, `write_absolute_lba`, `out_of_range_refused`.

This wrapper parses no MBR and does no I/O itself. Every read and write goes
through `fwhost viewio`, which is the firmware's own fw_part binding (with
host/port/mbr.c's recognition) over engine/port/dev_file, so the test
exercises the binding the Teensy runs.

    python3 wp17.py partition --adapter "python3 partition_adapter.py --fwhost build/fwhost/fwhost" --out DIR
"""

import argparse
import json
import os
import subprocess
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fwhost", required=True)
    a = ap.parse_args()
    req = json.load(sys.stdin)

    size = os.path.getsize(req["image"])
    if size != req["sectors"] * 512:
        # The card is the image; its sector count comes from its size, as the
        # SDIO card's comes from the card. A mismatch is a harness error.
        print(json.dumps({"error": "image size %d != sectors %d * 512" % (size, req["sectors"])}))
        return 2

    ops = ["R %d" % lba for lba in req["reads"]]
    ops += ["W %d %s" % (w["lba"], w["hex"]) for w in req["writes"]]
    p = subprocess.run([a.fwhost, "viewio", req["image"]], input="\n".join(ops) + "\n",
                       capture_output=True, text=True)
    lines = p.stdout.splitlines()
    head = json.loads(lines[0])
    if head.get("part") != "OK":
        print(json.dumps({"accepted": False, "part": head.get("part")}))
        return 0

    answers = lines[1:]
    if len(answers) != len(ops):
        print(json.dumps({"error": "fwhost answered %d of %d operations" % (len(answers), len(ops))}))
        return 2
    read_hex, write_abs, refused = [], [], []
    for op, ans in zip(ops, answers):
        ok = ans.startswith("OK ")
        val = ans[3:] if ok else None
        if op[0] == "R":
            if ok:
                read_hex.append(val)
            else:
                refused.append(op)
        else:
            if ok:
                write_abs.append(int(val))
            else:
                refused.append(op)
    # Out-of-range: every read or write outside [0, blocks) was refused, and
    # every one inside was not.
    blocks = head["blocks"]
    outside = [op for op in ops if not 0 <= int(op.split()[1]) < blocks]
    print(json.dumps({
        "accepted": True,
        "start": head["base"],
        "blocks": blocks,
        "read_hex": read_hex,
        "write_absolute_lba": write_abs,
        "out_of_range_refused": sorted(refused) == sorted(outside),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
