# Ruggedization — shock and load path, failure modes, and the staged abuse protocol

**Owner:** Hardware Lead · **Consumed by:** WP-25, WP-23, WP-22, WP-24 · **Status:** proposal
**Revision:** 0.2, 19 September 2026 · **Answers:** Guardrail 13, `docs/PACKAGES/WP-25.md`,
and Verification findings P1-R17-V-B01..B05

<!-- CHANGES: every revision adds a block here. -->

## CHANGES

### 0.2 — 2026-09-19
**Rev 0.1 was rejected as a test method, and it deserved to be.** Verification's
P1-R17-V-B01..B05 said, correctly, that a protocol whose checks have no instrument and no
threshold cannot be executed by anyone but its author, and that a control described in a
sentence has not been shown to fire. Every finding is answered:

- **B01 — the mechanics are now repeatable.** A datum convention names every face, edge and
  corner; the drop sequence is ordered and complete on that convention; release fixture,
  height datum and tolerance, attitude tolerance and settle time are declared. The shake's
  150 mm is defined as peak-to-peak of the centre of mass, with how it is measured and how
  the frequency is verified — and the 120 s per axis is split into four 30 s bouts, because
  continuous 3 Hz hand motion for two minutes is not reliably repeatable and saying so is
  better than pretending. The tumble box, what counts as one tumble, and the completion rule
  are specified.
- **B02 — every check carries its instrument.** Range, resolution, accuracy, calibration
  action, baseline and a numeric threshold, and a flag saying whether performing the check
  disturbs the article. Disturbing checks are scheduled where they cannot corrupt a
  cumulative sequence.
- **B03 — the controls are measured, not described.** Each injects a defect in the target
  check's own unit, sized to clear that threshold by at least 2×, and each says what it means
  if the check fails to go red.
- **B04 — the child-safety screens name their source.** Exact CFR sections, the operative
  method as far as it can be stated without the document in hand, and an explicit list of the
  numeric details that must be transcribed from the source before the screen runs. No source
  host is reachable from this environment and nothing is invented to fill the gap.
- **B05 — staging is a gate, not a list.** Entry and exit conditions per stage, dummy
  equivalence on five properties rather than mass alone, a restart rule that says exactly what
  a repair restarts, and a quarantine rule for failed articles.

**The protocol is now data.** `hardware/rugged/protocol.py` holds it and generates the tables
below, so the document cannot drift from the numbers; `hardware/rugged/test_protocol.py` holds
eleven retained controls that enforce the properties above and prove they go red. That is the
difference between a method and a description of one.

Still true, and unchanged: **nothing here has been tested.** No enclosure exists, no mass has
been weighed, no trial is authorized, and no live cell appears in any stage.

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

## 3. The drop family (B01)

**Nothing in this section may be executed before PM approves it and Verification reviews the
criteria.** Every parameter is declared so that it is approved as a number.

<!-- BEGIN GENERATED: rugged_drops -->
**Datum:** right-handed, article-fixed: +Z up through the control face, +Y the cartridge insertion direction, +X = Y x Z.

| # | Orientation | What lands |
|---|---|---|
| 1 | `F+Z` | flat on the control face (buttons up) |
| 2 | `F-Z` | flat on the base |
| 3 | `F+Y` | flat on the cartridge-slot face |
| 4 | `F-Y` | flat on the rear face |
| 5 | `F+X` | flat on the right side |
| 6 | `F-X` | flat on the left side |
| 7 | `E(+Y+Z)` | shell seam along the control face |
| 8 | `E(-Y-Z)` | shell seam over the cell compartment |
| 9 | `C(+X+Y+Z)` | nearest the cartridge latch and the control face |
| 10 | `C(-X+Y+Z)` | cartridge slot, opposite side |
| 11 | `C(+X-Y-Z)` | over the cell compartment |
| 12 | `C(-X-Y-Z)` | over the cell compartment, opposite side |

