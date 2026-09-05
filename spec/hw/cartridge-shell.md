# Cartridge shell — the clasp, the seam, and what opens it

**Owner:** Hardware Lead · **Consumed by:** WP-24, WP-23, WP-25 · **Status:** assessment
**Revision:** 0.1, 5 Sep 2026 · **Answers:** PM Decisions 006 §2 and §3

<!-- CHANGES: every revision adds a block here. -->

## CHANGES

### 0.1 — 2026-09-05
First issue. Answers the five asks in PM Decisions 006 §2, gives a week estimate for the
USB-MSC package asked for in §3, and records the material correction: **the A1 line does not
run nylon**, so the "print the latch in nylon at home" path in Decisions 005 §3 does not exist.

---

## 0. What this says, in one page

**Michael can have the clasp.** The PM's reframing is the whole reason, and it is correct: a
cartridge is opened **one to three times in its life**, because every cartridge after the first
is loaded by the device's own copy button. A snap that must survive thousands of cycles is a
fatigue problem no printed material solves. A snap that must survive five is an interference
fit, and PETG does it with margin to spare.

Five answers, in the order asked:

| # | Ask | Answer |
|---|---|---|
| 1 | Cycle target | **20 cycles at ≤ 20 % force loss, accepted** — and it is the *easy* criterion. §1 adds the three that can actually fail |
| 2 | Retention geometry | **Continuous seam, discontinuous engagement.** Perimeter lip is right about load and wrong at the corners. **0.75 % peak strain, 0.086 % at rest** |
| 3 | The seam | Tongue-and-groove on a 1.0 mm 45° chamfer. Achievable: **a 0.15–0.25 mm line with a step of up to ±0.2 mm**, both hidden by the chamfer. Not invisible — say so to Michael |
| 4 | Opening feature | **A 0.9 mm blade slot on the back face.** And the honest part: retention force does not separate a child from an adult. *Having nothing to grip* does |
| 5 | TPU | **Load-bearing, not an experiment.** A bending lip, not a compressed gasket — the shape is the whole difference. It is also where the print tolerance goes |

**And one correction that changes the plan, not the buy:** the A1 line runs PLA, PETG and TPU
and **does not run nylon** (§9). Everything above is designed for PETG, which is what the
printer actually gives us, so nothing here depends on the material we cannot have.

**On the sealed cartridge (§10): I agree with the PM's recommendation against it**, and the
trigger they named for reconsidering — *"if a printed clasp cannot hold a card safely"* — is not
met. My estimate for the USB-MSC package if it is ever wanted is **6 weeks ± 2**.

> **Every material property in this document is an estimate.** No vendor egress in this
> environment has reached a filament datasheet, so modulus, permissible strain and friction are
> from general knowledge of the polymers and are marked EST. **The PM's note in Decisions 006
> applies to me too**, and the way I have handled it is to make the plate measure what I have
> guessed: the interference sweep in §8 is bracketed so that if my stiffness numbers are wrong,
> the ranking says so.

---

## 1. The cycle target

**PM's proposal: 20 open-close cycles with retention force still within 20 % of first-cycle.
Accepted, unchanged.** Ten times the realistic life is the right margin for an object handled
by children, and I have no argument for moving it.

**But it is the criterion this design cannot fail, and I would rather say that than bank it.**
The reason is §4: the clasp holds **zero strain at rest**. The bead seats fully in its groove
and the wall returns undeflected, so 20 cycles means twenty one-second excursions to 0.75 %
strain, spread over years. That is not a fatigue duty in any thermoplastic — PETG's fatigue
knee is orders of magnitude beyond it. The test takes Michael four minutes and it will pass.

A criterion that cannot fail is not a gate, it is a receipt. So three more, and these are the
ones with teeth:

| # | Criterion | Why it can fail |
|---|---|---|
| **S-1** | 20 open-close cycles, retention force within 20 % of first cycle | PM's. Accepted. Expected to pass easily |
| **S-2** | **90 days closed at 23 °C, and 90 days closed at 45 °C**, then S-1's force within 20 % | The cartridge spends ~100 % of its life closed. This is the one that finds creep, and the 45 °C leg is a cartridge left in a car |
| **S-3** | **1.0 m drop onto hard floor, closed, six faces and four corners, card retained every time** | A drop is not a cycle and no cycle count catches it. See below |
| **S-4** | **A 30 N pinch held 10 s does not open it**, applied at the seam with no tool | The child-access criterion, and the only one that is safety-critical |

