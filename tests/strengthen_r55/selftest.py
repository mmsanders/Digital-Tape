#!/usr/bin/env python3
"""#126 strengthening self-test: census, clean synthetic run, causal controls with exact kill sets."""
from __future__ import annotations

import oracle as O
import rows as R
from synthetic_adapter import MUTANTS, lines, observation

EXPECTED = {"row1": 12, "row2": 1, "row3": 27}
ROW1_MULTIBLOCK = {(f, d) for f in R.DUP_FRAMES if f > 128 for d in R.DUP_DESTS}
EXACT = {
    # V-R54-02: every copy longer than one block must go red when only block 0 is copied (or any other block
    # is skipped), on blank and on reusable destinations alike.
    "copy_only_first_block": ROW1_MULTIBLOCK,
    "copy_skips_second_block": ROW1_MULTIBLOCK,
    "copy_skips_last_block": ROW1_MULTIBLOCK,
    "pass2_onto_then_live_chunk": {"PASS2-RUN-SIDE-A"},
    "pass2_declines": {"PASS2-RUN-SIDE-A"},
    "pass1_below_floor": {"PASS2-RUN-SIDE-A"},
    "a0_at_sequence_3": {c.id for c in R.CAP.cases()},
    "a1_structurally_valid": {c.id for c in R.CAP.cases()},
    "a_slots_not_snapshotted": {c.id for c in R.CAP.cases()},
}


def key(case):
    return ((case["frames"], case["destination"]) if case["row"] == 1 else
            case.get("fixture") or case.get("capacity_case"))


def main():
    census = O.plan_census()
    for k, v in EXPECTED.items():
        assert census[k] == v, f"census {k}: {census[k]} != {v}"
    n = O.check_stream(lines())
    killed = {}
    for mutant, row in MUTANTS.items():
        reds = set()
        for case in O.iter_cases():
            if case["row"] != row:
                continue
            try:
                O.check(case, observation(case, mutant))
            except AssertionError:
                reds.add(key(case))
        assert reds == EXACT[mutant], f"control {mutant} killed {sorted(reds, key=str)}"
        killed[mutant] = len(reds)
    assert {r for r in MUTANTS.values()} == {1, 2, 3}
    print(f"PASS census {census}; clean synthetic {n}/{n}; {len(MUTANTS)} controls killed on exact sets: "
          + ", ".join(f"{m}={k}" for m, k in killed.items()))


if __name__ == "__main__":
    main()
