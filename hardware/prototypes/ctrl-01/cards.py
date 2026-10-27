"""CTRL-01 cards and slots, at the new GameCube-class size (36 x 40 x 7 mm).

Six slots fill the case outside the transport bay: two in the top, two in the
bottom and two in the right side, one in front of the other at each place so
each half owns one. Each pocket opens toward the seam except for two edge
rails, so no pocket needs a roof bridged over it.

Top and bottom cards go in along their 36 mm side (a 40 mm opening), and the
side cards along their 40 mm side (a 36 mm opening): that is the only way all
six fit in 110 mm with the cards 3 mm proud.
"""

from __future__ import annotations

from dataclasses import dataclass

import cadquery as cq

import layout as L

A, B, TH = L.CARD                     # 40, 36, 7
XC = (L.SPINE_X[1] + L.W - L.WALL) / 2   # top/bottom slots centred in the free width
YC = 55.0                              # side slots centred between the top and bottom pockets


@dataclass(frozen=True)
class Slot:
    name: str
    loc: str          # top | bottom | right
    layer: str        # front | back
    clr: float        # per side, width and thickness
    hold: str         # none | ribs | detent

    @property
    def depth(self) -> float:
        """Pocket depth along the insertion: the card's length less PROUD, plus 0.3."""
        return (B if self.loc in ("top", "bottom") else A) - L.PROUD + 0.3

    @property
    def z(self) -> tuple[float, float]:
        t = TH + 2 * self.clr
        return (L.FRONT_CARD_Z, L.FRONT_CARD_Z + t) if self.layer == "front" else (L.BACK_CARD_Z - t, L.BACK_CARD_Z)


SLOTS = (
    Slot("TF", "top", "front", 0.20, "none"),
    Slot("TB", "top", "back", 0.30, "none"),
    Slot("RF", "right", "front", 0.40, "none"),
    Slot("RB", "right", "back", 0.30, "ribs"),
    Slot("BF", "bottom", "front", 0.30, "ribs"),
    Slot("BB", "bottom", "back", 0.30, "detent"),
)

RIB_INTERFERENCE = 0.10        # crush ribs, per side (LADDER-02's lid insert used 0.10)
DETENT_BUMP = 0.6
DETENT_AT = 14.0               # mm in from the card's proud edge
NOTCH_DEPTH = 0.7


def _box(x0, x1, y0, y1, z0, z1) -> cq.Workplane:
    return (cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, y0, z0)))


def footprint(s: Slot) -> tuple[float, float, float, float]:
    """(x0, x1, y0, y1) of the card cavity in the device frame."""
    if s.loc in ("top", "bottom"):
        x0, x1 = XC - A / 2 - s.clr, XC + A / 2 + s.clr
        y0, y1 = (-1.0, s.depth) if s.loc == "top" else (L.H - s.depth, L.H + 1)
    else:
        x0, x1 = L.W - s.depth, L.W + 1
        y0, y1 = YC - B / 2 - s.clr, YC + B / 2 + s.clr
    return x0, x1, y0, y1


def pocket(s: Slot) -> tuple[cq.Workplane, cq.Workplane]:
    """(material to add, material to cut) for one slot, in its own half."""
    x0, x1, y0, y1 = footprint(s)
    z0, z1 = s.z
    w = L.POCKET_WALL
    hz0, hz1 = (L.WALL - 0.01, L.SEAM) if s.layer == "front" else (L.SEAM, L.T - L.WALL + 0.01)
    rail_z = (z1, z1 + L.RAIL_OVER) if s.layer == "front" else (z0 - L.RAIL_OVER, z0)
    face_z = (L.WALL - 0.01, z0) if s.layer == "front" else (z1, L.T - L.WALL + 0.01)
    if s.loc in ("top", "bottom"):
        fy = (s.depth, s.depth + 1.5) if s.loc == "top" else (L.H - s.depth - 1.5, L.H - s.depth)
        ya, yb = (L.WALL - 0.01, fy[1]) if s.loc == "top" else (fy[0], L.H - L.WALL + 0.01)
        add = (_box(x0 - w, x0, ya, yb, hz0, hz1)
               .union(_box(x1, L.W - L.WALL + 0.01, ya, yb, hz0, hz1))
               .union(_box(x0 - w, L.W - L.WALL + 0.01, fy[0], fy[1], hz0, hz1))
               .union(_box(x0, x1, ya, yb, *face_z))
               .union(_box(x0, x0 + w, ya, yb, *rail_z))
               .union(_box(x1 - w, x1, ya, yb, *rail_z)))
    else:
        fx = (x0 - 1.5, x0)
        add = (_box(fx[0], L.W - L.WALL + 0.01, y0 - w, y0, hz0, hz1)
               .union(_box(fx[0], L.W - L.WALL + 0.01, y1, y1 + w, hz0, hz1))
               .union(_box(fx[0], fx[1], y0 - w, y1 + w, hz0, hz1))
               .union(_box(fx[1], L.W - L.WALL + 0.01, y0, y1, *face_z))
               .union(_box(fx[1], L.W - L.WALL + 0.01, y0, y0 + w, *rail_z))
               .union(_box(fx[1], L.W - L.WALL + 0.01, y1 - w, y1, *rail_z)))
    cut = _box(x0, x1, y0, y1, z0, z1)
    if s.hold == "ribs":
        # crush ribs: added material inside the cavity, so the cavity cut must spare them
        zm = (z0 + z1) / 2
        p = s.clr + RIB_INTERFERENCE
        if s.loc in ("top", "bottom"):
            ry = (max(y0, 0) + 3, y1 - 0.5) if s.loc == "top" else (y0 + 0.5, L.H - 3)
            ribs = (_box(x0 - 0.01, x0 + p, *ry, zm - 0.5, zm + 0.5)
                    .union(_box(x1 - p, x1 + 0.01, *ry, zm - 0.5, zm + 0.5)))
        else:
            rx = (x0 + 0.5, L.W - 3)
            ribs = (_box(*rx, y0 - 0.01, y0 + p, zm - 0.5, zm + 0.5)
                    .union(_box(*rx, y1 - p, y1 + 0.01, zm - 0.5, zm + 0.5)))
        add, cut = add.union(ribs), cut.cut(ribs)
    if s.hold == "detent":
        add, cut = _detent(s, add, cut)
    return add, cut