### Why S-3 is not theatre

A 25 g cartridge dropped 1.0 m arrives with about 0.25 J. Stopping in half a millimetre of
local deformation puts a peak contact force in the hundreds of newtons — **above the joint's own
pull-apart force**. The joint does not see all of that (most of it goes into the corner that
lands, not into separating the halves), but the arithmetic is close enough that the outcome is
not predictable from the static numbers, and a cartridge that springs open on impact scatters a
microSD across the floor. That is the choking hazard ADR-105 exists to prevent, arriving by a
route the cycle test does not look down.

### Why S-2 names a temperature, and one finding that goes with it

PETG's heat-deflection temperature is around **70 °C (EST)**. A closed car in summer reaches
that. So:

> **Finding for the PM and for Michael:** a PETG cartridge left on a dashboard may deform, and
> a deformed cartridge is one whose clasp no longer holds. This is not a reason to change
> material — every printable option except the ones the A1 cannot run has the same problem — but
> it belongs in whatever the family is told, and it belongs in WP-25's abuse plan.

S-2's 45 °C leg is deliberately *below* that and is a creep test, not a survival test. The
survival test is WP-25's.

### The audit standard applies here

Decisions 006 §5 changes what "done" means for the safety measurements: **witnessed by Michael,
independently audited by the Verification Lead from the method and the raw data.** S-4 is
safety-critical, so it is written to that standard from the start rather than retrofitted —
procedure, instrument and revision, raw readings, derivation. A 30 N pinch is measurable with a
$10 luggage scale and a jig, which is the point of choosing a number a scale can read.

---

## 2. Retention geometry

**The PM's read is right about the load and wrong about the corners, and the fix keeps both
halves of what they wanted.**

A continuous perimeter lip spreads the load and gives the near-invisible seam. But a
**rectangular** box cannot open at a corner by bending — the only path is stretching the
material in tension, which is effectively rigid, so a lip that runs through the corners does not
release there, it breaks there. Discrete cantilever snaps avoid that and give up the seam.

So: **the seam is continuous and the engagement is not.** The tongue-and-groove parting line
runs the entire perimeter — that is what hides it and what registers the halves — and the
interference that actually retains lives only on the two long walls, stopping short of each
corner. Michael sees an unbroken line. The mechanism sees two long, compliant runs and four
rigid corners doing the alignment.

<!-- BEGIN GENERATED: clasp_geometry -->
| Parameter | Value | Why this number |
|---|---:|---|
| Cartridge outer | 86 × 54 × 12 mm | **Michael's call, and the analysis does not depend on it** — see the note below |
| Nominal wall | 2.0 mm | Stiffness and drop survival everywhere except the run |
| Retention wall | **1.2 mm** | Thinned local to the run. Strain is linear in this |
| Cantilever span | 6.0 mm | Floor to seam. Half the shell height; strain goes as its square |
| Interference | **0.30 mm** total | Shared: 0.150 mm per half |
| Tolerance on it | ±0.15 mm | Two separate prints, plus colour-to-colour shrink |
| Engaged run | 68 mm per long wall | 86 mm less 9 mm of corner relief each end |
| Lead-in chamfer | 25° from the pull axis | Closing ramp; 0.64 mm tall for a 0.30 mm bead |
| Retention face | **40° from the pull axis** | Opening ramp; self-locks past **70.7°**, so this keeps half the range |

**Strain contains no length term.** `ε = 3yt/2a²` — wall section and deflection only. So 86 × 54 can become anything Michael likes: the outer dimensions move the *forces*, which are a comfort question, and leave the *strain* untouched, which is the materials question. That is the one decision in this document that can be taken on taste without reopening anything.

| Strain in PETG | Deflection per half | Peak strain | Against 2.0 % permissible |
|---|---:|---:|---|
| Interference at minimum | 0.075 mm | **0.37 %** | 5.3× |
| **Nominal** | 0.150 mm | **0.75 %** | 2.7× |
| Interference at maximum | 0.225 mm | **1.12 %** | 1.8× |
<!-- END GENERATED: clasp_geometry -->

