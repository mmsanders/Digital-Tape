"""Gates for the CTRL-01 rig (shrunk keys, slide lock, Record latch, shell, cards).
Each gate has a negative control that must go red.

    cd hardware/prototypes/ctrl-01 && python3 -m pytest -q test_rig.py
"""

from __future__ import annotations

import math
from functools import lru_cache

import cadquery as cq
import pytest
from shapely.geometry import Polygon

import assembly as A
import build as BLD
import cards as C
import layout as L
import mech as M
import shell as S


# --- latch behaviour (2D, the key against the pawl) ------------------------------

@lru_cache(None)
def kin(name: str):
    return M.kinematics(name)


@pytest.mark.parametrize("name", ["play", "ff", "rew"])
def test_latch_keys_latch_on_the_ledge_with_overtravel(name):
    k = kin(name)
    assert k.latched_at is not None and k.hold_is_ledge
    assert L.TRAVEL - k.latched_at >= 0.8


def test_stop_never_latches_and_frees_every_catch_in_time():
    k = kin("stop")
    assert k.latched_at is None
    assert k.shift_at[L.STOP_FULL_AT] >= L.STOP_SHIFT - 0.01     # bisection resolution
    assert L.STOP_SHIFT >= L.HOOK + 0.5


@pytest.mark.parametrize("name", L.KEYS)
def test_pawls_never_reach_the_next_key(name):
    assert M.neighbour_clear(name)


def test_latch_gate_catches_a_reversed_catch():
    flipped = [(y, L.BODY_H - z) for y, z in M.catch_profile("ff")]
    tooth, pawl = Polygon(flipped), Polygon(M.pawl_profile())
    full = M.bar_shift(tooth, pawl, L.TRAVEL)
    held = full < 0.01 and not M._free(tooth, pawl, 0.0, L.TRAVEL - 0.5)
    assert not held


def test_stop_gate_catches_a_stop_with_a_ledge():
    assert M.kinematics("ff").latched_at is not None     # a ledge latches; Stop's must not


def test_neighbour_gate_catches_too_much_bar_travel():
    assert not M.neighbour_clear("play", s_max=6.0)


# --- assembly: nothing occupies the same space twice -----------------------------

def _sweep_states():
    out = dict(A.pressed_states())
    for n in L.KEYS:
        if n == "rec":
            continue                       # Record's states are in A.record_states()
        k = kin(n)
        for d in (1.0, 2.0, 3.0, 4.0):
            out[f"{n}@{d}"] = dict(pressed={n: d}, bar_shift=k.shift_at[d])
    return out


@pytest.mark.parametrize("name,st", list(_sweep_states().items()))
def test_no_clashes(name, st):
    assert A.clashes(A.state(**st)) == []


def test_clash_gate_catches_a_key_off_its_slot():
    parts = A.state()
    parts["ff"] = parts["ff"].translate(cq.Vector(0, 0.4, 0))
    assert any("ff" in (a, b) for a, b, _ in A.clashes(parts))


# --- the Record latch (31 Oct): Record latches to Play, never to the slide lock -----

@lru_cache(None)
def rlatch():
    return M.record_latch()


def test_play_hold_is_the_depth_the_latch_is_built_for():
    assert kin("play").latched_at == pytest.approx(L.PLAY_HOLD, abs=0.05)


def test_record_alone_meets_nothing_and_springs_back():
    assert rlatch().alone_clear


def test_play_brings_the_hook_past_record_without_touching_it():
    assert rlatch().play_press_clear


def test_record_latches_to_play_on_a_ledge():
    r = rlatch()
    assert r.held_at is not None and r.hold_is_ledge
    assert L.TRAVEL - r.held_at >= 0.5                          # overtravel to snap past
    assert r.max_push <= L.TRAVEL - L.PLAY_HOLD - 0.2           # Play has room to be nudged
    assert r.push_slope <= 1.5                                  # Record ramps the hook aside


def test_play_rising_frees_record_in_time():
    assert rlatch().released_below is not None and rlatch().released_below >= 0.6


def test_record_never_touches_the_slide_lock():
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    for st in A.record_states().values():
        parts = A.state(**st)
        d = BRepExtrema_DistShapeShape(parts["rec"].wrapped, parts["bar"].wrapped)
        d.Perform()
        assert d.Value() >= 0.5


def test_latch_gate_catches_a_toe_without_its_chamfer(monkeypatch):
    monkeypatch.setattr(L, "TOE_CH", 0.0)
    assert M.record_latch().push_slope > 1.5          # flat on flat: the toe would just stall


def test_alone_gate_catches_a_hook_left_in_records_lane(monkeypatch):
    monkeypatch.setattr(L, "HOOK_OVERLAP", -3.0)
    assert not M.record_latch().alone_clear


