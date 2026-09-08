# Cartridge shell — the clasp, the seam, and what opens it

**Owner:** Hardware Lead · **Consumed by:** WP-24, WP-23, WP-25 · **Status:** assessment
**Revision:** 0.2, 6 Sep 2026 · **Answers:** PM Decisions 007 §2 (and 006 §2–§3 before it)

<!-- CHANGES: every revision adds a block here. -->

## CHANGES

### 0.2 — 2026-09-06
**The material assumption is gone, and the design changed to survive not having one.** PM
Decisions 007 §2: the library runs a **single spool of whatever it has loaded**, Michael is not
buying a printer, and PETG is no longer a thing we can assume. Rewritten around **creep under
sustained load** rather than cycle fatigue, per the design rule in §2 of that document.

Four substantive changes, and the first is the one that matters:

- **Closed-position strain is now stated as zero and proven as zero**, not "near zero". §4.
- **The retention wall went 1.2 → 1.6 mm and the interference 0.30 → 0.18 mm.** Lower snap
  strain *and* higher retention, because thickness enters strain linearly and force cubically.
  §2.
- **The TPU lip is void** — unprintable on a single spool. Its anti-rattle job is *deferred
  rather than redesigned* until the plate says rattle is real; a same-material replacement is
  sized and ready. §7.
- **Two tolerances, not one.** Halves printed together are a matched pair at ±0.05 mm; halves
  from different sessions are ±0.15 mm, and at this interference that range spans "no
  engagement" to "past PLA's limit". The paired-printing rule is now normative. §2.

### 0.1 — 2026-09-05
First issue. Answers the five asks in PM Decisions 006 §2, gives a week estimate for the
USB-MSC package asked for in §3, and records the material correction: **the A1 line does not
run nylon**, so the "print the latch in nylon at home" path in Decisions 005 §3 does not exist.

---

## 0. What this says, in one page

**Michael can have the clasp, and it no longer depends on a material we cannot specify.**

Two reframings carried this design, both the PM's. The first: a cartridge is opened **one to
three times in its life**, because every cartridge after the first is loaded by the device's own
copy button — so cycle fatigue was never the risk. The second, from Decisions 007 §2: **a clasp
is engaged 99.99 % of its life, so the risk is creep under sustained load**, and PLA relaxes at
room temperature.

Both point the same way, and the design rule follows from them: **the clasp must not be held
deflected when closed.**

| The number Decisions 007 §2 asks for | Answer |
|---|---:|
| **Closed-position strain** | **0.000 %** — and it is a geometric fact, checked by a boolean, not a model |
| **Snap-through peak strain** | **0.60 %**, assuming **PLA** — 1.7× under its permissible, 3.3× under PETG's |
| **Retention force, from geometry alone** | **322 N** in PLA, **176 N** in PETG |
| **Cycle target** | 20 open-close at ≤ 20 % loss (Decisions 006 §2), accepted — and §1 explains why it is the easy one |
| **Seam** | Tongue-and-groove on a 1.0 mm 45° chamfer. A 0.15–0.25 mm line, step to ±0.2 mm |
| **Opening feature** | A 0.9 mm blade slot on the back face — and §3 is honest about what actually keeps a child out |

**Zero is not a rounding of "near zero".** The groove is cut deeper than the bead stands proud,
so when the cartridge is shut the two halves do not touch at the bead at all. There is no stored
spring force anywhere in the closed cartridge, so there is nothing for any material to relax.
That is what makes the design **indifferent to whichever spool the library has loaded**, which
is the only kind of clasp specifiable when we do not choose the material.

**Everything safety-related in this document is quoted against the softer of the two candidate
materials**, for the same reason.

> **Every material property here is an estimate.** No vendor egress in this environment reaches
> a filament datasheet, so modulus, permissible strain, creep threshold and friction are from
> general knowledge of the polymers and are marked EST. The way that is handled is to make the
> plate measure what I guessed: the sweep in §8 is bracketed so that if my stiffness numbers are
> wrong, the ranking says so.

