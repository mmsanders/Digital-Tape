"""CTRL-01 assembly: every part in place, at rest and in each pressed state, and
the interference check that says nothing occupies the same space twice."""

from __future__ import annotations

from itertools import combinations

import cadquery as cq

import layout as L
import mech as M
import shell as S

_HALVES = None
_COMB = None


def halves():
    global _HALVES
    if _HALVES is None:
        _HALVES = S.halves()
    return _HALVES


def comb():
    global _COMB
    if _COMB is None:
        _COMB = S.comb()
    return _COMB


def state(pressed: dict[str, float] | None = None, bar_shift: float = 0.0,
          play_depth: float | None = None) -> dict[str, cq.Shape]:
    """All parts placed. `pressed` maps key name to press depth."""
    pressed = pressed or {}
    front, back = halves()
    parts = {"front": front.val(), "back": back.val(), "comb": comb().val(),
             "bar": M.bar(bar_shift).val()}
    for n in L.KEYS:
        parts[n] = M.key(n, pressed.get(n, 0.0)).val()
    pd = pressed.get("play", 0.0) if play_depth is None else play_depth
    parts["latch"] = M.latch(pd).val()
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
    ledge); Stop fully down with the bar at its full shift; the deepest bar shift
    any latch key reaches on the way down, at that depth; and Record through its
    whole story with Play (record_states).
    """
    out = {"rest": dict()}
    for n in L.KEYS:
        if n == "rec":
            continue
        kin = M.kinematics(n)
        d_peak = max(kin.shift_at, key=lambda d: kin.shift_at[d])
        out[f"{n}-full"] = dict(pressed={n: L.TRAVEL}, bar_shift=kin.shift_at[L.TRAVEL])
        out[f"{n}-peak"] = dict(pressed={n: d_peak}, bar_shift=kin.shift_at[d_peak])
    out.update(record_states())
    return out


def record_states() -> dict[str, dict]:
    """Record alone; Record pushing past the hook with Play latched (Play nudged as
    the 2D latch says); Record held; and Stop releasing both."""
    rl = M.record_latch()
    out = {}
    for d in (1.0, 2.5, 4.0, L.TRAVEL):
        out[f"rec-alone@{d}"] = dict(pressed={"rec": d})
    _, raised = M.slider_outlines()
    toe = M.toe_outline()
    from shapely.affinity import translate as tr
    for r in (1.0, 2.0, 3.0, 4.0, L.TRAVEL):
        s = L.PLAY_HOLD
        while tr(toe, r, 0).intersection(tr(raised, 0, s)).area > 1e-5:
            s += 0.02
        out[f"rec-push@{r}"] = dict(pressed={"play": s, "rec": r})
    out["rec-held"] = dict(pressed={"play": L.PLAY_HOLD, "rec": rl.held_at})
    stop = M.kinematics("stop")
    for s in (L.PLAY_HOLD - 0.4, L.PLAY_HOLD - 1.2, rl.released_below):
        out[f"stop-release@{s}"] = dict(pressed={"play": s, "rec": rl.held_at, "stop": L.STOP_FULL_AT},
                                        bar_shift=stop.shift_at[L.STOP_FULL_AT])
    return out


# --- assembly: every part has a way in -------------------------------------------

STEP = 0.5      # every part and obstacle is at least 1 mm thick along its path


def path_hits(part: cq.Shape, obstacles: list[cq.Shape], direction: tuple[float, float, float],
              distance: float, allowed: cq.Shape | None = None) -> list[tuple[float, float]]:
    """Slide `part` into its final place along `direction`, starting `distance` back,
    and report (offset, volume) wherever it overlaps an obstacle. `allowed` is
    material the part is meant to snap past (the slide lock's lips)."""
    if allowed is not None:
        obstacles = [ob.cut(allowed) for ob in obstacles]
    hits = []
    n = int(distance / STEP) + 1
    for i in range(n, 0, -1):
        d = i * STEP
        p = part.translate(cq.Vector(*(-c * d for c in direction)))
        for ob in obstacles:
            v = p.intersect(ob).Volume()
            if v > 1e-3:
                hits.append((d, round(v, 3)))
                break
    return hits


def assembly_sequence() -> list[tuple[str, cq.Shape, list[cq.Shape], tuple, float, cq.Shape | None]]:
    """The build, in order: (step, moving part, what is already there, direction, distance, allowed).

    1. Keys slide into the comb from its outer end, on the bench.
    2. The slide lock snaps into the back half's channel.
    3. The comb, keys in it, drops into the back half over the lock.
    4. The latch slider drops onto Play's rail.
    5. The front half closes over everything.
    """
    st = state()
    front, back = st["front"], st["back"]
    keys = [st[n] for n in L.KEYS]
    module = st["comb"]
    for k in keys:
        module = module.fuse(k)
    seq = []
    for n in L.KEYS:
        seq.append((f"key {n} into comb", st[n], [st["comb"]], (1, 0, 0), 15.0, None))
    seq.append(("slide lock into back half", st["bar"], [back], (0, 0, 1), 28.0, S.snap_lips().val()))
    seq.append(("comb with keys into back half", module, [back, st["bar"]], (0, 0, 1), 28.0, None))
    seq.append(("latch slider onto Play's rail", st["latch"], [back, st["bar"], module], (0, 0, 1), 28.0, None))
    seq.append(("front half", front, [st["bar"], module, st["latch"]], (0, 0, 1), 28.0, None))
    return seq
