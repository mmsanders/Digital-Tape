"""CTRL-01 shell: the full 68 x 110 x 29 mm case, split at mid-depth.

The back half is the chassis. Inside it the transport is sectioned off in its
own bay (Michael, 26 Oct: "lock it in" so it carries forward unchanged): a spine
wall closes the bay on the inside, and everything that locates a key, the slide
lock or the blocker hangs off the back half. The front half only adds flat faces
parallel to the seam, the partition that closes the bay, and clearance.

The rest of the case is the card-slot test (cards.py).
"""

from __future__ import annotations

import math

import cadquery as cq

import layout as L
import cards as C


def _box(x0, x1, y0, y1, z0, z1) -> cq.Workplane:
    return (cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, y0, z0)))


def _rrect(inset: float, z0: float, z1: float) -> cq.Workplane:
    """The plan outline inset by `inset`, extruded from z0 to z1."""
    w, h = L.W - 2 * inset, L.H - 2 * inset
    r = max(L.CORNER_R - inset, 0.5)
    return (cq.Workplane("XY", origin=(L.W / 2, L.H / 2, z0)).rect(w, h)
            .extrude(z1 - z0).edges("|Z").fillet(r))


def shell_walls() -> cq.Workplane:
    outer = _rrect(0, 0, L.T).faces(">Z or <Z").edges().chamfer(L.EDGE_CH)
    return outer.cut(_rrect(L.WALL, L.WALL, L.T - L.WALL))


# --- the tongue, groove and snap ridges ----------------------------------------

def tongue() -> cq.Workplane:
    t0 = L.WALL - L.TONGUE_W
    return _rrect(t0, L.SEAM - L.TONGUE_H, L.SEAM + 0.01).cut(_rrect(L.WALL, 0, L.T))


def groove() -> cq.Workplane:
    t0 = L.WALL - L.TONGUE_W - L.GROOVE_CLR
    return _rrect(t0, L.SEAM - L.TONGUE_H - L.GROOVE_CLR, L.SEAM + 0.01).cut(_rrect(L.WALL + 0.01, 0, L.T))


RIDGES = (("top", 14.0), ("top", 54.0), ("bottom", 14.0), ("bottom", 54.0),
          ("right", 22.0), ("right", 88.0), ("left", 16.0), ("left", 95.0))
RIDGE_LEN = 6.0


def _ridge(side: str, at: float, grow: float = 0.0) -> cq.Workplane:
    """A 45 degree ridge on the tongue's outer face, pointing out into the groove wall."""
    f = L.WALL - L.TONGUE_W                       # tongue outer face, inset from the outside
    zc, half = L.SEAM - L.TONGUE_H / 2, 0.3 + grow
    h = L.RIDGE_H + grow
    tri = [(0.0, zc - half), (-h, zc), (0.0, zc + half)]
    if side in ("top", "bottom"):
        y = f if side == "top" else L.H - f
        s = 1 if side == "top" else -1
        pts = [(y + s * u, z) for u, z in tri]
        return (cq.Workplane("YZ", origin=(at - RIDGE_LEN / 2 - grow, 0, 0)).polyline(pts).close()
                .extrude(RIDGE_LEN + 2 * grow))
    x = f if side == "left" else L.W - f
    s = 1 if side == "left" else -1
    pts = [(x + s * u, z) for u, z in tri]
    return (cq.Workplane("XZ", origin=(0, at - RIDGE_LEN / 2 - grow, 0)).polyline(pts).close()
            .extrude(-(RIDGE_LEN + 2 * grow)))


def coin_notch() -> cq.Workplane:
    return _box(L.W - 1.5, L.W + 1, 94.0, 100.0, L.SEAM - 1.0, L.SEAM + 1.0)


def key_apertures() -> cq.Workplane:
    out = None
    for n in L.KEYS:
        c = L.key_y(n)
        ex = L.STEM_XP / 2 - L.INSET + L.HOLE_CLR
        ey = L.STEM_YP / 2 - L.INSET + L.HOLE_CLR
        a = _box(-1, L.WALL + 0.1, c - ey, c + ey, L.KEY_Z - ex, L.KEY_Z + ex)
        out = a if out is None else out.union(a)
    return out


