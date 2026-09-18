# Ruggedization — shock and load path, failure modes, and the staged abuse protocol

**Owner:** Hardware Lead · **Consumed by:** WP-25, WP-23, WP-22, WP-24 · **Status:** proposal
**Revision:** 0.1, 18 September 2026 · **Answers:** Guardrail 13 and `docs/PACKAGES/WP-25.md`

<!-- CHANGES: every revision adds a block here. -->

## CHANGES

### 0.1 — 2026-09-18
First issue. Publishes the load-path architecture and failure-mode matrix that WP-25 A-1
requires before final enclosure CAD, and proposes the numeric drop and rough-play protocol
WP-25 A-3 to A-7 require PM to approve before any trial. **Nothing here has been tested.**
No enclosure exists, no mass has been weighed, and no trial has been run or authorized.

---

## 0. What this document is, and what it is not

Guardrail 13 makes kid-resistance a first-order requirement and says ruggedization is designed
**before** final enclosure CAD. This is the design half: where load goes, what can fail, how a
failure would be detected, and the exact protocol proposed to provoke it.

**It is a proposal, not evidence and not a result.** Every number below is either a declared
test parameter awaiting PM approval, or an estimate marked `EST`. Verification reviews the
criteria before any physical trial, Michael performs the physical work, and Hardware does not
accept its own design (WP-25, independent sign-off).

**No trial is authorized by this document.** The fabrication and cell-charging holds are
separate and unaffected; §7 states what must not happen under any reading of this document.

## 1. The load path, stated before the CAD exists

Every drop puts the same energy in. What decides the outcome is which parts it travels through
and where it is finally absorbed. Stated as a chain so that a later CAD change can be checked
against it:

```
    impact face (shell)
        ↓  distributes over the shell wall
    shell wall + ribs
        ↓  into the internal standoffs / bosses
    mounting features
        ↓  splits three ways
    ┌───────────────┬────────────────────┬──────────────────┐
  board mounts    cell retention     transport frame
    ↓                ↓                    ↓
  connectors      cell body            latch bar, carriers
  and their       (highest mass,       (alignment-critical:
  strain relief    lowest tolerance     absorption here is
                   for motion)          a fault, not a feature)
```

Three consequences fall out of the chain and they drive everything in §2:

1. **The cell is the largest single mass and the least tolerant of motion.** Under a 1.0 m
   drop it carries roughly half the kinetic energy of the whole unit. Its retention is
   therefore the first load path to design and the first to inspect, not a bracket added at
   the end.
2. **Energy must be absorbed before it reaches the transport.** The latch bar and carriers are
   alignment-critical: a compliant mount that "absorbs" there changes the geometry WP-04 is
   sweeping. Compliance belongs in the shell and at the board and cell mounts; the transport
   wants rigid location (WP-25 interface, restated).
3. **Connectors fail by walkout, not by fracture.** Repeated small accelerations back a
   connector out over many events; a single drop rarely does. That is why §3's rough-play
   family exists at all and why it is not redundant with the drop family.

## 2. Failure-mode and mitigation matrix (WP-25 A-1)

Each row names a **detection check** that can find it. A mitigation with no detection check is
an assertion, not a mitigation. Check IDs are used by the result cards in §5.

