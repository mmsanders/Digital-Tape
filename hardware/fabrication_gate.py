#!/usr/bin/env python3
"""May a board be fabricated or a cell charged? Machine-enforced.

Raised by the independent reviewer as an auditability caution on IR-018-16, and
it lands because the condition they made it conditional on is already true:

    "green thermal CI is not qualification of the solenoid circuit while
     IR-018-16 remains open. If the project later uses that CI status as a
     fabrication gate, this distinction should become machine-enforced rather
     than conventional."

**This project already has that gate**, and it was a sentence in a document:
*no board is fabricated and no cell is charged until all three IR-015 findings
close.* A sentence is exactly what "conventional" means. So this file is the
sentence, executable.

Two things it deliberately does NOT do:

  * It does not run as a blocking CI job. Its normal state is RED, and a
    permanently-red pipeline stops being read -- `ci.yml` says so itself about
    the golden suite. It is a target a human runs before spending money, and
    its verdict is quoted in STATUS-HARDWARE.md.
  * It does not decide whether a finding is closed. Closure is an acceptance by
    the PM or a reviewer, recorded here as a fact with a name attached. The
    author of a response does not get to mark it accepted -- CLAUDE.md §2 -- so
    an `accepted_by` this file cannot verify is left empty and reads as OPEN.

    make -C hardware fabrication-gate
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "thermal"))
import solenoid_timing as sol       # noqa: E402


@dataclass(frozen=True)
class Blocker:
    ident: str
    what: str
    clears_when: str
    accepted_by: str = ""           # empty => still open. Only the PM or a
                                    # reviewer may fill this in.


# The three IR-015 findings and the fabrication gate they carry, from
# spec/hw/thermal-budget.md's banner and PM Decisions 007 §3.
BLOCKERS = (
    Blocker("IR-015-charger",
            "Charger 45 °C enforcement mechanism",
            "the PM or a reviewer accepts the TS-divider response (ADR-111)"),
    Blocker("IR-015-solenoid",
            "Solenoid average coil power ≤ 0.25 W over any rolling 10 s window",
            "the PM or a reviewer accepts the response. Reviewed twice and "
            "rejected twice; IR-018-17 is resolved, IR-018-16 is not"),
    Blocker("IR-015-transient",
            "Per-device junction temperatures during the copy transient",
            "the PM or a reviewer accepts the per-device model"),
)


def open_blockers() -> list[str]:
    """Everything standing between here and spending money."""
    out = [f"{b.ident}: {b.what} — clears when {b.clears_when}"
           for b in BLOCKERS if not b.accepted_by.strip()]

    # Not taken on trust: asked of the analysis itself. This is the machine
    # enforcement the caution asks for -- a green `thermal-check` says the
    # inequalities hold at the assumed corners, and says nothing about whether
    # those corners are real.
    for gap in sol.qualification_gaps():
        out.append(f"solenoid qualification: {gap}")
    if sol.verdict() != "PASS":
        out.append(f"solenoid analysis verdict is {sol.verdict()}, not PASS — "
                   "an analysis that cannot certify itself cannot support fabrication")
    return out


def main() -> int:
    blocking = open_blockers()
    print("FABRICATION GATE — may a board be fabricated or a cell charged?")
    print()
    if not blocking:
        print("  OPEN. Every blocker is accepted and the analysis certifies.")
        print()
        for b in BLOCKERS:
            print(f"    accepted: {b.ident} — by {b.accepted_by}")
        return 0
    print(f"  **CLOSED.** {len(blocking)} blocking item(s):")
    print()
    for line in blocking:
        print(f"    - {line}")
    print()
    print("  No board is fabricated and no cell is charged while this reads CLOSED.")
    print("  A green `make -C hardware check` does NOT clear it: that gate checks the")
    print("  inequalities at their assumed corners, which is a different question.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
