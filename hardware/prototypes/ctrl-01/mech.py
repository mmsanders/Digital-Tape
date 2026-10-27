"""CTRL-01 mechanism: shrunk keys, slide lock (bar) and the Record blocker.

All the latch geometry lives in two 2D outlines in the (y', z') plane: a key's
catch and the bar's pawl. `kinematics()` moves one against the other exactly as
the rig will, so the gates check behaviour (does it latch, how deep, does Stop
free it, when does Record first touch the lock) rather than shapes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cadquery as cq
from shapely.geometry import Polygon
from shapely.affinity import translate

import layout as L


# --------------------------------------------------------------------------
# 2D outlines, key frame (y', z')
# --------------------------------------------------------------------------

def catch_profile(name: str, raise_: float | None = None) -> list[tuple[float, float]]:
    """The catch on a key's +x' face.

    Latch keys: the P business end (1.2 mm hook, 45 degree ramp, flat ledge),
    with the ledge and ramp lines run on to the edge of the face (Michael, 26 Oct).
    Record's sits RECORD_RAISE higher so the lock is reached only after the blocker
    has had its say. Stop: no ledge; one even ramp then a flat to the shoulder.
    """
    back = -L.STEM_YP / 2
    if name == "stop":
        tip, z_tip = L.PAWL_EDGE + L.STOP_SHIFT, L.stop_tip_z()
        slope = L.deg_slope(L.STOP_RAMP_DEG)
        z_back = z_tip - slope * (tip - back)
        if z_back >= 0:
            return [(back, z_back), (tip, z_tip), (tip, L.BODY_H), (back, L.BODY_H)]
        y0 = tip - z_tip / slope
        return [(y0, 0.0), (tip, z_tip), (tip, L.BODY_H), (back, L.BODY_H), (back, 0.0)]
    if raise_ is None:
        raise_ = L.RECORD_RAISE if name == "rec" else 0.0
    ledge = L.LEDGE + raise_
    tip = L.PAWL_EDGE + L.HOOK
    z_back = ledge - (tip - back)
    if z_back >= 0:
        return [(back, z_back), (tip, ledge), (back, ledge)]
    y0 = tip - ledge
    return [(y0, 0.0), (tip, ledge), (back, ledge), (back, 0.0)]


def pawl_profile() -> list[tuple[float, float]]:
    """The bar's pawl at rest. Catch region on the left (y' 0.5..2.0), a deeper
    back on the right that runs on toward the bar: the "thick latch"."""
    e, top, bot = L.PAWL_EDGE, L.PAWL_TOP, L.PAWL_TOP - L.PAWL_H
    back_end = e + L.PAWL_LEN
    return [(e, bot), (e, top - L.PAWL_CH), (e + L.PAWL_CH, top), (back_end, top),
            (back_end, 0.0), (e + 1.5, 0.0), (e + 1.5, bot)]


@dataclass(frozen=True)
class Travel:
    contact: float | None      # press depth where the lock first moves
    max_shift: float
    shift_at: dict             # depth -> bar shift
    latched_at: float | None   # depth the key is held at after release (None: returns)
    hold_is_ledge: bool        # the hold is a flat ledge, not a ramp


def _free(tooth: Polygon, pawl: Polygon, s: float, d: float) -> bool:
    return tooth.intersection(translate(pawl, s, d)).area < 1e-5


def bar_shift(tooth: Polygon, pawl: Polygon, d: float, s_max: float = 4.0) -> float:
    """Smallest bar shift (the bar springs push it to the smallest) that clears."""
    if _free(tooth, pawl, 0.0, d):
        return 0.0
    lo, hi = 0.0, s_max
    if not _free(tooth, pawl, hi, d):
        return math.inf
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if _free(tooth, pawl, mid, d) else (mid, hi)
    return hi


def kinematics(name: str, raise_: float | None = None, step: float = 0.02) -> Travel:
    tooth = Polygon(catch_profile(name, raise_))
    pawl = Polygon(pawl_profile())
    depths = [round(i * step, 4) for i in range(int(L.TRAVEL / step) + 1)]
    shifts = {d: bar_shift(tooth, pawl, d) for d in depths}
    contact = next((d for d in depths if shifts[d] > 0.01), None)
    # release from full press: the bar returns as far as it can, the key rises
    latched_at, ledge = None, False
    if shifts[depths[-1]] < 0.01:
        for d in reversed(depths):
            if not _free(tooth, pawl, 0.0, d):
                latched_at = round(d + step, 4)
                ov = tooth.intersection(translate(pawl, 0.0, d))
                minx, miny, maxx, maxy = ov.bounds
                ledge = (maxy - miny) <= step * 1.5 and (maxx - minx) >= 0.5
                break
    return Travel(contact, max(shifts.values()), shifts, latched_at, ledge)


def neighbour_clear(name: str, s_max: float = L.BAR_TRAVEL_MAX) -> bool:
    """A key's pawl, anywhere in the bar's travel, never meets the next key's catch."""
    row = list(L.ROW)
    i = row.index(name)
    if i + 1 >= len(row) or row[i + 1] == "gap":
        return True
    nxt = Polygon(catch_profile(row[i + 1]))
    pawl = Polygon(pawl_profile())
    for s10 in range(0, int(s_max * 10) + 1):
        for d10 in range(0, int(L.TRAVEL * 10) + 1):
            other = translate(nxt, L.PITCH, -d10 / 10)
            if other.intersection(translate(pawl, s10 / 10, 0.0)).area > 1e-5:
                return False
    return True