## 1. The cycle target, and the two risks it is not about

**PM Decisions 006 §2 proposed 20 open-close cycles with retention within 20 % of first-cycle.
Accepted, unchanged.** Ten times the realistic life is right for an object children handle.

**It is also the criterion this design cannot fail, and Decisions 007 §2 says why better than I
did.** Twenty one-second excursions to 0.60 % strain, spread over years, is not a fatigue duty
in any thermoplastic. The test takes four minutes and it will pass.

The two things that *can* fail are both about time, not count:

| # | Criterion | The risk it is actually about |
|---|---|---|
| **S-1** | 20 open-close cycles, retention within 20 % of first cycle | PM's. Accepted. Expected to pass easily |
| **S-2** | **90 days closed at 23 °C, and 90 days closed at 45 °C**, then S-1's force within 20 % | **Creep.** The cartridge is shut 99.99 % of its life |
| **S-3** | **1.0 m drop, closed, six faces and four corners, card retained every time** | Impact. Not a cycle, and no cycle count sees it |
| **S-4** | **A 30 N pinch held 10 s does not open it**, no tool | Child access. The only safety-critical one |

### S-2 is the one this revision is built around

Decisions 007 §2 states the risk exactly: *"a lip held deflected for a year loses its grip, and
it does so silently, on a cartridge in a child's pocket."*

**The design's answer is to remove the load rather than to survive it.** §4 shows the closed
strain is zero — not small, zero — so there is nothing sustained for any material to relax.
That makes S-2 a test of the *claim* rather than of the material: if the clasp loses grip after
90 days, the geometry is not doing what §4 says it does, and that is worth knowing regardless of
what spool it was printed in.

**S-2 still runs, and at 45 °C**, because the whole argument rests on a boolean over an ideal
solid model. A real printed part has elephant's foot, layer bulge and residual stress, and any
of those can put the two halves into contact where the model says they clear. **The check proves
the design; only the test proves the part.**

### One finding that goes with it

PLA's glass transition is around **60 °C** and PETG's heat deflection around **70 °C** (EST). A
closed car in summer reaches both. **A cartridge left on a dashboard may deform**, and a
deformed cartridge is one whose clasp no longer holds. Not a reason to change material — every
option we can actually print has this — but it needs a line in whatever the family is told and a
case in WP-25. **This is worse in PLA than it would have been in PETG**, which is a real cost of
not choosing the spool and should be recorded as one.

### The audit standard applies here

`spec/acceptance.md` DRAFT-7 now requires procedure, instrument and calibration, conditions, raw
readings, derivation and **stated measurement uncertainty** for the safety rows — the gap raised
as issue #23 and fixed by the PM. S-4 is safety-critical, so it is written to that standard from
the start rather than retrofitted: record it with `hardware/measurements/TEMPLATE.md`. A 30 N
pinch was chosen partly because a $10 luggage scale reads it, which is what makes the raw data
auditable at all.

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
| Cartridge outer | 86 × 54 × 12 mm | **Michael's call, and the analysis does not depend on it** — see below |
| Nominal wall | 2.0 mm | Stiffness and drop survival everywhere except the run |
| Retention wall | **1.6 mm** | Thinned local to the run. Was 1.2 mm; see the note below |
| Cantilever span | 6.0 mm | Floor to bead. Strain goes as its square |
| Interference | **0.18 mm** total | Shared: 0.090 mm per half |
| Tolerance on it | ±0.05 mm | Separately printed parts, and we do not choose the spool |
| Engaged run | 68 mm per long wall | 86 mm less 9 mm of corner relief each end |
| Lead-in chamfer | 25° from the pull axis | Closing ramp |
| Retention face | **40° from the pull axis** | Self-locks past **70.7°**, so this keeps half the range |

### The wall got thicker and the interference got smaller, and that improved both numbers

Rev 0.1 was a 1.2 mm wall at 0.30 mm interference: **0.75 % strain and 124 N** of retention in PETG. This is a 1.6 mm wall at 0.18 mm: **0.60 % strain and 176 N**. Lower strain *and* higher retention, which looks wrong until you write the two out:

