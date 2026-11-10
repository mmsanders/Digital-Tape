# Hardware status

**8 November 2026 PST.** ADR-208: hands-on acceptance, ~$30 instruments, Teensy self-run power-cut test, CID not required. Current design: [DEVICE-DESIGN.md](DEVICE-DESIGN.md).

| Area | State |
|---|---|
| Hardware Lead | #671 returned PR673/c32f1a56, a declaration only. Fresh [#675](https://github.com/mmsanders/Digital-Tape/issues/675) finishes selfrun-r1 host checker after V405 binding, staged first-order cart and S2 gap. Earlier646 integration complete |
| Parts | Missing Teensy/audio board now blocks target validation. PR673 revised full cart estimate$176.86 (unverified current checkout); first-order lines1-7 old estimate$71.95. #675 verifies small cart/vendor stock/header fit. Nothing ordered or newly approved |
| Atomicity rig | ADR208 self-run method; V398 planted-tear logic11 cases pass, complete method NOT CLEARED. New plan5/selfrun-r1 declaration + ADR209 P3/P4/SPI decisions go to V405 before code. No external-U/calibrated-instrument gate; no physical run/card qualified |
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