# --------------------------------------------------------------------------
# Solids
# --------------------------------------------------------------------------

def _box(x0, x1, y0, y1, z0, z1) -> cq.Workplane:
    return (cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, y0, z0)))


def _prism_yz(pts, x0, x1) -> cq.Workplane:
    """A (y', z') outline extruded along x' from x0 to x1."""
    return cq.Workplane("YZ", origin=(x0, 0, 0)).polyline(pts).close().extrude(x1 - x0)


def _icon(name: str, z: float) -> cq.Workplane:
    """Transport symbol cut into the cap top, pointing along +x'."""
    s = 1.3
    tri = lambda c: [(c - s * 0.9, -s), (c - s * 0.9, s), (c + s * 0.9, 0)]
    shapes = {
        "play": [tri(0)],
        "ff": [tri(-1.15), tri(1.15)],
        "rew": [[(-x, y) for x, y in tri(-1.15)], [(-x, y) for x, y in tri(1.15)]],
        "stop": [[(-s, -s), (-s, s), (s, s), (s, -s)]],
    }
    wp = cq.Workplane("XY", origin=(0, 0, z))
    if name == "rec":
        return wp.circle(s * 1.1).extrude(1.0)
    cut = None
    for poly in shapes[name]:
        solid = wp.polyline(poly).close().extrude(1.0)
        cut = solid if cut is None else cut.union(solid)
    return cut


def key_local(name: str, raise_: float | None = None, flip: bool = False) -> cq.Workplane:
    """One key in its own frame, upright as it prints (z' up, underside on the bed)."""
    hx, hy = L.STEM_XP / 2, L.STEM_YP / 2
    body = _box(-hx, hx, -hy, hy, 0, L.BODY_H)
    for y0, y1 in ((hy, hy + L.RAIL_P), (-hy - L.RAIL_P, -hy)):
        body = body.union(_box(-L.RAIL_W / 2, L.RAIL_W / 2, y0, y1, 0, L.BODY_H))
    groove = cq.Workplane("XY").circle(L.GROOVE_OD / 2).circle(L.BOSS_D / 2).extrude(L.GROOVE_D)
    body = body.cut(groove)
    prof = catch_profile(name, raise_)
    if flip:
        zc = L.BODY_H / 2
        prof = [(y, 2 * zc - z) for y, z in prof]
    body = body.union(_prism_yz(prof, hx - 0.01, hx + L.TOOTH_X))
    ex, ey = hx - L.INSET, hy - L.INSET
    body = body.union(_box(-ex, ex, -ey, ey, L.BODY_H - 0.01, L.CAP_Z0 + 0.01))
    cap = (cq.Workplane("XY").box(L.CAP_XP, L.CAP_YP, L.CAP_T, centered=(True, True, False))
           .edges("|Z").fillet(L.CAP_R).faces(">Z").edges().fillet(0.6)
           .translate((0, 0, L.CAP_Z0)))
    body = body.union(cap).cut(_icon(name, L.CAP_Z0 + L.CAP_T - 0.5))
    if name == "rec":
        body = body.union(_finger())
    if name == "play":
        body = body.union(_arm_and_pin())
    return body


FRONT_CLR = 0.2     # finger and arm stay this far in front of the keys' front plane (the fins' edge)
JOIN_Y = 1.0        # front-zone features join the key across its front face from |y'| = 1.0 ...
JOIN_EDGE = 3.4     # ... out to here, inside the key's own outline, where no fin can be
ARM_H = 6.0         # Play's arm, z' extent (taller than the finger: it carries the pin)


def _root(y0: float, y1: float, h: float) -> cq.Workplane:
    """The joint between a front-zone feature and its key: a block bridging the
    FRONT_CLR gap across the key's own front face (|y'| <= JOIN_EDGE), sunk 0.3 mm
    into the key so the two fuse over the whole face."""
    x = -L.STEM_XP / 2
    return _box(x - FRONT_CLR - 0.01, x + 0.3, y0, y1, 0, h)


def _finger() -> cq.Workplane:
    """Record's finger: reaches into the gap in front of the keys and lands on the
    blocker. It starts over the key's own front face, so it joins the key across
    2.4 x 3.5 mm. Its tip's inner corner is bevelled so a returning blocker pushes
    it up rather than jamming."""
    x0, x1 = L.FINGER_Z[0] - L.KEY_Z, L.FINGER_Z[1] - L.KEY_Z - FRONT_CLR
    y0, y1 = JOIN_Y, 9.0
    f = _box(x0, x1, y0, y1, 0, 3.5).union(_root(JOIN_Y, JOIN_EDGE, 3.5))
    bevel = _prism_yz([(y1 - 1.5, -0.01), (y1 + 0.01, -0.01), (y1 + 0.01, 1.51)], x0 - 1, x1 + 1)
    return f.cut(bevel)


