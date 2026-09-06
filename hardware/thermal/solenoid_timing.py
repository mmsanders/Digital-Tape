#!/usr/bin/env python3
"""Solenoid protection — sized against the sustained-power limit.

`spec/acceptance.md` DRAFT-3 (PM Decisions 003 §3b) replaces the duty limit with:

    Average coil power <= 0.25 W over any rolling 10 s window, enforced in
    hardware, not defeatable by firmware.

Power rather than duty, because power is what damages a coil. The PM's own note
is the important half: the bound must sit **above the fastest legitimate use** --
a child alternating stop and play about twice a second -- and **below the coil's
continuous rating**. If those do not leave a gap, the answer is a shorter pulse
or a lower-power coil, not a looser limit.

That turns the whole thing into an ENERGY budget, and the energy budget is what
selects the solenoid:

    2 actuations/s sustained x E_pulse <= 0.25 W   ->   E_pulse <= 0.125 J

The previous design here assumed a 9 W coil and a 30 ms pulse -- 0.27 J, which is
2.2x over that budget. That assumption was mine and it does not survive the limit.
So the coil is now specified by energy, and the pulse length comes from WP-04
measuring the shortest pulse that reliably releases the latch, not from assertion.
"""

from __future__ import annotations
import argparse, re, sys
from pathlib import Path

SPEC = Path(__file__).resolve().parents[2] / "spec" / "hw" / "thermal-budget.md"

POWER_LIMIT_W = 0.25          # acceptance.md DRAFT-3, rolling 10 s
POWER_WINDOW_S = 10.0
PULSE_CEILING_MS = 50.0       # single-pulse ceiling, retained from DRAFT-2
LEGIT_RATE_HZ = 2.0           # the fastest legitimate use the PM names
DESIGN_TARGET_W = 0.20        # design to this, not to the limit

# ---------------------------------------------------------------------------
# Timing tolerance. IR-018-13: this was 16 % and it was too small.
#
# The 74HC/HCT221 family's own guaranteed pulse width over -40..85 C spans about
# +/-14 % around nominal (Nexperia 74HCT221 Rev. 4 gives 602..798 us for the
# 100 nF / 10 kOhm example). The old stack allocated only 10 % to the IC before
# adding R and C, so it was tighter than the part it was modelling.
# IR-018-16: this is an ASSUMPTION, not a guarantee, and the difference is the
# whole finding. The 602..798 us figure is specified at CX = 0.1 uF, RX = 10 kOhm,
# VCC = 5 V -- one datasheet test point. It is applied here to a ~390 ms interval
# with a different R/C, on a 3.3 V rail. Neither the R/C nor the voltage is the
# condition the guarantee covers.
#
# Worse: the Nexperia part cited alongside it is a 74HCT221, a 4.5..5.5 V device.
# This board's logic rail is 3.3 V (board-rev-a §1), so that part is excluded
# outright and the HC family's K-factor varies with supply.
#
# So the number stays, marked, and the analysis REFUSES TO CERTIFY on it. See
# TIMING_BOUND_VERIFIED and qualification_gaps().
IC_TOL = 0.14              # ASSUMED. Not yet bound to a part at this rail
R_TOL = 0.01               # 1 % metal film
C_TOL = 0.05               # 5 % film
TIMING_TOL = IC_TOL + R_TOL + C_TOL          # 0.20, arithmetic sum not RSS

# Datasheet limit on the external timing resistor. 1.368 MOhm -- the value the
# previous 450 ms lockout needed -- is OUTSIDE this, so that working point was
# never inside the part's specified envelope. IR-018-13.
R_EXT_MIN_OHM, R_EXT_MAX_OHM = 2e3, 1e6

# The rail the one-shot actually runs on. Bound from board-rev-a §1, and it is
# the term IR-018-16 says was missing: a timing guarantee quoted at 5 V is not a
# guarantee at 3.3 V, and it excludes the HCT variant entirely.
V_LOGIC = 3.3
HCT_MIN_V = 4.5            # 74HCT221 is a 4.5..5.5 V part -> excluded here

