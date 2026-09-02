#!/usr/bin/env python3
"""Solenoid protection timing — closes the PR #15 solenoid finding.

`spec/acceptance.md` sets two limits:
  * single pulse <= 50 ms regardless of gate input
  * coil duty <= 5 % over any rolling 1 s window, enforced in hardware

PM Decisions 002-A section 2 upholds the reviewers' objection: the PPTC is
history-dependent, so it is a third layer and NOT the thing that meets the duty
limit. The one-shot and the RC lockout must meet it deterministically on their
own, with worst-case tolerance analysis. This computes that.

Topology, in order of who does what:
  1. 74HC221 non-retriggerable monostable  -> bounds a single pulse
  2. RC lockout on the trigger             -> bounds minimum off-time
  3. PPTC on the coil rail                 -> third layer, catches what 1+2 miss
"""

from __future__ import annotations
import argparse, re, sys
from pathlib import Path

SPEC = Path(__file__).resolve().parents[2] / "spec" / "hw" / "thermal-budget.md"

PULSE_LIMIT_MS = 50.0      # acceptance.md, single pulse
DUTY_LIMIT = 0.05          # acceptance.md, rolling 1 s
DUTY_WINDOW_S = 1.0
TEST_SETTLE_S = 2.0        # acceptance.md verification: settle within 2 s

# 74HC221: tW = 0.7 * Rext * Cext. Spread is dominated by the capacitor and by
# the IC's own formula constant, not by the resistor.
R_TOL = 0.01               # 1 % resistor
C_TOL = 0.05               # C0G/NP0, 5 % -- deliberately not X7R, see the note
IC_TOL = 0.10              # 74HC221 timing constant spread over temperature
TIMING_TOL = R_TOL + C_TOL + IC_TOL      # worst case, added not RSS

PULSE_NOM_MS = 30.0        # what the mechanism is expected to need (WP-04 confirms)
LOCKOUT_NOM_MS = 1200.0

COIL_W = 9.0               # from budget.py: 9 V into 9 ohm


def spread(nom: float) -> tuple[float, float]:
    return nom * (1 - TIMING_TOL), nom * (1 + TIMING_TOL)


def worst_duty(pulse_nom: float, lockout_nom: float) -> float:
    """Worst case: longest possible pulse, shortest possible lockout."""
    p_max = spread(pulse_nom)[1]
    l_min = spread(lockout_nom)[0]
    return p_max / (p_max + l_min)


def min_lockout_for(pulse_nom: float, duty: float = DUTY_LIMIT) -> float:
    """Smallest nominal lockout whose worst case still meets the duty limit."""
    p_max = spread(pulse_nom)[1]
    l_min_needed = p_max * (1 - duty) / duty
    return l_min_needed / (1 - TIMING_TOL)


