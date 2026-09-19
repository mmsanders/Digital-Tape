# Ruggedization — shock and load path, failure modes, and the staged abuse protocol

**Owner:** Hardware Lead · **Consumed by:** WP-25, WP-23, WP-22, WP-24 · **Status:** proposal
**Revision:** 0.4, 19 September 2026 · **Answers:** Guardrail 13, `docs/PACKAGES/WP-25.md`,
Verification P1-R17-V-B01..B05, and the P1-R20 assignment

<!-- CHANGES: every revision adds a block here. -->

## CHANGES

### 0.4 — 2026-09-19
**What P1-R20 asked for, and what this environment allowed.** The round asked for direct
primary-source transcription to replace the secondary rendering. **Every named source was
retried and every one is still refused** — `ecfr.gov` and all three `img.federalregister.gov`
figures answer 403 at the egress gateway, by direct fetch and by the harness fetch tool. So
**primary-source transcription is not achieved**, the record says so in the generated block,
and a retained control fails if that statement is ever removed.

What did change:

- **Probe B is dimensioned** (a..g) from the assignment, which cites the figure. The provenance
  says "via the assignment" on every one of the seven, and CS-1 stays open: a probe built to
  these numbers is dimensioned, not verified, and should be checked against the drawing by
  someone who can open it.
- **The use-and-abuse conditions for the seven-year band are recorded** — 1500.50's impact
  medium and 1500.53's drop, torque, tension and compression tests.
- **A crosswalk states every difference as a gap.** Our drop is higher onto a harder surface
  and in declared rather than random orientations; **torque, tension and compression are not
  covered at all**. Being harsher in places is not equivalence, and the crosswalk says so per
  row. A control fails if an uncovered test quietly stops being marked uncovered.
- **Tool facts** (§12a): the available scale could serve D-14 **only** if its model's published
  specification meets the existing 0.01 g / ±0.03 g requirement; screwdrivers are not a torque
  instrument; nothing else is owned and no purchase is requested.

### 0.3 — 2026-09-19
**B04: R-3 is no longer a judgement call.** The sharp-point and sharp-edge screens are
bound to 16 CFR 1500.48 and 1500.49, with the operative values transcribed per field and
cited, the Probe B accessibility basis stated and justified from the product's own
seven-year-old tiebreaker, and deterministic evaluation in `hardware/rugged/sharp.py` —
including run-conformance checks, so a tester that is out of specification produces **no
verdict** rather than a pass. Two measured checks (**D-19**, **D-20**) and two reference
red controls (**C-5**, **C-6**) join the protocol and are held to the same ≥2× margin
rule as the rest.

**The provenance is stated rather than glossed.** Every host serving the official text is
blocked by this environment's egress proxy — `ecfr.gov` answers 403 at the gateway, as do
`govinfo.gov`, `law.cornell.edu` and `cpsc.gov`. The values were recovered by web search
restricted to those same domains, which returns the regulation's own wording but is a
**secondary rendering**. No field claims primary verification, the edition banner could
not be read, and what could not be recovered — the probe figure geometry above all — is
listed in CS-1..CS-5 and left blank rather than filled in. A safety screen is the last
place to round a gap up to a number.