**12 drops per article, cumulative, in this order.** n=2 is a SCREEN, not a statistical claim. One failure on either article fails the stage.

- height **1.00 m** (+0 / -10 mm), datum: lowest point of the article to the impact surface, measured with a steel rule against a plumbed mark
- surface: bare concrete slab, >= 50 mm thick, flat within 1 mm over 300 mm, no covering
- release: hinged trapdoor release fixture: the article rests on two half-flaps held by a single latch, so both flaps fall away together and the article is not pushed, tipped or spun
- attitude within **±5°** of the nominal orientation at release
- the article is left untouched for 10 s after impact, then checked
<!-- END GENERATED: rugged_drops -->

**On the 1.0 m height.** This is an *internal screen* at the height a child holds a player at
chest level. It is not an external qualification height and this document does not claim it as
one. WP-25 A-3 sets 1.0 m as a floor; if PM wants a higher declared height the number changes
here and the sequence does not.

**Why cumulative, and why that makes order part of the method.** A child does not get a fresh
player after each drop. Severity accumulates, so the sequence runs least-severe first: a corner
landing on an already-cracked rib is a different test from one landing on a sound rib, and
running faces first means a failure is attributable to the step that caused it.

## 4. The rough-play family (B01)

<!-- BEGIN GENERATED: rugged_roughplay -->
**Shake.** PEAK-TO-PEAK travel of the article's centre of mass along the axis under test, **150 ± 25 mm**, at **3.0 ± 0.2 Hz**.

- displacement measured against a 10 mm-graduated scale fixed in the camera frame, in the plane of motion, counted from video
- frequency verified by cycle count from the same video divided by its duration -- an audible metronome proves cadence was available, not that it was followed
- grip: held in one hand across the F+X/F-X faces, controls unobstructed, wrist neutral
- **4 bouts of 30 s** with 30 s rest, per axis, three axes (X, Y, Z) — 120 s per axis in total
- 120 s of continuous 3 Hz hand motion is not reliably repeatable, so each axis is four 30 s bouts with 30 s rest. If any bout falls outside the displacement or frequency tolerance on review, that bout is repeated.

**Tumble.** 25 tumbles in a 400×400×400 mm internal box, 9 mm plywood, internal faces bare (no lining, no padding).

- one tumble = one 90 degree rotation of the box about a horizontal edge, so the article falls from the upper face to the new floor
- fall height **0.40 m**, internal box height; the article starts on the face that becomes the ceiling
- 2 s per tumble; one article, unrestrained, box otherwise empty
- completion: 25 tumbles counted aloud on video, box opened, article photographed in the position it came to rest
<!-- END GENERATED: rugged_roughplay -->

Connectors fail by walkout rather than by fracture, which is why this family exists and is not
redundant with the drop family. A single impact rarely backs a connector out; a few hundred
small accelerations do.

## 5. Checks: instrument, baseline, threshold (B02)

Every check below names what measures it, to what resolution, against what baseline, and the
number it must beat. A check without those is an opinion, and P1-R17-V-B02 was right that rev
0.1 was full of them.

