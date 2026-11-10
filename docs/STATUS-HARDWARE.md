# Hardware status

**10 November 2026 PST.** ADR-208: hands-on acceptance, ~$30 instruments, Teensy self-run power-cut test, CID not required. Current design: [DEVICE-DESIGN.md](DEVICE-DESIGN.md).

| Area | State |
|---|---|
| Hardware Lead | [#675](https://github.com/mmsanders/Digital-Tape/issues/675) stage 1 returned on PR673: schema correction 2 (ADR-209 P3/P4/P1/P2/SPI settled; exact CLI/normalisation/build boundaries), staged cart, S2 phone-method proposal. Stage 2 (host checker) waits for V405 bound tests on Verification main |
| Parts | **Group 1, buy first: $61.70** before tax/shipping, read on vendor pages 10 Nov ([PHASE3-BENCH](../hardware/sourcing/PHASE3-BENCH.md) rev 4): Teensy 4.1 no-Ethernet with headers DEV-20360, audio shield Rev D, header, breadboard, wires, buttons, cable; all in stock. Groups 2–4 (WP-18–20, self-run parts with multimeter, optional analyser) ≈$110.86 more, estimates. Michael approves and orders; **nothing ordered** |
| Atomicity rig | ADR-208 self-run method; V398 planted-tear logic passes, full method NOT CLEARED. [POWER-CUT-SCHEMA-R1](../hardware/characterisation/POWER-CUT-SCHEMA-R1.md) correction 2 declares plan 5/selfrun-r1 with ADR-209 decisions; not implemented until V405 binds tests. No physical run, card qualified or cut firmware |
| Owner prototypes | CTRL-01 controls rig filed in `hardware/prototypes/ctrl-01/` (owner-directed; not acceptance). Earlier FIT-01/LADDER-01/02 results are recorded in docs/archive/hardware/ |
| Instruments planned (ADR-208) | Multimeter; optional ~$12 clone logic analyser for debugging only; phone sound-level app. No bench logic analyser, SPL meter, coupler or thermal camera |
| Equipment Michael owns | A1 Mini printer, PLA, headphones, three PNY 64 GB V30 cards, a USB card reader, basic hand tools, likely access to a soldering iron. **No** Teensy, audio board, breadboard, LEDs, logic analyser or sound level meter |
| Cards | Three PNY 64 GB V30 bought; not characterised to WP-05 A-2 (the earlier method was rejected); atomicity not yet tested |
| Fabrication and charging | **CLOSED** (`make -C hardware fabrication-gate` returns nonzero). Phase 3 is bench-only: USB power, no cells, no boards |
| Spec | `spec/hw/` is versioned and still describes the earlier board and cartridge in places; Hardware revises it during Phase 3 |
| Legacy tooling | `hardware/cad`, `hardware/packets/wp04-01`, `hardware/thermal` and the solenoid model encode the superseded design. They stay as history until Hardware retires or reworks them |

Product safety limits are PM-owned in spec/acceptance.md. Michael witnesses measurements;
Verification checks the adopted method, candidate/build/raw-log/record linkage and strict
facts under ADR-208; it does not audit retired calibration/uncertainty requirements.
Every purchase needs Michael's approval.
