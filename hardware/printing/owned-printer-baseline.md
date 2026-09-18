# Owned-printer process baseline — Bambu Lab A1 Mini

**Owner:** Hardware Lead · **Status:** plan, awaiting Michael's setup · **18 September 2026**
**Replaces:** the library-print assumptions in `WP-04.md`, `WP-24.md`,
`spec/hw/cartridge-shell.md` and `packets/wp04-01/CARD.md`

> **Nothing here has been printed, measured or characterized.** This is the plan Michael runs
> once the machine is set up. Until the coupons in §4 come back, **no dimension, fit, retention
> or abuse result from this printer is usable as evidence**, and the printer, material, slicer
> settings and any printed part remain unqualified.

## 1. What changed, and what that does not settle

Michael has bought a **Bambu Lab A1 Mini**. Three project assumptions were built on not having
one, and all three are now void:

| Old assumption | Source | Now |
|---|---|---|
| "Michael is not buying a printer" | PM Decisions 007 §2 | **Void.** He bought one |
| "The library runs a single spool of whatever it has loaded, probably PLA, not chosen by us" | Decisions 007 §2, `cartridge-shell.md` 0.2 | **Void.** Material is now a choice we make and record |
| "Two library prints a month, so one trip must carry two experiments" | `WP-04.md`, packet `CARD.md` | **Void.** Iteration is no longer rationed by trips |

**What it does not settle:** an owned printer is not a characterized process. Repeatability,
dimensional accuracy and the material actually loaded are now *ours to establish* rather than
the library's to vary — which is an improvement in control, not a result.

### The library rev-5 attempt: inconclusive, no returned result

The WP04-01 rev-5 plate was reported as printing at the library. **No parts came back and no
`RESULTS.md` was filled in.** Michael reports the library path was too slow and inconsistent.

**That is recorded as inconclusive — not as a pass, not as a failure, and not as evidence about
any part on the plate.** Every WP-04 and WP-24 question the plate was built to answer is still
open and still unanswered.

## 2. Machine facts — to be confirmed from the machine, not from memory

**Every row in this table is unverified.** No vendor host is reachable from the Hardware Lead's
environment (`bambulab.com`, the wiki and the store all fail to connect), so these are stated
from general knowledge and **must be replaced with what the machine and its documentation
actually say** before anything depends on them.

| Field | Expected | Confirmed? | Consequence if wrong |
|---|---|---|---|
| Build volume | **180 × 180 × 180 mm** | ☐ **unconfirmed** | **Decisive — see §3** |
| Nozzle | 0.4 mm, hardened or stainless variant | ☐ | Changes minimum feature width and the clasp lip |
| Plate | Textured PEI | ☐ | Changes first-layer and bottom-surface finish |
| Materials supported | PLA, PETG, TPU — **not** high-temperature engineering filaments | ☐ | The "nylon at home" path stays closed (`cartridge-shell.md` 0.1) |
| Multi-material | Only with the optional AMS lite | ☐ | Decides whether a two-material part (e.g. a TPU lip) is printable at all |
| Slicer | Bambu Studio / Orca, exact version to record | ☐ | The settings profile in §5 is meaningless without the version |

**Michael, the smallest useful reply:** the build volume from the machine's own documentation,
the nozzle diameter, whether an AMS lite is attached, and the slicer name and version.

## 3. The finding that blocks the existing packet

**The committed WP04-01 rev-5 plate is 228 × 119 mm. If the A1 Mini's bed is 180 × 180 mm, the
plate does not fit — it is 48 mm too long in X.**

The plate was laid out against a 250 × 210 mm bed "verified against the library machine"
(`packets/wp04-01/manifest.json`). That bed is gone.

This is a **blocker on printing the existing packet at all**, and it is not fixed by rotating:
the plate is a single merged solid by design, and 228 mm exceeds 180 mm on the diagonal budget
once part clearance is counted.

Three ways out, none of them chosen here:

| Option | What it costs | What it risks |
|---|---|---|
| **A. Split into two plates** (WP-04 buttons, WP-24 boxes) | A rebuild and a second print; trivially affordable now that trips are not rationed | Parts on different plates are no longer a matched pair — which matters for WP-24's paired-lid rule (`cartridge-shell.md` §2) |
| **B. Re-lay out to fit 180 × 180** | A rebuild; tighter spacing | Bed-position controls (`M`, `D`, `H`) lose their spread, weakening the control that detects position confounding |
| **C. Reduce the sweep** | Fewer variants per plate | Loses bracketing that was deliberately set to be wrong at both ends |