<!-- BEGIN GENERATED: rugged_checks -->
| ID | Measures | Instrument | Range · resolution · accuracy | Calibration | Baseline | Threshold | Disturbs? |
|---|---|---|---|---|---|---|---|
| **D-01** | cell retention: free travel of the cell dummy in its pocket | dial indicator on a magnetic stand, article opened and fixtured | 0-10 mm · 0.01 mm · +/-0.02 mm | zeroed against a 1.000 mm gauge block before each session | travel under a 5.0 N applied load, recorded per article at stage 0 | **increase over baseline <= 0.20 mm** | **yes** |
| **D-04** | shell seam gap | feeler gauge set | 0.05-1.00 mm · 0.05 mm · +/-0.005 mm (set spec) | blades checked against a micrometer annually; visually before use | largest blade entering the seam at stage 0, per edge, recorded | **no blade 0.20 mm or larger enters where the baseline blade was smaller** | no |
| **D-07** | cartridge retention against withdrawal | push-pull force gauge, hook adapter on the cartridge grip feature | 0-50 N · 0.05 N · +/-0.5% of reading | checked against a 2.00 kg reference mass before each session | withdrawal force at stage 0, mean of three, per article | **within 30% of baseline, and never below 8.0 N** | **yes** |
| **D-10** | connector retention | push-pull force gauge in line with the connector axis | 0-50 N · 0.05 N · +/-0.5% of reading | checked against a 2.00 kg reference mass before each session | unmate force at stage 0 on the DESIGNATED DISTURB ARTICLE only | **unmate force >= 0.50 x baseline; in-sequence articles use continuity and seating instead** | **yes** |
| **D-12** | transport alignment | dial indicator against the latch-bar datum face | 0-10 mm · 0.01 mm · +/-0.02 mm | zeroed against a 1.000 mm gauge block before each session | datum reading at stage 0 with the bar at rest, per article | **shift from baseline <= 0.15 mm** | **yes** |
| **D-14** | loose part inside: mass and audible impact | balance for mass; quiet room (<= 35 dBA) and a 0.3 m listen for impacts, article rotated through all three axes twice | 0-500 g · 0.01 g · +/-0.03 g | checked against a 100.00 g class-M2 mass before each session | assembled mass at stage 0, per article | **mass change <= 0.10 g AND no audible internal impact** | no |
| **D-17** | fastener retention | torque screwdriver, breakaway direction | 0.10-1.00 N.m · 0.01 N.m · +/-6% of reading | verified against a torque tester at the start of each session | install torque 0.35 N.m, recorded per fastener at stage 0 | **residual breakaway torque >= 0.25 N.m (70% of install). Measuring it releases the fastener, so it is re-torqued and recorded** | **yes** |
| **FC-02** | audio output, both channels | USB audio interface, line input, 1 kHz reference tone from the article's test track, RMS over 5 s | -60 to +6 dBu · 0.1 dB · +/-0.2 dB | interface input calibrated against a 1.000 Vrms source | per-channel RMS at stage 0, article at its fixed volume setting | **within 1.0 dB of baseline on both channels, no dropout** | no |
| **FC-03** | controls | 10 actuations per control, logged by the article's own firmware counter | n/a · 1 actuation · exact count | counter zeroed before each check | 10 of 10 registered per control at stage 0 | **10 of 10 registered, no double-fire, no dead press** | no |

A check marked DISTURBS changes the article -- opening it, releasing a fastener or unmating a connector. Those run at stage 0, at every third drop, and at the end of a family, never in the middle of a cumulative sequence. Non-disturbing checks run after every event. An article that has been opened is reassembled to the recorded install torque before the sequence continues, and the reassembly is recorded as an event.
<!-- END GENERATED: rugged_checks -->

**A measurement can be the thing that breaks the article.** Measuring breakaway torque releases
the fastener. Measuring unmate force disconnects the connector. Opening the shell disturbs
everything inside it. That is why `D-10` is measured on a designated disturb article rather than
on the articles carrying the sequence, and why the in-sequence proxy for connector retention is
continuity plus visual seating, which changes nothing.

## 6. Controls: defects large enough that the check cannot miss them (B03)

A control is not a plan to break something. It is a *measured* defect, in the same unit as the
threshold it must trip, large enough that a check which fails to notice is proven inadequate
rather than merely unlucky.

