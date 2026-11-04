# Project status

**4 November 2026 PDT. Phase 3 OPEN** ([ADR-201](DECISIONS.md#adr-201--phase-3-opened-round-1-issued)). Phases 1 and 2 are complete.
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

Round 2 continuation after [PM661 review](REVIEW/PM661-P3-2026-11-04.md)
and ADR-206 (Michael starts each issue manually):

| Owner | Issue | Outcome |
|---|---|---|
| Software | [#663](https://github.com/mmsanders/Digital-Tape/issues/663) | First: own Hardware PR646 current-main integration/CI/merge; conditional PM scope sign-off issued |
| Software | [#658](https://github.com/mmsanders/Digital-Tape/issues/658) | Restore mandatory Windows/Linux retained census; separate narrow review-regression gate PR after independent tests |
| Software | [#652](https://github.com/mmsanders/Digital-Tape/issues/652) | Corrected kit0db6ce5c awaits independent disposition; preserve original/import/fix lineage |
| Verification | [V#394](https://github.com/mmsanders/digital-tape-verification/issues/394) | Dispose ready corrected kit; publish new two-platform census and ordering-policy tests before implementation |

Hardware651 is returned/closed. V392 publication2fc2298b clears the exact c55e5ad
judge's bounded artifact-consistency corrections (339 published +3 CLI cases).
PR646 head443a5a53 keeps judge blobd4ab1866 and adds published CLI regressions/wiring;
CI41907017746 and integrity41907017664 are green, but current-main integration remains.
Software663 owns that handoff. Carry clearance by identity; no repeat acceptance for
a base-only change. Physical method remains NOT CLEARED.
Kit0db6ce5c reports fixed SW652-R1..R3 and passing controls; V394 must dispose it.
CI660/e0b6bb02 remains HOLD SW658-R1 despite111 green checks: Git identity does not
replace downloaded Windows/Linux evidence completeness and byte authentication.
PM retains that mandatory coverage and the unchanged three-platform manual route.
Review-regression imports get a narrow independently tested provenance/order route;
ordinary new behavior stays tests-first, no history rewrite or gate bypass.
Michael's CODEOWNERS approval covers matching @mmsanders entries for these bounded
imports/corrections, including be1_review_r1; protection and independent review remain.
No target/package advance: **1/12** (F6); integrated FW-1 aa472667 carries.
All365 deferred faults pass; six long cuts unavailable/unexecuted; batching held.
Rig unbuilt/NOT CLEARED; E0-E4/dry controls unmeasured; SPI is not native qualification.
Target PCM/I2S/instance/stack/timing/removal and DRAFT-11 remain pending. No physical
session ready. Last owner-confirmed parts status: not ordered; changed cart unapproved.

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
