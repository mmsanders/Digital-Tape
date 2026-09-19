#!/usr/bin/env python3
"""Build print-run packet WP04-01: one plate, one card, one results template.

The packet is the deliverable, not the model (Hardware Charter §03). Michael
should arrive at the library with a file, put it on the machine, and leave with
an answer -- no arranging, no orientation choice, no support decision.

    make -C hardware packet-wp04

**One plate, two experiments** (PM Decisions 006 §2 and §4). Michael gets two
library prints a month, so the WP-04 latch sweep and the WP-24 cartridge-clasp
sweep share a bed. They are independent: different parts, different letters,
different questions, and neither ranking can contaminate the other. What they
share is a trip.

Outputs into hardware/packets/wp04-01/:
    plate.stl        THE library deliverable -- one merged solid, all parts
    plate.3mf        our own preview; the library cannot open 3MF
    tpu-lip.stl      the TPU variant. NOT on the plate -- the library is PLA-only
    stl/<part>.stl   individual parts, if something needs reprinting alone
    manifest.json    the blind mapping. NOT for the card -- see below
    plate-map.md     which letter sits where on the bed

The letter on each button is deliberately unrelated to its hook depth, and the
mapping lives here rather than on the card, so the ranking is blind. Michael can
read this file; the point is that he will not, and that nothing he is handed
tells him which button is supposed to win.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import shutil
import sys
import zipfile
from pathlib import Path

import cadquery as cq
from cadquery import exporters

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cartridge"))
import latch  # noqa: E402
import shell  # noqa: E402

# Shasta Public Libraries, Original Prusa i3 MK3: 250 x 210 x 210 mm build volume,
# PLA only, .stl only, staff choose orientation, jobs over 6 h may be refused.
# We keep laying out for the small common bed -- it costs nothing and an A1 mini
# is 180 x 180 if Michael buys one.
PRINT_RATE_MM3_S = 11.0     # EST, MK3 at 0.2 mm with perimeters and travel
MAX_JOB_HOURS = 6.0         # library refusal threshold

OUT = Path(__file__).resolve().parents[2] / "packets" / "wp04-01"

# The bed is now a fact rather than a guess. PM Decisions 007 §0 verified the
# rev-4 plate against the library's actual machine and states the constraint
# directly: "the binding limits are now the six-hour cap and the 250 x 210 bed".
# Rev 4 and earlier laid out for a conservative 180 x 180 because Q-006 came back
# "not yet checked, proceed on the default"; that caution is spent, and the extra
# room is what pays for four lids instead of two.
# Rev 6. Michael confirms the A1 Mini's ADVERTISED NOMINAL envelope, 180 x 180 x
# 180 mm. That is a nominal figure from the machine's specification, not a
# measured usable area, and the difference is the whole reason for the clearance
# below: a nominal envelope is not proof that every edge of it is printable.
BED_X, BED_Y, BED_Z = 180.0, 180.0, 180.0
BED_SOURCE = ("Michael-confirmed ADVERTISED NOMINAL envelope of the Bambu Lab "
              "A1 Mini, 180 x 180 x 180 mm. Not a measured usable area: no "
              "print has been made and no edge has been proven usable.")

# Every object stays at least this far from every nominal bed edge, and no
# taller than MAX_Z. Both are deliberate deratings of a number we do not trust
# to its last millimetre.
EDGE_CLEARANCE = 5.0     # mm, XY, from each of the four nominal edges
MAX_Z = 175.0            # mm, 5 mm under the nominal height

# A filleted solid's tessellated bounding box dips a few microns below the
# plane it was built on -- the measured worst here is 9 um. That is a quarter
# of a percent of a 0.2 mm layer and the first layer absorbs it. The tolerance
# is set at a quarter of a layer so it stays far below anything a slicer would
# act on, while a part genuinely modelled INTO the bed still fails.
Z_SINK_TOLERANCE = 0.05  # mm

MARGIN = EDGE_CLEARANCE
GAP = 4.0
SEED = 20260902          # fixed, so the plate is reproducible from source
PACKET_RELEASE_DATE = "2026-09-19"  # rev-6 provenance, never the rebuild's wall clock
PACKET_REVISION = 6


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


# --------------------------------------------------------------------------
# Duplicate detection -- PM Decisions 007 §1
# --------------------------------------------------------------------------
#
# The PM's plate review found that D, M and H are the same button. They are, and
# it is deliberate (ADR-104: bed controls, ranked blind to test whether print
# position is confounding the sweep). But the review's mechanism was that they
# are "byte-identical solids", and they are not -- each carries a different
# letter, so as shipped every one of the nine is a distinct mesh.
#
# THAT is the part worth building a gate around. The obvious check -- compare the
# solids -- runs GREEN on this plate while three of nine parts are the same
# mechanism, because the blind label that makes the experiment work also makes
# every part unique. It is the allocation gate again (CLAUDE.md §1): a check that
# measures the wrong quantity reads as passing.
#
# So there are two checks, and they catch different failures:
#
#   PARAMETER  no two parts share the swept parameter unless declared a control.
#              Catches the sweep collapsing -- what the PM was actually pointing
#              at, and what a mesh comparison cannot see.
#   MECHANISM  no two parts are the same solid once the LABEL IS SUPPRESSED.
#              Catches a parameter that never reached the geometry: two variants
#              differing on paper and identical in the file.

def mechanism_signature(shape, tol: float = 0.02) -> str:
    """Position-independent hash of a solid, for comparing parts across a plate.

    Translated to its own bounding-box origin, so where a part sits on the bed
    cannot mask that it is a duplicate of one somewhere else.
    """
    verts, tris = shape.tessellate(tol)
    b = shape.BoundingBox()
    pts = [(round(v.x - b.xmin, 3), round(v.y - b.ymin, 3), round(v.z - b.zmin, 3))
           for v in verts]
    h = hashlib.sha256()
    for tri in sorted(tuple(sorted(t)) for t in tris):
        for i in tri:
            h.update(("%.3f,%.3f,%.3f;" % pts[i]).encode())
    return h.hexdigest()[:16]


def check_duplicates(entries) -> None:
    """`entries` is [(name, swept_value, declared_control, bare_solid), ...].

    Fails the build on any undeclared collision, in either check.
    """
    problems = []

    by_param, by_mech = {}, {}
    for name, param, declared, solid in entries:
        by_param.setdefault(param, []).append((name, declared))
        by_mech.setdefault(mechanism_signature(solid), []).append((name, declared))

    for param, group in sorted(by_param.items(), key=lambda kv: str(kv[0])):
        if len(group) < 2:
            continue
        undeclared = [n for n, declared in group if not declared]
        if len(undeclared) > 1:
            problems.append(
                f"parameter {param}: {sorted(undeclared)} share the swept value and none "
                "is declared a control -- the sweep has collapsed")

    for sig, group in by_mech.items():
        if len(group) < 2:
            continue
        undeclared = [n for n, declared in group if not declared]
        if len(undeclared) > 1:
            problems.append(
                f"mechanism {sig}: {sorted(undeclared)} are the same solid once the label "
                "is suppressed -- a parameter did not reach the geometry")

    if problems:
        for line in problems:
            print(f"  DUPLICATE: {line}")
        raise SystemExit("undeclared duplicate parts -- refusing to write the packet")

    declared_groups = {p: [n for n, _ in g] for p, g in by_param.items() if len(g) > 1}
    for param, names in sorted(declared_groups.items(), key=lambda kv: str(kv[0])):
        print(f"  declared repeat at {param}: {sorted(names)} (blind control, ADR-104)")


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


def validate(placed, bed_x=BED_X, bed_y=BED_Y, bed_z=BED_Z,
             clearance=EDGE_CLEARANCE, max_z=MAX_Z):
    """Every object inside the bed with clearance, and under the height cap.

    Fail-closed, and checked per object on BOTH edges of BOTH axes plus Z. Hand
    placement is how object 8 once ended up at Y = -11 mm off the front of the
    bed, with a check that only looked at xmax/ymax.

    The clearance is not decoration. The envelope is a nominal advertised
    figure; the outer few millimetres of a bed are where adhesion and levelling
    fail first, and nothing here has ever printed. Returns (ok, problems).
    """
    lo, hi_x, hi_y = clearance, bed_x - clearance, bed_y - clearance
    bad = []
    if max_z > bed_z:
        bad.append(f"the height cap {max_z} mm exceeds the bed's {bed_z} mm")
    for name, shape, x, y, w, h in placed:
        b = shape.BoundingBox()
        if b.xmin < lo - 1e-6 or b.ymin < lo - 1e-6 or \
                b.xmax > hi_x + 1e-6 or b.ymax > hi_y + 1e-6:
            bad.append(
                f"{name}: x {b.xmin:.1f}..{b.xmax:.1f}, y {b.ymin:.1f}..{b.ymax:.1f} "
                f"is outside the usable area {lo:.1f}..{hi_x:.1f} x "
                f"{lo:.1f}..{hi_y:.1f} mm ({clearance:.1f} mm clearance from a "
                f"{bed_x:.0f} x {bed_y:.0f} mm nominal bed)")
        if b.zmax > max_z + 1e-6:
            bad.append(f"{name}: {b.zmax:.1f} mm tall, over the {max_z:.0f} mm cap")
        if b.zmin < -Z_SINK_TOLERANCE:
            bad.append(f"{name}: sits {b.zmin:.3f} mm below the plate, more "
                       f"than the {Z_SINK_TOLERANCE} mm tessellation allowance")
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


def shell_variants(seed: int = SEED + 1):
    """The WP-24 clasp sweep. Shuffled with its own seed so the two experiments
    on this plate cannot correlate through a shared shuffle."""
    v = shell.packet_variants()
    random.Random(seed).shuffle(v)
    return v


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    # Wipe the per-part directory rather than writing over it. `carrier-X-onside.stl`
    # survived in here for two revisions after the on-its-side variant was dropped,
    # so the packet shipped a printable file for a part that no longer exists in
    # the design. A build that only ever adds files cannot notice that.
    stl_dir = OUT / "stl"
    if stl_dir.exists():
        shutil.rmtree(stl_dir)
    stl_dir.mkdir(parents=True)

    variants, probe = parts_and_probe()

    items, meta, dup = [], {}, []
    for v in variants:
        part = latch.carrier(v)
        dup.append((f"carrier-{v.label}", ("hook_depth", v.hook_depth),
                    v.role == "bed-control", latch.carrier(v, label=False).val()))
        exporters.export(part, str(OUT / "stl" / f"carrier-{v.label}.stl"))
        items.append((f"carrier-{v.label}", part.val()))
        meta[f"carrier-{v.label}"] = v.dict()

    # The probe prints FLAT, like everything else. Its difference is geometric --
    # a longer, thinner cantilever -- because print direction is a setting the
    # library controls and we do not.
    pr = latch.carrier(probe)
    dup.append((f"carrier-{probe.label}",
                ("beam", probe.beam_length, probe.beam_thickness), False,
                latch.carrier(probe, label=False).val()))
    exporters.export(pr, str(OUT / "stl" / f"carrier-{probe.label}.stl"))
    items.append((f"carrier-{probe.label}", pr.val()))
    meta[f"carrier-{probe.label}"] = probe.dict()

    # --- WP-24: the cartridge clasp sweep, sharing this plate ---------------
    for sv in shell_variants():
        part = shell.base(sv)
        dup.append((f"shell-base-{sv.label}", ("interference", sv.interference),
                    False, shell.base(sv, label=False).val()))
        exporters.export(part, str(OUT / "stl" / f"shell-base-{sv.label}.stl"))
        items.append((f"shell-base-{sv.label}", part.val()))
        meta[f"shell-base-{sv.label}"] = sv.dict()

    # FOUR lids, one per base, labelled to match (PM Decisions 007 §1).
    #
    # Rev 4 shipped two lids for four bases. Michael would have had to reuse a
    # mating half across variants, so wear on the shared part would be confounded
    # with whichever variant he happened to test last -- on a plate whose entire
    # question is retention. The print budget now covers a lid each, so the
    # confound is removed rather than managed with a test order on the card.
    #
    # They are the same mechanism on purpose, so they are DECLARED to the
    # duplicate gate. Undeclared, four identical lids are exactly what that gate
    # exists to catch.
    for sv in shell_variants():
        part = shell.lid(sv.label)
        dup.append((f"shell-lid-{sv.label}", ("lid", "common"), True,
                    shell.lid().val()))
        exporters.export(part, str(OUT / "stl" / f"shell-lid-{sv.label}.stl"))
        items.append((f"shell-lid-{sv.label}", part.val()))

    # No TPU part. PM Decisions 007 §2: the library runs a single spool of
    # whatever it has loaded, so a second-material part cannot be printed at all.
    # `tpu-lip.stl` from rev 4 is deleted rather than left lying in the packet.
    tpu = OUT / "tpu-lip.stl"
    if tpu.exists():
        tpu.unlink()

    bar = latch.hook_bar()
    exporters.export(bar, str(OUT / "stl" / "hook-bar.stl"))
    items.append(("hook-bar", bar.val()))

    frame = latch.test_frame()
    exporters.export(frame, str(OUT / "stl" / "test-frame.stl"))
    items.append(("test-frame", frame.val()))

    # PM Decisions 007 §1. Before anything is written: no undeclared duplicates.
    check_duplicates(dup)

    # --- two plates, because one no longer fits ------------------------------
    #
    # The rev-5 plate was 228 mm long, laid out for the library's 250 x 210 bed.
    # That machine is gone; the A1 Mini's nominal envelope is 180 x 180. So the
    # packet splits, and the split is not arbitrary:
    #
    #   plate-wp24  all four shell bases AND their four matching lids, together
    #               in ONE job. A base and its lid are a matched pair -- printed
    #               in the same session they shrink together and what survives
    #               is the printer's repeatability, not the material's. Splitting
    #               a pair across jobs re-introduces exactly the confound rev 5
    #               removed by giving every base its own lid.
    #
    #   plate-wp04  the latch sweep: every carrier including the beam probe, the
    #               hook bar and the test frame. It has no pairing constraint,
    #               and it keeps the spread M/D/H bed-position controls.
    #
    # Both keep the full sweeps, the blind lettering and the labels.
    groups = {
        "wp24": [it for it in items
                 if it[0].startswith(("shell-base-", "shell-lid-"))],
        "wp04": [it for it in items
                 if not it[0].startswith(("shell-base-", "shell-lid-"))],
    }
    for gname, gitems in groups.items():
        if not gitems:
            raise SystemExit(f"plate {gname} would be empty -- refusing")

    plates, rows, all_placed = {}, [], []
    for gname, gitems in groups.items():
        placed = pack(gitems)
        ok, problems = validate(placed)
        if not ok:
            for line in problems:
                print(f"  OFF-BED [{gname}]: {line}")
            raise SystemExit(
                f"plate {gname} does not fit the usable area -- refusing to "
                f"write a broken packet")
        plate = cq.Compound.makeCompound([shape for _, shape, *_ in placed])
        bb = plate.BoundingBox()

        stem = f"plate-{gname}"
        exporters.export(plate, str(OUT / f"{stem}.stl"))
        check_stl(OUT / f"{stem}.stl", plate)
        exporters.export(plate, str(OUT / f"{stem}.3mf"))
        normalise_3mf(OUT / f"{stem}.3mf")
        check_3mf(OUT / f"{stem}.3mf")

        for name, shape, x, y, w, h in placed:
            b = shape.BoundingBox()
            rows.append({"plate": stem, "part": name, "x": round(b.xmin, 1),
                         "y": round(b.ymin, 1), "w": round(w, 1),
                         "h": round(h, 1), **meta.get(name, {})})
        all_placed += placed
        plates[stem] = {
            "file": f"{stem}.stl",
            "preview": f"{stem}.3mf",
            "objects": len(placed),
            "extent_mm": [round(bb.xlen, 1), round(bb.ylen, 1), round(bb.zmax, 1)],
            "occupies_mm": [round(bb.xmin, 1), round(bb.ymin, 1),
                            round(bb.xmax, 1), round(bb.ymax, 1)],
            "clearance_mm": {
                "min_x": round(bb.xmin, 1),
                "min_y": round(bb.ymin, 1),
                "max_x": round(BED_X - bb.xmax, 1),
                "max_y": round(BED_Y - bb.ymax, 1),
            },
            "estimated_print_hours": round(print_time_hours(plate), 1),
        }

    # The old single merged deliverable is gone with the machine that needed it.
    for stale in ("plate.stl", "plate.3mf", "tpu-lip.stl"):
        q = OUT / stale
        if q.exists():
            q.unlink()

    manifest = {
        "packet": "WP04-01", "work_packages": ["WP-04", "WP-24"],
        "built": PACKET_RELEASE_DATE, "revision": PACKET_REVISION,
        "experiments": [
            {"work_package": "WP-04", "plate": "plate-wp04",
             "parts": "carrier-*, hook-bar, test-frame",
             "swept_parameter": "hook_depth (mm)", "bracket_mm": [0.6, 2.1]},
            {"work_package": "WP-24", "plate": "plate-wp24",
             "parts": "shell-base-*, shell-lid-*",
             "swept_parameter": "interference (mm)",
             "bracket_mm": [min(shell.SWEEP_INTERFERENCE),
                            max(shell.SWEEP_INTERFERENCE)]},
        ],
        "seed": SEED, "blind": True,
        "single_material": True,
        "bed_mm": [BED_X, BED_Y, BED_Z],
        "bed_source": BED_SOURCE,
        "edge_clearance_mm": EDGE_CLEARANCE,
        "max_object_height_mm": MAX_Z,
        "printed": False,
        "usable_area_proven": False,
        "duplicate_check": "parameter + label-suppressed mechanism",
        "plates": plates,
        "matched_pairs_on_one_plate": True,
        "xml_valid": True,
        "stl_validated": True,
        "print_settings_assumed": {
            "material": "PLA or PETG, recorded per job; PLA is the conservative "
                        "case the analysis assumes",
            "layer_mm": 0.2, "nozzle_mm": 0.4,
            "perimeters": 3, "infill_pct": 40,
            "supports": "OFF -- every overhang is <= 45 degrees by design, and "
                        "support material in a carrier's relief slot destroys "
                        "the property the sweep measures",
            "orientation": "flat as laid out; all parts in one orientation",
        },
        "parts": rows,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    lines = [
        f"# Plate map — packet WP04-01 (rev {PACKET_REVISION})", "",
        "**Two plates, two experiments.** `plate-wp04` is the latch sweep:",
        "`carrier-*`, `hook-bar`, `test-frame`. `plate-wp24` is the cartridge clasp",
        "sweep: every `shell-base-*` **with its matching `shell-lid-*` in the same",
        "job**, because a base and its lid are a matched pair and printing them",
        "apart re-introduces the confound the per-base lids removed.", "",
        f"Laid out for a **{BED_X:.0f} × {BED_Y:.0f} × {BED_Z:.0f} mm** nominal",
        f"envelope with **{EDGE_CLEARANCE:.0f} mm clearance** from every edge and a",
        f"**{MAX_Z:.0f} mm** height cap. The envelope is the machine's advertised",
        "figure, not a measured usable area — nothing here has been printed.", "",
        "The letter is **not** related to hook depth; the mapping is in",
        "`manifest.json` and deliberately not on the card.", "",
        "| Plate | Part | X | Y | W | H |", "|---|---|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(f"| {r['plate']} | {r['part']} | {r['x']:.0f} | {r['y']:.0f} | "
                     f"{r['w']:.0f} | {r['h']:.0f} |")
    lines += ["", "`D` and `H` are the same geometry as one of the lettered variants, placed",
              "apart on the bed. If they do not rank together, bed position is affecting the",
              "parts more than the swept parameter is, and the next sweep needs coarser steps."]
    (OUT / "plate-map.md").write_text("\n".join(lines) + "\n")

    print(f"packet WP04-01 rev {PACKET_REVISION} -> {OUT}")
    print(f"  {len(all_placed)} objects on {len(plates)} plates, all inside the "
          f"usable area")
    for stem, pl in plates.items():
        c = pl["clearance_mm"]
        print(f"  {stem}: {pl['objects']} objects, extent "
              f"{pl['extent_mm'][0]:.1f} x {pl['extent_mm'][1]:.1f} x "
              f"{pl['extent_mm'][2]:.1f} mm, clearance "
              f"{min(c.values()):.1f} mm minimum, ~{pl['estimated_print_hours']:.1f} h")
    print(f"  nominal bed {BED_X:.0f} x {BED_Y:.0f} x {BED_Z:.0f} mm, "
          f"{EDGE_CLEARANCE:.0f} mm edge clearance, {MAX_Z:.0f} mm height cap")
    print("  NOT printed, and the nominal envelope is not proof every edge is usable")
    return 0


if __name__ == "__main__":
    raise SystemExit(build())