The small-parts screen is unchanged. Its Part 1501 citation is now explicit that the
source's under-three scope is **the source's**, not a claim about this product.

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
| **D-19** | sharp point created by the trial (R-3), on the Probe B accessibility basis | sharp-point tester per 16 CFR 1500.48: slotted cap, recessed sensing head, 0.5 lbf return spring, indicating circuit | 0-0.050 in travel · 0.001 in · +/-0.0005 in | gap set against a 0.015 in feeler before each session; indication confirmed on the reference sharp artifact (control C-5) | no accessible sharp point at stage 0, recorded per article | **sharp if the point contacts the sensing head and moves it a further 0.005 in; insertion force never above 1.00 lbf** | no |
| **D-20** | sharp metal or glass edge created by the trial (R-3) | sharp-edge tester per 16 CFR 1500.49: 0.375 in mandrel wrapped with a single layer of TFE tape, 1.35 lbf normal force, one revolution | 0-2 in cut length · 0.01 in · +/-0.02 in | mandrel diameter and tape thickness checked before each session; cut confirmed on the reference blade (control C-6) | no accessible sharp edge at stage 0, recorded per article | **sharp if the tape is completely cut for 0.5 in or more in one revolution** | no |
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
| **C-5** | D-19 | a reference sharp artifact -- a new steel scribe point -- is presented to the tester and moves the sensing head a measured 0.012 in, against the 0.005 in limit | **2.4×** past the 0.005 in limit | D-19 must indicate SHARP on the reference artifact before any article is screened | the point tester does not indicate on a known sharp point, so every not-sharp reading it has produced is meaningless |
| **C-6** | D-20 | a reference blade -- a new utility knife blade -- is run against the mandrel under the same 1.35 lbf, cutting a measured 1.20 in of tape against a 0.5 in limit | **2.4×** past the 0.5 in limit | D-20 must cut at least 1.0 in on the reference blade before any article is screened | the edge tester cannot cut on a known sharp edge, so every not-sharp reading it has produced is meaningless |
| **C-4** | D-17 | one fastener is set to 0.10 N.m install torque instead of 0.35, giving a residual breakaway below the 0.25 N.m floor | **2.5×** past the 0.25 N.m limit | D-17 must read a breakaway torque <= 0.15 N.m | fastener retention is not being measured and the torque check must be replaced |

Each control runs **before** the articles it protects are exposed, on a control article that never produces a qualifying result. Safety: C-1 — inert dummy only; no cell, charged or otherwise; C-2 — no energy stored; the article is not dropped in this state; C-3 — inert mass, no sharp edges, article closed; C-5 — a bench artifact, handled with the article closed and no cell present; nothing is dropped or powered; C-6 — a bench artifact, blade handled in a holder; no article, no cell; C-4 — no live cell; the article is not dropped in this state.
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
| **R-3** | Any **Probe B accessible** point or edge created by the trial is sharp by the §9 screen: a point that moves the sensing head ≥ 0.005 in, or an edge that cuts ≥ 0.5 in of tape in one revolution. Checks **D-19** and **D-20** |
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

## 9. Child-safety screens: sourced method (B04)

**These are internal engineering screens adopted for our own use. They are not
regulatory testing, not certification, and not a compliance claim**, and a pass here says
nothing about whether the product would pass a competent laboratory's version.

### Small parts (R-4) — unchanged, and runnable today

| Adopted source | What the method requires |
|---|---|
| **16 CFR Part 1501**, whose own scope is articles intended for children under three. **Adopting its cylinder is not a claim about our product's intended age** — our tiebreaker is a seven-year-old, and the cylinder is adopted because a detached part that fits it is a choking hazard whatever age the article is for | A test cylinder of **31.7 mm inside diameter** with a **slanted base**, giving a depth of **25.4 mm at the shallow side and 57.1 mm at the deep side**. A detached part is placed into the cylinder **without compressing it**, in **any orientation**; if it fits **entirely within**, it is a small part and R-4 fails. Fragments are tested individually, as found. |

### Sharp points and sharp edges (R-3) — now deterministic

