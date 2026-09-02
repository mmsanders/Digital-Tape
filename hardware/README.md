# hardware/ — Hardware Lead

**Hardware Lead assigned 2026-08-31.** Charter received and reviewed; see
`docs/STATUS-HARDWARE.md` for the review, the open concerns and what is blocked. This
directory is still empty — nothing is built until the toolchain gap below is closed.

Access: write here, read on `spec/`. **No access to `engine/` or `firmware/`.**

Reporting: `docs/STATUS-HARDWARE.md`, updated on every merge that touches `hardware/`.
Escalation: `pm-decision` issues for the PM, `docs/FOR-MICHAEL.md` for taste and hands.
Scope: WP-04, WP-22–27, WP-29, WP-30, WP-34, WP-37 (plus WP-05, per the charter's ask #04 —
see the scope note in `docs/STATUS-HARDWARE.md`).

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

## Environment needs — verified 2026-08-31, and not yet met

Probed rather than assumed. Details and the exact evidence are in `docs/STATUS-HARDWARE.md`
(H-02, H-03).

| Need | State | Fixable from here? |
|---|---|---|
| CadQuery | Not installed. PyPI **is** reachable | Yes — will install |
| KiCad + `kicad-cli` | Not installed. `archive.ubuntu.com` offers **7.0.11 only** | Partly |
| `kicad-cli sch erc` | **Needs KiCad 8+.** Not in 7.0. KiCad PPA is 403 through the proxy | **No** |
| Vendor / distributor / fab web access | **Blocked.** `nxp.com`, `digikey.com`, `octopart.com`, `jlcpcb.com` all 403 at CONNECT | **No** |

The last two are the ones that need someone else. Without KiCad 8+ the charter's "run ERC
yourself, a clean report is part of the deliverable" becomes a claim rather than an artefact.
Without vendor access there is no assembler-library check, no errata checklist, no lead times
and no BOM anyone should order from — all four of which the charter asks for by name.

## Caveat

Agents are good at netlists and parametric solids, and weaker at layout aesthetics, mechanical
intuition, and knowing when a part choice is technically fine but practically annoying. PM
review on every schematic before layout. The first board spin is an experiment — this is why
the plan carries three spins rather than two.
