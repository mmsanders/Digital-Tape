# FOR MICHAEL

The question queue. Things that need your taste or your hands — nothing else blocks on you.

*Rewritten by the PM 5 Sep 2026 after the fifth review round (DRAFT-7).*

---

## The substitute verifier — yes, it will work until Monday

You asked for an extra hard look. I gave it one and it holds up. Four things it did that no previous pass did, or did unprompted:

- **It verified the three file hashes against the manifest before reviewing**, and said so. That's the whole point of the manifest and it's the first reviewer to use it that way.
- **It ran its own numerical traces on the audio arithmetic and then declined to file anything against it**, stating that explicitly. That's the harder judgement — a weak reviewer pads the list to look thorough.
- **It applied the raised freeze standard** — no blockers *and* no majors in the sections being frozen — without being told twice, and recommended against signing on that basis.
- **It updated its notes file**, which I'd asked the regular lead for three rounds running and hadn't got.

All nine findings are real; I checked seven of them against the documents myself.

**I did look specifically for it being soft.** Nine findings and zero blockers, against fourteen and fifteen with two blockers in the last two rounds, is exactly the shape a lenient pass would have. So I re-graded the two most severe-looking findings myself — and **major is right for both.** Neither loses data that wasn't already being destroyed on purpose. The grading is honest.

**The one thing I can't tell from a single pass is depth.** Nine findings on a draft that had just absorbed fifteen findings plus thirty-seven of my own fixes is a plausible number; it's also what a shallower pass would produce. So when the usual arrangement comes back: **have them review DRAFT-7 without reading the substitute's DRAFT-6 findings first.** Compare what each finds in the same text. One pass, and it answers a question we otherwise can't.

---

## The printing budget — M-04 is closed

Six plates a month changes the picture enough that I'm withdrawing the printer recommendation. Two things worth knowing:

**Six plates is not six designs.** The button plate already carries seventeen objects. Six plates at ten-plus variants each is a real iteration loop — call it **2–4 months for a working latch instead of 5–10.** That's the difference between a schedule and a wall, and it's why the printer isn't needed.

**But not choosing the material changes the clasp design, and this one matters.** I'd assumed PETG. With a single library spool — probably PLA, no colour choice — the relevant property isn't what I told you last time.

It's not how many times the clasp can be opened. You open a cartridge once or twice in its life, so cycling was never the risk. **It's that a clasp is closed 99.99 % of the time**, and PLA slowly relaxes under sustained load at room temperature. A lip held under tension for a year loses its grip — silently, on a cartridge in a kid's pocket.

So I've given the Hardware Lead a rule that makes the material stop mattering: **the clasp must not be under tension when closed.** The lip snaps past a shoulder and returns to near-zero strain; what holds it shut is the *shape* it's sitting behind, not stored spring force. Strain is spent only during the snap itself — twice, ever. A clasp built that way works in whatever the library has loaded, and still works if you win the filament argument later.

### Questions worth asking the printing guy on Monday

1. **Can I supply my own filament?** The single question that unlocks the most. If yes: PETG for the shells, and colour stops mattering.
2. **What material and brand is normally loaded, and does it change?** If it's consistent we can at least measure it once.
3. **Is the two-per-month limit per card or per household?** You're assuming per card — worth confirming before you rely on borrowed credits.
4. **Do you keep a slicer profile, or is it per-job?** If there's a saved profile, "supports off" can live there instead of on my card every time.
5. **Can I ask for a specific orientation if I explain why?** Not expecting yes. Worth knowing.
6. **Does a failed print consume the request?** Decides whether to risk one plate or split across two.

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
- **Smaller prints faster.** Less pressing now you have six plates a month rather than two,
  but it still buys room for more variants on the same plate.

**Default if you don't pick:** 86 × 54 × 12 mm. Nothing waits on this — the clasp is
designed, the variants are on the plate, and the size can move afterwards.

---

---

### M-01 — The plate is ready, but settle two things on the card first
**Needs:** ten minutes with the card · **Blocks:** the library trip

The regenerated `plate.stl` is **sound and cleared** — watertight, 17 separate manifold parts, 138 × 137 mm, nothing off the bed, no supports needed, ~3–4 hours and ~64 g. Every fault in the old broken file is gone. Full check is in the project as `decisions/pm-wp04-plate-stl-verification.md`.

**Two things to check before it goes:**

