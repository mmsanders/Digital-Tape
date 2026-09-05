#!/usr/bin/env python3
"""Checks on the cartridge shell: the geometry must realise the analysis.

`spec/hw/cartridge-shell.md` makes three claims that are geometric, not textual,
and a document cannot hold itself to them:

  1. **The sweep is blind.** Every base is the same outside. A deeper bead has a
     taller lead-in ramp, and the first draft of `shell.py` let that push the
     wall up -- the bases came out 8.4, 8.4, 8.6, 8.8 mm tall, so the deepest
     variant was visibly the tallest and the blind ranking leaked its answer.
  2. **The bead seats free.** Closed, the two halves must not touch at the bead
     at all. That is the whole answer to "does PETG creep": if they touch, the
     opening strain becomes the resting strain and the design is wrong by 9x.
  3. **There is retention.** Withdrawn, they must interfere, and more so for a
     deeper bead -- otherwise claim 2 is satisfied by a joint that does nothing.

Claims 2 and 3 pull in opposite directions, which is why both are here.

The fourth check is the seam between this file and `hardware/mech/clasp.py`:
they share a span, a wall thickness, two ramp angles and a sweep, and if those
drift the spec describes a part nobody printed.

    python3 test_shell.py            run the checks
    python3 test_shell.py --mutate   prove they can go red
"""

from __future__ import annotations

import sys
from pathlib import Path

import cadquery as cq

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mech"))

import shell            # noqa: E402
import clasp            # noqa: E402

FAILED: list[str] = []


def check(ok: bool, what: str) -> None:
    if not ok:
        FAILED.append(what)
        print(f"  FAIL {what}")


def closed_lid():
    off = shell.H_BASE - shell.TONGUE_H
    return shell.lid().val().moved(cq.Location(cq.Vector(0, 0, off)))


def overlap(base_solid, lid_solid) -> float:
    got = base_solid.intersect(lid_solid)
    return got.Volume() if got else 0.0


def run() -> int:
    variants = shell.packet_variants()
    bases = {v.label: shell.base(v).val() for v in variants}

    # --- 1. the sweep is blind -------------------------------------------
    boxes = {k: (round(b.BoundingBox().xlen, 3), round(b.BoundingBox().ylen, 3),
                 round(b.BoundingBox().zlen, 3)) for k, b in bases.items()}
    check(len(set(boxes.values())) == 1,
          f"every base has the same outside (got {sorted(set(boxes.values()))})")
    check(all(abs(b[2] - shell.H_BASE) < 1e-6 for b in boxes.values()),
          "base height is H_BASE, so no bead pokes through the rim")

    # --- 2. the bead seats free ------------------------------------------
    lid = closed_lid()
    for v in variants:
        check(overlap(bases[v.label], lid) < 1e-6,
              f"{v.label}: closed assembly has zero interference (bead seats free)")

    # --- 3. and yet it retains -------------------------------------------
    off = shell.H_BASE - shell.TONGUE_H
    lifted = shell.lid().val().moved(cq.Location(cq.Vector(0, 0, off + 0.8)))
    vols = [(v.interference, overlap(bases[v.label], lifted)) for v in variants]
    check(all(x > 0 for _, x in vols), "withdrawing 0.8 mm engages every variant")
    check(all(a[1] < b[1] for a, b in zip(vols, vols[1:])),
          f"engagement grows with interference (got {[round(x, 2) for _, x in vols]})")

    # --- 4. geometry and analysis describe the same part -----------------
    check(shell.SPAN == clasp.SPAN, "span agrees with clasp.py")
    check(shell.WALL_RET == clasp.WALL_RET, "retention wall agrees with clasp.py")
    check(shell.WALL_NOM == clasp.WALL_NOM, "nominal wall agrees with clasp.py")
    check(shell.LEAD_DEG == clasp.CHAMFER_LEAD, "lead-in angle agrees with clasp.py")
    check(shell.RETAIN_DEG == clasp.CHAMFER_RETAIN, "retention angle agrees with clasp.py")
    check(shell.CORNER_RELIEF == clasp.CORNER_RELIEF, "corner relief agrees with clasp.py")
    check(tuple(shell.SWEEP_INTERFERENCE) == tuple(clasp.SWEEP), "sweep agrees with clasp.py")
    check((shell.L, shell.W) == (clasp.COUPON_L, clasp.COUPON_W),
          "coupon footprint agrees with clasp.py")
    check(abs(shell.engaged_run() - clasp.engaged_run(clasp.COUPON_L)) < 1e-9,
          "engaged run agrees with clasp.py")
    check(clasp.CHAMFER_RETAIN < clasp.self_lock_deg(),
          "the retention face is not self-locking")

    # --- 5. the cantilever is the one the strain was computed from -------
    # The bead must sit SPAN above the floor, on wall thinned all the way down
    # to the floor. Thinning only the rim would shorten the span and quadruple
    # the strain, and the part would still print and still assemble.
    check(abs(shell.BEAD_Z - (shell.FLOOR + shell.SPAN)) < 1e-9,
          "bead sits exactly SPAN above the floor")
    b = bases["G"]
    thin_at = []
    for z in (shell.FLOOR + 0.5, shell.BEAD_Z - 1.0):
        probe = (cq.Workplane("XY").box(2.0, shell.W, 0.2, centered=(True, True, False))
                 .translate((0, 0, z)).val())
        sliver = b.intersect(probe)
        thin_at.append(sliver.Volume() if sliver else 0.0)
    # 2 mm x 0.2 mm slice through two walls: 1.2 mm walls give 0.96 mm^3.
    check(all(abs(x - 2 * 2.0 * shell.WALL_RET * 0.2) < 0.02 for x in thin_at),
          f"wall is WALL_RET from the floor up to the bead (got {[round(x, 3) for x in thin_at]})")

    n = 22
    if FAILED:
        print(f"\n{len(FAILED)} of {n} checks FAILED")
        return 1
    print(f"all {n} checks pass")
    return 0


def mutate() -> int:
    """The most consequential silent failure: a groove too shallow for the bead.

    It prints, it assembles, it latches, it feels right -- and the wall is held
    deflected for the life of the cartridge, which is the one thing
    `cartridge-shell.md` argues does not happen. Nothing but a boolean catches it.
    """
    shell.GROOVE_DEPTH = 0.0
    rc = run()
    if rc == 0:
        print("MUTATION SURVIVED -- the checks cannot go red. That is the bug.")
        return 1
    print("\nOK  mutation caught: a bead that cannot seat is detected")
    return 0


if __name__ == "__main__":
    if "--mutate" in sys.argv:
        raise SystemExit(mutate())
    raise SystemExit(run())
