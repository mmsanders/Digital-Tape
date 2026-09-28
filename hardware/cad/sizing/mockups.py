#!/usr/bin/env python3
"""Size mockups: Sony WM-2 (1981) and a Digital-Tape envelope, packet SIZE-01.

    python3 mockups.py              writes hardware/packets/size-01/
    python3 mockups.py --self-test  shows each gate going red on a broken part

Life-size, hollow, re-openable, for holding in the hand and ballasting with coins.

SHAPE SOURCES. WM-2 outer size 80 x 109 x 29.5 mm, read from walkman.land on
27 Sep 2026 and matching the 1981 Japanese ad (80 x 109 x 29.5, 280 g incl.
battery). Control POSITIONS are traced by eye from product photos and the ad --
good to a few millimetres, not measured. Our envelope is layout A of
layout_study.py: two cartridges stacked, 92 x 97 x 42, every internal part an
estimate except the cartridge's working size.

THE SHELL IS SPLIT THE WAY A REAL ONE WOULD BE: front and back halves, parting
line parallel to the big faces, each half printed on its outer face so the
visible surfaces get the plate finish and nothing needs support.

THE JOINT answers three things the library clasp plate taught us:
  * the lid's rim broke off because it hung from a thin ledge. Here it is a
    RABBET: each half's lip stands directly on its own full wall, so there is
    no ledge to snap;
  * the seam was too wide. A rabbet leaves a butt line at the outer skin;
  * A and Q could not be opened without breaking them. The lip clearance is
    0.05 mm/side -- the band the fit ladder says releases with a twist -- plus
    four small detents, and a pry notch so a fingernail or a coin opens it.

CONTROLS on a face that prints against the bed can only be recessed, so the
WM-2's buttons are the button shape standing inside a moat: you feel the edge
of every button. Our device has edge keys (Michael's preference), and an edge
is a vertical wall in print, so those keys are genuinely raised.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import cadquery as cq
from cadquery import exporters

OUT = Path(__file__).resolve().parents[2] / "packets" / "size-01"

WALL = 2.0
FLOOR = 2.0
SKIRT_H = 4.0            # lid skirt, drops over the tray tongue
TONGUE_H = 3.8           # 0.2 short of the skirt so the seam closes, not the tongue
CLR = 0.05               # per side, tongue to skirt. The A1MINI-01 ladder was
                         # diametral: 0.10 there = 0.05 a side = rung 3, "snug,
                         # releases with a twist" in Michael's hand
SKIRT_T = 1.0            # skirt occupies offset 0 .. -1.0
TONGUE_IN = SKIRT_T + CLR  # tongue occupies offset -1.05 .. -WALL
DETENT_H = 0.25          # bump proud of the tongue; interference 0.20 after CLR
BED, MARGIN = 180.0, 5.0
PLA_DENSITY = 1.24       # g/cm^3, solid; a real print with infill weighs less

NICKEL_D, NICKEL_T, NICKEL_G = 21.21, 1.95, 5.000   # US Mint specification


# ---------------------------------------------------------------- primitives

def _rr_face(W, H, r, off=0.0):
    w = cq.Wire.makePolygon([(0, 0, 0), (W, 0, 0), (W, H, 0), (0, H, 0)], close=True)
    w = w.fillet2D(r, w.Vertices())
    if off:
        w = w.offset2D(off, "arc")[0]
    return cq.Face.makeFromWires(w)


def slab(W, H, r, off, z0, z1):
    s = cq.Solid.extrudeLinear(_rr_face(W, H, r, off), cq.Vector(0, 0, z1 - z0))
    return cq.Workplane().add(s.translate(cq.Vector(0, 0, z0)))


def ring(W, H, r, off_out, off_in, z0, z1):
    return slab(W, H, r, off_out, z0, z1).cut(slab(W, H, r, off_in, z0, z1))


def box(x0, y0, z0, x1, y1, z1):
    return (cq.Workplane().box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, y0, z0)))


def stadium(cx, cy, length, width, angle_deg, z0, z1):
    return (cq.Workplane().workplane(offset=z0).center(cx, cy)
            .slot2D(length, width, angle_deg).extrude(z1 - z0))


def cyl(cx, cy, r, z0, z1):
    return cq.Workplane().workplane(offset=z0).center(cx, cy).circle(r).extrude(z1 - z0)


def rod(r, length, base, direction):
    """A cylinder from an explicit base point along an explicit axis. No
    named sketch planes, so no guessing which way a plane's normal points."""
    return cq.Workplane().add(cq.Solid.makeCylinder(
        r, length, cq.Vector(*base), cq.Vector(*direction)))


