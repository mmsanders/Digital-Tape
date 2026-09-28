#!/usr/bin/env python3
"""Size mockups: Sony WM-2 (1981) and a Digital-Tape envelope, packet SIZE-01.

    python3 mockups.py              writes hardware/packets/size-01/
    python3 mockups.py --self-test  shows each gate going red on a broken part

Life-size, hollow, re-openable, for holding in the hand and ballasting with coins.

SHAPE SOURCES. WM-2 outer size 80 x 109 x 29.5 mm, read from walkman.land on
27 Sep 2026 and matching the 1981 Japanese ad (80 x 109 x 29.5, 280 g incl.
battery). Control POSITIONS are traced by eye from product photos and the ad --
good to a few millimetres, not measured. Our envelope is layout A of
layout_study.py: two cartridges stacked, 92 x 97 x 42, every internal part an
estimate except the cartridge's working size.

THE SHELL IS SPLIT THE WAY A REAL ONE WOULD BE: front and back halves, parting
line parallel to the big faces, each half printed on its outer face so the
visible surfaces get the plate finish and nothing needs support.

THE JOINT answers three things the library clasp plate taught us:
  * the lid's rim broke off because it hung from a thin ledge. Here it is a
    RABBET: each half's lip stands directly on its own full wall, so there is
    no ledge to snap;
  * the seam was too wide. A rabbet leaves a butt line at the outer skin;
  * A and Q could not be opened without breaking them. The lip clearance is
    0.05 mm/side -- the band the fit ladder says releases with a twist -- plus
    four small detents, and a pry notch so a fingernail or a coin opens it.

CONTROLS on a face that prints against the bed can only be recessed, so the
WM-2's buttons are the button shape standing inside a moat: you feel the edge
of every button. Our device has edge keys (Michael's preference), and an edge
is a vertical wall in print, so those keys are genuinely raised.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import cadquery as cq
from cadquery import exporters

OUT = Path(__file__).resolve().parents[2] / "packets" / "size-01"

WALL = 2.0
FLOOR = 2.0
SKIRT_H = 4.0            # lid skirt, drops over the tray tongue
TONGUE_H = 3.8           # 0.2 short of the skirt so the seam closes, not the tongue
CLR = 0.05               # per side, tongue to skirt. The A1MINI-01 ladder was
                         # diametral: 0.10 there = 0.05 a side = rung 3, "snug,
                         # releases with a twist" in Michael's hand
SKIRT_T = 1.0            # skirt occupies offset 0 .. -1.0
TONGUE_IN = SKIRT_T + CLR  # tongue occupies offset -1.05 .. -WALL
DETENT_H = 0.25          # bump proud of the tongue; interference 0.20 after CLR
BED, MARGIN = 180.0, 5.0
PLA_DENSITY = 1.24       # g/cm^3, solid; a real print with infill weighs less

NICKEL_D, NICKEL_T, NICKEL_G = 21.21, 1.95, 5.000   # US Mint specification


# ---------------------------------------------------------------- primitives

def _rr_face(W, H, r, off=0.0):
    w = cq.Wire.makePolygon([(0, 0, 0), (W, 0, 0), (W, H, 0), (0, H, 0)], close=True)
    w = w.fillet2D(r, w.Vertices())
    if off:
        w = w.offset2D(off, "arc")[0]
    return cq.Face.makeFromWires(w)


def slab(W, H, r, off, z0, z1):
    s = cq.Solid.extrudeLinear(_rr_face(W, H, r, off), cq.Vector(0, 0, z1 - z0))
    return cq.Workplane().add(s.translate(cq.Vector(0, 0, z0)))


def ring(W, H, r, off_out, off_in, z0, z1):
    return slab(W, H, r, off_out, z0, z1).cut(slab(W, H, r, off_in, z0, z1))


def box(x0, y0, z0, x1, y1, z1):
    return (cq.Workplane().box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, y0, z0)))


def stadium(cx, cy, length, width, angle_deg, z0, z1):
    return (cq.Workplane().workplane(offset=z0).center(cx, cy)
            .slot2D(length, width, angle_deg).extrude(z1 - z0))


def cyl(cx, cy, r, z0, z1):
    return cq.Workplane().workplane(offset=z0).center(cx, cy).circle(r).extrude(z1 - z0)


def rod(r, length, base, direction):
    """A cylinder from an explicit base point along an explicit axis. No
    named sketch planes, so no guessing which way a plane's normal points."""
    return cq.Workplane().add(cq.Solid.makeCylinder(
        r, length, cq.Vector(*base), cq.Vector(*direction)))