```
strain    ~ i · t / a²        thickness enters LINEARLY
retention ~ E · w · t³ · i / a³   thickness enters CUBICALLY
```

So thickening the wall and pulling the interference back down to compensate is a strict win: you give up strain linearly and buy retention cubically. **The thicker wall is also the better drop part** (S-3), which is the rarest kind of result — the same change helping three criteria at once.

### The outer dimensions are free, and this is the one decision Michael can take on taste

**Strain contains no length term.** `ε = 3yt/2a²` — wall section and deflection only. So 86 × 54 can become anything: the outer dimensions move the *forces*, which is a comfort question, and leave the *strain* untouched, which is the materials question.

### Snap-through strain, and the material it assumes

The number PM Decisions 007 §2 asks for. **This is the only strain in the design, and it exists for about a second, twice in the cartridge's life.**

| | Deflection per half | **Snap-through strain** | vs PLA 1.0 % | vs PETG 2.0 % |
|---|---:|---:|---|---|
| Interference at minimum | 0.065 mm | **0.43 %** | 2.3× | 4.6× |
| **Nominal** | 0.090 mm | **0.60 %** | 1.7× | 3.3× |
| Interference at maximum | 0.115 mm | **0.77 %** | 1.3× | 2.6× |

### Why the wall is thinned only over the run

The thinning *is* the cantilever: 1.6 mm over the full 6.0 mm from floor to bead. Everywhere else the wall stays 2.0 mm, for stiffness and for the drop criterion. The tempting simplification is to thin the whole rim so the lid's tongue can be a plain rectangle — and that moves the flexing span from 6.0 mm to about 3.2 mm. Strain goes as the square of the span, so **0.60 % becomes 2.11 %** — 2.1× PLA's permissible strain. That version prints, assembles and feels correct on the bench. `hardware/cad/cartridge/test_shell.py` probes the wall section from the floor to the bead for exactly this reason.

**The assumed material is PLA**, because that is what we will get: a single library spool of whatever is loaded, not chosen by us (Decisions 007 §2). Every row above clears PLA's permissible strain, so the design does not depend on which of the two arrives — which is the point, since we cannot specify it.

**And this is what the paired-printing rule buys.** Build a cartridge from halves printed in *different* sessions and the tolerance is ±0.15 mm instead of ±0.05 mm. The interference then ranges from 0.03 mm — **no engagement at all** — up to 0.33 mm at **1.10 % strain**, which is past PLA's limit. Both ends of that range are a failure. **Halves are a matched pair and the card says so.**
<!-- END GENERATED: clasp_geometry -->

---

## 3. Retention force, from geometry alone

<!-- BEGIN GENERATED: clasp_forces -->
**All of this comes from geometry, not from stored spring force** — which is the distinction PM Decisions 007 §2 turns on. Nothing is held deflected when the cartridge is shut. The lip sits behind a shoulder, and separating the halves has to push it back out over its ramp against a wall that starts from rest.

| Action | PLA | PETG | Who does it |
|---|---:|---:|---|
| Pull the halves apart, whole seam at once | 322 N | 176 N | nobody — see below |
| Press closed, whole seam at once | 187 N | 102 N | nobody — closing rolls too |
| Lever one 14 mm span open with a blade | 33 N | 18 N | **the parent** |
| Press one 14 mm span closed | 19 N | 10 N | the parent, rolling along |

**The tool does not beat the latch by force, it beats it by unzipping it.** **10 : 1** — deflection force is linear in engaged length, so a blade in the slot deflects 14 mm of run while a brute pull has to deflect all 68 mm of both walls at once. The ratio is a property of the geometry and is **identical in both materials**, which is what makes the opening feature specifiable when the spool is not.

### Why the pull force is not the safety argument

