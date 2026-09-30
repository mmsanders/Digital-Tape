#!/usr/bin/env python3
"""WP-10 backlog rows 1-3 self-test: census, clean synthetic run, causal controls per row."""
from __future__ import annotations

import oracle as O
from synthetic_adapter import MUTANTS, lines, observation

EXPECTED = {"row1_crash": 24_660, "row1_complete": 2, "row2_frontier": 55_152, "row3_groups": 6,
            "caseset_sha256": "036e255eb2a704d041b87eb21116900ea307ba450a5cf72f3b0440dffdd3b2d7"}
ROW_OF = {1: O.ROW1, 2: O.ROW2, 3: O.ROW3}


def main():
    census = O.plan_census()
    for k, v in EXPECTED.items():
        assert census[k] == v, f"census {k}: {census[k]} != {v}"
    n, row3 = O.check_stream(lines())
    killed = {}
    for mutant, row in MUTANTS.items():
        for trust_trace in ((False, True) if row == 1 else (False,)):
            reds, groups = 0, set()
            for case in O.iter_cases():
                if case["row"] != row:
                    continue
                try:
                    O.check(case, observation(case, mutant), trust_trace)
                except AssertionError:
                    reds += 1
                    groups.add(case.get("scenario") or case.get("campaign") or case.get("record_mode"))
            assert reds, f"control {mutant} (trust_trace={trust_trace}) survived"
            if row in (1, 3):
                want = set(O.D.SCENARIOS) if row == 1 else set(O.RECORD_MODES)
                assert groups == want, f"control {mutant} missed {want - groups}"
            killed[(mutant, trust_trace)] = reds
    rows_controlled = {ROW_OF[r] for r in MUTANTS.values()}
    assert rows_controlled == {O.ROW1, O.ROW2, O.ROW3}
    print(f"PASS census row1 {census['row1_crash']} crash ({census['row1_by_mode']}) + {census['row1_complete']} complete; "
          f"row2 {census['row2_frontier']} frontier ({census['row2_by_campaign']} of {census['row2_campaign_totals']}, "
          f"{census['row2_by_mode']}); row3 {census['row3_groups']} groups; caseset {census['caseset_sha256']}; "
          f"clean synthetic {n}/{n} with {row3} row-3 injections; {len(MUTANTS)} causal controls killed: "
          + ", ".join(f"{m}{'[outcome-only]' if t else ''}={r}" for (m, t), r in killed.items()))


if __name__ == "__main__":
    main()