| # | Failure mode | Where | Candidate mitigation (not mandated) | Detection check |
|---|---|---|---|---|
| F-01 | Cell breaks free of its retainer | cell compartment | Captured pocket with a positive ledge; retainer engaged in shear, not in tension on a boss | **D-01** post-drop: open, photograph, hand-load the cell — any motion, or a retainer with a changed shape, fails |
| F-02 | Cell body dented, pinched or punctured by an internal feature | cell compartment | No rib, boss or fastener tip projecting into the cell pocket; compliant liner | **D-02** post-drop: inspect cell face and pocket walls; any witness mark is a finding even if the cell is intact |
| F-03 | Cell moves enough to strain its leads | cell → board | Service loop with a strain relief anchored to the same part as the cell, not across the seam | **D-03** continuity and visual on the lead entry, before and after |
| F-04 | Enclosure opens on impact | shell seam | Fasteners or clasps in shear; seam not on the most-likely impact corner | **D-04** post-drop: seam gap measured with feeler stock; any opening fails |
| F-05 | Shell cracks into a sharp fragment | shell wall | Ductile-at-temperature material; radii at corners; wall thickness set by impact, not by looks | **D-05** post-drop sharp-edge inspection, §4 rule R-3 |
| F-06 | A part detaches and is small enough to swallow | anywhere | Captive fasteners; no unretained trim | **D-06** small-parts cylinder, §4 rule R-4 |
| F-07 | Cartridge ejects on impact | cartridge slot | Retention independent of the door; detent engaged across the drop axis | **D-07** post-drop: cartridge still seated, and still reads |
| F-08 | Cartridge shell opens and releases the card | cartridge | WP-24's clasp — **S-3 remains a separate minimum and is not consumed by a player-shell pass** | **D-08** WP-24 S-3, run separately |
| F-09 | Board cracks or a solder joint fractures | board mounts | Mount count and spacing set against board span; no mount at a high-mass component | **D-09** functional card §5.2 plus visual under magnification |
| F-10 | Connector walks out | board connectors | Latching connectors where the mate is serviceable; adhesive or clip where it is not | **D-10** rough-play family, then unmate force check against baseline |
| F-11 | Wire chafes against a printed edge | harness routing | Service loops, radiused exits, no wire across a seam that moves | **D-11** insulation inspection at every crossing |
| F-12 | Transport alignment shifts | transport frame | Rigid location; the frame not used as a drop-energy path | **D-12** latch/pop function check plus a datum measurement before and after |
| F-13 | Control goes intermittent or dead | controls | Switch carried by the board, not by the shell; travel limited by a hard stop | **D-13** all five transport controls, 10 actuations each |
| F-14 | Loose part rattles inside with no external sign | anywhere | Every internal part captured | **D-14** shake-and-listen, and it is the reason F-14 is on this list: it is the failure a functional check alone misses |
| F-15 | Speaker or audio path damaged | audio | Driver mounted on a compliant gasket, leads strain-relieved | **D-15** audio check, both channels, §5.2 |
| F-16 | Opening or vent lets a small object in | openings | Openings sized below the smallest part that could enter and bridge | **D-16** probe check per opening |
| F-17 | Fastener backs out over repeated handling | fasteners | Thread-forming into a boss with adequate engagement; or captive nut | **D-17** torque check against as-built record after the rough-play family |
| F-18 | Deformation from heat, not impact | shell | Material choice; **SH-4's car-dashboard case** (`cartridge-shell.md`) | **D-18** out of scope for the abuse protocol; carried as a separate thermal case |

**F-08 and F-18 are deliberately not absorbed into this protocol.** F-08 is WP-24's S-3 and
runs separately; F-18 is a thermal case and a drop protocol would not find it.

## 3. The proposed test protocol (WP-25 A-3, A-4, A-5 — for PM approval)

**Nothing in this section may be executed before PM approves it and Verification reviews the
criteria.** Every parameter is declared here so that it is approved as a number, not as an
intention.

### 3.1 Staging — inert before representative (WP-25 A-5)

| Stage | Unit under test | Cell | Purpose |
|---|---|---|---|
| **0** | bench only, no abuse | n/a | Record as-built state and functional baseline |
| **1** | enclosure with **dummy mass**, inert or non-functional internals | **inert dummy of matched mass and outline** | Find gross shell and retention failures cheaply |
| **2** | representative assembled unit in the intended material and process | **inert dummy of matched mass and outline** | The qualifying run |
| **3** | live-cell trial | **live cell** | **Not proposed. Not scheduled.** See §7 |

**No live lithium cell is used in any exploratory or destructive trial.** Stage 2 is the
qualifying stage and it runs on an inert cell dummy. Whether a live-cell trial is ever needed,
and under what separate safety review, is a PM and Michael decision that this document does not
make and does not pre-authorize.

### 3.2 Declared parameters

