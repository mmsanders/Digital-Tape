# Phase 3 plan — bench firmware

**PROPOSED by PM634, 1 November 2026 PDT ([ADR-198](DECISIONS.md#adr-198--phase-2-closed-g2-deferred-host-scope-frozen-phase-3-proposed)).**
Nothing in this file assigns work or opens Phase 3. Michael answers the kickoff decisions in §4
(issue [#635](https://github.com/mmsanders/Digital-Tape/issues/635)). "Go with the defaults" is a
complete answer. Work is then assigned in role-labeled issues, as in Phase 2.

## 1. What Phase 3 delivers

**Goal:** the Phase 1 engine runs on a Teensy 4.1 bench build and plays a cartridge made by the
Phase 2 app through headphones, with real buttons.

**Milestone:** Michael makes a cartridge with the app, puts it in the bench build, presses Play
and hears it. Scrub, stop and a short overdub work. Pulling the cartridge and putting it back
resumes near where it stopped.

| Package | Delivers | Key criteria (`spec/acceptance.md` "Firmware criteria", guardrails) |
|---|---|---|
| WP-17 Firmware skeleton, engine integration | Teensy port: SD device read/write/flush, I²S audio out, the shared engine unchanged | Goldens bit-identical to desktop at 1.0× (a divergence blocks release, CLAUDE.md §6); RAM/stack/.rodata budgets measured on target (G08); warm instant-on < 100 ms on a logic analyser (G04); commit latency < 200 ms; resume position; end of tape |
| WP-18 Dual card, hot-swap, copy with LED row | Second card slot, insert/remove detect, cartridge copy with progress LEDs | Copy *correctness* and progress from the callback, never a timer. Copy *time* is not provable on the bench (ADR-103: SPI second slot); guardrail 10 stays a Phase 5 measurement |
| WP-19 Line-in, mic, gain, output limit | Codec bring-up, record inputs, output cap | 85 dB SPL cap set in the codec, re-asserted every boot, unreachable from controls; measured with SPL meter and coupler, **witnessed by Michael** (G11) |
| WP-20 Button matrix, transport, interlock | Play/stop/scrub/record controls and record interlock | Record light and interlock per spec; scrub ramp per spec. Transport mechanism (solenoid or not) depends on the WP-04/owner-layout decision (D5) |
| WP-21 Bench acceptance demo | The firmware criteria table run end to end | Michael-witnessed record; Verification audits method and raw data |

**Phase 3 exit gate (proposed):**
1. WP-17 to WP-21 independently accepted on the bench build.
2. Goldens bit-identical on firmware at 1.0×. Phase 1/2 goldens and replays still green on main.
3. Media atomicity (WP-05 A-6) run on the PNY cards: at least 1,000 qualifying cuts per exact
   SKU/revision, zero torn blocks. A torn block is a blocker for the format, not a firmware fix.
4. Q-P2-1 entry conditions met before any firmware write batching is enabled (ADR-195 §4).

**Not in Phase 3:**
- board fabrication, cells or charging (the fabrication gate stays CLOSED);
- enclosure and cartridge CAD (Phase 4);
- the SDR50/UHS-I port and the < 30 s copy proof (Phase 5);
- any engine or format change, apart from ADR-169's read-only exception;
- desktop app changes, except the deferred G2 work below.

## 2. Carried into Phase 3

- **Q-P2-1 (ADR-195 §4):** port-level batching, engine unchanged. Before firmware batching is
  enabled, Verification completes any-subset coverage of the 365 deferred load faults and the six
  unexecuted long-copy cuts.
- **Hardware park (ADR-160)** ends only for the bench scope in D3. Owner layout #569 and the
  prototype record stay filed for Phase 4.
- **Deferred from Phase 2 (ADR-198):**
  - the G2 unaided app test (pinned, with a possible mini app redesign round);
  - macOS;
  - the Phase 2 limitations in ADR-196.

## 3. How the work runs

ADR-195 carries over:
- outcome tests plus a negative control;
- no separate method rounds;
- outcome-sized issues;
- same-issue stage continuation;
- the criterion ledger as the progress record.

Structural Rule 1 still governs engine code. Firmware is a port and consumer: it must not fork
seek, mixing or any other engine behaviour (CLAUDE.md §6). Verification authors firmware tests from
`spec/acceptance.md` and the WP-17 contract without reading firmware first. Physical safety
measurements are witnessed by Michael and audited by Verification (method, instrument,
calibration, raw data, uncertainty).

**Proposed first round (R1), if D1–D9 are answered:**
- **PM:** issue the WP-17 contract: port interface, bench pin map (a subset of `spec/hw/board-rev-a.md`), the golden-on-target method.
- **Hardware:** draft the bench parts cart and wiring for Michael's approval. Also draft the atomicity rig.
- **Verification:**
  - author WP-17 acceptance: goldens on target, budgets, wake latency method;
  - complete the Q-P2-1 any-subset coverage.
- **Software:** start the firmware skeleton, building and running engine-on-port tests off-target until parts arrive.
- **Michael:** approve and order the cart.

## 4. Kickoff decisions

| # | Decision | Owner | Recommended default |
|---|---|---|---|
| D1 | Open Phase 3 | Michael | Go |
| D2 | Thin path first | PM/Michael | WP-17 plays an app-made cartridge over headphones with Play/Stop before WP-18–21 start |
| D3 | Unpark Hardware for the bench | Michael | Yes, bench-only: parts cart, wiring, atomicity rig. No fabrication, no cells, no enclosure |
| D4 | Bench parts purchase | Michael (wallet) | Hardware drafts one cart; Michael approves it before anything is ordered. Tell PM what you already own (Teensy 4.1? audio board? logic analyser? SPL meter and coupler? reference headphones?) |
| D5 | Transport on the bench | Michael | Plain momentary switches. The solenoid or solenoid-free decision waits for WP-04/WP-22 and owner layout #569 |
| D6 | WP-19 order | PM | Output cap with first codec bring-up (safety first); line-in and mic after WP-17/18 |
| D7 | Card atomicity in Phase 3 | Michael | Yes, as a parallel Hardware/Verification lane on the PNY cards, using the Teensy as the rig controller |
| D8 | Roles and runtimes | Michael | As Phase 2: Software (firmware) is local Windows Claude Code with the Teensy over USB; Verification separate and independent; Hardware unparked bench-only; PM as now |
| D9 | Process | PM | ADR-195 carries over (§3) |