**Why the wall is thinned only over the run.** The thinning *is* the cantilever: 1.2 mm over the
full 6.0 mm from floor to bead. Everywhere else the wall stays 2.0 mm for stiffness and for
S-3. The tempting simplification is to thin the whole rim so the lid's tongue can be a plain
rectangle — and it moves the flexing span from 6.0 mm to 3.2 mm. Strain goes as the square of
the span, so **0.75 % becomes 2.6 %**, past PETG's permissible and far past PLA's. That version
prints, assembles, and feels correct on the bench. `hardware/cad/cartridge/test_shell.py` checks
the wall section from the floor to the bead for exactly this reason.

---

## 3. Forces, and the question the PM did not ask

<!-- BEGIN GENERATED: clasp_forces -->
| Action | Force | Who does it |
|---|---:|---|
| Pull the halves apart, whole seam at once | **124 N** | nobody — see below |
| Press closed, whole seam at once | 72 N | nobody — closing rolls too |
| Lever one 14 mm span open with a blade | **12.7 N** | the parent |
| Press one 14 mm span closed | 7.4 N | the parent, rolling along |

**The tool does not beat the latch by force, it beats it by unzipping it.** The ratio is **10 : 1** — because deflection force is linear in engaged length, and a blade in the slot deflects 14 mm of run while a brute pull has to deflect all 68 mm of both walls at once. Every millimetre of length you add to the cartridge makes the brute path harder and leaves the tool path exactly where it is.

### Why the pull force is not the safety argument

| | Force available | vs the 124 N pull |
|---|---:|---|
| Five-year-old, pinch on a flush 12 mm slab | ~20 N | **6.2× margin** |
| Five-year-old, two-handed grip on something to hold | ~80 N | 1.5× margin |
| Adult, two-handed pull | 200 N+ | none — an adult can force it |

Read the second row before the first. **Retention force does not separate a child from an adult** — a determined seven-year-old with something to grip is inside a factor of two of this joint, and I am not going to design a number that pretends otherwise. What separates them is that there is *nothing to grip*: the seam is flush, there is no lip, no recess and no proud edge anywhere on the shell, so the only force a child can bring is a pinch on a smooth 12 mm slab. That is the first row, and it is the one with the margin in it.

**The consequence for the design is a rule, not a number:** any feature that gives a fingernail or a fingertip purchase on the parting line converts row 1 into row 2 and spends the entire safety margin. That rules out the recessed thumb-notch that every battery cover has, and it is why the opening feature is a slot for a blade.
<!-- END GENERATED: clasp_forces -->

---

## 4. Does PETG creep? No, and here is the number

<!-- BEGIN GENERATED: clasp_creep -->
The question PM Decisions 006 §2 asks — *does PETG creep at the deflection you chose* — has a better answer than a margin, which is that **the design does not hold the deflection**. The bead seats fully in the groove and the wall returns to undeflected. The opening strain exists for about a second, once or twice in the cartridge's life.

What is held for years is only the TPU lip's preload, and this is what it costs:

| | Value |
|---|---:|
| TPU lip section | 0.8 mm thick × 2.0 mm tall, deflected 0.2 mm |
| Perimeter preload | 22 N |
| Camming component per long wall | 4.2 N |
| **Sustained strain in the PETG wall** | **0.086 %** |
| Opening strain, for comparison | 0.75 % |
| Creep threshold where PETG starts to matter | ~0.5 % (EST) |

**0.086 % is 6× below the threshold**, and it is the only sustained figure in the design. The reason the TPU is a bending lip rather than a compressed gasket is arithmetic: the same TPU as a 1 mm gasket squashed 0.2 mm over this perimeter develops several hundred newtons and would hold the shell open. In bending it develops 22 N. **Same material, same displacement, two orders of magnitude apart** — the compliance has to come from the shape.

**The TPU is also where the tolerance goes.** The PETG bead gives *retention* — a hard stop at a defined interference. The TPU lip gives *preload* — it takes up the ±0.15 mm of print variation so the joint does not rattle at the loose end of the stack and does not bind at the tight end. Splitting those two jobs across two materials is what makes a printed clasp survive a colour change, which is the failure PM Decisions 006 §1 warns about.
<!-- END GENERATED: clasp_creep -->

---

## 5. The seam, in millimetres

The PM asked what is achievable. This is the honest figure, and it is short of invisible.

