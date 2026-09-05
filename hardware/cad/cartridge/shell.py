"""Cartridge shell clasp — parametric coupon for the interference sweep.

WP-24, and the deliverable PM Decisions 006 §2 asks for. The mechanics are in
`hardware/mech/clasp.py`; this file is the geometry that realises them, and the
two must agree or the plate tests something the spec does not describe.

**What is swept: interference, and nothing else.** Wall section, span, ramp
angles, corner relief and seam are identical across every variant, so a ranking
means one thing.

Three geometric commitments carry the whole design, and each is here rather than
in prose because prose cannot be checked:

  1. **The engagement stops short of the corners.** A continuous perimeter lip is
     the right instinct about load spreading and the wrong answer at a corner: a
     rectangular box cannot open at a corner by bending, only by stretching, and
     stretching is rigid. So the SEAM is continuous -- that is what hides it --
     and the ENGAGEMENT is not.
  2. **The bead seats with clearance.** The groove is deeper than the bead is
     tall. That is what makes the resting strain ~0.09 % instead of 0.75 %, and
     it is the entire answer to "does PETG creep".
  3. **The parting line sits on a 45 deg chamfer**, split half to each half, so a
     print-to-print step across the seam reads as part of the chamfer rather
     than as a ridge that catches the light.

This is a COUPON, not a cartridge: one long-wall run at full section with both
corner relieves. A whole cartridge does not fit on the plate beside WP-04, and
the run is the thing being swept.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict

import cadquery as cq

# --------------------------------------------------------------------------
# Common geometry -- shared by every variant, so it cannot confound the sweep
# --------------------------------------------------------------------------

L, W = 62.0, 28.0          # coupon footprint
FLOOR = 1.5
SPAN = 6.0                 # floor top to the bead: the cantilever length
WALL_NOM = 2.0
WALL_RET = 1.2             # thinned local to the engaged run
CORNER_RELIEF = 9.0        # engagement stops this far short of each corner

SWEEP_INTERFERENCE = (0.15, 0.25, 0.35, 0.45)

BEAD_Z = FLOOR + SPAN                  # 7.5 -- bead tip centre, the cantilever's load point
BEAD_FLAT = 0.20                       # tip land
LEAD_DEG, RETAIN_DEG = 25.0, 40.0      # from the PULL AXIS -- see clasp.py

TONGUE_CLEAR = 0.10        # per side, tongue to thinned wall
TONGUE_H = 4.5             # lid tongue insertion depth
GROOVE_EXTRA = 0.05        # groove deeper than the bead is proud -> the bead seats FREE
CLOSED_H = 12.0            # cartridge thickness

SEAM_CHAMFER = 0.5         # per half; 1.0 mm across the closed seam

SLOT_W, SLOT_L, SLOT_D = 0.9, 12.0, 2.5    # the opening feature
SLOT_X = -15.0                              # offset from centre, away from a corner

TPU_T, TPU_H = 0.8, 2.0    # the lip seal, printed as its own part

def _ramp_rise(projection: float, angle_deg: float) -> float:
    """Vertical extent of a ramp of horizontal `projection` at `angle_deg` from
    the pull axis. Shallower faces are TALLER, which is why the lead-in is the
    tall one and the retention face is the short one."""
    return projection / math.tan(math.radians(angle_deg))


# ---- Heights, DERIVED from the worst-case variant ------------------------
#
# These were literals in the first draft and it was a bug with teeth: a deeper
# bead has a taller lead-in ramp, so the bases came out 8.4, 8.4, 8.6 and 8.8 mm
# tall. In a BLIND sweep that is not a cosmetic defect -- the deepest variant is
# visibly the tallest, and the ranking stops being blind. Every shared dimension
# is now sized for max(SWEEP_INTERFERENCE) and is identical across the plate.

_MAX_PROUD = TONGUE_CLEAR + max(SWEEP_INTERFERENCE)

# The top of the wall IS the lead-in ramp -- no land above it -- so the rim is as
# low as the deepest bead allows.
H_BASE = round(BEAD_Z + BEAD_FLAT / 2 + _ramp_rise(_MAX_PROUD, LEAD_DEG) + 0.05, 1)
H_LID = CLOSED_H - H_BASE + TONGUE_H

# Groove depth is measured from the tongue's full-width face, and the bead only
# stands `interference` proud of THAT (the rest of `proud` is the running
# clearance). Sizing it from `proud` instead over-cut it by 0.10 mm.
GROOVE_DEPTH = max(SWEEP_INTERFERENCE) + GROOVE_EXTRA

# Where the deepest bead's retention face bottoms out, mapped into lid
# coordinates: the lid's shoulder lands on the base's rim, so
# lid_z = TONGUE_H - (H_BASE - base_z). Everything below this is the tongue's
# foot -- the shoulder the bead actually catches.
_BEAD_BOT = BEAD_Z - BEAD_FLAT / 2 - _ramp_rise(_MAX_PROUD, RETAIN_DEG)
FOOT_H = round(TONGUE_H - (H_BASE - _BEAD_BOT), 2)


@dataclass(frozen=True)
class Shell:
    """One point in the sweep. `label` is embossed and is deliberately unrelated
    to the interference, so the ranking is blind (ADR-104)."""
    label: str
    interference: float        # THE swept parameter, mm, total across both halves
    role: str = "variant"      # variant | bed-control
    note: str = ""

    def dict(self) -> dict:
        return asdict(self)

    @property
    def bead_proud(self) -> float:
        """How far the bead stands off the thinned wall's inner face."""
        return TONGUE_CLEAR + self.interference