# Set to True ONLY when the exact orderable part's guaranteed pulse-width limits,
# at V_LOGIC and over the intended R/C and temperature range, have been read from
# its datasheet. It is False because vendor egress reaches no datasheet (H-02),
# and because IC_TOL above is extrapolated from a test point that does not apply.
TIMING_BOUND_VERIFIED = False
CANDIDATE_PART = "74HC221 (HC, 2..6 V) -- exact orderable variant NOT yet bound"

# Worst-case propagation from a trigger edge to the one-shot's output actually
# asserting. IR-018-17: without this term the model assumed the inhibit was
# continuous across the pulse-to-lockout handoff, and it was not.
PROP_MAX_S = 100e-9

# ---------------------------------------------------------------------------
# Coil power, from the electrical corners rather than a label. IR-018-11.
#
# The acceptance criterion is AVERAGE COIL POWER, and coil power is not a
# constant -- P = V^2 / R, so the boost rail's upper tolerance and the winding's
# lower resistance are the quantities that decide it. The previous model bounded
# only the TIMING corners on an exactly-5.0 W coil, which is a nominal label and
# not a safety maximum.
#
# Copper's resistance FALLS as it cools, so the cold end of the operating range
# is the worst case, not the hot end. That is the counter-intuitive term and it
# is worth about 10 % on its own.
V_BOOST_NOM = 12.0
V_BOOST_TOL = 0.05         # regulated boost output
R_COIL_TOL = 0.10          # winding, as-supplied
ALPHA_CU = 0.00393         # /K, copper
T_COLD_C = 0.0             # cold end of the operating range
T_REF_C = 25.0

# Usability margin held between the slowest possible inhibit and the fastest
# legitimate press, so the bound never suppresses the interaction it is
# specified to sit above. IR-018-12.
USABILITY_MARGIN_MS = 25.0

# ---------------------------------------------------------------------------
# Working point. PULSE_NOM_MS is a PLACEHOLDER until WP-04 measures it, and the
# coil follows FROM it -- see feasible_coil_w(). The previous point (5.0 W,
# 15 ms, 450 ms) FAILS once the electrical corners are included: 0.299 W against
# a 0.25 W limit, where the old model reported 0.220 W and a 1.14x pass.
# TOPOLOGY CHANGED by IR-018-17, and this is what the numbers now mean.
#
# BEFORE: A fired the coil; B was triggered by A's FALLING edge and held the
# lockout; admission was gated on "neither A nor B active". That has a hole. B's
# output only asserts after propagation, so between A releasing and B asserting
# there is a finite window in which a request edge is admitted -- and a firmware
# fault is not phase-constrained, so it can present an edge exactly there. One
# extra pulse inside the nominal lockout invalidates the minimum period that the
# whole 0.25 W proof rests on.
#
# AFTER: B is triggered by the SAME edge that triggers A, and its period spans
# the ENTIRE cycle -- coil pulse plus lockout. Admission is gated on B ALONE.
#
#   request edge --+--> A (non-retriggerable, PULSE_NOM_MS)  --> coil driver
#                  |
#                  +--> B (non-retriggerable, INHIBIT_NOM_MS) --> admission gate
#
#   admit = (not B)      one term, one output, no handoff
#
# There is no A->B handoff to race, because B is already asserted before A ends
# and stays asserted long after. The only remaining window is PROP_MAX_S at the
# very start, before B asserts -- and A is already triggered and NON-retriggerable
# through it, so no second coil pulse can occur in that window either. That is
# the structural argument the finding asks for, and b_covers_a() asserts it.
COIL_W = 3.5               # NOMINAL, at V_BOOST_NOM. Worst case is ~1.36x this
PULSE_NOM_MS = 10.0        # A: coil on-time
INHIBIT_NOM_MS = 390.0     # B: the WHOLE cycle, not the lockout after the pulse
LOCKOUT_NOM_MS = INHIBIT_NOM_MS   # retained name; B now spans the cycle

ENERGY_BUDGET_J = POWER_LIMIT_W / LEGIT_RATE_HZ


def spread(nom): return nom * (1 - TIMING_TOL), nom * (1 + TIMING_TOL)


# ---------------------------------------------------------------------------
# Coil power at the electrical corners -- IR-018-11
# ---------------------------------------------------------------------------