# --- the transport bay ---------------------------------------------------------

def bay_back() -> cq.Workplane:
    """Back-half bay: spine, end walls, fins with rail slots, spring bosses, bar
    channel with lips, bar stop, spring housing, and the blocker's pedestal."""
    s0, s1 = L.SPINE_X
    y0, y1 = L.BAY_Y
    z_key_front = L.KEY_Z - L.STEM_XP / 2                         # 7.5
    parts = [
        _box(s0, s1, y0, y1, z_key_front, L.T - L.WALL + 0.01),   # spine
        _box(L.WALL - 0.01, s1, y0, y0 + 1.5, L.SEAM, L.T - L.WALL + 0.01),
        _box(L.WALL - 0.01, s1, y1 - 1.5, y1, L.SEAM, L.T - L.WALL + 0.01),
    ]
    fin_z1 = L.KEY_Z + L.PAWL_XP[0] - 0.2                          # stops short of the pawls (20.3)
    half = (L.PITCH - L.STEM_YP) / 2 - L.SLIDE_CLR                 # 1.85
    slot_x1 = L.KEY_BOTTOM + L.TRAVEL + 0.5
    rz0, rz1 = L.KEY_Z - L.RAIL_W / 2 - L.SLIDE_CLR, L.KEY_Z + L.RAIL_W / 2 + L.SLIDE_CLR
    for b in L.FIN_Y:
        fin = _box(L.WALL, s0 + 0.01, b - half, b + half, z_key_front, fin_z1)
        for c in (b - L.PITCH / 2, b + L.PITCH / 2):
            name = next((n for n in L.KEYS if abs(L.key_y(n) - c) < 1e-6), None)
            if name is None:
                continue
            s = 1 if c > b else -1
            yy = (c - s * (L.STEM_YP / 2 + L.RAIL_P + L.SLIDE_CLR), c - s * (L.STEM_YP / 2))
            fin = fin.cut(_box(L.WALL - 1, slot_x1, min(yy), max(yy), rz0, rz1))
        parts.append(fin)
    for n in L.KEYS:
        boss = (cq.Workplane("YZ", origin=(s0 - L.SPRING_BOSS_L, 0, 0))
                .center(L.key_y(n), L.KEY_Z).circle(L.BOSS_D / 2).extrude(L.SPRING_BOSS_L + 0.01))
        parts.append(boss)
    # bar channel: two walls up from the back wall, lips over the bar's front edges
    bx0, bx1 = L.BAR_X
    cz = L.BAR_Z[0] - 0.15 - 0.2                                    # lip underside 0.15 in front of the bar
    wy0, wy1 = y0 + 1.5, y1 - 1.5
    parts += [
        _box(bx0 - L.CHANNEL_CLR - 1.0, bx0 - L.CHANNEL_CLR, wy0, wy1, cz, L.T - L.WALL + 0.01),
        _box(bx1 + L.CHANNEL_CLR, bx1 + L.CHANNEL_CLR + 1.0, wy0, wy1, cz, L.T - L.WALL + 0.01),
        _box(bx0 - L.CHANNEL_CLR - 0.01, bx0 - L.CHANNEL_CLR + L.LIP, L.FIN_Y[0], L.FIN_Y[-1] - 3, cz, cz + 0.2),
        _box(bx1 + L.CHANNEL_CLR - L.LIP, bx1 + L.CHANNEL_CLR + 0.01, L.FIN_Y[0], L.FIN_Y[-1] - 3, cz, cz + 0.2),
        _box(bx0 - L.CHANNEL_CLR, bx1 + L.CHANNEL_CLR, wy0, L.BAR_Y0 - 0.15, cz, L.T - L.WALL + 0.01),
    ]
    # spring housing: bore along Y, the spring's seat SPRING_REST below the bar's end at rest
    bar_end = L.FIN_Y[-1] + 1.9
    h0 = bar_end + L.BAR_TRAVEL_MAX + 0.4
    housing = _box(bx0 - L.CHANNEL_CLR, bx1 + L.CHANNEL_CLR, h0, wy1, 21.0, L.T - L.WALL + 0.01)
    bore = (cq.Workplane("XZ", origin=(0, h0 - 1, 0)).center(9.0, L.BAR_SPRING_Z)
            .circle(2.5).extrude(-(bar_end + L.SPRING_REST - h0 + 1)))
    parts.append(housing.cut(bore))
    # blocker pedestal in the gap slot, with relief for Record's finger
    gy0, gy1 = L.FIN_Y[1] + half, L.FIN_Y[2] - half
    ped = _box(bx1 + L.CHANNEL_CLR + 1.0, s0, gy0, gy1, L.BLOCKER_Z[1] + 0.2, L.T - L.WALL + 0.01)
    ped = ped.cut(_box(7.0, 17.3, gy0 - 0.1, 35.3, 2.5, L.FINGER_Z[1] + 0.2))
    ground = _box(17.2, 18.7, 33.4, gy1, L.BLOCKER_Z[0], L.BLOCKER_Z[1] + 0.21)
    column = _box(7.0, 8.0, 36.0, gy1 + 0.01, L.BLOCKER_Z[0], fin_z1)
    parts += [ped, ground, column]
    out = parts[0]
    for p in parts[1:]:
        out = out.union(p)
    return out


