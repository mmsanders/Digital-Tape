"""CTRL-01 controls rig: parametric parts.

Owner-directed prototype (Michael, 26 Oct 2026), not a PM-issued round and not
acceptance. The plan and drawings are the "CTRL-01 Controls Rig Plan" canvas.

Key frame (device coordinates, mm):
    x  press direction: 0 at the cap's outer face, increasing inward
    y  along the key row, +y toward the spring housing (Stop end)
    z  device depth, +z toward the back half and the slide lock

Only the key exists so far. Shell halves, slide lock, spring rail and the Play
gate follow once Michael has seen a key.

    python3 hardware/prototypes/ctrl-01/ctrl01.py      writes print/*.stl
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import cadquery as cq

# committed on purpose (Michael, 26 Oct): the per-part stl/ folders elsewhere are ignored
OUT = Path(__file__).resolve().parent / "print"


@dataclass(frozen=True)
class Key:
    # cap: 1.5 proud of the side face plus the 2.5 mm wall it passes through
    cap_y: float = 8.0
    cap_z: float = 12.0
    cap_x: float = 4.0
    cap_round: float = 0.8
    # body behind the wall; 0.8 mm shoulders along the row are the out-stop
    body_x: float = 7.0
    shoulder: float = 0.8
    # pen spring pocket, open at the inner end
    pocket_d: float = 5.0
    pocket_depth: float = 5.0
    # catch: P business end, unchanged from LADDER-01/02
    hook: float = 1.2           # overhang along +y beyond the body
    ledge_x: float = 7.5        # flat retention face, faces the cap
    tip_x: float = 0.6          # straight tip before the 45 degree ramp
    # catch root, carried to the key's inner end ("to the edge")
    root_y: float = 3.0         # root width along y, inside the body footprint
    root_chamfer: float = 1.0   # 45 degree lead-in under the ledge (the "fillet")
    reach_z: float = 3.3        # how far the catch reaches back into the slide lock
    ramp_deg: float = 45.0      # negative control varies this
    icon: str = "ff"            # engraved on the cap: ff | rew | play | stop | rec | none

    @property
    def length(self) -> float:
        return self.cap_x + self.body_x

    @property
    def body_y0(self) -> float:
        return -self.shoulder

    @property
    def body_y1(self) -> float:
        return self.cap_y + self.shoulder


def _catch_profile(k: Key) -> list[tuple[float, float]]:
    """Catch outline in the x-y plane, walked clockwise from the root corner.

    Only the hook (beyond body_y1) meets the slide-lock latch. Inward of the ramp
    that lane stays empty, otherwise the key would push the slide lock early and
    a light touch could pop Play.
    """
    import math

    y_edge = k.body_y1
    y_root = y_edge - k.root_y
    ramp_dx = k.hook / math.tan(math.radians(k.ramp_deg))
    return [
        (k.ledge_x - k.root_chamfer, y_root),
        (k.ledge_x, y_root + k.root_chamfer),
        (k.ledge_x, y_edge + k.hook),                    # flat ledge, faces the cap
        (k.ledge_x + k.tip_x, y_edge + k.hook),          # tip
        (k.ledge_x + k.tip_x + ramp_dx, y_edge),         # ramp back to the body
        (k.length, y_edge),                              # body edge, lane empty
        (k.length, y_root),                              # inner end
    ]


def _icon(k: Key, wp: cq.Workplane) -> cq.Workplane:
    """Engrave a 0.4 mm transport symbol on the cap face (the x = 0 plane)."""
    s = 1.4
    tri = lambda c: [(c - s, -s), (c - s, s), (c + s * 0.9, 0)]
    shapes = {
        "play": [tri(0)],
        "ff": [tri(-1.4), tri(1.4)],
        "rew": [[(-x, y) for x, y in tri(-1.4)], [(-x, y) for x, y in tri(1.4)]],
        "stop": [[(-s, -s), (-s, s), (s, s), (s, -s)]],
    }
    cy, cz = k.cap_y / 2, k.cap_z / 2
    sk = cq.Workplane("YZ")
    if k.icon == "rec":
        cut = sk.center(cy, cz).circle(s).extrude(0.4)
    elif k.icon in shapes:
        cut = None
        for poly in shapes[k.icon]:
            # symbols run along z (the long axis of the cap)
            pts = [(cy + v, cz + u) for u, v in poly]
            solid = sk.polyline(pts).close().extrude(0.4)
            cut = solid if cut is None else cut.union(solid)
    else:
        return wp
    return wp.cut(cut)


def key(k: Key = Key()) -> cq.Workplane:
    cap = (
        cq.Workplane("XY")
        .box(k.cap_x, k.cap_y, k.cap_z, centered=False)
        .faces("<X").edges().fillet(k.cap_round)
    )
    body = (
        cq.Workplane("XY")
        .box(k.body_x, k.body_y1 - k.body_y0, k.cap_z, centered=False)
        .translate((k.cap_x, k.body_y0, 0))
        .faces(">X").edges().chamfer(0.4)
    )
    pocket = (
        cq.Workplane("YZ", origin=(k.length, 0, 0))
        .center(k.cap_y / 2, k.cap_z / 2)
        .circle(k.pocket_d / 2)
        .extrude(-k.pocket_depth)
    )
    # 90 degree drill-point end: prints as a 45 degree roof instead of a bridge
    r = k.pocket_d / 2
    tip = cq.Solid.makeCone(r, 0, r, cq.Vector(k.length - k.pocket_depth, k.cap_y / 2, k.cap_z / 2),
                            cq.Vector(-1, 0, 0))
    pocket = pocket.union(cq.Workplane().add(tip))
    catch = (
        cq.Workplane("XY", origin=(0, 0, k.cap_z))
        .polyline(_catch_profile(k)).close()
        .extrude(k.reach_z)
    )
    part = cap.union(body).union(catch).cut(pocket)
    return _icon(k, part)


def print_pose(part: cq.Workplane, k: Key) -> cq.Workplane:
    """Cap up: the inner end on the bed, press axis vertical.

    The ledge is then a top surface and the ramp a 45 degree underside, and no
    layer line crosses the catch root.
    """
    return part.rotate((0, 0, 0), (0, 1, 0), 90).translate((0, 0, k.length))


def build(out: Path = OUT) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    k = Key()
    p = out / "ctrl01-key-ff.stl"
    cq.exporters.export(print_pose(key(k), k), str(p), tolerance=0.01, angularTolerance=0.1)
    return [p]


if __name__ == "__main__":
    for p in build():
        print(p)
