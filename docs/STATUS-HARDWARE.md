# Hardware status

**6 November 2026 PST.** ADR-208: hands-on acceptance, ~$30 instruments, Teensy self-run power-cut test, CID not required. Current design: [DEVICE-DESIGN.md](DEVICE-DESIGN.md).

| Area | State |
|---|---|
| Hardware Lead | #651 correction and Software663 integration complete. PR646 merged60dfe6aa after current-base CI; V392 clearance carries identical judge/imports. Physical method remains NOT CLEARED; no fresh Hardware base-update assignment |
| Parts | Michael selected minimum bench + rig; confirms **not ordered** (2 Nov). PR646 returns revised circuit/instrument delta; changed items/totals not approved or ordered |
| Atomicity rig | Replaced by a Teensy self-run power-cut test (ADR-208); the earlier externally traced rig and its E0–E4 instrument controls are no longer required. Hardware revises the method; no physical run yet |
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