<!-- BEGIN GENERATED: rugged_sharp -->
**Adopted sources**, retrieved 2026-09-19: [16 CFR 1500.48](https://www.ecfr.gov/current/title-16/chapter-II/subchapter-C/part-1500/section-1500.48) — Technical requirements for determining a sharp point in toys and other articles intended for use by children under 8 years of age; [16 CFR 1500.49](https://www.ecfr.gov/current/title-16/chapter-II/subchapter-C/part-1500/section-1500.49) — Technical requirements for determining a sharp metal or glass edge in toys and other articles intended for use by children under 8 years of age.

> Internal engineering screen only. Adopted from the cited sections for our own design use. NOT CPSC approval, certification, regulatory compliance, third-party testing or safety acceptance. Hardware cannot accept its own screen, and a pass here is not a ruggedization result.

**P1-R20 named the two sections and three official figure URLs directly and asked for direct primary-source transcription. Every one was retried on 19 September 2026 and every one is still refused by this environment's egress proxy: ecfr.gov and img.federalregister.gov both answer 403 at the gateway, by direct fetch and by the harness fetch tool. PRIMARY-SOURCE TRANSCRIPTION IS THEREFORE NOT ACHIEVED, and this file does not pretend otherwise.**

**Provenance of every value below:** web search restricted to ecfr.gov, law.cornell.edu, govinfo.gov and cpsc.gov; the documents themselves are unreachable from this environment (gateway 403 on CONNECT). No field is marked verified against the primary document, and the edition banner ("current through") could not be read. See CS-1..CS-5.

### Accessibility basis

| Field | Value | Cited as |
|---|---|---|
| probe for this product | **Probe B** | 16 CFR 1500.48 — probe A for articles intended for children 3 years or less; probe B for over 3 up to 8 years |
| adjacent-gap exemption | **0.020 in** | 16 CFR 1500.48 — a point is inaccessible without probe testing if it lies adjacent to a surface and the gap does not exceed 0.020 in (0.50 mm) |
| insertion depth, bounded openings | **up to 2.25x the opening's minor dimension** | 16 CFR 1500.48 — for an opening whose minor dimension exceeds the probe collar diameter but is below the unrestricted threshold, the probe with its extension is inserted in any direction up to 2.25x the minor dimension, measured from any point in the plane of the opening |
| unrestricted-depth threshold, probe B | **9.00 in** | 16 CFR 1500.48 — 9.00 in (228.6 mm) or larger minor dimension with probe B; insertion depth is then unrestricted |

### Sharp-point tester and criterion

| Field | Value | Cited as |
|---|---|---|
| gaging slot opening | **0.040 in wide by 0.045 in long** | 16 CFR 1500.48 — rectangular opening 0.040 in (1.02 mm) wide by 0.045 in (1.15 mm) long in the end of the slotted cap |
| sensing head recess | **0.015 in** | 16 CFR 1500.48 — the sensing head is recessed 0.015 in (0.38 mm) below the end cap |
| additional travel that identifies a sharp point | **0.005 in** | 16 CFR 1500.48 — the point must move the sensing head a further 0.005 in (0.12 mm) |
| return-spring force opposing that travel | **0.5 lbf** | 16 CFR 1500.48 — against the 0.5 lb (2.2 N) force of a return spring |
| maximum insertion force | **1.00 lbf** | 16 CFR 1500.48 — the force applied when inserting a point into the gaging slot is no more than 1.00 lb |

### Sharp-edge tester and criterion

| Field | Value | Cited as |
|---|---|---|
| mandrel diameter | **0.375 +/- 0.005 in** | 16 CFR 1500.49 — 0.375 +/- 0.005 in (9.35 +/- 0.12 mm) |
| tape | **single layer of polytetrafluoroethylene (TFE) tape wrapped around the full circumference** | 16 CFR 1500.49 — contact between test edge and mandrel at the approximate centre of the tape width |
| tape backing thickness | **0.0026 to 0.0035 in** | 16 CFR 1500.49 — between 0.0026 in (0.066 mm) and 0.0035 in (0.089 mm) |
| normal force | **1.35 lbf** | 16 CFR 1500.49 — applied to the edge with a normal force of 1.35 lb (6.00 N) |
| rotation | **one complete revolution** | 16 CFR 1500.49 — rotated through one complete revolution while the force against the edge is held constant |
| tangential velocity | **1.00 +/- 0.08 in/s** | 16 CFR 1500.49 — 1.00 +/- 0.08 in/s (25.4 +/- 2.0 mm/s) during the centre 75 percent of the rotation, with a smooth start and stop |
| cut length that identifies a sharp edge | **not less than 1/2 (0.5) in** | 16 CFR 1500.49 — the edge is sharp if it completely cuts through the tape for a length of not less than 1/2 in (13 mm) |

### Not recovered, and therefore not stated

| # | Missing | Consequence |
|---|---|---|
| **CS-1** | **Probe B's figure.** Seven dimensions are now recorded (a..g) from the P1-R20 assignment, which cites the figure -- but the figure itself is still unreachable, so nothing here is checked against the drawing. Tolerances, surface finish and how the extension attaches are not recovered at all. | a probe can be dimensioned but not verified; check it against the figure before it is used on anything |
| **CS-2** | **Tape width** for the edge tester. The contact point is specified relative to the width; the width itself was not recovered. | blocks specifying the consumable |
| **CS-3** | **The eCFR edition banner** — the 'current through' date. Nothing here can claim to be the current text. | blocks any currency claim |
| **CS-4** | **The complete exclusion clauses** of both sections — which points and edges are exempt (functional features and similar). | a screen that does not know its exclusions can only over-report, which is the safe direction, but it is not the method |
| **CS-5** | **The conditioning and use tests** referenced by the accessibility rule (1500.51/.52/.53, excluding the bite test), which determine whether a point is accessible before or after use and abuse. | our sequence applies the screen after the abuse family, which is at least as severe; matching the referenced procedure exactly is not established |

### Probe B geometry (CS-1 — dimensioned, not verified)

| Dim | Value | Cited as |
|---|---|---|
| a | **0.170 in** | 16 CFR 1500.48 figure, via the P1-R20 assignment |
| b | **0.340 in** | 16 CFR 1500.48 figure, via the P1-R20 assignment |
| c | **1.510 in** | 16 CFR 1500.48 figure, via the P1-R20 assignment |
| d | **0.760 in** | 16 CFR 1500.48 figure, via the P1-R20 assignment |
| e | **2.280 in** | 16 CFR 1500.48 figure, via the P1-R20 assignment |
| f | **1 1/2 in** | 16 CFR 1500.48 figure, via the P1-R20 assignment |
| g | **27 25/32 in** | 16 CFR 1500.48 figure, via the P1-R20 assignment |

### Use-and-abuse conditioning for the seven-year band

| Condition | Value | Cited as |
|---|---|---|
| impact medium | 1/8 in nominal type IV vinyl-composition tile, composition 1 (asbestos free), over at least 2.5 in of concrete, impact area at least 3 sq ft | 16 CFR 1500.50 — impact medium |
| drop test | 4 drops from 3 ft +/- 0.5 in, random orientation | 16 CFR 1500.53 — impact, over 36 through 96 months |
| torque test | 4 in-lb +/- 0.2 applied evenly over 5 s clockwise to 180 degrees or until exceeded, held 10 s | 16 CFR 1500.53 — torque |
| tension test | 15 lb +/- 0.5 applied evenly over 5 s, parallel then perpendicular to the major axis, each held 10 s | 16 CFR 1500.53 — tension |
| compression test | 30 lb +/- 0.5 applied evenly within 5 s through the disc, held 10 s | 16 CFR 1500.53 — compression |

### Crosswalk — our method against those conditions

Every difference is a gap, stated as one. Being harsher in places is not equivalence.

| Item | Our internal method | The referenced condition | Gap |
|---|---|---|---|
| drop height | 1.00 m (+0/-10 mm) | 0.92 m (3 ft +/- 0.5 in) | ours is ~9% higher, which is more severe -- severity is not equivalence |
| drop count and orientation | 12 per article, declared, cumulative | 4, random orientation | neither contains the other: a random sequence can land where our twelve never do |
| impact surface | bare concrete slab >= 50 mm | 1/8 in vinyl-composition tile over >= 2.5 in concrete | **a real gap.** Bare concrete is harder, so ours is more severe and NOT comparable; a result on one surface does not transfer to the other |
| articles | 2, explicitly a screen | as the method specifies | ours makes no statistical claim |
| torque | not performed | 4 in-lb | **not covered** -- a part that only fails under torque passes our screen |
| tension | not performed | 15 lb | **not covered**, same consequence |
| compression | not performed | 30 lb | **not covered**, same consequence |
| shake and tumble | 3 Hz shake, 25 tumbles | no direct equivalent | ours goes beyond these conditions; that is extra evidence, not compliance |
| when the screen runs | R-3/R-4 after the abuse families | accessibility assessed before and after 1500.51/.52/.53 (excluding the bite test) | ours screens after a harsher sequence, but the before side and the exact referenced sequence are not reproduced |

**Evaluation is deterministic**, in `hardware/rugged/sharp.py`: `point_run_conforms` and `edge_run_conforms` reject a run whose tester is out of specification — a non-conforming run yields no verdict rather than a pass — and `point_is_sharp` / `edge_is_sharp` then apply the criterion above. R-3 is no longer a judgement call.

**What the screen can do today:** nothing physical. The testers are not owned and no purchase is approved (RG-7), and CS-1 and CS-2 must close before a conforming probe or consumable can even be specified.
<!-- END GENERATED: rugged_sharp -->

**The age basis, stated once.** The product's tiebreaker is a seven-year-old
(`CLAUDE.md` §1). That is inside both sections' under-8 scope and above the three-year
boundary that selects the accessibility probe, so **Probe B applies**. No product
document places intended use under three; if one ever does, the probe selection changes
and this section must be reissued rather than reinterpreted.

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

## 12a. What the available tools can and cannot do

Recorded as facts, not as substitutions. **An ordinary tool is not a substitute for an
instrument with a stated resolution, accuracy and calibration** — that is the whole content of
B02, and it does not stop applying because a drawer is closer than a supplier.

| Tool available | Could serve | Only if | Cannot serve |
|---|---|---|---|
| **Sensitive food-preparation scale** | **D-14**, the loose-part mass check | its **exact model's published specification** proves **≥ 0.01 g resolution, ±0.03 g accuracy** and enough capacity for the article, and it can be checked against a reference mass. A kitchen scale reading to 1 g is 100× too coarse and would pass a detached 2 g part as noise | any force, torque or displacement check |
| **Screwdrivers and sockets** | assembly and disassembly | — | **D-17.** Driving a fastener is not measuring its breakaway torque, and a hand-tight guess is not 0.25 N·m |
| **Soldering iron (likely)** | building a harness or a fixture | — | nothing in §5 or §9 |

**Still unowned and unapproved:** torque screwdriver, dial indicator, push-pull force gauge,
gauge blocks, reference masses, audio interface, sharp-point tester, sharp-edge tester, TFE tape.
**D-14 is the only check that a currently-available tool could plausibly serve**, and only
conditionally — the requirement in §5 is unchanged and the scale does not meet it until its own
specification says so.

## 13. Open items

| # | Item | Owner | Effect if it resolves the other way |
|---|---|---|---|
| RG-1 | **Loaded mass is an estimate, not a measurement.** ~150 g `EST` | Hardware, then Michael's balance | Height and surface go back to PM if the real mass is >20% off |
| RG-2 | No enclosure design exists, so §2's mitigations are named against a load path rather than geometry | Hardware (WP-23) | The matrix gains rows as the CAD acquires features |
| RG-3 | The printer, material and process are uncharacterized | Michael's setup, then Hardware | Stage 2 is gated on it; a representative article cannot be built without it |
| RG-4 | Whether a live-cell trial is ever required | **PM and Michael** | Would need a separate safety review, not an extension of this protocol |
| RG-5 | Drop surface assumes a domestic concrete slab is available | Michael | A different declared surface changes severity and must be re-approved |
| RG-6 | **CS-1..CS-5** (§9): the probe figure geometry, tape width, edition banner, exclusion clauses and referenced conditioning tests are **not recovered** — every official host is blocked from the Hardware environment. The operative criteria themselves are sourced and R-3 is deterministic | Michael or PM, from a reachable copy | A conforming probe and consumable cannot be specified, and no currency claim can be made, until CS-1..CS-3 close |
| RG-7 | **Tools actually available** (Michael, 19 Sep): a sensitive food-preparation scale, ordinary screwdrivers and sockets, and likely access to a soldering iron. **Nothing else in §5 or §9 is owned**, and no purchase is requested this round. See the table below | **Michael** | Most checks in §5 still cannot run; this is the largest physical dependency after the articles themselves |
