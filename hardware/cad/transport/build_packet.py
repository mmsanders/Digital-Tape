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
import re
import shutil
import sys
import zipfile
from datetime import date
from pathlib import Path

import cadquery as cq
from cadquery import exporters

sys.path.insert(0, str(Path(__file__).resolve().parent))
import latch  # noqa: E402

# Shasta Public Libraries, Original Prusa i3 MK3: 250 x 210 x 210 mm build volume,
# PLA only, .stl only, staff choose orientation, jobs over 6 h may be refused.
# We keep laying out for the small common bed -- it costs nothing and an A1 mini
# is 180 x 180 if Michael buys one.
PRINT_RATE_MM3_S = 11.0     # EST, MK3 at 0.2 mm with perimeters and travel
MAX_JOB_HOURS = 6.0         # library refusal threshold

OUT = Path(__file__).resolve().parents[2] / "packets" / "wp04-01"

# Library-machine assumptions. Q-006 replaces these with facts; until then they
# are the safe defaults promised to Michael in FOR-MICHAEL.md.
# A Prusa Mini and a Bambu A1 mini are both 180 x 180 and both common in library
# makerspaces. Assume the smaller machine until Q-006 says otherwise -- a plate that
# fits a small bed fits a big one, and the reverse costs a trip.
BED_X, BED_Y = 180.0, 180.0
MARGIN = 12.0
GAP = 4.0
SEED = 20260902          # fixed, so the plate is reproducible from source


# The plate is a committed artefact -- Michael downloads it, he cannot run `make`.
# So it has to be byte-identical on every rebuild, or it shows as modified forever
# and a real geometry change hides in the noise. Two sources of drift, neither of
# them the mesh:
#   * 3MF is a zip, and a zip stores each entry's mtime
#   * CadQuery stamps a <metadata name="CreationDate"> into the model XML
# Both are pinned below. The vertex data is already deterministic, so with these
# fixed a rebuild that changes anything has genuinely changed the geometry.
EPOCH = (2026, 9, 2, 0, 0, 0)
FIXED_CREATION_DATE = b"2026-09-02T00:00:00.000000"
_CREATION_DATE = re.compile(
    rb'(<metadata name="CreationDate">)(.*?)(</metadata>)', re.DOTALL)


def normalise_3mf(path: Path) -> None:
    """Rewrite a 3MF so that rebuilding it produces identical bytes."""
    tmp = path.with_suffix(".3mf.tmp")
    with zipfile.ZipFile(path) as src:
        entries = sorted(src.infolist(), key=lambda i: i.filename)
        payload = {i.filename: src.read(i.filename) for i in entries}

    for name, data in payload.items():
        if name.endswith(".model"):
            # A REPLACEMENT TEMPLATE IS NOT SAFE HERE. `rb"\1" + b"2026..."`
            # makes the template parser read \120 as an OCTAL escape (0o120 = 'P'),
            # which silently ate the opening <metadata> tag and left an orphaned
            # closing tag -- malformed XML that every slicer refuses. A function
            # replacement bypasses template parsing entirely.
            payload[name] = _CREATION_DATE.sub(
                lambda m: m.group(1) + FIXED_CREATION_DATE + m.group(3), data)

    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in entries:
            fixed = zipfile.ZipInfo(info.filename, date_time=EPOCH)
            fixed.compress_type = zipfile.ZIP_DEFLATED
            fixed.external_attr = info.external_attr
            dst.writestr(fixed, payload[info.filename])
    shutil.move(str(tmp), str(path))


def _bbox(shape):
    b = shape.BoundingBox()
    return b.xmin, b.ymin, b.xlen, b.ylen