def prism_xz(pts_xz, y0, length):
    """A prism whose cross-section lies in the XZ plane, extruded along +Y."""
    w = cq.Wire.makePolygon([cq.Vector(x, y0, z) for x, z in pts_xz], close=True)
    return cq.Workplane().add(
        cq.Solid.extrudeLinear(cq.Face.makeFromWires(w), cq.Vector(0, length, 0)))


def ridge(side_x, W, zc, y0, length, face_x, proud, inward, half_base, half_top):
    """A trapezoidal ridge standing `proud` off a vertical face at x = face_x.

    Straight-sided so the boolean is reliable -- small spheres pushed a quarter
    of a millimetre proud of a thin wall made the kernel drop the whole tray.
    `side_x` is -1 for the left wall (ridge points -X), +1 for the right.
    """
    pts = [(face_x + inward, zc - half_base), (face_x, zc - half_base),
           (face_x - proud, zc - half_top), (face_x - proud, zc + half_top),
           (face_x, zc + half_base), (face_x + inward, zc + half_base)]
    if side_x > 0:
        pts = [(W - x, z) for x, z in pts]
    return prism_xz(pts, y0, length)


# ---------------------------------------------------------------- the shell

def shell_pair(W, H, T, r, zs):
    """Tray (back, z 0..zs+tongue) and lid (front, zs..T), rabbet-jointed.

    The seam is the plane z = zs. The lid's skirt drops over the tray's tongue.
    """
    tray = (slab(W, H, r, 0, 0, FLOOR)
            .union(ring(W, H, r, 0, -WALL, FLOOR, zs))
            .union(ring(W, H, r, -TONGUE_IN, -WALL, zs, zs + TONGUE_H)))
    lid = (slab(W, H, r, 0, T - FLOOR, T)
           .union(ring(W, H, r, 0, -WALL, zs + SKIRT_H, T - FLOOR))
           .union(ring(W, H, r, 0, -SKIRT_T, zs, zs + SKIRT_H)))

    # Detents on the long sides: a ridge on the tongue, a groove in the skirt.
    zc = zs + TONGUE_H / 2
    for y in (H * 0.3, H * 0.7):
        for sx in (-1, 1):
            tray = tray.union(ridge(sx, W, zc, y - 2.5, 5.0, face_x=TONGUE_IN,
                                    proud=DETENT_H, inward=0.5,
                                    half_base=1.0, half_top=0.5))
            lid = lid.cut(ridge(sx, W, zc, y - 2.7, 5.4, face_x=SKIRT_T,
                                proud=DETENT_H + 0.05, inward=0.3,
                                half_base=1.1, half_top=0.6))
    # Pry notch in the skirt, bottom edge centre: a thumbnail or a coin opens it.
    lid = lid.cut(box(W / 2 - 6, -1, zs - 0.1, W / 2 + 6, SKIRT_T + 0.2, zs + 1.6))
    return tray, lid


def coin_grid(W, H, r, z0, height, pitch=24.0, t=1.2):
    """Low ribs so coins stack in cells instead of sliding. Cells fit a nickel."""
    inner = slab(W, H, r, -WALL + 0.3, z0, z0 + height)   # bite into the wall
    ribs = None
    x = WALL + pitch
    while x < W - WALL - 4:
        b = box(x - t / 2, 0, z0, x + t / 2, H, z0 + height)
        ribs = b if ribs is None else ribs.union(b)
        x += pitch
    y = WALL + pitch
    while y < H - WALL - 4:
        b = box(0, y - t / 2, z0, W, y + t / 2, z0 + height)
        ribs = b if ribs is None else ribs.union(b)
        y += pitch
    return ribs.intersect(inner)


def groove_rr(W, H, r, inset, width, depth, z_face, up):
    """An engraved rounded-rectangle outline on a face (door seams, windows)."""
    z0, z1 = (z_face - depth, z_face + 1) if up else (z_face - 1, z_face + depth)
    return ring(W, H, r, -inset, -(inset + width), z0, z1)


def groove_rect(x, y, w, h, r, width, depth, z_face, up):
    return groove_rr(w, h, r, 0, width, depth, z_face, up).translate((x, y, 0))


# ---------------------------------------------------------------- WM-2

