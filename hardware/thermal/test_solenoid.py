#!/usr/bin/env python3
"""Checks on the solenoid safety criteria, and proof they can go red.

IR-018-14: the solenoid analysis failed open as a gate. `--check` only asked
whether the Markdown matched the generator, so an unsafe parameter edit produced
an unsafe table, a fresh file, and a GREEN result. Worse, `hardware.yml` never
invoked it at all. That is the same fail-open class this project has removed
everywhere else, sitting in the one analysis backing a safety limit.

So the criteria are executable now, and this file proves each can fail. The
headline red case is the strongest one available: **the previous working point**
(5.0 W, 15 ms, 450 ms), which the old model reported as a 1.14x pass and the
corrected model rejects on two separate criteria.

    python3 test_solenoid.py            run the checks
    python3 test_solenoid.py --mutate   prove they can go red
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import solenoid_timing as st        # noqa: E402

FAILED: list[str] = []


def check(ok: bool, what: str) -> None:
    if not ok:
        FAILED.append(what)
        print(f"  FAIL {what}")


def at(coil, pulse, lockout):
    """Evaluate the criteria at a working point, then restore."""
    saved = (st.COIL_W, st.PULSE_NOM_MS, st.LOCKOUT_NOM_MS)
    st.COIL_W, st.PULSE_NOM_MS, st.LOCKOUT_NOM_MS = coil, pulse, lockout
    try:
        return st.check_criteria(strict=False)
    finally:
        st.COIL_W, st.PULSE_NOM_MS, st.LOCKOUT_NOM_MS = saved


def run() -> int:
    # --- 1. the working point as designed passes -------------------------
    check(at(st.COIL_W, st.PULSE_NOM_MS, st.LOCKOUT_NOM_MS) == [],
          "the committed working point meets every criterion")

    # --- 2. the electrical corner is real and points the way it should ---
    check(st.coil_power_factor() > 1.0,
          "worst-case coil power exceeds nominal")
    check(st.coil_power_factor(t_cold=st.T_REF_C) < st.coil_power_factor(t_cold=0.0),
          "a colder coil is the worse case -- copper resistance falls as it cools")
    check(st.worst_coil_w(1.0) == st.coil_power_factor(),
          "worst_coil_w scales the nominal by the corner factor")

    # --- 3. the two corners are distinct, and the right way round -------
    check(st.min_inhibit_ms() < st.max_inhibit_ms(),
          "the fast and slow inhibit corners are distinct")
    check(st.max_inhibit_ms() <= 1000.0 / st.LEGIT_RATE_HZ,
          f"the SLOW corner ({st.max_inhibit_ms():.1f} ms) clears the "
          f"{1000.0/st.LEGIT_RATE_HZ:.0f} ms period of legitimate use")

    # --- 4. the finite window is not below the asymptotic ratio ---------
    check(st.rolling_window_w() >= st.fault_avg_w(),
          "the finite rolling window is at least the asymptotic duty ratio")

    # --- 5. timing resistors are inside the part's specified envelope ---
    for name, ms, cap in (("pulse", st.PULSE_NOM_MS, 100e-9),
                          ("lockout", st.LOCKOUT_NOM_MS, 1e-6)):
        r = st.timing_resistor_ohm(ms, cap)
        check(st.R_EXT_MIN_OHM <= r <= st.R_EXT_MAX_OHM,
              f"{name} timing resistor {r/1000:.0f} kOhm is inside "
              f"{st.R_EXT_MIN_OHM/1000:.0f}..{st.R_EXT_MAX_OHM/1000:.0f} kOhm")

    # --- 6. RED: the previous working point must be rejected ------------
    # 5.0 W / 15 ms / 450 ms. The old model called this 0.220 W and a 1.14x
    # pass. It fails the power criterion AND the usability criterion.
    old = at(5.0, 15.0, 450.0)
    check(any("average coil power" in f for f in old),
          "RED: the previous working point fails the power criterion")
    check(any("block a legitimate press" in f for f in old),
          "RED: the previous working point fails the usability criterion")

    # --- 7. RED: each criterion individually ----------------------------
    check(any("average coil power" in f for f in at(12.0, st.PULSE_NOM_MS, st.LOCKOUT_NOM_MS)),
          "RED: an over-powered coil is caught")
    check(any("block a legitimate press" in f for f in at(st.COIL_W, st.PULSE_NOM_MS, 440.0)),
          "RED: a lockout that blocks 2 Hz use is caught")
    check(any("single-pulse ceiling" in f for f in at(0.05, 60.0, st.LOCKOUT_NOM_MS)),
          "RED: a pulse over the single-pulse ceiling is caught")
    check(any("outside the part's specified" in f
              for f in at(st.COIL_W, 200.0, st.LOCKOUT_NOM_MS)),
          "RED: a timing resistor outside the datasheet range is caught")

    # --- 8. IR-018-17: the handoff cannot race --------------------------
    covers, a_max = st.b_covers_a()
    check(covers, f"the inhibit outlasts the coil pulse ({st.min_inhibit_ms():.0f} ms vs "
                  f"{a_max:.3f} ms incl. propagation) -- no handoff gap")
    check(st.PROP_MAX_S > 0, "propagation is in the model at all")
    # RED: the OLD topology, where B started at A's falling edge, is exactly a
    # design whose inhibit does not outlast the pulse. Model it by shrinking the
    # inhibit below the pulse and assert the criteria reject it.
    gap = at(st.COIL_W, 400.0, 300.0)
    check(any("handoff gap" in f for f in gap),
          "RED: an inhibit that does not outlast the pulse is caught")
    check(any("handoff gap" in f
              for f in at(st.COIL_W, st.PULSE_NOM_MS, st.PULSE_NOM_MS)),
          "RED: an inhibit equal to the pulse is caught (propagation makes it short)")

    # --- 9. IR-018-16: unbound corners are reported, not absorbed --------
    check(st.qualification_gaps() != [],
          "the unverified timing bound is reported as a qualification gap")
    check(st.verdict() == "PROVISIONAL",
          f"the verdict is PROVISIONAL while a corner is unbound (got {st.verdict()})")
    check(st.V_LOGIC < st.HCT_MIN_V,
          f"the {st.V_LOGIC} V logic rail excludes the HCT family, as it must")

    # --- 10. the feasibility boundary is monotonic ----------------------
    # A longer pulse must permit a weaker coil, or the boundary is inverted.
    ws = [st.feasible_coil_w(p) for p in (8.0, 10.0, 12.0, 15.0, 20.0)]
    check(all(a > b for a, b in zip(ws, ws[1:])),
          f"a longer pulse permits a weaker coil ({[round(w,2) for w in ws]})")
    check(st.feasible_coil_w(st.PULSE_NOM_MS) >= st.COIL_W,
          f"the committed coil ({st.COIL_W:.1f} W) is within the boundary "
          f"({st.feasible_coil_w(st.PULSE_NOM_MS):.2f} W) for its pulse")

    n = 24
    if FAILED:
        print(f"\n{len(FAILED)} of {n} checks FAILED")
        return 1
    print(f"all {n} checks pass")
    return 0


def mutate() -> int:
    """The fail-open that IR-018-14 found: a check that only asks whether the
    document is fresh, and never whether the design is safe."""
    st.check_criteria = lambda strict=True: []
    rc = run()
    if rc == 0:
        print("\nMUTATION SURVIVED -- the checks cannot go red. That is the bug.")
        return 1
    print("\nOK  mutation caught: a criteria check that never fails is detected")
    return 0


if __name__ == "__main__":
    if "--mutate" in sys.argv:
        raise SystemExit(mutate())
    raise SystemExit(run())