<!-- BEGIN GENERATED: rugged_controls -->
| Control | Targets | Injected defect | Margin | Must read | If it does not go red |
|---|---|---|---|---|---|
| **C-1** | D-01 | the cell-dummy retainer is fitted with its 0.60 mm shim removed and its fastener omitted, giving a measured free travel of 0.60 mm +/- 0.05 against a 0.20 mm limit | **3.0×** past the 0.2 mm limit | D-01 must read >= 0.55 mm of travel before any abuse | D-01 cannot detect a loose cell, so the cell-retention check is invalid and no article may be exposed until it is redesigned |
| **C-2** | D-04 | one shell fastener is backed out until a 0.45 mm feeler blade enters the seam, against a 0.20 mm limit | **2.2×** past the 0.2 mm limit | D-04 must admit a 0.40 mm blade where the baseline admitted none | the seam check is decorative and must be redefined before it is relied on |
| **C-3** | D-14 | a 2.00 g captive mass is released inside the closed article, against a 0.10 g mass limit | **20.0×** past the 0.1 g limit | D-14 must show a mass change >= 1.9 g on the article-plus-parts weighing, and an audible impact on rotation | the loose-part check cannot find a detached part, which is the one failure a functional check alone never sees |
| **C-4** | D-17 | one fastener is set to 0.10 N.m install torque instead of 0.35, giving a residual breakaway below the 0.25 N.m floor | **2.5×** past the 0.25 N.m limit | D-17 must read a breakaway torque <= 0.15 N.m | fastener retention is not being measured and the torque check must be replaced |

Each control runs **before** the articles it protects are exposed, on a control article that never produces a qualifying result. Safety: C-1 — inert dummy only; no cell, charged or otherwise; C-2 — no energy stored; the article is not dropped in this state; C-3 — inert mass, no sharp edges, article closed; C-4 — no live cell; the article is not dropped in this state.
<!-- END GENERATED: rugged_controls -->

`hardware/rugged/test_protocol.py` enforces the margin: a control whose defect is less than 2×
its target threshold fails the suite, and so does one measured in a different unit from the
check it claims to exercise. Both failure modes are demonstrated in that file rather than
asserted here.

## 7. Pass and fail rules

A trial **fails** if any of these is true. They are absolute — no cosmetic allowance applies —
and a repaired design restarts per the rule in §8.

| Rule | Failure |
|---|---|
| **R-1** | The cell dummy is exposed, loose beyond D-01's threshold, dented, punctured, or has moved in its pocket |
| **R-2** | Any live conductor is exposed, or any insulation is breached |
| **R-3** | Any accessible edge or point created by the trial is sharp by the §9 screen |
| **R-4** | Any part detaches that is a small part by the §9 screen |
| **R-5** | The enclosure opens unintentionally, or the cartridge ejects |
| **R-6** | Any check in §5 falls outside its threshold, including intermittently |
| **R-7** | D-14 shows a mass change or an audible internal impact |
| **R-8** | D-12 shows transport alignment outside its threshold |

**A cosmetic blemish passes.** Scuffs, witness marks and colour transfer from the surface are
recorded and do not fail a trial. The line is function, containment and safety.

## 8. Staging, restart and quarantine (B05)

<!-- BEGIN GENERATED: rugged_stages -->
| Stage | Article | Cell | What runs | Exit gate | On failure |
|---|---|---|---|---|---|
| 0 | bench | inert | record as-built state, every baseline in CHECKS, and photographs | all baselines recorded and within their build spec | n/a |
| 1 | enclosure with dummy mass, inert or non-functional internals | inert dummy of matched mass, centre of mass, envelope, mounting interface and mount stiffness | full drop family, then the rough-play family | BOTH articles complete the full sequence with every check inside its threshold, AND every control in CONTROLS has been shown to go red on the control article | any failure fails the stage; see the restart rule |
| 2 | representative assembled unit in the intended material and process | inert dummy, same equivalence as stage 1 | the same sequence, on articles built to a recorded process | as stage 1; this is the qualifying stage | any failure fails the stage; see the restart rule |
| 3 | live-cell trial | NOT PROPOSED | NOT PROPOSED | not scheduled and not implied by this document | would require a separate safety review by PM and Michael |

