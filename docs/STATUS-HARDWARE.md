# Hardware status

**1 November 2026 PDT.** Current design: [DEVICE-DESIGN.md](DEVICE-DESIGN.md).

| Area | State |
|---|---|
| Hardware Lead | Resumes for **bench work** when Phase 3 opens (Michael, 1 Nov). Its first task is drafting the bench parts list and the card power-cut rig |
| Owner prototypes | CTRL-01 controls rig filed in `hardware/prototypes/ctrl-01/` (owner-directed; not acceptance). Earlier FIT-01/LADDER-01/02 results are recorded in docs/archive/hardware/ |
| Equipment Michael owns | A1 Mini printer, PLA, headphones, three PNY 64 GB V30 cards, a USB card reader, basic hand tools, likely access to a soldering iron. **No** Teensy, audio board, breadboard, LEDs, logic analyser or sound level meter |
| Cards | Three PNY 64 GB V30 bought; not characterised to WP-05 A-2 (the earlier method was rejected); atomicity not yet tested |
| Fabrication and charging | **CLOSED** (`make -C hardware fabrication-gate` returns nonzero). Phase 3 is bench-only: USB power, no cells, no boards |
| Spec | `spec/hw/` is versioned and still describes the earlier board and cartridge in places; Hardware revises it during Phase 3 |
| Legacy tooling | `hardware/cad`, `hardware/packets/wp04-01`, `hardware/thermal` and the solenoid model encode the superseded design. They stay as history until Hardware retires or reworks them |

Product safety limits are PM-owned in spec/acceptance.md. Michael witnesses measurements;
Verification audits method, instruments, calibration, raw data and uncertainty. Every
purchase needs Michael's approval.
