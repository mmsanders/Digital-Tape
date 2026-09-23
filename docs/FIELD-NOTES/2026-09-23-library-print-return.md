# Library print return — Michael's notes, 23 September 2026

**Recorded by:** Hardware Lead, verbatim from Michael, plus my diagnosis below.
**Status:** raw field observation. Nothing here is acceptance, qualification or a
measurement — no instrument was used and no criterion was run.

This is the WP04-01 plate coming back from the library. It is the first physical
return the project has ever had, so these notes outrank a lot of paper.

---

## 1. Michael's notes, as given

> The clasp test was a bit of a flop, the lids aren't labeled to match the boxes
> and the print came back from the library in a ziplock bag. But, I clipped things
> together and in general **A and Q were super tight and firm, but actually SO firm
> they couldn't be opened without breaking the plastic.** In general, if the lid
> needs to go with a particular box, **they both need to be labeled.**
>
> **Letters were a bit vague, let's make them larger** to make them clearer in the
> future.
>
> **The outer rim of the lid was too weak**, it was barely connected to the part
> that sits in the box. **It broke right off** when I tried to open the tighter
> clasps.
>
> **Really impressed with the strength of the clasp!** The hairline seam is pretty
> thick, **it would be nice if it was narrower.**
>
> We'll do future prototyping on this on the **A1 mini** unless we need something
> big. The A1 mini has better output quality. I have an **0.4 mm and 0.2 mm
> hotends, Bambu PLA Basic, PLA Matte, and PETG HF.**
>
> Let's push to get the cards **closer to the dimensions of a GameCube card.** And,
> I see the GameCube card has screws, so if they are **really small and flush** like
> this it could be ok. And maybe **necessary for screws to push for thinness?**
>
> **Button test doesn't work as printed.** We made a revised box to remove the
> intersection issue, but that box doesn't work either. We're going to need new
> buttons it seems, and maybe another new box, and maybe new everything?

Attempted fixes by a temp are in PRs #197 and #198; Michael reports both
unsatisfactory.

## 2. What the blind mapping says about A and Q

**Do not read this section to Michael before he ranks anything else on that
plate.** A and Q are the two *tightest* interferences in the sweep. His report —
"so firm they couldn't be opened without breaking the plastic" — is the sweep
working: the top of the bracket is past the usable range, which is exactly what a
deliberately over-wide bracket is for. The bracket's top end is now bounded by a
physical observation rather than by an estimate.

## 3. My diagnosis of the button failure

The button test could not have worked as printed, and the reason is geometric, not
a print-quality problem. In `hardware/cad/transport/latch.py`:

- the carrier stem occupies **y ∈ [−4.0, +4.0]** (`STEM_D = 8.0`, centred);
- the frame's bar channel is cut `.faces(">X")...rect(BAR_D + 0.6, BAR_H + 0.6)`
  centred on the frame's own Y centre, so it occupies **y ∈ [−2.8, +2.8]**.

The bar channel is therefore **entirely inside the stem**. The bar and the button
want the same volume. With the carrier in the frame the bar cannot pass; with the
bar in place the carrier cannot drop in. That is the intersection the temp tried
to remove.

But removing the intersection by moving the *box* cannot work either, and this is
why PR #198 also failed: the barb protrudes to **y = −4 − hook_depth**, i.e. it
lives *outside* the stem's −Y face. For the bar to be caught by the barb, the bar
must sit **in front of that face**, not on the frame's centreline. Any fix that
keeps the bar centred is moving the wrong part.

**So the mechanism was never assembled, and every number in the depth sweep is
untested.** Hook depth has not been shown to be the right variable, because
nothing has latched yet.

## 4. What I changed for the revised test

See `hardware/cad/transport/button_v2.py` and packet `A1MINI-BTN-02`. The short
version:

1. **The bar moved, not the box.** The bar channel is now in front of the stem
   face with a stated air gap, and a build-time assertion fails the plate if the
   bar volume and the stem volume overlap at all. The defect that produced this
   round cannot be re-shipped silently.
2. **One question, not eight.** Nothing latches yet, so a blind eight-point
   ranking is premature. The revised plate asks only: *does this mechanism latch
   and release at all?* Three depths, plus one no-barb control that must NOT
   latch.
3. **Open frame.** The engagement is visible and reachable from the front, so a
   failure can be seen rather than inferred, and a stuck part can be freed with a
   fingernail instead of a knife.
4. **Bigger letters**, 7 mm, on the cap top — Michael's note applies here too.

## 5. Carried forward, not addressed this round

| # | Item | Why not now |
|---|---|---|
| N-1 | **Label both halves** of every mated pair, always | A packet rule, belongs in the clasp packet's next revision |
| N-2 | **Lid outer rim broke off** — rim-to-plug junction is the weak point | Needs a shell geometry change (`cad/cartridge/shell.py`), not a button change |
| N-3 | **Seam too thick** | Same file; likely a lid/base lip parameter |
| N-4 | **Get closer to GameCube memory-card dimensions**; small flush screws acceptable, and possibly required to reach that thinness | This is a real scope change to ADR-105/ADR-119 — the clasp exists *because* screws were rejected. **Goes to PM**, not decided by me |
| N-5 | A and Q too tight to open without breaking | Bounds the sweep's top end; feeds the next clasp revision |

**N-4 is the significant one.** Michael is reconsidering screws, which the project
previously ruled out in Michael's own issue #6 and in Decisions 006 §2. A
GameCube-card thickness target plus flush micro-screws is a different cartridge
than the one ADR-119 specifies. I am recording it and escalating it rather than
acting on it.
