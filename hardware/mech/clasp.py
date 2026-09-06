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
WALL_RET = 1.6             # thinned local to the retention run
SPAN = 6.0                 # floor to seam: the cantilever length. Half the shell height
INTERFERENCE = 0.18        # total, shared between the two halves
# Two tolerances, and choosing the right one is the whole reason the 0.18 mm
# nominal is viable at all.
#
#   ACROSS sessions: +/-0.15 mm. Different spool, different colour, different
#   thermal state. This is the figure Decisions 007 §2 warns about.
#   WITHIN one plate: +/-0.05 mm. Both halves print in the same machine, same
#   material, same session -- they shrink TOGETHER, so what survives is the
#   printer's XY repeatability, not the material's shrinkage.
#
# A cartridge's two halves are a matched pair and are always printed together, so
# the relative figure is the one that governs the fit. That is a manufacturing
# rule, not a tuned fit, so it does not violate "do not tune to a filament" --
# it removes the filament from the comparison entirely.
TOL_PAIRED = 0.05          # +/-, both halves on one plate. THE governing figure
TOL_MIXED = 0.15           # +/-, halves from different sessions. Forbidden, costed below
TOL_INTERFERENCE = TOL_PAIRED
CORNER_RELIEF = 9.0        # engagement stops this far short of each corner
SPUDGER_SPAN = 14.0        # length of run a levered blade deflects at once
GROOVE_EXTRA = 0.05        # groove cut deeper than the bead is proud -> zero closed strain

# BOTH ANGLES ARE MEASURED FROM THE PULL AXIS, not from the seam plane, and the
# distinction is not pedantic: it inverts the formula. Virtual work settles it --
# W dz = P dy, so W = P (dy/dz), and dy/dz = tan(angle from the pull axis). A face
# at 0 deg from the pull axis is vertical and cams nothing; a face approaching
# horizontal self-locks. check_convention() below asserts it.
CHAMFER_LEAD = 25.0        # closing ramp, degrees from the pull axis
CHAMFER_RETAIN = 40.0      # opening ramp, degrees from the pull axis

# Anti-rattle leaf, IF the first plate says rattle is real. Same material as the
# shell -- the TPU lip this replaces cannot be printed on a single library spool.
# Not on the coupon on purpose: see t_rattle().
LEAF_T, LEAF_SPAN, LEAF_DEFL, LEAF_W = 0.8, 14.0, 0.10, 20.0
LEAF_COUNT = 4

# --------------------------------------------------------------------------
# Material properties. ALL ESTIMATES -- see the module docstring in the spec.
# No vendor egress reached a filament datasheet, so these are from general
# knowledge of the polymers and are marked EST everywhere they surface.
# --------------------------------------------------------------------------

