# Print packet SIZE-01 — how big should it be in the hand?

**Two life-size hollow mockups you can open, fill with coins and hold.** Three plates, A1 Mini.
Hardware Lead · rev 2, 28 Sep 2026 · sizing study, layout A

**Print plate 1 (the WM-2) first.** Ours (plates 2 and 3) is still up for discussion.
`preview.png` shows both. `size-01-assembled.step` is 2.7 MB, so it is not kept in git;
`python3 hardware/cad/sizing/mockups.py` rebuilds it.

**Rev 2 reshaped the WM-2's outer surface from measurements, not by eye.** See "How close is
the WM-2" below.

---

## What this is

| | Outside | Where the numbers come from |
|---|---|---|
| **Sony WM-2 (1981)** | 80 × 109 × 29.5 mm | walkman.land, which matches the 1981 ad. Shape and controls are measured from an orthographic render and checked against product photos, to about ±1 mm |
| **Digital-Tape, layout A** | 92 × 97 × 42 mm | `layout_study.py`: two cartridges stacked. Every part inside it is an **estimate** except the cartridge's working size |

The WM-2 is a **size reference, not a design reference**. It shows you what a real, loved,
pocketable player felt like at its weight. Ours is the honest size for what we plan to put
inside, with corner bumper pads and five raised edge keys roughed in. Those five keys are
**positions, not functions**; the control set is not decided.

## The plates

| File | Contents | Size on bed | Prints on |
|---|---|---|---|
| `plate-1-wm2.stl` | WM-2 back (door side) + WM-2 front (controls side) | 165 × 109 × 17 mm | outer faces |
| `plate-2-ours-back.stl` | Our back half | 96 × 100 × 33 mm | outer face |
| `plate-3-ours-front.stl` | Our front half | 95 × 97 × 13 mm | outer face |

Plate 1 uses nearly the whole 180 mm bed but fits inside a 5 mm margin. Each of ours is
too big to share a bed with its other half, so ours takes two plates.

## How close is the WM-2

The outer size comes from walkman.land and the 1981 ad. Everything else was measured off the
orthographic fan render Michael sent. Its outline is 80:109 to within 0.1 %, so
it measures at 9.2 px/mm. Each feature was then checked against the walkman.land photos.
Expect **about ±1 mm**. None of it was measured on a real unit.

| Feature | Rev 1 | Rev 2 |
|---|---|---|
| Edges | Square | Back-face edges round 3 mm, front-face 2 mm, plan corners 2 mm |
| Buttons | Wrong angle (−35°) | +40°, square to the black diagonal. Positions overlay the render |
| Volume wheel | Guessed | Ø16 at the measured centre, rim showing through a notch in the top edge |
| Black ribbed zone | A flat triangle | Triangle plus the strip down the right edge, ribbed |
| Cassette window | Landscape (wrong) | Portrait, 31 × 70 mm, hubs and label window where they are |
| Door | Not shown | Hinge strip on the back, door line round the other three edges |
| Jacks | Near the back | Near the front, where they are |
| Edges' other features | A made-up "hotline" button | OPEN slider, DC IN jack, TAPE NORM/METAL switch, ribbed right side, top and bottom slots, hinge pins, rating plate outline |

**Not reproduced:** the SONY and WALKMAN II lettering, the door arrow, and the
VOLUME wedge. The real buttons stand about 1 mm proud. Here they are flush, because that
face prints against the bed. The real black/silver line is at 12.3 mm from the back; the
print seam is at 13.6, so the slots and the OPEN slider stay in one piece. The reference
shows the back edge on the hinge side a little rounder than the rest. That edge uses the same 3 mm.

**Edges that print face-down.** A rounded edge touching the bed would start almost flat and
sag. The lowest part of each round is replaced by a 45° chamfer tangent to it. You won't
see it, and nothing needs support.

## Settings

| | |
|---|---|
| Printer / nozzle | A1 Mini, **0.4 mm** |
| Material | **PLA Basic**, one spool per plate, no swaps mid-print |
| Profile | Stock 0.20 mm Standard. Default walls and infill are fine |
| **Supports** | **Off.** Nothing needs them. The edge keys have a 45° underside for exactly this reason |
| Orientation | **Leave it as loaded.** Every part already sits on its outer face. Rotating one onto its side would need supports |
| Brim | Not needed |

I have not sliced these. Bambu Studio will give you the time and grams. The masses below are
**solid-plastic upper bounds**, and a real print with infill will come in lighter.

## Opening and closing

The halves join the way I expect the real shell to. The back half has a thin **tongue**
around its rim, and the front half's **skirt** drops over it. Four small ridges on the tongue
click into grooves in the skirt: on ours, two on each long side; on the WM-2, two on the
top edge and two on the bottom, which keeps them clear of the side switches and ribs.

- **To close:** line up the halves and press around the edge until you feel the clicks.
- **To open:** at the middle of the bottom edge there is a **notch**. Put a fingernail or a
  coin in it and twist.

The clearance is 0.05 mm a side. That is rung 3 of the A1MINI-01 ladder, "snug, releases
with a twist" in your hand. The fit is what this plate tests about the joint, so please try
it several times.

## Adding weight

1. **Weigh each shell empty** on a kitchen scale, with both halves together.
2. Subtract that from the target, then divide by **5 g**. A US nickel is 5.000 g.
3. Spread the nickels around the cells of the coin grid in the back half, so the
   weight sits evenly. A dab of Blu-Tack stops the rattle.

| Mockup | Target mass | Shell (solid upper bound) | Roughly |
|---|---|---|---|
| WM-2 | 280 g, including its AA battery (1981 ad) | ≤ 71.5 g | **~42 nickels** |
| Ours | ~150 g **estimate** (`thermal-budget.md`) | ≤ 91.6 g | **~12 nickels** |

Because the printed shells will be lighter than the solid upper bound, expect a few more
nickels than the table says. Your scale is the real answer.

Coins and a lid that opens are fine for a seven-year-old, but not for a toddler who
might be nearby. Close it up before handing it over.

## What I'd like back

Answers in any form are fine. Photos help.

**Size, you and your child both:**
1. Holding each one, which feels more like "mine"? Which is too big, too thick or too heavy?
2. Ours is 42 mm thick against the WM-2's 29.5. Does it feel like a brick?
3. Can a thumb reach the top-edge keys while the same hand holds the player? Which key is
   hardest to reach?
4. Can your child find the middle key (it has a dimple) without looking?

**The joint:**
5. Did it click shut? Did it open from the notch without anything cracking?
6. Open and close it about ten times. Is it any looser at the end?
7. Is the seam line visible or catchy under a fingernail?

**The print:**
8. Did anything droop or string, especially under the edge keys and the thumbwheel?
9. The shells' actual weights (both halves together), and how many nickels you used.