def wm2():
    W, H, T, r = 80.0, 109.0, 29.5, 2.0
    zs = 20.5                                   # door half 20.5, controls half 9
    tray, lid = shell_pair(W, H, T, r, zs)
    tray = tray.union(coin_grid(W, H, r, FLOOR, 8.0))

    # --- controls face (z = T, on the lid) -----------------------------------
    # The black ribbed triangle behind the wheel, 0.8 mm down.
    tri = (cq.Workplane().workplane(offset=T - 0.8)
           .polyline([(47, H + 1), (W + 1, H + 1), (W + 1, 72)]).close().extrude(2))
    lid = lid.cut(tri)
    # Button wells: the button shape stands flush inside a 1.5 mm moat.
    ang = -35
    for cx, cy, L, Wd in ((47, 86, 22, 9), (37, 71, 22, 10), (56, 61, 22, 10)):
        lid = lid.cut(stadium(cx, cy, L, Wd, ang, T - 1.5, T + 1))
    lid = lid.union(stadium(37, 71, 16, 6.5, ang, T - 1.5, T))       # FWD/PLAY
    lid = lid.union(stadium(56, 61, 16, 6.5, ang, T - 1.5, T))       # STOP
    for d in (-5.5, 5.5):                                            # FF, REW
        c = math.radians(ang)
        lid = lid.union(cyl(47 + d * math.cos(c), 86 + d * math.sin(c), 2.6,
                            T - 1.5, T))
    lid = lid.cut(cyl(51, 75, 1.2, T - 0.8, T + 1))                  # battery LED

    # Volume wheel, rim exposed at the top-right corner. A cup inside the lid
    # carries it, so it is attached rather than a floating island.
    wc = (72.0, 101.0)
    body = slab(W, H, r, 0, 24.6, T)
    cup = cyl(*wc, 10.0, 24.6, T).intersect(body)
    lid = lid.union(cup).cut(cyl(*wc, 9.0, 25.6, T + 1))
    wheel = cyl(*wc, 8.0, 25.6, T)
    for i in range(40):
        a = 2 * math.pi * i / 40
        wheel = wheel.cut(box(-0.4, 7.3, 25.6, 0.4, 9.0, T + 1)
                          .rotate((0, 0, 0), (0, 0, 1), math.degrees(a))
                          .translate((*wc, 0)))
    lid = lid.union(wheel)

    # --- door face (z = 0, on the tray) ---------------------------------------
    tray = tray.cut(groove_rr(W, H, r, 3.0, 0.8, 0.7, 0, up=False))          # door seam
    tray = tray.cut(groove_rect(18, 50, 44, 22, 3, 0.8, 0.7, 0, up=False))   # window
    for dx in (-11, 11):
        tray = tray.cut(cyl(40 + dx, 61, 3.5, -1, 0.7))                      # hubs

    # --- edges -----------------------------------------------------------------
    for x in (46, 55):                                            # two phone jacks
        tray = tray.cut(rod(2.8, 2.0, (x, H - 1.5, 10), (0, 1, 0)))
    tray = tray.union(box(W - 0.5, 32, 7, W + 1.2, 40, 13))        # tape switch
    tray = tray.union(box(-1.0, 92, 8, 0.5, 98, 13))               # hotline button
    return dict(name="WM-2", W=W, H=H, T=T, r=r, zs=zs, tray=tray, lid=lid,
                target_g=280, target_note="280 g incl. AA battery (1981 ad)")


# ---------------------------------------------------------------- ours