def prism_xz(pts_xz, y0, length):
    """A prism whose cross-section lies in the XZ plane, extruded along +Y."""
    w = cq.Wire.makePolygon([cq.Vector(x, y0, z) for x, z in pts_xz], close=True)
    return cq.Workplane().add(
        cq.Solid.extrudeLinear(cq.Face.makeFromWires(w), cq.Vector(0, length, 0)))


def prism_yz(pts_yz, x0, length):
    """A prism whose cross-section lies in the YZ plane, extruded along +X."""
    w = cq.Wire.makePolygon([cq.Vector(x0, y, z) for y, z in pts_yz], close=True)
    return cq.Workplane().add(
        cq.Solid.extrudeLinear(cq.Face.makeFromWires(w), cq.Vector(length, 0, 0)))


def _ridge_pts(face, zc, proud, inward, half_base, half_top):
    return [(face + inward, zc - half_base), (face, zc - half_base),
            (face - proud, zc - half_top), (face - proud, zc + half_top),
            (face, zc + half_base), (face + inward, zc + half_base)]


def ridge_y(side_y, H, zc, x0, length, face_y, proud, inward, half_base, half_top):
    """ridge() for the top (+1) and bottom (-1) edges instead of the sides."""
    pts = _ridge_pts(face_y, zc, proud, inward, half_base, half_top)
    if side_y > 0:
        pts = [(H - y, z) for y, z in pts]
    return prism_yz(pts, x0, length)


def _rr_wire(W, H, r, inset, z):
    """Rounded rectangle inset by `inset`, corner radius shrinking to match --
    the flat face of a box whose edge blends are bigger than its plan corners."""
    w, h, rc = W - 2 * inset, H - 2 * inset, max(r - inset, 0.25)
    wire = cq.Wire.makePolygon([(0, 0, 0), (w, 0, 0), (w, h, 0), (0, h, 0)], close=True)
    return wire.fillet2D(rc, wire.Vertices()).translate(cq.Vector(inset, inset, z))


def _bed_edge_profile(R, steps=8):
    """(height above face, inset) for an edge round of radius R that prints
    face-down: the lower half of the round (flatter than 45 deg, which would
    sag) is replaced by the 45 deg chamfer tangent to it. Invisible in the
    hand, and no support needed."""
    if R <= 0:
        return [(0.0, 0.0)]
    pts = [(0.0, R * (2 - math.sqrt(2)))]
    for i in range(steps + 1):
        phi = math.radians(45 + 45 * i / steps)
        pts.append((R - R * math.cos(phi), R - R * math.sin(phi)))
    return pts


def rounded_body(W, H, T, r, r_back, r_front):
    """The outer mould line: plan corners r, back-face edges r_back, front-face
    edges r_front, both faces print-safe (see _bed_edge_profile)."""
    secs = [(h, i) for h, i in _bed_edge_profile(r_back)]
    secs += [(T - h, i) for h, i in reversed(_bed_edge_profile(r_front))]
    wires = [_rr_wire(W, H, r, i, z) for z, i in secs]
    return cq.Workplane().add(cq.Solid.makeLoft(wires, True))


def ridge(side_x, W, zc, y0, length, face_x, proud, inward, half_base, half_top):
    """A trapezoidal ridge standing `proud` off a vertical face at x = face_x.

    Straight-sided so the boolean is reliable -- small spheres pushed a quarter
    of a millimetre proud of a thin wall made the kernel drop the whole tray.
    `side_x` is -1 for the left wall (ridge points -X), +1 for the right.
    """
    pts = _ridge_pts(face_x, zc, proud, inward, half_base, half_top)
    if side_x > 0:
        pts = [(W - x, z) for x, z in pts]
    return prism_xz(pts, y0, length)


# ---------------------------------------------------------------- the shell

