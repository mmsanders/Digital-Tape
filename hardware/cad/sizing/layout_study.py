#!/usr/bin/env python3
"""Device size study — what has to go inside, and what envelope that implies.

NOT A DESIGN. A conversation piece for Michael, 27 Sep 2026. Two stack-ups of the
same parts, beside ghost envelopes of the three reference Walkmans.

Provenance, per part:
  [REPO] from this repository        [EST] my estimate, no layout or datasheet
"""
import cadquery as cq
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "packets" / "sizing-study"
WALL, CLR = 2.5, 0.5

PARTS = {  # name: (W, H, T, tier, note)
    "cartridge":  (86, 54, 12, "REPO", "cartridge-shell.md SH-1 working size -- Michael's call"),
    "board":      (70, 50, 6,  "EST",  "rev A: RT1062 + codec + 2 edge connectors; no layout exists"),
    "battery":    (50, 34, 6,  "EST",  "a ~1000 mAh pouch class; capacity not yet specified"),
    "solenoid":   (20, 12, 11, "EST",  "Route A release; no part selected"),
    "buttons":    (80, 28, 14, "EST",  "5 latching keys on the top edge, incl. 8 mm travel"),
}

def blk(name, x, y, z):
    w, h, t = PARTS[name][:3]
    return cq.Workplane("XY").box(w, h, t, centered=False).translate((x, y, z))

def option_a():
    """Two decks STACKED in thickness. Compact face, thick body."""
    W = 86 + 2 * (WALL + CLR)
    z = WALL
    parts = [blk("cartridge", WALL + CLR, WALL + 8, z)]; z += 12 + CLR
    parts.append(blk("cartridge", WALL + CLR, WALL + 8, z)); z += 12 + CLR
    parts.append(blk("board", WALL + CLR, WALL + 8, z)); z += 6
    parts.append(blk("battery", WALL + CLR + 18, WALL + 12, z)); z += 6
    top = WALL + 8 + 54 + 2
    parts.append(blk("buttons", WALL + CLR + 3, top, WALL))
    parts.append(blk("solenoid", WALL + CLR + 60, top + 2, WALL + 16))
    H = top + 28 + WALL
    T = z + WALL
    return (W, H, T), parts

def option_b():
    """Two decks SIDE BY SIDE in height. Thin body, tall face."""
    W = 86 + 2 * (WALL + CLR)
    y = WALL + 8
    parts = [blk("cartridge", WALL + CLR, y, WALL)]
    parts.append(blk("board", WALL + CLR + 8, y, WALL + 12 + CLR)); y += 54 + 3
    parts.append(blk("cartridge", WALL + CLR, y, WALL))
    parts.append(blk("battery", WALL + CLR + 18, y + 10, WALL + 12 + CLR)); y += 54 + 2
    parts.append(blk("buttons", WALL + CLR + 3, y, WALL))
    parts.append(blk("solenoid", WALL + CLR + 60, y + 2, WALL + 14))
    H = y + 28 + WALL
    T = WALL + 12 + CLR + 6 + 1 + WALL
    return (W, H, T), parts

WALKMEN = {  # W, H, T mm, grams -- search-index figures attributed to walkman.land
    "TPS-L2 (1979)": (88, 133.5, 29, 390),
    "WM-2 (1981)":   (80, 109, 29.5, 280),
    "WM-F5 (1983)":  (100.4, 125.2, 42.1, 370),
}

def ghost(w, h, t):
    """An envelope drawn as a thin shell so it reads as an outline, not a brick."""
    o = cq.Workplane("XY").box(w, h, t, centered=False)
    return o.cut(cq.Workplane("XY").box(w - 2, h - 2, t + 2, centered=False)
                 .translate((1, 1, -1)))

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    assy = cq.Assembly()
    x = 0
    rows = []
    for label, fn, col in (("A-stacked", option_a, "steelblue"),
                           ("B-side-by-side", option_b, "darkorange")):
        (W, H, T), parts = fn()
        assy.add(ghost(W, H, T).translate((x, 0, 0)), name=f"{label}-envelope",
                 color=cq.Color("gray"))
        for i, p in enumerate(parts):
            assy.add(p.translate((x, 0, 0)), name=f"{label}-part{i}", color=cq.Color(col))
        rows.append((label, W, H, T))
        x += W + 25
    for name, (w, h, t, g) in WALKMEN.items():
        assy.add(ghost(w, h, t).translate((x, 0, 0)), name=name, color=cq.Color("black"))
        x += w + 25
    assy.save(str(OUT / "layout-study.step"))
    for label, W, H, T in rows:
        print(f"  {label:15s} {W:6.1f} x {H:6.1f} x {T:5.1f} mm   vol {W*H*T/1000:5.0f} cm3")
    for name, (w, h, t, g) in WALKMEN.items():
        print(f"  {name:15s} {w:6.1f} x {h:6.1f} x {t:5.1f} mm   vol {w*h*t/1000:5.0f} cm3   {g} g")
