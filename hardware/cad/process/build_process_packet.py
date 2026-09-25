#!/usr/bin/env python3
"""Build print packet A1MINI-01: what Michael's own printer actually does.

    make -C hardware packet-a1mini

**Why this print exists.** The held cartridge-clasp sweep asks Michael to rank
four interference fits at 0.10, 0.18, 0.26 and 0.34 mm. Those steps are 0.08 mm
apart. Nobody has measured what this printer's own clearance error is, and if it
is larger than 0.08 mm the sweep cannot mean anything -- four variants would
differ by less than the machine's own noise, and whichever one Michael preferred
would be telling us about the printer, not about the design. `RG-3` in
`spec/hw/ruggedization.md` says the same thing in one line: the printer,
material and process are uncharacterized.

So this plate is printed BEFORE the clasp sweep, not after, and it answers one
question: **how far off is a hole on this machine, in this filament?**

**Designed for the instruments Michael actually owns.** `spec/hw/ruggedization.md`
RG-7 lists them: a sensitive food-preparation scale, ordinary screwdrivers and
sockets, and likely a soldering iron. **No calipers.** A coupon plate that has to
be measured with calipers is not a plate that can be measured, so nothing here
asks for a dimension to be read off. Two things are asked for instead:

  the fit ladder   six sockets at known, increasing clearance and one pin. Michael
                   reports which sockets the pin enters. That brackets the
                   machine's effective clearance to one 0.05 mm step using his
                   hands and nothing else -- and 0.05 mm is finer than the
                   0.08 mm the clasp sweep needs to resolve.

  the mass coupons three identical blocks of exactly known modelled volume. The
                   kitchen scale gives their mass, and mass over modelled volume
                   is an effective density: it catches under-extrusion, and the
                   spread across three catches print-to-print repeatability.

**What it cannot establish.** Not a dimension, not a tolerance, not a material
property, not a qualification of anything. A fit ladder brackets one clearance in
one orientation on one plate in one session. It is a precondition for reading the
clasp sweep, not evidence about the clasp.

Outputs into hardware/packets/a1mini-01/:
    plate.stl          the deliverable -- one merged solid
    plate.3mf          preview
    stl/<part>.stl     individual parts, if one needs reprinting alone
    CARD.md            the one page Michael works from
    RESULTS.md         what he brings back
    plate-map.md       which coupon sits where on the bed

Nothing here is blind. The clasp sweep is blind because a ranking can be
contaminated by knowing the answer; "which socket did the pin enter" cannot be,
and hiding the clearances would only stop Michael noticing if a socket were
mislabelled.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cadquery as cq
from cadquery import exporters

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "transport"))
# Reuse the packet plumbing rather than reimplementing it. The 3MF determinism
# in particular was hard-won -- see the octal-escape note in that module -- and a
# second copy of it would drift. This imports; it changes nothing there.
from build_packet import (                                    # noqa: E402
    check_3mf, check_stl, normalise_3mf, pack, validate,
)

OUT = Path(__file__).resolve().parents[2] / "packets" / "a1mini-01"

# The A1 Mini's nominal build volume. Held PR #92 confirmed 180 x 180 x 180 mm
# as the nominal envelope; this packet is laid out independently of that PR and
# does not depend on it.
BED_X, BED_Y, BED_Z = 180.0, 180.0, 180.0
MARGIN = 12.0            # mm, XY, from each of the four nominal edges
GAP = 4.0                # mm between objects
MAX_Z = 175.0            # mm, 5 mm under the nominal height
PACKET_REVISION = 1
PACKET_RELEASE_DATE = "2026-09-20"

# --- the fit ladder ---------------------------------------------------------
#
# Diametral clearance, in millimetres, socket minus pin. The steps are 0.05 mm
# because that is half the 0.10 mm smallest step in the clasp sweep: a ladder
# coarser than the thing it calibrates would not calibrate it.
#
# Zero is included deliberately and is expected NOT to accept the pin. A ladder
# whose every rung passes has measured nothing -- it would be consistent with any
# clearance at all below the smallest rung. The zero rung is this plate's own
# negative control, and if the pin enters it freely that is a real result meaning
# the machine prints holes oversize.
CLEARANCES_MM = (0.00, 0.05, 0.10, 0.15, 0.20, 0.25)

PIN_D = 8.00             # mm, the nominal both halves are cut to
PIN_LEN = 22.0           # mm of shank
PIN_GRIP_D = 16.0        # mm, a flange wide enough for fingers
PIN_GRIP_H = 4.0         # mm
SOCKET_DEPTH = 9.0       # mm, deeper than the 8 mm of shank that needs to enter
LADDER_PITCH = 14.0      # mm between socket centres
LADDER_W = 18.0          # mm across
LADDER_H = 12.0          # mm tall
INDEX_MARK = 2.5         # mm, the corner cut that says which end is socket 1

# --- the mass coupons -------------------------------------------------------
MASS_X, MASS_Y, MASS_Z = 20.0, 20.0, 6.0
MASS_COUNT = 3


def fit_ladder() -> cq.Workplane:
    """One block, six sockets, increasing clearance left to right."""
    length = LADDER_PITCH * len(CLEARANCES_MM) + 8.0
    block = cq.Workplane("XY").box(length, LADDER_W, LADDER_H,
                                   centered=(True, True, False))
    x0 = -length / 2 + LADDER_PITCH / 2 + 4.0
    for i, clearance in enumerate(CLEARANCES_MM):
        block = (block.faces(">Z").workplane()
                 .pushPoints([(x0 + i * LADDER_PITCH, 0)])
                 .hole(PIN_D + clearance, SOCKET_DEPTH))
    # The index cut. Socket 1 is the end with the chamfered corner, so the block
    # cannot be read backwards -- which would invert the whole ladder and turn a
    # tight machine into a loose one in the write-up.
    mark = (cq.Workplane("XY")
            .box(INDEX_MARK * 2, INDEX_MARK * 2, LADDER_H * 3,
                 centered=(True, True, True))
            .rotate((0, 0, 0), (0, 0, 1), 45)
            .translate((-length / 2, -LADDER_W / 2, LADDER_H / 2)))
    return block.cut(mark)


def fit_pin() -> cq.Workplane:
    """The pin, with a flange so a hand can push and pull it."""
    return (cq.Workplane("XY")
            .circle(PIN_GRIP_D / 2).extrude(PIN_GRIP_H)
            .faces(">Z").workplane()
            .circle(PIN_D / 2).extrude(PIN_LEN))


def mass_coupon() -> cq.Workplane:
    """A plain block. Its whole job is to have an exactly known modelled volume."""
    return cq.Workplane("XY").box(MASS_X, MASS_Y, MASS_Z,
                                  centered=(True, True, False))


def modelled_volume_mm3(shape) -> float:
    return shape.val().Volume()


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "stl").mkdir(exist_ok=True)

    items, parts = [], {}
    ladder = fit_ladder()
    parts["fit-ladder"] = ladder
    items.append(("fit-ladder", ladder.val()))

    # Two pins: one to push, one kept untouched as a reference. If the first is
    # damaged getting it out of a tight socket, the session is not over.
    pin = fit_pin()
    parts["fit-pin"] = pin
    for n in (1, 2):
        items.append((f"fit-pin-{n}", pin.val()))

    coupon = mass_coupon()
    parts["mass-coupon"] = coupon
    for n in range(1, MASS_COUNT + 1):
        items.append((f"mass-coupon-{n}", coupon.val()))

    for name, shape in parts.items():
        exporters.export(shape, str(OUT / "stl" / f"{name}.stl"))

    placed = pack(items, bed_x=BED_X, bed_y=BED_Y, margin=MARGIN, gap=GAP)
    ok, problems = validate(placed, bed_x=BED_X, bed_y=BED_Y)
    if not ok:
        raise SystemExit("plate does not fit the bed:\n  " + "\n  ".join(problems))

    plate = placed[0][1]
    for _, shape, *_ in placed[1:]:
        plate = plate.fuse(shape)

    b = plate.BoundingBox()
    if b.zmax > MAX_Z:
        raise SystemExit(f"plate is {b.zmax:.1f} mm tall, over the {MAX_Z} mm cap")

    exporters.export(cq.Workplane(obj=plate), str(OUT / "plate.stl"))
    check_stl(OUT / "plate.stl", plate)
    exporters.export(cq.Workplane(obj=plate), str(OUT / "plate.3mf"))
    normalise_3mf(OUT / "plate.3mf")
    check_3mf(OUT / "plate.3mf")

    manifest = {
        "packet": "A1MINI-01",
        "revision": PACKET_REVISION,
        "released": PACKET_RELEASE_DATE,
        "printer": "Bambu Lab A1 Mini (Michael's own)",
        "bed_mm": [BED_X, BED_Y, BED_Z],
        "margin_mm": MARGIN,
        "max_z_mm": MAX_Z,
        "material": "Bambu PLA Basic, white -- the spool already owned",
        "pin_nominal_mm": PIN_D,
        "socket_clearances_mm": list(CLEARANCES_MM),
        "mass_coupon_mm": [MASS_X, MASS_Y, MASS_Z],
        "mass_coupon_modelled_volume_mm3": round(modelled_volume_mm3(coupon), 3),
        "mass_coupon_count": MASS_COUNT,
        "objects": len(items),
        "blind": False,
        "blind_rationale":
            "nothing is hidden: a socket-entry observation cannot be biased by "
            "knowing the clearances, and hiding them would only stop Michael "
            "noticing a mislabelled rung",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    rows = ["| Object | X mm | Y mm | W mm | D mm |", "|---|---:|---:|---:|---:|"]
    for name, _shape, x, y, w, h in sorted(placed, key=lambda p: (p[3], p[2])):
        rows.append(f"| `{name}` | {x:.1f} | {y:.1f} | {w:.1f} | {h:.1f} |")
    (OUT / "plate-map.md").write_text(
        f"# A1MINI-01 rev {PACKET_REVISION} — plate map\n\n"
        f"Bed {BED_X:.0f} × {BED_Y:.0f} mm, {MARGIN:.0f} mm margin, "
        f"{GAP:.0f} mm between objects. Origin is the front-left bed corner.\n\n"
        + "\n".join(rows) + "\n")

    print(f"  packet A1MINI-01 rev {PACKET_REVISION}: {len(items)} objects, "
          f"bbox {b.xlen:.1f} x {b.ylen:.1f} x {b.zlen:.1f} mm")
    print(f"  mass coupon modelled volume "
          f"{modelled_volume_mm3(coupon):.1f} mm^3, x{MASS_COUNT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