| | Value | Source of it |
|---|---:|---|
| Tongue | 0.8 mm wide × 1.0 mm tall | — |
| Groove | 1.0 mm wide × 1.1 mm tall | 0.10 mm clearance per side — one nozzle-tolerance unit, so it prints without fusing |
| Parting-line chamfer | **1.0 mm at 45°**, split 0.5 mm to each half | The feature that hides everything below |
| Visible line width | **0.15 – 0.25 mm** | Layer height; the seam lands on a layer boundary |
| Lateral step across the seam | **up to ±0.20 mm** | Two independently printed parts, each ±0.1 mm in XY |

**The chamfer is what makes those numbers acceptable.** A 0.2 mm step on a flat face is a ridge
that catches the light from across a room. The same step halfway down a 45° chamfer reads as
part of the chamfer. This is the difference between "you can see the join if you look for it"
and "there is a line on it".

**Tell Michael it is a line, not nothing.** "Near-invisible" is achievable at arm's length in a
matte filament; it is not achievable under a lamp, and promising otherwise sets up a
disappointment on the first print rather than a pleasant surprise.

The tongue-and-groove also does the registration, which is the PM's third point and the reason
to prefer it over a butt joint: **the clasp is not also doing alignment.** The two jobs are in
different features, so a tolerance problem in one does not present as a failure of the other.

---

## 6. The opening feature

**A 0.9 mm × 12 mm slot, 2.5 mm deep, on the back face, offset from the corner.**

Take the requirement in the order it actually binds:

1. **Nothing on the shell may offer a fingernail purchase.** No recess, no lip, no proud edge,
   no thumb-notch. §3 shows why: purchase is what converts a 20 N child into an 80 N child, and
   it spends the entire margin. This rules out the battery-cover idiom every consumer product
   uses.
2. **The parent needs a low-force path**, and it comes from geometry rather than from strength:
   a blade in the slot deflects one 14 mm span, where a pull has to deflect both full runs at
   once. That is the **≈ 10 : 1** ratio in §3. The tool does not overpower the latch; it unzips
   it.
3. **The slot sits mid-run, not at a corner**, because the corners are the rigid part. A slot at
   a corner would be a slot that does not work.
4. **0.9 mm takes a spudger, a guitar pick or a butter knife, and not a fingernail.** A nail is
   about 0.5 mm and would enter — and it is flexible, so it cannot develop 13 N through a 0.9 mm
   gap without folding. The width is chosen for stiffness, not for thickness.

**What I am not proposing, and why.** The PM's alternative — two points of pressure at once —
is a good instinct that does not survive the dimensions. Squeezing the two short ends to bow the
long walls outward is a real mechanism, but a five-year-old's hand spans about 130 mm and the
cartridge is 86 mm, so it is a motion a child *can* make. The slot needs an object a child does
not have in hand, which is a better filter than a motion a child cannot make.

**S-4 is what proves this**, and it is deliberately falsifiable: 30 N of pinch for 10 seconds
with no tool. If it opens, the geometry is wrong and this section is wrong with it.

---

## 7. The TPU lip

<!-- see §4 for the arithmetic; this section is what it means -->

The PM offered TPU as "worth one experiment". **It is worth more than that, and it is doing a
job nothing else in the design can do.**

The PETG bead gives **retention**: a hard stop at a defined interference. What it cannot give is
tolerance absorption — 0.30 mm of interference with ±0.15 mm of print variation is a joint that
is either loose or tight depending on the day and the colour, which is precisely the failure
Decisions 006 §1 warns about when a filament changes.

The TPU lip gives **preload**: about 22 N spread round the perimeter, taking up the slop so the
joint does not rattle at the loose end of the stack and does not bind at the tight end. Two
jobs, two materials, and the tolerance lands on the one that has 400 % elongation to spend.

**The shape is the entire trick, and it is worth stating because the obvious version fails.** A
1 mm TPU gasket squashed 0.2 mm over this perimeter develops several hundred newtons — it would
hold the shell open. The same rubber as a **thin lip in bending** develops 22 N. Same material,
same displacement, two orders of magnitude apart.

**It cannot be printed at the library.** Shasta runs PLA only, and a merged STL carries one
material for every part in it. So `tpu-lip.stl` ships beside the plate and waits for a machine
that runs TPU — which is an argument for the A1 combo that is more concrete than "more
materials would be nice": **this part is on the critical path for the clasp's tolerance, and
today we cannot make it.**

---

## 8. The variant plate