def test_release_gate_catches_a_hook_too_wide_to_clear(monkeypatch):
    monkeypatch.setattr(L, "HOOK_W", 4.0)
    r = M.record_latch()
    assert r.released_below is None or r.released_below < 0.6


# --- parts and plates ---------------------------------------------------------------

def test_every_printed_part_is_one_valid_solid():
    for name, part in BLD.parts().items():
        v = part.val()
        assert v.isValid() and len(v.Solids()) == 1, name


def overhangs(shape: cq.Shape, allowed_z=(), max_deg=45.0):
    limit = -math.sin(math.radians(max_deg)) - 1e-3
    bad = []
    for f in shape.Faces():
        bb = f.BoundingBox()
        if bb.zmax < 0.3:
            continue
        worst = min(f.normalAt(f.positionAt(u, v)).z for u in (0.1, 0.5, 0.9) for v in (0.1, 0.5, 0.9))
        if worst < limit and not any(abs(bb.zmin - z) < 0.05 and bb.zlen < 0.05 for z in allowed_z):
            bad.append((round(bb.zmin, 2), round(bb.xmin, 1), round(bb.ymin, 1)))
    return bad


KEY_ALLOWED = (L.GROOVE_D, L.CAP_Z0)     # spring-groove roof (1 mm bridge) and the cap underside (support)


@pytest.mark.parametrize("name", L.KEYS)
def test_keys_print_upright_with_support_only_under_the_cap(name):
    assert overhangs(M.key_local(name).val(), KEY_ALLOWED) == []


def test_bar_blocker_comb_and_cards_print_without_support():
    poses = BLD.print_poses()
    for name in ["bar", "latch", "comb", "guide-retrofit", "card-portrait", "card-snap-back"] + [f"card-{v}" for v in C.CARDS]:
        assert overhangs(poses[name].val()) == [], name
    # the snap card's face half prints face up: only its groove (1.2 wide) and the bead
    # relief above it are roofed, both bridged across less than 1.5 mm
    k = C.SNAP
    roofs = (k["groove_d"] - 0.01, k["bead_z"] + k["bead"] * 1.6 + 0.1)
    assert overhangs(poses["card-snap-face"].val(), roofs) == []


def test_overhang_gate_catches_a_reversed_catch():
    assert overhangs(M.key_local("ff", flip=True).val(), KEY_ALLOWED) != []


def test_plates_fit_the_a1_mini_bed():
    for name, plate in BLD.plates().items():
        bb = plate.val().BoundingBox()
        assert bb.xmin >= 0 and bb.ymin >= 0 and abs(bb.zmin) < 1e-3, name
        assert bb.xmax <= 180 and bb.ymax <= 180, name


# --- cards in slots ------------------------------------------------------------------

def seated(card_name: str, s: C.Slot) -> cq.Shape:
    """A card seated in a slot, PROUD out of its face, in the device frame."""
    c = C.card(card_name)
    x0, x1, y0, y1 = C.footprint(s)
    z0, z1 = s.z
    zc = z0 + s.clr
    if s.loc in ("top", "bottom"):
        yc = (-L.PROUD + C.B / 2) if s.loc == "top" else (L.H + L.PROUD - C.B / 2)
        return c.translate((C.XC, yc, zc)).val()
    # the card already lies 40 along X, 36 along Y: right for every slot
    xc = L.W + L.PROUD - C.A / 2
    return c.translate((xc, C.YC, zc)).val()


def _half(s: C.Slot) -> cq.Shape:
    f, b = A.halves()
    return (f if s.layer == "front" else b).val()


@pytest.mark.parametrize("s", [s for s in C.SLOTS if s.hold == "none"], ids=lambda s: s.name)
def test_plain_slots_take_every_card(s):
    for v in C.CARDS:
        assert seated(v, s).intersect(_half(s)).Volume() < 1e-3, v


@pytest.mark.parametrize("s", [s for s in C.SLOTS if s.hold == "ribs"], ids=lambda s: s.name)
def test_rib_slots_grip_every_card(s):
    for v in C.CARDS:
        assert seated(v, s).intersect(_half(s)).Volume() > 0.5, v


def _seated_portrait(card: cq.Workplane) -> cq.Shape:
    s = next(s for s in C.SLOTS if s.name == "RB")
    xc = L.W + L.PROUD + (C.P_LEN - C.A) - C.P_LEN / 2
    return card.translate((xc, C.YC, s.z[0] + s.clr - card.val().BoundingBox().zmin)).val()


def test_portrait_cards_grip_in_the_slot_michael_chose_and_touch_only_its_ribs():
    s = next(s for s in C.SLOTS if s.name == "RB")
    ribs_only = seated("A", s).intersect(_half(s)).Volume()
    face, back = C.snap_card()
    for name, c in (("solid", C.portrait_card()), ("snap", face.union(back))):
        v = _seated_portrait(c).intersect(_half(s)).Volume()
        assert 0.5 < v <= ribs_only + 0.2, name


