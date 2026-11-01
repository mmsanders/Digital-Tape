# Phase 3 plan — bench firmware

**Planned; opens after the Phase 2.5 cleanout** (Michael, 1 Nov 2026; [ADR-199](DECISIONS.md#adr-199--phase-25-cleanout-device-design-baseline-and-phase-3-answers)).
Work is assigned in role-labeled issues once Michael opens the phase. The device is described
in [DEVICE-DESIGN.md](DEVICE-DESIGN.md).

## 1. What Phase 3 delivers

**Goal:** the shared engine runs on a Teensy 4.1 bench build and plays a cartridge made by the
desktop app, through headphones and a speaker, with real keys and LED status.

**Milestone:** Michael makes a cartridge with the app, puts it in the bench build, presses Play
and hears it. Scrub, stop and a short recording work. Pulling the cartridge and putting it back
resumes near where it stopped.

| Package | Delivers | Key criteria |
|---|---|---|
| WP-05 Cards and bench parts | Bench parts list (Michael approves); card power-cut rig; card characterisation | Atomicity: ≥ 1,000 qualifying cuts per exact SKU/revision, zero torn blocks (a torn block is a format blocker); sustained-write on 80%-filled media |
| WP-17 Firmware skeleton, engine integration | Teensy port (SD read/write/flush, I²S out), shared engine unchanged | Goldens bit-identical to desktop at 1.0× (divergence blocks release); RAM/stack/.rodata budgets measured on target (G08); warm instant-on < 100 ms on a logic analyser (G04); commit latency < 200 ms; resume position |
| WP-18 Second slot, insert detect, copy | Rear-slot source, front-slot destination, copy with LED-ring progress | Copy correctness; progress from the callback, never a timer. Copy *time* is not provable on the bench (SPI second slot); guardrail 10 stays a Phase 5 measurement |
| WP-19 Audio paths and caps | Codec, headphone out, speaker amplifier, microphone, two aux ports | Headphone cap 85 dB SPL (G11) and a separate speaker cap, both set in hardware/codec, re-asserted at boot, unreachable from controls; measured with an SPL meter, **witnessed by Michael** |
| WP-20 Transport reading and status | Read the mechanical keys; LED-ring status; record light | No solenoid: firmware never moves a key. End of tape and cartridge-full shown on the LED ring (spec revision at kickoff); record light per spec; scrub ramp per spec |
| WP-21 Bench acceptance demo | The firmware criteria run end to end | Michael-witnessed record; Verification audits method and raw data |

**Exit gate:**
1. WP-05 and WP-17 to WP-21 independently accepted on the bench build.
2. Goldens bit-identical on firmware at 1.0×; Phase 1/2 goldens and replays still green.
3. Atomicity passed on the PNY cards (or a torn block escalated as a format blocker).
4. Q-P2-1 entry conditions met before any firmware write batching is enabled.

**Not in Phase 3:**
- board fabrication, cells or charging (the gate stays CLOSED; the bench runs on USB);
- enclosure and cartridge CAD (Phase 4);
- the SDR50/UHS-I port and the < 30 s copy proof (Phase 5);
- any engine or format change;
- desktop app changes, except the deferred G2 work.

## 2. Kickoff work (round 1)

- **PM:** a spec revision covering
  - the speaker cap value (guardrail 11 revision);
  - end-of-tape and cartridge-full behaviour without a solenoid;
  - removal of the coil limits.
  
  Also the WP-17 contract (port interface, bench pin map, golden-on-target method). These
  follow Michael's answers to DEVICE-DESIGN §6.
- **Hardware:**
  - the bench parts list for Michael's approval: Teensy 4.1, audio board, breadboard and
    wiring, keys and LEDs, second microSD breakout, small speaker and amplifier, MEMS mic,
    aux jacks, logic analyser, and SPL meter plus coupler;
  - the atomicity rig design;
  - toy-safety acoustic limits for the speaker cap.
- **Verification:**
  - the Q-P2-1 any-subset completion;
  - WP-17 acceptance authored from the contract;
  - review of the atomicity rig method.
- **Software:** firmware skeleton and engine-on-port tests off-target until parts arrive.
- **Michael:** approve and order the parts list.

## 3. How the work runs

ADR-195 carries over:
- outcome tests plus a negative control;
- no separate method rounds;
- outcome-sized issues;
- same-issue stage continuation;
- a criterion ledger as the progress record.

Structural Rule 1 governs engine code. Firmware is a port and consumer: it must not fork seek,
mixing or any other engine behaviour (CLAUDE.md §6). Physical safety measurements are witnessed
by Michael and audited by Verification.

## 4. Carried in

- Q-P2-1: port-level batching, engine unchanged (ADR-195 §4).
- Deferred from Phase 2:
  - the G2 unaided app test;
  - macOS;
  - the ADR-196 limitations.
