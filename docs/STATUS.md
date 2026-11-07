# Project status

**6 November 2026 PST. Phase 3 OPEN** ([ADR-201](DECISIONS.md#adr-201--phase-3-opened-round-1-issued)). Phases 1 and 2 are complete.
Progress: [Phase 3 ledger](PHASE3-LEDGER.md).

## Completed

| Phase | Result |
|---|---|
| 1 Audio engine | 36/36 accepted (3 Oct 2026) |
| 2 Desktop tooling | 12/12, with the G2 unaided test deferred (1 Nov 2026). `tapectl` on real cards, ingest and the one-window app are accepted for Windows 11. Michael made real cartridges through the app |

Package detail: [packages](PACKAGES/README.md) and [verification integration](VERIFICATION-INTEGRATION.md).
The desktop tool's scope is frozen (ADR-198): it loads cartridges, nothing more.

## Phase 3

[Phase 3 plan](PHASE3-PLAN.md):
- the shared engine on a Teensy 4.1 bench build, with keys, LED status, headphones and speaker;
- the card power-cut test on the PNY cards;
- the deferred crash coverage before firmware write batching.

The device design has moved:
- mechanical latching side keys and no solenoid (LED status instead);
- depth-sensitive Rew/FF;
- a speaker with its own loudness cap;
- a microphone, aux in, and aux out shared with the headphone jack.

See [DEVICE-DESIGN](DEVICE-DESIGN.md).

**Acceptance method changed (ADR-208, 6 Nov).** Physical and timing criteria are now
firmware-timed and judged by Michael, recorded in [MICHAEL-CHECKS](MICHAEL-CHECKS.md). The caps
stay enforced in the codec and are checked with a phone app with a 5 dB margin. Instruments
are about $30; there is no lab gear. CID is no longer required. The power-cut test is
Teensy self-run. Next: Hardware revises the cart and the test, and Verification preflights
the DRAFT-11 delta (issues posted for Michael to start). Still open: the copy button and the promote-B-to-A
key combination.

## Current assignments

Round 2 continuation after [PM666 review](REVIEW/PM666-P3-2026-11-05.md)
and ADR-207 (Michael manually starts issues):

| Owner | Issue | Outcome |
|---|---|---|
| Software | [#667](https://github.com/mmsanders/Digital-Tape/issues/667) | First: restore wp11-portability job on Ubuntu24.04; unchanged differential and detecting gates |
| Verification | [V#397](https://github.com/mmsanders/digital-tape-verification/issues/397) | Review ready census660/d8ead444 and ordering665/8ce0fe52 now; review runner pin when returned |
| Software | [#658](https://github.com/mmsanders/Digital-Tape/issues/658) | After independent clearance/runner repair, integrate both CI corrections with required current-base CI green |
| Software | [#652](https://github.com/mmsanders/Digital-Tape/issues/652) | Kit behavior CLEARED at0db6ce5c; final approved provenance/ownership/base integration after CI prerequisites |

Software663 completed Hardware PR646 integration at60dfe6aa (head168b7dc0).
V392 clearance carries unchanged judge/import identities;52 current-base checks pass,
15 classifier-unselected qualification skips. Hardware651/663 are complete.
Physical rig/method remains unbuilt/NOT CLEARED; no new Hardware task for base sync.
V394 kit publication80d93c50 independently clears SW652-R1..R3 at0db6ce5c:
109/4/53/47 plus8 review cases,32 old controls plus6 predicates and old-pair negative
control. This is bounded off-target consistency, not target or package acceptance.
V394 policy publication8790e20d binds new supported census/order packages before
Software implementation. Returned PR660/d8ead444 and PR665/8ce0fe52 are ready for
V397 review; Software25-case replays are readiness, not clearance.
Current failures are arm-m3 portability and regression aggregate on Ubuntu26.04;
main41910086479 passed on60dfe6aa. PM adopts narrow job-only Ubuntu24.04 pin.
No kernel/emulator cause is proven, no CI waiver or comparison change authorized.
Independent registry attests review/publication chronology; Git proves identity/order.
Final metadata-only provenance after the fix avoids a future-SHA cycle; old imports
stay fixed. CODEOWNERS matching-owner approval carries; protections remain.
No target/package advance: **1/12** (F6); FW-1 aa472667 and engine d96b4245 carry.
365 deferred faults pass; six long cuts unavailable/unexecuted; batching held.
E0-E4/dry controls unmeasured; SPI is not native qualification. Target PCM/I2S,
instance/stack/timing/removal and DRAFT-11 pending. Parts last confirmed not ordered;
changed cart unapproved. Parts criterion now BLOCKED; no physical session ready.

## Holds that stand

- Guardrails 01–13; engine pinned at `d96b4245`; format frozen; Structural Rule 1 for engine
  code; Verification independence.
- Host scope frozen. The app and ingest never run elevated; WP-14 A4 disk safety outranks
  everything.
- Fabrication and charging CLOSED. No card is qualified yet.
- Deferred, not waived:
  - G2: run [the protocol](WP15-G2-PROTOCOL.md) before the app goes to anyone else for real use;
  - macOS (ADR-205: retained manual checks, excluded from normal required aggregates);
  - the ADR-196 limitations.

[Hardware status](STATUS-HARDWARE.md) · [human queue](FOR-MICHAEL.md) · [decisions index](DECISIONS-INDEX.md)
