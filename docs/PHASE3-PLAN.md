# Phase 3 plan — bench firmware

**OPEN since 2 November 2026** ([ADR-201](archive/DECISIONS-ADR-001-209.md#adr-201--phase-3-opened-round-1-issued)). Work is assigned in
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

## 2. Order of work

Updated 16 November ([ADR-210](DECISIONS.md#adr-210--light-process-outside-the-engine)).
Contract: [FW-1](WP17-FIRMWARE-CONTRACT.md). Spec draft: [DRAFT-11](SPEC-DRAFT-11-PROPOSAL.md).

1. **Michael orders group 1** of [the parts list](../hardware/sourcing/PHASE3-BENCH.md).
2. **Bring-up and WP-17** on the bench: play a real cartridge, then goldens, warm wake,
   stack and removal ([ledger](PHASE3-LEDGER.md)).
3. **WP-19 recording and the headphone cap**, then **WP-18 second slot and copy** (group 2
   parts).
4. **WP-20 keys, depth-sensitive scrub and LEDs.** Hardware proposes the depth sensor.
5. **WP-05 power-cut test** on the PNY cards (group 3 parts), any time after step 2.
6. **WP-21 bench demo.**

DRAFT-11 (speaker cap, end-of-tape and cartridge-full without a solenoid, depth-sensitive
scrub) is finished once Michael approves the speaker limit. It is needed before WP-19 and
WP-20 are judged, not before bring-up.

## 3. How the work runs

Light track (CLAUDE.md §3): one lead, one session, one PR per step, with the author's own
tests and a host-side check where one is possible. The firmware measures itself and prints
the numbers; Michael tries the behaviour and records a verdict in
[MICHAEL-CHECKS](MICHAEL-CHECKS.md) (ADR-208). Limits stay as targets. The output caps stay
enforced in the codec, and a phone app checks them with a 5 dB margin. No lab instruments.

Firmware is a consumer of the engine: it must not fork seek, mixing or any other engine
behaviour (CLAUDE.md §6). No engine change is planned; one would be strict track.

## 4. Carried in

- Q-P2-1: port-level batching, engine unchanged (ADR-195 §4).
- Deferred from Phase 2:
  - the G2 unaided app test;
  - macOS;
  - the ADR-196 limitations.
