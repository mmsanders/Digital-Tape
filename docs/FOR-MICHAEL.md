# FOR MICHAEL

The question queue. Things that need your taste or your hands — nothing else blocks on you.

*Rewritten by the PM 4 Sep 2026 after the fourth review round (DRAFT-6).*

---

## Answers you asked for

### The printer — your four questions

**Does the A1 have an enclosure? Is it extra?**
No, and no — because Bambu doesn't sell one for this line. The A1 and A1 mini are open-frame by design, and the A1 mini's own FAQ says outright: *"We don't recommend enclosing the A1 mini."* That isn't a gap you'd be filling with an accessory; it's a design position.

**One thing I got wrong, and it matters.** I told you a home printer would give us PETG *and* nylon for the latch. **The A1 line does not run nylon.** Bambu supports *"PLA, PETG, TPU, and their corresponding support filaments"* and explicitly does not recommend *"ABS, ASA, PC, PA, and PET"* — `PA` is nylon — because the hotend tops out at 300 °C and the bed at 80 °C. PETG and TPU are still exactly right for a cartridge shell, and §"the clasp" below explains why nylon turns out not to be needed. But I asserted it and it was wrong.

**Can I iterate in one colour and print the final in multicolour?**
Yes, with one caveat worth designing around: **a tight fit tuned in one filament isn't guaranteed to fit in another.** Pigment loading changes how a plastic flows and shrinks, so a snap that's perfect in grey can be tight or loose in red — and that's between *colours of the same brand*, before you change brands. Multicolour also purges material at every tool change, so those prints are slower and waste more.

The fix is a design rule, not a workflow rule: **tune the clasp in the filament the real cartridges will use**, and make the retention come from a chamfer and a defined interference rather than a knife-edge fit, so a few hundredths of shrinkage gets absorbed instead of being fatal. That's in the Hardware Lead's brief.

**Can we outsource the important mechanism to better material and do everything else at home?**
Yes — SLS/MJF nylon from a print service is genuinely better for a small flexure than any FDM part, because it's isotropic and FDM fails along its layer lines. It's a normal split and it stays available to us.

**But I don't think we'll need it**, for the reason in the next answer. Hold it in reserve rather than budgeting for it.

**Verdict: the A1 combo is a good buy and the missing enclosure costs us nothing**, since everything we want to print is PLA, PETG or TPU. The combo's AMS Lite is a convenience for the final look, not a requirement for the engineering.

---

### The cartridge shell — you chose the clasp, and I think you can have it

**Your instinct is right, and here's the argument nobody had made yet: how often does a parent actually open a cartridge?**

Count it honestly. Once at assembly, to put the card in. Once more to load the *first* cartridge from a computer. After that — never, because **every cartridge after the first is loaded by the copy button**, which is the whole point of the device. So a cartridge gets opened **one to three times in its life**, not weekly.

That changes the problem completely. A clasp that has to survive thousands of openings is a hard fatigue problem in any printed plastic, and PLA creep would rule it out. **A clasp that has to survive five openings with margin is an ordinary fit problem**, and PETG handles it comfortably. The nylon we can't print is a solution to a problem we don't have.

So: **no screw, a continuous lip with a lead-in chamfer, and a tongue-and-groove seam on an edge chamfer** to hide the parting line and keep the two halves registered. I've asked the Hardware Lead for a stated cycle target — I proposed 20 openings with retention still within 20 % of first-cycle, roughly ten times the real life — plus the strain number that decides whether PETG creeps, and a plate of variants using the same blind-comparison process as the button packet.

**One thing I've added that you didn't ask for.** The opening feature has to be something **a child can't work**. A fingernail recess is a recess a five-year-old finds, and a loose microSD is a choking hazard. Two points of pressure at once, or a thin slot on the back face, is the shape to aim at.

### The sealed cartridge — feasible, and I recommend against it

Your own question is the one that decides it: *how would we get the card in in the first place?*

The firmware side works. The chip has USB device capability and mass-storage support is well-trodden on it — call it a work package of weeks, not a tweak. But:

1. **A sealed cartridge is assembled with the card inside, so when that card dies the cartridge is landfill.** A microSD in a child's hands will die. This is meant to be an object a family keeps.
2. **A computer will offer to format it.** Our format lives in a partition type no desktop recognises, and Windows volunteers to "fix" those. The person clicking Yes will be a parent trying to help.
3. **It buys almost nothing over the clasp.** The clasp already gives you the sealed look and the near-invisible seam. Sealing only adds that a *parent* can't open it either — and the parent is the one person who needs to.

**The clasp doesn't close this door.** If the assessment comes back saying a printed clasp can't hold a card safely at a size a child can hold, the trade changes and I'll bring it back. Until then, USB loading is a Phase 5 enhancement we can add later without touching the shell.

---

## Open

### Q-008 — How big is a cartridge, and does it have to look like a cassette?

**Needs:** your taste · **Blocks:** nothing — a working number is in use
**Why you and not us:** this is the one shell decision that is genuinely aesthetic

I have designed the clasp — the thing that holds the two halves of the cartridge together
without a screw, that you asked for. It works. But I had to pick an outside size to draw it, and
I picked **86 × 54 × 12 mm** for a reason that is defensible and not yours: 86 × 54 is a credit
card, so it is a shape a child's hand already knows, and 12 mm is about a cassette's thickness.

**The good news is that this is a free choice.** The maths that decides whether the plastic
survives has no length term in it — it depends on the wall section and how far the lip bends,
not on how big the box is. So changing the size moves how *hard* it is to open (bigger is
harder) and changes nothing about whether it lasts. You can pick this on taste and I will not
have to redo anything.

Three things worth knowing before you pick:

- **A real cassette is 100 × 64 × 12 mm.** If "it should feel like a cassette" matters more to
  you than "it should fit a small hand", that is the number, and it costs nothing.
- **Bigger is harder for a child to pull open**, slightly, because there is more lip to peel at
  once. Not by enough to change the safety case.
- **Smaller prints faster**, which matters while you are getting two library prints a month.

**Default if you don't pick:** 86 × 54 × 12 mm. Nothing waits on this — the clasp is
designed, the variants are on the plate, and the size can move afterwards.

---

### Q-007 — One more argument for the combo, from the shell design

**Needs:** nothing from you — this is an addendum, not a question
**Blocks:** nothing

The PM's printer answer above already covers the nylon correction, and I have nothing to add
to it. Two things came out of designing the clasp that bear on the same decision.

**TPU turns out to be load-bearing, not a nice-to-have.** The clasp uses a thin rubbery lip
round the inside of the seam. Its job is to soak up the variation between one print and the
next — it is exactly what stops a clasp being tight in grey and loose in red, which is the
caveat the PM flags above. Without it the design still works, but with much less room for the
plastic to come out slightly different on a different day.

**The library cannot print TPU and the A1 can.** So that part is on the critical path for the
clasp's tolerance and today we simply cannot make it. That is a more concrete argument for the
combo than "more materials would be nice".

**And the one place nylon does still bite is the transport latch, not the shell.** The shell
gets opened once or twice ever. The latch clicks every time somebody presses play, for years —
that one genuinely is a fatigue part. If the button plate comes back saying the latch is
marginal, we send **that one small part** to a print service in nylon and print everything else
at home. Exactly the split the PM describes holding in reserve, and it is about the price of a
takeaway.

---

### M-04 — The printer decision, now with the facts

**Needs:** your call and ~$450 · **Blocks:** nothing this week; the mechanism from about October

Everything above. **A1 combo, $449** in a March 2026 tracker — check current pricing. The library stays useful for exactly one thing: the WP-04 button packet, which is a single print whose answer is *comparative*, so it survives someone else choosing the settings.

**Default if you don't decide:** the library, two prints a month, and the latch work stretches into next spring.

---

### M-01 — The print packet still isn't ready

**Needs:** nothing from you yet · **Blocks:** WP-04 and everything mechanical

**Done as of 5 Sep — packet WP04-01 rev 4, and it is with you.** All five: merged `.stl`, the on-its-side variant dropped for a geometric one, and the card carries the plate size (150 × 149 mm), the time estimate (~1 h 40) and the orientation line. **The cartridge-shell variants are on the same plate** — together they are 1.6 h against the 6 h limit, so one print really is worth two. *(The PM's original text follows.)* Unchanged and still on the Hardware Lead: re-export as a single merged `.stl` (the library takes STL only, so `plate-FIXED.3mf` is void), drop the on-its-side variant, put the bounding box, time estimate and *"any orientation is fine provided all the parts get the same one"* on the card. I've asked them to put the cartridge-shell variants on the same plate if they fit inside six hours — one library print is worth two.

---

### M-02 — Vendor domains

**Needs:** two minutes in the environment settings · **Blocks:** the Hardware Lead's BOM work

The Hardware Lead found the pattern: **the allowlist matches exact hosts, so the `www.` prefix is the whole thing.** `www.nxp.com` and `www.lcsc.com` work; bare hostnames don't. Still blocked: **`www.ti.com`, `www.octopart.com`, `www.mouser.com`**, and DigiKey returns bot protection regardless. Add those three with the `www.`, plus `www.digikey.com` and `www.jlcpcb.com` in case they behave differently.

---

### M-03 — Approve parts order 1a

**Needs:** your wallet · **Blocks:** the bench build

Unchanged. ~$267 of the $600 budget. Order 1c stays cancelled.

---

### Q-001 — Format freeze (Phase 0 gate) — **held one round, by you, correctly**

**Status:** one verification round away

You held the signature and raised the bar, and it was the right call. The verifier's report met the letter of my condition — two blockers, neither in the sections I proposed freezing — and I brought you the condition instead of the signature. You declined it because eight *major* defects were still sitting in those sections.

Two of them justify the decision on their own: **reverse playback was off by one fixed-point unit**, so rewinding produced a smeared, duplicated sound and a reference recording taken from that draft would have frozen the defect as correct; and one function's signature contradicted its own document so no implementation could satisfy both.

**The standard is now: no blockers *and* no majors** in the sections being frozen. One more verification pass measures against it.

---

## Answered

- **Safety sign-off (issue #8):** you witness the loudness and thermal measurements; the Verification Lead separately audits the method and the raw numbers without being in the room. Two checks, neither of them the person who built it. The Hardware Lead now has to write results so a stranger can audit them.
- **Cartridge shell (issue #6):** clasp, no screw, near-invisible seam. Sealed-USB assessed and set aside as a later enhancement.
- **Q-006 library printer, Q-005 spending, Q-004 resume position, Q-003 the wall, Q-002 tape length** — all as previously recorded.

---

## This round, in one paragraph

The verifier found **15 defects in DRAFT-5: 2 blockers, 13 majors.** Both blockers were ways a child could lose a cartridge by ordinary use — copying a *blank* tape destroyed the tape you copied onto, and pulling a card at the wrong moment let the next ordinary action overwrite live audio. Both are closed. My own audit then found **37 more in my own draft, six of them blockers** — including one where **rewinding never reached the first frame of the tape**, and one where a cartridge could become permanently unreadable while its music was perfectly intact. Two of those six were introduced by my fixes for the verifier's findings, which is the pattern I'd watch if I were you: on this project the most dangerous text is whatever was written last, in a hurry, to close a hole someone just found.
