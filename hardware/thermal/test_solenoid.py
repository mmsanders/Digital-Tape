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

    python3 test_solenoid.py                  run the checks
    python3 test_solenoid.py --mutate         prove they can go red
    python3 test_solenoid.py --mutate-supply  prove the supply-envelope control
                                              goes red if its own inequality is deleted
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


# ---------------------------------------------------------------------------
# P1-R3-HW: the supply-envelope criterion gets its own retained control.
#
# PR #47 added an inequality to check_criteria(): the BOUND part's supply
# envelope must contain V_LOGIC. It was prompted by a real catalogue listing of
# an HC part number (NXP 74HC221DB112) at 4.5..5.5 V -- selecting it would put
# the one-shot outside its supply range at this rail, and no other check here
# would have noticed.
#
# That criterion was demonstrated once, by hand, and nothing in the repository
# retained the demonstration. So deleting those four lines would have been a
# silent, green regression -- the exact fail-open class IR-018-14 removed from
# this file. The generic --mutate control does NOT cover it: that one replaces
# check_criteria wholesale, so it proves the suite notices a totally dead gate,
# not that this particular inequality is alive.
#
# Hence a targeted control, and a targeted mutation of it. Nothing here touches
# a datasheet, a measurement, a part acceptance or a gate: it is evidence
# hardening on an inequality that already exists.
SUPPLY_MARK = "outside its supply range"
HCT_LIKE_RANGE = (4.5, 5.5)      # the anomalous catalogue envelope, at a 3.3 V rail


def with_supply_range(rng):
    """Evaluate the criteria with a different bound-part envelope, then restore."""
    saved = st.PART_SUPPLY_RANGE_V
    st.PART_SUPPLY_RANGE_V = rng
    try:
        return st.check_criteria(strict=False)
    finally:
        st.PART_SUPPLY_RANGE_V = saved


def supply_failures_added_by_injection() -> set[str]:
    """Failures that appear ONLY because an HCT-envelope part was injected.

    Taking the difference against the committed baseline is what makes the
    control specific: a criterion that was already failing for an unrelated
    reason cannot masquerade as this one being alive.
    """
    base = set(with_supply_range(st.PART_SUPPLY_RANGE_V))
    return set(with_supply_range(HCT_LIKE_RANGE)) - base


def supply_control_survives_unrelated_noise() -> bool:
    """Is the control still specific when ANOTHER criterion is already failing?

    This is the distinguishability requirement. Differencing against the
    baseline is what delivers it: an over-powered coil fails the power criterion
    in both runs, so it cancels, and the injected envelope is still the only
    thing the control attributes to itself. Without the difference, "some
    criterion failed" would have been mistaken for "this criterion is alive".
    """
    saved = st.COIL_W
    st.COIL_W = 12.0          # fails the power criterion in BOTH runs
    try:
        noisy_base = set(with_supply_range(st.PART_SUPPLY_RANGE_V))
        added = supply_failures_added_by_injection()
        return (len(noisy_base) > 0
                and len(added) == 1
                and SUPPLY_MARK in next(iter(added)))
    finally:
        st.COIL_W = saved


def supply_removal_is_caught() -> bool:
    """Is the control above able to detect its own inequality being deleted?

    A negative control that survives the removal of the thing it controls for is
    decoration. The deletion is simulated by filtering that one finding out of
    check_criteria's output while leaving every other criterion intact, which is
    precisely what striking those lines from the source would do.

    Returns True when the deletion makes the control's central assertion -- one
    new failure, and it is the supply-envelope one -- stop holding.
    """
    real = st.check_criteria
    st.check_criteria = lambda strict=True: [f for f in real(strict=False)
                                             if SUPPLY_MARK not in f]
    try:
        return len(supply_failures_added_by_injection()) != 1
    finally:
        st.check_criteria = real


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

    # --- 11. P1-R3-HW: the supply-envelope criterion, retained ----------
    base = set(with_supply_range(st.PART_SUPPLY_RANGE_V))
    added = supply_failures_added_by_injection()
    only = next(iter(added)) if len(added) == 1 else ""
    lo, hi = HCT_LIKE_RANGE

    check(not any(SUPPLY_MARK in f for f in base),
          f"the committed envelope ({st.PART_SUPPLY_RANGE_V[0]:.0f}.."
          f"{st.PART_SUPPLY_RANGE_V[1]:.0f} V) does not itself trip the supply criterion")
    check(len(added) == 1,
          f"RED: injecting a {lo}..{hi} V part at the {st.V_LOGIC} V rail adds exactly "
          f"one failure (got {len(added)}: {sorted(added)})")
    check(SUPPLY_MARK in only,
          f"RED: that one added failure is the SUPPLY-ENVELOPE criterion and not a "
          f"coincidental other one (got {only!r})")
    check(f"{lo}..{hi} V" in only and f"rail is {st.V_LOGIC} V" in only,
          f"the supply-envelope failure names both the injected envelope and the rail, "
          f"so it cannot be mistaken for another criterion (got {only!r})")
    check(supply_control_survives_unrelated_noise(),
          "the control stays specific while an unrelated criterion is also failing")
    check(supply_removal_is_caught(),
          "the supply-envelope control goes RED if its own inequality is deleted")

    n = 30
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


def mutate_supply() -> int:
    """P1-R3-HW: delete ONLY the supply-envelope inequality and prove the suite
    notices -- which the generic wholesale mutation above cannot establish."""
    real = st.check_criteria
    st.check_criteria = lambda strict=True: [f for f in real(strict=False)
                                             if SUPPLY_MARK not in f]
    try:
        rc = run()
    finally:
        st.check_criteria = real
    if rc == 0:
        print("\nMUTATION SURVIVED -- the supply-envelope inequality can be deleted "
              "without turning this suite red. That is the bug.")
        return 1
    failed_on_it = [f for f in FAILED if "supply" in f.lower() or SUPPLY_MARK in f]
    if not failed_on_it:
        print("\nMUTATION CAUGHT, BUT NOT BY THE RIGHT CHECK -- the suite went red for "
              f"another reason: {FAILED}")
        return 1
    print("\nOK  targeted mutation caught: deleting the supply-envelope inequality "
          "turns the retained control red, and it is that control which fails")
    return 0


if __name__ == "__main__":
    if "--mutate-supply" in sys.argv:
        raise SystemExit(mutate_supply())
    if "--mutate" in sys.argv:
        raise SystemExit(mutate())
    raise SystemExit(run())
