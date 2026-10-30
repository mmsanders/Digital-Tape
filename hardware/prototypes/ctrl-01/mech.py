"""CTRL-01 mechanism: shrunk keys, slide lock (bar) and the Record latch.

All the latch geometry lives in two 2D outlines in the (y', z') plane: a key's
catch and the bar's pawl. `kinematics()` moves one against the other exactly as
the rig will, so the gates check behaviour (does it latch, how deep, does Stop
free it) rather than shapes.

Record has no catch (31 Oct): it latches to Play through a slider that Play's
diagonal rail drives. `record_latch()` moves Record's toe against the slider's
hook the same way, in plan (device X, Y).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cadquery as cq
from shapely.geometry import Polygon, box
from shapely.affinity import rotate, translate
from shapely.ops import unary_union

import layout as L


# --------------------------------------------------------------------------
# 2D outlines, key frame (y', z')
# --------------------------------------------------------------------------

def catch_profile(name: str, raise_: float | None = None) -> list[tuple[float, float]]:
    """The catch on a key's +x' face.

    Latch keys: the P business end (1.2 mm hook, 45 degree ramp, flat ledge),
    with the ledge and ramp lines run on to the edge of the face (Michael, 26 Oct).
    Stop: no ledge; one even ramp then a flat to the shoulder. Record's key carries
    none (31 Oct); its outline here only feeds the old gates' history.
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
    return [(e, bot), (e, top - L.PAWL_CH), (e + L.PAWL_CH, top), (back_end, top + L.PAWL_RISE),
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
        "play": [[(-x, y) for x, y in tri(0)]],            # flipped 31 Oct (Michael)
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
    if name != "rec":
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
        body = body.union(_toe_and_web())
    if name == "play":
        body = body.union(_arm_and_rail())
    return body


FRONT_CLR = 0.2     # finger and arm stay this far in front of the keys' front plane (the fins' edge)
JOIN_EDGE = 3.49    # front-zone features span the key's whole front face (|y'| <= 3.5); the
                    # nearest fin starts at 3.65, so the joint never reaches a fin
ARM_H = 6.0         # Play's arm, z' extent (taller than the finger: it carries the pin)


def _root(y0: float, y1: float, h: float) -> cq.Workplane:
    """The joint between a front-zone feature and its key: a block bridging the
    FRONT_CLR gap across the key's own front face (|y'| <= JOIN_EDGE), sunk 0.3 mm
    into the key so the two fuse over the whole face."""
    x = -L.STEM_XP / 2
    return _box(x - FRONT_CLR - 0.01, x + 0.3, y0, y1, 0, h)


def _toe_and_web() -> cq.Workplane:
    """Record's web and toe. The web spans the key's whole front face (joining it
    across 7 x 3.5 mm) and runs along the row into the gap; the toe hangs from its
    end, over the latch slider's floor, with its leading inner corner chamfered so
    it pushes the slider's hook aside."""
    x0, x1 = L.WEB_Z[0] - L.KEY_Z, L.WEB_Z[1] - L.KEY_Z
    yc = L.key_y("rec")
    ty0, ty1 = L.TOE_Y[0] - yc, L.TOE_Y[1] - yc
    web = _box(x0, x1, -JOIN_EDGE, ty1, 0, 3.5).union(_root(-JOIN_EDGE, JOIN_EDGE, 3.5))
    h = L.TOE_X[1] - L.TOE_X[0]
    c = L.TOE_CH
    toe = _prism_yz([(ty0, 0), (ty1 - c, 0), (ty1, c), (ty1, h), (ty0, h)],
                    L.TOE_Z[0] - L.KEY_Z, x0 + 0.01)
    return web.union(toe)


def _arm_and_rail() -> cq.Workplane:
    """Play's arm and the diagonal rail (31 Oct; was a square pin) that drives the
    latch slider both ways and keeps it from turning. The arm spans the key's whole
    front face and joins it across 7 x 6 mm."""
    x0, x1 = L.ARM_Z[0] - L.KEY_Z, L.ARM_Z[1] - L.KEY_Z - FRONT_CLR
    py = L.PIN_Y - L.key_y("play")
    arm = _box(x0, x1, py - 1.6, JOIN_EDGE, 0, ARM_H).union(_root(-JOIN_EDGE, JOIN_EDGE, ARM_H))
    # rail outline in (y', z'): device (X, Y) -> (Y - centre, KEY_BOTTOM - X)
    pts = [(y - L.key_y("play"), L.KEY_BOTTOM - x) for x, y in rail_outline().exterior.coords[:-1]]
    rail = _prism_yz(pts, L.LATCH_FLOOR_Z[0] + 0.2 - L.KEY_Z, x0 + 0.01)
    return arm.union(rail)


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


# --------------------------------------------------------------------------
# Record latch: plan outlines (device X, Y; slider at rest) and its kinematics
# --------------------------------------------------------------------------

def toe_outline() -> Polygon:
    x0, x1 = L.TOE_X
    y0, y1 = L.TOE_Y
    c = L.TOE_CH
    return Polygon([(x0, y0), (x1, y0), (x1, y1 - c), (x1 - c, y1), (x0, y1)])


def hook_outline() -> Polygon:
    """The slider's hook. With Play latched (slider shifted PLAY_HOLD) it overlaps the
    toe's lane by HOOK_OVERLAP from the far side; its inner corner is chamfered."""
    x0, x1 = L.HOOK_X
    y0 = L.TOE_Y[1] - L.HOOK_OVERLAP - L.PLAY_HOLD
    return Polygon([(x0 + 0.4, y0), (x1, y0), (x1, y0 + L.HOOK_W), (x0, y0 + L.HOOK_W), (x0, y0 + 0.4)])


def rail_outline() -> Polygon:
    cx, cy = L.RAIL_C
    r = box(cx - L.RAIL_L / 2, cy - L.RAIL_T / 2, cx + L.RAIL_L / 2, cy + L.RAIL_T / 2)
    return rotate(r, -45, origin=(cx, cy))


def slot_outline() -> Polygon:
    """The rail's path through the slider: Play moves the rail +X, the slider moves +Y
    by the same amount, so in the slider the rail runs along its own axis."""
    d = L.TRAVEL + 0.4                                  # 0.2 spare at each end
    swept = rail_outline().union(translate(rail_outline(), d, -d)).convex_hull
    return translate(swept, -0.2, 0.2).buffer(L.SLOT_CLR, join_style=2)


def slider_outlines() -> tuple[Polygon, Polygon]:
    """(floor, raised) plan outlines. The floor runs under Record's lane; everything
    raised stays out of it except the hook."""
    floor = unary_union([box(8.2, 29.9, 17.0, 41.0), box(5.0, 41.0, 17.0, 48.5)]).difference(slot_outline())
    raised = unary_union([hook_outline(), box(8.2, 29.9, 8.7, 36.4),
                          unary_union([box(8.2, 36.4, 17.0, 41.0), box(5.0, 41.0, 17.0, 48.5)])
                          .difference(slot_outline())])
    return floor, raised


def _toe_hits(r: float, s: float) -> bool:
    _, raised = slider_outlines()
    return translate(toe_outline(), r, 0).intersection(translate(raised, 0, s)).area > 1e-5


@dataclass(frozen=True)
class RecordLatch:
    alone_clear: bool          # Record alone, Play up: the toe meets nothing
    play_press_clear: bool     # Play pressed, Record up: the hook passes in front of the toe
    max_push: float            # deepest Play is nudged while Record goes past the hook
    push_slope: float          # steepest slider push per mm of Record: a ramp gives ~1, a wall jumps
    held_at: float | None      # Record's depth once released, Play latched (None: not held)
    hold_is_ledge: bool
    released_below: float | None   # slider shift below which Record is free again


def record_latch(step: float = 0.05) -> RecordLatch:
    _, raised = slider_outlines()
    toe = toe_outline()
    hits = lambda r, s: translate(toe, r, 0).intersection(translate(raised, 0, s)).area > 1e-5
    rs = [round(i * step, 4) for i in range(int(L.TRAVEL / step) + 1)]
    alone = not any(hits(r, 0.0) for r in rs)
    play_clear = not any(hits(0.0, s) for s in rs)
    # Record pressed with Play latched: the slider is pushed only as far as it must be
    pushes = []
    for r in rs:
        s = L.PLAY_HOLD
        if hits(r, s):
            lo, hi = s, L.TRAVEL + 1.0
            if hits(r, hi):
                pushes.append(math.inf)
                continue
            for _ in range(30):
                mid = (lo + hi) / 2
                lo, hi = (lo, mid) if not hits(r, mid) else (mid, hi)
            s = hi
        pushes.append(s)
    held, ledge = None, False
    if not hits(L.TRAVEL, L.PLAY_HOLD):
        for r in reversed(rs):
            if hits(r, L.PLAY_HOLD):
                held = round(r + step, 4)
                ov = translate(toe, r, 0).intersection(translate(raised, 0, L.PLAY_HOLD))
                minx, miny, maxx, maxy = ov.bounds
                ledge = (maxx - minx) <= step * 1.5 and (maxy - miny) >= 0.5
                break
    released = None
    if held is not None:
        below = [r for r in rs if r <= held - step]
        for s in [round(L.PLAY_HOLD - i * step, 4) for i in range(int(L.PLAY_HOLD / step) + 1)]:
            if not any(hits(r, s2) for r in below for s2 in (s,)):
                released = s
                break
    slope = max((b - a) / step for a, b in zip(pushes, pushes[1:]))     # the snap back is a drop, not a push
    return RecordLatch(alone, play_clear, max(pushes) - L.PLAY_HOLD, slope, held, ledge, released)


def latch(play_depth: float = 0.0) -> cq.Workplane:
    """The latch slider, device frame, at Play depth `play_depth` (it moves +Y with Play)."""
    floor, raised = slider_outlines()

    def solid(poly, z0, z1):
        out = None
        for g in ([poly] if poly.geom_type == "Polygon" else list(poly.geoms)):
            w = cq.Workplane("XY", origin=(0, 0, z0)).polyline(list(g.exterior.coords)[:-1]).close()
            for hole in g.interiors:
                w = w.polyline(list(hole.coords)[:-1]).close()
            w = w.extrude(z1 - z0)
            out = w if out is None else out.union(w)
        return out

    z0, z1 = L.LATCH_FLOOR_Z
    b = solid(floor, z0, z1).union(solid(raised, z1 - 0.01, L.LATCH_TOP))
    return b.translate((0, play_depth, 0))
