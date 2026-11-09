# Hardware status

**9 November 2026 PST.** ADR-208: hands-on acceptance, ~$30 instruments, Teensy self-run power-cut test, CID not required. Current design: [DEVICE-DESIGN.md](DEVICE-DESIGN.md).

| Area | State |
|---|---|
| Hardware Lead | #651 correction and Software663 integration complete. PR646 merged60dfe6aa after current-base CI; V392 clearance carries identical judge/imports. Physical method remains NOT CLEARED; no fresh Hardware base-update assignment |
| Parts | **Revision 3 cart (ADR-208, #671)** in [PHASE3-BENCH](../hardware/sourcing/PHASE3-BENCH.md): prototype parts $117.81 + power-cut parts $25.55 + instruments $33.50 (multimeter $21.50, optional clone analyser ≈$12, debugging only) = **$176.86** before tax and shipping. Awaiting Michael's approval; **nothing ordered**. Replaces the 2 Nov selection and the round 2 delta |
| Atomicity rig | **Teensy self-run method drafted** (#671): [POWER-CUT-SELFRUN](../hardware/characterisation/POWER-CUT-SELFRUN.md). TPS22918 switched card rail with discharge, SPI at 4 MHz, cut only straight after a busy byte, per-row ADC check that the card was off, revision-3 rows read by the unchanged judge; planted-tear control N1. V398 (Verification `321c5236`) passed the off-target planted-tear check and held the full method (H398-1..4). Correction: new `selfrun-r1` route declared in [POWER-CUT-SCHEMA-R1](../hardware/characterisation/POWER-CUT-SCHEMA-R1.md): CID optional, P1/P2/build enforced, not implemented. Next: PM rules on P3/P4/SPI scope, then Verification binds tests. Not built or run |
| Owner prototypes | CTRL-01 controls rig filed in `hardware/prototypes/ctrl-01/` (owner-directed; not acceptance). Earlier FIT-01/LADDER-01/02 results are recorded in docs/archive/hardware/ |
| Instruments planned (ADR-208) | Multimeter; optional ~$12 clone logic analyser for debugging only; phone sound-level app. No bench logic analyser, SPL meter, coupler or thermal camera |
| Equipment Michael owns | A1 Mini printer, PLA, headphones, three PNY 64 GB V30 cards, a USB card reader, basic hand tools, likely access to a soldering iron. **No** Teensy, audio board, breadboard, LEDs, logic analyser or sound level meter |
| Cards | Three PNY 64 GB V30 bought; not characterised to WP-05 A-2 (the earlier method was rejected); atomicity not yet tested |
| Fabrication and charging | **CLOSED** (`make -C hardware fabrication-gate` returns nonzero). Phase 3 is bench-only: USB power, no cells, no boards |
| Spec | `spec/hw/` is versioned and still describes the earlier board and cartridge in places; Hardware revises it during Phase 3 |
| Legacy tooling | `hardware/cad`, `hardware/packets/wp04-01`, `hardware/thermal` and the solenoid model encode the superseded design. They stay as history until Hardware retires or reworks them |

Product safety limits are PM-owned in spec/acceptance.md. Michael witnesses measurements;
Verification audits method, instruments, calibration, raw data and uncertainty. Every
purchase needs Michael's approval.
