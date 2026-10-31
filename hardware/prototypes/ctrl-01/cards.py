"""CTRL-01 cards and slots (1 Nov): four portrait slots, two in the top face and two
in the bottom, one in front of the other at each end so each half owns one
(Michael: "representative of where they would actually be").

The card goes in along its 42 mm length, 36 mm across, and stands 5 mm proud. Every
slot is the side slot Michael liked on 31 Oct: 0.30 mm clearance and crush ribs.
Each pocket opens toward the seam except for two edge rails, so no pocket needs a
roof; the mouth in the outer wall is the one bridge left, and prints on supports.
"""

from __future__ import annotations

from dataclasses import dataclass

import cadquery as cq

import layout as L

_, B, TH = L.CARD                      # 36 across, 7 thick
P_LEN = L.CARD_P_LEN                   # 42 along the insertion
P_PROUD = L.PROUD + (P_LEN - L.CARD[0])   # 5
XC = (L.SPINE_X[1] + L.COMB_CLR + L.BACKSTOP_T + L.W - L.WALL) / 2   # centred in the free width


@dataclass(frozen=True)
class Slot:
    name: str
    loc: str          # top | bottom
    layer: str        # front | back
    clr: float        # per side, width and thickness
    hold: str         # ribs

    @property
    def depth(self) -> float:
        """Pocket depth along the insertion: the card's length less what stands proud, plus 0.3."""
        return P_LEN - P_PROUD + 0.3

    @property
    def z(self) -> tuple[float, float]:
        t = TH + 2 * self.clr
        return (L.FRONT_CARD_Z, L.FRONT_CARD_Z + t) if self.layer == "front" else (L.BACK_CARD_Z - t, L.BACK_CARD_Z)


SLOTS = (
    Slot("TF", "top", "front", 0.30, "ribs"),
    Slot("TB", "top", "back", 0.30, "ribs"),
    Slot("BF", "bottom", "front", 0.30, "ribs"),
    Slot("BB", "bottom", "back", 0.30, "ribs"),
)

RIB_INTERFERENCE = 0.10        # crush ribs, per side (LADDER-02's lid insert used 0.10)


def _box(x0, x1, y0, y1, z0, z1) -> cq.Workplane:
    return (cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, y0, z0)))


def footprint(s: Slot) -> tuple[float, float, float, float]:
    """(x0, x1, y0, y1) of the card cavity in the device frame."""
    x0, x1 = XC - B / 2 - s.clr, XC + B / 2 + s.clr
    y0, y1 = (-1.0, s.depth) if s.loc == "top" else (L.H - s.depth, L.H + 1)
    return x0, x1, y0, y1


def ribs(s: Slot) -> cq.Workplane:
    x0, x1, y0, y1 = footprint(s)
    z0, z1 = s.z
    zm, p = (z0 + z1) / 2, s.clr + RIB_INTERFERENCE
    ry = (max(y0, 0) + 3, y1 - 0.5) if s.loc == "top" else (y0 + 0.5, L.H - 3)
    return (_box(x0 - 0.01, x0 + p, *ry, zm - 0.5, zm + 0.5)
            .union(_box(x1 - p, x1 + 0.01, *ry, zm - 0.5, zm + 0.5)))


def pocket(s: Slot) -> tuple[cq.Workplane, cq.Workplane]:
    """(material to add, material to cut) for one slot, in its own half."""
    x0, x1, y0, y1 = footprint(s)
    z0, z1 = s.z
    w = L.POCKET_WALL
    hz0, hz1 = (L.WALL - 0.01, L.SEAM) if s.layer == "front" else (L.SEAM, L.T - L.WALL + 0.01)
    rail_z = (z1, z1 + L.RAIL_OVER) if s.layer == "front" else (z0 - L.RAIL_OVER, z0)
    face_z = (L.WALL - 0.01, z0) if s.layer == "front" else (z1, L.T - L.WALL + 0.01)
    fy = (s.depth, s.depth + 1.5) if s.loc == "top" else (L.H - s.depth - 1.5, L.H - s.depth)
    ya, yb = (L.WALL - 0.01, fy[1]) if s.loc == "top" else (fy[0], L.H - L.WALL + 0.01)
    add = (_box(x0 - w, x0, ya, yb, hz0, hz1)
           .union(_box(x1, x1 + w, ya, yb, hz0, hz1))
           .union(_box(x0 - w, x1 + w, fy[0], fy[1], hz0, hz1))
           .union(_box(x0, x1, ya, yb, *face_z))
           .union(_box(x0, x0 + w, ya, yb, *rail_z))
           .union(_box(x1 - w, x1, ya, yb, *rail_z)))
    cut = _box(x0, x1, y0, y1, z0, z1)
    r = ribs(s)
    return add.union(r), cut.cut(r)


# --- portrait cards (31 Oct) ------------------------------------------------------
#
# Michael, 31 Oct: portrait, sized for the side slot that fit best (0.30 mm and crush
# ribs), 2 mm taller so 5 mm stands proud. Face, top (proud end) to bottom: grip
# notches on both sides, a grab scoop under a 2 mm lip, and a label window over the
# lower two-thirds. The card lies with its proud end at +X, face up.

