# hardware/ — Hardware Lead

**No Hardware Lead agent is assigned yet.** This directory is scaffolded and empty.

Access: write here, read on `spec/`. **No access to `engine/` or `firmware/`.**

## Everything hardware is source

Boards in **KiCad** (text files). Enclosure, button mechanism and cartridge shell in
**CadQuery** or OpenSCAD. Not Fusion 360 — see `docs/DECISIONS.md` ADR-004.

The point is the variant sweep: "print six variants of the latch bar with hook depths from
0.8 to 1.8 mm" is a for-loop, not six modelling sessions. Michael carries one plate to the
library and comes back with the answer instead of one data point.

## Scope

- **Schematic and layout** — RT1062 with QSPI flash and PSRAM, SGTL5000, dual USDHC with 1.8 V
  switching, switching charger with NTC, solenoid driver with hardware one-shot, LED banks,
  controlled impedance on both UHS-I buses
- **Mechanical** — transport latch mechanism, enclosure, reversible cartridge shell and its
  carrier PCB. Parameterised, with variant sweeps generated per print run
- **Sourcing and thermal** — part selection with datasheet reading, BOM, lead times, assembler
  library coverage, and `spec/thermal-budget.md` maintained against reality
- **Print run packets** — per library trip: an STL set, a plate layout, what to measure on each
  variant, and where to record it. **Michael should never have to decide what to print**

## Needs, when the agent is stood up

KiCad, CadQuery and `kicad-cli` in the environment so it can run ERC and DRC itself rather
than proposing a board nobody checked. Web access for datasheets, availability and pricing.

## Caveat

Agents are good at netlists and parametric solids, and weaker at layout aesthetics, mechanical
intuition, and knowing when a part choice is technically fine but practically annoying. PM
review on every schematic before layout. The first board spin is an experiment — this is why
the plan carries three spins rather than two.