def _arm_and_pin() -> cq.Workplane:
    """Play's arm and the square pin (turned 45 degrees) that drives the blocker.
    The arm starts over the key's own front face and joins it across 2.4 x 6 mm."""
    x0, x1 = L.ARM_Z[0] - L.KEY_Z, L.ARM_Z[1] - L.KEY_Z - FRONT_CLR
    py = L.PIN_Y - L.key_y("play")
    arm = _box(x0, x1, py - 1.6, -JOIN_Y, 0, ARM_H).union(_root(-JOIN_EDGE, -JOIN_Y, ARM_H))
    pz = L.KEY_BOTTOM - L.PIN_X_REST
    r = L.PIN_SIDE / math.sqrt(2)
    diamond = [(py - r, pz), (py, pz - r), (py + r, pz), (py, pz + r)]
    pin = _prism_yz(diamond, L.BLOCKER_Z[0] + 0.1 - L.KEY_Z, x0 + 0.01)
    return arm.union(pin)


def joint_area(feature: cq.Workplane, depth: float = 0.1) -> float:
    """Area over which a front-zone feature fuses with the key body: its volume in a
    thin slab just inside the key's front face, divided by the slab's depth."""
    x = -L.STEM_XP / 2
    slab = _box(x + 0.05, x + 0.05 + depth, -L.STEM_YP / 2, L.STEM_YP / 2, 0, L.BODY_H)
    return feature.val().intersect(slab.val()).Volume() / depth


def place_key(part: cq.Workplane, name: str, depth: float = 0.0) -> cq.Workplane:
    """Key frame to device frame: X = KEY_BOTTOM - z' + depth, Y = centre + y', Z = KEY_Z + x'."""
    return (part.rotate((0, 0, 0), (0, 1, 0), -90)
            .translate((L.KEY_BOTTOM + depth, L.key_y(name), L.KEY_Z)))


def key(name: str, depth: float = 0.0) -> cq.Workplane:
    return place_key(key_local(name), name, depth)


def bar(shift: float = 0.0) -> cq.Workplane:
    """The slide lock, device frame. Prints with its back face on the bed, so every
    pawl stands up from it with a root about 3.9 x 3 mm."""
    x0, x1 = L.BAR_X
    z0, z1 = L.BAR_Z
    y_end = L.FIN_Y[-1] + 1.9
    b = _box(x0, x1, L.BAR_Y0, y_end, z0, z1)
    pz0, pz1 = L.KEY_Z + L.PAWL_XP[0], L.KEY_Z + L.PAWL_XP[1] + 0.01
    for n in L.KEYS:
        c = L.key_y(n)
        pts = [(L.KEY_BOTTOM - z, c + y) for y, z in pawl_profile()]
        b = b.union(cq.Workplane("XY", origin=(0, 0, pz0)).polyline(pts).close().extrude(pz1 - pz0))
    # spring boss on the bottom end (pencil spring threads on). The bar prints back
    # face (+Z) down, so the boss's teardrop point faces +Z, toward the bed.
    r = 1.4
    ring = [(9.0 + r * math.cos(math.radians(a)), L.BAR_SPRING_Z + r * math.sin(math.radians(a)))
            for a in range(0, 360, 15) if not (45 < a < 135)] + [(9.0, L.BAR_SPRING_Z + r * math.sqrt(2))]
    ring = sorted(ring, key=lambda p: math.atan2(p[1] - L.BAR_SPRING_Z, p[0] - 9.0))
    boss = (cq.Workplane("XZ", origin=(0, y_end - 0.01, 0)).polyline(ring).close()
            .extrude(-3.0))
    return b.union(boss).translate((0, shift, 0))


def blocker_outline() -> list[tuple[float, float]]:
    """(X, Y) outline of the blocker at rest: the pad (top) and the slotted body."""
    return [(14.7, 31.0), (17.0, 31.0), (17.0, 44.5), (8.2, 44.5), (8.2, 36.0),
            (12.7, 36.0), (12.7, 33.0)]


def blocker_slot() -> list[tuple[float, float]]:
    """(X, Y) outline of the 45 degree slot, at rest: the pin swept over the full
    press, with SLOT_CLR on every flat."""
    r = L.PIN_SIDE / math.sqrt(2) + L.SLOT_CLR * math.sqrt(2)
    x0, y0 = L.PIN_X_REST, L.PIN_Y
    x1, y1 = x0 + L.TRAVEL, y0 - L.TRAVEL
    return [(x0 - r, y0), (x0, y0 + r), (x1 + r, y1), (x1, y1 - r)]


def blocker(play_depth: float = 0.0) -> cq.Workplane:
    z0, z1 = L.BLOCKER_Z
    b = cq.Workplane("XY", origin=(0, 0, z0)).polyline(blocker_outline()).close().extrude(z1 - z0)
    slot = cq.Workplane("XY", origin=(0, 0, z0 - 1)).polyline(blocker_slot()).close().extrude(z1 - z0 + 2)
    return b.cut(slot).translate((0, play_depth, 0))
