# Print packet SIZE-01 — how big should it be in the hand?

**Two life-size hollow mockups you can open, fill with coins and hold.** A1 Mini.
Hardware Lead · rev 4, 28 Sep 2026 · sizing study, layout A

**Plate 0 is done: coupon 3 (65°) won, and the WM-2 is now set to it.** Plate 1 can go now,
at coupon 3's quality. Plate 0b (optional, small) tests two ways to make the round smoother
before you do. Ours (plates 2 and 3) is still up for discussion.
`preview.png` shows both. `size-01-assembled.step` is about 5 MB, so it is not kept in git;
`python3 hardware/cad/sizing/mockups.py` rebuilds it.

**Rev 2 reshaped the WM-2's outer surface from measurements, not by eye.** **Rev 3** gives
it the reference's much softer back edges. **Rev 4** sets the edge limit to 65° from plate 0
and adds plate 0b. See "How close is the WM-2" and "Edges" below.

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
| `plate-0-edge-coupon.stl` | Four copies of the WM-2's hinge-side back corner, one per overhang limit. See "Edges" | 61 × 61 × 9 mm | outer face |
| `plate-0b-edge-smoothing.stl` | Optional. The same corner four ways, to test smoothing (marked with a bar). See "Edges" | 61 × 61 × 9 mm | outer face |
| `plate-1-wm2.stl` | WM-2 back (door side) + WM-2 front (controls side). Sent directly: at 1.3 MB it is rebuilt by the script, not kept in git. `wm2-tray.stl` + `wm2-lid.stl` are the same two parts | 165 × 109 × 17 mm | outer faces |
| `plate-2-ours-back.stl` | Our back half | 96 × 100 × 33 mm | outer face |
| `plate-3-ours-front.stl` | Our front half | 95 × 97 × 13 mm | outer face |

Plate 1 uses nearly the whole 180 mm bed but fits inside a 5 mm margin. Each of ours is
too big to share a bed with its other half, so ours takes two plates.

## How close is the WM-2

The outer size comes from walkman.land and the 1981 ad. Everything else was measured off the
orthographic fan render Michael sent. Its outline is 80:109 to within 0.1 %, so
it measures at 9.2 px/mm. Each feature was then checked against the walkman.land photos.
Expect **about ±1 mm**. None of it was measured on a real unit.

| Feature | Rev 1 | Rev 2 / 3 |
|---|---|---|
| Edges | Square | Rev 2: 3 mm back, 2 mm front. **Rev 3: measured profiles.** The back door's long edges have a soft round about 6 mm deep (rounder on the hinge side), its short ends about 2 mm; the front edges are 2 mm; plan corners 2 mm |
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
print seam is at 13.6, so the slots and the OPEN slider stay in one piece.

## Edges: the one place printing and moulding differ

Each profile was measured from the reference's edge-on views, one pixel row at a time.
Both big faces print against the bed, so each edge round starts at the bed. The real round
flattens out into the face. That lowest part overhangs further than a printer can build
without support; each new layer would have to reach out almost a millimetre past the one
below it.

So the round is kept exactly as measured down to the height where it becomes steeper than
a limit angle. Below that it runs straight at the limit angle to the bed, as a tangent line,
so there is no crease. At **65°**, the limit now set, that straight part is only about the
bottom millimetre of a round about 6 mm deep. The rest is the measured curve. **Nothing needs
support, and no injection moulding is needed for this shape.** A moulded part would get the
last millimetre too, and that is the whole difference.

**Plate 0 settles the limit.** Four copies of the hinge-side back corner, the roundest
edge on the WM-2, with the real ribs:

| Dimples on the face | Limit | Expect |
|---|---|---|
| 1 | 45° | Cleanest, a visible bevel at the bottom |
| 2 | 55° | The default before plate 0 |
| 3 | 65° | Closer to the real curve, may be rough underneath |
| 4 | none, the true curve | **The control.** It should droop or curl at the bed edge; if it doesn't, the limit is costing us nothing |

**Result, 28 Sep (Michael):** "#3 is the cleanest overall. #4 prints but the outside of the
fillet is getting pretty bumpy and uneven." The control failed the way it should, so the
limit is doing real work. **The WM-2 is now set to 65°.**

In Michael's photos, the bumps sit where the ribs cross the flattest part of the round, and
#4 has small beads along its bed edge. On that nearly flat part, each groove is cut into a
surface that is almost horizontal, so every layer steps in and out by the groove depth on
top of the overhang.

**Plate 0b (optional): can the round be smoother?** Same corner, marked with a **bar**
beside the dimples so it can't be mixed up with plate 0. Two changes are tested together:

- **Thin layers through the round (slicer only).** Each layer then has to reach out less
  far past the one below. In Bambu Studio, right-click each part → **Height range
  Modifier**, 0 to 7 mm, layer height **0.08 mm**. The **Variable layer height** tool
  does the same job if the menu differs in your version. Use the same setting on plate 1
  if 0b looks better.
- **Ribs faded (model).** Grooves are left off where the round is flatter than 50°, the
  bottom ~2 mm of its height. That is 3 to 5 grooves.

| Bar + dimples | Limit | Ribs |
|---|---|---|
| 1 | 65° | faded |
| 2 | 65° | full, as plate 0 #3 |
| 3 | none, the true curve | faded |
| 4 | none, the true curve | full, as plate 0 #4 |

Put each next to its plate 0 twin (2 beside #3, 4 beside #4) and you see what thin layers
alone did. Compare 1 with 2, and 3 with 4, and you see what fading the ribs did. If 3 is
clean, the true curve prints and I drop the limit. I have not printed any of this. These
are expectations, not results.

## Settings

| | |
|---|---|
| Printer / nozzle | A1 Mini, **0.4 mm** |
| Material | **PLA Basic**, one spool per plate, no swaps mid-print |
| Profile | Stock 0.20 mm Standard. Default walls and infill are fine. Optional: 0.08 mm layers from 0 to 7 mm (see plate 0b) |
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
