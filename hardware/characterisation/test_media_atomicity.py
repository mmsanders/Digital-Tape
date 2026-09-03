#!/usr/bin/env python3
"""Tests for the media-atomicity judge — IR-018-05.

This tool decides whether the format's central physical assumption holds, so a
regression in it fails open: a PASS nobody earned. `CLAUDE.md` section 1 requires
every gate to be proven able to go red, and the first version of this tool was
committed without a test — the same omission that let a malformed 3MF through a
reproducibility gate.

`--mutate` is the red case: it patches `classify` to always return NEW, the most
plausible way this tool could silently fail open, and asserts the suite catches it.

    ./test_media_atomicity.py            run the suite
    ./test_media_atomicity.py --mutate   prove the suite goes red
"""

from __future__ import annotations

import argparse
import struct
import sys

import media_atomicity as M

OK, FAIL = [], []


def check(name, cond, detail=""):
    (OK if cond else FAIL).append(name)
    print(f"  {'ok  ' if cond else 'FAIL'} {name}{'' if cond else '  <- ' + detail}")


def plan(n=3, sku="TEST", run="run-1"):
    return {"run_id": run, "sku": sku, "revision": "r1", "block": 1000,
            "neighbour_offsets": list(M.NEIGHBOUR_OFFSETS),
            "required_qualifying": n,
            "trials": [{"iteration": i, "cut_offset_fraction": 0.5}
                       for i in range(1, n + 1)]}


NB_BASE = {off: (bytes([i + 1]) * M.BLOCK).hex()
           for i, off in enumerate(M.NEIGHBOUR_OFFSETS)}


def trial(n, *, data=None, run="run-1", sku="TEST", busy=True, pre_ok=True,
          pre=None, neighbours=None, baseline=None, write_start=100, cut=150):
    return {"run_id": run, "sku": sku, "iteration": n,
            "precondition_ok": pre_ok,
            "precondition_readback_hex": (pre if pre is not None
                                          else M.pattern(n - 1)).hex()
            if isinstance(pre, (bytes, type(None))) else pre,
            "busy_at_cut": busy, "write_start_us": write_start, "cut_us": cut,
            "readback_hex": (data if data is not None else M.pattern(n)).hex(),
            "neighbours": dict(NB_BASE) if neighbours is None else neighbours,
            "neighbour_baseline": dict(NB_BASE) if baseline is None else baseline}


def run(rows, p=None):
    return M.judge(p or plan(), rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mutate", action="store_true")
    a = ap.parse_args()

    if a.mutate:
        M.classify = lambda data, n: "NEW"          # the plausible fail-open
        print("MUTATION ACTIVE: classify() always returns NEW\n")

    print("classification")
    check("NEW recognised", M.classify(M.pattern(7), 7) == "NEW")
    check("OLD recognised", M.classify(M.pattern(6), 7) == "OLD")
    torn = M.pattern(7)[:200] + M.pattern(6)[200:]
    check("TORN at a byte offset", M.classify(torn, 7) == "TORN",
          M.classify(torn, 7))
    torn_word = M.pattern(7)[:4] + M.pattern(6)[4:]
    check("TORN at a word boundary", M.classify(torn_word, 7) == "TORN",
          M.classify(torn_word, 7))
    check("CORRUPT on a foreign value",
          M.classify(struct.pack("<I", 99) * M.WORDS, 7) == "CORRUPT")
    check("CORRUPT on a short read", M.classify(b"\x00" * 8, 7) == "CORRUPT")

    print("\nhappy path")
    r = run([trial(1), trial(2, data=M.pattern(1)), trial(3)])
    check("clean run passes", r["verdict"] == "PASS", str(r["problems"])[:120])
    check("counts 3 qualifying", r["qualifying"] == 3)

    print("\nIR-018-01  a cut must be proven inside the write")
    r = run([trial(n, busy=False) for n in (1, 2, 3)])
    check("cuts outside the write do not count", r["qualifying"] == 0)
    check("and the run fails rather than passing", r["verdict"] == "FAIL")
    r = run([trial(1), trial(2), trial(3, cut=50, write_start=100)])
    check("a cut before the write starts does not count", r["qualifying"] == 2)

    print("\nIR-018-02  plan membership and uniqueness")
    r = run([trial(1)] * 3)
    check("duplicates are rejected", r["verdict"] == "FAIL")
    check("duplicates named in problems",
          any("duplicate" in p for p in r["problems"]))
    r = run([trial(1), trial(2)])
    check("a missing trial fails", any("missing" in p for p in r["problems"]))
    r = run([trial(1), trial(2), trial(3), trial(9)])
    check("a trial outside the plan fails",
          any("not in the plan" in p for p in r["problems"]))
    r = run([trial(1, run="other"), trial(2), trial(3)])
    check("run_id mismatch fails", any("run_id" in p for p in r["problems"]))
    r = run([trial(1, sku="OTHER"), trial(2), trial(3)])
    check("SKU mismatch fails", any("SKU" in p for p in r["problems"]))

    print("\nIR-018-03  neighbours are mandatory and per-offset")
    r = run([trial(n, neighbours={}, baseline={}) for n in (1, 2, 3)])
    check("omitted neighbours invalidate rather than pass",
          r["verdict"] == "FAIL" and r["qualifying"] == 0)
    partial = {"-1": NB_BASE["-1"], "+1": NB_BASE["+1"]}
    r = run([trial(n, neighbours=partial, baseline=partial) for n in (1, 2, 3)])
    check("a partial offset set is rejected",
          any("offsets must be exactly" in p for p in r["problems"]))
    damaged = dict(NB_BASE); damaged["+2"] = (b"\xFF" * M.BLOCK).hex()
    r = run([trial(1, neighbours=damaged), trial(2), trial(3)])
    check("neighbour damage is caught", len(r["neighbour_damage"]) == 1)
    check("and fails the run", r["verdict"] == "FAIL")
    distinct = {off: (bytes([9 - i]) * M.BLOCK).hex()
                for i, off in enumerate(M.NEIGHBOUR_OFFSETS)}
    r = run([trial(n, neighbours=distinct, baseline=distinct) for n in (1, 2, 3)])
    check("distinct-but-unchanged neighbours are not false damage",
          r["neighbour_damage"] == [] and r["verdict"] == "PASS")

    print("\nIR-018-04  the old image is established, not inferred")
    r = run([trial(1, pre_ok=False), trial(2), trial(3)])
    check("a failed precondition invalidates the trial",
          any("precondition_ok" in p for p in r["problems"]))
    r = run([trial(1, pre=M.pattern(5)), trial(2), trial(3)])
    check("a precondition readback that is not N-1 is rejected",
          any("pattern N-1" in p for p in r["problems"]))

    print("\ndetection of the thing this tool exists to detect")
    r = run([trial(1), trial(2, data=M.pattern(2)[:200] + M.pattern(1)[200:]),
             trial(3)])
    check("one torn block fails the whole run", r["verdict"] == "FAIL",
          r["verdict"])
    check("and is reported by iteration", r["torn_iterations"] == [2])

    print("\ninsufficient qualifying count")
    p10 = plan(3); p10["required_qualifying"] = 10
    r = run([trial(1), trial(2), trial(3)], p10)
    check("too few qualifying cuts cannot pass", r["verdict"] == "FAIL")

    print(f"\n{len(OK)} passed, {len(FAIL)} failed")
    if a.mutate:
        if FAIL:
            print("RED CASE OK: the suite catches a classify() that always says NEW.")
            return 0
        print("RED CASE BROKEN: the mutation was not caught. The gate is useless.")
        return 1
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
    raise SystemExit(main())
