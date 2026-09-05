#!/usr/bin/env python3
"""Tests for the media-atomicity judge — IR-018-05, extended for IR-018-06..10.

This tool decides whether the format's central physical assumption holds, so a
regression in it fails OPEN: a PASS nobody earned. Two rounds of independent
review each found a way to reach PASS without the evidence, so the suite is
organised by finding.

`--mutate` is the red case: it patches `classify` to always return NEW, the most
plausible fail-open, and asserts the suite catches it.

    ./test_media_atomicity.py            run the suite
    ./test_media_atomicity.py --mutate   prove the suite goes red
"""

from __future__ import annotations

import argparse
import struct
import sys

import media_atomicity as M

OK, FAIL = [], []
SKU, REV, CID = "TEST-SKU", "rev-1", "cid-deadbeef"
# IR-018-06: tests inject their own policy. They cannot lower the production
# threshold through the plan file, because the plan file no longer carries one.
TINY = M.Policy(min_qualifying=3)


def check(name, cond, detail=""):
    (OK if cond else FAIL).append(name)
    print(f"  {'ok  ' if cond else 'FAIL'} {name}{'' if cond else '  <- ' + detail}")


def plan(n=3, run="run-1", sku=SKU, rev=REV, cid=CID, start=1, extends=None):
    p = {"plan_version": 3, "run_id": run, "sku": sku, "revision": rev,
         "card_cid": cid, "block": 1000,
         "neighbour_offsets": list(M.NEIGHBOUR_OFFSETS),
         "planned_attempts": n, "extends": extends,
         "trials": [{"iteration": i, "cut_offset_fraction": 0.5}
                    for i in range(start, start + n)]}
    p["plan_digest"] = M.plan_digest(p)
    return p


NB = {off: (bytes([i + 1]) * M.BLOCK).hex()
      for i, off in enumerate(M.NEIGHBOUR_OFFSETS)}


def trial(n, *, data=None, p=None, sku=SKU, rev=REV, cid=CID, pre_ok=True, pre=None,
          neighbours=None, baseline=None, bus="sd4", busy_line=None,
          payload=True, response=True, be=100, bs=120, cut=150, deassert=None,
          digest=None):
    p = p or plan()
    return {"run_id": p["run_id"], "iteration": n,
            "sku": sku, "revision": rev, "card_cid": cid,
            "plan_digest": digest if digest is not None else p["plan_digest"],
            "precondition_ok": pre_ok,
            "precondition_readback_hex": (pre if pre is not None
                                          else M.pattern(n - 1)).hex(),
            "bus_mode": bus,
            "busy_line": busy_line if busy_line is not None else M.BUS_MODES.get(bus, "DAT0"),
            "payload_complete": payload, "data_response_accepted": response,
            "busy_entry_us": be, "busy_sampled_us": bs, "cut_us": cut,
            "busy_deassert_us": deassert,
            "readback_hex": (data if data is not None else M.pattern(n)).hex(),
            "neighbours": dict(NB) if neighbours is None else neighbours,
            "neighbour_baseline": dict(NB) if baseline is None else baseline}


def run(rows, p=None, policy=TINY):
    return M.judge([p or plan()], rows, policy)