def t_solenoid_values() -> str:
    p_lo, p_hi = spread(PULSE_NOM_MS)
    l_lo, l_hi = spread(LOCKOUT_NOM_MS)
    d = worst_duty(PULSE_NOM_MS, LOCKOUT_NOM_MS)
    need = min_lockout_for(PULSE_NOM_MS)
    # Pick real parts: tW = 0.7*R*C
    # tW = 0.7 * R * C. Pick the capacitor first from what is actually stable and
    # buyable in the value needed, then let R fall out.
    c1_nf = 100.0                    # C0G, 0805 -- the top of practical C0G values
    r1 = PULSE_NOM_MS / 1000.0 / (0.7 * c1_nf * 1e-9)
    c2_nf = 1000.0                   # 1 uF FILM (PPS/polyester), not C0G -- see note
    r2 = LOCKOUT_NOM_MS / 1000.0 / (0.7 * c2_nf * 1e-9)
    return "\n".join([
        "| Element | Part | Nominal | Worst case | Against |",
        "|---|---|---:|---|---|",
        f"| One-shot pulse | `74HC221` A-half, R = {r1/1000:.0f} kΩ 1 %, C = {c1_nf:.0f} nF **C0G** | "
        f"{PULSE_NOM_MS:.0f} ms | {p_lo:.1f} … **{p_hi:.1f} ms** | "
        f"≤ {PULSE_LIMIT_MS:.0f} ms — **pass**, {PULSE_LIMIT_MS/p_hi:.2f}× margin |",
        f"| Lockout | `74HC221` B-half, R = {r2/1e6:.2f} MΩ 1 %, C = {c2_nf/1000:.0f} µF **film** | "
        f"{LOCKOUT_NOM_MS:.0f} ms | **{l_lo:.0f}** … {l_hi:.0f} ms | "
        f"≥ {need:.0f} ms needed — **pass** |",
        f"| **Resulting duty** | worst pulse over shortest lockout | "
        f"{PULSE_NOM_MS/(PULSE_NOM_MS+LOCKOUT_NOM_MS)*100:.1f} % | **{d*100:.2f} %** | "
        f"≤ {DUTY_LIMIT*100:.0f} % — **pass**, {DUTY_LIMIT/d:.2f}× margin |",
        f"| Coil average at that duty | | | **{COIL_W*d:.2f} W** | "
        f"vs {COIL_W:.0f} W energised |",
        "",
        f"Timing tolerance is **±{TIMING_TOL*100:.0f} %**, taken as the arithmetic sum of "
        f"resistor ±{R_TOL*100:.0f} %, capacitor ±{C_TOL*100:.0f} % and the `74HC221` timing "
        f"constant ±{IC_TOL*100:.0f} % over temperature — not RSS, because these are not "
        f"independent random variables on one board.",
        "",
        "**Neither timing capacitor is X7R, and that is load-bearing.** X7R loses a large "
        "fraction of its capacitance under DC bias and over temperature, so a timing network "
        "built on one does not have a ±5 % tolerance — it has an unbounded one. Here that would "
        "widen the pulse and shorten the lockout, both in the unsafe direction, and it would "
        "pass every bench test at room temperature.",
        "",
        "**The two halves live in one `74HC221`.** The package is a dual monostable: the A half "
        "sets the pulse, the B half is retriggered by A's falling edge and holds the lockout. "
        "One part, one footprint, and the lockout cannot be defeated by any gate input because "
        "it is downstream of the pulse rather than in front of it.",
        "",
        "**Why the lockout capacitor is film and not C0G.** 1 µF C0G does not exist in a "
        "practical package — C0G runs out around 100 nF at these sizes. Holding 1.2 s with "
        "100 nF would need a 17 MΩ timing resistor, beyond the part's usable range and badly "
        "leakage-sensitive. A 1 µF PPS or polyester film capacitor is stable, buyable in 1206, "
        "and brings the resistor back to a sane 1.71 MΩ. This is the kind of substitution that "
        "gets made silently at assembly time, so it is written down here as a requirement.",
    ])


def t_solenoid_test() -> str:
    p_hi = spread(PULSE_NOM_MS)[1]
    l_lo = spread(LOCKOUT_NOM_MS)[0]
    period = (p_hi + l_lo) / 1000.0
    pulses = int(TEST_SETTLE_S / period) + 1
    duty_2s = pulses * p_hi / 1000.0 / TEST_SETTLE_S
    return "\n".join([
        "The acceptance test drives the gate with a continuous 100 Hz square wave and requires "
        "average coil current to fall to ≤ 5 % of the energised value within 2 s and stay there.",
        "",
        "| Quantity | Worst case |",
        "|---|---:|",
        f"| Gate input | 100 Hz continuous, 50 % duty — 100 rising edges per second |",
        f"| Pulses the hardware actually allows | {pulses} in {TEST_SETTLE_S:.0f} s |",
        f"| Coil on-time in that window | {pulses * p_hi:.0f} ms |",
        f"| **Average coil duty over 2 s** | **{duty_2s*100:.2f} %** |",
        f"| Limit | ≤ {DUTY_LIMIT*100:.0f} % |",
        "",
        "**This is the retrigger loop the one-shot alone does not cover.** A non-retriggerable "
        "monostable ignores edges while its output is high, but it accepts the very next edge "
        "afterwards — at 100 Hz that is 10 ms later, giving roughly 75 % duty and a coil that "
        "cooks while every part behaves exactly as specified. The lockout is what turns 100 "
        "edges per second into one pulse per 1.2 s, and it does so with an RC, so no firmware "
        "state can shorten it.",
    ])


BLOCKS = {"solenoid_values": t_solenoid_values, "solenoid_test": t_solenoid_test}


def render(text: str) -> str:
    for name, fn in BLOCKS.items():
        pat = re.compile(rf"(<!-- BEGIN GENERATED: {name} -->\n).*?(\n<!-- END GENERATED: {name} -->)", re.DOTALL)
        if not pat.search(text):
            sys.exit(f"solenoid_timing.py: no marker block for '{name}'")
        text = pat.sub(lambda m: m.group(1) + fn() + m.group(2), text)
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.report:
        print(t_solenoid_values(), "\n"); print(t_solenoid_test()); return 0
    cur = SPEC.read_text(); new = render(cur)
    if a.check:
        if cur != new:
            print("solenoid tables STALE", file=sys.stderr); return 1
        print("solenoid tables up to date"); return 0
    if cur != new:
        SPEC.write_text(new); print("regenerated solenoid tables")
    else:
        print("solenoid tables already up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