| | Force available | vs 176 N (the softer material) |
|---|---:|---|
| Five-year-old, pinch on a flush 12 mm slab | ~20 N | **8.8× margin** |
| Five-year-old, two-handed grip **on something to hold** | ~80 N | 2.2× margin |
| Adult, two-handed pull | 200 N+ | none — an adult can force it |

Read the second row before the first. **Retention force does not separate a child from an adult.** What separates them is that there is *nothing to grip*: the seam is flush, there is no lip, no recess and no proud edge anywhere on the shell, so the only force a child can bring is a pinch on a smooth slab. That is the first row, and it is the one with the margin in it.

**The consequence is a rule, not a number:** any feature that gives a fingernail or a fingertip purchase on the parting line converts row 1 into row 2 and spends the entire margin. That rules out the recessed thumb-notch every battery cover has, and it is why the opening feature is a slot for a blade.

**The margin is quoted against the softer material on purpose.** We do not choose the spool, so every safety number in this document is the worst of the two candidates. In PLA the same joint takes 322 N.
<!-- END GENERATED: clasp_forces -->

---

## 4. Closed-position strain — the number Decisions 007 §2 asks for

<!-- BEGIN GENERATED: clasp_creep -->
**Closed-position strain: zero. Not near zero — zero, by construction.**

The groove is cut deeper than the bead stands proud, so when the cartridge is shut the two halves **do not touch at the bead at all**. The lip snaps past its shoulder and the wall returns to its undeflected shape. There is no stored spring force holding the cartridge together; retention is the lip sitting behind the shoulder, which is exactly the arrangement Decisions 007 §2 asks for.

**This is a geometric claim, so it is checked as one.** `hardware/cad/cartridge/test_shell.py` intersects the closed assembly as solids and asserts the overlap volume is zero, for every variant on the plate. Zero contact means zero contact force means zero strain — there is no modelling step between the check and the claim. Its `--mutate` run makes the groove too shallow to seat the bead and asserts the check goes red; that failure mode prints, assembles, latches and feels correct while holding the wall deflected for the life of the cartridge.

| | Strain | Held for | Against PLA's creep threshold (~0.25 %) |
|---|---:|---|---|
| **Closed** | **0.000 %** | years | no sustained load exists |
| Snapping open or shut | 0.60 % | ~1 s, twice in the cartridge's life | not a creep duty |

**Why this matters more than the cycle count.** A clasp is engaged 99.99 % of its life. PLA relaxes at room temperature under sustained strain, and a lip held deflected for a year loses its grip silently, on a cartridge in a child's pocket. **Cycling was never the risk** — the cartridge is opened once or twice ever. A design whose closed strain is zero is indifferent to how creep-prone the spool turns out to be, which is the only kind of clasp specifiable when we do not choose the material.

### What the TPU lip was doing, and what replaces it

Rev 0.1 used a TPU lip to preload the joint against rattle. **That is void** — the library runs a single spool and a merged STL carries one material for every part in it. It also introduced 0.086 % of *sustained* strain, which was defensible in PETG and is a worse idea in PLA.

**The replacement is to not solve the problem yet.** The coupon on the plate carries no preload feature at all, so Michael's answer to *does it stay shut when you shake it* tells us whether rattle is real before anything is designed for it. If it is, the same feature in the shell's own material is ready:

| Anti-rattle leaf, if needed | Value |
|---|---:|
| Section | 4 × 20 mm wide, 0.8 mm thick, 14 mm long, deflected 0.10 mm |
| Preload | 1.2 N in PLA, 0.7 N in PETG |
| **Sustained strain** | **0.061 %** — 4.1× under PLA's creep threshold |

**A short stiff rib cannot do this job and the arithmetic says why.** The gap to close is 0.10 mm. Deflect a 2.9 mm tall rib by that and it is **1.4 % strain, held forever** — the exact failure §2 forbids, arrived at while trying to fix rattle. The compliance has to come from a long, thin leaf: strain falls as the square of the span while force falls as the cube, so lengthening buys strain faster than it costs force. Same material, same displacement, twenty times less strain.
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