def coil_power_factor(v_tol=V_BOOST_TOL, r_tol=R_COIL_TOL, t_cold=T_COLD_C) -> float:
    """How much more than nominal the coil can actually dissipate.

    P = V^2 / R, so the worst case is the highest rail into the lowest
    resistance, and the lowest resistance is at the COLD end of the operating
    range because copper's resistance falls as it cools. All three terms push
    the same way, which is why the factor is large.
    """
    r_factor = (1.0 - r_tol) * (1.0 + ALPHA_CU * (t_cold - T_REF_C))
    return (1.0 + v_tol) ** 2 / r_factor


def worst_coil_w(nominal_w: float = None) -> float:
    """The number the acceptance criterion is actually about."""
    return (COIL_W if nominal_w is None else nominal_w) * coil_power_factor()


# ---------------------------------------------------------------------------
# Two claims, two opposite corners -- IR-018-12
#
# The old model used min_period_ms() for BOTH "the fault is bounded" and "real
# use is never blocked". Those need opposite corners, and using the fast one for
# the usability claim is how a design can satisfy the safety bound by
# suppressing the very interaction the bound is specified to sit above.
# ---------------------------------------------------------------------------

def min_inhibit_ms(pulse_nom=None, lockout_nom=None) -> float:
    """FAST corner of B. Bounds FAULT POWER -- the most often the hardware can
    possibly fire.

    B spans the whole cycle, so this is B's shortest period and NOT
    `pulse + lockout`. Summing the two was only correct under the old topology,
    and only if the handoff between them were instantaneous, which it is not.
    """
    l = LOCKOUT_NOM_MS if lockout_nom is None else lockout_nom
    return spread(l)[0]


def max_inhibit_ms(pulse_nom=None, lockout_nom=None) -> float:
    """SLOW corner of B. Bounds USABILITY -- the longest a legitimate press can
    be locked out."""
    l = LOCKOUT_NOM_MS if lockout_nom is None else lockout_nom
    return spread(l)[1]


def b_covers_a(pulse_nom=None, lockout_nom=None) -> tuple[bool, float]:
    """IR-018-17, as a checkable inequality.

    B must still be asserted when A releases, at the worst corners in opposite
    directions -- B shortest, A longest -- with propagation on top. If this ever
    goes false, the handoff gap is back and every power number above is void.
    """
    p = PULSE_NOM_MS if pulse_nom is None else pulse_nom
    a_max = spread(p)[1] + PROP_MAX_S * 1000.0
    return min_inhibit_ms(pulse_nom, lockout_nom) >= a_max, a_max


def fault_avg_w(coil_w=None, pulse_nom=None, lockout_nom=None) -> float:
    """Worst case in every axis at once: worst-case coil power, longest pulse,
    shortest lockout, retriggered forever."""
    p = spread(PULSE_NOM_MS if pulse_nom is None else pulse_nom)[1] / 1000.0
    inhibit = min_inhibit_ms(pulse_nom, lockout_nom) / 1000.0
    return worst_coil_w(coil_w) * p / inhibit


def legit_avg_w(coil_w=None, pulse_nom=None, rate_hz=LEGIT_RATE_HZ) -> float:
    p = spread(PULSE_NOM_MS if pulse_nom is None else pulse_nom)[1] / 1000.0
    return worst_coil_w(coil_w) * p * rate_hz


def rolling_window_w(coil_w=None, pulse_nom=None, lockout_nom=None,
                     window_s=POWER_WINDOW_S) -> float:
    """The criterion is a FINITE rolling window, not an asymptotic duty ratio.

    Over 10 s the hardware can fit ceil() actuations, not the fractional number
    the duty ratio implies, so the real bound is very slightly above it. IR-018-11
    asks for this explicitly, and it is the version the acceptance test measures.
    """
    import math
    inhibit = min_inhibit_ms(pulse_nom, lockout_nom) / 1000.0
    p = spread(PULSE_NOM_MS if pulse_nom is None else pulse_nom)[1] / 1000.0
    n = math.floor(window_s / inhibit) + 1        # worst alignment of the window
    return worst_coil_w(coil_w) * min(n * p, window_s) / window_s