def shell_pair(W, H, T, r, zs, edges=None, detents_on="sides"):
    """Tray (back, z 0..zs+tongue) and lid (front, zs..T), rabbet-jointed.

    The seam is the plane z = zs. The lid's skirt drops over the tray's tongue.
    `edges` = (r_back, r_front) rounds the two big faces; None leaves them square.
    `detents_on` = "sides" (the long edges) or "ends" (top and bottom).
    """
    if edges:
        body = rounded_body(W, H, T, r, *edges)
        tray = (body.intersect(box(-5, -5, -1, W + 5, H + 5, zs))
                .cut(slab(W, H, r, -WALL, FLOOR, zs + 1))
                .union(ring(W, H, r, -TONGUE_IN, -WALL, zs, zs + TONGUE_H)))
        lid = (body.intersect(box(-5, -5, zs, W + 5, H + 5, T + 1))
               .cut(slab(W, H, r, -WALL, zs - 1, T - FLOOR))
               .cut(slab(W, H, r, -SKIRT_T, zs - 1, zs + SKIRT_H)))
    else:
        tray = (slab(W, H, r, 0, 0, FLOOR)
                .union(ring(W, H, r, 0, -WALL, FLOOR, zs))
                .union(ring(W, H, r, -TONGUE_IN, -WALL, zs, zs + TONGUE_H)))
        lid = (slab(W, H, r, 0, T - FLOOR, T)
               .union(ring(W, H, r, 0, -WALL, zs + SKIRT_H, T - FLOOR))
               .union(ring(W, H, r, 0, -SKIRT_T, zs, zs + SKIRT_H)))

    # Detents: a ridge on the tongue, a groove in the skirt, two per edge.
    zc = zs + TONGUE_H / 2
    tongue_ridge = dict(proud=DETENT_H, inward=0.5, half_base=1.0, half_top=0.5)
    skirt_groove = dict(proud=DETENT_H + 0.05, inward=0.3, half_base=1.1, half_top=0.6)
    if detents_on == "sides":
        for y in (H * 0.3, H * 0.7):
            for sx in (-1, 1):
                tray = tray.union(ridge(sx, W, zc, y - 2.5, 5.0, face_x=TONGUE_IN,
                                        **tongue_ridge))
                lid = lid.cut(ridge(sx, W, zc, y - 2.7, 5.4, face_x=SKIRT_T,
                                    **skirt_groove))
    else:
        for x in (W * 0.3, W * 0.7):
            for sy in (-1, 1):
                tray = tray.union(ridge_y(sy, H, zc, x - 2.5, 5.0, face_y=TONGUE_IN,
                                          **tongue_ridge))
                lid = lid.cut(ridge_y(sy, H, zc, x - 2.7, 5.4, face_y=SKIRT_T,
                                      **skirt_groove))
    # Pry notch in the skirt, bottom edge centre: a thumbnail or a coin opens it.
    lid = lid.cut(box(W / 2 - 6, -1, zs - 0.1, W / 2 + 6, SKIRT_T + 0.2, zs + 1.6))
    return tray, lid


def coin_grid(W, H, r, z0, height, pitch=24.0, t=1.2):
    """Low ribs so coins stack in cells instead of sliding. Cells fit a nickel."""
    inner = slab(W, H, r, -WALL + 0.3, z0, z0 + height)   # bite into the wall
    ribs = None
    x = WALL + pitch
    while x < W - WALL - 4:
        b = box(x - t / 2, 0, z0, x + t / 2, H, z0 + height)
        ribs = b if ribs is None else ribs.union(b)
        x += pitch
    y = WALL + pitch
    while y < H - WALL - 4:
        b = box(0, y - t / 2, z0, W, y + t / 2, z0 + height)
        ribs = b if ribs is None else ribs.union(b)
        y += pitch
    return ribs.intersect(inner)


def prism_line(pts, width, z0, z1):
    """A strip `width` wide following a polyline -- an engraved line."""
    out = None
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        L = math.hypot(x1 - x0, y1 - y0)
        seg = (box(0, -width / 2, z0, L, width / 2, z1)
               .rotate((0, 0, 0), (0, 0, 1), math.degrees(math.atan2(y1 - y0, x1 - x0)))
               .translate((x0, y0, 0)))
        out = seg if out is None else out.union(seg)
    return out


