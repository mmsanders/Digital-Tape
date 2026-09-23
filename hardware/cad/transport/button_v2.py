#!/usr/bin/env python3
"""Button latch test, revision 2 — packet A1MINI-BTN-02.

Rev 1 could not have worked. In `latch.py` the frame's bar channel is cut on the
frame's own Y centre (y in [-2.8, +2.8]) while the carrier stem occupies
y in [-4.0, +4.0]: the bar and the button want the same volume. With the carrier
in, the bar cannot pass; with the bar in, the carrier cannot drop.

Moving the BOX cannot fix that, which is why the second attempt also failed. The
barb protrudes to y = -4 - hook_depth, OUTSIDE the stem's -Y face, so the bar has
to sit in front of that face. The bar was the part in the wrong place.

So this revision moves the bar, and `assert_no_interference()` below fails the
build if the bar volume and the stem volume overlap by so much as a micron. The
defect that produced the last round cannot be shipped again quietly.

ONE QUESTION. Nothing has ever latched, so a blind eight-point ranking is
premature -- it would rank a mechanism nobody has seen work. This plate asks only:
*does it latch, and does it release?* Three engagement depths and one no-barb
control that MUST NOT latch. If the control latches, the rig is gripping by
friction and every other result on the plate is void.

NO SPRING NEEDED. Rev 1 wanted a return spring nobody owns. Here the cap rests on
the post tops under its own weight, you press it down until it clicks, and it
stays down -- that is the latch. Pull the bar forward and it comes free -- that is
the release. Two observations, zero bought parts.

    python3 button_v2.py        writes the packet
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import cadquery as cq
from cadquery import exporters

OUT = Path(__file__).resolve().parents[2] / "packets" / "a1mini-btn-02"

# --- carrier ---------------------------------------------------------------
STEM_W, STEM_D, STEM_H = 10.0, 8.0, 18.0
CAP_W, CAP_D, CAP_H = 14.0, 12.0, 3.0
SHELF_Z = 6.0             # stem-local height of the catching shelf
RAMP_H = 2.5              # the lead-in the bar cams over on the way down
BARB_W = 6.0              # X extent of the barb
TONGUE_T = 1.6            # the flexing wall
SLOT_D = 3.0              # relief behind it
TONGUE_ROOT_Z = 12.0      # slot runs base -> here; fixed at top, free at bottom

# --- frame -----------------------------------------------------------------
BASE_T = 3.0
POST_W = 8.0
POST_Y0, POST_Y1 = -12.0, 12.0
GUIDE_CLR = 0.25          # per side, stem to post
TRAVEL = 8.0              # rest height above the latched position
BACKWALL_Y0 = STEM_D / 2 + GUIDE_CLR   # touches the stem's back face

# --- bar -------------------------------------------------------------------
BAR_L, BAR_D, BAR_H = 46.0, 4.0, 4.0
BAR_AIR = 0.4             # air gap, stem face to bar near face
BAR_SLOT_CLR = 0.5

# Derived. Latched, the stem sits on the base and the shelf catches the bar's
# underside; at rest the whole barb must clear the bar's top by REST_GAP.
Z_LATCH = BASE_T
Z_REST = Z_LATCH + TRAVEL
BAR_Z0 = Z_LATCH + SHELF_Z
BAR_Z1 = BAR_Z0 + BAR_H
REST_GAP = (Z_REST + SHELF_Z - RAMP_H) - BAR_Z1
POST_H = Z_REST + STEM_H
BAR_Y1 = -STEM_D / 2 - BAR_AIR        # near face
BAR_Y0 = BAR_Y1 - BAR_D               # far face


@dataclass(frozen=True)
class Btn:
    label: str
    hook_depth: float
    note: str = ""

    @property
    def engagement(self) -> float:
        """How much barb actually overlaps the bar. THE number under test."""
        return self.hook_depth - BAR_AIR


VARIANTS = (
    Btn("A", 1.0, "shallowest that can engage at all"),
    Btn("B", 1.4, "centre"),
    Btn("C", 1.8, "deepest"),
    Btn("N", 0.0, "NO BARB -- must not latch. If it does, the rig grips by "
                  "friction and the other three results are void"),
)


def carrier(v: Btn) -> cq.Workplane:
    body = (cq.Workplane("XY")
            .box(STEM_W, STEM_D, STEM_H, centered=(True, True, False))
            .faces(">Z").workplane()
            .box(CAP_W, CAP_D, CAP_H, centered=(True, True, False), combine=True))

    # Relief slot: leaves a tongue on the -Y wall, fixed at the top, free at the
    # bottom where the barb is. Flexing inward is what lets the barb pass the bar.
    y0 = -STEM_D / 2 + TONGUE_T
    body = body.cut(cq.Workplane("XY")
                    .box(BARB_W + 1.0, SLOT_D, TONGUE_ROOT_Z,
                         centered=(True, False, False))
                    .translate((0, y0, 0)))

    if v.hook_depth > 0:
        # Flat shelf on TOP (catches under the bar), ramp BELOW it (the bar cams
        # over this on the way down). Rev 1 had these the other way up.
        yf, yt = -STEM_D / 2, -STEM_D / 2 - v.hook_depth
        barb = (cq.Workplane("YZ")
                .polyline([(yf, SHELF_Z), (yt, SHELF_Z), (yf, SHELF_Z - RAMP_H)])
                .close().extrude(BARB_W / 2, both=True))
        body = body.union(barb)

    return (body.faces(">Z").workplane(centerOption="CenterOfBoundBox")
            .text(v.label, 7.0, -0.8, combine="cut", font="DejaVu Sans"))


def frame() -> cq.Workplane:
    """Two posts, a back wall, an open front. The engagement is visible and a
    stuck part can be freed with a fingernail rather than a knife."""
    half_gap = STEM_W / 2 + GUIDE_CLR
    w = 2 * (half_gap + POST_W)
    f = (cq.Workplane("XY")
         .box(w, POST_Y1 - POST_Y0, BASE_T, centered=(True, False, False))
         .translate((0, POST_Y0, 0)))
    for sx in (-1, 1):
        post = (cq.Workplane("XY")
                .box(POST_W, POST_Y1 - POST_Y0, POST_H, centered=(False, False, False))
                .translate((half_gap if sx > 0 else -half_gap - POST_W, POST_Y0, 0)))
        # Bar slot: open to -Y so the bar pulls straight out. That open end IS
        # the release, standing in for the solenoid.
        post = post.cut(cq.Workplane("XY")
                        .box(POST_W * 2, (BAR_Y1 + BAR_SLOT_CLR) - POST_Y0,
                             BAR_H + 2 * BAR_SLOT_CLR, centered=(False, False, False))
                        .translate((half_gap - POST_W if sx > 0 else -half_gap - POST_W,
                                    POST_Y0, BAR_Z0 - BAR_SLOT_CLR)))
        f = f.union(post)
    # Back wall guides the stem in Y; the front stays open on purpose.
    f = f.union(cq.Workplane("XY")
                .box(w, POST_Y1 - BACKWALL_Y0, POST_H, centered=(False, False, False))
                .translate((-w / 2, BACKWALL_Y0, 0)))
    return f


def bar() -> cq.Workplane:
    return (cq.Workplane("XY")
            .box(BAR_L, BAR_D, BAR_H, centered=(True, False, False))
            .translate((0, BAR_Y0, BAR_Z0))
            .edges("|X and >Z and <Y").chamfer(1.0))


def assert_no_interference() -> None:
    """The rev-1 defect, as a build-time gate.

    The bar's Y span and the stem's Y span must not overlap at all, and the barb
    must actually reach into the bar. Rev 1 shipped because nothing checked this.
    """
    assert BAR_Y1 <= -STEM_D / 2, (
        f"bar near face {BAR_Y1} is inside the stem (-{STEM_D/2}) -- this is the "
        f"rev-1 defect: the bar and the button want the same volume")
    for v in VARIANTS:
        if v.hook_depth <= 0:
            continue
        assert v.engagement > 0, f"{v.label}: barb never reaches the bar"
        assert v.engagement < BAR_D, f"{v.label}: barb passes clean through the bar"
    assert REST_GAP > 0, (
        f"at rest the barb overlaps the bar by {-REST_GAP:.2f} mm; it would be "
        f"latched before anyone pressed it")
    assert Z_REST + STEM_H == POST_H, "cap does not rest on the post tops"
    # And the cap must be wider than the gap, or there is nothing to rest ON.
    assert CAP_W > STEM_W + 2 * GUIDE_CLR, "cap falls through the guide slot"
    # The stem must be pinched between the back wall and the bar, or it rocks
    # back, unhooks, and the plate measures slop instead of engagement.
    slop = (BACKWALL_Y0 - STEM_D / 2) + (-STEM_D / 2 - BAR_Y1)
    assert slop <= 1.0, f"{slop:.2f} mm of Y slop; the button can tilt out of engagement"


def build() -> int:
    assert_no_interference()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "stl").mkdir(exist_ok=True)

    # Carriers lie down, stem axis along bed X, so the tongue flexes IN-PLANE
    # rather than across the layer bonds. Upright, every press would be pulling
    # layers apart -- which would test the printer, not the design.
    placed, x = [], 0.0
    for v in VARIANTS:
        part = carrier(v).rotate((0, 0, 0), (0, 1, 0), -90)
        exporters.export(part, str(OUT / "stl" / f"button-{v.label}.stl"))
        b = part.val().BoundingBox()
        placed.append(part.translate((x - b.xmin, -b.ymin, -b.zmin)))
        x += b.xlen + 6.0

    fr = frame()
    exporters.export(fr, str(OUT / "stl" / "frame.stl"))
    b = fr.val().BoundingBox()
    placed.append(fr.translate((-b.xmin, -b.ymin + 30.0, -b.zmin)))

    br = bar().rotate((0, 0, 0), (1, 0, 0), 0)
    exporters.export(br, str(OUT / "stl" / "bar.stl"))
    b = br.val().BoundingBox()
    placed.append(br.translate((-b.xmin, -b.ymin + 70.0, -b.zmin)))

    plate = placed[0]
    for p in placed[1:]:
        plate = plate.union(p)
    bb = plate.val().BoundingBox()
    assert bb.xlen < 160 and bb.ylen < 160 and bb.zlen < 175, "off the A1 mini bed"

    exporters.export(plate, str(OUT / "plate.stl"))
    (OUT / "manifest.json").write_text(json.dumps({
        "packet": "A1MINI-BTN-02", "revision": 2,
        "printer": "Bambu Lab A1 Mini", "nozzle_mm": 0.4,
        "material": "Bambu PLA Basic",
        "travel_mm": TRAVEL, "rest_clearance_mm": round(REST_GAP, 3),
        "bar_air_gap_mm": BAR_AIR,
        "bar_y": [BAR_Y0, BAR_Y1], "stem_y": [-STEM_D / 2, STEM_D / 2],
        "bar_z": [BAR_Z0, BAR_Z1],
        "variants": [{"label": v.label, "hook_depth_mm": v.hook_depth,
                      "engagement_mm": round(v.engagement, 3), "note": v.note}
                     for v in VARIANTS],
        "blind": False,
        "blind_rationale": "nothing has latched yet; this asks whether the "
                           "mechanism works at all, and 'did it click' cannot "
                           "be biased by knowing the depths",
    }, indent=2) + "\n")
    print(f"  A1MINI-BTN-02: {len(placed)} objects, "
          f"{bb.xlen:.0f} x {bb.ylen:.0f} x {bb.zlen:.0f} mm")
    print(f"  travel {TRAVEL} mm, rest clearance {REST_GAP:.2f} mm, "
          f"engagements {[round(v.engagement,2) for v in VARIANTS if v.hook_depth]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
