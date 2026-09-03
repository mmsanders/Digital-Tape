#!/usr/bin/env python3
"""Media atomicity — is a 512-byte SD block write atomic under power loss?

`spec/acceptance.md` DRAFT-4, via PM Decisions 004 section 1:

    On each candidate card SKU, powered from a switched supply: write a known
    512-byte pattern to a fixed block, cut power at randomised offsets inside the
    write window, then re-read. Across at least 1 000 cuts per SKU, every read
    must return either the previous content or the new content in full -- never
    a mixture.

This is the single load-bearing physical assumption under the whole format.
`tapefs` section 8's commit protocol reduces to it. A single torn block is a
BLOCKER and forces a format change, not a firmware workaround.

REVISION 2, after independent review IR-018. The first version could return PASS
having never cut a card mid-write, which is the same class of failure as a gate
that measures the wrong quantity. Five things changed:

  IR-018-01  A trial only counts if the rig PROVES the cut landed inside the
             write. The card's own busy signal (DAT0 held low) is the oracle:
             sampled at the instant of the cut, it is the card saying "I am
             mid-write". Attempted and qualifying cuts are reported separately
             and the 1 000 threshold applies to QUALIFYING cuts only.
  IR-018-02  Trials are matched against a committed plan by run id. Duplicates,
             missing trials, extras, out-of-range iterations and SKU mismatches
             invalidate the run rather than being counted.
  IR-018-03  All four neighbour offsets are mandatory, each with its OWN
             baseline. Missing or malformed neighbour evidence makes a run
             INVALID -- it can no longer fail open by omission.
  IR-018-04  Every trial is preconditioned: pattern N-1 is written WITHOUT a cut
             and read back for exact equality before the cut write of N is
             attempted. Power-cut testing cannot assume the previous iteration
             completed, so the old-image oracle has to be established, not
             inferred.
  IR-018-05  See test_media_atomicity.py, which is run by CI and includes a
             deliberate red case.

    ./media_atomicity.py plan  --sku "..." --cuts 1000 --out plan.json
    ./media_atomicity.py judge --plan plan.json --results run.jsonl --json v.json
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
REQUIRED_QUALIFYING = 1000
NEIGHBOUR_OFFSETS = ("-2", "-1", "+1", "+2")


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


# --------------------------------------------------------------------------
# plan
# --------------------------------------------------------------------------

def cmd_plan(a) -> int:
    rng = random.Random(a.seed)
    plan = {
        "run_id": a.run_id or f"{a.sku or 'sku'}-{a.seed}",
        "sku": a.sku, "revision": a.revision,
        "block": a.block,
        "neighbour_offsets": list(NEIGHBOUR_OFFSETS),
        "required_qualifying": a.cuts,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "trials": [{"iteration": n, "cut_offset_fraction": round(rng.random() * 1.5, 4)}
                   for n in range(1, a.cuts + 1)],
    }
    out = json.dumps(plan, indent=2) + "\n"
    if a.out:
        Path(a.out).write_text(out)
        print(f"wrote {a.out}: {a.cuts} trials, run_id {plan['run_id']}")
    else:
        print(out)
    return 0


# --------------------------------------------------------------------------
# judge
# --------------------------------------------------------------------------

def _hex(v):
    try:
        b = bytes.fromhex(v)
    except (ValueError, TypeError):
        return None
    return b


def validate_trial(r: dict, n_expected: int) -> tuple[bool, str]:
    """Structural validity of one trial. Invalid trials invalidate the RUN."""
    if r.get("iteration") != n_expected:
        return False, f"iteration mismatch: {r.get('iteration')} != {n_expected}"

    # IR-018-04: the old image must be established, never inferred.
    if r.get("precondition_ok") is not True:
        return False, "precondition_ok is not true"
    pre = _hex(r.get("precondition_readback_hex", ""))
    if pre is None or pre != pattern(n_expected - 1):
        return False, "precondition readback is not exactly pattern N-1"

    rb = _hex(r.get("readback_hex", ""))
    if rb is None or len(rb) != BLOCK:
        return False, "readback missing or not 512 bytes"

    # IR-018-03: all four offsets, each with its own baseline. No fail-open.
    nb, base = r.get("neighbours"), r.get("neighbour_baseline")
    if not isinstance(nb, dict) or not isinstance(base, dict):
        return False, "neighbours/neighbour_baseline missing"
    if set(nb) != set(NEIGHBOUR_OFFSETS) or set(base) != set(NEIGHBOUR_OFFSETS):
        return False, f"neighbour offsets must be exactly {list(NEIGHBOUR_OFFSETS)}"
    for off in NEIGHBOUR_OFFSETS:
        a_, b_ = _hex(nb[off]), _hex(base[off])
        if a_ is None or b_ is None or len(a_) != BLOCK or len(b_) != BLOCK:
            return False, f"neighbour {off} missing or not 512 bytes"
    return True, ""


def qualifies(r: dict) -> tuple[bool, str]:
    """IR-018-01: did this cut provably land inside the write?

    The card's busy signal is the oracle. Timestamps alone cannot settle it,
    because a cut write never reports completion -- there is no 'end' to compare
    against. DAT0 held low at the instant power was removed is the card's own
    statement that it was mid-write.
    """
    if r.get("busy_at_cut") is not True:
        return False, "card was not busy at the cut"
    ws, cut = r.get("write_start_us"), r.get("cut_us")
    if not isinstance(ws, (int, float)) or not isinstance(cut, (int, float)):
        return False, "missing write_start_us / cut_us"
    if cut < ws:
        return False, "cut preceded the write"
    return True, ""


def judge(plan: dict, rows: list[dict]) -> dict:
    problems: list[str] = []
    expected = {t["iteration"] for t in plan["trials"]}
    required = plan.get("required_qualifying", REQUIRED_QUALIFYING)

    # IR-018-02: plan membership and uniqueness, before anything is counted.
    seen: dict[int, dict] = {}
    for r in rows:
        if r.get("run_id") != plan["run_id"]:
            problems.append(f"trial {r.get('iteration')}: run_id mismatch")
            continue
        if plan.get("sku") and r.get("sku") not in (None, plan["sku"]):
            problems.append(f"trial {r.get('iteration')}: SKU mismatch")
            continue
        n = r.get("iteration")
        if n not in expected:
            problems.append(f"trial {n}: not in the plan")
            continue
        if n in seen:
            problems.append(f"trial {n}: duplicate result")
            continue
        seen[n] = r
    for n in sorted(expected - set(seen)):
        problems.append(f"trial {n}: missing")

    verdicts, tears, corrupt, neigh_bad = Counter(), [], [], []
    qualifying, non_qualifying = 0, Counter()

    for n in sorted(seen):
        r = seen[n]
        ok, why = validate_trial(r, n)
        if not ok:
            problems.append(f"trial {n}: {why}")
            continue
        q, why = qualifies(r)
        if not q:
            non_qualifying[why] += 1
            continue
        qualifying += 1

        v = classify(bytes.fromhex(r["readback_hex"]), n)
        verdicts[v] += 1
        if v == "TORN":
            tears.append(n)
        elif v == "CORRUPT":
            corrupt.append(n)
        for off in NEIGHBOUR_OFFSETS:
            if bytes.fromhex(r["neighbours"][off]) != bytes.fromhex(r["neighbour_baseline"][off]):
                neigh_bad.append([n, off])

    ok = (not problems and not tears and not corrupt and not neigh_bad
          and qualifying >= required)
    return {
        "run_id": plan["run_id"], "sku": plan.get("sku"),
        "revision": plan.get("revision"),
        "attempted": len(rows), "matched": len(seen),
        "qualifying": qualifying, "required_qualifying": required,
        "non_qualifying": dict(non_qualifying),
        "verdicts": dict(verdicts),
        "torn_iterations": tears, "corrupt_iterations": corrupt,
        "neighbour_damage": neigh_bad,
        "problems": problems,
        "verdict": "PASS" if ok else "FAIL",
        "judged_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def cmd_judge(a) -> int:
    plan = json.loads(Path(a.plan).read_text())
    rows = [json.loads(l) for l in Path(a.results).read_text().splitlines() if l.strip()]
    res = judge(plan, rows)

    print(f"run        {res['run_id']}")
    print(f"SKU        {res['sku']}  rev {res['revision']}")
    print(f"attempted  {res['attempted']}   matched to plan {res['matched']}")
    print(f"QUALIFYING {res['qualifying']}   (criterion needs >= {res['required_qualifying']})")
    for why, k in sorted(res["non_qualifying"].items()):
        print(f"  not counted: {k:>6}  {why}")
    for k in ("OLD", "NEW", "TORN", "CORRUPT"):
        print(f"  {k:<8} {res['verdicts'].get(k, 0):>6}")
    print(f"neighbour damage: {len(res['neighbour_damage'])}")
    if res["problems"]:
        print(f"run integrity problems: {len(res['problems'])}")
        for p in res["problems"][:8]:
            print(f"  - {p}")
        if len(res["problems"]) > 8:
            print(f"  ... and {len(res['problems']) - 8} more")
    print()
    print(f"VERDICT    {res['verdict']}")
    if res["torn_iterations"]:
        print("  *** TORN blocks. This is a BLOCKER: a torn block forces a format")
        print("  *** change, not a firmware workaround.")
    if res["neighbour_damage"]:
        print("  *** Neighbour-block corruption: the FTL damaged data nobody wrote.")
    if res["qualifying"] < res["required_qualifying"]:
        print(f"  Not enough PROVEN in-write cuts to conclude anything. A run whose")
        print(f"  cuts all landed outside the write window tests nothing.")

    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(res, indent=2) + "\n")
        print(f"\nwrote {a.json}")
    return 0 if res["verdict"] == "PASS" else 2


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan", help="emit the committed cut schedule")
    p.add_argument("--sku", default=""); p.add_argument("--revision", default="")
    p.add_argument("--run-id", default="")
    p.add_argument("--cuts", type=int, default=REQUIRED_QUALIFYING)
    p.add_argument("--block", type=int, default=1_000_000)
    p.add_argument("--seed", type=int, default=20260903)
    p.add_argument("--out")
    p.set_defaults(fn=cmd_plan)

    j = sub.add_parser("judge", help="classify a completed run against its plan")
    j.add_argument("--plan", required=True)
    j.add_argument("--results", required=True, help="JSONL from the rig")
    j.add_argument("--json", help="write the verdict here")
    j.set_defaults(fn=cmd_judge)

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
