# Hardware status

**4 November 2026 PDT.** Current design: [DEVICE-DESIGN.md](DEVICE-DESIGN.md).

| Area | State |
|---|---|
| Hardware Lead | #651 returned/closed. V392/2fc2298b clears c55e5ad bounded judge corrections; same judge in PR646/443a5a53. [Software663](https://github.com/mmsanders/Digital-Tape/issues/663) owns current-main integration/CI/merge with conditional PM sign-off; no Hardware base-update task |
| Parts | Michael selected minimum bench + rig; confirms **not ordered** (2 Nov). PR646 returns revised circuit/instrument delta; changed items/totals not approved or ordered |
| Atomicity rig | Method NOT CLEARED by Verification `3d616c14`; revision-2 circuit analysis and E0–E4 controls still unqualified; no physical run. SPI results would be bounded characterization only, no native SD4 qualification |
| Owner prototypes | CTRL-01 controls rig filed in `hardware/prototypes/ctrl-01/` (owner-directed; not acceptance). Earlier FIT-01/LADDER-01/02 results are recorded in docs/archive/hardware/ |
| Equipment Michael owns | A1 Mini printer, PLA, headphones, three PNY 64 GB V30 cards, a USB card reader, basic hand tools, likely access to a soldering iron. **No** Teensy, audio board, breadboard, LEDs, logic analyser or sound level meter |
| Cards | Three PNY 64 GB V30 bought; not characterised to WP-05 A-2 (the earlier method was rejected); atomicity not yet tested |
| Fabrication and charging | **CLOSED** (`make -C hardware fabrication-gate` returns nonzero). Phase 3 is bench-only: USB power, no cells, no boards |
| Spec | `spec/hw/` is versioned and still describes the earlier board and cartridge in places; Hardware revises it during Phase 3 |
| Legacy tooling | `hardware/cad`, `hardware/packets/wp04-01`, `hardware/thermal` and the solenoid model encode the superseded design. They stay as history until Hardware retires or reworks them |

Product safety limits are PM-owned in spec/acceptance.md. Michael witnesses measurements;
Verification audits method, instruments, calibration, raw data and uncertainty. Every
purchase needs Michael's approval.
