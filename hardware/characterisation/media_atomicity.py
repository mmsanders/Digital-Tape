#!/usr/bin/env python3
"""Media atomicity — is a 512-byte SD block write atomic under power loss?

`spec/acceptance.md` DRAFT-4, via PM Decisions 004 section 1:

    On each candidate card SKU, powered from a switched supply: write a known
    512-byte pattern to a fixed block, cut power at randomised offsets inside the
    write window, then re-read. Across at least 1 000 cuts per SKU, every read
    must return either the previous content or the new content in full -- never
    a mixture.

This is the single load-bearing physical assumption under the whole format.
`tapefs` section 8's commit protocol reduces to it, and so does every crash-safety
guarantee in the project. It is widely believed and not guaranteed by the SD
specification. A single torn block is a BLOCKER and forces a format change, not
a firmware workaround.

WHAT THIS TOOL IS. The rig writes, cuts power, and reads back; this generates the
patterns and classifies what comes back. Keeping the science here rather than in
the rig means the rig stays dumb enough to trust.

PATTERN DESIGN. Iteration N fills all 512 bytes with a 4-byte little-endian
counter N, repeated. So:

    every word == N-1   -> OLD   (write never landed; safe)
    every word == N     -> NEW   (write landed entirely; safe)
    any mixture         -> TORN  (BLOCKER)
    anything else       -> CORRUPT (worse than torn -- neither value)

A repeated counter is deliberate: a tear anywhere in the block is visible no
matter where the boundary falls, which a random payload would not guarantee.

NEIGHBOUR BLOCKS. The criterion asks only about the target block, but an SD card's
FTL can garbage-collect during a power cut and damage blocks nobody wrote. That
would be just as fatal to the format and the same rig catches it for free, so the
tool also verifies that the blocks either side of the target are untouched.

    ./media_atomicity.py plan  --sku "SanDisk ..." --cuts 1000
    ./media_atomicity.py judge --results run.jsonl --json out.json
"""

from __future__ import annotations

import argparse
import json
import random
import struct
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BLOCK = 512
WORDS = BLOCK // 4
REQUIRED_CUTS = 1000
NEIGHBOURS = 2          # blocks either side that must stay untouched


def pattern(n: int) -> bytes:
    """512 bytes of the little-endian counter `n`, repeated."""
    return struct.pack("<I", n & 0xFFFFFFFF) * WORDS


def classify(data: bytes, n: int) -> str:
    """OLD, NEW, TORN or CORRUPT for a readback at iteration `n`."""
    if len(data) != BLOCK:
        return "CORRUPT"
    words = set(struct.unpack("<%dI" % WORDS, data))
    old, new = (n - 1) & 0xFFFFFFFF, n & 0xFFFFFFFF
    if words == {old}:
        return "OLD"
    if words == {new}:
        return "NEW"
    if words <= {old, new}:
        return "TORN"
    return "CORRUPT"


def cmd_plan(a) -> int:
    rng = random.Random(a.seed)
    print(f"# Media atomicity plan — {a.sku or '(unnamed SKU)'}")
    print(f"# {a.cuts} cuts, target block {a.block}, "
          f"neighbours {a.block - NEIGHBOURS}..{a.block + NEIGHBOURS}")
    print(f"#")
    print(f"# Measure the nominal single-block write time t_w FIRST, then cut at a")
    print(f"# uniformly random offset in [0, 1.5*t_w]. Cutting only inside the mean")
    print(f"# write window would miss tears at the very start and the very end,")
    print(f"# which are exactly where a controller is most likely to be mid-commit.")
    print(f"#")
    print(f"# iteration  cut_offset_fraction_of_1.5tw")
    for n in range(1, a.cuts + 1):
        print(f"{n}\t{rng.random() * 1.5:.4f}")
    return 0


def cmd_judge(a) -> int:
    rows = [json.loads(l) for l in Path(a.results).read_text().splitlines() if l.strip()]
    if not rows:
        sys.exit("no results")

    verdicts, tears, corrupt, neigh_bad = Counter(), [], [], []
    for r in rows:
        n = r["iteration"]
        v = classify(bytes.fromhex(r["readback_hex"]), n)
        verdicts[v] += 1
        if v == "TORN":
            tears.append(n)
        elif v == "CORRUPT":
            corrupt.append(n)
        for off, hexd in (r.get("neighbours") or {}).items():
            if bytes.fromhex(hexd) != bytes.fromhex(r["neighbour_baseline_hex"]):
                neigh_bad.append((n, off))

    total = sum(verdicts.values())
    atomic = not tears and not corrupt
    enough = total >= REQUIRED_CUTS
    verdict = "PASS" if (atomic and enough and not neigh_bad) else "FAIL"

    print(f"SKU        {a.sku or rows[0].get('sku', '(unrecorded)')}")
    print(f"revision   {a.revision or rows[0].get('revision', '(unrecorded)')}")
    print(f"cuts       {total}  (criterion needs >= {REQUIRED_CUTS})")
    for k in ("OLD", "NEW", "TORN", "CORRUPT"):
        print(f"  {k:<8} {verdicts[k]:>6}")
    print(f"neighbour blocks damaged: {len(neigh_bad)}")
    print()
    print(f"VERDICT    {verdict}")
    if tears:
        print(f"  *** {len(tears)} TORN blocks: iterations {tears[:10]}"
              f"{' ...' if len(tears) > 10 else ''}")
        print(f"  *** This is a BLOCKER. A torn block forces a format change, not a")
        print(f"  *** firmware workaround -- no commit sequence survives it.")
    if corrupt:
        print(f"  *** {len(corrupt)} CORRUPT blocks (neither old nor new). Worse than torn.")
    if neigh_bad:
        print(f"  *** {len(neigh_bad)} neighbour-block corruptions. The FTL damaged data")
        print(f"  *** nobody wrote. Equally fatal, and outside the stated criterion.")
    if not enough:
        print(f"  Not enough cuts to conclude: {total} < {REQUIRED_CUTS}.")

    if a.json:
        Path(a.json).write_text(json.dumps({
            "sku": a.sku, "revision": a.revision,
            "cuts": total, "verdicts": dict(verdicts),
            "torn_iterations": tears, "corrupt_iterations": corrupt,
            "neighbour_damage": neigh_bad,
            "required_cuts": REQUIRED_CUTS,
            "verdict": verdict,
            "judged_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }, indent=2) + "\n")
        print(f"\nwrote {a.json}")
    return 0 if verdict == "PASS" else 2


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan", help="emit the randomised cut schedule")
    p.add_argument("--sku", default=""); p.add_argument("--revision", default="")
    p.add_argument("--cuts", type=int, default=REQUIRED_CUTS)
    p.add_argument("--block", type=int, default=1_000_000)
    p.add_argument("--seed", type=int, default=20260903)
    p.set_defaults(fn=cmd_plan)

    j = sub.add_parser("judge", help="classify a completed run")
    j.add_argument("--results", required=True, help="JSONL from the rig")
    j.add_argument("--sku", default=""); j.add_argument("--revision", default="")
    j.add_argument("--json", help="write the verdict here")
    j.set_defaults(fn=cmd_judge)

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