**Dummy equivalence** — an inert dummy matched on mass alone is not equivalent:

| Property | Tolerance |
|---|---|
| mass | +/- 2 g of the cell it replaces |
| centre of mass | +/- 2 mm in each axis |
| envelope | +/- 0.5 mm on each dimension |
| mounting interface | identical features, same fasteners, same torque |
| mount stiffness | within 20% of the cell's, measured as deflection under a 5.0 N transverse load |

**Restart.** A repair, a redesign or any change to the article, the material or the process restarts the ENTIRE affected cumulative family, on FRESH articles, for BOTH articles -- not the failed orientation alone. The drop family and the rough-play family are separate families for this purpose; a change that can only affect one restarts only that one, and the reason is recorded. Every control that covers a check in the restarted family is rerun before the articles are exposed.

**Quarantine.** A failed article is photographed as found, bagged, labelled with its article id, the step it failed and the date, and retained until the package is accepted. It is never returned to a sequence, never used for a later stage, and never repaired for reuse as a test article. Its data stays in the record: a failure is not deleted by a later pass.
<!-- END GENERATED: rugged_stages -->

**No live lithium cell is used in any exploratory or destructive trial**, including the
qualifying stage, which runs on an inert dummy. Whether a live-cell trial is ever needed, and
under what separate safety review, is a PM and Michael decision this document does not make and
does not pre-authorize.

## 9. Child-safety screens: source, method, and what is missing (B04)

**These are internal engineering screens adopted for our own use. They are not regulatory
testing, not certification, and not a compliance claim**, and a pass here says nothing about
whether the product would pass a competent laboratory's version.

| Screen | Adopted source | What the method requires |
|---|---|---|
| **Small parts (R-4)** | 16 CFR Part 1501 — the small-parts cylinder used for articles intended for children under three | A test cylinder of **31.7 mm inside diameter** with a **slanted base**, giving a depth of **25.4 mm at the shallow side and 57.1 mm at the deep side**. A detached part is placed into the cylinder **without compressing it**, in **any orientation**; if it fits **entirely within**, it is a small part and R-4 fails. Fragments are tested individually, as found. |
| **Sharp points (R-3)** | 16 CFR §1500.48 — technical requirements for determining a sharp point | A sharp-point tester with a gauge slot and an indicating circuit: the point is inserted into the slot under a defined load and the circuit indicates if it is sharp. Applies to accessible points on the article as presented after the trial. |
| **Sharp edges (R-3)** | 16 CFR §1500.49 — technical requirements for determining a sharp metal or glass edge | A mandrel wrapped with a defined tape is rotated against the edge under a defined force for a defined arc; the edge is sharp if the tape is cut over more than a defined fraction of the contact length. |

### What must be transcribed before either sharp screen runs

**No host serving the CFR is reachable from the Hardware Lead's environment** (`ecfr.gov` and
its API both fail to connect), and inventing a number to fill a gap in a safety method is
exactly the failure this project has rules against. The following are therefore **named, not
guessed**, and each must be transcribed from the cited section before the screen is run:

| # | Missing detail | Section |
|---|---|---|
| CS-1 | Sharp-point tester slot width, insertion depth and applied load | §1500.48 |
| CS-2 | The accessibility rule — which points and edges count as accessible, and the probe that decides it | §1500.48 / §1500.49 |
| CS-3 | Sharp-edge mandrel diameter, rotation speed, applied force and arc | §1500.49 |
| CS-4 | The tape specification and the cut fraction that defines "sharp" | §1500.49 |
| CS-5 | Whether the adopted edition matches the current one, and its date | all three |

**Michael, the smallest useful reply:** the three sections above, from any library or online
copy, or the corresponding ASTM F963 clauses if that is easier to reach. Until then R-3 runs as
a **documented judgement call** and is recorded as such — which is weaker than a screen and must
not be written up as if it were one. R-4's cylinder is fully specified above and can run today.