def lockout_for_usability_ms(pulse_nom=None) -> float:
    """Largest NOMINAL lockout whose SLOW corner still clears before the fastest
    legitimate press, with USABILITY_MARGIN_MS held back."""
    p = PULSE_NOM_MS if pulse_nom is None else pulse_nom
    budget = 1000.0 / LEGIT_RATE_HZ - USABILITY_MARGIN_MS - spread(p)[1]
    return budget / (1.0 + TIMING_TOL)


def feasible_coil_w(pulse_nom: float) -> float:
    """Largest NOMINAL coil power that still meets the limit at every corner,
    given a pulse length and a lockout sized for usability.

    This is the useful shape of the answer: the pulse is a WP-04 measurement, so
    the design is a boundary rather than a point, and the coil is chosen once
    that measurement lands.
    """
    lock = lockout_for_usability_ms(pulse_nom)
    return POWER_LIMIT_W / rolling_window_w(1.0, pulse_nom, lock)


def timing_resistor_ohm(ms: float, cap_f: float) -> float:
    return (ms / 1000.0) / (0.7 * cap_f)


# ---------------------------------------------------------------------------
# The criteria, as executable assertions -- IR-018-14
# ---------------------------------------------------------------------------

def check_criteria(strict: bool = True):
    """Every PM-owned inequality, evaluated. Returns a list of failures.

    The previous `--check` only asked whether the Markdown matched the
    generator, so an unsafe parameter edit produced an unsafe table, a fresh
    file, and a GREEN gate. That is the same fail-open class this project has
    removed everywhere else, sitting in the one analysis that backs a safety
    limit.
    """
    bad = []
    fault = rolling_window_w()
    legit = legit_avg_w()
    if fault > POWER_LIMIT_W:
        bad.append(f"fault-case average coil power {fault:.3f} W exceeds "
                   f"{POWER_LIMIT_W:.2f} W over a rolling {POWER_WINDOW_S:.0f} s window")
    if legit > POWER_LIMIT_W:
        bad.append(f"legitimate-use average {legit:.3f} W exceeds {POWER_LIMIT_W:.2f} W")
    if spread(PULSE_NOM_MS)[1] > PULSE_CEILING_MS:
        bad.append(f"longest pulse {spread(PULSE_NOM_MS)[1]:.1f} ms exceeds the "
                   f"{PULSE_CEILING_MS:.0f} ms single-pulse ceiling")
    covers, a_max = b_covers_a()
    if not covers:
        bad.append(f"the inhibit ({min_inhibit_ms():.1f} ms at its shortest) does not outlast "
                   f"the coil pulse ({a_max:.3f} ms incl. propagation) -- there is a handoff "
                   "gap in which a request edge can be admitted")
    slowest = max_inhibit_ms()
    period = 1000.0 / LEGIT_RATE_HZ
    if slowest > period:
        bad.append(f"slowest inhibit {slowest:.1f} ms exceeds the {period:.0f} ms period of "
                   f"{LEGIT_RATE_HZ:.0f} Hz use -- the bound would block a legitimate press")
    for name, ms, cap in (("pulse", PULSE_NOM_MS, 100e-9),
                          ("lockout", LOCKOUT_NOM_MS, 1e-6)):
        r = timing_resistor_ohm(ms, cap)
        if not (R_EXT_MIN_OHM <= r <= R_EXT_MAX_OHM):
            bad.append(f"{name} timing resistor {r/1000:.0f} kOhm is outside the part's "
                       f"specified {R_EXT_MIN_OHM/1000:.0f}..{R_EXT_MAX_OHM/1000:.0f} kOhm range")
    if V_LOGIC >= HCT_MIN_V:
        bad.append(f"logic rail {V_LOGIC} V is in the HCT range; re-check the part family")
    if strict and bad:
        for line in bad:
            print(f"  SOLENOID: {line}", file=sys.stderr)
    return bad


