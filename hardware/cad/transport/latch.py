"""Route A transport latch — parametric button carrier, hook bar and test frame.

Route A (Hardware Charter §04): momentary switches under printed button carriers
that latch on a shared hook bar. One solenoid pulls the bar and everything pops.

Only the CARRIER is swept. The bar and the frame are common parts, printed once,
so a variant differs from its neighbours in exactly one number -- which is what
makes the ranking mean anything.

    make -C hardware packet-wp04     build the plate, the STLs and the manifest

Every dimension is a guess until Michael ranks the first plate. That is the point
of the packet: this file is the hypothesis, and the library trip is the test.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict, field

import cadquery as cq

# --------------------------------------------------------------------------
# Common geometry -- shared by every variant, so it cannot confound the sweep
# --------------------------------------------------------------------------

STEM_W = 10.0          # X, across the button row
STEM_D = 8.0           # Y, toward the latch bar
STEM_H = 20.0          # Z, travel plus engagement
CAP_W, CAP_D, CAP_H = 14.0, 11.0, 3.0
SPRING_BORE_D = 4.0
SPRING_BORE_H = 9.0
HOOK_W = 6.0           # X extent of the barb
HOOK_Z_TOP = 8.0       # where the barb starts, up from the stem base
HOOK_Z_TIP = 5.0
HOOK_Z_SHELF = 4.4
HOOK_Z_ROOT = 4.0      # below HOOK_Z_SHELF => the shelf undercuts, resisting release

BAR_L, BAR_D, BAR_H = 70.0, 5.0, 4.0
BAR_CHAMFER = 1.2

FRAME_W, FRAME_D, FRAME_H = 30.0, 26.0, 26.0


@dataclass(frozen=True)
class Variant:
    """One point in the sweep. `label` is what gets embossed; it is deliberately
    unrelated to the parameter value so the ranking is blind."""
    label: str
    hook_depth: float          # THE swept parameter, mm
    carrier_clearance: float = 0.20   # per side, in the frame slot
    role: str = "variant"      # variant | bed-control | orientation-probe
    note: str = ""

    def dict(self) -> dict:
        return asdict(self)


def carrier(v: Variant) -> cq.Workplane:
    """Button carrier with a latching barb of depth `v.hook_depth`."""
    body = (
        cq.Workplane("XY")
        .box(STEM_W, STEM_D, STEM_H, centered=(True, True, False))
        .faces(">Z").workplane()
        .box(CAP_W, CAP_D, CAP_H, centered=(True, True, False), combine=True)
    )

    # Return-spring pocket, up from the base.
    body = (
        body.faces("<Z").workplane(centerOption="CenterOfBoundBox")
        .circle(SPRING_BORE_D / 2).cutBlind(SPRING_BORE_H)
    )

    # The barb, as a profile in the YZ plane extruded across X.
    #   p1 top-at-stem -> p2 tip (the lead-in ramp the bar cams over)
    #   p2 -> p3 tip flat -> p4 shelf back at the stem, slightly lower => undercut
    y_face = -STEM_D / 2
    y_tip = y_face - v.hook_depth
    pts = [
        (y_face, HOOK_Z_TOP),
        (y_tip, HOOK_Z_TIP),
        (y_tip, HOOK_Z_SHELF),
        (y_face, HOOK_Z_ROOT),
    ]
    barb = (
        cq.Workplane("YZ")
        .polyline(pts).close()
        .extrude(HOOK_W / 2, both=True)
    )

    out = body.union(barb)

    # Blind label on the cap. Sunk, so it survives handling and does not add a
    # bump under the thumb that could itself bias the ranking.
    out = (
        out.faces(">Z").workplane(centerOption="CenterOfBoundBox")
        .text(v.label, 5.0, -0.6, combine="cut", font="DejaVu Sans")
    )
    return out


def hook_bar() -> cq.Workplane:
    """Shared latch bar. One per plate -- it is not part of the sweep."""
    bar = cq.Workplane("XY").box(BAR_L, BAR_D, BAR_H, centered=(True, True, False))
    # Chamfer the edge that meets the carrier ramps, so the cam action is defined
    # by the carrier's hook angle rather than by a square corner.
    return bar.edges(">Y and >Z").chamfer(BAR_CHAMFER)


def test_frame(clearance: float = 0.20) -> cq.Workplane:
    """A single-station rig: guides one carrier, carries the bar, and leaves the
    engagement visible so a failure can be seen rather than inferred."""
    slot_w = STEM_W + 2 * clearance
    slot_d = STEM_D + 2 * clearance

    f = cq.Workplane("XY").box(FRAME_W, FRAME_D, FRAME_H, centered=(True, True, False))
    f = (
        f.faces(">Z").workplane(centerOption="CenterOfBoundBox")
        .rect(slot_w, slot_d).cutBlind(-(FRAME_H - 3.0))
    )
    # Bar channel, across X at the barb's height.
    f = (
        f.faces(">X").workplane(centerOption="CenterOfBoundBox")
        .center(0, HOOK_Z_TOP - FRAME_H / 2 + 1.0)
        .rect(BAR_D + 0.6, BAR_H + 0.6).cutThruAll()
    )
    # Inspection window on the front face.
    f = (
        f.faces(">Y").workplane(centerOption="CenterOfBoundBox")
        .center(0, HOOK_Z_TOP - FRAME_H / 2)
        .rect(FRAME_W * 0.5, 10.0).cutThruAll()
    )
    return f


# --------------------------------------------------------------------------
# The sweep
# --------------------------------------------------------------------------

def packet_01_variants() -> list[Variant]:
    """Packet 01: bracket hook depth WIDE.

    The charter suggests 0.8-1.8 mm. This goes 0.6-2.1, deliberately wider, so
    both endpoints are expected to be obviously wrong: 0.6 mm should barely hold
    and 2.1 mm should be stiff to press and reluctant to pop. If all eight feel
    alike, the bracket was too narrow and the week is wasted -- so it is better
    to overshoot on the first plate and refine on the second.

    C and its two controls are the same geometry. They are ranked blind alongside
    the real variants, which tests the print and the ranker at the same time:
      * if the three C's do not cluster, bed position or print noise is larger
        than the parameter and the sweep needs coarser steps
      * if they do cluster, the ranking is trustworthy
    """
    return [
        Variant("K", 0.6, note="expected too shallow -- should not hold"),
        Variant("R", 0.9),
        Variant("M", 1.2, note="centre of the bracket"),
        Variant("T", 1.5),
        Variant("B", 1.8),
        Variant("W", 2.1, note="expected too deep -- stiff, reluctant to release"),
        Variant("D", 1.2, role="bed-control", note="duplicate of M, far bed corner"),
        Variant("H", 1.2, role="bed-control", note="duplicate of M, near bed corner"),
    ]


def orientation_probe() -> Variant:
    """Not ranked. Printed on its side to test whether layer orientation, rather
    than geometry, governs whether the barb survives 200 cycles.

    Upright printing puts the barb root on a layer interface, which is the weak
    direction -- but it also puts hook_depth in the XY plane, where FDM accuracy
    is best, and hook_depth is the thing being measured. Upright is the right
    choice for the sweep; this part is how we find out what it cost.
    """
    return Variant("X", 1.2, role="orientation-probe",
                   note="same as M, printed on its side")