def pack(items, bed_x=BED_X, bed_y=BED_Y, margin=MARGIN, gap=GAP):
    """Shelf-pack solids into the bed and return them translated into place.

    Hand-placed coordinates are how object 8 ended up at Y = -11 mm, off the front
    of the bed: the old check tested only xmax/ymax, so anything placed at negative
    coordinates passed. Packing from measured bounding boxes removes the class of
    bug, and validate() below checks BOTH edges of BOTH axes, per object.
    """
    ordered = sorted(items, key=lambda it: -_bbox(it[1])[3])
    placed, x, y, shelf_h = [], margin, margin, 0.0
    for name, shape in ordered:
        xmin, ymin, w, h = _bbox(shape)
        if x + w > bed_x - margin:
            x, y, shelf_h = margin, y + shelf_h + gap, 0.0
        placed.append((name, shape.moved(cq.Location(cq.Vector(x - xmin, y - ymin, 0))),
                       x, y, w, h))
        x += w + gap
        shelf_h = max(shelf_h, h)
    return placed


def validate(placed, bed_x=BED_X, bed_y=BED_Y):
    """Every object fully inside the bed, on all four sides. Returns (ok, problems)."""
    bad = []
    for name, shape, x, y, w, h in placed:
        b = shape.BoundingBox()
        if b.xmin < -1e-6 or b.ymin < -1e-6 or b.xmax > bed_x + 1e-6 or b.ymax > bed_y + 1e-6:
            bad.append(f"{name}: x {b.xmin:.1f}..{b.xmax:.1f}, y {b.ymin:.1f}..{b.ymax:.1f} "
                       f"outside 0..{bed_x:.0f} x 0..{bed_y:.0f}")
    return (not bad), bad


def check_3mf(path: Path) -> None:
    """A packet that will not open is exactly as broken as a schematic failing ERC."""
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(path) as z:
        for entry in ("[Content_Types].xml", "_rels/.rels", "3D/3dmodel.model"):
            if entry not in z.namelist():
                raise SystemExit(f"3MF is missing {entry}")
            try:
                ET.fromstring(z.read(entry))
            except ET.ParseError as e:
                raise SystemExit(f"3MF entry {entry} is not well-formed XML: {e}")


def check_stl(path: Path, plate) -> None:
    """Non-empty, parseable, and the bounding box logged. IR/Decisions 005 section 2.4.

    An STL that will not open is exactly as broken as a schematic that fails ERC,
    and this is now the file the library actually prints.
    """
    size = path.stat().st_size
    if size < 1000:
        raise SystemExit(f"STL is {size} bytes -- effectively empty")
    with path.open("rb") as fh:
        head = fh.read(84)
    if len(head) < 84:
        raise SystemExit("STL is shorter than a binary STL header")
    tri = int.from_bytes(head[80:84], "little")
    expected = 84 + tri * 50
    if tri == 0:
        raise SystemExit("STL declares zero triangles")
    if size != expected:
        raise SystemExit(f"STL length {size} != header's {tri} triangles ({expected})")
    b = plate.BoundingBox()
    print(f"  STL ok: {tri} triangles, {size/1024:.0f} KiB, bbox "
          f"{b.xlen:.1f} x {b.ylen:.1f} x {b.zlen:.1f} mm")


def print_time_hours(plate) -> float:
    return plate.Volume() / PRINT_RATE_MM3_S / 3600.0