**Three of the nine buttons are the same part.** `D`, `M` and `H` are identical solids — I verified it by exact geometry comparison. If the card says that's a deliberate repeat, it's good design: a hidden control that tells us whether your ranking is real signal or noise, and you should know it's there so you don't think it's a mistake. **If the card doesn't say so, the generator collapsed three levels into one** and you'd be ranking three identical objects against each other. That wastes three of nine slots.

**Four clasp variants but only two mating halves**, and they're identical. You can build two cartridges at a time and must reuse the same halves for all four — so wear on the shared half gets confused with whichever variant you test last. Either the card tells you the test order, or the next plate carries four halves. With six prints a month, four halves.

**One line for the card that matters more than the others: SUPPORTS OFF.** Each button has a 6 × 4 mm bore, 14 mm deep, opening down onto the bed. It needs no support, but a "supports everywhere" *or* "on build plate only" setting fills it — and support material 14 mm down that hole is not removable, sitting directly on the flexure whose stiffness the whole packet measures. It's the one setting that can silently waste the trip.
---

### M-02 — Vendor domains

**Needs:** two minutes · **Blocks:** the Hardware Lead's BOM work · *unchanged*

The allowlist matches exact hosts, so the `www.` prefix is the whole thing. Still blocked: **`www.ti.com`, `www.octopart.com`, `www.mouser.com`**, plus `www.digikey.com` and `www.jlcpcb.com`.

---

### M-03 — Approve parts order 1a

**Needs:** your wallet · ~$267 of the $600 budget · *unchanged*

---

### Q-001 — Format freeze — **held a second round**

**Status:** the verifier found six major defects in the sections we were about to freeze

Nine findings, no blockers, but six of them landed in the freeze-candidate sections — so the standard you raised last round did its job for the second time. The most consequential:

- A **shared counter every write depends on was never actually defined**, so two implementations could disagree about which version of a cartridge is current.
- An invariant required a counter to advance on every operation, when **ordinary recording doesn't touch it** — so anyone testing that rule literally would have failed every recording the device makes.
- A test I wrote last round **started from a state the rules forbid reaching**, so it could never have been run.

All nine fixed. **Nothing is blocked on you** — this is the verifier and me converging, and it is converging: fifteen findings two rounds ago, nine now, none of them blockers.

---

## Answered

- **M-04, printer:** closed. Six plates a month is enough. Not buying.
- **Cartridge shell (#6):** clasp, no screw. Now with a material-independent design rule (above).
- **Safety sign-off (#8):** you witness, verifier audits method and raw data. **And this round the Hardware Lead caught that I'd announced that audit in a memo and never written it into the spec** — `acceptance.md` contained the word "audit" zero times. Fixed, and it now also demands stated measurement uncertainty, because your thermal margins are tight enough for the uncertainty to decide pass or fail.
- Q-002 through Q-006 as previously recorded.

---

## PR status, since you asked

| PR / issue | Verdict |
|---|---|
| `Digital-Tape` **#22**, DRAFT-6 bundle | **Merged, correctly.** Verified byte-exact on `main` |
| `Digital-Tape` **#20**, engine read path + allocator | **Do not merge; keep as draft.** Two holds: the verifier's tests aren't on `main` yet, and it's three revisions behind. **Not stale — parked.** I've asked for it to be rebased and reconciled rather than extended |
| `Digital-Tape` **#23**, missing audit language | **Valid.** Fixed in DRAFT-7; close it when the bundle lands |
| `Digital-Tape-Verification` **#1** | **Merge it.** See below |

**One thing I found while checking:** the verification repo's `main` only carries findings up to DRAFT-3. The DRAFT-4, DRAFT-5 and DRAFT-6 passes all live on branches, and PR #1 has been open since 3 September still titled DRAFT-5.

That's the **same failure I built a mechanism against two rounds ago** — `main` publishing something stale while the real work sat on a branch — in the other repository, which I hadn't thought to check. Findings now land on that repo's `main` too.

---

## This round in one paragraph

The verifier found nine defects in DRAFT-6, none of them blockers, six in the sections we were about to freeze. My own audit then found **27 more in my own draft, two of them blockers — and both were in text I wrote to fix this round's findings.** One had a promote operation reusing the same version number for four different writes, which would have left a cartridge unmountable and unrecoverable with all its music intact but unreachable. That's three rounds running where the blockers were in the fixes rather than the original text, and I think the reason is simple: **a fix is the only text in a document nobody but its author has ever read.**