Same process as WP-04, deliberately: shuffled letters unrelated to the parameter, a shared
mating part as a control, and *"they all felt about the same"* as a first-class answer
(ADR-104). **It shares WP-04's plate**, per Decisions 006 §4 — one library trip, two
experiments, 1.6 h of print against a 6 h limit.

<!-- BEGIN GENERATED: clasp_sweep -->
Coupon: **62 × 28 × 12 mm**, a real long-wall run (44 mm engaged) with both corner relieves, at full section. Not a cartridge — a cartridge does not fit on the plate beside WP-04 and the coupon tests the thing being swept.

**The plate prints in PLA, and the design is for PETG.** That is not a flaw in the packet, it is the bracket. PLA is roughly twice as stiff and half as extensible, so the same geometry that is comfortable in PETG is at PLA's limit — which means **the top of this sweep is expected to crack**, and that is a useful result rather than a wasted part.

| Interference | Strain | vs PLA 1.0 % | vs PETG 2.0 % | Brute pull | **Lever** | Expectation |
|---:|---:|---|---|---:|---:|---|
| 0.15 mm | 0.37 % | ok | ok | 73 N | **12 N** | too loose — should rattle or fall open |
| 0.25 mm | 0.62 % | ok | ok | 122 N | **19 N** | candidate |
| 0.35 mm | 0.87 % | ok | ok | 171 N | **27 N** | candidate, at PLA's limit |
| 0.45 mm | 1.13 % | **over** | ok | 220 N | **35 N** | **expected to crack in PLA**; comfortable in PETG |

**The lever column is the one that matters for the packet**, because it is the force Michael's hand actually applies. It runs 12–35 N across the sweep — a light push to a firm one on a blade — so **every variant is openable by hand, including the one expected to crack.** If the brute-pull column were the operating force, the top two variants would be untestable and the plate would be worthless.

The brute-pull column is the coupon in PLA, not the cartridge in PETG, and it is here so that nobody reads a cartridge number off it later. The coupon's run is shorter and its material is stiffer; the two effects push opposite ways and the number means nothing except relative to the other rows.
<!-- END GENERATED: clasp_sweep -->

**Two lids, and they are the control.** One geometry mates every base, so the lid is shared
across four sequential tests and will wear. If Michael's ranking tracks *which lid he used*
rather than which base, the sweep is measuring wear on the shared part and not interference —
the same trick as WP-04's `D`/`H` bed controls, aimed at a different confound.

**What each result means, decided in advance** so the next plate goes out without another round
of thinking:

| If the plate says… | Then… |
|---|---|
| A clear winner, lids do not matter | Print that interference in PETG and run S-1 to S-4 |
| The ranking tracks the lid | The shared part is wearing. Print four matched pairs next time and accept the cost |
| Nothing holds, including Q | My stiffness estimate is too low. Re-bracket upward and get a filament datasheet before the next plate |
| Everything holds, including N | My stiffness estimate is too high, and the good news is that the interference can shrink until it is inside FDM's comfortable range |
| Q cracks and A does not | The PLA permissible-strain estimate is about right, which also calibrates the PETG number by the same reasoning |
| They all feel the same | Interference is not what the hand reads. Sweep the retention angle instead, at fixed interference |

---

## 9. Materials — the correction, and what it does and does not change

**Decisions 005 §3 told Michael a home printer would give us PETG and nylon. It will not.** The
A1 line officially runs **PLA, PETG, TPU and their support filaments**, with a 300 °C hotend and
an 80 °C bed, and explicitly does not recommend ABS, ASA, PC, **PA** or PET. PA is nylon.

| Where nylon was assumed | Now |
|---|---|
| `docs/PACKAGES/WP-04.md` A-4, "1000 cycles in the final material (MJF nylon or PETG)" | **PETG from the A1**, or MJF nylon **from a service bureau**. Those are different procurement paths and the document now says which |
| `docs/REVIEW/hardware-lead.md` round 1, "the production latch bar will be PETG, ABS, nylon or an insert" | PETG or an insert. ABS and nylon both need a machine we are not buying. **The review log is append-only and has not been edited** — the correction is here and in round 9 |

**It changes less than it sounds like it should**, for the reason in §0: this shell is designed
for PETG throughout, and the PM's own reframing is why. Nylon's advantage is fatigue life in a
small flexure, and a part that flexes twenty times in its life does not need fatigue life. **The
material we cannot print is the solution to a problem this design does not have.**

