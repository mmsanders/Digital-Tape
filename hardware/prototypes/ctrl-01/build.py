"""CTRL-01 build: every printed part in its print pose, two plates, and STLs.

    python3 hardware/prototypes/ctrl-01/build.py      writes print/ctrl01-*.stl

Plates (A1 Mini, 180 x 180), 1 Nov Play/Record rig:
    shell  front and back halves together, so they are a matched pair; outer faces down
    mech   Record, Play and Stop upright (support under the blocks), a spare Play, the
           slide lock (back face down), the latch slider (floor down), the comb (spine down)
"""

from __future__ import annotations

from pathlib import Path

import cadquery as cq

import cards as C
import layout as L
import mech as M
import shell as S

OUT = Path(__file__).resolve().parent / "print"


def _to_bed(part: cq.Workplane, x: float, y: float) -> cq.Workplane:
    """Move a part so its bounding box starts at (x, y, 0)."""
    bb = part.val().BoundingBox()
    return part.translate((x - bb.xmin, y - bb.ymin, -bb.zmin))


_PARTS = None


def parts() -> dict[str, cq.Workplane]:
    """Every printed part in the device frame (keys in their own frame)."""
    global _PARTS
    if _PARTS is None:
        front, back = S.halves()
        _PARTS = {"front": front, "back": back, "comb": S.comb(), "bar": M.bar(), "latch": M.latch()}
        for n in L.KEYS:
            _PARTS[f"key-{n}"] = M.key_local(n)
        _PARTS["card-portrait"] = C.portrait_card()
        face, back = C.snap_card()
        _PARTS["card-snap-face"], _PARTS["card-snap-back"] = face, back
    return _PARTS


def print_poses() -> dict[str, cq.Workplane]:
    p = parts()
    out = {
        "front": p["front"],                                                   # outer face (Z 0) down
        "back": p["back"].rotate((0, 0, 0), (0, 1, 0), 180),                   # outer face (Z 29) down
        "bar": p["bar"].rotate((0, 0, 0), (1, 0, 0), 180),                     # back face down, pawls up
        "latch": p["latch"],                                                   # floor down
        "card-portrait": p["card-portrait"],                                   # face up
        "card-snap-face": p["card-snap-face"],                                 # face up, groove down
        "card-snap-back": p["card-snap-back"],                                 # outer face down
        "comb": p["comb"].rotate((0, 0, 0), (0, 1, 0), 90),                    # spine down, fins up
    }
    for n in L.KEYS:
        out[f"key-{n}"] = p[f"key-{n}"]                                        # upright
    return {k: _to_bed(v, 0, 0) for k, v in out.items()}


def plates() -> dict[str, cq.Workplane]:
    pp = print_poses()
    shell = _to_bed(pp["front"], 5, 5).union(_to_bed(pp["back"], 85, 5))
    mech = None
    for i, n in enumerate(L.KEYS + ("play",)):
        k = _to_bed(pp[f"key-{n}"], 8 + (i % 2) * 24, 8 + (i // 2) * 24)
        mech = k if mech is None else mech.union(k)
    mech = (mech.union(_to_bed(pp["bar"], 60, 8)).union(_to_bed(pp["latch"], 72, 8))
            .union(_to_bed(pp["comb"], 92, 8)))
    return {"shell": shell, "mech": mech}


def build(out: Path = OUT) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for name, part in print_poses().items():
        p = out / f"ctrl01-{name}.stl"
        cq.exporters.export(part, str(p), tolerance=0.02, angularTolerance=0.2)
        written.append(p)
    for name, plate in plates().items():
        p = out / f"ctrl01-plate-{name}.stl"
        cq.exporters.export(plate, str(p), tolerance=0.02, angularTolerance=0.2)
        written.append(p)
    return written


if __name__ == "__main__":
    for p in build():
        print(p)