| Parameter | Declared value | Why this value |
|---|---|---|
| **Drop height** | **1.0 m**, measured from the lowest point of the unit to the surface | WP-25 A-3's floor. A child holds the player at chest height; 1.0 m is that, not a lab margin |
| **Surface** | Bare concrete slab ≥50 mm thick, flat, level, no covering; slab temperature recorded | Reproducible, and the realistic worst case in a kitchen or garage. Declared rather than "a hard floor" |
| **Loaded mass** | **measured before the run and recorded**; planning estimate ~150 g `EST`, carried from `thermal-budget.md` §3 | The protocol is keyed to the real mass. **If measured mass differs from the planning estimate by more than 20%, the height and surface go back to PM before the run** |
| **Impact energy at 1.0 m** | **1.47 J** at the 150 g `EST` — recompute from measured mass as `m·g·h` | Stated so an auditor can check the arithmetic rather than the adjective |
| **Orientations** | 12 per unit: **6 faces, 4 corners, 2 edges** | The four corners are the two nearest the cell compartment and the two nearest the cartridge slot — F-01 and F-07. The two edges are the shell seam and the control face — F-04 and F-13 |
| **Order** | Faces (least severe) → edges → corners, **cumulative on one unit** | Cumulative is the honest version: a child does not get a fresh player after each drop. A fresh unit per orientation would hide progressive damage |
| **Units** | **2 per stage**, both taking the full sequence | n=1 cannot distinguish a unit defect from a design failure. n=2 is a consistency screen, not a statistical claim |
| **Functional check** | after **every** drop, §5.2 card | A fault that appears at drop 4 and is only found at drop 12 has lost its cause |
| **Full inspection** | after every **third** drop and at the end | Opening the unit after every drop would itself disturb the retention being tested |

### 3.3 Rough-play family (WP-25 A-4)

*"Shook it and it seemed fine" is not evidence.* Both elements below are paced and counted so
a second person can repeat them.

| Element | Declared protocol |
|---|---|
| **Shake** | Metronome at **180 bpm (3 Hz)**, hand travel **150 mm ± 25 mm**, **120 s per axis**, three orthogonal axes, unit held as a child would hold it. Recorded to video with the metronome audible, which is what makes the cadence auditable |
| **Tumble** | **25 tumbles** in a 400 mm cube box, end over end, one tumble per 2 s. A repeated random-orientation impact at roughly 0.4 m — the rough-handling case the drop family's fixed orientations cannot reach |
| **After each element** | **D-14** shake-and-listen, **D-10** connector unmate force against baseline, **D-17** fastener torque against the as-built record, and the §5.2 functional card |

### 3.4 Negative control (WP-25 A-7) — the part that makes the rest mean something

Before the final qualifying run, on a **separate control unit that is never used for a
qualifying result**:

| Control | Deliberate defect | The check that must catch it | If it does not |
|---|---|---|---|
| **C-1** | Cell retainer fitted but **its fastener omitted** | **D-14** shake-and-listen must report cell motion within the first 120 s axis, and **D-01** must find it | The rough-play family is not sensitive enough to detect a loose cell, and **the whole shake protocol is invalid** — not the unit |
| **C-2** | One shell fastener **backed out two full turns** from the as-built torque | **D-17** must flag the torque, and **D-04** must find the seam gap after the drop family | The fastener and seam checks are decorative and must be redesigned before the qualifying run |

Neither control involves a live cell, a charged cell or a powered board beyond the functional
card. This is the direct application of the standing rule: a check that never goes red has not
established what it detects.

## 4. Pass and fail rules (WP-25 A-2)

A trial **fails** if any of these is true. They are absolute — no cosmetic allowance applies to
them, and a repaired design **restarts the affected sequence** rather than erasing the failure.

| Rule | Failure |
|---|---|
| **R-1** | The cell is exposed, loose, dented, punctured, or has moved in its pocket |
| **R-2** | Any live conductor is exposed, or any insulation is breached |
| **R-3** | Any accessible edge or point created by the trial is sharp. Assessed against the sharp-edge and sharp-point criteria used for children's products; **this is a design criterion adopted for our own use, not a claim of regulatory testing or compliance** |
| **R-4** | Any part detaches that fits entirely within a **31.7 mm diameter × 57.1 mm deep** cylinder — the small-parts dimensions used for children's products, adopted here for the same reason and with the same caveat as R-3 |
| **R-5** | The enclosure opens unintentionally, or the cartridge ejects |
| **R-6** | Any functional check on the §5.2 card fails, including intermittently |
| **R-7** | A loose part is audible or visible inside, even with every functional check passing |
| **R-8** | Transport alignment has changed against its datum |

**A cosmetic blemish passes.** Scuffs, witness marks on an outer face, and colour transfer from
the surface are recorded and do not fail a trial. The line is drawn at anything that changes
function, containment or safety.

## 5. Evidence (WP-25 A-6)

