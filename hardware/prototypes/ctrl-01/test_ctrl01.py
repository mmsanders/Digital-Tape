"""Gates for the CTRL-01 key. Each gate has a negative control that must go red.

    python3 -m pytest hardware/prototypes/ctrl-01/test_ctrl01.py
"""

from __future__ import annotations

import math
from dataclasses import replace

import cadquery as cq
import pytest

from ctrl01 import Key, _catch_profile, key, print_pose

MAX_OVERHANG_DEG = 45.0      # from vertical; the A1 Mini prints 45 cleanly
BED_Z = 0.5                  # faces this low are the bed or its edge chamfer


def _posed(k: Key) -> cq.Shape:
    return print_pose(key(k), k).val()


def overhangs(shape: cq.Shape, max_deg: float = MAX_OVERHANG_DEG) -> list[tuple[float, float]]:
    """Downward faces steeper than max_deg from vertical, above the bed.

    Returns (face centre z, angle from vertical) for each offender.
    """
    limit = -math.sin(math.radians(max_deg)) - 1e-3
    bad = []
    for f in shape.Faces():
        if f.BoundingBox().zmax < BED_Z:
            continue
        # sample the normal across the face so curved faces are covered too
        samples = [f.normalAt(f.positionAt(u, v)) for u in (0.1, 0.5, 0.9) for v in (0.1, 0.5, 0.9)]
        worst = min(n.z for n in samples)
        if worst < limit:
            bad.append((round(f.Center().z, 2), round(math.degrees(math.asin(min(1.0, -worst))), 1)))
    return bad


def ledge_faces_cap(shape: cq.Shape, k: Key) -> bool:
    """True when a flat face in the hook lane faces the cap (up, when posed).

    That face is what holds a key down under the slide-lock latch. The WP-04
    root-cause failure was this face pointing the wrong way.
    """
    for f in shape.Faces():
        if f.geomType() != "PLANE":
            continue
        n = f.normalAt()
        bb = f.BoundingBox()
        # posed: key y is unchanged; the face must reach out into the hook lane
        if n.z > 0.99 and bb.ymax > k.body_y1 + k.hook - 0.05 and bb.zmax < k.length - 0.5:
            return True
    return False


def lane_clear_inward(shape: cq.Shape, k: Key) -> bool:
    """Nothing in the hook lane inward of the ramp.

    Material there would meet the slide lock before the ramp does, so a light
    touch on any key could shift the lock and pop Play.
    """
    ramp_end_x = k.ledge_x + k.tip_x + k.hook / math.tan(math.radians(k.ramp_deg))
    probe_top = k.length - ramp_end_x - 0.05          # posed z of the ramp's lower end
    probe = cq.Workplane().box(k.cap_z + k.reach_z + 2, k.hook - 0.1, probe_top,
                               centered=False).translate((-1, k.body_y1 + 0.05, 0.0)).val()
    return shape.intersect(probe).Volume() < 1e-3


# --- the shipped key -----------------------------------------------------------

def test_one_valid_solid():
    s = _posed(Key())
    assert s.isValid()
    assert len(s.Solids()) == 1


def test_prints_without_support():
    assert overhangs(_posed(Key())) == []


def test_ledge_faces_the_cap():
    assert ledge_faces_cap(_posed(Key()), Key())


def test_lane_inward_of_ramp_is_empty():
    assert lane_clear_inward(_posed(Key()), Key())


def test_business_end_is_P():
    k = Key()
    prof = _catch_profile(k)
    ledge = [p for p in prof if math.isclose(p[0], k.ledge_x)]
    assert max(p[1] for p in ledge) - k.body_y1 == pytest.approx(1.2)
    assert k.ramp_deg == 45.0


# --- negative controls: each gate must go red ----------------------------------

def test_overhang_gate_catches_a_flat_ramp():
    assert overhangs(_posed(replace(Key(), ramp_deg=80.0))) != []


def test_ledge_gate_catches_a_reversed_catch():
    k = Key()
    s = _posed(k).mirror("XY", (0, 0, k.length / 2))   # flips press direction
    assert not ledge_faces_cap(s, k)


def test_lane_gate_catches_a_filled_lane():
    k = Key()
    s = _posed(k)
    filler = cq.Workplane().box(3, k.hook - 0.2, 1.0, centered=False) \
        .translate((k.cap_z, k.body_y1, 0.0)).val()
    assert not lane_clear_inward(s.fuse(filler), k)