def e2e():
    """Run the exact commands WP-05 publishes, end to end.

    IR-018-10: the documented judge invocation had drifted from the CLI and could
    not run. A doc example nobody executes is a doc example that rots, so CI runs
    this one.
    """
    import json, subprocess, tempfile, os
    here = os.path.dirname(os.path.abspath(__file__))
    with tempfile.TemporaryDirectory() as d:
        plan_p, run_p, out_p = (os.path.join(d, f) for f in
                                ("plan.json", "run.jsonl", "verdict.json"))
        r = subprocess.run([sys.executable, "media_atomicity.py", "plan",
                            "--sku", "E2E", "--revision", "r9", "--cid", "cid-e2e",
                            "--attempts", "1100", "--out", plan_p],
                           cwd=here, capture_output=True, text=True)
        check("plan runs as published", r.returncode == 0, r.stderr[:100])
        if r.returncode:
            return
        pl = json.load(open(plan_p))
        nb = {o: (bytes([i + 1]) * M.BLOCK).hex()
              for i, o in enumerate(M.NEIGHBOUR_OFFSETS)}
        with open(run_p, "w") as fh:
            for t in pl["trials"]:
                n = t["iteration"]
                miss = n % 15 == 0
                fh.write(json.dumps({
                    "run_id": pl["run_id"], "iteration": n, "sku": pl["sku"],
                    "revision": pl["revision"], "card_cid": pl["card_cid"],
                    "plan_digest": pl["plan_digest"], "precondition_ok": True,
                    "precondition_readback_hex": M.pattern(n - 1).hex(),
                    "bus_mode": "sd4", "busy_line": "DAT0",
                    "payload_complete": True, "data_response_accepted": not miss,
                    "busy_entry_us": 100, "busy_sampled_us": 120, "cut_us": 150,
                    "busy_deassert_us": None,
                    "readback_hex": (M.pattern(n) if n % 2 else M.pattern(n - 1)).hex(),
                    "neighbours": nb, "neighbour_baseline": nb}) + "\n")
        r = subprocess.run([sys.executable, "media_atomicity.py", "judge",
                            "--plan", plan_p, "--results", run_p, "--json", out_p],
                           cwd=here, capture_output=True, text=True)
        check("judge runs as published and passes a sound campaign",
              r.returncode == 0, (r.stderr or r.stdout)[-140:])
        if os.path.exists(out_p):
            v = json.load(open(out_p))
            check("verdict records measured identity, not the plan's claim",
                  v["sku"] == "E2E" and v["card_cid"] == "cid-e2e")
            check("misses are absorbed by the surplus",
                  v["qualifying"] >= M.REQUIRED_QUALIFYING
                  and v["planned_attempts"] > v["qualifying"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mutate", action="store_true")
    a = ap.parse_args()
    if a.mutate:
        M.classify = lambda data, n: "NEW"
        print("MUTATION ACTIVE: classify() always returns NEW\n")

    print("classification")
    check("NEW", M.classify(M.pattern(7), 7) == "NEW")
    check("OLD", M.classify(M.pattern(6), 7) == "OLD")
    t = M.pattern(7)[:200] + M.pattern(6)[200:]
    check("TORN at a byte offset", M.classify(t, 7) == "TORN", M.classify(t, 7))
    tw = M.pattern(7)[:4] + M.pattern(6)[4:]
    check("TORN at a word boundary", M.classify(tw, 7) == "TORN", M.classify(tw, 7))
    check("CORRUPT on a foreign value",
          M.classify(struct.pack("<I", 99) * M.WORDS, 7) == "CORRUPT")
    check("CORRUPT on a short read", M.classify(b"\x00" * 8, 7) == "CORRUPT")

    print("\nhappy path")
    r = run([trial(1), trial(2, data=M.pattern(1)), trial(3)])
    check("clean run passes", r["verdict"] == "PASS", str(r["problems"])[:110])
    check("identity comes from evidence",
          (r["sku"], r["revision"], r["card_cid"]) == (SKU, REV, CID))

    print("\nIR-018-06  the 1000 minimum is unconditional")
    r = M.judge([plan(3)], [trial(1), trial(2), trial(3)], M.PRODUCTION)
    check("3 qualifying cannot pass under production policy", r["verdict"] == "FAIL")
    r = M.judge([plan(0)], [], M.PRODUCTION)
    check("an empty plan cannot pass", r["verdict"] == "FAIL")
    p_lie = plan(3); p_lie["required_qualifying"] = 0
    p_lie["plan_digest"] = M.plan_digest(p_lie)
    r = M.judge([p_lie], [trial(1, p=p_lie), trial(2, p=p_lie), trial(3, p=p_lie)],
                M.PRODUCTION)
    check("a plan claiming required_qualifying=0 is ignored", r["verdict"] == "FAIL")
    check("the judge reports its own threshold",
          r["required_qualifying"] == M.REQUIRED_QUALIFYING)

    print("\nIR-018-07  qualification is from protocol state, not a pin level")
    r = run([trial(1, payload=False), trial(2), trial(3)])
    check("incomplete payload does not qualify", r["qualifying"] == 2)
    r = run([trial(1, response=False), trial(2), trial(3)])
    check("no data-response token does not qualify", r["qualifying"] == 2)
    r = run([trial(1, be=200, bs=150), trial(2), trial(3)])
    check("busy sampled before the busy phase began does not qualify",
          r["qualifying"] == 2)
    r = run([trial(1, bs=200, cut=150), trial(2), trial(3)])
    check("busy sampled after the cut does not qualify", r["qualifying"] == 2)
    r = run([trial(1, deassert=140, cut=150), trial(2), trial(3)])
    check("busy already ended before the cut does not qualify", r["qualifying"] == 2)
    r = run([trial(1, bus=None), trial(2), trial(3)])
    check("an unstated bus mode does not qualify", r["qualifying"] == 2)
    r = run([trial(1, bus="spi", busy_line="DAT0"), trial(2), trial(3)])
    check("SPI must sense MISO, not DAT0", r["qualifying"] == 2)
    r = run([trial(1, bus="spi", busy_line="MISO"), trial(2), trial(3)])
    check("SPI sensing MISO qualifies", r["qualifying"] == 3)

    print("\nIR-018-08  results are bound to card identity")
    for f, kw in (("sku", {"sku": None}), ("revision", {"rev": None}),
                  ("CID", {"cid": None})):
        r = run([trial(1, **kw), trial(2), trial(3)])
        check(f"missing {f} invalidates the trial",
              any(("missing" in p) for p in r["problems"]))
    r = run([trial(1, cid="other-card"), trial(2), trial(3)])
    check("a different card's CID is rejected",
          any("card_cid" in p for p in r["problems"]))
    r = run([trial(1, digest="0" * 64), trial(2), trial(3)])
    check("a result not bound to this plan is rejected",
          any("plan_digest" in p for p in r["problems"]))
    p_t = plan(3); p_t["trials"][0]["cut_offset_fraction"] = 0.9
    r = M.judge([p_t], [trial(1, p=p_t)], TINY)
    check("a tampered plan fails its own digest",
          any("digest does not match" in p for p in r["problems"]))

    print("\nIR-018-09  surplus attempts, and a continuation plan")
    p6 = plan(6)
    rows = [trial(1, p=p6), trial(2, p=p6, payload=False), trial(3, p=p6),
            trial(4, p=p6, busy_line="wrong"), trial(5, p=p6), trial(6, p=p6)]
    r = M.judge([p6], rows, TINY)
    check("a run with misses still passes on qualifying count",
          r["verdict"] == "PASS", str(r["problems"])[:110])
    check("misses are reported, not hidden", sum(r["non_qualifying"].values()) == 2)
    check("attempted and qualifying are separate numbers",
          r["planned_attempts"] == 6 and r["qualifying"] == 4)
    ext = plan(2, start=7, extends="run-1")
    r = M.judge([plan(3), ext], [trial(1), trial(2), trial(3),
                                 trial(7, p=ext), trial(8, p=ext)], TINY)
    check("a continuation plan extends the campaign", r["verdict"] == "PASS",
          str(r["problems"])[:110])

    print("\nIR-018-02/03/04  earlier findings stay closed")
    r = run([trial(1)] * 3)
    check("duplicates rejected", any("duplicate" in p for p in r["problems"]))
    r = run([trial(1), trial(2)])
    check("an unreported planned trial fails",
          any("not reported" in p for p in r["problems"]))
    r = run([trial(n, neighbours={}, baseline={}) for n in (1, 2, 3)])
    check("omitted neighbours invalidate rather than pass", r["verdict"] == "FAIL")
    dmg = dict(NB); dmg["+2"] = (b"\xFF" * M.BLOCK).hex()
    r = run([trial(1, neighbours=dmg), trial(2), trial(3)])
    check("neighbour damage caught", len(r["neighbour_damage"]) == 1)
    distinct = {o: (bytes([9 - i]) * M.BLOCK).hex()
                for i, o in enumerate(M.NEIGHBOUR_OFFSETS)}
    r = run([trial(n, neighbours=distinct, baseline=distinct) for n in (1, 2, 3)])
    check("distinct-but-unchanged neighbours are not false damage",
          r["verdict"] == "PASS")
    r = run([trial(1, pre_ok=False), trial(2), trial(3)])
    check("failed precondition invalidates", any("precondition" in p for p in r["problems"]))
    r = run([trial(1, pre=M.pattern(5)), trial(2), trial(3)])
    check("precondition not equal to N-1 is rejected",
          any("pattern N-1" in p for p in r["problems"]))

    print("\ndetection of the thing this tool exists to detect")
    r = run([trial(1), trial(2, data=M.pattern(2)[:200] + M.pattern(1)[200:]), trial(3)])
    check("one torn block fails the run", r["verdict"] == "FAIL", r["verdict"])
    check("and is reported by iteration", r["torn_iterations"] == [2])

    print("\nIR-018-10  the published procedure is executable")
    e2e()

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