**Where it does still bite: WP-04's latch.** That mechanism actuates on every press for years,
so it *is* a fatigue part, and WP-04's A-4 criterion (1 000 cycles in the final material) may
still want MJF nylon from a bureau. Outsourcing one small part while the rest prints at home is
a normal split and the PM already sketched it. **That decision belongs to WP-22, after WP04-01
says which geometry won** — printing the wrong shape properly is worse than printing the right
shape badly.

**One thing to design around regardless** (Decisions 006 §1): a press fit tuned in one filament
is not guaranteed to fit in another. Two consequences, both already in this design:

- **Tune in the production filament**, and re-verify after any colour change. It is on the card.
- **Retention comes from a feature with tolerance in it** — a lead-in chamfer and a defined
  interference backed by a TPU preload — not from a knife-edge fit. §7.

---

## 10. The sealed cartridge — my estimate, and my agreement

**I agree with the PM's recommendation against it.** The trigger they set for reconsidering was
*"if the clasp assessment comes back saying a printed clasp cannot hold a card safely at a size
a child can hold."* It does not: §3 puts a child's realistic pinch at a 6× margin, and the
failure mode that worried me most (S-3, the drop) is a problem the sealed version has *equally*,
because sealing does not stop a shell from splitting — it only stops it from being repaired
afterwards.

I would add one reason to the PM's three. **A sealed cartridge does not remove the shell
problem, it relocates it.** It still needs a seam, a parting line, a retention feature to hold
itself together during assembly, and a drop case. Everything in §2 to §6 is still required. What
sealing removes is the *opening* feature — one 0.9 mm slot — and what it costs is the ability to
replace a dead card. That is a very bad trade for a nine-line saving.

### The week estimate the PM asked for

**6 weeks, ± 2**, as a new work package in Phase 5. **This is an outside estimate and the
Software Lead should correct it** — firmware is not my stream and I am sizing someone else's
work, which is exactly the kind of number that should be checked rather than inherited.

| Piece | Estimate | Note |
|---|---:|---|
| USB device stack on the RT1062 | 1 wk | Well-trodden: NXP SDK, TinyUSB, the Teensy 4.1 ecosystem |
| MSC class over the existing block device | 1 wk | The block layer already exists; MSC is a thin SCSI shim over it |
| Mode entry and exit **with no screen** | 1.5 wk | The hard part that is not about USB. Guardrail 03 says there is nothing to display "USB mode" on, and guardrail 12 says firmware must not reimplement what the engine does. Interacts with WP-36 |
| Quiescing local access while the host holds the card | 1.5 wk | Two writers, one card, and a format whose whole safety argument is a single atomic commit. This is where the ± 2 lives |
| Bring-up and acceptance | 1 wk | — |

**The risk is not the USB stack, it is the host.** TAPEFS sits in partition 2 with a type byte
no desktop recognises, and Windows volunteers to repair unrecognised volumes. The person
clicking *Yes* is a parent trying to help, and the result is an erased cartridge with no
recovery. Any serious version of this package spends most of its schedule on that, not on
enumeration.

**No board change either way.** USB-C already carries data (`board-rev-a.md` §7, ADR-105), so
this stays a firmware-and-host question and can be added in Phase 5 without touching the shell —
which is itself an argument for the clasp, because the clasp does not close the door.

---

## 11. Open items

| # | Item | Who | Default if nobody answers |
|---|---|---|---|
| SH-1 | **Cartridge outer dimensions.** 86 × 54 × 12 mm is a working number chosen to be child-holdable, not a designed one. This is an aesthetic call and §2 shows the analysis does not depend on it | **Michael** | 86 × 54 × 12 proceeds; changing it later costs a rebuild, not a redesign |
| SH-2 | **Filament datasheets.** Modulus, permissible strain and friction are all EST. No vendor egress here reaches a filament vendor | Michael or PM | The §8 sweep measures around the uncertainty; a datasheet would narrow the bracket, not unblock it |
| SH-3 | **S-2's 90 days starts when the first PETG pair exists**, which is after a printer arrives. It is the long-lead criterion in this document | — | Runs in parallel with everything; does not gate WP-24 |
| SH-4 | **The car-dashboard finding** (§1) needs a line in whatever the family is told, and a case in WP-25 | PM | Recorded here; carried into WP-25 |
| SH-5 | **The TPU lip cannot be printed today.** The library is PLA-only | Michael's printer decision | The plate ships without it; the clasp works without it but with less tolerance margin |
