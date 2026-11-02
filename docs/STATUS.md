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
| Software | [#642](https://github.com/mmsanders/Digital-Tape/issues/642) | Teensy firmware skeleton per [FW-1](WP17-FIRMWARE-CONTRACT.md): build, SD partition view, play path, golden hook, CI size gates |
| Verification | [V#374](https://github.com/mmsanders/digital-tape-verification/issues/374) | Q-P2-1 completion; WP-17 acceptance tests; [DRAFT-11](SPEC-DRAFT-11-PROPOSAL.md) preflight; its repo's baseline; then Software's head and the rig method |

All three can start now; none needs parts. Target-side checks wait for the bench.

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
