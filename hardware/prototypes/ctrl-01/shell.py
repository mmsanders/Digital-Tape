"""CTRL-01 shell: the full 68 x 110 x 29 mm case, split at mid-depth.

The back half is the chassis. Inside it the transport is sectioned off in its
own bay (Michael, 26 Oct: "lock it in" so it carries forward unchanged). The keys
ride in a separate comb (spine, fins, spring bosses) that drops into the back half
after the slide lock (30 Oct). The back half locates the lock, the comb and the
blocker; the front half adds flat faces parallel to the seam, the partition that
closes the bay and clamps the comb, and clearance.

The rest of the case is the card-slot test (cards.py).
"""

from __future__ import annotations

import math

import cadquery as cq

import layout as L
import cards as C
import mech as M


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


# left-side ridges sit clear of the key openings: between Record and Play, and below Stop
_gap = (L.key_y("rec") + L.key_y("play")) / 2
RIDGES = (("top", L.W / 2), ("bottom", L.W / 2),
          ("right", L.H * 0.25), ("right", L.H * 0.5), ("right", L.H * 0.75),
          ("left", _gap), ("left", (L.key_y("stop") + L.BLOCK_YP / 2 + L.H - L.CORNER_R) / 2))
RIDGE_LEN = L.RIDGE_LEN


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
    y = L.H - L.CORNER_R - 8.0
    return _box(L.W - 1.5, L.W + 1, y, y + 6.0, L.SEAM - 1.0, L.SEAM + 1.0)


def key_apertures() -> cq.Workplane:
    """Two openings: Record on its own, and one for Play..Stop side by side (1 Nov)."""
    c, hy = L.HOLE_CLR, L.BLOCK_YP / 2
    z0, z1 = L.BLOCK_Z[0] - c, L.BLOCK_Z[1] + c
    rec = _box(-1, L.WALL + 0.1, L.key_y("rec") - hy - c, L.key_y("rec") + hy + c, z0, z1)
    row = _box(-1, L.WALL + 0.1, L.key_y("play") - hy - c, L.key_y("stop") + hy + c, z0, z1)
    return rec.union(row).edges("|X").fillet(L.BLOCK_R + c)


# --- the transport bay ---------------------------------------------------------

def comb() -> cq.Workplane:
    """The key comb: spine, the fins between the keys with their rail tunnels, and the
    key-spring bosses. A separate part (Michael, 30 Oct: the guides printed on the back
    half covered the slide lock, and the closed tunnels trapped the keys). The keys
    slide into it from the outer end on the bench; the comb then drops into the back
    half over the slide lock, located by the end walls and a backstop wall, and the
    front half's partition clamps it."""
    s0, s1 = L.SPINE_X
    y0, y1 = L.BAY_Y
    c = L.COMB_CLR
    z_key_front = L.KEY_Z - L.STEM_XP / 2                         # 7.5
    parts = [_box(s0, s1, y0 + 1.5 + c, y1 - 1.5 - c, z_key_front, L.T - L.WALL - c)]
    fin_z1 = L.KEY_Z + L.PAWL_XP[0] - 0.2                          # stops short of the pawls (20.3)
    half = (L.PITCH - L.STEM_YP) / 2 - L.SLIDE_CLR                 # 1.85
    slot_x1 = L.KEY_BOTTOM + L.TRAVEL + 0.5
    rz0, rz1 = L.KEY_Z - L.RAIL_W / 2 - L.SLIDE_CLR, L.KEY_Z + L.RAIL_W / 2 + L.SLIDE_CLR
    for b in L.FIN_Y:
        fin = _box(L.FIN_X0 + 0.02, s0 + 0.01, b - half, b + half, z_key_front, fin_z1)   # the block lands here
        for yc in (b - L.PITCH / 2, b + L.PITCH / 2):
            name = next((n for n in L.KEYS if abs(L.key_y(n) - yc) < 1e-6), None)
            if name is None:
                continue
            sgn = 1 if yc > b else -1
            yy = (yc - sgn * (L.STEM_YP / 2 + L.RAIL_P + L.SLIDE_CLR), yc - sgn * (L.STEM_YP / 2))
            fin = fin.cut(_box(L.FIN_X0 - 1, slot_x1, min(yy), max(yy), rz0, rz1))
        parts.append(fin)
    for n in L.KEYS:
        parts.append(cq.Workplane("YZ", origin=(s0 - L.SPRING_BOSS_L, 0, 0))
                     .center(L.key_y(n), L.KEY_Z).circle(L.BOSS_D / 2).extrude(L.SPRING_BOSS_L + 0.01))
    out = parts[0]
    for p in parts[1:]:
        out = out.union(p)
    return out