### 5.1 Recorded before the first drop, per unit

Mass (g, measured); outline dimensions; **material and vendor, with the exact filament spool**;
printer, nozzle, plate, orientation, slicer and version, and the full settings profile — by
reference to the process record in `hardware/printing/owned-printer-baseline.md`; fastener
type, count and **as-built torque**; photographs of every face and of the open interior;
functional baseline per §5.2; ambient temperature and slab temperature.

### 5.2 Functional card, run at every checkpoint

| ID | Check | Pass condition |
|---|---|---|
| FC-1 | Power on | Comes up, no reset loop |
| FC-2 | Audio, left and right | Both channels present at the same reference level as baseline |
| FC-3 | All five transport controls, 10 actuations each | Every actuation registers; no double-fire, no dead press |
| FC-4 | Latch and pop | Latches and releases as before the trial (**D-12**) |
| FC-5 | Cartridge seated and read | Reads, and the card is retained (**D-07**) |
| FC-6 | Cartridge insert/remove | Normal force, no new resistance or looseness |
| FC-7 | Shake and listen (**D-14**) | Nothing audible inside |
| FC-8 | Charge inhibit intact | The NTC path still reads; **no charging is performed** (`thermal-budget.md` T-1) |

### 5.3 Recorded after every trial

Every observation in the order taken; the drop number and orientation each observation belongs
to; photographs; **every failure and every repair, kept in the record**; the raw video of the
shake element. Nothing is summarized away, and a failure is never edited out of the sequence.

## 6. Material and process — candidates, explicitly not mandated

WP-25's interface is mechanism-neutral and this document keeps it that way. Recorded so the
eventual choice is visible as a choice:

| Candidate | Argument for | Argument against | Status |
|---|---|---|---|
| **PETG shell** | Tougher and less brittle than PLA at the same wall; now printable on the owned machine | Heat-deflection still modest; SH-4's dashboard case survives | **Candidate.** Now selectable where it previously was not — but not chosen and not tested |
| **PLA shell** | What the existing analysis assumes; cheap; dimensionally stable | Brittle at the corner radii that matter for F-05 | **Candidate**, and the conservative case the current numbers already clear |
| **TPU bumper or corner** | Absorbs at the shell, which is where §1 wants absorption | Second material; adds a process step and a joint | **Candidate**, unprioritized |
| **Foam or compliant liner in the cell pocket** | Directly addresses F-01 to F-03 | Compression set over time; thickness eats volume | **Candidate**, likely the cheapest win |
| **Ribs and radii** | Free in a printed part | Can move a crack rather than prevent it | **Expected**, but sized only against a tested failure |
| **Locking connectors, strain relief, service loops** | Directly address F-10 and F-11 | Cost and board area | **Expected** |

**None of these is a product decision.** The protocol above is how one becomes one.

## 7. What this document does not authorize

- **No fabrication and no cell charging.** `make -C hardware fabrication-gate` reads CLOSED
  with five blockers and this document does not touch any of them.
- **No purchase.** Filament, fasteners, foam, a metronome or anything else needs Michael.
- **No physical trial.** Every parameter here is a proposal pending PM approval and
  Verification's review of the criteria.
- **No live-cell abuse trial**, now or implicitly later.
- **No acceptance.** Hardware cannot accept its own design. There is no signed acceptance field
  in this document because there is nothing yet to sign.

## 8. Open items

| # | Item | Owner | Effect if it resolves the other way |
|---|---|---|---|
| RG-1 | **Loaded mass is an estimate, not a measurement.** ~150 g `EST` | Hardware, then Michael's scale | Height and surface go back to PM if the real mass is >20% off |
| RG-2 | No enclosure design exists, so §2's mitigations are named against a load path rather than against geometry | Hardware (WP-23) | The matrix gains rows as the CAD acquires features; it is not expected to shrink |
| RG-3 | The printer, material and process are uncharacterized (`printing/owned-printer-baseline.md`) | Michael's setup, then Hardware | A representative unit cannot be built until the process is repeatable; Stage 2 is gated on it |
| RG-4 | Whether a live-cell trial is ever required | **PM and Michael** | Would need a separate safety review, not an extension of this protocol |
| RG-5 | Drop surface assumes a domestic concrete slab is available and usable | Michael | A different declared surface changes severity and must be re-approved, not substituted |
