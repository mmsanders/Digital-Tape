# Project status

**PM627 · 29 October 2026 PDT · input main `ea54a418` · Verification main `3ff22aae`.**
Phase 1 is complete (36/36). Phase 2 is at **11/12** rungs, in closeout under ADR-195 and
[ADR-196](DECISIONS.md#adr-196--c1-disposed-phase-2-at-1112-c2-and-g2-queued). Windows 11 x64 is
the only current release platform; macOS is deferred and Linux stays as CI.
- [Phase 2 ledger](PHASE2-LEDGER.md): every exit criterion, row by row.
- [Closeout plan](PHASE2-PLAN.md#8-closeout-plan-adr-195): the rounds.

## Packages

| Package | Rungs | Where it stands |
|---|---:|---|
| WP-14 `tapectl` on real cards | 4/4 | **Accepted** (Verification #364). A1–A9 pass on Windows 11. |
| WP-16 Ingest | 4/4 | **Accepted** (Verification #364). I1–I8 and own-host pass. |
| WP-15 App | 3/4 | Make built, cleared and merged at `ea54a41`. G1/G3/G4/G5 tests pass in CI. Michael's real-card C2 session is next, then G2. |
| **Total** | **11/12** | |

## What happened in round C1

- **Verification #364 Stage 1** accepted WP-14 and WP-16 under ADR-195. A6 closed with a compiled
  32-bit offset mutant beside the existing 64 GB card evidence. It also authored the WP-15
  tests and the C2 checklist.
- **Software #624** built `tapectl make` and the app's Make button:
  - provision's own safety and open, with one retained handle for load and NULL-write verify;
  - `CARD_CHANGED` on a reported removal;
  - one UAC prompt, naming tapectl only.
- **Verification found three defects across four passes**, all in query-failure handling,
  including a real Windows volume-census gap that also affected standalone `provision`. Software
  corrected them on the same branch. The final exact head `5101e3f3` was cleared and merged at
  `ea54a41` with an identical tree and 130 checks green.
- The cleared C2 candidate is ZIP `b8a689cf…`; hashes are in [#628](https://github.com/mmsanders/Digital-Tape/issues/628).

## Current assignments (manual activation, ADR-192/195)

| Owner | Issue | Outcome wanted |
|---|---|---|
| Michael | [#628](https://github.com/mmsanders/Digital-Tape/issues/628) | C2: ~45 minutes with the cleared candidate and one PNY card, per Verification's checklist; return on #628 |
| Verification | [V#370](https://github.com/mmsanders/digital-tape-verification/issues/370) | Stage A now: supersede stale "Make disabled" assertions. Stage B after C2: dispose G1/G3/G4/G5 |

No Software task while C2 is pending: any product change would invalidate the cleared candidate.
Michael starts each issue; a started lead may continue to the next stage of the same issue if its
input has arrived. No listener, polling, kickoff or subworker.

## Next rounds

1. **C3:** if C2 passes, G2 with Michael's wife ([protocol](WP15-G2-PROTOCOL.md)) on the same
   candidate. If C2 finds defects, PM opens one Software correction issue, and the corrected
   candidate gets its own clearance before G2.
2. **C4:** the exit ADR: host scope frozen, goldens green, Q-P2-1 recorded.

## Holds that stand

- Guardrails 01–13; engine pinned at A8 `d96b4245`; format frozen; Structural Rule 1 for engine
  code; Verification independence.
- WP-14 A4 outranks everything. The app and ingest never run elevated.
- Hardware, firmware, fabrication and charging are parked. Card atomicity is unqualified.
- Phase 3 entry items: any-subset coverage of deferred faults, and guardrail 10 measured on target.
- Accepted Phase 2 limitations (ADR-196):
  - elevated-launch race from a user-writable folder (same-user only);
  - no stale job cleanup after a crash;
  - typed `NOT_READY` rows;
  - undetected equal-size swap.

## Preserved references

[PM622 review](REVIEW/PM622-CLOSEOUT-RESET.md), [verification integration](VERIFICATION-INTEGRATION.md),
[package index](PACKAGES/README.md), [human queue](FOR-MICHAEL.md). Earlier status revisions are
unchanged in Git history.
