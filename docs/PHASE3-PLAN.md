# Phase 3 plan — bench firmware

**OPEN since 2 November 2026** ([ADR-201](DECISIONS.md#adr-201--phase-3-opened-round-1-issued)). Work is assigned in
role-labeled issues; progress is in [the Phase 3 ledger](PHASE3-LEDGER.md). The device is described
in [DEVICE-DESIGN.md](DEVICE-DESIGN.md).

## 1. What Phase 3 delivers

**Goal:** the shared engine runs on a Teensy 4.1 bench build and plays a cartridge made by the
desktop app, through headphones and a speaker, with real keys and LED status.

**Milestone:** Michael makes a cartridge with the app, puts it in the bench build, presses Play
and hears it. Scrub, stop and a short recording work. Pulling the cartridge and putting it back
resumes near where it stopped.

| Package | Delivers | Key criteria |
|---|---|---|
| WP-05 Cards and bench parts | Bench parts list (Michael approves); Teensy self-run power-cut test; card characterisation | Atomicity: ≥ 1,000 qualifying cuts per card model, zero torn blocks (a torn block is a format blocker); sustained-write on 80%-filled media with the existing reader. Identity from the card label and photo; CID logged by firmware when available, not required |
| WP-17 Firmware skeleton, engine integration | Teensy port (SD read/write/flush, I²S out), shared engine unchanged | Goldens bit-identical to desktop at 1.0× (divergence blocks release); RAM/stack/.rodata budgets measured on target (G08); warm instant-on < 100 ms and commit latency < 200 ms, firmware-timed and judged by Michael (G04, ADR-208); resume position |
| WP-18 Second slot, insert detect, copy | Rear-slot source, front-slot destination, copy with LED-ring progress | Copy correctness; progress from the callback, never a timer. Copy *time* is not provable on the bench (SPI second slot); guardrail 10 stays a Phase 5 measurement |
| WP-19 Audio paths and caps | Codec; headphone/aux-out jack; aux in; speaker amplifier; microphone. Speaker mutes with headphones and while recording; aux in wins over mic as record source | Headphone cap 85 dB SPL (G11) and a separate speaker cap, both set in hardware/codec, re-asserted at boot, unreachable from controls; checked with a phone sound-level app at ≤ limit − 5 dB on the headphones in use and the speaker, recorded by Michael (ADR-208) |
| WP-20 Transport reading and status | Read the mechanical keys; depth-sensitive Rew/FF; copy button; LED-ring status; record light | No solenoid: firmware never moves a key. End of tape and cartridge-full shown on the LED ring; Rew/FF scrub speed follows press depth and works while Play is latched (spec revision at kickoff); record light per spec |
| WP-21 Bench acceptance demo | The firmware criteria run end to end | Michael's verdicts in [MICHAEL-CHECKS](MICHAEL-CHECKS.md) with firmware logs; Verification checks records against the candidate |

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

## 2. Round 1 (issued 2 Nov)

Contract: [FW-1](WP17-FIRMWARE-CONTRACT.md). Spec draft: [DRAFT-11](SPEC-DRAFT-11-PROPOSAL.md).

- **PM:** a spec revision covering
  - the speaker cap value (guardrail 11 revision);
  - end-of-tape and cartridge-full behaviour without a solenoid;
  - removal of the coil limits.
  
  Also the depth-sensitive scrub behaviour (ADR-200), and the WP-17 contract (port interface,
  bench pin map, golden-on-target method).
- **Hardware:**
  - the bench parts list for Michael's approval: Teensy 4.1, audio board, breadboard and
    wiring, keys and LEDs, second microSD breakout, small speaker and amplifier, MEMS mic,
    aux jacks, and the power-cut test's load switch. *Revised by ADR-208:* no bench logic
    analyser, SPL meter or coupler; instruments are about $30 in total (multimeter, optional
    clone logic analyser for debugging);
  - the power-cut test, simplified to a Teensy self-run test (ADR-208);
  - toy-safety acoustic limits for the speaker cap;
  - a depth-sensing approach for Rew/FF;
  - a copy-button placement.
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

**Hands-on acceptance (ADR-208).** For physical and timing criteria, the firmware measures
itself and logs the values; Michael tries the behaviour and records a verdict in
[MICHAEL-CHECKS](MICHAEL-CHECKS.md). Limits stay as targets. The output caps stay enforced in
the codec; a phone app checks them with a 5 dB margin. No lab instruments are bought.

Structural Rule 1 governs engine code. Firmware is a port and consumer: it must not fork seek,
mixing or any other engine behaviour (CLAUDE.md §6). Physical safety checks are done and recorded by
Michael; Verification checks the records, not instruments.

## 4. Carried in

- Q-P2-1: port-level batching, engine unchanged (ADR-195 §4).
- Deferred from Phase 2:
  - the G2 unaided app test;
  - macOS;
  - the ADR-196 limitations.
