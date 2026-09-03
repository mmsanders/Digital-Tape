#!/usr/bin/env python3
"""Media atomicity — is a 512-byte SD block write atomic under power loss?

`spec/acceptance.md` DRAFT-4, via PM Decisions 004 section 1: across at least
1 000 cuts per SKU, every read must return either the previous content or the new
content in full, never a mixture. This is the single load-bearing physical
assumption under the format; `tapefs` section 8's commit protocol reduces to it.
A torn block is a BLOCKER and forces a format change, not a firmware workaround.

REVISION 3, after independent reviews IR-018 (rounds 1 and 2). Both rounds found
ways this tool could say PASS without the evidence to justify it. What changed:

  IR-018-06  The 1 000 minimum is now UNCONDITIONAL and lives in code, not in the
             plan file. `--cuts 0` used to produce a plan with zero trials and a
             threshold of zero, and an empty result set passed. Thresholds are no
             longer readable from operator-supplied input at all; tests inject a
             Policy object instead of going through the production file format.

  IR-018-07  A single DAT0-low sample is NOT proof of the programming phase. In
             native 4-bit mode DAT0 is a data line during the payload -- it can be
             low simply because the current bit is zero -- and the protocol's busy
             indication is a distinct phase AFTER the data-response token. In SPI
             mode busy is on MISO, not DAT0, and the bus mode was never stated.
             Qualification is now from protocol state: complete single-block
             payload, accepted data-response token, observed entry into the busy
             phase, and the busy indication still asserted when the rail opened.

  IR-018-08  Results are bound to card identity. SKU, revision and CID are
             required on every row and must match the plan exactly; `None` is no
             longer accepted. Rows are bound to a digest of the committed plan,
             and run ids are collision-resistant. The verdict reports identity
             only from cross-checked evidence, never by copying the plan.

  IR-018-09  Planned attempts and required qualifying cuts are separate numbers.
             Previously `--cuts N` set both, so a single correctly-identified
             non-qualifying attempt made PASS unreachable -- and since cut offsets
             deliberately span 0-1.5, misses are expected. A campaign now plans a
             surplus, and `plan --extend` issues an auditable continuation under
             the same run id when misses outrun it.

Every planned attempt must still be reported exactly once. Non-qualifying is a
result; missing is a broken run.

    ./media_atomicity.py plan --sku S --revision R --cid C --attempts 1500 --out plan.json
    ./media_atomicity.py judge --plan plan.json [--plan ext.json] --results run.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import secrets
import struct
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

BLOCK = 512
WORDS = BLOCK // 4
REQUIRED_QUALIFYING = 1000          # normative, from acceptance.md. Not negotiable.
DEFAULT_SURPLUS = 1.5               # plan this many attempts per required cut
NEIGHBOUR_OFFSETS = ("-2", "-1", "+1", "+2")
BUS_MODES = {"sd4": "DAT0", "spi": "MISO"}


@dataclass(frozen=True)
class Policy:
    """Acceptance thresholds. Injected, never read from operator input.

    IR-018-06: the production minimum is a property of the criterion, not of a
    file the operator writes. Tests construct their own Policy; the CLI cannot.
    """
    min_qualifying: int = REQUIRED_QUALIFYING


PRODUCTION = Policy()


def pattern(n: int) -> bytes:
    return struct.pack("<I", n & 0xFFFFFFFF) * WORDS


def classify(data: bytes, n: int) -> str:
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


def plan_digest(plan: dict) -> str:
    """Digest over identity and schedule, so results cannot be re-pointed."""
    core = {k: plan[k] for k in ("run_id", "sku", "revision", "card_cid", "block",
                                 "neighbour_offsets") if k in plan}
    core["trials"] = [[t["iteration"], t["cut_offset_fraction"]] for t in plan["trials"]]
    return hashlib.sha256(
        json.dumps(core, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


# --------------------------------------------------------------------------
# plan
# --------------------------------------------------------------------------

def cmd_plan(a) -> int:
    prior = json.loads(Path(a.extend).read_text()) if a.extend else None
    if prior:
        run_id, sku, rev, cid = (prior["run_id"], prior["sku"],
                                 prior["revision"], prior["card_cid"])
        start = max(t["iteration"] for t in prior["trials"]) + 1
        block = prior["block"]
    else:
        if not (a.sku and a.revision and a.cid):
            sys.exit("plan: --sku, --revision and --cid are all required "
                     "(IR-018-08: results are bound to card identity)")
        run_id = f"{a.sku.replace(' ', '-')}-{a.revision}-{secrets.token_hex(8)}"
        sku, rev, cid = a.sku, a.revision, a.cid
        start, block = 1, a.block

    # `a.attempts or default` would silently turn an explicit 0 into the default.
    # An out-of-range request must be refused, not quietly corrected.
    attempts = (int(REQUIRED_QUALIFYING * DEFAULT_SURPLUS)
                if a.attempts is None else a.attempts)
    if not prior and attempts < REQUIRED_QUALIFYING:
        sys.exit(f"plan: --attempts must be at least {REQUIRED_QUALIFYING}; "
                 f"the criterion needs that many QUALIFYING cuts and misses are "
                 f"expected, so plan a surplus (default "
                 f"{int(REQUIRED_QUALIFYING * DEFAULT_SURPLUS)})")

    rng = random.Random(a.seed)
    plan = {
        "plan_version": 3,
        "run_id": run_id, "sku": sku, "revision": rev, "card_cid": cid,
        "block": block,
        "neighbour_offsets": list(NEIGHBOUR_OFFSETS),
        "planned_attempts": attempts,
        "required_qualifying": REQUIRED_QUALIFYING,
        "note": ("required_qualifying is informational. The judge enforces its own "
                 "minimum and ignores this field (IR-018-06)."),
        "extends": prior["run_id"] if prior else None,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "trials": [{"iteration": n, "cut_offset_fraction": round(rng.random() * 1.5, 4)}
                   for n in range(start, start + attempts)],
    }
    plan["plan_digest"] = plan_digest(plan)
    out = json.dumps(plan, indent=2) + "\n"
    if a.out:
        Path(a.out).write_text(out)
        print(f"wrote {a.out}")
        print(f"  run_id  {run_id}")
        print(f"  trials  {attempts} attempts, iterations "
              f"{start}..{start + attempts - 1}")
        print(f"  judge requires {REQUIRED_QUALIFYING} QUALIFYING cuts; the surplus "
              f"absorbs expected misses")
    else:
        print(out)
    return 0


# --------------------------------------------------------------------------
# judge
# --------------------------------------------------------------------------

def _hex(v, n=BLOCK):
    if not isinstance(v, str):
        return None
    try:
        b = bytes.fromhex(v)
    except ValueError:
        return None
    return b if len(b) == n else None


def validate_trial(r: dict, n: int, plan: dict) -> tuple[bool, str]:
    if r.get("iteration") != n:
        return False, f"iteration mismatch: {r.get('iteration')} != {n}"

    # IR-018-08: identity on every row, exact, no None.
    for field in ("sku", "revision", "card_cid"):
        if not r.get(field):
            return False, f"{field} missing"
        if r[field] != plan[field]:
            return False, f"{field} does not match the plan"
    if r.get("plan_digest") != plan["plan_digest"]:
        return False, "plan_digest does not match the committed plan"

    # IR-018-04: the old image is established, not inferred.
    if r.get("precondition_ok") is not True:
        return False, "precondition_ok is not true"
    if _hex(r.get("precondition_readback_hex")) != pattern(n - 1):
        return False, "precondition readback is not exactly pattern N-1"

    if _hex(r.get("readback_hex")) is None:
        return False, "readback missing or not 512 bytes"

    # IR-018-03: all four offsets, each with its own baseline.
    nb, base = r.get("neighbours"), r.get("neighbour_baseline")
    if not isinstance(nb, dict) or not isinstance(base, dict):
        return False, "neighbours/neighbour_baseline missing"
    if set(nb) != set(NEIGHBOUR_OFFSETS) or set(base) != set(NEIGHBOUR_OFFSETS):
        return False, f"neighbour offsets must be exactly {list(NEIGHBOUR_OFFSETS)}"
    for off in NEIGHBOUR_OFFSETS:
        if _hex(nb[off]) is None or _hex(base[off]) is None:
            return False, f"neighbour {off} missing or not 512 bytes"
    return True, ""


def qualifies(r: dict) -> tuple[bool, str]:
    """IR-018-07: qualify from protocol state, not from a pin level.

    A DAT0-low sample proves nothing on its own. In 4-bit mode DAT0 carries data
    during the payload and is low whenever the current bit is zero; the busy
    indication is a distinct phase entered only after the data-response token is
    accepted. In SPI mode the indication is on MISO instead. So a trial qualifies
    only if the rig can show the whole sequence: payload transferred, response
    token accepted, busy phase entered, and busy still asserted when the rail
    opened.
    """
    bus = r.get("bus_mode")
    if bus not in BUS_MODES:
        return False, f"bus_mode must be one of {sorted(BUS_MODES)}"
    if r.get("busy_line") != BUS_MODES[bus]:
        return False, f"busy_line for {bus} must be {BUS_MODES[bus]}"
    if r.get("payload_complete") is not True:
        return False, "single-block payload not proven complete"
    if r.get("data_response_accepted") is not True:
        return False, "data-response token not accepted"

    be, bs, cut = (r.get("busy_entry_us"), r.get("busy_sampled_us"), r.get("cut_us"))
    if not all(isinstance(v, (int, float)) for v in (be, bs, cut)):
        return False, "busy_entry_us / busy_sampled_us / cut_us missing"
    if not (be <= bs <= cut):
        return False, "busy was not observed asserted before the rail opened"
    de = r.get("busy_deassert_us")
    if isinstance(de, (int, float)) and de <= cut:
        return False, "busy ended before the cut -- the write had completed"
    return True, ""


def judge(plans: list[dict], rows: list[dict], policy: Policy = PRODUCTION) -> dict:
    problems: list[str] = []

    head = plans[0]
    for p in plans[1:]:
        if p["run_id"] != head["run_id"] and p.get("extends") != head["run_id"]:
            problems.append(f"plan {p['run_id']} is not a continuation of {head['run_id']}")
    for p in plans:
        if plan_digest(p) != p.get("plan_digest"):
            problems.append(f"plan {p.get('run_id')}: digest does not match its contents")

    trials: dict[int, dict] = {}
    for p in plans:
        for t in p["trials"]:
            trials[t["iteration"]] = p
    expected = set(trials)
    planned_attempts = len(expected)

    # IR-018-02 / IR-018-08
    seen: dict[int, dict] = {}
    for r in rows:
        n = r.get("iteration")
        p = trials.get(n)
        if p is None:
            problems.append(f"trial {n}: not in any committed plan")
            continue
        if r.get("run_id") != p["run_id"]:
            problems.append(f"trial {n}: run_id mismatch")
            continue
        if n in seen:
            problems.append(f"trial {n}: duplicate result")
            continue
        seen[n] = r
    for n in sorted(expected - set(seen)):
        problems.append(f"trial {n}: planned but not reported")

    verdicts, tears, corrupt, neigh_bad = Counter(), [], [], []
    qualifying = 0
    non_qualifying: Counter = Counter()
    identity: set[tuple] = set()

    for n in sorted(seen):
        r, p = seen[n], trials[n]
        ok, why = validate_trial(r, n, p)
        if not ok:
            problems.append(f"trial {n}: {why}")
            continue
        identity.add((r["sku"], r["revision"], r["card_cid"]))
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

    if len(identity) > 1:
        problems.append(f"results span {len(identity)} distinct cards; expected one")

    ok = (not problems and not tears and not corrupt and not neigh_bad
          and qualifying >= policy.min_qualifying and len(identity) == 1)

    # IR-018-08: identity from evidence, never copied from the plan.
    sku, revision, cid = (sorted(identity)[0] if len(identity) == 1
                          else (None, None, None))
    return {
        "run_id": head["run_id"],
        "sku": sku, "revision": revision, "card_cid": cid,
        "planned_attempts": planned_attempts, "reported": len(seen),
        "qualifying": qualifying, "required_qualifying": policy.min_qualifying,
        "non_qualifying": dict(non_qualifying),
        "verdicts": dict(verdicts),
        "torn_iterations": tears, "corrupt_iterations": corrupt,
        "neighbour_damage": neigh_bad,
        "problems": problems,
        "verdict": "PASS" if ok else "FAIL",
        "judged_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def cmd_judge(a) -> int:
    plans = [json.loads(Path(p).read_text()) for p in a.plan]
    rows = [json.loads(l) for l in Path(a.results).read_text().splitlines() if l.strip()]
    res = judge(plans, rows)                      # production policy, always

    print(f"run        {res['run_id']}")
    print(f"card       {res['sku']}  rev {res['revision']}  CID {res['card_cid']}")
    print(f"attempts   {res['planned_attempts']} planned, {res['reported']} reported")
    print(f"QUALIFYING {res['qualifying']}   (criterion needs >= {res['required_qualifying']})")
    for why, k in sorted(res["non_qualifying"].items(), key=lambda kv: -kv[1]):
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
    print(f"\nVERDICT    {res['verdict']}")
    if res["torn_iterations"]:
        print("  *** TORN blocks. BLOCKER: this forces a format change, not a")
        print("  *** firmware workaround.")
    if res["neighbour_damage"]:
        print("  *** Neighbour-block corruption: the FTL damaged data nobody wrote.")
    if res["qualifying"] < res["required_qualifying"]:
        short = res["required_qualifying"] - res["qualifying"]
        print(f"  {short} short of the required qualifying cuts. Issue a continuation")
        print(f"  with `plan --extend` rather than editing this run.")

    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(res, indent=2) + "\n")
        print(f"\nwrote {a.json}")
    return 0 if res["verdict"] == "PASS" else 2


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan", help="emit a committed cut schedule")
    p.add_argument("--sku"); p.add_argument("--revision"); p.add_argument("--cid")
    p.add_argument("--attempts", type=int,
                   help=f"planned attempts (default {int(REQUIRED_QUALIFYING * DEFAULT_SURPLUS)}); "
                        f"the judge always requires {REQUIRED_QUALIFYING} qualifying")
    p.add_argument("--extend", help="prior plan to continue under the same run id")
    p.add_argument("--block", type=int, default=1_000_000)
    p.add_argument("--seed", type=int, default=20260903)
    p.add_argument("--out")
    p.set_defaults(fn=cmd_plan)

    j = sub.add_parser("judge", help="classify a run against its committed plan(s)")
    j.add_argument("--plan", action="append", required=True,
                   help="repeat for continuation plans")
    j.add_argument("--results", required=True)
    j.add_argument("--json")
    j.set_defaults(fn=cmd_judge)

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