def test_snap_card_halves_close_without_overlap_and_make_a_full_card():
    face, back = C.snap_card()
    assert face.val().intersect(back.val()).Volume() < 1e-3
    bb = face.union(back).val().BoundingBox()
    assert (bb.xlen, bb.ylen, bb.zlen) == pytest.approx((C.P_LEN, C.B, C.TH), abs=1e-3)


def test_snap_gate_catches_a_bead_bigger_than_its_relief(monkeypatch):
    face, _ = C.snap_card()                                  # relief cut for the 0.25 bead
    monkeypatch.setattr(C, "SNAP", dict(C.SNAP, bead=0.45))
    _, back = C.snap_card()                                  # tongue carrying a 0.45 bead
    assert face.val().intersect(back.val()).Volume() > 1e-3


def test_detent_holds_card_C_in_its_notch_and_only_C():
    s = next(s for s in C.SLOTS if s.hold == "detent")
    assert seated("C", s).intersect(_half(s)).Volume() < 1e-3
    assert seated("A", s).intersect(_half(s)).Volume() > 0.5      # control: no notch, the bump is in the way


def test_slot_clearances_are_as_specified():
    for s in C.SLOTS:
        x0, x1, y0, y1 = C.footprint(s)
        width = (x1 - x0) if s.loc in ("top", "bottom") else (y1 - y0)
        assert width - (C.A if s.loc in ("top", "bottom") else C.B) == pytest.approx(2 * s.clr)
        assert (s.z[1] - s.z[0]) - C.TH == pytest.approx(2 * s.clr)


# --- front-zone features are properly joined to their keys ---------------------------

MIN_JOINT = 20.0     # mm^2: the joint spans the key's whole front face


def test_record_finger_and_play_arm_are_joined_across_the_key_face():
    assert M.joint_area(M._toe_and_web()) >= MIN_JOINT
    assert M.joint_area(M._arm_and_rail()) >= MIN_JOINT


def test_joint_gate_catches_a_feature_hanging_on_a_sliver():
    # the 27 Oct defect: the arm touched the key only along a 0.01 mm strip
    x = -L.STEM_XP / 2
    sliver = M._box(x - 0.21, x + 0.3, -3.6, -3.49, 0, 3.5)
    assert M.joint_area(sliver) < MIN_JOINT


# --- the slide lock's latches have the Stop shape ------------------------------------

def _rises_toward_far_end(profile) -> float:
    """How much the latch's top rises from the end of its chamfer to its far end."""
    tops = [(y, z) for y, z in profile if z >= L.PAWL_TOP - 1e-6]
    near, far = min(tops), max(tops)
    return far[1] - near[1]


def test_every_latch_has_the_rising_stop_shape():
    assert _rises_toward_far_end(M.pawl_profile()) >= 1.5


def test_rise_gate_catches_the_flat_topped_stub():
    e, top = L.PAWL_EDGE, L.PAWL_TOP
    stub = [(e, top - L.PAWL_H), (e, top - L.PAWL_CH), (e + L.PAWL_CH, top), (e + L.PAWL_LEN, top),
            (e + L.PAWL_LEN, 0.0), (e + 1.5, 0.0), (e + 1.5, top - L.PAWL_H)]
    assert _rises_toward_far_end(stub) < 1.5


# --- every part has a way in, in build order ----------------------------------------

@lru_cache(None)
def _sequence():
    return A.assembly_sequence()


@pytest.mark.parametrize("i", range(9), ids=lambda i: f"step{i + 1}")
def test_every_part_has_a_clear_path_in(i):
    name, part, obstacles, direction, distance, allowed = _sequence()[i]
    assert A.path_hits(part, obstacles, direction, distance, allowed) == [], name


def test_sequence_covers_every_part():
    assert len(_sequence()) == 9      # five keys, lock, comb, blocker, front half


def test_path_gate_catches_the_30_oct_back_half():
    # the printed back half had the comb built in: the lock could not get under it
    st = A.state()
    old_back = st["back"].fuse(st["comb"])
    assert A.path_hits(st["bar"], [old_back], (0, 0, 1), 28.0, S.snap_lips().val()) != []
    # and a key could not drop into its closed rail tunnels
    assert A.path_hits(st["ff"], [old_back], (0, 0, 1), 28.0) != []


def test_glue_in_guide_clears_every_moving_part():
    # it replaces nothing on the new front half, so it must sit in free space in every state
    g = S.guide_retrofit().val()
    for name, st in _sweep_states().items():
        parts = A.state(**st)
        for k, v in parts.items():
            if k != "front":
                assert g.intersect(v).Volume() < 1e-3, (name, k)


def test_glue_in_guide_gate_catches_a_guide_set_into_the_latch():
    g = S.guide_retrofit().translate((0.5, 0, 0)).val()        # 0.5 mm too far in
    assert g.intersect(A.state()["latch"]).Volume() > 1e-3
