#!/usr/bin/env python3
"""The fabrication gate must be able to OPEN, and must stay shut otherwise.

Most gates in this repo are normally green and are proven able to go red. This
one is the inverse: its normal state is CLOSED, and the thing worth proving is
that it can ever open. **A gate that can only fail is a gate nobody reads**, and
it would quietly stop being consulted long before anyone ordered a board.

    python3 test_fabrication_gate.py
    python3 test_fabrication_gate.py --mutate
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fabrication_gate as fg       # noqa: E402
import solenoid_timing as sol       # noqa: E402

FAILED: list[str] = []


def check(ok: bool, what: str) -> None:
    if not ok:
        FAILED.append(what)
        print(f"  FAIL {what}")


def with_state(accepted: bool, verified: bool):
    """Evaluate the gate under a hypothetical world, then restore."""
    saved_b, saved_v = fg.BLOCKERS, sol.TIMING_BOUND_VERIFIED
    fg.BLOCKERS = tuple(replace(b, accepted_by="PM, 2026-01-01" if accepted else "")
                        for b in saved_b)
    sol.TIMING_BOUND_VERIFIED = verified
    try:
        return fg.open_blockers()
    finally:
        fg.BLOCKERS, sol.TIMING_BOUND_VERIFIED = saved_b, saved_v


def run() -> int:
    # --- 1. today: shut, and for reasons it can name ---------------------
    now = fg.open_blockers()
    check(now != [], "the gate is CLOSED today")
    check(any("IR-015-solenoid" in b for b in now),
          "the solenoid finding is named as a blocker")
    check(any("qualification" in b for b in now),
          "the unverified timing bound blocks fabrication, not just the document")

    # --- 2. it can OPEN. This is the point of the file -------------------
    check(with_state(accepted=True, verified=True) == [],
          "the gate OPENS when every blocker is accepted and the analysis certifies")

    # --- 3. neither condition alone is enough ----------------------------
    check(with_state(accepted=True, verified=False) != [],
          "acceptance alone does not open it while a corner is unbound")
    check(with_state(accepted=False, verified=True) != [],
          "a certifying analysis alone does not open it while a finding is open")

    # --- 4. the distinction the reviewer asked to be machine-enforced ----
    # A green `thermal-check` must not be mistakable for qualification.
    check(sol.check_criteria(strict=False) == [] and sol.verdict() != "PASS",
          "the inequalities can hold while the verdict is not PASS -- "
          "so green thermal CI is not qualification")
    check(any("verdict is PROVISIONAL" in b for b in now),
          "the gate says so itself rather than leaving it to convention")

    n = 8
    if FAILED:
        print(f"\n{len(FAILED)} of {n} checks FAILED")
        return 1
    print(f"all {n} checks pass")
    return 0


def mutate() -> int:
    """The failure that matters for THIS gate: one that opens for free."""
    fg.open_blockers = lambda: []
    rc = run()
    if rc == 0:
        print("\nMUTATION SURVIVED -- the checks cannot go red. That is the bug.")
        return 1
    print("\nOK  mutation caught: a fabrication gate that opens for free is detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(mutate() if "--mutate" in sys.argv else run())