def snap_lips() -> cq.Workplane:
    """The 0.35 mm lips the slide lock snaps past: interference on the way in is intended."""
    bx0, bx1 = L.BAR_X
    cz = L.BAR_Z[0] - 0.15 - 0.2
    ly0, ly1 = L.BAR_Y0 + 1.0, L.FIN_Y[-1] - 3
    return (_box(bx0 - L.CHANNEL_CLR - 0.01, bx0 - L.CHANNEL_CLR + L.LIP, ly0, ly1, cz, cz + 0.2)
            .union(_box(bx1 + L.CHANNEL_CLR - L.LIP, bx1 + L.CHANNEL_CLR + 0.01, ly0, ly1, cz, cz + 0.2)))


def bay_back() -> cq.Workplane:
    """Back-half bay: end walls, the backstop wall that takes the comb's spring load,
    bar channel with lips, bar stop, spring housing, and the blocker's pedestal."""
    s0, s1 = L.SPINE_X
    y0, y1 = L.BAY_Y
    c = L.COMB_CLR
    parts = [
        _box(L.WALL - 0.01, s1, y0, y0 + 1.5, L.SEAM, L.T - L.WALL + 0.01),
        _box(L.WALL - 0.01, s1, y1 - 1.5, y1, L.SEAM, L.T - L.WALL + 0.01),
        _box(s1 + c, s1 + c + L.BACKSTOP_T, y0, y1, L.SEAM, L.T - L.WALL + 0.01),
    ]
    half = (L.PITCH - L.STEM_YP) / 2 - L.SLIDE_CLR                 # 1.85
    # bar channel: two walls up from the back wall, lips over the bar's front edges
    bx0, bx1 = L.BAR_X
    cz = L.BAR_Z[0] - 0.15 - 0.2                                    # lip underside 0.15 in front of the bar
    wy0, wy1 = L.BAR_Y0 - 2.0, y1 - 1.5            # the lock starts at Play: Record has no pawl
    parts += [
        _box(bx0 - L.CHANNEL_CLR - 1.0, bx0 - L.CHANNEL_CLR, wy0, wy1, cz, L.T - L.WALL + 0.01),
        _box(bx1 + L.CHANNEL_CLR, bx1 + L.CHANNEL_CLR + 1.0, wy0, wy1, cz, L.T - L.WALL + 0.01),
        snap_lips(),
        _box(bx0 - L.CHANNEL_CLR, bx1 + L.CHANNEL_CLR, wy0, L.BAR_Y0 - 0.15, cz, L.T - L.WALL + 0.01),
    ]
    # spring housing: bore along Y, the spring's seat SPRING_REST below the bar's end at rest
    bar_end = L.FIN_Y[-1] + 1.9
    h0 = bar_end + L.BAR_TRAVEL_MAX + 0.4
    housing = _box(bx0 - L.CHANNEL_CLR, bx1 + L.CHANNEL_CLR, h0, wy1, 21.0, L.T - L.WALL + 0.01)
    bore = (cq.Workplane("XZ", origin=(0, h0 - 1, 0)).center((bx0 + bx1) / 2, L.BAR_SPRING_Z)
            .circle(2.5).extrude(-(bar_end + L.SPRING_REST - h0 + 1)))
    parts.append(housing.cut(bore))
    # pedestal in the gap slot: holds the latch slider down
    gy0, gy1 = L.FIN_Y[1] + half + c, L.FIN_Y[2] - half - c
    ped = _box(bx1 + L.CHANNEL_CLR + 1.0, s0 - c, gy0, gy1, L.BLOCKER_Z[1] + 0.2, L.T - L.WALL + 0.01)
    parts += [ped]
    out = parts[0]
    for p in parts[1:]:
        out = out.union(p)
    return out


def bay_front() -> cq.Workplane:
    """Front-half bay: the partition and end walls that close the bay, and the latch
    slider's inner guide rail."""
    s0, s1 = L.SPINE_X
    y0, y1 = L.BAY_Y
    z_key_front = L.KEY_Z - L.STEM_XP / 2
    parts = [
        _box(s0, s1, y0, y1, L.WALL - 0.01, z_key_front - 0.1),
        _box(L.WALL - 0.01, s1, y0, y0 + 1.5, L.WALL - 0.01, L.SEAM),
        _box(L.WALL - 0.01, s1, y1 - 1.5, y1, L.WALL - 0.01, L.SEAM),
        _box(s0, s1, y0, y0 + 1.5, L.WALL - 0.01, z_key_front - 0.1),
        _box(s0, s1, y1 - 1.5, y1, L.WALL - 0.01, z_key_front - 0.1),
    ]
    # the latch slider's inner guide: a rail along the whole of its travel. Its outer
    # edge runs on the partition. Long guides, so it cannot turn (1 Nov)
    sy0, sy1 = M.slider_y()
    parts.append(_box(L.GUIDE_X[0], L.GUIDE_X[1], sy0 - 1.0, sy1 + L.TRAVEL + 1.0, L.WALL - 0.01, L.LATCH_TOP + 0.1))
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