def ours():
    W, H, T, r = 92.0, 97.0, 42.0, 4.0
    zs = 29.0                                   # back half 29, front half 13
    tray, lid = shell_pair(W, H, T, r, zs)
    tray = tray.union(coin_grid(W, H, r, FLOOR, 8.0))

    # Corner bumpers, 1.5 mm proud on the sides. Guardrail 13 will want
    # something here; this reserves the space so the size is honest.
    for x0, x1 in ((-1.5, 0.5), (W - 0.5, W + 1.5)):
        for y0, y1 in ((0, 12), (H - 12, H)):
            tray = tray.union(box(x0, y0, 0, x1, y1, zs))
            lid = lid.union(box(x0, y0, zs, x1, y1, T))

    # Edge keys on the top edge: five, raised 2.5 mm. The set is not decided --
    # these are positions, not functions. The middle one has a home dimple.
    for i in range(5):
        cx = W / 2 + (i - 2) * 14.5
        key = box(cx - 5.75, H - 0.5, 9, cx + 5.75, H + 2.5, 23)
        key = key.edges("|X and >Y and >Z").chamfer(0.8)
        key = key.edges("|X and >Y and <Z").chamfer(2.2)   # 45 deg underside, no droop
        tray = tray.union(key)
    tray = tray.cut(rod(1.6, 1.0, (W / 2, H + 2.5 - 0.8, 16), (0, 1, 0)))

    # Volume thumbwheel through the right side, knurled.
    wheel = cq.Workplane().workplane(offset=12).center(W - 7, 70).circle(9).extrude(8)
    for i in range(36):
        a = 360.0 * i / 36
        wheel = wheel.cut(box(-0.4, 8.2, 11, 0.4, 10, 21)
                          .rotate((0, 0, 0), (0, 0, 1), a).translate((W - 7, 70, 0)))
    tray = tray.union(wheel.intersect(box(W - 9, 58, 12, W + 2.1, 82, 20)))

    # Left side: headphone jack and USB-C, recessed.
    tray = tray.cut(rod(3.0, 1.5, (-0.01, 60, 15), (1, 0, 0)))
    tray = tray.cut(box(-0.01, 40 - 4.5, 15 - 1.75, 1.5, 40 + 4.5, 15 + 1.75))

    # Bottom edge: the destination slot, as an engraved outline.
    slot = (box(W / 2 - 42, -0.01, 16, W / 2 + 42, 0.8, 28)
            .cut(box(W / 2 - 41.2, -0.02, 16.8, W / 2 + 41.2, 0.81, 27.2)))
    tray = tray.cut(slot)

    # Front face: the source deck's door, its window, and the record light.
    lid = lid.cut(groove_rr(W, H, r, 4.0, 0.8, 0.7, T, up=True))
    lid = lid.cut(groove_rect(W / 2 - 30, 30, 60, 30, 4, 0.8, 0.7, T, up=True))
    lid = lid.cut(cyl(W / 2, 80, 1.6, T - 1.0, T + 1))
    return dict(name="Digital-Tape layout A", W=W, H=H, T=T, r=r, zs=zs, tray=tray,
                lid=lid, target_g=150,
                target_note="~150 g EST (thermal-budget.md): no motor, no AA cells")


# ---------------------------------------------------------------- output

def for_print(part, flip):
    """Tray prints on its back face; lid is flipped onto its front face."""
    if flip:
        part = part.rotate((0, 0, 0), (1, 0, 0), 180)
    b = whole(part)[1].BoundingBox()
    return part.translate((-b.xmin, -b.ymin, -b.zmin))


def mass_g(part):
    return sum(s.Volume() for s in whole(part)[0]) / 1000.0 * PLA_DENSITY


def whole(part):
    """Every solid on the stack, as one shape -- never just the first object."""
    solids = [s for o in part.vals() for s in o.Solids()]
    return solids, cq.Compound.makeCompound(solids)


def check(name, part):
    solids, shape = whole(part)
    b = shape.BoundingBox()
    bad = []
    if len(solids) != 1:
        bad.append(f"{name}: {len(solids)} separate solids -- something is floating")
    if not solids or min(s.Volume() for s in solids) <= 0:
        bad.append(f"{name}: non-positive volume -- the solid is inside-out")
    if b.xlen > BED - 2 * MARGIN or b.ylen > BED - 2 * MARGIN or b.zlen > BED - 5:
        bad.append(f"{name}: {b.xlen:.1f} x {b.ylen:.1f} x {b.zlen:.1f} off the bed")
    return bad


def _overlap(a, b):
    return sum(s.Volume() for s in whole(a)[1].intersect(whole(b)[1]).Solids())


def check_joint(m):
    """Closed, the halves must not occupy the same space; and the detent ridges
    must really sit in their grooves. The second test is the first one's
    negative control: the same overlap measure, against a skirt with no
    grooves, has to come out positive or it cannot see a collision at all."""
    W, H, r, zs = m["W"], m["H"], m["r"], m["zs"]
    bad = []
    v = _overlap(m["tray"], m["lid"])
    if v > 0.01:
        bad.append(f"{m['name']}: closed halves overlap by {v:.2f} mm^3")
    plain = ring(W, H, r, 0, -SKIRT_T, zs, zs + SKIRT_H)
    v0 = _overlap(m["tray"], plain)
    if v0 < 1.0:
        bad.append(f"{m['name']}: ridges do not reach the skirt ({v0:.2f} mm^3) "
                   f"-- the detents would not click")
    return bad