**Recommendation: A, with the WP-24 boxes and their lids kept on one plate together** so the
matched-pair rule survives; the WP-04 buttons have no such constraint. **This is a design change
to a blind experiment and PM should approve it before the plate is rebuilt** — it is not a
mechanical consequence of the printer purchase, and regenerating the plate reshuffles the blind
letters.

**Not done in this round:** the plate has not been rebuilt and `make -C hardware packet-check`
still reports the committed plate matching its source. Rebuilding it before the bed is confirmed
would bake an unverified number into a blind experiment.

## 4. Calibration and repeatability coupons — the auditable baseline

Runs once after setup, then again whenever material, nozzle or plate changes. **All coupon
geometry is to be generated from code** under `hardware/cad/`, like every other part
(ADR-004), so a coupon is reproducible rather than a one-off STL.

| # | Coupon | What it measures | Recorded |
|---|---|---|---|
| **K-1** | 20 mm cube, ×5, printed in **one** job at spread bed positions | Dimensional accuracy and **within-job** variation | X, Y, Z of each, to 0.01 mm, with the instrument named |
| **K-2** | The same 20 mm cube, ×5, in **five separate jobs** on different days | **Between-job** repeatability — the number the paired-printing rule depends on | Same fields, plus date and ambient |
| **K-3** | Interference-fit gauge: pin/hole pairs at 0.10 / 0.18 / 0.26 / 0.34 mm | Whether the clasp sweep is above the machine's own noise | Fit/no-fit per pair, by hand |
| **K-4** | Cantilever coupon at the WP-04 beam geometry | Whether beam compliance survives the process | Deflection under a known mass, or fails to print |
| **K-5** | Bridging and overhang fan | Support-free printability of the box interiors | Visual, photographed |
| **K-6** | First-layer / bed-adhesion patch | Whether the plate and profile are stable across the bed | Visual, photographed |

**K-2 is the one that matters most.** `cartridge-shell.md` §2 makes the paired-printing rule
normative on the basis of ±0.05 mm within a job against ±0.15 mm between jobs — **numbers that
were estimates for a machine we did not own.** K-2 replaces them with measurements, and if the
real between-job spread is wider, the clasp interference sweep may sit inside the noise.

**A coupon result is a measurement and is bound by the usual rule:** Michael measures and
witnesses, Verification audits method, instrument, conditions and derivation, and Hardware does
not accept it. Record each run with `hardware/measurements/TEMPLATE.md`.

## 5. Process record — the fields every printed part carries from now on

No printed part is evidence for anything unless these are recorded with it. This is the
result-card block referenced by `spec/hw/ruggedization.md` §5.1 and by every future packet.

```
Printer            Bambu Lab A1 Mini      Serial ______________
Firmware version   ____________________
Slicer / version   ____________________   Profile name ____________________
Material           ____________________   Vendor ____________________
Spool / lot        ____________________   Opened on __________  Dried? ______
Nozzle             ____ mm, ____________ (material)
Plate              ____________________   Plate temp ____ °C
Nozzle temp        ____ °C                Chamber/ambient ____ °C
Layer height       ____ mm                Walls ____   Infill ____ %  Pattern ______
Supports           OFF / ____________     Orientation ____________________
Print time         ____ h ____ min        Job date ____________
Coupon set in force (K-1..K-6 date)       ____________________
Anything unusual   ______________________________________________
```

**Orientation is now ours.** Under the library, staff chose it and the packet was built to
survive that (`WP-04.md`, "why merged, and why one orientation"). We now choose and record it —
so a part's orientation becomes a controlled variable rather than an uncontrolled one, and
`plate.stl` no longer has to be a single merged solid to protect the comparison. That is a real
simplification available to the next packet revision.

## 6. What this unlocks, and what it does not

**Unlocked:** material choice including PETG; iteration measured in hours rather than trips;
controlled orientation; multi-material parts **if** an AMS lite is attached; the S-2 ageing
trial in WP-24, which needs a first PETG pair to exist before its 90-day clock can start.

**Not unlocked:** nothing is qualified. Not the printer, not the material, not a printed part,
not a dimension, not a fit. **No abuse trial may use a printed unit until K-1 and K-2 have been
run and reviewed**, because an abuse result from an uncharacterized process cannot be told apart
from a bad print.
