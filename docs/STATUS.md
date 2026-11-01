# Project status

**PM634 · 1 November 2026 PDT · input main `3bf43471` · Verification main `1938e651`.**
**Phase 1 complete (36/36). Phase 2 CLOSED (12/12, G2 deferred) under
[ADR-198](DECISIONS.md#adr-198--phase-2-closed-g2-deferred-host-scope-frozen-phase-3-proposed).**
Phase 3 (bench firmware) is PROPOSED and waits on Michael's kickoff decisions.

## Phase 2 outcome

| Package | Result |
|---|---|
| WP-14 `tapectl` on real cards | **Accepted**, Windows 11 (Verification #364) |
| WP-16 Ingest | **Accepted**, Windows 11 (Verification #364) |
| WP-15 App | **Accepted with G2 deferred**: G1/G3/G4/G5 on exact `5101e3f3` / ZIP `b8a689cf` (Verification #364, #370; ADR-197). Michael made real cartridges through the app in C2 |

- Exit items: goldens and replays green on the last code head (`ea54a41`, engine `d96b4245`);
  Q-P2-1 ruled (ADR-195 §4); host scope frozen (ADR-198).
- Record: the [Phase 2 ledger](PHASE2-LEDGER.md) and [PM622 review](REVIEW/PM622-CLOSEOUT-RESET.md).
- The closeout took four PM rounds from the 28 October reset.

**Deferred, not waived:**
- **G2** unaided test: before the app goes to anyone else for real use, or on request. A mini
  app redesign round follows if needed.
- macOS.
- The ADR-196 limitations:
  - elevated-launch race from a user-writable folder;
  - no stale-job cleanup after a crash;
  - typed `NOT_READY` rows;
  - undetected equal-size swap.

## Phase 3 — proposed

[Phase 3 plan](PHASE3-PLAN.md):
- **Goal:** the shared engine runs on a Teensy 4.1 bench build and plays an app-made cartridge
  through headphones, with real buttons.
- **Packages:** WP-17 to WP-21.
- **Also in scope:** card atomicity on the PNY cards, and the Q-P2-1 entry conditions.

Michael answers D1–D9 and says what equipment he owns in
[#635](https://github.com/mmsanders/Digital-Tape/issues/635).

## Current assignments

| Owner | Issue | Outcome wanted |
|---|---|---|
| Michael | [#635](https://github.com/mmsanders/Digital-Tape/issues/635) | Phase 3 kickoff decisions and equipment on hand |

No lead task is open. Leads start only when Michael starts them (ADR-192/195).

## Holds that stand

- Guardrails 01–13; engine pinned at `d96b4245`; format frozen; Structural Rule 1 for engine
  code; Verification independence.
- Host scope frozen (ADR-198).
- The app and ingest never run elevated. WP-14 A4 outranks everything.
- Hardware stays parked (ADR-160) until Phase 3 D3.
- Fabrication and charging stay CLOSED. Card atomicity is unqualified.
- Phase 3 entry items: any-subset coverage before firmware batching; guardrail 10 measured on target.

## Preserved references

[Phase 2 plan](PHASE2-PLAN.md), [verification integration](VERIFICATION-INTEGRATION.md),
[package index](PACKAGES/README.md), [human queue](FOR-MICHAEL.md). Earlier status revisions are
unchanged in Git history.