def _bead_profile(y_face: float, proud: float, sign: float) -> cq.Workplane:
    """The bead, as a YZ profile extruded along X. `sign` is +1 for the +Y wall.

    Four points: up the wall face to the lead-in top, in and down to the tip
    land, down the land, then out and down to the wall face. The retention face
    is the short one because it is the steep one.
    """
    y_tip = y_face - sign * proud
    z_lead = BEAD_Z + BEAD_FLAT / 2 + _ramp_rise(proud, LEAD_DEG)
    z_ret = BEAD_Z - BEAD_FLAT / 2 - _ramp_rise(proud, RETAIN_DEG)
    pts = [
        (y_face, z_lead),
        (y_tip, BEAD_Z + BEAD_FLAT / 2),
        (y_tip, BEAD_Z - BEAD_FLAT / 2),
        (y_face, z_ret),
    ]
    return cq.Workplane("YZ").polyline(pts).close().extrude(L / 2 + 1.0, both=True)


def engaged_run() -> float:
    """Retention runs the long walls and stops short of the corners.

    A rectangular box cannot open at a corner by bending, only by stretching,
    and stretching is rigid. So the SEAM is continuous -- that is what hides it
    -- and the ENGAGEMENT is not.
    """
    return L - 2 * CORNER_RELIEF


def base(v: Shell) -> cq.Workplane:
    """The half that flexes. Carries the bead, the thinned run and the slot."""
    body = (
        cq.Workplane("XY")
        .box(L, W, H_BASE, centered=(True, True, False))
        .edges(">Z").chamfer(SEAM_CHAMFER)
    )
    # Cavity
    body = body.cut(
        cq.Workplane("XY")
        .box(L - 2 * WALL_NOM, W - 2 * WALL_NOM, H_BASE - FLOOR, centered=(True, True, False))
        .translate((0, 0, FLOOR)))

    run = engaged_run()
    y_in = W / 2 - WALL_RET          # inner face after thinning

    # Clip every added feature to the run AND to the rim, so all four bases are
    # the same 62 x 28 x H_BASE box whatever the bead does.
    envelope = cq.Workplane("XY").box(run, W, H_BASE, centered=(True, True, False))

    for sign in (1.0, -1.0):
        # Thin the wall from WALL_NOM to WALL_RET over the engaged run only.
        # The strip runs from the old inner face out to the new one.
        y_lo = min(sign * (W / 2 - WALL_NOM), sign * (W / 2 - WALL_RET))
        relief = (
            cq.Workplane("XY")
            .box(run, WALL_NOM - WALL_RET, H_BASE - FLOOR, centered=(True, False, False))
            .translate((0, y_lo, FLOOR)))
        body = body.cut(relief)

        # Bead, clipped so the corners stay rigid and the rim stays flat.
        body = body.union(_bead_profile(sign * y_in, v.bead_proud, sign).intersect(envelope))

    # The opening feature: a blade-width slot through the seam chamfer, placed
    # mid-run rather than at a corner, because the lever has to start where the
    # wall can move.
    body = body.cut(
        cq.Workplane("XY")
        .box(SLOT_L, WALL_NOM * 2, SLOT_D, centered=(True, True, False))
        .translate((SLOT_X, -(W / 2), H_BASE - SLOT_D)))

    # Blind label, sunk into the outside of the floor.
    return (
        body.faces("<Z").workplane(centerOption="CenterOfBoundBox")
        .text(v.label, 7.0, -0.6, combine="cut", font="DejaVu Sans"))