def groove_rr(W, H, r, inset, width, depth, z_face, up):
    """An engraved rounded-rectangle outline on a face (door seams, windows)."""
    z0, z1 = (z_face - depth, z_face + 1) if up else (z_face - 1, z_face + depth)
    return ring(W, H, r, -inset, -(inset + width), z0, z1)


def groove_rect(x, y, w, h, r, width, depth, z_face, up):
    return groove_rr(w, h, r, 0, width, depth, z_face, up).translate((x, y, 0))


# ---------------------------------------------------------------- WM-2

RIB_W, RIB_P = 0.6, 1.2   # the real ribs are ~1 mm pitch; 0.6 is what a 0.4 nozzle
                          # can leave standing between two grooves on the bed


def _grooves_along_y(x_list, y0, y1, z0, z1, w=RIB_W):
    g = None
    for x in x_list:
        b = box(x - w / 2, y0, z0, x + w / 2, y1, z1)
        g = b if g is None else g.union(b)
    return g


def _poly_prism(pts_xy, z0, z1):
    return (cq.Workplane().workplane(offset=z0).polyline(pts_xy).close()
            .extrude(z1 - z0))


def wm2():
    """Sony WM-2 outer mould line.

    Size 80 x 109 x 29.5 (walkman.land, 1981 ad). Everything else was measured
    off an orthographic fan render Michael supplied (its plan is 80:109 to 0.1 %,
    so 9.2 px/mm) and cross-checked against walkman.land product photos, which
    also supplied the DC IN jack the render leaves out. Good to about +-1 mm;
    not measured on a real unit. Coordinates: x across from the left edge seen
    from the controls face, y up from the bottom edge, z from the back (door).
    """
    W, H, T, r = 80.0, 109.0, 29.5, 2.0
    R_BACK, R_FRONT = 3.0, 2.0         # edge rounds, from the edge-on views
    zs = 13.6        # print seam: the real black/silver line is at 12.3, but the
                     # door-edge slots and the OPEN slider end at 13.5
    tray, lid = shell_pair(W, H, T, r, zs, edges=(R_BACK, R_FRONT), detents_on="ends")
    tray = tray.union(coin_grid(W, H, r, FLOOR, 8.0))

    # ======================= controls face (z = T, the lid) ===================
    # Black ribbed zone: triangle behind the wheel plus a strip down the right
    # edge. Real ribs are about 1 mm pitch; here 0.6 mm grooves at 1.2, 0.4 deep.
    diag = [(47.8, H), (73.6, 75.1), (73.6, 0.0)]
    lid = lid.cut(prism_line(diag, 0.6, T - 0.4, T + 1))              # boundary
    zone = _poly_prism([(49.2, H - 2.2), (74.9, 75.6), (74.9, 2.2),
                        (W - 2.2, 2.2), (W - 2.2, H - 2.2)], T - 0.4, T + 1)
    xs = [49.6 + RIB_P * i for i in range(24)]
    lid = lid.cut(_grooves_along_y(xs, 0, H, T - 0.4, T + 1).intersect(zone))

    # Button wells at +40 deg, square to the diagonal. Buttons stand flush in a
    # moat: they print against the bed, so they cannot stand proud of it.
    A = 40.0
    WELL = 1.5
    for cx, cy, L, Wd in ((45.0, 91.3, 22.0, 7.5),      # FF / REW
                          (46.5, 77.5, 23.0, 8.5),      # FWD (PLAY)
                          (59.7, 73.5, 20.5, 8.5)):     # STOP
        lid = lid.cut(stadium(cx, cy, L, Wd, A, T - WELL, T + 1))
    lid = lid.union(stadium(45.8, 76.9, 18.5, 5.2, A, T - WELL - 0.2, T))   # PLAY
    lid = lid.union(stadium(59.7, 73.5, 16.0, 5.2, A, T - WELL - 0.2, T))   # STOP
    for bx, by in ((41.0, 87.8), (50.4, 95.9)):                            # FF, REW
        lid = lid.union(cyl(bx, by, 2.1, T - WELL - 0.2, T))
    lid = lid.cut(cyl(40.2, 72.6, 1.6, T - 0.3, T + 1))       # green PLAY dot, felt
    lid = lid.cut(cyl(59.2, 88.6, 0.9, T - 0.8, T + 1))       # battery LED
    lid = lid.cut(cyl(51.8, 105.2, 1.4, T - 0.5, T + 1))      # the corner screw

    # Volume wheel: face flush with the front, rim showing through a notch in
    # the top edge. A cup inside the lid carries it.
    wc, WR, WT = (65.4, 100.6), 8.0, 4.5
    cup = cyl(*wc, WR + 1.8, T - WT - 1.0, T).intersect(
        box(-1, -1, T - WT - 1.0, W + 1, H + 1, T + 1)).intersect(
        rounded_body(W, H, T, r, R_BACK, R_FRONT))
    lid = (lid.union(cup).cut(cyl(*wc, WR + 0.8, T - WT, T + 1))
           .cut(box(59.5, H - 3.0, T - WT, 72.0, H + 1, T + 1)))
    wheel = cyl(*wc, WR, T - WT, T)
    for i in range(44):
        wheel = wheel.cut(box(-0.35, WR - 0.5, T - WT - 0.1, 0.35, WR + 1, T + 1)
                          .rotate((0, 0, 0), (0, 0, 1), 360.0 * i / 44)
                          .translate((*wc, 0)))
    for rr in (2.5, 4.5):                                     # the ringed cap
        wheel = wheel.cut(ring(2 * rr, 2 * rr, rr - 0.01, 0, -0.5, T - 0.3, T + 1)
                          .translate((wc[0] - rr, wc[1] - rr, 0)))
    lid = lid.union(wheel)

    # ======================= door face (z = 0, the tray) ======================
    tray = tray.cut(box(72.2 - 0.3, -1, -1, 72.2 + 0.3, H + 1, 0.5))       # hinge strip
    tray = tray.cut(_grooves_along_y([73.6 + RIB_P * i for i in range(4)], 2.5, H - 2.5,
                                     -1, 0.4))
    tray = tray.cut(cyl(74.7, 57.4, 0.9, -1, 0.8))                          # door pin
    tray = tray.cut(groove_rect(12.7, 19.0, 31.2, 70.5, 4.3, 0.8, 0.6, 0, up=False))
    tray = tray.cut(groove_rect(23.0, 45.0, 11.5, 19.0, 1.5, 0.6, 0.4, 0, up=False))
    for hy in (76.3, 35.7):                                                 # hubs
        tray = tray.cut(ring(6.6, 6.6, 3.29, 0, -0.7, -1, 0.5).translate((29.5, hy - 3.3, 0)))

    # ======================= edges ============================================
    DOOR_Z = 6.8                              # the door's edge line, 3 sides
    tray = tray.cut(box(-1, 2, DOOR_Z - 0.25, 0.4, H - 2, DOOR_Z + 0.25))
    for yb in ((-1, 0.4), (H - 0.4, H + 1)):
        tray = tray.cut(box(2, yb[0], DOOR_Z - 0.25, 72.2, yb[1], DOOR_Z + 0.25))

    # Slanted slots in the top and bottom edges, just inside the door line,
    # with a block behind each so a coin cannot get out.
    slot = [(5.6, DOOR_Z), (23.3, DOOR_Z), (26.3, 13.4), (9.0, 13.4)]
    for y_out, y_in in ((H + 1, H - 3.0), (-1, 3.0)):
        y0, y1 = min(y_out, y_in), max(y_out, y_in)
        yb0, yb1 = (H - 5.0, H - 1.9) if y_out > H else (1.9, 5.0)
        tray = tray.union(box(3.5, yb0, FLOOR - 0.1, 28.5, yb1, zs))
        tray = tray.cut(prism_xz(slot, y0, y1 - y0))

    # Left side: the OPEN slider (in a recess, just in front of the door line)
    # and the DC IN jack near the bottom.
    tray = tray.cut(box(-1, 25.4, DOOR_Z, 0.8, 41.8, 13.5))
    knob = box(0.2, 27.4, 7.6, 0.85, 39.8, 12.7)
    for gy in (30.5, 33.6, 36.7):
        knob = knob.cut(box(0.1, gy - 0.3, 7.5, 0.5, gy + 0.3, 12.8))
    tray = tray.union(knob)
    lid = lid.cut(rod(1.4, 3.0, (-0.01, 6.5, 19.5), (1, 0, 0)))
    lid = lid.cut(rod(2.5, 0.4, (-0.01, 6.5, 19.5), (1, 0, 0)))

    # Top edge: headphone jacks A and B, near the front.
    for jx in (32.0, 42.7):
        lid = lid.cut(rod(1.75, 3.0, (jx, H + 0.01, 22.8), (0, -1, 0)))
        lid = lid.cut(rod(3.2, 0.4, (jx, H + 0.01, 22.8), (0, -1, 0)))
    # Hinge pins, top and bottom, right-hand end.
    for py, d in ((H + 0.01, -1), (-0.01, 1)):
        tray = tray.cut(rod(0.9, 1.0, (76.3, py, 9.6), (0, d, 0)))
    # Bottom edge: a small hole, and the rating plate's outline.
    lid = lid.cut(rod(1.2, 1.0, (50.4, -0.01, 22.0), (0, 1, 0)))
    plate_o = box(53.4, -1, 14.3, 73.0, 0.3, 27.0)
    lid = lid.cut(plate_o.cut(box(53.8, -2, 14.7, 72.6, 1, 26.6)))

    # Right side: ribs all along it, the TAPE NORM/METAL switch, two screws.
    zr = [3.6 + RIB_P * i for i in range(20)]
    ribs = None
    for z in zr:
        b = box(W - 0.3, 2.2, z - RIB_W / 2, W + 1, H - 2.2, z + RIB_W / 2)
        ribs = b if ribs is None else ribs.union(b)
    tray = tray.cut(ribs)
    lid = lid.cut(ribs)
    lid = lid.cut(box(W - 0.5, 39.8, 15.2, W + 1, 57.7, 22.3))
    lid = lid.union(box(W - 0.6, 48.2, 16.0, W - 0.1, 52.0, 21.5))       # slider
    for sy in (17.6, 92.6):
        lid = lid.cut(rod(0.9, 0.5, (W + 0.01, sy, 16.6), (-1, 0, 0)))

    return dict(name="WM-2", W=W, H=H, T=T, r=r, zs=zs, tray=tray, lid=lid,
                target_g=280, target_note="280 g incl. AA battery (1981 ad)")


