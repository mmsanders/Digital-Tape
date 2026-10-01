#!/usr/bin/env python3
"""#130 self-test: census, clean synthetic run, causal controls on exact kill sets, and the V-R55-01 demonstration.

Row 1 controls: each must go red on exactly the positions where its timeline differs from the spec's.
Row 2 controls: every single under-reported clean write or flush, on every fixture, must go red here; the
pinned #118 row-3 oracle must ACCEPT every one of them except a dropped final flush (which it already sees) -
that acceptance is the V-R55-01 defect this row closes. Dropping pass 2 must go red exactly on the fixtures
§9.4 forces to two commits.
"""
from __future__ import annotations

import oracle as O
import rows as R
from synthetic_adapter import ROW1_MUTANTS, lines, observation, overdub_timeline, w10_row3_records

EXPECTED = {"row1": 3, "row2": 5}
ROW1_KILLS = {"overdub_wraps": 3, "negative_rail_32767": 3, "positive_overflow_wraps": 3,
              "append_mixed_with_last_frame": 1}
UNDER_REPORT_VARIANTS = 48          # 24 writes + 24 flushes across the five #118 clean traces
W10_ACCEPTS = 43                    # every variant but the five dropped final flushes


def red(case, mutant):
    try:
        O.check(case, observation(case, mutant))
        return False
    except (AssertionError, ValueError):
        return True


def w10_accepts(case, mutant):
    rec = observation(case, mutant)["wp10_final_record"]
    w = next(c for c in O.W10.iter_cases() if c["row"] == 3 and c["fixture"] == case["fixture"])
    try:
        O.W10.check(w, rec)
        return True
    except (AssertionError, ValueError):
        return False


def main():
    census = O.plan_census()
    for k, v in EXPECTED.items():
        assert census[k] == v, f"census {k}: {census[k]} != {v}"
    n = O.check_stream(lines())
    cases = list(O.iter_cases())
    out = []
    for m in ROW1_MUTANTS:
        want = {c["index"] for c in cases if c["row"] == 1
                and overdub_timeline(R.POSITIONS[c["position"]], m) != R.expected_timeline(R.POSITIONS[c["position"]])}
        got = {c["index"] for c in cases if c["row"] == 1 and red(c, m)}
        assert got == want and len(got) == ROW1_KILLS[m], f"{m}: killed {sorted(got)} want {sorted(want)}"
        out.append(f"{m}={len(got)}")
    variants = accepted = 0
    for c in cases:
        if c["row"] != 2:
            continue
        ev = w10_row3_records()[c["fixture"]]["clean"]["events"]
        for i, e in enumerate(ev):
            if e["op"] not in ("write", "flush"):
                continue
            variants += 1
            assert red(c, ("drop_event", i)), f"{c['fixture']}: under-reported {e['op']} #{i} survived the floor"
            last_flush = e["op"] == "flush" and not any(x["op"] == "flush" for x in ev[i + 1:])
            acc = w10_accepts(c, ("drop_event", i))
            assert acc == (not last_flush), f"{c['fixture']} #{i}: #118 oracle acceptance {acc}"
            accepted += acc
    assert (variants, accepted) == (UNDER_REPORT_VARIANTS, W10_ACCEPTS), (variants, accepted)
    two = {c["fixture"] for c in cases if c["row"] == 2 and red(c, ("drop_second_commit", None))}
    assert two == {f for f, a in R.COMMITS_ALLOWED.items() if min(a) == 2}, two
    assert all(w10_accepts(c, ("drop_second_commit", None)) for c in cases if c["row"] == 2)
    out += [f"under_report_one_event={variants}/{variants} (#118 oracle accepts {accepted})",
            f"drop_second_commit={len(two)} {sorted(two)}"]
    print(f"PASS census {census}; clean synthetic {n}/{n}; controls: " + ", ".join(out))


if __name__ == "__main__":
    main()
