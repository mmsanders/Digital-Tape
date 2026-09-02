#!/usr/bin/env python3
"""Thermal and power budget for the Digital Tape production board.

The budget is computed, not asserted. Edit the numbers here; the tables in
`spec/hw/thermal-budget.md` are regenerated from them.

    make -C hardware thermal        regenerate the tables in the spec
    make -C hardware thermal-check  fail if the spec is stale (CI gate)

Every input carries a source tag. `EST` is an engineering estimate that WP-37
replaces with a measurement. `DS` is a datasheet figure. `UNVERIFIED` means the
datasheet could not be read from this environment -- see STATUS-HARDWARE.md H-02.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

SPEC = Path(__file__).resolve().parents[2] / "spec" / "hw" / "thermal-budget.md"

# --------------------------------------------------------------------------
# Enclosure and environment
# --------------------------------------------------------------------------

ENCLOSURE_MM = (110.0, 75.0, 28.0)   # Hardware Charter section 04
H_COMBINED = 9.0                     # W/m^2K, free convection + radiation, small
                                     # plastic box in still air. EST, +/-30%.
H_INTERNAL = 22.0                    # W/m^2K, board -> internal air -> case in a
                                     # SEALED volume. EST, the weakest number here.
BOARD_AREA_M2 = 0.0090               # ~90 x 50 mm, both faces. EST.
THERMAL_MASS_J_PER_K = 150.0         # ~150 g of plastic, board, cell. EST.
AMBIENT_NOMINAL_C = 25.0
AMBIENT_WARM_C = 30.0
AMBIENT_HOT_C = 35.0                 # a warm room, a sunny windowsill

# --------------------------------------------------------------------------
# Loads
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Load:
    name: str
    rail: str
    volts: float
    amps_idle: float      # asleep / waiting
    amps_play: float      # one card streaming, audio out
    amps_copy: float      # both cards at UHS-I, the electrical worst case
    source: str
    note: str = ""

    def watts(self, mode: str) -> float:
        return self.volts * getattr(self, f"amps_{mode}")


LOADS: list[Load] = [
    Load("i.MX RT1062 @ 600 MHz", "+3V3", 3.3, 0.006, 0.110, 0.180, "EST",
         "Both USDHC controllers active during copy. Core DCDC is internal."),
    Load("PSRAM (APS6404L QSPI)", "+3V3", 3.3, 0.000, 0.015, 0.030, "EST/UNVERIFIED"),
    Load("QSPI flash", "+3V3", 3.3, 0.000, 0.008, 0.015, "EST/UNVERIFIED"),
    Load("SGTL5000 + headphone amp", "+3V3A", 3.3, 0.000, 0.035, 0.005, "EST",
         "Audio is muted during a copy, so the copy column is quiescent only."),
    Load("microSD, source slot", "+3V3", 3.3, 0.000, 0.045, 0.200, "EST",
         "Sustained UHS-I read. Cards vary widely; 200 mA is a pessimistic pick."),
    Load("microSD, destination slot", "+3V3", 3.3, 0.000, 0.000, 0.220, "EST",
         "Sustained UHS-I write draws more than read. THE largest single load."),
    Load("LED banks", "+3V3", 3.3, 0.000, 0.010, 0.025, "EST",
         "Five indicators; copy lights the progress row."),
    Load("+1V8 rail quiescent", "+1V8", 1.8, 0.000, 0.002, 0.008, "EST",
         "UHS-I signalling rail. Bypassable with 0R jumpers on rev A."),
]

# Conversion losses
BUCK_EFFICIENCY = 0.90               # VBAT -> +3V3. EST for a small synchronous buck.
CHARGER_EFFICIENCY = 0.90            # switching charger, 5V -> cell. DS-class figure.
CHARGE_CURRENT_A = 0.500
CELL_V_NOMINAL = 3.7
CELL_V_MAX = 4.2
CELL_ESR_OHM = 0.060                 # EST for a 1000 mAh pouch cell with PCM

# Solenoid
SOLENOID_V = 9.0                     # boost rail, jumper-selectable on rev A
SOLENOID_R = 9.0                     # ohms, so ~1 A pull. EST/UNVERIFIED.
SOLENOID_PULSE_MS = 30.0
SOLENOID_ONESHOT_MAX_MS = 50.0       # hardware ceiling, proposed for acceptance.md
SOLENOID_COUNT_ROUTE_B = 4
SOLENOID_STAGGER_MS = 10.0

COPY_SECONDS = 30.0                  # guardrail 10


# --------------------------------------------------------------------------
# Derived
# --------------------------------------------------------------------------

def enclosure_area_m2() -> float:
    w, d, h = (x / 1000.0 for x in ENCLOSURE_MM)
    return 2 * (w * d + w * h + d * h)


def rail_totals(mode: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for load in LOADS:
        out[load.rail] = out.get(load.rail, 0.0) + load.watts(mode)
    return out


def load_watts(mode: str) -> float:
    return sum(load.watts(mode) for load in LOADS)


def buck_loss(mode: str) -> float:
    p = load_watts(mode)
    return p * (1.0 / BUCK_EFFICIENCY - 1.0)


def charger_loss() -> float:
    p_out = CELL_V_MAX * CHARGE_CURRENT_A
    return p_out * (1.0 / CHARGER_EFFICIENCY - 1.0)


def cell_loss() -> float:
    return CHARGE_CURRENT_A**2 * CELL_ESR_OHM


def dissipated(mode: str, charging: bool) -> float:
    """Total power turned into heat inside the sealed enclosure."""
    p = load_watts(mode) + buck_loss(mode)
    if charging:
        p += charger_loss() + cell_loss()
    return p


def bulk_rise_k(p: float) -> float:
    """Steady-state case rise over ambient."""
    return p / (H_COMBINED * enclosure_area_m2())


def internal_rise_k(p: float) -> float:
    """Extra step from board to internal air in a sealed box, on top of the case rise."""
    return p / (H_INTERNAL * BOARD_AREA_M2)


def transient_rise_k(p: float, seconds: float) -> float:
    """First-order rise before the enclosure has time to shed anything."""
    return p * seconds / THERMAL_MASS_J_PER_K


def time_constant_s() -> float:
    return THERMAL_MASS_J_PER_K / (H_COMBINED * enclosure_area_m2())


def solenoid_pulse_w() -> float:
    return SOLENOID_V**2 / SOLENOID_R


def solenoid_pulse_j() -> float:
    return solenoid_pulse_w() * SOLENOID_PULSE_MS / 1000.0


# --------------------------------------------------------------------------
# Per-device junction temperatures
#
# PM Decisions 002-A section 3 upholds the reviewers' finding: a lumped enclosure
# mass does not resolve a 30-second copy. It cannot -- the enclosure's time
# constant is ten minutes, while a QFN's junction reaches steady state in seconds.
# Averaging them hides exactly the device that gets hot fastest.
#
# So this is a two-time-constant model. The slow term is the enclosure rise the
# lumped model already computes; the fast term is each device heating above its
# own local board, with its own theta_JA and its own tau.
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Device:
    name: str
    theta_ja: float        # C/W, junction to ambient on a 4-layer board with pour
    tau_s: float           # own thermal time constant, seconds
    tj_max: float          # C, absolute maximum from the datasheet
    power: dict            # W dissipated, per mode
    source: str


DEVICES: list[Device] = [
    Device("MCU (RT1062, 196-MAPBGA)", 35.0, 20.0, 105.0,
           {"idle": 0.02, "play": 0.36, "copy": 0.59}, "EST/UNVERIFIED"),
    Device("Buck regulator (3V3)", 50.0, 6.0, 125.0,
           {"idle": 0.002, "play": 0.08, "copy": 0.25}, "EST"),
    Device("Charger (buck, thermal pad)", 45.0, 8.0, 125.0,
           {"idle": 0.23, "play": 0.23, "copy": 0.23}, "EST"),
]


def junction_temp(d: Device, mode: str, ambient: float, seconds: float | None,
                  charging: bool = True) -> float:
    """Ambient + enclosure rise + this device's own rise above its local board."""
    p_box = dissipated(mode, charging)
    if seconds is None:                      # held indefinitely -- steady state
        board = bulk_rise_k(p_box) + internal_rise_k(p_box)
        local = d.power[mode] * d.theta_ja
    else:                                    # transient
        board = transient_rise_k(p_box, seconds)
        local = d.power[mode] * d.theta_ja * (1 - math.exp(-seconds / d.tau_s))
    return ambient + board + local