# ---------------------------------------------------------------- ours

def ours():
    W, H, T, r = 92.0, 97.0, 42.0, 4.0
    zs = 29.0                                   # back half 29, front half 13
    tray, lid = shell_pair(W, H, T, r, zs)
    tray = tray.union(coin_grid(W, H, r, FLOOR, 8.0))

    # Corner bumpers, 1.5 mm proud on the sides. Guardrail 13 will want
    # something here; this reserves the space so the size is honest.
    for x0, x1 in ((-1.5, 0.5), (W - 0.5, W + 1.5)):
        for y0, y1 in ((0, 12), (H - 12, H)):
            tray = tray.union(box(x0, y0, 0, x1, y1, zs))
            lid = lid.union(box(x0, y0, zs, x1, y1, T))

    # Edge keys on the top edge: five, raised 2.5 mm. The set is not decided --
    # these are positions, not functions. The middle one has a home dimple.
    for i in range(5):
        cx = W / 2 + (i - 2) * 14.5
        key = box(cx - 5.75, H - 0.5, 9, cx + 5.75, H + 2.5, 23)
        key = key.edges("|X and >Y and >Z").chamfer(0.8)
        key = key.edges("|X and >Y and <Z").chamfer(2.2)   # 45 deg underside, no droop
        tray = tray.union(key)
    tray = tray.cut(rod(1.6, 1.0, (W / 2, H + 2.5 - 0.8, 16), (0, 1, 0)))

    # Volume thumbwheel through the right side, knurled.
    wheel = cq.Workplane().workplane(offset=12).center(W - 7, 70).circle(9).extrude(8)
    for i in range(36):
        a = 360.0 * i / 36
        wheel = wheel.cut(box(-0.4, 8.2, 11, 0.4, 10, 21)
                          .rotate((0, 0, 0), (0, 0, 1), a).translate((W - 7, 70, 0)))
    tray = tray.union(wheel.intersect(box(W - 9, 58, 12, W + 2.1, 82, 20)))

    # Left side: headphone jack and USB-C, recessed.
    tray = tray.cut(rod(3.0, 1.5, (-0.01, 60, 15), (1, 0, 0)))
    tray = tray.cut(box(-0.01, 40 - 4.5, 15 - 1.75, 1.5, 40 + 4.5, 15 + 1.75))

    # Bottom edge: the destination slot, as an engraved outline.
    slot = (box(W / 2 - 42, -0.01, 16, W / 2 + 42, 0.8, 28)
            .cut(box(W / 2 - 41.2, -0.02, 16.8, W / 2 + 41.2, 0.81, 27.2)))
    tray = tray.cut(slot)

    # Front face: the source deck's door, its window, and the record light.
    lid = lid.cut(groove_rr(W, H, r, 4.0, 0.8, 0.7, T, up=True))
    lid = lid.cut(groove_rect(W / 2 - 30, 30, 60, 30, 4, 0.8, 0.7, T, up=True))
    lid = lid.cut(cyl(W / 2, 80, 1.6, T - 1.0, T + 1))
    return dict(name="Digital-Tape layout A", W=W, H=H, T=T, r=r, zs=zs, tray=tray,
                lid=lid, target_g=150,
                target_note="~150 g EST (thermal-budget.md): no motor, no AA cells")


