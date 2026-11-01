# Project status

**1 November 2026 PDT. Phase 2.5 cleanout** ([#637](https://github.com/mmsanders/Digital-Tape/issues/637)).
Phases 1 and 2 are complete. Phase 3 (bench firmware) opens after this cleanout.

## Completed

| Phase | Result |
|---|---|
| 1 Audio engine | 36/36 accepted (3 Oct 2026) |
| 2 Desktop tooling | 12/12, with the G2 unaided test deferred (1 Nov 2026). `tapectl` on real cards, ingest and the one-window app are accepted for Windows 11. Michael made real cartridges through the app |

Package detail: [packages](PACKAGES/README.md) and [verification integration](VERIFICATION-INTEGRATION.md).
The desktop tool's scope is frozen (ADR-198): it loads cartridges, nothing more.

## Next: Phase 3

[Phase 3 plan](PHASE3-PLAN.md):
- the shared engine on a Teensy 4.1 bench build, with keys, LED status, headphones and speaker;
- the card power-cut test on the PNY cards;
- the deferred crash coverage before firmware write batching.

Hardware returns for bench work and drafts the parts list; Michael owns no bench equipment yet.

The device design has moved: mechanical latching keys and no solenoid, a speaker with its own
loudness cap, a microphone, two aux ports. See [DEVICE-DESIGN](DEVICE-DESIGN.md). Its
open questions (§6) are with Michael.

## Current assignments

None. Phase 3 issues follow when Michael opens the phase.

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
