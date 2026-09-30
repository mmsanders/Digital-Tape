#!/usr/bin/env python3
"""Positive synthetic census plus causal mutant controls for every R53 gap row."""
from __future__ import annotations

from oracle import check, check_all, load_plan, plan_sha256
from synthetic_adapter import MUTANTS, all_observations, observation

# Each mutant must turn exactly these cases red and leave every other case green.
EXPECTED_KILLS = {
    "drop_last_frame": {"RENDER-TWOPASS", "RENDER-DECLINE", "RENDER-FRAGMENTED"},
    "ignore_entry_start": {"RENDER-FRAGMENTED"},
    "flush_failure_not_faulted": {"F-RESPOOL-WRITE", "F-RESPOOL-HEADER-FLUSH",
                                  "F-PROMOTE-WRITE", "F-PROMOTE-FLUSH"},
    "arm_after_header_flush": {"F-RESPOOL-WRITE", "F-RESPOOL-HEADER-FLUSH",
                               "F-PROMOTE-WRITE", "F-PROMOTE-FLUSH"},
    "service_touches_media": {"F-RESPOOL-WRITE", "F-RESPOOL-HEADER-FLUSH",
                              "F-PROMOTE-WRITE", "F-PROMOTE-FLUSH"},
    "failure_keeps_more_work": {"F-RESPOOL-WRITE", "F-RESPOOL-HEADER-FLUSH",
                                "F-PROMOTE-WRITE", "F-PROMOTE-FLUSH"},
}


def killed_by(mutant, plan):
    out = set()
    for case in plan["cases"]:
        try:
            check(case, observation(case, plan, mutant), plan)
        except AssertionError:
            out.add(case["id"])
    return out


def main():
    plan = load_plan()
    count = check_all(all_observations())
    assert set(EXPECTED_KILLS) == set(MUTANTS), "control census drift"
    row_killers = {}
    for mutant in MUTANTS:
        got = killed_by(mutant, plan)
        if got != EXPECTED_KILLS[mutant]:
            raise AssertionError(f"control {mutant}: killed {sorted(got)}, "
                                 f"expected {sorted(EXPECTED_KILLS[mutant])}")
        for case in plan["cases"]:
            if case["id"] in got:
                for row in case["rows"]:
                    row_killers.setdefault(row, set()).add(mutant)
    rows = {row for case in plan["cases"] for row in case["rows"]}
    missing = rows - set(row_killers)
    assert not missing, f"gap rows without a causal control: {sorted(missing)}"
    assert all(any(case["id"] in k for k in EXPECTED_KILLS.values()) for case in plan["cases"])
    print(f"PASS {count} positive synthetic cases; {len(MUTANTS)} causal controls killed; "
          f"{len(rows)} gap rows each with >=1 control; plan {plan_sha256()}")


if __name__ == "__main__":
    main()
