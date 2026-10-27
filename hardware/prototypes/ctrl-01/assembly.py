"""CTRL-01 assembly: every part in place, at rest and in each pressed state, and
the interference check that says nothing occupies the same space twice."""

from __future__ import annotations

from itertools import combinations

import cadquery as cq

import layout as L
import mech as M
import shell as S

_HALVES = None


def halves():
    global _HALVES
    if _HALVES is None:
        _HALVES = S.halves()
    return _HALVES


def state(pressed: dict[str, float] | None = None, bar_shift: float = 0.0,
          play_depth: float | None = None) -> dict[str, cq.Shape]:
    """All parts placed. `pressed` maps key name to press depth."""
    pressed = pressed or {}
    front, back = halves()
    parts = {"front": front.val(), "back": back.val(),
             "bar": M.bar(bar_shift).val()}
    for n in L.KEYS:
        parts[n] = M.key(n, pressed.get(n, 0.0)).val()
    pd = pressed.get("play", 0.0) if play_depth is None else play_depth
    parts["blocker"] = M.blocker(pd).val()
    return parts


def clashes(parts: dict[str, cq.Shape], tol: float = 1e-3) -> list[tuple[str, str, float]]:
    out = []
    boxes = {k: v.BoundingBox() for k, v in parts.items()}
    for a, b in combinations(parts, 2):
        ba, bb = boxes[a], boxes[b]
        if (ba.xmax < bb.xmin or bb.xmax < ba.xmin or ba.ymax < bb.ymin or bb.ymax < ba.ymin
                or ba.zmax < bb.zmin or bb.zmax < ba.zmin):
            continue
        v = parts[a].intersect(parts[b]).Volume()
        if v > tol:
            out.append((a, b, round(v, 4)))
    return out


def pressed_states() -> dict[str, dict]:
    """The states the rig must pass through without anything clashing.

    Each latch key fully down with the bar at rest (it has snapped back over the
    ledge); Stop fully down with the bar at its full shift; Record with Play down
    (the blocker has moved away); and the deepest bar shift any key reaches on
    the way down, at that depth.
    """
    out = {"rest": dict()}
    for n in L.KEYS:
        kin = M.kinematics(n)
        d_peak = max(kin.shift_at, key=lambda d: kin.shift_at[d])
        # Record can only go deep with Play already down
        extra = {"play": L.TRAVEL} if n == "rec" else {}
        out[f"{n}-full"] = dict(pressed={n: L.TRAVEL, **extra}, bar_shift=kin.shift_at[L.TRAVEL])
        out[f"{n}-peak"] = dict(pressed={n: d_peak, **extra}, bar_shift=kin.shift_at[d_peak])
    out["play+rec"] = dict(pressed={"play": L.TRAVEL, "rec": L.TRAVEL}, bar_shift=0.0)
    out["rec-blocked"] = dict(pressed={"rec": L.BLOCK_STOP - 0.02}, bar_shift=0.0)
    return out
