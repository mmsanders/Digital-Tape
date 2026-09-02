#!/usr/bin/env python3
"""Build print-run packet WP04-01: one plate, one card, one results template.

The packet is the deliverable, not the model (Hardware Charter §03). Michael
should arrive at the library with a file, put it on the machine, and leave with
an answer -- no arranging, no orientation choice, no support decision.

    make -C hardware packet-wp04

Outputs into hardware/packets/wp04-01/:
    plate.3mf        every part positioned on one bed -- this is the file to print
    plate.stl        same, for a slicer that will not take 3MF
    stl/<part>.stl   individual parts, if something needs reprinting alone
    manifest.json    the blind mapping. NOT for the card -- see below
    plate-map.md     which letter sits where on the bed

The letter on each button is deliberately unrelated to its hook depth, and the
mapping lives here rather than on the card, so the ranking is blind. Michael can
read this file; the point is that he will not, and that nothing he is handed
tells him which button is supposed to win.
"""

from __future__ import annotations

import json
import random
import sys
from datetime import date
from pathlib import Path

import cadquery as cq
from cadquery import exporters

sys.path.insert(0, str(Path(__file__).resolve().parent))
import latch  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "packets" / "wp04-01"

# Library-machine assumptions. Q-006 replaces these with facts; until then they
# are the safe defaults promised to Michael in FOR-MICHAEL.md.
BED_X, BED_Y = 220.0, 220.0
MARGIN = 12.0
PITCH_X, PITCH_Y = 26.0, 30.0
SEED = 20260902          # fixed, so the plate is reproducible from source


def placed(seed: int = SEED):
    """Assign variants to bed positions. Bed-controls are forced to opposite
    corners of the populated area -- that is the entire point of them."""
    variants = latch.packet_01_variants()
    probe = latch.orientation_probe()

    controls = [v for v in variants if v.role == "bed-control"]
    others = [v for v in variants if v.role != "bed-control"]
    rng = random.Random(seed)
    rng.shuffle(others)

    cols = 3
    slots = [(MARGIN + c * PITCH_X, MARGIN + r * PITCH_Y)
             for r in range(3) for c in range(cols)]

    # Controls to the far corners of the 3x3 grid, the rest shuffled between.
    order: list = [None] * len(slots)
    order[0] = controls[0]
    order[len(slots) - 1] = controls[1]
    it = iter(others)
    for i, cell in enumerate(order):
        if cell is None:
            order[i] = next(it, None)

    out = []
    for (x, y), v in zip(slots, order):
        if v is not None:
            out.append((v, x, y))
    return out, probe


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "stl").mkdir(exist_ok=True)

    layout, probe = placed()
    solids = []
    rows = []

    for v, x, y in layout:
        part = latch.carrier(v)
        exporters.export(part, str(OUT / "stl" / f"carrier-{v.label}.stl"))
        solids.append(part.val().moved(cq.Location(cq.Vector(x, y, 0))))
        rows.append({"label": v.label, "x": x, "y": y, **v.dict()})

    # Orientation probe: rotated onto its side, so the barb root crosses layers.
    pr = latch.carrier(probe).rotate((0, 0, 0), (1, 0, 0), 90)
    bb = pr.val().BoundingBox()
    pr = pr.translate((0, 0, -bb.zmin))
    exporters.export(pr, str(OUT / "stl" / f"carrier-{probe.label}-onside.stl"))
    px, py = MARGIN + 3 * PITCH_X, MARGIN
    solids.append(pr.val().moved(cq.Location(cq.Vector(px, py, 0))))
    rows.append({"label": probe.label, "x": px, "y": py, **probe.dict()})

    bar = latch.hook_bar()
    exporters.export(bar, str(OUT / "stl" / "hook-bar.stl"))
    solids.append(bar.val().moved(cq.Location(cq.Vector(BED_X / 2, BED_Y - 25.0, 0))))

    frame = latch.test_frame()
    exporters.export(frame, str(OUT / "stl" / "test-frame.stl"))
    solids.append(frame.val().moved(cq.Location(cq.Vector(BED_X - 45.0, 60.0, 0))))

    plate = cq.Compound.makeCompound(solids)
    exporters.export(plate, str(OUT / "plate.3mf"))
    exporters.export(plate, str(OUT / "plate.stl"))

    pbb = plate.BoundingBox()
    fits = pbb.xmax <= BED_X and pbb.ymax <= BED_Y
    manifest = {
        "packet": "WP04-01",
        "work_package": "WP-04",
        "built": date.today().isoformat(),
        "swept_parameter": "hook_depth (mm)",
        "bracket_mm": [0.6, 2.1],
        "seed": SEED,
        "blind": True,
        "bed_mm": [BED_X, BED_Y],
        "plate_extent_mm": [round(pbb.xmax, 1), round(pbb.ymax, 1)],
        "fits_bed": fits,
        "print_settings_assumed": {
            "material": "PLA",
            "layer_mm": 0.2,
            "nozzle_mm": 0.4,
            "perimeters": 3,
            "infill_pct": 40,
            "supports": "none required -- every overhang is <= 45 degrees by design",
            "note": "Assumed pending Q-006. Regenerate once the machine is known.",
        },
        "parts": rows,
        "common_parts": ["hook-bar", "test-frame"],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    lines = [
        "# Plate map — packet WP04-01",
        "",
        "Bed positions, front-left origin. The letter is **not** related to the hook",
        "depth: the mapping is in `manifest.json` and deliberately not on the card.",
        "",
        "| Letter | Bed X | Bed Y | Role |",
        "|---|---:|---:|---|",
    ]
    for r in rows:
        lines.append(f"| **{r['label']}** | {r['x']:.0f} | {r['y']:.0f} | {r['role']} |")
    lines += [
        "",
        f"Plate extent {pbb.xmax:.0f} × {pbb.ymax:.0f} mm on a "
        f"{BED_X:.0f} × {BED_Y:.0f} mm bed — **{'fits' if fits else 'DOES NOT FIT'}**.",
        "",
        "`D` and `H` are the same geometry as one of the lettered variants, placed at",
        "opposite ends of the populated area. If they do not rank together, bed position",
        "is affecting the parts more than the swept parameter is, and the next sweep needs",
        "coarser steps rather than finer ones.",
    ]
    (OUT / "plate-map.md").write_text("\n".join(lines) + "\n")

    print(f"packet WP04-01 -> {OUT}")
    print(f"  {len(rows)} carriers + hook bar + test frame")
    print(f"  plate extent {pbb.xmax:.1f} x {pbb.ymax:.1f} mm on "
          f"{BED_X:.0f} x {BED_Y:.0f} bed: {'FITS' if fits else 'DOES NOT FIT'}")
    if not fits:
        raise SystemExit("plate does not fit the assumed bed")
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