def detent_y(s: Slot) -> float:
    """Device Y of the detent bump: DETENT_AT in from the proud edge of a seated card."""
    proud_edge = L.H + L.PROUD
    return proud_edge - DETENT_AT


def _detent(s: Slot, add: cq.Workplane, cut: cq.Workplane):
    """A cantilever finger cut from the right pocket wall, with a 45 degree bump.
    Only built for the bottom slots; the finger's root is the deeper end."""
    x0, x1, y0, y1 = footprint(s)
    z0, z1 = s.z
    by = detent_y(s)
    f0, f1 = by - 7.0, by + 3.0                       # root .. free end
    w = L.POCKET_WALL
    relief = (_box(x1 + w, x1 + w + 0.8, f0, f1 + 0.6, z0 - 0.4, z1 + 0.4)
              .union(_box(x1 - 0.01, x1 + w + 0.8, f1, f1 + 0.6, z0 - 0.4, z1 + 0.4))
              .union(_box(x1 - L.RAIL_OVER - 0.01, x1 + w + 0.8, f0, f1 + 0.6, z0 - L.RAIL_OVER - 0.4, z0))
              .union(_box(x1 - 0.01, x1 + w + 0.8, f0, f1 + 0.6, z1, z1 + 0.4)))
    bump = (cq.Workplane("XY", origin=(0, 0, z0)).polyline(
        [(x1 + 0.01, by - DETENT_BUMP * 2), (x1 - DETENT_BUMP, by), (x1 + 0.01, by + DETENT_BUMP * 2)])
        .close().extrude(z1 - z0))
    return add.cut(relief).union(bump), cut.union(relief).cut(bump)


# --- cards ---------------------------------------------------------------------

CARDS = ("A", "B", "C", "D", "E")
CARD_NOTES = {
    "A": "0.5 mm chamfer on every edge (baseline)",
    "B": "square edges",
    "C": "chamfered, with detent notches for slot BB",
    "D": "chamfered, with thumb dimples on the top face",
    "E": "chamfered, with a 0.4 mm label recess on the top face",
}


def card(v: str) -> cq.Workplane:
    """A card lying as it prints: 40 along X, 36 along Y, 7 thick."""
    c = cq.Workplane("XY").box(A, B, TH, centered=(True, True, False))
    if v != "B":
        c = c.edges().chamfer(0.5)
    if v == "C":
        # V notches on the 36 mm edges, at DETENT_AT from either end so it works either way round
        for x in (-A / 2, A / 2):
            for y in (-B / 2 + DETENT_AT, B / 2 - DETENT_AT):
                s = 1 if x < 0 else -1
                n = (cq.Workplane("XY").polyline(
                    [(x, y - NOTCH_DEPTH * 1.6), (x + s * NOTCH_DEPTH, y), (x, y + NOTCH_DEPTH * 1.6)])
                    .close().extrude(TH + 2).translate((0, 0, -1)))
                c = c.cut(n)
    if v == "D":
        for cx, cy in ((0, B / 2), (A / 2, 0)):
            # flat-bottomed round dimple, 0.8 deep, centred on the edge
            c = c.cut(cq.Workplane("XY", origin=(cx, cy, TH - 0.8)).circle(6.0).extrude(1.0))
    if v == "E":
        c = c.cut(_box(-14, 14, -10, 10, TH - 0.4, TH + 1))
    label = (cq.Workplane("XY", origin=(-A / 2 + 4.5, -B / 2 + 4.5, TH))
             .text(v, 4.0, -0.4, combine=False, font="DejaVu Sans"))
    return c.cut(label)
