# Print packet SIZE-01 — how big should it be in the hand?

**Two life-size hollow mockups you can open, fill with coins and hold.** Three plates, A1 Mini.
Hardware Lead · rev 1, 28 Sep 2026 · sizing study, layout A

**Don't print this yet.** It is up for review first, as agreed. Look at `preview.png` and
`size-01-assembled.step` (sent to you directly; at 2.7 MB it is not kept in git, and
`python3 hardware/cad/sizing/mockups.py` rebuilds it), and tell me what to change.

---

## What this is

| | Outside | Where the numbers come from |
|---|---|---|
| **Sony WM-2 (1981)** | 80 × 109 × 29.5 mm | walkman.land, which matches the 1981 ad. Control positions are traced by eye from photos, so they are good to a few mm but not measured |
| **Digital-Tape, layout A** | 92 × 97 × 42 mm | `layout_study.py`: two cartridges stacked. Every part inside it is an **estimate** except the cartridge's working size |

The WM-2 is a **size reference, not a design reference**. It shows you what a real, loved,
pocketable player felt like at its weight. Ours is the honest size for what we plan to put
inside, with corner bumper pads and five raised edge keys roughed in. Those five keys are
**positions, not functions**; the control set is not decided.

## The plates

| File | Contents | Size on bed | Prints on |
|---|---|---|---|
| `plate-1-wm2.stl` | WM-2 back (door side) + WM-2 front (controls side) | 167 × 109 × 24 mm | outer faces |
| `plate-2-ours-back.stl` | Our back half | 96 × 100 × 33 mm | outer face |
| `plate-3-ours-front.stl` | Our front half | 95 × 97 × 13 mm | outer face |

Plate 1 uses nearly the whole 180 mm bed but fits inside a 5 mm margin. Each of ours is
too big to share a bed with its other half, so ours takes two plates.

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
click into grooves in the skirt, two on each long side.

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