def t_solenoid_values() -> str:
    t_lo, t_hi = spread(PULSE_NOM_MS)
    l_lo, l_hi = spread(LOCKOUT_NOM_MS)
    kf = coil_power_factor()
    pw = worst_coil_w()
    fault = rolling_window_w()
    legit = legit_avg_w()
    r_pulse = timing_resistor_ohm(PULSE_NOM_MS, 100e-9)
    r_lock = timing_resistor_ohm(LOCKOUT_NOM_MS, 1e-6)
    e = pw * t_hi / 1000.0
    period = 1000.0 / LEGIT_RATE_HZ
    return "\n".join([
        f"> **VERDICT: {verdict()}.** The inequalities below hold at the assumed corners. "
        "**One corner is not yet bound to a real part** (IR-018-16), so this is not a PASS "
        "and the document does not claim one. See *What is still open*.",
        "",
        "> **Reworked twice after independent review — IR-018-11…15, then IR-018-16…17.** The "
        "original working point (5.0 W, 15 ms, 450 ms) **fails** once the electrical corners "
        "are included: **0.330 W against 0.25 W**, where the first model reported 0.220 W and "
        "a 1.14× pass. The second review then found the pulse-to-lockout handoff could be "
        "raced. **The response remains open and I do not accept it.**",
        "",
        "### The coil is bounded by its corners, not by its label",
        "",
        "The criterion is *average coil power*, and coil power is not a constant: "
        "`P = V²/R`. So the rail's upper tolerance and the winding's lower resistance are the "
        "quantities that decide it — and the lowest resistance is at the **cold** end of the "
        "range, because copper's resistance falls as it cools. All three push the same way.",
        "",
        "| Corner | Value | Effect on power |",
        "|---|---:|---:|",
        f"| Boost rail | {V_BOOST_NOM:.0f} V +{V_BOOST_TOL*100:.0f} % | ×{(1+V_BOOST_TOL)**2:.3f} |",
        f"| Coil resistance | −{R_COIL_TOL*100:.0f} % as supplied | ×{1/(1-R_COIL_TOL):.3f} |",
        f"| Copper at {T_COLD_C:.0f} °C | −{ALPHA_CU*(T_REF_C-T_COLD_C)*100:.1f} % vs {T_REF_C:.0f} °C | "
        f"×{1/(1+ALPHA_CU*(T_COLD_C-T_REF_C)):.3f} |",
        f"| **Combined** | | **×{kf:.3f}** |",
        "",
        f"So a **{COIL_W:.1f} W** nominal coil is a **{pw:.2f} W** coil for the purposes of this "
        f"limit. **That factor, not the nominal, is what the old margin was missing** — and at "
        f"{kf:.2f}× it is larger than the 1.14× margin the previous analysis claimed.",
        "",
        "### Working point",
        "",
        "| Quantity | Value | Against | Verdict |",
        "|---|---:|---|---|",
        f"| Coil, **nominal** | {COIL_W:.1f} W at {V_BOOST_NOM:.0f} V | | selection |",
        f"| Coil, **worst case** | **{pw:.2f} W** | the number the limit is about | |",
        f"| Pulse (**placeholder — WP-04 measures this**) | {PULSE_NOM_MS:.0f} ms nominal, "
        f"{t_lo:.1f}…**{t_hi:.1f} ms** | ≤ {PULSE_CEILING_MS:.0f} ms | "
        f"**pass**, {PULSE_CEILING_MS/t_hi:.1f}× |",
        f"| Energy per actuation, worst case | **{e*1000:.0f} mJ** | ≤ {ENERGY_BUDGET_J*1000:.0f} mJ | "
        f"**pass**, {ENERGY_BUDGET_J/e:.2f}× |",
        f"| **Inhibit (B)** | {LOCKOUT_NOM_MS:.0f} ms nominal, {l_lo:.0f}…{l_hi:.0f} ms | "
        f"spans the WHOLE cycle, not the tail | see topology |",
        f"| **Fastest** the hardware can fire | one per **{min_inhibit_ms():.0f} ms** | "
        f"bounds fault power | |",
        f"| **Slowest** a press can be locked out | **{max_inhibit_ms():.0f} ms** | "
        f"must be < {period:.0f} ms so real use is never blocked | "
        f"**pass**, {period-max_inhibit_ms():.0f} ms spare |",
        f"| Average at {LEGIT_RATE_HZ:.0f} Hz legitimate use | **{legit:.3f} W** | "
        f"≤ {POWER_LIMIT_W:.2f} W | **pass**, {POWER_LIMIT_W/legit:.1f}× |",
        f"| Average in a retrigger fault, rolling {POWER_WINDOW_S:.0f} s | **{fault:.3f} W** | "
        f"≤ {POWER_LIMIT_W:.2f} W | **pass**, {POWER_LIMIT_W/fault:.2f}× |",
        "",
        f"Timing tolerance **±{TIMING_TOL*100:.0f} %**, arithmetic sum not RSS: "
        f"±{IC_TOL*100:.0f} % for the one-shot itself (its *guaranteed* spread over "
        f"temperature, not a typical), ±{R_TOL*100:.0f} % resistor, ±{C_TOL*100:.0f} % "
        f"capacitor. The previous stack allocated only 10 % to the IC and was therefore "
        "tighter than the part it was modelling.",
        "",
        "### The topology, and why the handoff cannot be raced",
        "",
        "**This changed after IR-018-17.** The previous arrangement fired the coil from A and "
        "triggered B from **A's falling edge**, gating admission on *neither A nor B active*. "
        "B's output only asserts after propagation, so between A releasing and B asserting "
        "there is a finite window in which a request edge is admitted — and a firmware fault "
        "is not phase-constrained, so it can present an edge exactly there. **One extra pulse "
        "inside the lockout invalidates the minimum period the whole 0.25 W proof rests on.**",
        "",
        "So B is now triggered by the **same edge that triggers A**, and its period spans the "
        "**entire cycle** rather than the tail after the pulse. Admission is gated on **B "
        "alone**:",
        "",
        "```",
        "request edge --+--> A (non-retriggerable, pulse)    --> coil driver",
        "               |",
        "               +--> B (non-retriggerable, inhibit)  --> admission gate",
        "",
        "admit = NOT B          one term, one output, no handoff",
        "```",
        "",
        f"There is no A→B handoff to race: **B is asserted before A ends** "
        f"({min_inhibit_ms():.0f} ms at its shortest against a "
        f"{spread(PULSE_NOM_MS)[1] + PROP_MAX_S*1000:.2f} ms pulse including propagation) and "
        "stays asserted long after. The only remaining window is the propagation delay at the "
        "very start, before B asserts — and **A is already triggered and non-retriggerable "
        "through it**, so no second coil pulse can occur there either.",
        "",
        "That is a structural argument, not a statistical one, and it is checked: "
        "`b_covers_a()` asserts the inequality at opposite corners with propagation included, "
        "and `test_solenoid.py` has a red case that fails when the inhibit does not outlast "
        "the pulse — which is exactly the old topology.",
        "",
        "### The part, and the rail",
        "",
        f"**Candidate: {CANDIDATE_PART}.** A half sets the pulse "
        f"(R = {timing_resistor_ohm(PULSE_NOM_MS, 100e-9)/1000:.0f} kΩ, C = 100 nF **C0G**); "
        f"B half sets the inhibit "
        f"(R = {timing_resistor_ohm(LOCKOUT_NOM_MS, 1e-6)/1000:.0f} kΩ, C = 1 µF **film**). "
        "Both resistors are inside the family's specified "
        f"{R_EXT_MIN_OHM/1000:.0f}…{R_EXT_MAX_OHM/1000:.0f} kΩ range; the original 450 ms "
        "lockout on 470 nF needed **1368 kΩ** and was not.",
        "",
        f"**The logic rail is {V_LOGIC} V** (`board-rev-a` §1), and that is a binding "
        f"constraint IR-018-16 was right to demand. It **excludes the 74HCT221 outright** — "
        f"that part is {HCT_MIN_V}…5.5 V — and it means the HC family's supply-dependent "
        "K-factor applies. Any timing figure quoted at 5 V is not a figure for this circuit.",
        "",
        "**74HC221 devices are non-retriggerable**, and the design depends on it: it is what "
        "makes the propagation window at the start harmless.",
        "",
    ])