def bay_front() -> cq.Workplane:
    """Front-half bay: the partition and end walls that close the bay, and flat lands
    on the front of FF, Rew and Stop."""
    s0, s1 = L.SPINE_X
    y0, y1 = L.BAY_Y
    z_key_front = L.KEY_Z - L.STEM_XP / 2
    parts = [
        _box(s0, s1, y0, y1, L.WALL - 0.01, z_key_front - 0.1),
        _box(L.WALL - 0.01, s0, y0, y0 + 1.5, L.WALL - 0.01, L.SEAM),     # the spine closes the rest
        _box(L.WALL - 0.01, s0, y1 - 1.5, y1, L.WALL - 0.01, L.SEAM),
        _box(s0, s1, y0, y0 + 1.5, L.WALL - 0.01, z_key_front - 0.1),
        _box(s0, s1, y1 - 1.5, y1, L.WALL - 0.01, z_key_front - 0.1),
    ]
    for n in ("ff", "rew", "stop"):
        c = L.key_y(n)
        # solid from the front wall: a flat face 0.1 in front of the key, nothing to bridge
        parts.append(_box(3.0, L.KEY_BOTTOM + L.TRAVEL, c - 3.0, c + 3.0, L.WALL - 0.01, z_key_front - 0.1))
    out = parts[0]
    for p in parts[1:]:
        out = out.union(p)
    return out


# --- halves ------------------------------------------------------------------------

def halves() -> tuple[cq.Workplane, cq.Workplane]:
    walls = shell_walls()
    front = walls.intersect(_box(-1, L.W + 1, -1, L.H + 1, -1, L.SEAM))
    back = walls.intersect(_box(-1, L.W + 1, -1, L.H + 1, L.SEAM, L.T + 1))
    back = back.union(tongue()).union(bay_back())
    front = front.union(bay_front())
    for side, at in RIDGES:
        back = back.union(_ridge(side, at))
        front = front.cut(_ridge(side, at, grow=0.05))
    for s in C.SLOTS:
        add, cut = C.pocket(s)
        if s.layer == "front":
            front = front.union(add).cut(cut)
        else:
            back = back.union(add).cut(cut)
    front = front.cut(groove())            # last, so nothing added above refills it
    for side, at in RIDGES:
        front = front.cut(_ridge(side, at, grow=0.05))
    for p in (key_apertures(), coin_notch()):
        front, back = front.cut(p), back.cut(p)
    return front, back