## 7. What happened to the TPU lip

**It is void.** Rev 0.1 used a thin TPU lip to preload the joint against rattle and to absorb
print tolerance. PM Decisions 007 §2 removes it twice over: the library runs **a single spool**,
so a second-material part cannot be printed at all, and Michael is not buying a printer, so the
route by which we would have got one is closed.

**It was also carrying 0.086 % of sustained strain** — defensible in PETG, and a worse idea in
the PLA we should now assume. Losing it makes the closed-strain number *better*, from 0.086 % to
zero.

What it leaves behind is the tolerance problem, and that is answered by §2's paired-printing
rule rather than by a part: both halves of a cartridge come off one plate in one session, so
they shrink together and what survives is the printer's repeatability, not the material's
shrinkage.

**The anti-rattle job is deferred, not redesigned.** The coupon on the plate carries no preload
feature at all, so Michael's answer to *does it stay shut when you shake it* tells us whether
rattle is real before anything is built for it. If it is, §4 has the replacement sized in the
shell's own material — and the arithmetic there is the useful part, because the obvious version
of that feature is a short stiff rib at **1.4 % sustained strain**, which is the exact failure
Decisions 007 §2 forbids, arrived at while trying to fix rattle.

**Not designing it yet is the point.** A preload feature added now would be a solution to a
problem nobody has confirmed exists, in a material nobody has confirmed, on a plate that has not
been printed.

## 8. The variant plate

Same process as WP-04, deliberately: shuffled letters unrelated to the parameter, a shared
mating part as a control, and *"they all felt about the same"* as a first-class answer
(ADR-104). **It shares WP-04's plate**, per Decisions 006 §4 — one library trip, two
experiments, 1.6 h of print against a 6 h limit.

<!-- BEGIN GENERATED: clasp_sweep -->
Coupon: **62 × 28 × 12 mm**, a real long-wall run (44 mm engaged) with both corner relieves, at full section. Not a whole cartridge — the run is the thing being swept, and a coupon leaves plate room for more of them.

**Swept in PLA, because that is what the library will load.** Bracketed so both ends are expected to be wrong: the bottom is at the printer's own repeatability and should barely engage, and the top is past PLA's permissible strain and is **expected to crack** — a result, not a wasted part.

| | Interference | Snap strain | vs PLA 1.0 % | Pull-apart | **Lever** | Expectation |
|---|---:|---:|---|---:|---:|---|
| | 0.10 mm | 0.33 % | ok | 116 N | **18 N** | at the printer's repeatability — should barely hold |
| | 0.18 mm | 0.60 % | ok | 209 N | **33 N** | **the nominal** |
| | 0.26 mm | 0.87 % | ok | 301 N | **48 N** | candidate, and the one to beat |
| | 0.34 mm | 1.13 % | **over** | 394 N | **63 N** | **expected to crack in PLA** |

**The lever column is the one that matters for the packet**, because it is the force Michael's hand actually applies through a blade. It runs 18–63 N across the sweep, so **every variant is openable by hand, including the one expected to crack.** If the brute-pull column were the operating force the top two would be untestable and the plate would be worthless.

**Four bases, four lids** (PM Decisions 007 §1). Rev 0.1 shipped two lids for four bases, so Michael would have reused a mating half across variants and **wear on the shared part would be confounded with whichever variant he tested last** — on a plate whose entire question is retention. The print budget now covers a dedicated lid per base, so the confound is removed rather than managed with a test order.

**Each pair is printed together and stays together.** Both halves come off one plate in one session, which is what holds the interference tolerance at ±0.05 mm instead of ±0.15 mm. Mixing halves between pairs is the one thing that invalidates the ranking, and the card says so.

**What each result means, decided in advance** so the next plate goes out without another round of thinking:

| If the plate says… | Then… |
|---|---|
| A clear winner, and it does not rattle | Print it at cartridge scale and run S-1…S-4 |
| A clear winner **that rattles** | Add the anti-rattle leaf above. Its numbers are ready |
| Nothing holds, including 0.34 | My stiffness estimate is too low. Re-bracket upward |
| Everything holds, including 0.10 | My estimate is too high, and the interference can shrink until it is comfortably inside the printer's repeatability |
| The top one cracks and the next does not | The PLA permissible-strain estimate is about right, which also calibrates every other number in this document |
| They all feel the same | Interference is not what the hand reads. Sweep the retention angle instead, at fixed interference |
<!-- END GENERATED: clasp_sweep -->

---

## 9. Materials — we do not choose the spool, and the design stopped caring

Rev 0.1 corrected one material error (the A1 line does not run nylon). **Decisions 007 §2
removes the premise underneath it:** Michael is not buying a printer, the library loads a single
spool of whatever it has, and we do not pick the material or the colour. PETG is no longer an
assumption available to us.

| What rev 0.1 assumed | What is actually true |
|---|---|
| PETG, from a printer Michael buys | **One library spool, probably PLA, not chosen by us** |
| A TPU lip for preload and tolerance | **Unprintable.** Single spool, and a merged STL carries one material for every part |
| Nylon from a service bureau for the latch | Still available and still the right answer for the *latch*, which is a fatigue part. Not for the shell |

### What that changed, and what it did not

**It did not change the geometry's logic.** The design rule Decisions 007 §2 states — the clasp
must not be held deflected when closed — is the rule rev 0.1 already followed, for the PETG
creep argument. The new material makes it *more* important, not different.

**It did change three numbers**, and §2 has them: a thicker retention wall, a smaller
interference, and a tolerance figure that now depends on a manufacturing rule rather than on a
filament.

**The honest cost of not choosing the spool** is in §1's dashboard finding: PLA's glass
transition is ~20 K below PETG's heat-deflection temperature, so a cartridge left in a hot car
is a real risk in the material we will get and a marginal one in the material we cannot have.
That is the one place where losing the choice actually costs something, and it belongs in WP-25
rather than being absorbed here.

### The instruction that shaped the fit

Decisions 007 §2: *"Do not tune a fit to a specific filament. Colours and brands differ in
shrinkage; retention must come from a chamfer and a defined interference with tolerance in it,
not from a knife-edge fit."*

Followed, and §2 shows how: the retention is a 25° lead-in chamfer onto a defined 0.18 mm
interference with a ±0.05 mm band around it, and **the paired-printing rule is what makes that
band achievable without tuning anything.** Halves printed together shrink together — which
removes the filament from the comparison rather than accommodating it.

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
| SH-1 | **Cartridge outer dimensions.** 86 × 54 × 12 mm is a working number, not a designed one. §2 shows the analysis does not depend on it — strain has no length term | **Michael** | 86 × 54 × 12 proceeds; changing it later costs a rebuild, not a redesign |
| SH-2 | **Filament datasheets.** Modulus, permissible strain, creep threshold and friction are all EST, and now for a material we do not choose. No vendor egress here reaches a filament vendor | Michael or PM | The §8 sweep measures around the uncertainty; a datasheet narrows the bracket, it does not unblock it |
| SH-3 | **Whether the library will let Michael supply his own filament.** He is asking on Monday (Decisions 009 §5). A yes would restore PETG and make the dashboard finding in §1 much less sharp | Michael | Everything here assumes no. If the answer is yes, nothing needs redesigning — the margins just get wider |
| SH-4 | **S-2's 90-day clock has not started** and cannot until a printed pair exists. It is the longest-lead criterion on the hardware stream and it is on no schedule | — | Runs in parallel; does not gate WP-24 |
| SH-5 | **Does it rattle?** There is deliberately no preload feature. The first plate answers it; §4 has the replacement sized if the answer is yes | Michael, via the plate | If it rattles, add the leaf. If not, the design is simpler and stays that way |
| SH-6 | **The car-dashboard finding** (§1) needs a line in whatever the family is told, and a case in WP-25. Sharper in PLA than it would have been in PETG | PM | Recorded here; carried into WP-25 |
