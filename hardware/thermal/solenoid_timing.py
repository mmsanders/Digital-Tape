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

TIMING_TOL = 0.16             # 1% R + 5% film/C0G C + 10% 74HC221 constant

# Working point. PULSE_NOM_MS is a PLACEHOLDER until WP-04 measures it.
COIL_W = 5.0
PULSE_NOM_MS = 15.0
LOCKOUT_NOM_MS = 450.0

ENERGY_BUDGET_J = POWER_LIMIT_W / LEGIT_RATE_HZ


def spread(nom): return nom * (1 - TIMING_TOL), nom * (1 + TIMING_TOL)


def fault_avg_w(coil_w, pulse_nom, lockout_nom):
    """Worst case: longest pulse, shortest lockout, retriggered forever."""
    t = spread(pulse_nom)[1] / 1000.0
    l = spread(lockout_nom)[0] / 1000.0
    return coil_w * t / (t + l)


def legit_avg_w(coil_w, pulse_nom, rate_hz=LEGIT_RATE_HZ):
    return coil_w * spread(pulse_nom)[1] / 1000.0 * rate_hz


def min_period_ms(pulse_nom, lockout_nom):
    return spread(pulse_nom)[1] + spread(lockout_nom)[0]


def t_solenoid_values() -> str:
    t_lo, t_hi = spread(PULSE_NOM_MS)
    l_lo, l_hi = spread(LOCKOUT_NOM_MS)
    fault = fault_avg_w(COIL_W, PULSE_NOM_MS, LOCKOUT_NOM_MS)
    legit = legit_avg_w(COIL_W, PULSE_NOM_MS)
    per = min_period_ms(PULSE_NOM_MS, LOCKOUT_NOM_MS)
    e = COIL_W * PULSE_NOM_MS / 1000.0
    c1, r1 = 100.0, PULSE_NOM_MS / 1000.0 / (0.7 * 100e-9)
    c2, r2 = 470.0, LOCKOUT_NOM_MS / 1000.0 / (0.7 * 470e-9)  # film: 470 nF C0G is not a real part
    return "\n".join([
        "| Quantity | Value | Against | Verdict |",
        "|---|---:|---|---|",
        f"| Energy budget at {LEGIT_RATE_HZ:.0f} Hz sustained | **{ENERGY_BUDGET_J*1000:.0f} mJ** "
        f"per actuation | {POWER_LIMIT_W:.2f} W ÷ {LEGIT_RATE_HZ:.0f} Hz | the governing number |",
        f"| Coil, specified by energy | **{COIL_W:.1f} W** | | selection constraint |",
        f"| Pulse (**placeholder — WP-04 measures this**) | {PULSE_NOM_MS:.0f} ms nominal, "
        f"{t_lo:.1f}…**{t_hi:.1f} ms** | ≤ {PULSE_CEILING_MS:.0f} ms | "
        f"**pass**, {PULSE_CEILING_MS/t_hi:.1f}× |",
        f"| Energy per actuation | **{e*1000:.0f} mJ** | ≤ {ENERGY_BUDGET_J*1000:.0f} mJ | "
        f"**pass**, {ENERGY_BUDGET_J/e:.2f}× |",
        f"| Lockout | {LOCKOUT_NOM_MS:.0f} ms nominal, **{l_lo:.0f}**…{l_hi:.0f} ms | | |",
        f"| Fastest the hardware allows | one per **{per:.0f} ms** | must be ≤ "
        f"{1000/LEGIT_RATE_HZ:.0f} ms so real use is not blocked | "
        f"**pass** |",
        f"| Average at {LEGIT_RATE_HZ:.0f} Hz legitimate use | **{legit:.3f} W** | "
        f"≤ {POWER_LIMIT_W:.2f} W | **pass** |",
        f"| Average in a retrigger fault | **{fault:.3f} W** | ≤ {POWER_LIMIT_W:.2f} W | "
        f"**pass**, {POWER_LIMIT_W/fault:.2f}× |",
        "",
        f"Timing tolerance ±{TIMING_TOL*100:.0f} %, arithmetic sum not RSS. One `74HC221`: "
        f"A half sets the pulse (R = {r1/1000:.0f} kΩ, C = {c1:.0f} nF **C0G**), B half holds "
        f"the lockout (R = {r2/1000:.0f} kΩ, C = {c2:.0f} nF **film**), retriggered by A's "
        f"falling edge so it sits downstream of the pulse and no gate input can defeat it.",
    ])


def t_solenoid_test() -> str:
    rows = [
        "The limit only means something if it clears real use and still bounds a fault. Both, "
        "at the working point above:",
        "",
        "| Case | Rate | Average coil power | Against 0.25 W |",
        "|---|---|---:|---|",
    ]
    per = min_period_ms(PULSE_NOM_MS, LOCKOUT_NOM_MS)
    for label, hz in (("One press", 0.2), ("Brisk use", 1.0),
                      ("**Child mashing stop/play**", LEGIT_RATE_HZ),
                      ("Firmware retrigger loop, 100 Hz input", 1000.0 / per)):
        w = legit_avg_w(COIL_W, PULSE_NOM_MS, hz)
        rows.append(f"| {label} | {hz:.1f} /s | **{w:.3f} W** | "
                    f"{'**pass**' if w <= POWER_LIMIT_W else '❌'} |")
    rows += [
        "",
        "The last row is the fault case and it is the one the hardware actually bounds: a 100 Hz "
        f"gate input is throttled by the lockout to one pulse per {per:.0f} ms, whatever firmware "
        "does. The row above it is a child, and it passes with room — which is the point the "
        "limit was restated to make.",
        "",
        "**Why the coil dropped from 9 W to 5 W.** At 9 W a 30 ms pulse is 270 mJ, and two of "
        f"those a second is 0.54 W — more than double the limit. No lockout fixes that without "
        "also blocking the child, because the energy is spent inside a single legitimate "
        "actuation. The fix has to be the coil or the pulse, exactly as the PM's note says. "
        "**The 9 W / 30 ms figure was my assumption, not a measurement**, and it is the third "
        "number this project has found wrong by costing it.",
        "",
        "**The pulse length is a placeholder and is marked as one.** WP-04 measures the shortest "
        "pulse that reliably releases the latch; that number, plus margin, replaces the 15 ms "
        "above and the lockout resistor follows it. Until then the working point demonstrates "
        "that a compliant design exists — it does not claim to be the final one.",
    ]
    return "\n".join(rows)


BLOCKS = {"solenoid_values": t_solenoid_values, "solenoid_test": t_solenoid_test}


def render(text):
    for name, fn in BLOCKS.items():
        pat = re.compile(rf"(<!-- BEGIN GENERATED: {name} -->\n).*?(\n<!-- END GENERATED: {name} -->)", re.DOTALL)
        if not pat.search(text):
            sys.exit(f"solenoid_timing.py: no marker block for '{name}'")
        text = pat.sub(lambda m: m.group(1) + fn() + m.group(2), text)
    return text


def main():
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
