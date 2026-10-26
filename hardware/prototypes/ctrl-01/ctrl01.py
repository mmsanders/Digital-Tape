"""CTRL-01 controls rig: parametric parts.

Owner-directed prototype (Michael, 26 Oct 2026), not a PM-issued round and not
acceptance. The plan and drawings are the "CTRL-01 Controls Rig Plan" canvas.

The key starts from the LADDER-02 P key exactly. Its body, rails, spring groove
and tooth are rebuilt here from the LADDER-01/02 generator (`rig.py` in Michael's
latch-rig.zip, SHA-256 e49c6a49...882689b), and `old_key()` reproduces the
printed key-P-2.stl to check that. Michael's change, 26 Oct:

  1. body, rails and catch unchanged;
  2. where the stem started, the body carries on up without the rails, inset on
     every side, so a flat shoulder runs round the whole key and stops on the
     shell from inside;
  3. at the height the old cap sat once installed, a cap that is part of the
     same piece. Its flat underside lands on the shell at full press.

Key frame, as in rig.py: X across the slide lock (the tooth is on the -X face),
Y along the key row (rails on the +/-Y faces), Z up, 0 at the key's underside.
The key prints upright as modelled.

    python3 hardware/prototypes/ctrl-01/ctrl01.py      writes print/*.stl
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import math

import cadquery as cq

# committed on purpose (Michael, 26 Oct): the per-part stl/ folders elsewhere are ignored
OUT = Path(__file__).resolve().parent / "print"
FONT = "DejaVu Sans"

# --- LADDER-02, unchanged (rig.py names) -------------------------------------
STEM_X, STEM_Y = 10.0, 11.0
BODY_H = 16.0                # underside to shoulder; the shoulder stops on the shell
RAIL_W, RAIL_P = 3.0, 1.5    # rail ribs on the +/-Y faces: width in X, protrusion in Y
GROOVE_D = 2.2               # spring groove depth around the key's boss
BOSS_D = 3.0                 # FIT-01
SPRING_OD = 5.0              # FIT-01, pen spring
TRAVEL = 6.2                 # full press: cap underside lands on the shell
LID_T = 3.0                  # LADDER shell (lid) thickness the key passes through
TOOTH_X = 2.5                # tooth protrusion from the -X face
RAMP = 2.5                   # 45 degree ramp: run = rise
LEDGE_Z = 12.0               # ledge height above the underside
PAWL_EDGE = 0.5
CAP_X, CAP_Y, CAP_T = 15.0, 16.0, 5.5
CAP_R = 2.5
NECK_D, NECK_FLAT = 6.0, 2.5
SOCKET_D = 4.0
LABEL_DEPTH = 0.6

# --- CTRL-01 ---------------------------------------------------------------
INSET = 1.5                  # extension inset per side (Michael: 1-2 mm, what prints reliably)
HOLE_CLR = 0.4               # shell aperture round the extension, per side (LADDER's lid value)
REST_GAP = 0.5               # LADDER: the tooth clears the pawl top by this much at rest
PAWL_TOP = LEDGE_Z - RAMP - REST_GAP   # pawl top at rest, in the key's own frame
STOP_SHIFT = 2.1             # LADDER: bar shift under Stop; more than any catch is deep
STOP_RAMP_DEG = 30.0         # from the press direction; LADDER's was 45 then a vertical dwell
STOP_FULL_AT = TRAVEL - 0.6  # press depth where the shift is complete; the flat after it
                             # is reached only in the last 0.6 mm, so it is barely felt


@dataclass(frozen=True)
class Key:
    label: str = "P"
    h: float = 1.2           # catch overhang; P
    inset: float = INSET
    hole_clr: float = HOLE_CLR
    full_catch: bool = True  # catch lines run on to the face edge (Michael, 26 Oct)
    role: str = "latch"      # latch | stop
    icon: str = "ff"         # engraved on the cap: ff | rew | play | stop | rec
    stop_full_at: float = STOP_FULL_AT

    @property
    def ext_x(self) -> float:
        return STEM_X - 2 * self.inset

    @property
    def ext_y(self) -> float:
        return STEM_Y - 2 * self.inset

    @property
    def cap_z0(self) -> float:
        """Old cap underside, installed: shoulder + shell + travel."""
        return BODY_H + LID_T + TRAVEL

    @property
    def shoulder_overlap(self) -> float:
        """How far the shoulder reaches past the aperture edge, per side."""
        return self.inset - self.hole_clr


def _box(x0, x1, y0, y1, z0, z1) -> cq.Workplane:
    return (cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, y0, z0)))


def _yz_prism(pts, x0, x1) -> cq.Workplane:
    return cq.Workplane("YZ", origin=(x0, 0, 0)).polyline(pts).close().extrude(x1 - x0)


def tooth_profile(k: Key, flip: bool = False) -> list[tuple[float, float]]:
    """(Y, Z) outline of the tooth: flat ledge on top, 45 degree ramp below.

    LADDER's tooth was a small right triangle whose third, vertical side did no
    work. With `full_catch` the ledge line and the ramp line simply run on until
    they meet the edge of the key face, so the tip, ledge and ramp the pawl sees
    are unchanged and only the root grows. The pawl sits on the tip's side and
    never reaches the extension.

    `flip=True` builds the 23 Sep failure (ramp above, shelf below) so the
    retention gate can be shown to go red.
    """
    if k.role == "stop":
        return stop_profile(k, flip)
    z = LEDGE_Z
    tip = PAWL_EDGE + k.h
    back = -STEM_Y / 2 if k.full_catch else tip - RAMP
    pts = [(back, z - (tip - back)), (tip, z), (back, z)]
    if flip:
        zc = z - RAMP / 2
        pts = [(y, 2 * zc - zz) for y, zz in pts]
    return pts


def stop_profile(k: Key, flip: bool = False) -> list[tuple[float, float]]:
    """(Y, Z) outline of Stop's cam. No ledge anywhere, so it never latches.

    One even ramp, STOP_RAMP_DEG from the press direction, moves the slide lock
    STOP_SHIFT by press depth `stop_full_at`; then a flat runs to the top of the
    body. Like the latch keys' catch, both lines run on to the edge of the face:
    the ramp down to the face's far edge (or its bottom, if it gets there first),
    the flat up to the shoulder.
    """
    tip = PAWL_EDGE + STOP_SHIFT
    z_tip = PAWL_TOP + k.stop_full_at
    slope = 1 / math.tan(math.radians(STOP_RAMP_DEG))      # dz per dy
    back = -STEM_Y / 2
    z_back = z_tip - slope * (tip - back)
    if z_back >= 0:
        pts = [(back, z_back), (tip, z_tip), (tip, BODY_H), (back, BODY_H)]
    else:
        y0 = tip - z_tip / slope
        pts = [(y0, 0.0), (tip, z_tip), (tip, BODY_H), (back, BODY_H), (back, 0.0)]
    if flip:
        zc = BODY_H / 2
        pts = [(y, 2 * zc - zz) for y, zz in pts]
    return pts


def _icon(k: Key) -> cq.Workplane:
    """Transport symbol to engrave on the cap top, 0.6 mm deep, pointing along +X."""
    s = 2.2
    tri = lambda c: [(c - s * 0.9, -s), (c - s * 0.9, s), (c + s * 0.9, 0)]
    shapes = {
        "play": [tri(0)],
        "ff": [tri(-1.9), tri(1.9)],
        "rew": [[(-x, y) for x, y in tri(-1.9)], [(-x, y) for x, y in tri(1.9)]],
        "stop": [[(-s, -s), (-s, s), (s, s), (s, -s)]],
    }
    z = k.cap_z0 + CAP_T - LABEL_DEPTH
    if k.icon == "rec":
        return cq.Workplane("XY", origin=(0, 0, z)).circle(s).extrude(1.0)
    cut = None
    for poly in shapes[k.icon]:
        solid = cq.Workplane("XY", origin=(0, 0, z)).polyline(poly).close().extrude(1.0)
        cut = solid if cut is None else cut.union(solid)
    return cut


def _body(k: Key, flip: bool = False, tooth: bool = True) -> cq.Workplane:
    """The LADDER-02 key below its shoulder: stem, rails, spring groove, tooth."""
    body = _box(-STEM_X / 2, STEM_X / 2, -STEM_Y / 2, STEM_Y / 2, 0, BODY_H)
    for s in (-1, 1):
        y0, y1 = (STEM_Y / 2, STEM_Y / 2 + RAIL_P) if s > 0 else (-STEM_Y / 2 - RAIL_P, -STEM_Y / 2)
        body = body.union(_box(-RAIL_W / 2, RAIL_W / 2, y0, y1, 0, BODY_H))
    groove = (cq.Workplane("XY").circle((SPRING_OD + 0.8) / 2).circle(BOSS_D / 2)
              .extrude(GROOVE_D))
    body = body.cut(groove)
    if tooth:
        body = body.union(_yz_prism(tooth_profile(k, flip), -STEM_X / 2 - TOOTH_X, -STEM_X / 2 + 0.01))
    return body


def _label(part: cq.Workplane, k: Key) -> cq.Workplane:
    return (part.faces(">X").workplane(centerOption="CenterOfBoundBox")
            .center(0, -2.0).text(k.label, 5.0, -LABEL_DEPTH, combine="cut", font=FONT))


def old_key(k: Key = Key()) -> cq.Workplane:
    """LADDER-02 key-P-2 with its D neck, for checking the rebuild against the print."""
    k = replace(k, full_catch=False)
    neck = (cq.Workplane("XY").circle(NECK_D / 2).extrude(LID_T + TRAVEL + SOCKET_D)
            .intersect(_box(-NECK_D, NECK_FLAT, -NECK_D, NECK_D, 0, LID_T + TRAVEL + SOCKET_D)))
    neck = neck.faces(">Z").edges().chamfer(0.4).translate((0, 0, BODY_H))
    return _label(_body(k).union(neck), k)


def key(k: Key = Key(), flip: bool = False) -> cq.Workplane:
    body = _body(k, flip)
    ext = _box(-k.ext_x / 2, k.ext_x / 2, -k.ext_y / 2, k.ext_y / 2, BODY_H - 0.01, k.cap_z0 + 0.01)
    cap = (cq.Workplane("XY").box(CAP_X, CAP_Y, CAP_T, centered=(True, True, False))
           .edges("|Z").fillet(CAP_R).faces(">Z").edges().fillet(0.8)
           .translate((0, 0, k.cap_z0)))
    cap = cap.cut(_icon(k))
    # label the stem's own +X face first, as LADDER did; the cap is wider now
    return _label(body, k).union(ext).union(cap)


# The keys built so far. Play and Record wait on Michael's call on the gate.
KEYS = {
    "stop": Key(label="S", role="stop", icon="stop"),
    "rew": Key(label="W", icon="rew"),
    "ff": Key(label="F", icon="ff"),
}
PLATE_PITCH = 22.0           # key spacing on the bed, mm


def plate(names=tuple(KEYS)) -> cq.Workplane:
    out = None
    for i, n in enumerate(names):
        part = key(KEYS[n]).translate((0, i * PLATE_PITCH, 0))
        out = part if out is None else out.union(part)
    return out


def build(out: Path = OUT) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for n, k in KEYS.items():
        p = out / f"ctrl01-key-{n}.stl"
        cq.exporters.export(key(k), str(p), tolerance=0.01, angularTolerance=0.1)
        written.append(p)
    p = out / "ctrl01-plate-keys.stl"
    cq.exporters.export(plate(), str(p), tolerance=0.01, angularTolerance=0.1)
    return written + [p]


if __name__ == "__main__":
    for p in build():
        print(p)