def parts_and_probe(seed: int = SEED):
    variants = latch.packet_01_variants()
    probe = latch.beam_probe()
    rng = random.Random(seed)
    rng.shuffle(variants)
    return variants, probe


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "stl").mkdir(exist_ok=True)

    variants, probe = parts_and_probe()

    items, meta = [], {}
    for v in variants:
        part = latch.carrier(v)
        exporters.export(part, str(OUT / "stl" / f"carrier-{v.label}.stl"))
        items.append((f"carrier-{v.label}", part.val()))
        meta[f"carrier-{v.label}"] = v.dict()

    # The probe prints FLAT, like everything else. Its difference is geometric --
    # a longer, thinner cantilever -- because print direction is a setting the
    # library controls and we do not.
    pr = latch.carrier(probe)
    exporters.export(pr, str(OUT / "stl" / f"carrier-{probe.label}.stl"))
    items.append((f"carrier-{probe.label}", pr.val()))
    meta[f"carrier-{probe.label}"] = probe.dict()

    bar = latch.hook_bar()
    exporters.export(bar, str(OUT / "stl" / "hook-bar.stl"))
    items.append(("hook-bar", bar.val()))

    frame = latch.test_frame()
    exporters.export(frame, str(OUT / "stl" / "test-frame.stl"))
    items.append(("test-frame", frame.val()))

    placed = pack(items)
    ok, problems = validate(placed)
    if not ok:
        for line in problems:
            print(f"  OFF-BED: {line}")
        raise SystemExit("plate does not fit the bed -- refusing to write a broken packet")

    plate = cq.Compound.makeCompound([shape for _, shape, *_ in placed])

    # THE library deliverable is the merged STL. One file containing every part in
    # its intended relative position, because the library chooses orientation and a
    # single merged solid forces that choice to apply to all parts uniformly -- a
    # blind comparison survives being rotated together, not part by part.
    exporters.export(plate, str(OUT / "plate.stl"))
    check_stl(OUT / "plate.stl", plate)

    # The 3MF is ours, not the library's: it cannot open one. Kept because it is
    # the format our own slicer previews use, and gated because it shipped broken.
    exporters.export(plate, str(OUT / "plate.3mf"))
    normalise_3mf(OUT / "plate.3mf")
    check_3mf(OUT / "plate.3mf")

    pbb = plate.BoundingBox()
    need_x, need_y = pbb.xmax + MARGIN, pbb.ymax + MARGIN
    rows = []
    for name, shape, x, y, w, h in placed:
        b = shape.BoundingBox()
        rows.append({"part": name, "x": round(b.xmin, 1), "y": round(b.ymin, 1),
                     "w": round(w, 1), "h": round(h, 1), **meta.get(name, {})})

    manifest = {
        "packet": "WP04-01", "work_package": "WP-04",
        "built": date.today().isoformat(), "revision": 3,
        "swept_parameter": "hook_depth (mm)", "bracket_mm": [0.6, 2.1],
        "seed": SEED, "blind": True,
        "bed_assumed_mm": [BED_X, BED_Y],
        "plate_extent_mm": [round(pbb.xmax, 1), round(pbb.ymax, 1)],
        "minimum_bed_mm": [round(need_x), round(need_y)],
        "xml_valid": True,
        "stl_validated": True,
        "library_deliverable": "plate.stl",
        "estimated_print_hours": round(print_time_hours(plate), 1),
        "library_job_limit_hours": MAX_JOB_HOURS,
        "print_settings_assumed": {
            "material": "PLA", "layer_mm": 0.2, "nozzle_mm": 0.4,
            "perimeters": 3, "infill_pct": 40,
            "supports": "none required -- every overhang is <= 45 degrees by design",
            "note": "Michael's answer to Q-006 (Decisions 002 §2).",
        },
        "parts": rows,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    lines = [
        "# Plate map — packet WP04-01 (rev 3)", "",
        f"Fits a **{round(need_x)} × {round(need_y)} mm** bed. Laid out for "
        f"{BED_X:.0f} × {BED_Y:.0f} mm — a Prusa Mini or Bambu A1 mini.", "",
        "The letter is **not** related to hook depth; the mapping is in `manifest.json` and",
        "deliberately not on the card.", "",
        "| Part | X | Y | W | H |", "|---|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(f"| {r['part']} | {r['x']:.0f} | {r['y']:.0f} | "
                     f"{r['w']:.0f} | {r['h']:.0f} |")
    lines += ["", "`D` and `H` are the same geometry as one of the lettered variants, placed",
              "apart on the bed. If they do not rank together, bed position is affecting the",
              "parts more than the swept parameter is, and the next sweep needs coarser steps."]
    (OUT / "plate-map.md").write_text("\n".join(lines) + "\n")

    print(f"packet WP04-01 rev 3 -> {OUT}")
    print(f"  {len(placed)} objects, all inside the bed")
    print(f"  extent {pbb.xmax:.1f} x {pbb.ymax:.1f} mm; needs a bed of at least "
          f"{round(need_x)} x {round(need_y)} mm")
    hrs = print_time_hours(plate)
    print(f"  estimated print time {hrs:.1f} h "
          f"({'within' if hrs < MAX_JOB_HOURS else 'OVER'} the library's "
          f"{MAX_JOB_HOURS:.0f} h limit)")
    print(f"  library deliverable: plate.stl")
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
