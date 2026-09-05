#!/usr/bin/env python3
"""Cartridge clasp — strain, retention force, and the child/adult separation.

PM Decisions 006 §2 asks for five numbers. Four of them are here; the fifth (the
seam, in mm) is a process figure, not a mechanics one, and lives in the spec text.

The one that decides the material question is **strain**, and the useful property
of the strain formula is what it does NOT contain:

    eps = 3 y t / (2 a^2)

No run length, no perimeter, no cartridge size. Strain depends only on the wall
section and how far it is pushed. So the cartridge's outer dimensions are
Michael's aesthetic call and can move without reopening the creep question --
they change the FORCES, which are a comfort matter, and not the strain, which is
a materials matter.

Two strains matter and they are wildly different:

  * during opening, ~1 second, once or twice in the cartridge's life
  * at rest, closed, for years -- and this is the one that decides creep

The design makes the second one nearly zero on purpose: the bead seats fully in
its groove and the wall returns undeflected. The only sustained load is the TPU
lip's preload, and §T-4 below shows what that costs.

    make -C hardware clasp        print the analysis
    make -C hardware mech-check   fail if spec/hw/cartridge-shell.md is stale
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

SPEC = Path(__file__).resolve().parents[2] / "spec" / "hw" / "cartridge-shell.md"

# --------------------------------------------------------------------------
# Working geometry. Every one of these is a proposal, not a measurement.
# --------------------------------------------------------------------------

CART_L, CART_W, CART_H = 86.0, 54.0, 12.0   # outer; Michael's call, see module docstring
WALL_NOM = 2.0             # nominal shell wall
WALL_RET = 1.2             # thinned local to the retention run -- THE lever on strain
SPAN = 6.0                 # floor to seam: the cantilever length. Half the shell height
INTERFERENCE = 0.30        # total, shared between the two halves
TOL_INTERFERENCE = 0.15    # +/-, FDM on two separately printed parts, plus colour shrink
CORNER_RELIEF = 9.0        # engagement stops this far short of each corner
SPUDGER_SPAN = 14.0        # length of run a levered blade deflects at once

# BOTH ANGLES ARE MEASURED FROM THE PULL AXIS, not from the seam plane, and the
# distinction is not pedantic: it inverts the formula. Virtual work settles it --
# W dz = P dy, so W = P (dy/dz), and dy/dz = tan(angle from the pull axis). A face
# at 0 deg from the pull axis is vertical and cams nothing; a face approaching
# horizontal self-locks. check_convention() below asserts it.
CHAMFER_LEAD = 25.0        # closing ramp, degrees from the pull axis
CHAMFER_RETAIN = 40.0      # opening ramp, degrees from the pull axis

# TPU lip seal: compliant in BENDING, which is the only way to get a soft preload
# out of TPU. The same rubber as a block in compression is stiffer than the PETG.
TPU_T, TPU_SPAN, TPU_DEFL = 0.8, 2.0, 0.2

# --------------------------------------------------------------------------
# Material properties. ALL ESTIMATES -- see the module docstring in the spec.
# No vendor egress reached a filament datasheet, so these are from general
# knowledge of the polymers and are marked EST everywhere they surface.
# --------------------------------------------------------------------------

MATERIALS = {
    #                E MPa   permissible strain, repeated assembly
    "PETG": (1800.0, 0.020),
    "PLA":  (3300.0, 0.010),
    "TPU":  (25.0,   0.300),
}
MU = 0.35                  # print-surface polymer on polymer, EST

# Bounding paediatric figures, EST, and used one-sided (a bigger child is the
# hazard, so these are chosen high rather than typical).
CHILD_PINCH_N = 20.0
CHILD_GRIP_N = 80.0


def strain(deflection: float, thickness: float, span: float) -> float:
    """Peak surface strain at the root of a cantilever deflected `deflection`."""
    return 3.0 * deflection * thickness / (2.0 * span * span)


def deflect_force(e_mpa: float, run: float, thickness: float,
                  deflection: float, span: float) -> float:
    """Force to push a `run`-long strip of wall out by `deflection`. N."""
    return e_mpa * run * thickness ** 3 * deflection / (4.0 * span ** 3)


def self_lock_deg(mu: float = MU) -> float:
    """Above this angle from the pull axis, the joint cannot be opened at all."""
    return math.degrees(math.atan(1.0 / mu))


def ramp_factor(angle_deg: float, mu: float = MU) -> float:
    """Force multiplier for a ramp at `angle_deg` FROM THE PULL AXIS.

    The standard snap-fit relation. The denominator reaches zero at
    atan(1/mu) -- 70.7 deg for mu = 0.35 -- and past that the joint is
    self-locking: it breaks before it opens. That threshold, not 90 deg, is
    what the retention face has to stay under, and 40 deg leaves half of it.
    """
    t = math.tan(math.radians(angle_deg))
    denom = 1.0 - mu * t
    if denom <= 0:
        return float("inf")
    return (mu + t) / denom


def engaged_run(length: float) -> float:
    """Retention runs the long walls but stops short of the corners.

    A continuous perimeter lip is the right instinct and the wrong part is the
    CORNERS: a rectangular box cannot open at a corner by bending, only by
    stretching, which is effectively rigid. So the seam is continuous and the
    engagement is not.
    """
    return length - 2.0 * CORNER_RELIEF


def joint(material: str, run: float, interference: float = INTERFERENCE,
          walls: int = 2, thickness: float = WALL_RET, span: float = SPAN):
    """Everything about one clasp, as a dict. Deflection is SHARED: both halves
    bend, so each takes half the interference -- which is also why the strain is
    half what a single-flexing-member design would give."""
    e, eps_max = MATERIALS[material]
    y = interference / 2.0
    p = deflect_force(e, run, thickness, y, span) * walls
    return {
        "material": material, "run": run, "interference": interference,
        "deflection_per_half": y,
        "strain": strain(y, thickness, span),
        "strain_permissible": eps_max,
        "deflect_n": p,
        "separate_n": p * ramp_factor(CHAMFER_RETAIN),
        "close_n": p * ramp_factor(CHAMFER_LEAD),
    }


def tpu_preload_n(perimeter: float) -> float:
    e, _ = MATERIALS["TPU"]
    return deflect_force(e, perimeter, TPU_T, TPU_DEFL, TPU_SPAN)


def resting_strain(perimeter: float, run: float) -> tuple[float, float, float]:
    """What the TPU preload costs the PETG wall, held for years.

    The preload pushes the lid against the bead's undercut. That normal force has
    a component trying to cam the wall outward, and THAT is the only sustained
    bending in the design. Returns (preload N, cam N per wall, resting strain).
    """
    pre = tpu_preload_n(perimeter)
    t = math.tan(math.radians(CHAMFER_RETAIN))
    cam_total = pre * (t - MU) / (1.0 + MU * t)
    cam_wall = cam_total / 2.0
    e, _ = MATERIALS["PETG"]
    y = 4.0 * cam_wall * SPAN ** 3 / (e * run * WALL_RET ** 3)
    return pre, cam_wall, strain(y, WALL_RET, SPAN)


# --------------------------------------------------------------------------
# The variant sweep that goes on the plate
# --------------------------------------------------------------------------

COUPON_L, COUPON_W = 62.0, 28.0
SWEEP = (0.15, 0.25, 0.35, 0.45)


def sweep_rows(material: str = "PLA"):
    run = engaged_run(COUPON_L)
    out = []
    for i in SWEEP:
        j = joint(material, run, interference=i)
        out.append(j)
    return out


# --------------------------------------------------------------------------
# Generated blocks
# --------------------------------------------------------------------------

def t_geometry() -> str:
    run = engaged_run(CART_L)
    j = joint("PETG", run)
    worst = joint("PETG", run, interference=INTERFERENCE + TOL_INTERFERENCE)
    best = joint("PETG", run, interference=max(0.0, INTERFERENCE - TOL_INTERFERENCE))
    rows = [
        "| Parameter | Value | Why this number |",
        "|---|---:|---|",
        f"| Cartridge outer | {CART_L:.0f} × {CART_W:.0f} × {CART_H:.0f} mm | "
        "**Michael's call, and the analysis does not depend on it** — see the note below |",
        f"| Nominal wall | {WALL_NOM:.1f} mm | Stiffness and drop survival everywhere except the run |",
        f"| Retention wall | **{WALL_RET:.1f} mm** | Thinned local to the run. Strain is linear in this |",
        f"| Cantilever span | {SPAN:.1f} mm | Floor to seam. Half the shell height; strain goes as its square |",
        f"| Interference | **{INTERFERENCE:.2f} mm** total | Shared: {j['deflection_per_half']:.3f} mm per half |",
        f"| Tolerance on it | ±{TOL_INTERFERENCE:.2f} mm | Two separate prints, plus colour-to-colour shrink |",
        f"| Engaged run | {run:.0f} mm per long wall | {CART_L:.0f} mm less {CORNER_RELIEF:.0f} mm of corner relief each end |",
        f"| Lead-in chamfer | {CHAMFER_LEAD:.0f}° from the pull axis | Closing ramp; "
        f"{INTERFERENCE/math.tan(math.radians(CHAMFER_LEAD)):.2f} mm tall for a "
        f"{INTERFERENCE:.2f} mm bead |",
        f"| Retention face | **{CHAMFER_RETAIN:.0f}° from the pull axis** | Opening ramp; "
        f"self-locks past **{self_lock_deg():.1f}°**, so this keeps half the range |",
        "",
        "**Strain contains no length term.** `ε = 3yt/2a²` — wall section and deflection only. "
        f"So {CART_L:.0f} × {CART_W:.0f} can become anything Michael likes: the outer dimensions "
        "move the *forces*, which are a comfort question, and leave the *strain* untouched, which "
        "is the materials question. That is the one decision in this document that can be taken "
        "on taste without reopening anything.",
        "",
        "| Strain in PETG | Deflection per half | Peak strain | Against 2.0 % permissible |",
        "|---|---:|---:|---|",
    ]
    for label, k in (("Interference at minimum", best), ("**Nominal**", j),
                     ("Interference at maximum", worst)):
        margin = k["strain_permissible"] / k["strain"] if k["strain"] else float("inf")
        rows.append(f"| {label} | {k['deflection_per_half']:.3f} mm | "
                    f"**{k['strain']*100:.2f} %** | {margin:.1f}× |")
    return "\n".join(rows)


def t_forces() -> str:
    run = engaged_run(CART_L)
    j = joint("PETG", run)
    span_j = joint("PETG", SPUDGER_SPAN, walls=1)
    ratio = j["separate_n"] / span_j["separate_n"]
    rows = [
        "| Action | Force | Who does it |",
        "|---|---:|---|",
        f"| Pull the halves apart, whole seam at once | **{j['separate_n']:.0f} N** | nobody — see below |",
        f"| Press closed, whole seam at once | {j['close_n']:.0f} N | nobody — closing rolls too |",
        f"| Lever one {SPUDGER_SPAN:.0f} mm span open with a blade | **{span_j['separate_n']:.1f} N** | the parent |",
        f"| Press one {SPUDGER_SPAN:.0f} mm span closed | {span_j['close_n']:.1f} N | the parent, rolling along |",
        "",
        f"**The tool does not beat the latch by force, it beats it by unzipping it.** The ratio "
        f"is **{ratio:.0f} : 1** — because deflection force is linear in engaged length, and a "
        f"blade in the slot deflects {SPUDGER_SPAN:.0f} mm of run while a brute pull has to "
        f"deflect all {run:.0f} mm of both walls at once. Every millimetre of length you add to "
        "the cartridge makes the brute path harder and leaves the tool path exactly where it is.",
        "",
        "### Why the pull force is not the safety argument",
        "",
        "| | Force available | vs the {sep:.0f} N pull |".format(sep=j["separate_n"]),
        "|---|---:|---|",
        f"| Five-year-old, pinch on a flush 12 mm slab | ~{CHILD_PINCH_N:.0f} N | "
        f"**{j['separate_n']/CHILD_PINCH_N:.1f}× margin** |",
        f"| Five-year-old, two-handed grip on something to hold | ~{CHILD_GRIP_N:.0f} N | "
        f"{j['separate_n']/CHILD_GRIP_N:.1f}× margin |",
        f"| Adult, two-handed pull | 200 N+ | none — an adult can force it |",
        "",
        "Read the second row before the first. **Retention force does not separate a child from "
        "an adult** — a determined seven-year-old with something to grip is inside a factor of "
        "two of this joint, and I am not going to design a number that pretends otherwise. What "
        "separates them is that there is *nothing to grip*: the seam is flush, there is no lip, "
        "no recess and no proud edge anywhere on the shell, so the only force a child can bring "
        "is a pinch on a smooth 12 mm slab. That is the first row, and it is the one with the "
        "margin in it.",
        "",
        "**The consequence for the design is a rule, not a number:** any feature that gives a "
        "fingernail or a fingertip purchase on the parting line converts row 1 into row 2 and "
        "spends the entire safety margin. That rules out the recessed thumb-notch that every "
        "battery cover has, and it is why the opening feature is a slot for a blade.",
    ]
    return "\n".join(rows)


def t_creep() -> str:
    run = engaged_run(CART_L)
    perim = 2.0 * (CART_L + CART_W)
    pre, cam, eps = resting_strain(perim, run)
    j = joint("PETG", run)
    rows = [
        "The question PM Decisions 006 §2 asks — *does PETG creep at the deflection you chose* — "
        "has a better answer than a margin, which is that **the design does not hold the "
        "deflection**. The bead seats fully in the groove and the wall returns to undeflected. "
        "The opening strain exists for about a second, once or twice in the cartridge's life.",
        "",
        "What is held for years is only the TPU lip's preload, and this is what it costs:",
        "",
        "| | Value |",
        "|---|---:|",
        f"| TPU lip section | {TPU_T:.1f} mm thick × {TPU_SPAN:.1f} mm tall, deflected {TPU_DEFL:.1f} mm |",
        f"| Perimeter preload | {pre:.0f} N |",
        f"| Camming component per long wall | {cam:.1f} N |",
        f"| **Sustained strain in the PETG wall** | **{eps*100:.3f} %** |",
        f"| Opening strain, for comparison | {j['strain']*100:.2f} % |",
        f"| Creep threshold where PETG starts to matter | ~0.5 % (EST) |",
        "",
        f"**{eps*100:.3f} % is {0.5/(eps*100):.0f}× below the threshold**, and it is the only "
        "sustained figure in the design. The reason the TPU is a bending lip rather than a "
        "compressed gasket is arithmetic: the same TPU as a 1 mm gasket squashed 0.2 mm over this "
        "perimeter develops several hundred newtons and would hold the shell open. In bending it "
        f"develops {pre:.0f} N. **Same material, same displacement, two orders of magnitude apart** "
        "— the compliance has to come from the shape.",
        "",
        "**The TPU is also where the tolerance goes.** The PETG bead gives *retention* — a hard "
        f"stop at a defined interference. The TPU lip gives *preload* — it takes up the "
        f"±{TOL_INTERFERENCE:.2f} mm of print variation so the joint does not rattle at the loose "
        "end of the stack and does not bind at the tight end. Splitting those two jobs across two "
        "materials is what makes a printed clasp survive a colour change, which is the failure "
        "PM Decisions 006 §1 warns about.",
    ]
    return "\n".join(rows)


def t_sweep() -> str:
    run = engaged_run(COUPON_L)
    _, eps_pla = MATERIALS["PLA"]
    _, eps_petg = MATERIALS["PETG"]
    rows = [
        f"Coupon: **{COUPON_L:.0f} × {COUPON_W:.0f} × {CART_H:.0f} mm**, a real long-wall run "
        f"({run:.0f} mm engaged) with both corner relieves, at full section. Not a cartridge — a "
        "cartridge does not fit on the plate beside WP-04 and the coupon tests the thing being "
        "swept.",
        "",
        "**The plate prints in PLA, and the design is for PETG.** That is not a flaw in the "
        "packet, it is the bracket. PLA is roughly twice as stiff and half as extensible, so the "
        "same geometry that is comfortable in PETG is at PLA's limit — which means **the top of "
        "this sweep is expected to crack**, and that is a useful result rather than a wasted part.",
        "",
        "| Interference | Strain | vs PLA {p:.1f} % | vs PETG {q:.1f} % | Brute pull | **Lever** | Expectation |".format(
            p=eps_pla * 100, q=eps_petg * 100),
        "|---:|---:|---|---|---:|---:|---|",
    ]
    notes = {
        0.15: "too loose — should rattle or fall open",
        0.25: "candidate",
        0.35: "candidate, at PLA's limit",
        0.45: "**expected to crack in PLA**; comfortable in PETG",
    }
    levers = []
    for j in sweep_rows("PLA"):
        i = j["interference"]
        lev = joint("PLA", SPUDGER_SPAN, interference=i, walls=1)
        levers.append(lev["separate_n"])
        pla_ok = "ok" if j["strain"] <= eps_pla else "**over**"
        petg_ok = "ok" if j["strain"] <= eps_petg else "**over**"
        rows.append(f"| {i:.2f} mm | {j['strain']*100:.2f} % | {pla_ok} | {petg_ok} | "
                    f"{j['separate_n']:.0f} N | **{lev['separate_n']:.0f} N** | {notes[i]} |")
    rows += [
        "",
        f"**The lever column is the one that matters for the packet**, because it is the force "
        f"Michael's hand actually applies. It runs {min(levers):.0f}–{max(levers):.0f} N across "
        "the sweep — a light push to a firm one on a blade — so **every variant is openable by "
        "hand, including the one expected to crack.** If the brute-pull column were the operating "
        "force, the top two variants would be untestable and the plate would be worthless.",
        "",
        "The brute-pull column is the coupon in PLA, not the cartridge in PETG, and it is here so "
        "that nobody reads a cartridge number off it later. The coupon's run is shorter and its "
        "material is stiffer; the two effects push opposite ways and the number means nothing "
        "except relative to the other rows.",
    ]
    return "\n".join(rows)


def check_convention() -> None:
    """The ramp angle is measured from the PULL AXIS. Assert it, because the
    other reading is plausible, silently inverts every force in this file, and
    would still produce a table full of confident numbers.

    Virtual work: W dz = P dy. A shallower face (further from the pull axis)
    trades travel for deflection, so it must cost MORE force, and past
    atan(1/mu) it cannot be opened at all.
    """
    assert ramp_factor(25.0) < ramp_factor(40.0) < ramp_factor(60.0), \
        "ramp_factor is not increasing in angle -- the convention is inverted"
    assert math.isinf(ramp_factor(self_lock_deg() + 1.0)), \
        "a face past the self-lock angle must be unopenable"
    assert abs(ramp_factor(45.0, mu=0.0) - 1.0) < 1e-9, \
        "frictionless 45 deg must be a 1:1 force ratio"
    assert CHAMFER_RETAIN < self_lock_deg(), \
        "the retention face is self-locking: it would break before it opened"


BLOCKS = {
    "clasp_geometry": t_geometry,
    "clasp_forces": t_forces,
    "clasp_creep": t_creep,
    "clasp_sweep": t_sweep,
}


def render(text: str) -> str:
    for name, fn in BLOCKS.items():
        pat = re.compile(
            rf"(<!-- BEGIN GENERATED: {name} -->\n).*?(\n<!-- END GENERATED: {name} -->)",
            re.DOTALL)
        if not pat.search(text):
            sys.exit(f"clasp.py: no marker block for '{name}'")
        text = pat.sub(lambda m: m.group(1) + fn() + m.group(2), text)
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    check_convention()
    if a.report:
        for fn in BLOCKS.values():
            print(fn(), "\n")
        return 0
    cur = SPEC.read_text()
    new = render(cur)
    if a.check:
        if cur != new:
            print("clasp tables STALE", file=sys.stderr)
            return 1
        print("clasp tables up to date")
        return 0
    if cur != new:
        SPEC.write_text(new)
        print("regenerated clasp tables")
    else:
        print("clasp tables already up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