# ---------------------------------------------------------------- output

def for_print(part, flip):
    """Tray prints on its back face; lid is flipped onto its front face."""
    if flip:
        part = part.rotate((0, 0, 0), (1, 0, 0), 180)
    b = whole(part)[1].BoundingBox()
    return part.translate((-b.xmin, -b.ymin, -b.zmin))


def mass_g(part):
    return sum(s.Volume() for s in whole(part)[0]) / 1000.0 * PLA_DENSITY


def whole(part):
    """Every solid on the stack, as one shape -- never just the first object."""
    solids = [s for o in part.vals() for s in o.Solids()]
    return solids, cq.Compound.makeCompound(solids)


def check(name, part):
    solids, shape = whole(part)
    b = shape.BoundingBox()
    bad = []
    if len(solids) != 1:
        bad.append(f"{name}: {len(solids)} separate solids -- something is floating")
    if not solids or min(s.Volume() for s in solids) <= 0:
        bad.append(f"{name}: non-positive volume -- the solid is inside-out")
    if b.xlen > BED - 2 * MARGIN or b.ylen > BED - 2 * MARGIN or b.zlen > BED - 5:
        bad.append(f"{name}: {b.xlen:.1f} x {b.ylen:.1f} x {b.zlen:.1f} off the bed")
    return bad