def t_solenoid_test() -> str:
    period = 1000.0 / LEGIT_RATE_HZ
    rows = [
        "The limit only means something if it clears real use and still bounds a fault. "
        "**Those are two different claims and they need opposite timing corners** — using one "
        "corner for both is how a design satisfies a safety bound by suppressing the exact "
        "interaction the bound was specified to sit above.",
        "",
        "| Claim | Corner used | Value | Against |",
        "|---|---|---:|---|",
        f"| A fault is bounded | **fastest**: longest pulse, *shortest* lockout | "
        f"one per {min_inhibit_ms():.0f} ms | {rolling_window_w():.3f} W ≤ {POWER_LIMIT_W:.2f} W |",
        f"| Real use is never blocked | **slowest**: longest pulse, *longest* lockout | "
        f"{max_inhibit_ms():.0f} ms | < {period:.0f} ms |",
        "",
        f"**The previous version checked the fast corner for both**, and reported "
        f"395 ms against the {period:.0f} ms period. At the slow corner the same design held "
        f"the inhibit for **539 ms** — so a legitimate press arriving {period:.0f} ms after the "
        "last one would have been silently dropped. IR-018-12.",
        "",
        "| Case | Rate | Average coil power | Against 0.25 W |",
        "|---|---|---:|---|",
    ]
    for label, hz in (("One press", 0.2), ("Brisk use", 1.0),
                      ("**Child mashing stop/play**", LEGIT_RATE_HZ),
                      ("Firmware retrigger loop, 100 Hz input",
                       1000.0 / min_inhibit_ms())):
        w = legit_avg_w(rate_hz=hz)
        rows.append(f"| {label} | {hz:.1f} /s | **{w:.3f} W** | "
                    f"{'**pass**' if w <= POWER_LIMIT_W else '❌ **FAIL**'} |")
    rows += [
        "",
        f"The last row is the fault case: a 100 Hz gate input is throttled by the lockout to "
        f"one pulse per {min_inhibit_ms():.0f} ms whatever firmware does. It is evaluated over "
        f"a **finite rolling {POWER_WINDOW_S:.0f} s window** rather than as an asymptotic duty "
        f"ratio — {rolling_window_w():.3f} W against {fault_avg_w():.3f} W — because the "
        "criterion is a window and a window can align worse than the ratio implies.",
        "",
        "### The design is a boundary, not a point",
        "",
        "**The pulse is a WP-04 measurement and the coil follows from it.** So the useful shape "
        "of the answer is the feasibility curve: for each pulse length, the largest nominal "
        "coil that still passes every corner with the lockout sized for usability.",
        "",
        "| Pulse, nominal | Lockout, nominal | Slowest inhibit | Largest **nominal** coil |",
        "|---:|---:|---:|---:|",
    ]
    for pn in (8.0, 10.0, 12.0, 15.0, 20.0):
        lock = lockout_for_usability_ms(pn)
        mark = " ← **committed**" if abs(pn - PULSE_NOM_MS) < 1e-9 else ""
        rows.append(f"| {pn:.0f} ms | {lock:.0f} ms | {max_inhibit_ms(pn, lock):.0f} ms | "
                    f"**{feasible_coil_w(pn):.2f} W**{mark} |")
    rows += [
        "",
        f"At the placeholder 15 ms the ceiling is **{feasible_coil_w(15.0):.2f} W**, so the "
        "old 5 W coil was never compliant at that pulse. The committed point takes a shorter "
        f"pulse instead, which buys back the coil: **{COIL_W:.1f} W at "
        f"{PULSE_NOM_MS:.0f} ms**, inside the "
        f"{feasible_coil_w(PULSE_NOM_MS):.2f} W ceiling with "
        f"{POWER_LIMIT_W/rolling_window_w():.2f}× on the power limit.",
        "",
        "**The dominant term is the tolerance stack, not the nominal.** Specifying the rail to "
        "±2 % and the winding to ±5 % would drop the corner factor from "
        f"{coil_power_factor():.2f}× to {coil_power_factor(0.02, 0.05):.2f}×, which buys more "
        "headroom than any plausible change to the coil. **That is the cheapest lever and it is "
        "a procurement decision, not a circuit one.**",
        "",
        "### What is still open",
        "",
        "**This is a PROVISIONAL result and the reasons are listed, not buried.**",
        "",
    ] + [f"- {g}" for g in qualification_gaps()] + [
        f"- **The pulse length is a placeholder.** WP-04 measures the shortest pulse that "
        f"reliably releases the latch. If it comes back above ~{PULSE_NOM_MS:.0f} ms the "
        "feasibility table says what the coil must drop to — and if the mechanism then needs "
        "more energy than the budget allows, that is a genuine conflict between a safety limit "
        "and a mechanism, and it goes to the PM rather than being absorbed by widening the "
        "limit.",
        "- **Vendor egress reaches no datasheet** (H-02), so binding the one-shot's guaranteed "
        "timing at this rail is blocked on either the egress gap or a bench measurement of the "
        "chosen part. **A measurement is the honest route** and does not wait on anyone: it "
        "belongs with WP-04's pulse measurement, on the same bench, on the same day.",
        "",
        "**The response to the IR-015 solenoid finding is not closed, and I do not get to close "
        "it.** Two reviews have now found real defects in it — one physical, one structural — "
        "and the disposition after each was the same.",
    ]
    return "\n".join(rows)