def self_test():
    """Every gate here has to be able to go red. Feed it parts that are wrong."""
    good = box(0, 0, 0, 50, 50, 10)
    cases = {
        "good part passes": (check("good", good), False),
        "floating island": (check("island", good.union(box(60, 0, 0, 65, 5, 5))), True),
        "too big for the bed": (check("big", box(0, 0, 0, 171, 50, 10)), True),
    }
    m = ours()
    m_nogroove = dict(m, lid=m["lid"].union(ring(m["W"], m["H"], m["r"], 0, -SKIRT_T,
                                                  m["zs"], m["zs"] + SKIRT_H)))
    m_noridge = dict(m, tray=shell_pair(m["W"], m["H"], m["T"], m["r"], m["zs"])[0]
                     .cut(ring(m["W"], m["H"], m["r"], 0, -TONGUE_IN,
                               m["zs"], m["zs"] + TONGUE_H)))
    cases["real joint passes"] = (check_joint(m), False)
    cases["skirt without grooves"] = (check_joint(m_nogroove), True)
    cases["tongue without ridges"] = (check_joint(m_noridge), True)
    ok = True
    for label, (found, want_red) in cases.items():
        red = bool(found)
        ok &= red == want_red
        print(f"  {'ok ' if red == want_red else 'BAD'} {label:24s} "
              f"{'red' if red else 'green'}{': ' + found[0] if found else ''}")
    return 0 if ok else 1


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    report, problems, assy = [], [], cq.Assembly()
    x_view = 0.0
    parts_out = {}
    for m in (wm2(), ours()):
        key = "wm2" if m["name"] == "WM-2" else "ours"
        problems += check_joint(m)
        tray_p, lid_p = for_print(m["tray"], False), for_print(m["lid"], True)
        for nm, p in (("tray", tray_p), ("lid", lid_p)):
            problems += check(f"{key}-{nm}", p)
            exporters.export(p, str(OUT / f"{key}-{nm}.stl"))
            parts_out[f"{key}-{nm}"] = p
        g = mass_g(m["tray"]) + mass_g(m["lid"])
        coins = max(0, round((m["target_g"] - g) / NICKEL_G))
        report.append((m["name"], m["W"], m["H"], m["T"], g, m["target_g"], coins,
                       m["target_note"]))
        assy.add(m["tray"].translate((x_view, 0, 0)), name=f"{key}-tray",
                 color=cq.Color("gray"))
        assy.add(m["lid"].translate((x_view, 0, 0)), name=f"{key}-lid",
                 color=cq.Color("steelblue"))
        x_view += m["W"] + 30

    # Plates. WM-2's two halves share one; ours needs one per half.
    w_t, w_l = parts_out["wm2-tray"], parts_out["wm2-lid"]
    plate1 = w_t.union(w_l.translate((whole(w_t)[1].BoundingBox().xlen + 5, 0, 0)))
    for nm, p in (("plate-1-wm2", plate1), ("plate-2-ours-back", parts_out["ours-tray"]),
                  ("plate-3-ours-front", parts_out["ours-lid"])):
        b = whole(p)[1].BoundingBox()
        if b.xlen > BED - 2 * MARGIN or b.ylen > BED - 2 * MARGIN:
            problems.append(f"{nm}: {b.xlen:.1f} x {b.ylen:.1f} does not fit")
        exporters.export(p, str(OUT / f"{nm}.stl"))
        print(f"  {nm:20s} {b.xlen:6.1f} x {b.ylen:6.1f} x {b.zlen:5.1f} mm")
    assy.save(str(OUT / "size-01-assembled.step"))

    for n, W, H, T, g, tg, coins, note in report:
        print(f"  {n:22s} {W} x {H} x {T} mm  shell <= {g:5.1f} g solid  "
              f"target {tg} g -> ~{coins} nickels  ({note})")
    (OUT / "manifest.json").write_text(json.dumps({
        "packet": "SIZE-01", "revision": 1, "released": "2026-09-28",
        "printer": "Bambu Lab A1 Mini", "nozzle_mm": 0.4, "material": "PLA Basic",
        "joint": {"type": "rabbet + 4 detents + pry notch", "clearance_per_side_mm": CLR,
                  "detent_interference_mm": DETENT_H - CLR},
        "mockups": [{"name": n, "mm": [W, H, T], "shell_mass_upper_bound_g": round(g, 1),
                     "target_g": tg, "nickels_approx": coins, "target_note": note}
                    for n, W, H, T, g, tg, coins, note in report],
    }, indent=2) + "\n")
    if problems:
        raise SystemExit("\n".join(problems))
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(self_test() if "--self-test" in sys.argv[1:] else build())
