"""Gates for the CTRL-01 key. Each gate has a negative control that must go red.

    cd hardware/prototypes/ctrl-01 && python3 -m pytest -q test_ctrl01.py
"""

from __future__ import annotations

import math
import struct
from dataclasses import replace
from pathlib import Path

import cadquery as cq
import pytest

from ctrl01 import BODY_H, Key, key, old_key

HERE = Path(__file__).resolve().parent
# Michael's LADDER-02 print file, from latch-rig.zip; SHA-256 a3e0dafd...a5ece0a
REFERENCE = HERE / "reference" / "ladder02-key-P-2.stl"
MAX_OVERHANG_DEG = 45.0       # from vertical
MIN_SHOULDER = 1.0            # mm the shoulder must reach past the aperture, per side


def stl_vertices(path: Path) -> set[tuple[float, float, float]]:
    raw = path.read_bytes()
    n = struct.unpack("<I", raw[80:84])[0]
    out = set()
    for i in range(n):
        f = struct.unpack("<12f", raw[84 + i * 50:84 + i * 50 + 48])
        for j in (3, 6, 9):
            out.add((round(f[j], 4), round(f[j + 1], 4), round(f[j + 2], 4)))
    return out


def worst_vertex_gap(shape: cq.Shape, path: Path) -> float:
    """Largest distance from a reference STL vertex to `shape`'s surface.

    The reference was exported with its bounding box moved to the origin; the
    shape is moved the same way before comparing.
    """
    bb = shape.BoundingBox()
    skin = cq.Compound.makeCompound(shape.Faces())
    worst = 0.0
    for x, y, z in stl_vertices(path):
        v = cq.Vertex.makeVertex(x + bb.xmin, y + bb.ymin, z + bb.zmin)
        worst = max(worst, skin.distance(v))
    return worst


def lower_part(shape: cq.Shape) -> cq.Shape:
    """Everything below the shoulder."""
    return shape.intersect(cq.Workplane().box(60, 60, BODY_H, centered=(True, True, False)).val())


def overhangs(shape: cq.Shape, allowed_z: tuple[float, ...]) -> list[tuple[float, float]]:
    """Downward faces steeper than 45 degrees, except at the heights in allowed_z.

    The allowed ones are declared, not hidden: the spring-groove roof (a 1.4 mm
    bridge that printed fine on LADDER-01/02) and the cap underside, which is
    flat on purpose and gets support.
    """
    from ctrl01 import LABEL_DEPTH, STEM_X
    limit = -math.sin(math.radians(MAX_OVERHANG_DEG)) - 1e-3
    bad = []
    for f in shape.Faces():
        bb = f.BoundingBox()
        if bb.zmax < 0.3:
            continue
        # the engraved letter on the stem's +X face (0.6 mm deep, as LADDER printed it)
        if bb.xmin >= STEM_X / 2 - LABEL_DEPTH - 0.01 and bb.xmax <= STEM_X / 2 + 0.01:
            continue
        worst = min(f.normalAt(f.positionAt(u, v)).z for u in (0.1, 0.5, 0.9) for v in (0.1, 0.5, 0.9))
        if worst < limit and not any(abs(bb.zmin - z) < 0.05 and bb.zlen < 0.05 for z in allowed_z):
            bad.append((round(bb.zmin, 2), round(math.degrees(math.asin(min(1.0, -worst))), 1)))
    return bad


def _allowed(k: Key) -> tuple[float, ...]:
    from ctrl01 import GROOVE_D
    return (GROOVE_D, k.cap_z0)


# --- the shipped key -----------------------------------------------------------

def test_one_valid_solid():
    s = key().val()
    assert s.isValid() and len(s.Solids()) == 1


def test_rebuild_matches_the_printed_ladder02_key():
    assert worst_vertex_gap(old_key().val(), REFERENCE) < 0.02


def test_body_below_the_shoulder_is_unchanged():
    new, old = lower_part(key().val()), lower_part(old_key().val())
    assert abs(new.Volume() - old.Volume()) < 0.01
    assert new.cut(old).Volume() < 0.01 and old.cut(new).Volume() < 0.01


def test_shoulder_reaches_past_the_aperture():
    assert Key().shoulder_overlap >= MIN_SHOULDER


def test_cap_underside_lands_on_the_shell_at_full_press():
    from ctrl01 import LID_T, TRAVEL
    s = key().val()
    flats = [f.BoundingBox().zmin for f in s.Faces()
             if f.geomType() == "PLANE" and f.normalAt().z < -0.99]
    cap_underside = max(flats)
    assert cap_underside - TRAVEL == pytest.approx(BODY_H + LID_T, abs=0.01)


def test_prints_upright_with_support_only_under_the_cap():
    assert overhangs(key().val(), _allowed(Key())) == []


# --- negative controls: each gate must go red ----------------------------------

def test_rebuild_gate_catches_a_different_ladder_key():
    assert worst_vertex_gap(old_key(replace(Key(), h=0.9)).val(), REFERENCE) > 0.2


def test_body_gate_catches_a_reversed_tooth():
    new, old = lower_part(key(flip=True).val()), lower_part(old_key().val())
    assert new.cut(old).Volume() > 1.0


def test_shoulder_gate_catches_a_thin_shoulder():
    assert replace(Key(), inset=0.8).shoulder_overlap < MIN_SHOULDER


def test_cap_gate_catches_a_cap_at_the_wrong_height():
    from ctrl01 import LID_T, TRAVEL
    s = key().val().translate(cq.Vector(0, 0, 0))
    moved = s.cut(cq.Workplane().box(40, 40, 1.0, centered=(True, True, False))
                  .translate((0, 0, Key().cap_z0)).val())
    flats = [f.BoundingBox().zmin for f in moved.Faces()
             if f.geomType() == "PLANE" and f.normalAt().z < -0.99]
    assert max(flats) - TRAVEL != pytest.approx(BODY_H + LID_T, abs=0.01)


def test_overhang_gate_catches_a_reversed_tooth():
    assert overhangs(key(flip=True).val(), _allowed(Key())) != []