def qualification_gaps() -> list[str]:
    """What is NOT established, kept separate from what is.

    IR-018-16. The inequalities in check_criteria() hold *at the assumed timing
    corners*. Whether those corners are the real ones is a different question,
    and answering it needs a datasheet this environment cannot fetch (H-02).
    Collapsing the two into one PASS is how an assumption becomes a claim, so
    they are reported separately and the document's verdict is PROVISIONAL.
    """
    gaps = []
    if not TIMING_BOUND_VERIFIED:
        gaps.append(
            f"the ±{IC_TOL*100:.0f} % one-shot timing term is ASSUMED, not guaranteed: it is "
            f"extrapolated from a 700 µs datasheet test point at VCC = 5 V and applied to a "
            f"{LOCKOUT_NOM_MS:.0f} ms interval at {V_LOGIC} V with a different R/C. "
            f"Part still unbound ({CANDIDATE_PART})")
    return gaps


def verdict() -> str:
    """PASS is not available while a corner the proof rests on is unbound."""
    if check_criteria(strict=False):
        return "FAIL"
    return "PROVISIONAL" if qualification_gaps() else "PASS"


BLOCKS = {"solenoid_values": t_solenoid_values, "solenoid_test": t_solenoid_test}


def render(text):
    for name, fn in BLOCKS.items():
        pat = re.compile(rf"(<!-- BEGIN GENERATED: {name} -->\n).*?(\n<!-- END GENERATED: {name} -->)", re.DOTALL)
        if not pat.search(text):
            sys.exit(f"solenoid_timing.py: no marker block for '{name}'")
        text = pat.sub(lambda m: m.group(1) + fn() + m.group(2), text)
    return text