def t_junction() -> str:
    rows = [
        "| Device | θ_JA | τ | P (copy) | **T_j after a 30 s copy** | T_j if held forever | T_j max |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for d in DEVICES:
        t30 = junction_temp(d, "copy", AMBIENT_NOMINAL_C, COPY_SECONDS)
        tinf = junction_temp(d, "copy", AMBIENT_NOMINAL_C, None)
        rows.append(
            f"| {d.name} | {d.theta_ja:.0f} °C/W | {d.tau_s:.0f} s | "
            f"{d.power['copy']*1000:.0f} mW | **{t30:.1f} °C** | {tinf:.1f} °C | "
            f"{d.tj_max:.0f} °C |")
    rows += ["", "At 25 °C ambient. Hot-room case (35 °C ambient, held indefinitely):", "",
             "| Device | T_j | Margin to T_j max |", "|---|---:|---:|"]
    for d in DEVICES:
        t = junction_temp(d, "copy", AMBIENT_HOT_C, None)
        rows.append(f"| {d.name} | {t:.1f} °C | **{d.tj_max - t:+.1f} K** |")
    rows += [
        "",
        "**Why the fast term matters and the lumped model missed it.** The enclosure's time "
        "constant is 621 s; a QFN's is 6–20 s. Over a 30 s copy the box barely moves — half a "
        "kelvin — while the regulator gets within a few percent of its own steady rise. Averaging "
        "the two into one mass reports the box's answer for the die, which is the wrong answer "
        "by roughly the entire local rise. Each device is now carried separately, with its own "
        "θ_JA and its own τ.",
        "",
        "**The result is comfortable, and that is a finding rather than a relief** — it says the "
        "sealed enclosure is not the constraint anywhere, so the thermal argument for vents does "
        "not exist at any point in the design. Every θ_JA here is `EST` until WP-37 measures it; "
        "θ_JA in particular depends on copper pour area, which is a layout output, so these "
        "numbers are a budget layout must hit rather than a prediction of what it will do.",
    ]
    return "\n".join(rows)


# --------------------------------------------------------------------------
# Table rendering
# --------------------------------------------------------------------------

def t_loads() -> str:
    rows = ["| Load | Rail | Idle | Playback | **Copy** | Source |",
            "|---|---|---:|---:|---:|---|"]
    for l in LOADS:
        rows.append(
            f"| {l.name} | `{l.rail}` | {l.watts('idle')*1000:.0f} mW | "
            f"{l.watts('play')*1000:.0f} mW | **{l.watts('copy')*1000:.0f} mW** | {l.source} |")
    rows.append(
        f"| **Load subtotal** | | **{load_watts('idle')*1000:.0f} mW** | "
        f"**{load_watts('play')*1000:.0f} mW** | **{load_watts('copy')*1000:.0f} mW** | |")
    for mode in ("idle", "play", "copy"):
        pass
    rows.append(
        f"| Buck loss @ {BUCK_EFFICIENCY*100:.0f}% | `VBAT` | {buck_loss('idle')*1000:.0f} mW | "
        f"{buck_loss('play')*1000:.0f} mW | {buck_loss('copy')*1000:.0f} mW | EST |")
    rows.append(
        f"| Charger loss @ {CHARGER_EFFICIENCY*100:.0f}% | `+5V` | {charger_loss()*1000:.0f} mW | "
        f"{charger_loss()*1000:.0f} mW | {charger_loss()*1000:.0f} mW | EST |")
    rows.append(
        f"| Cell I²R @ {CELL_ESR_OHM*1000:.0f} mΩ | `VBAT` | {cell_loss()*1000:.0f} mW | "
        f"{cell_loss()*1000:.0f} mW | {cell_loss()*1000:.0f} mW | EST |")
    rows.append(
        f"| **Total in the box, charging** | | "
        f"**{dissipated('idle', True)*1000:.0f} mW** | "
        f"**{dissipated('play', True)*1000:.0f} mW** | "
        f"**{dissipated('copy', True):.2f} W** | |")
    return "\n".join(rows)


def t_rails() -> str:
    rows = ["| Rail | Idle | Playback | Copy |", "|---|---:|---:|---:|"]
    rails = sorted({l.rail for l in LOADS})
    for r in rails:
        i, p, c = (rail_totals(m).get(r, 0.0) for m in ("idle", "play", "copy"))
        rows.append(f"| `{r}` | {i*1000:.0f} mW | {p*1000:.0f} mW | {c*1000:.0f} mW |")
    return "\n".join(rows)


def t_scenarios() -> str:
    area = enclosure_area_m2()
    tau = time_constant_s()
    rows = [
        "| Scenario | Duration | Power in box | Case rise (steady) | Board→air step | Realised rise |",
        "|---|---|---:|---:|---:|---|",
    ]

    def row(name, dur_s, p, sustained):
        case = bulk_rise_k(p)
        step = internal_rise_k(p)
        if sustained:
            realised = f"**{case + step:.1f} K** (reaches steady state)"
        else:
            tr = transient_rise_k(p, dur_s)
            realised = f"**{tr:.1f} K** bulk + local (see below)"
        d = "indefinite" if sustained else f"{dur_s:.0f} s"
        return (f"| {name} | {d} | {p:.2f} W | {case:.1f} K | {step:.1f} K | {realised} |")

    rows.append(row("Asleep, charging", 3600, dissipated("idle", True), True))
    rows.append(row("Playback, charging", 3600, dissipated("play", True), True))
    rows.append(row("Copy, not charging", COPY_SECONDS, dissipated("copy", False), False))
    rows.append(row("Copy + charging (WP-37 stress)", COPY_SECONDS,
                    dissipated("copy", True), False))
    rows.append(row("Copy + charging, held (fault)", 3600,
                    dissipated("copy", True), True))
    rows.append("")
    rows.append(f"Enclosure surface area **{area*1e4:.1f} cm²**; "
                f"thermal time constant **τ = {tau:.0f} s ({tau/60:.0f} min)**.")
    return "\n".join(rows)


def t_ambient() -> str:
    p_sus = dissipated("play", True)
    rise = bulk_rise_k(p_sus) + internal_rise_k(p_sus)
    rows = ["| Ambient | Internal air (sustained worst case) | Margin to 45 °C JEITA ceiling |",
            "|---|---:|---:|"]
    for amb in (AMBIENT_NOMINAL_C, AMBIENT_WARM_C, AMBIENT_HOT_C):
        t = amb + rise
        margin = 45.0 - t
        flag = "" if margin > 8 else (" ⚠️" if margin > 0 else " ❌")
        rows.append(f"| {amb:.0f} °C | {t:.1f} °C | {margin:+.1f} K{flag} |")
    rows.append("")
    rows.append(f"Sustained worst case is **playback while charging at "
                f"{dissipated('play', True):.2f} W**, not copy — see §3.")
    return "\n".join(rows)


def t_solenoid() -> str:
    w = solenoid_pulse_w()
    j = solenoid_pulse_j()
    duty_max = SOLENOID_ONESHOT_MAX_MS / 1000.0 / 10.0
    return "\n".join([
        "| Quantity | Value | Note |",
        "|---|---:|---|",
        f"| Coil power while energised | **{w:.1f} W** | {SOLENOID_V:.0f} V into "
        f"{SOLENOID_R:.0f} Ω, ~{SOLENOID_V/SOLENOID_R:.2f} A |",
        f"| Energy per actuation | {j*1000:.0f} mJ | {SOLENOID_PULSE_MS:.0f} ms pulse |",
        f"| One-shot ceiling (hardware) | {SOLENOID_ONESHOT_MAX_MS:.0f} ms | "
        f"{SOLENOID_ONESHOT_MAX_MS/SOLENOID_PULSE_MS:.1f}× the nominal pulse |",
        f"| Worst case a one-shot alone permits | **{w:.1f} W continuous** | "
        "a retrigger loop; this is why on-time alone is not enough |",
        f"| Duty backstop ceiling | {duty_max*100:.1f}% over 10 s | "
        f"= {w*duty_max:.2f} W average, survivable indefinitely |",
        f"| Route B, all four at once | **{SOLENOID_COUNT_ROUTE_B*SOLENOID_V/SOLENOID_R:.1f} A** | "
        "unstaggered — the charter's peak-current objection |",
        f"| Route B, staggered {SOLENOID_STAGGER_MS:.0f} ms | "
        f"**{SOLENOID_V/SOLENOID_R:.2f} A** | over "
        f"{SOLENOID_COUNT_ROUTE_B*SOLENOID_STAGGER_MS:.0f} ms, imperceptible |",
    ])


BLOCKS = {
    "loads": t_loads,
    "rails": t_rails,
    "scenarios": t_scenarios,
    "ambient": t_ambient,
    "junction": t_junction,
}


def render(text: str) -> str:
    for name, fn in BLOCKS.items():
        pat = re.compile(
            rf"(<!-- BEGIN GENERATED: {name} -->\n).*?(\n<!-- END GENERATED: {name} -->)",
            re.DOTALL)
        if not pat.search(text):
            sys.exit(f"budget.py: no marker block for '{name}' in {SPEC}")
        text = pat.sub(lambda m: m.group(1) + fn() + m.group(2), text)
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="exit non-zero if the spec is out of date")
    args = ap.parse_args()

    if not SPEC.exists():
        sys.exit(f"budget.py: {SPEC} does not exist")
    current = SPEC.read_text()
    updated = render(current)

    if args.check:
        if current != updated:
            print("thermal budget is STALE: run `make -C hardware thermal`",
                  file=sys.stderr)
            return 1
        print("thermal budget is up to date")
        return 0

    if current != updated:
        SPEC.write_text(updated)
        print(f"regenerated {SPEC.relative_to(SPEC.parents[2])}")
    else:
        print("thermal budget already up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
