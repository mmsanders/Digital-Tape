# Project status

**2 November 2026 PDT. Phase 3 OPEN** ([ADR-201](DECISIONS.md#adr-201--phase-3-opened-round-1-issued)). Phases 1 and 2 are complete.
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

See [DEVICE-DESIGN](DEVICE-DESIGN.md). Still open: the copy button and the promote-B-to-A
key combination.

## Current assignments

Round 1 (Michael starts each):

| Owner | Issue | Outcome |
|---|---|---|
| Hardware | [#641](https://github.com/mmsanders/Digital-Tape/issues/641) | Bench parts list (minimum and full, for Michael's approval); card power-cut rig design; speaker loudness limit research; Rew/FF depth-sensing approach; copy-button options |
| Software | [#642](https://github.com/mmsanders/Digital-Tape/issues/642) | Returned #647 `ee478a91`, 117 checks pass; integration HELD pending V378 corrected admission disposition. Host F1/static F2 pass; target halves pending |
| Verification | [V#378](https://github.com/mmsanders/digital-tape-verification/issues/378) | Publish explicit FW-1 recognition correction, preserve original package, re-dispose unchanged Software head; V374 publications carry |

Latest [PM648 review](REVIEW/PM648-P3-R1-2026-11-02.md) / ADR-202: F6 passes on the held
candidate (**1/12** defined package criteria). V41995965 passes all 365 deferred faults;
six long cuts are unavailable on the issued fixture, not executed. Batching stays held.
V3d616c14: rig method NOT CLEARED (R374-1…5); Hardware #641 owns corrections. SPI
characterization is not native SD4 qualification. DRAFT-11 preflight requires revision;
proposal remains unissued. Target PCM/I²S, stack, timing and controls/removal await the bench.

## Holds that stand

- Guardrails 01–13; engine pinned at `d96b4245`; format frozen; Structural Rule 1 for engine
  code; Verification independence.
- Host scope frozen. The app and ingest never run elevated; WP-14 A4 disk safety outranks
  everything.
- Fabrication and charging CLOSED. No card is qualified yet.
- Deferred, not waived:
  - G2: run [the protocol](WP15-G2-PROTOCOL.md) before the app goes to anyone else for real use;
  - macOS;
  - the ADR-196 limitations.

[Hardware status](STATUS-HARDWARE.md) · [human queue](FOR-MICHAEL.md) · [decisions index](DECISIONS-INDEX.md)