## 10. Evidence (WP-25 A-6)

### 10.1 Recorded before the first drop, per article

Mass (g, measured); outline dimensions; **material and vendor, with the exact filament spool**;
printer, nozzle, plate, orientation, slicer and version and the full settings profile — by
reference to `hardware/printing/owned-printer-baseline.md`; fastener type, count and as-built
install torque; photographs of every face and of the open interior; **every baseline named in
§5**; ambient temperature and slab temperature.

### 10.2 Recorded after every event

Every observation in the order taken; the step number and orientation it belongs to;
photographs; **every failure and every repair, kept in the record**; the raw video of the shake
and tumble elements. Nothing is summarized away, and a failure is never edited out of a
sequence.

## 11. Material and process — candidates, explicitly not mandated

WP-25's interface is mechanism-neutral and this document keeps it that way.

| Candidate | Argument for | Argument against | Status |
|---|---|---|---|
| **PETG shell** | Tougher and less brittle than PLA at the same wall; printable on the owned machine | Heat-deflection still modest; SH-4's dashboard case survives | **Candidate**, not chosen, not tested |
| **PLA shell** | What the existing analysis assumes; cheap; dimensionally stable | Brittle at the corner radii that matter for F-05 | **Candidate**, and the conservative case the numbers already clear |
| **TPU bumper or corner** | Absorbs at the shell, which is where §1 wants absorption | Second material; adds a process step and a joint | **Candidate**, unprioritized |
| **Foam or compliant liner in the cell pocket** | Directly addresses F-01 to F-03 | Compression set over time; thickness eats volume | **Candidate**, likely the cheapest win |
| **Ribs and radii** | Free in a printed part | Can move a crack rather than prevent it | **Expected**, sized only against a tested failure |
| **Locking connectors, strain relief, service loops** | Directly address F-10 and F-11 | Cost and board area | **Expected** |

**None of these is a product decision.** The protocol above is how one becomes one.

## 12. What this document does not authorize

- **No fabrication and no cell charging.** `make -C hardware fabrication-gate` reads CLOSED
  with five blockers and nothing here touches any of them.
- **No purchase.** Filament, fasteners, foam, a force gauge, a torque screwdriver, a dial
  indicator, a balance or a tumble box all need Michael.
- **No physical trial.** Every parameter here is a proposal pending PM approval and
  Verification's review of the criteria.
- **No live-cell abuse trial**, now or implicitly later.
- **No acceptance.** Hardware cannot accept its own design. There is no signed acceptance field
  in this document because there is nothing yet to sign.

## 13. Open items

| # | Item | Owner | Effect if it resolves the other way |
|---|---|---|---|
| RG-1 | **Loaded mass is an estimate, not a measurement.** ~150 g `EST` | Hardware, then Michael's balance | Height and surface go back to PM if the real mass is >20% off |
| RG-2 | No enclosure design exists, so §2's mitigations are named against a load path rather than geometry | Hardware (WP-23) | The matrix gains rows as the CAD acquires features |
| RG-3 | The printer, material and process are uncharacterized | Michael's setup, then Hardware | Stage 2 is gated on it; a representative article cannot be built without it |
| RG-4 | Whether a live-cell trial is ever required | **PM and Michael** | Would need a separate safety review, not an extension of this protocol |
| RG-5 | Drop surface assumes a domestic concrete slab is available | Michael | A different declared surface changes severity and must be re-approved |
| RG-6 | **CS-1..CS-5: the sharp-point and sharp-edge methods are not fully transcribed** (§9) | Michael or PM, from the cited sections | R-3 stays a documented judgement call until they are |
| RG-7 | The instruments in §5 — force gauge, torque screwdriver, dial indicator, balance, audio interface — are **not owned**, and none is approved for purchase | **Michael** | No check in §5 can run without them; this is the largest physical dependency after the articles themselves |