def lid(label: str = "") -> cq.Workplane:
    """The common half. Not swept -- one geometry mates every variant.

    Two are printed, and they are a control in WP-04's sense: if the ranking
    tracks which lid was used rather than which base, the shared part is wearing
    and the sweep is measuring that instead of the interference.

    **The tongue has ears.** It is not a plain rectangle, and the reason is the
    one thing in this file that a reader will otherwise get wrong. The base's
    wall is thinned to WALL_RET only over the engaged run, because that thinning
    IS the cantilever -- 1.2 mm over the full 6.0 mm from floor to bead, which is
    the span `clasp.py` computes the strain from. Everywhere else the wall stays
    WALL_NOM for stiffness and drop survival.

    So the cavity is two different widths, and a rectangular tongue wide enough
    to reach the beads fouls the corners. The tempting fix -- thin the whole rim
    -- moves the flexing span from 6.0 mm down to 3.2 mm, and strain goes as the
    square of it: 0.75 % becomes 2.6 %, past PETG's permissible and well past
    PLA's. **That fix would have printed, assembled, felt fine on the bench, and
    quietly invalidated the entire analysis.** The ears are the honest answer.

    Built from chamfered boxes unioned, rather than one box chamfered after
    cutting, so every selector acts on a plain box where `<Z` means exactly four
    edges and cannot pick up a face a later cut created.
    """
    core_l = L - 2 * WALL_NOM - 2 * TONGUE_CLEAR
    core_w = W - 2 * WALL_NOM - 2 * TONGUE_CLEAR
    ear_l = engaged_run() - 2 * TONGUE_CLEAR
    ear_w = W - 2 * WALL_RET - 2 * TONGUE_CLEAR

    # Visible half, above the seam. Its lower outer edge is half the seam V.
    visible = (
        cq.Workplane("XY")
        .box(L, W, H_LID - TONGUE_H, centered=(True, True, False))
        .edges("<Z").chamfer(SEAM_CHAMFER)
        .translate((0, 0, TONGUE_H)))

    # Tongue core: clears the full-thickness wall everywhere.
    core = (
        cq.Workplane("XY")
        .box(core_l, core_w, TONGUE_H, centered=(True, True, False))
        .edges("<Z").chamfer(0.35))

    # Ears: reach out to the thinned run, where the beads are. The foot is the
    # shoulder the bead catches; above it the ear steps in by GROOVE_DEPTH, and
    # that step is the groove -- open at the top so the whole bead enters it.
    foot = (
        cq.Workplane("XY")
        .box(ear_l, ear_w, FOOT_H, centered=(True, True, False))
        .edges("<Z").chamfer(0.35))          # meets the bead's lead-in ramp
    blade = (
        cq.Workplane("XY")
        .box(ear_l, ear_w - 2 * GROOVE_DEPTH, TONGUE_H - FOOT_H,
             centered=(True, True, False))
        .translate((0, 0, FOOT_H)))

    body = visible.union(core).union(foot).union(blade)

    # Hollow it from the top, leaving FLOOR.
    body = body.cut(
        cq.Workplane("XY")
        .box(L - 2 * WALL_NOM, W - 2 * WALL_NOM, H_LID, centered=(True, True, False))
        .translate((0, 0, TONGUE_H)))

    if label:
        body = (body.faces(">Z").workplane(centerOption="CenterOfBoundBox")
                .text(label, 7.0, -0.6, combine="cut", font="DejaVu Sans"))
    return body


def tpu_lip() -> cq.Workplane:
    """The TPU lip seal — a bending lip, NOT a compressed gasket.

    The arithmetic is in clasp.py and it is the reason for the shape: this
    section develops ~22 N over the perimeter, where the same rubber squashed the
    same distance as a solid gasket develops several hundred and would hold the
    shell open. The compliance has to come from the shape, not the material.

    It cannot be printed at the library -- PLA only -- so it ships as its own
    file and waits for a machine that runs TPU.
    """
    half_l = (L - 2 * WALL_NOM - 2 * TONGUE_CLEAR) / 2
    half_w = (W - 2 * WALL_NOM - 2 * TONGUE_CLEAR) / 2
    outer = cq.Workplane("XY").box(half_l * 2, half_w * 2, TPU_H, centered=(True, True, False))
    inner = cq.Workplane("XY").box(half_l * 2 - 2 * TPU_T, half_w * 2 - 2 * TPU_T, TPU_H,
                                   centered=(True, True, False))
    return outer.cut(inner)


# --------------------------------------------------------------------------
# The sweep
# --------------------------------------------------------------------------

def packet_variants() -> list[Shell]:
    """Four interferences, bracketed so both ends are expected to be wrong.

    The plate prints in PLA and the design is for PETG. PLA is roughly twice as
    stiff and half as extensible, so 0.45 mm is over PLA's permissible strain and
    is EXPECTED to crack -- which is a result, not a wasted part. 0.15 mm should
    be too loose to hold. If neither endpoint misbehaves, the bracket was too
    narrow and the trip bought nothing.
    """
    return [
        Shell("N", 0.15, note="expected too loose -- should rattle or fall open"),
        Shell("G", 0.25),
        Shell("A", 0.35, note="at PLA's permissible strain"),
        Shell("Q", 0.45, note="expected to crack in PLA; comfortable in PETG"),
    ]