def _show_stale(current: str, updated: str, who: str) -> None:
    """Print WHAT is stale, not just that something is.

    A gate that says "STALE" and nothing else costs a full round-trip to
    diagnose -- which is exactly what happened when a one-milliwatt rounding
    difference between Python 3.11 and 3.12 turned this check red in CI and
    green on the author's machine. The diff would have said so immediately.
    """
    import difflib
    print(f"{who}: the committed document does not match the generator:",
          file=sys.stderr)
    diff = difflib.unified_diff(current.splitlines(), updated.splitlines(),
                                fromfile="committed", tofile="generated",
                                lineterm="", n=1)
    for i, line in enumerate(diff):
        if i > 60:
            print("  ... (truncated)", file=sys.stderr)
            break
        print(f"  {line}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()

    if a.report:
        print(t_solenoid_values(), "\n")
        print(t_solenoid_test())
        return 0

    # IR-018-14: the SAFETY verdict comes first and is independent of whether
    # the document happens to be fresh. The old --check asked only about
    # freshness, so an unsafe edit produced an unsafe table, a fresh file and a
    # green gate.
    bad = check_criteria()
    if bad:
        print(f"solenoid criteria FAIL ({len(bad)})", file=sys.stderr)
        return 1

    cur = SPEC.read_text()
    new_text = render(cur)
    if a.check:
        if cur != new_text:
            _show_stale(cur, new_text, 'solenoid_timing.py')
            print("solenoid tables STALE", file=sys.stderr)
            return 1
        print("solenoid criteria pass, tables up to date")
        return 0
    if cur != new_text:
        SPEC.write_text(new_text)
        print("regenerated solenoid tables")
    else:
        print("solenoid tables already up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