def _overlap(a, b):
    return sum(s.Volume() for s in whole(a)[1].intersect(whole(b)[1]).Solids())


def check_joint(m):
    """Closed, the halves must not occupy the same space; and the detent ridges
    must really sit in their grooves. The second test is the first one's
    negative control: the same overlap measure, against a skirt with no
    grooves, has to come out positive or it cannot see a collision at all."""
    W, H, r, zs = m["W"], m["H"], m["r"], m["zs"]
    bad = []
    v = _overlap(m["tray"], m["lid"])
    if v > 0.01:
        bad.append(f"{m['name']}: closed halves overlap by {v:.2f} mm^3")
    plain = ring(W, H, r, 0, -SKIRT_T, zs, zs + SKIRT_H)
    v0 = _overlap(m["tray"], plain)
    if v0 < 1.0:
        bad.append(f"{m['name']}: ridges do not reach the skirt ({v0:.2f} mm^3) "
                   f"-- the detents would not click")
    return bad


def self_test():
    """Every gate here has to be able to go red. Feed it parts that are wrong."""
    good = box(0, 0, 0, 50, 50, 10)
    cases = {
        "good part passes": (check("good", good), False),
        "floating island": (check("island", good.union(box(60, 0, 0, 65, 5, 5))), True),
        "too big for the bed": (check("big", box(0, 0, 0, 171, 50, 10)), True),
    }
    for m in (wm2(), ours()):
        W, H, r, zs = m["W"], m["H"], m["r"], m["zs"]
        nogroove = dict(m, lid=m["lid"].union(ring(W, H, r, 0, -SKIRT_T, zs, zs + SKIRT_H)))
        noridge = dict(m, tray=m["tray"].cut(ring(W, H, r, 0, -TONGUE_IN,
                                                   zs, zs + TONGUE_H)))
        tag = m["name"].split()[0]
        cases[f"{tag}: real joint passes"] = (check_joint(m), False)
        cases[f"{tag}: skirt, no grooves"] = (check_joint(nogroove), True)
        cases[f"{tag}: tongue, no ridges"] = (check_joint(noridge), True)
    ok = True
    for label, (found, want_red) in cases.items():
        red = bool(found)
        ok &= red == want_red
        print(f"  {'ok ' if red == want_red else 'BAD'} {label:30s} "
              f"{'red' if red else 'green'}{': ' + found[0] if found else ''}")
    return 0 if ok else 1


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    report, problems, assy = [], [], cq.Assembly()
    x_view = 0.0
    parts_out = {}
    for m in (wm2(), ours()):
        key = "wm2" if m["name"] == "WM-2" else "ours"
        problems += check_joint(m)
        tray_p, lid_p = for_print(m["tray"], False), for_print(m["lid"], True)
        for nm, p in (("tray", tray_p), ("lid", lid_p)):
            problems += check(f"{key}-{nm}", p)
            exporters.export(p, str(OUT / f"{key}-{nm}.stl"))
            parts_out[f"{key}-{nm}"] = p
        g = mass_g(m["tray"]) + mass_g(m["lid"])
        coins = max(0, round((m["target_g"] - g) / NICKEL_G))
        report.append((m["name"], m["W"], m["H"], m["T"], g, m["target_g"], coins,
                       m["target_note"]))
        assy.add(m["tray"].translate((x_view, 0, 0)), name=f"{key}-tray",
                 color=cq.Color("gray"))
        assy.add(m["lid"].translate((x_view, 0, 0)), name=f"{key}-lid",
                 color=cq.Color("steelblue"))
        x_view += m["W"] + 30

    # Plates. WM-2's two halves share one; ours needs one per half.
    w_t, w_l = parts_out["wm2-tray"], parts_out["wm2-lid"]
    plate1 = w_t.union(w_l.translate((whole(w_t)[1].BoundingBox().xlen + 5, 0, 0)))
    for nm, p in (("plate-1-wm2", plate1), ("plate-2-ours-back", parts_out["ours-tray"]),
                  ("plate-3-ours-front", parts_out["ours-lid"])):
        b = whole(p)[1].BoundingBox()
        if b.xlen > BED - 2 * MARGIN or b.ylen > BED - 2 * MARGIN:
            problems.append(f"{nm}: {b.xlen:.1f} x {b.ylen:.1f} does not fit")
        exporters.export(p, str(OUT / f"{nm}.stl"))
        print(f"  {nm:20s} {b.xlen:6.1f} x {b.ylen:6.1f} x {b.zlen:5.1f} mm")
    assy.save(str(OUT / "size-01-assembled.step"))

    for n, W, H, T, g, tg, coins, note in report:
        print(f"  {n:22s} {W} x {H} x {T} mm  shell <= {g:5.1f} g solid  "
              f"target {tg} g -> ~{coins} nickels  ({note})")
    (OUT / "manifest.json").write_text(json.dumps({
        "packet": "SIZE-01", "revision": 2, "released": "2026-09-28",
        "printer": "Bambu Lab A1 Mini", "nozzle_mm": 0.4, "material": "PLA Basic",
        "joint": {"type": "rabbet + 4 detents + pry notch", "clearance_per_side_mm": CLR,
                  "detent_interference_mm": DETENT_H - CLR},
        "mockups": [{"name": n, "mm": [W, H, T], "shell_mass_upper_bound_g": round(g, 1),
                     "target_g": tg, "nickels_approx": coins, "target_note": note}
                    for n, W, H, T, g, tg, coins, note in report],
    }, indent=2) + "\n")
    if problems:
        raise SystemExit("\n".join(problems))
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(self_test() if "--self-test" in sys.argv[1:] else build())
