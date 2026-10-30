"""CTRL-01 build: every printed part in its print pose, three plates, and STLs.

    python3 hardware/prototypes/ctrl-01/build.py      writes print/ctrl01-*.stl

Plates (A1 Mini, 180 x 180):
    shell  front and back halves together, so they are a matched pair; outer faces down
    mech   the five keys upright, a spare FF, the slide lock (back face down), the blocker,
           the key comb (spine down)
    cards  the new front half, the five card variants (flat) and a spare slide lock
    rebuild  the new back half, the key comb and the glue-in blocker guide (30 Oct)
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
        _PARTS = {"front": front, "back": back, "comb": S.comb(), "bar": M.bar(), "blocker": M.blocker(),
                  "guide-retrofit": S.guide_retrofit()}
        for n in L.KEYS:
            _PARTS[f"key-{n}"] = M.key_local(n)
        for v in C.CARDS:
            _PARTS[f"card-{v}"] = C.card(v)
    return _PARTS


def print_poses() -> dict[str, cq.Workplane]:
    p = parts()
    out = {
        "front": p["front"],                                                   # outer face (Z 0) down
        "back": p["back"].rotate((0, 0, 0), (0, 1, 0), 180),                   # outer face (Z 29) down
        "bar": p["bar"].rotate((0, 0, 0), (1, 0, 0), 180),                     # back face down, pawls up
        "blocker": p["blocker"],                                               # flat
        "comb": p["comb"].rotate((0, 0, 0), (0, 1, 0), 90),                    # spine down, fins up
        "guide-retrofit": p["guide-retrofit"],                                 # front-wall face down
    }
    for n in L.KEYS:
        out[f"key-{n}"] = p[f"key-{n}"]                                        # upright
    for v in C.CARDS:
        out[f"card-{v}"] = p[f"card-{v}"]
    return {k: _to_bed(v, 0, 0) for k, v in out.items()}


def plates() -> dict[str, cq.Workplane]:
    pp = print_poses()
    shell = _to_bed(pp["front"], 5, 5).union(_to_bed(pp["back"], 85, 5))
    mech = None
    for i, n in enumerate(L.KEYS + ("ff",)):
        k = _to_bed(pp[f"key-{n}"], 8 + (i % 3) * 30, 8 + (i // 3) * 30)
        mech = k if mech is None else mech.union(k)
    mech = mech.union(_to_bed(pp["bar"], 100, 8)).union(_to_bed(pp["blocker"], 120, 8))
    mech = mech.union(_to_bed(pp["comb"], 145, 8))
    # the card plate also carries a spare slide lock (Michael, 28 Oct: the mech plate was
    # already printing with flat-topped latches) and the new front half (30 Oct: so the
    # blocker guide comes built in rather than glued)
    cards = _to_bed(pp["front"], 5, 5)
    for i, v in enumerate(C.CARDS):
        cards = cards.union(_to_bed(pp[f"card-{v}"], 80 + (i % 2) * 45, 5 + (i // 2) * 41))
    cards = cards.union(_to_bed(pp["bar"], 170, 5))
    # 30 Oct rebuild: the new back half and the comb; the glue-in guide lets a front half
    # printed before 30 Oct be kept
    rebuild = (_to_bed(pp["back"], 5, 5).union(_to_bed(pp["comb"], 85, 5))
               .union(_to_bed(pp["guide-retrofit"], 115, 5)))
    return {"shell": shell, "mech": mech, "cards": cards, "rebuild": rebuild}


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