# PLA leads because PLA is what we will get. PM Decisions 007 §2: the library
# runs a single spool of whatever it has loaded, we do not choose it, and Michael
# is not buying a printer. The PETG column is kept only to show the design does
# not depend on which of them arrives.
#
# `creep` is the sustained strain above which the material relaxes measurably at
# room temperature over months. It is the number Decisions 007 §2 is really about
# -- a clasp is engaged 99.99 % of its life, so this, not fatigue, is the risk.
MATERIALS = {
    #        E MPa   permissible (snap)  creep threshold (sustained)
    "PLA":  (3300.0, 0.010,              0.0025),
    "PETG": (1800.0, 0.020,              0.0050),
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


def modulus(material: str) -> float:
    return MATERIALS[material][0]


def permissible(material: str) -> float:
    return MATERIALS[material][1]


def creep_threshold(material: str) -> float:
    return MATERIALS[material][2]


def joint(material: str, run: float, interference: float = INTERFERENCE,
          walls: int = 2, thickness: float = WALL_RET, span: float = SPAN):
    """Everything about one clasp, as a dict. Deflection is SHARED: both halves
    bend, so each takes half the interference -- which is also why the strain is
    half what a single-flexing-member design would give."""
    e, eps_max = MATERIALS[material][0], MATERIALS[material][1]
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


def leaf(material: str) -> tuple[float, float]:
    """The anti-rattle leaf, if one turns out to be needed: (force N, strain).

    A short stiff rib cannot do this job -- deflecting a 2.9 mm tall rib by
    0.10 mm is 1.4 % strain, held forever, which is the exact failure Decisions
    007 §2 forbids. The compliance has to come from a LONG, THIN leaf, and the
    strain formula says why: strain goes as 1/span squared while force goes as
    1/span cubed, so lengthening the leaf buys strain faster than it loses force.
    """
    f = deflect_force(modulus(material), LEAF_W, LEAF_T, LEAF_DEFL, LEAF_SPAN)
    return f * LEAF_COUNT, strain(LEAF_DEFL, LEAF_T, LEAF_SPAN)


# --------------------------------------------------------------------------
# The variant sweep that goes on the plate
# --------------------------------------------------------------------------

COUPON_L, COUPON_W = 62.0, 28.0
SWEEP = (0.10, 0.18, 0.26, 0.34)


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
    j = joint("PLA", run)
    worst = joint("PLA", run, interference=INTERFERENCE + TOL_INTERFERENCE)
    best = joint("PLA", run, interference=max(0.0, INTERFERENCE - TOL_INTERFERENCE))
    rows = [
        "| Parameter | Value | Why this number |",
        "|---|---:|---|",
        f"| Cartridge outer | {CART_L:.0f} × {CART_W:.0f} × {CART_H:.0f} mm | "
        "**Michael's call, and the analysis does not depend on it** — see below |",
        f"| Nominal wall | {WALL_NOM:.1f} mm | Stiffness and drop survival everywhere except the run |",
        f"| Retention wall | **{WALL_RET:.1f} mm** | Thinned local to the run. Was 1.2 mm; see the note below |",
        f"| Cantilever span | {SPAN:.1f} mm | Floor to bead. Strain goes as its square |",
        f"| Interference | **{INTERFERENCE:.2f} mm** total | Shared: {j['deflection_per_half']:.3f} mm per half |",
        f"| Tolerance on it | ±{TOL_INTERFERENCE:.2f} mm | Separately printed parts, and we do not choose the spool |",
        f"| Engaged run | {run:.0f} mm per long wall | {CART_L:.0f} mm less {CORNER_RELIEF:.0f} mm of corner relief each end |",
        f"| Lead-in chamfer | {CHAMFER_LEAD:.0f}° from the pull axis | Closing ramp |",
        f"| Retention face | **{CHAMFER_RETAIN:.0f}° from the pull axis** | Self-locks past **{self_lock_deg():.1f}°**, so this keeps half the range |",
        "",
        "### The wall got thicker and the interference got smaller, and that improved both numbers",
        "",
        "Rev 0.1 was a 1.2 mm wall at 0.30 mm interference: **0.75 % strain and 124 N** of "
        "retention in PETG. This is a 1.6 mm wall at 0.18 mm: **0.60 % strain and "
        f"{joint('PETG', run)['separate_n']:.0f} N**. Lower strain *and* higher retention, which "
        "looks wrong until you write the two out:",
        "",
        "```",
        "strain    ~ i · t / a²        thickness enters LINEARLY",
        "retention ~ E · w · t³ · i / a³   thickness enters CUBICALLY",
        "```",
        "",
        "So thickening the wall and pulling the interference back down to compensate is a strict "
        "win: you give up strain linearly and buy retention cubically. **The thicker wall is also "
        "the better drop part** (S-3), which is the rarest kind of result — the same change "
        "helping three criteria at once.",
        "",
        "### The outer dimensions are free, and this is the one decision Michael can take on taste",
        "",
        "**Strain contains no length term.** `ε = 3yt/2a²` — wall section and deflection only. "
        f"So {CART_L:.0f} × {CART_W:.0f} can become anything: the outer dimensions move the "
        "*forces*, which is a comfort question, and leave the *strain* untouched, which is the "
        "materials question.",
        "",
        "### Snap-through strain, and the material it assumes",
        "",
        "The number PM Decisions 007 §2 asks for. **This is the only strain in the design, and it "
        "exists for about a second, twice in the cartridge's life.**",
        "",
        "| | Deflection per half | **Snap-through strain** | vs PLA 1.0 % | vs PETG 2.0 % |",
        "|---|---:|---:|---|---|",
    ]
    for label, k in (("Interference at minimum", best), ("**Nominal**", j),
                     ("Interference at maximum", worst)):
        e = k["strain"]
        rows.append(f"| {label} | {k['deflection_per_half']:.3f} mm | "
                    f"**{e*100:.2f} %** | {permissible('PLA')/e:.1f}× | {permissible('PETG')/e:.1f}× |")
    worst_ratio = permissible("PLA") / worst["strain"]
    verdict = ("Every row above clears PLA's permissible strain"
               if worst_ratio >= 1.0 else
               f"**The worst row does NOT clear PLA** ({worst_ratio:.1f}×)")
    mixed = joint("PLA", run, interference=INTERFERENCE + TOL_MIXED)
    short_span = 3.2
    rows += [
        "",
        "### Why the wall is thinned only over the run",
        "",
        f"The thinning *is* the cantilever: {WALL_RET:.1f} mm over the full {SPAN:.1f} mm from "
        "floor to bead. Everywhere else the wall stays "
        f"{WALL_NOM:.1f} mm, for stiffness and for the drop criterion. The tempting "
        "simplification is to thin the whole rim so the lid's tongue can be a plain rectangle — "
        f"and that moves the flexing span from {SPAN:.1f} mm to about {short_span:.1f} mm. "
        "Strain goes as the square of the span, so "
        f"**{j['strain']*100:.2f} % becomes {strain(j['deflection_per_half'], WALL_RET, short_span)*100:.2f} %** — "
        f"{strain(j['deflection_per_half'], WALL_RET, short_span)/permissible('PLA'):.1f}× PLA's "
        "permissible strain. That version prints, assembles and feels correct on the bench. "
        "`hardware/cad/cartridge/test_shell.py` probes the wall section from the floor to the "
        "bead for exactly this reason.",
        "",
        f"**The assumed material is PLA**, because that is what we will get: a single library "
        f"spool of whatever is loaded, not chosen by us (Decisions 007 §2). {verdict}, so the "
        "design does not depend on which of the two arrives — which is the point, since we "
        "cannot specify it.",
        "",
        f"**And this is what the paired-printing rule buys.** Build a cartridge from halves "
        f"printed in *different* sessions and the tolerance is ±{TOL_MIXED:.2f} mm instead of "
        f"±{TOL_PAIRED:.2f} mm. The interference then ranges from "
        f"{max(0.0, INTERFERENCE - TOL_MIXED):.2f} mm — **no engagement at all** — up to "
        f"{INTERFERENCE + TOL_MIXED:.2f} mm at **{mixed['strain']*100:.2f} % strain**, which is "
        f"{'past' if mixed['strain'] > permissible('PLA') else 'inside'} PLA's limit. Both ends "
        "of that range are a failure. **Halves are a matched pair and the card says so.**",
    ]
    return "\n".join(rows)


def t_forces() -> str:
    run = engaged_run(CART_L)
    rows = [
        "**All of this comes from geometry, not from stored spring force** — which is the "
        "distinction PM Decisions 007 §2 turns on. Nothing is held deflected when the cartridge "
        "is shut. The lip sits behind a shoulder, and separating the halves has to push it back "
        "out over its ramp against a wall that starts from rest.",
        "",
        "| Action | PLA | PETG | Who does it |",
        "|---|---:|---:|---|",
    ]
    acts = [
        ("Pull the halves apart, whole seam at once", lambda m: joint(m, run)["separate_n"], "nobody — see below"),
        ("Press closed, whole seam at once", lambda m: joint(m, run)["close_n"], "nobody — closing rolls too"),
        (f"Lever one {SPUDGER_SPAN:.0f} mm span open with a blade",
         lambda m: joint(m, SPUDGER_SPAN, walls=1)["separate_n"], "**the parent**"),
        (f"Press one {SPUDGER_SPAN:.0f} mm span closed",
         lambda m: joint(m, SPUDGER_SPAN, walls=1)["close_n"], "the parent, rolling along"),
    ]
    for label, fn, who in acts:
        rows.append(f"| {label} | {fn('PLA'):.0f} N | {fn('PETG'):.0f} N | {who} |")

    j = joint("PLA", run)
    span_j = joint("PLA", SPUDGER_SPAN, walls=1)
    ratio = j["separate_n"] / span_j["separate_n"]
    soft = joint("PETG", run)["separate_n"]
    rows += [
        "",
        f"**The tool does not beat the latch by force, it beats it by unzipping it.** "
        f"**{ratio:.0f} : 1** — deflection force is linear in engaged length, so a blade in the "
        f"slot deflects {SPUDGER_SPAN:.0f} mm of run while a brute pull has to deflect all "
        f"{run:.0f} mm of both walls at once. The ratio is a property of the geometry and is "
        "**identical in both materials**, which is what makes the opening feature specifiable "
        "when the spool is not.",
        "",
        "### Why the pull force is not the safety argument",
        "",
        f"| | Force available | vs {soft:.0f} N (the softer material) |",
        "|---|---:|---|",
        f"| Five-year-old, pinch on a flush {CART_H:.0f} mm slab | ~{CHILD_PINCH_N:.0f} N | "
        f"**{soft/CHILD_PINCH_N:.1f}× margin** |",
        f"| Five-year-old, two-handed grip **on something to hold** | ~{CHILD_GRIP_N:.0f} N | "
        f"{soft/CHILD_GRIP_N:.1f}× margin |",
        f"| Adult, two-handed pull | 200 N+ | none — an adult can force it |",
        "",
        "Read the second row before the first. **Retention force does not separate a child from "
        "an adult.** What separates them is that there is *nothing to grip*: the seam is flush, "
        "there is no lip, no recess and no proud edge anywhere on the shell, so the only force a "
        "child can bring is a pinch on a smooth slab. That is the first row, and it is the one "
        "with the margin in it.",
        "",
        "**The consequence is a rule, not a number:** any feature that gives a fingernail or a "
        "fingertip purchase on the parting line converts row 1 into row 2 and spends the entire "
        "margin. That rules out the recessed thumb-notch every battery cover has, and it is why "
        "the opening feature is a slot for a blade.",
        "",
        f"**The margin is quoted against the softer material on purpose.** We do not choose the "
        f"spool, so every safety number in this document is the worst of the two candidates. In "
        f"PLA the same joint takes {j['separate_n']:.0f} N.",
    ]
    return "\n".join(rows)


def t_creep() -> str:
    run = engaged_run(CART_L)
    j = joint("PLA", run)
    lf_pla, lf_eps = leaf("PLA")
    lf_petg, _ = leaf("PETG")
    rows = [
        "**Closed-position strain: zero. Not near zero — zero, by construction.**",
        "",
        "The groove is cut deeper than the bead stands proud, so when the cartridge is shut the "
        "two halves **do not touch at the bead at all**. The lip snaps past its shoulder and the "
        "wall returns to its undeflected shape. There is no stored spring force holding the "
        "cartridge together; retention is the lip sitting behind the shoulder, which is exactly "
        "the arrangement Decisions 007 §2 asks for.",
        "",
        "**This is a geometric claim, so it is checked as one.** "
        "`hardware/cad/cartridge/test_shell.py` intersects the closed assembly as solids and "
        "asserts the overlap volume is zero, for every variant on the plate. Zero contact means "
        "zero contact force means zero strain — there is no modelling step between the check and "
        "the claim. Its `--mutate` run makes the groove too shallow to seat the bead and asserts "
        "the check goes red; that failure mode prints, assembles, latches and feels correct while "
        "holding the wall deflected for the life of the cartridge.",
        "",
        "| | Strain | Held for | Against PLA's creep threshold (~0.25 %) |",
        "|---|---:|---|---|",
        f"| **Closed** | **0.000 %** | years | no sustained load exists |",
        f"| Snapping open or shut | {j['strain']*100:.2f} % | ~1 s, twice in the cartridge's life | not a creep duty |",
        "",
        "**Why this matters more than the cycle count.** A clasp is engaged 99.99 % of its life. "
        "PLA relaxes at room temperature under sustained strain, and a lip held deflected for a "
        "year loses its grip silently, on a cartridge in a child's pocket. **Cycling was never "
        "the risk** — the cartridge is opened once or twice ever. A design whose closed strain is "
        "zero is indifferent to how creep-prone the spool turns out to be, which is the only kind "
        "of clasp specifiable when we do not choose the material.",
        "",
        "### What the TPU lip was doing, and what replaces it",
        "",
        "Rev 0.1 used a TPU lip to preload the joint against rattle. **That is void** — the "
        "library runs a single spool and a merged STL carries one material for every part in it. "
        "It also introduced 0.086 % of *sustained* strain, which was defensible in PETG and is a "
        "worse idea in PLA.",
        "",
        "**The replacement is to not solve the problem yet.** The coupon on the plate carries no "
        "preload feature at all, so Michael's answer to *does it stay shut when you shake it* "
        "tells us whether rattle is real before anything is designed for it. If it is, the same "
        "feature in the shell's own material is ready:",
        "",
        "| Anti-rattle leaf, if needed | Value |",
        "|---|---:|",
        f"| Section | {LEAF_COUNT} × {LEAF_W:.0f} mm wide, {LEAF_T:.1f} mm thick, "
        f"{LEAF_SPAN:.0f} mm long, deflected {LEAF_DEFL:.2f} mm |",
        f"| Preload | {lf_pla:.1f} N in PLA, {lf_petg:.1f} N in PETG |",
        f"| **Sustained strain** | **{lf_eps*100:.3f} %** — {creep_threshold('PLA')/lf_eps:.1f}× "
        f"under PLA's creep threshold |",
        "",
        "**A short stiff rib cannot do this job and the arithmetic says why.** The gap to close "
        "is 0.10 mm. Deflect a 2.9 mm tall rib by that and it is **1.4 % strain, held forever** — "
        "the exact failure §2 forbids, arrived at while trying to fix rattle. The compliance has "
        "to come from a long, thin leaf: strain falls as the square of the span while force falls "
        "as the cube, so lengthening buys strain faster than it costs force. Same material, same "
        "displacement, twenty times less strain.",
    ]
    return "\n".join(rows)


def t_sweep() -> str:
    run = engaged_run(COUPON_L)
    rows = [
        f"Coupon: **{COUPON_L:.0f} × {COUPON_W:.0f} × {CART_H:.0f} mm**, a real long-wall run "
        f"({run:.0f} mm engaged) with both corner relieves, at full section. Not a whole "
        "cartridge — the run is the thing being swept, and a coupon leaves plate room for more "
        "of them.",
        "",
        f"**Swept in PLA, because that is what the library will load.** Bracketed so both ends "
        "are expected to be wrong: the bottom is at the printer's own repeatability and should "
        "barely engage, and the top is past PLA's permissible strain and is **expected to "
        "crack** — a result, not a wasted part.",
        "",
        "| | Interference | Snap strain | vs PLA 1.0 % | Pull-apart | **Lever** | Expectation |",
        "|---|---:|---:|---|---:|---:|---|",
    ]
    notes = {
        0.10: "at the printer's repeatability — should barely hold",
        0.18: "**the nominal**",
        0.26: "candidate, and the one to beat",
        0.34: "**expected to crack in PLA**",
    }
    levers = []
    for j in sweep_rows("PLA"):
        i = j["interference"]
        lev = joint("PLA", SPUDGER_SPAN, interference=i, walls=1)
        levers.append(lev["separate_n"])
        ok = "ok" if j["strain"] <= permissible("PLA") else "**over**"
        rows.append(f"| | {i:.2f} mm | {j['strain']*100:.2f} % | {ok} | "
                    f"{j['separate_n']:.0f} N | **{lev['separate_n']:.0f} N** | {notes[i]} |")
    rows += [
        "",
        f"**The lever column is the one that matters for the packet**, because it is the force "
        f"Michael's hand actually applies through a blade. It runs {min(levers):.0f}–"
        f"{max(levers):.0f} N across the sweep, so **every variant is openable by hand, including "
        "the one expected to crack.** If the brute-pull column were the operating force the top "
        "two would be untestable and the plate would be worthless.",
        "",
        "**Four bases, four lids** (PM Decisions 007 §1). Rev 0.1 shipped two lids for four "
        "bases, so Michael would have reused a mating half across variants and **wear on the "
        "shared part would be confounded with whichever variant he tested last** — on a plate "
        "whose entire question is retention. The print budget now covers a dedicated lid per "
        "base, so the confound is removed rather than managed with a test order.",
        "",
        "**Each pair is printed together and stays together.** Both halves come off one plate in "
        "one session, which is what holds the interference tolerance at ±"
        f"{TOL_PAIRED:.2f} mm instead of ±{TOL_MIXED:.2f} mm. Mixing halves between pairs is the "
        "one thing that invalidates the ranking, and the card says so.",
        "",
        "**What each result means, decided in advance** so the next plate goes out without "
        "another round of thinking:",
        "",
        "| If the plate says… | Then… |",
        "|---|---|",
        "| A clear winner, and it does not rattle | Print it at cartridge scale and run S-1…S-4 |",
        "| A clear winner **that rattles** | Add the anti-rattle leaf above. Its numbers are ready |",
        "| Nothing holds, including 0.34 | My stiffness estimate is too low. Re-bracket upward |",
        "| Everything holds, including 0.10 | My estimate is too high, and the interference can "
        "shrink until it is comfortably inside the printer's repeatability |",
        "| The top one cracks and the next does not | The PLA permissible-strain estimate is about "
        "right, which also calibrates every other number in this document |",
        "| They all feel the same | Interference is not what the hand reads. Sweep the retention "
        "angle instead, at fixed interference |",
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
    # Decisions 007 §2: the closed clasp must not be held deflected, and the snap
    # must be survivable in the material we do not get to choose. Both are design
    # commitments, so both are assertions rather than prose.
    assert GROOVE_EXTRA > 0.0, \
        "the groove must be deeper than the bead is proud, or the closed strain is not zero"
    worst = joint("PLA", engaged_run(CART_L),
                  interference=INTERFERENCE + TOL_PAIRED)["strain"]
    assert worst <= permissible("PLA"), \
        f"snap strain {worst*100:.2f}% exceeds PLA's permissible at the tolerance limit"


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