P_NOTCH = (2.5, 0.9, 1.8)             # centre in from the top, depth, half-height
SCOOP = (2.0, 6.0, 9.0, 1.2)          # lip, height, half-width, depth
WINDOW = (2.0, 25.0, 12.0, 0.4, 1.5)  # from the bottom, length, half-width, depth, corner r


def _face_features(c: cq.Workplane, top_z: float) -> cq.Workplane:
    """Cut the scoop and window into the face at top_z."""
    x_top = P_LEN / 2
    lip, h, hw, d = SCOOP
    xs = x_top - lip
    scoop = (cq.Workplane("XY", origin=(0, 0, top_z - d)).moveTo(xs, -hw).lineTo(xs, hw)
             .lineTo(xs - h + hw * 0.5, hw).threePointArc((xs - h, 0), (xs - h + hw * 0.5, -hw)).close()
             .extrude(d + 1))
    w0, wl, whw, wd, wr = WINDOW
    xb = -P_LEN / 2 + w0
    window = (cq.Workplane("XY", origin=(xb + wl / 2, 0, top_z - wd)).rect(wl, 2 * whw)
              .extrude(wd + 1).edges("|Z").fillet(wr))
    return c.cut(scoop).cut(window)


def _notches(c: cq.Workplane, z0: float, z1: float) -> cq.Workplane:
    at, depth, hh = P_NOTCH
    x = P_LEN / 2 - at
    for y in (-B / 2, B / 2):
        s = 1 if y < 0 else -1
        n = (cq.Workplane("XY", origin=(0, 0, z0 - 1)).polyline(
            [(x - hh, y - s * 0.01), (x, y + s * depth), (x + hh, y - s * 0.01)]).close().extrude(z1 - z0 + 2))
        c = c.cut(n)
    return c


def portrait_card() -> cq.Workplane:
    """The solid portrait card, 42 x 36 x 7, face up."""
    c = cq.Workplane("XY").box(P_LEN, B, TH, centered=(True, True, False)).edges().chamfer(0.5)
    return _notches(_face_features(c, TH), 0, TH)


SNAP = dict(wall=2.6, floor=1.2, tongue=(1.4, 2.4), tongue_h=1.3, groove_clr=0.1, groove_d=1.5,
            bead=0.25, bead_z=0.9, bead_len=8.0)


def snap_card() -> tuple[cq.Workplane, cq.Workplane]:
    """(face half, back half) of the snap-together portrait card, assembled: the back
    half is Z 0..3.5 with an open pocket and a tongue all round on its rim; the face
    half is Z 3.5..7, solid, with the features on top and a groove underneath that
    the tongue clicks into (a bead on each side of the tongue, a relief in the groove)."""
    k = SNAP
    hz = TH / 2
    t0, t1 = k["tongue"]
    back = cq.Workplane("XY").box(P_LEN, B, hz, centered=(True, True, False))
    back = back.faces("<Z").edges().chamfer(0.5).edges("|Z").chamfer(0.5)
    w = k["wall"]
    back = back.cut(cq.Workplane("XY", origin=(0, 0, k["floor"])).rect(P_LEN - 2 * w, B - 2 * w).extrude(hz))
    ring = lambda a, b, z0, z1: (cq.Workplane("XY", origin=(0, 0, z0)).rect(P_LEN - 2 * a, B - 2 * a)
                                 .extrude(z1 - z0).cut(cq.Workplane("XY", origin=(0, 0, z0 - 1))
                                                       .rect(P_LEN - 2 * b, B - 2 * b).extrude(z1 - z0 + 2)))
    back = back.union(ring(t0, t1, hz - 0.01, hz + k["tongue_h"]))
    # beads: short ridges on the tongue's outer face, one per side
    bz = hz + k["bead_z"]
    beads = None
    for (x, y, along_x, s) in ((0, B / 2 - t0, True, 1), (0, -B / 2 + t0, True, -1),
                               (P_LEN / 2 - t0, 0, False, 1), (-P_LEN / 2 + t0, 0, False, -1)):
        b = k["bead"]
        tri = [(0, bz - b * 1.6), (s * b, bz), (0, bz + b * 1.6)]
        if along_x:
            r = cq.Workplane("YZ", origin=(x - k["bead_len"] / 2, 0, 0)).polyline(
                [(y + u, z) for u, z in tri]).close().extrude(k["bead_len"])
        else:
            r = cq.Workplane("XZ", origin=(0, y - k["bead_len"] / 2, 0)).polyline(
                [(x + u, z) for u, z in tri]).close().extrude(-k["bead_len"])
        beads = r if beads is None else beads.union(r)
    back = back.union(beads)
    face = cq.Workplane("XY", origin=(0, 0, hz)).box(P_LEN, B, hz, centered=(True, True, False))
    face = face.faces(">Z").edges().chamfer(0.5).edges("|Z").chamfer(0.5)
    c = k["groove_clr"]
    face = face.cut(ring(t0 - c, t1 + c, hz - 0.01, hz + k["groove_d"]))
    # relief for the beads: the groove's outer wall stepped out over the bead's height
    face = face.cut(ring(t0 - c - k["bead"] - 0.05, t0 - c + 0.01, bz - k["bead"] * 1.6 - 0.1, bz + k["bead"] * 1.6 + 0.1))
    face = _face_features(face, TH)
    return _notches(face, hz, TH), _notches(back, 0, hz)
