# Hardware status

**18 November 2026.** ADR-208: hands-on acceptance, about $30 of instruments. ADR-210: light process. Current design: [DEVICE-DESIGN.md](DEVICE-DESIGN.md).

| Area | State |
|---|---|
| Hardware Lead | No task open. Next: depth-sensing proposal for Rew/FF and the power-cut rig, once playback works on the bench |
| Parts | Michael confirmed the minimal bench order is in transit (18 Nov). Check contents on arrival against group 1 of the [staged list](../hardware/sourcing/PHASE3-BENCH.md). Later feature/rig orders are not confirmed |
| Power-cut test | Method: Teensy self-run (ADR-208 §6), 1,000 or more qualifying cuts per card model, zero torn. The host-side judge and its planted-tear tests are in `hardware/characterisation/`. The cut firmware is not written; it is written directly when group 3 parts are on the bench (ADR-210). ADR-209 design rulings stand: CID is diagnostic only, a write that completed before the cut and reads old fails the run, SPI results are scoped to SPI |
| Owner prototypes | CTRL-01 controls rig filed in `hardware/prototypes/ctrl-01/` (owner-directed; not acceptance). Earlier FIT-01/LADDER-01/02 results are recorded in docs/archive/hardware/ |
| Instruments planned (ADR-208) | Multimeter; optional ~$12 clone logic analyser for debugging only; phone sound-level app. No bench logic analyser, SPL meter, coupler or thermal camera |
| Equipment Michael owns | A1 Mini printer, PLA, headphones, three PNY 64 GB V30 cards, a USB card reader, basic hand tools, likely access to a soldering iron. **No** Teensy, audio board, breadboard, LEDs, logic analyser or sound level meter |
| Cards | Three PNY 64 GB V30 bought; not characterised to WP-05 A-2 (the earlier method was rejected); atomicity not yet tested |
| Fabrication and charging | **CLOSED** (`make -C hardware fabrication-gate` returns nonzero). Phase 3 is bench-only: USB power, no cells, no boards |
| Spec | `spec/hw/` is versioned and still describes the earlier board and cartridge in places; Hardware revises it during Phase 3 |
| Legacy tooling | `hardware/cad`, `hardware/packets/wp04-01`, `hardware/thermal` and the solenoid model encode the superseded design. They stay as history until Hardware retires or reworks them |

Safety limits live in spec/acceptance.md and change only with Michael's approval. Michael
witnesses measurements. Every purchase needs his approval.
