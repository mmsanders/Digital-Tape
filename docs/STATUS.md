# Project status

**PM630 · 30 October 2026 PDT · input main `1d341573` · Verification main `1938e651`.**
Phase 1 is complete (36/36). Phase 2 is at **11/12** rungs, in closeout under ADR-195/196 and
[ADR-197](DECISIONS.md#adr-197--c2-disposed-rejected-drop-notice-needs-no-show-details-g2-issued). Windows 11 x64 is
the only current release platform; macOS is deferred and Linux stays as CI.
- [Phase 2 ledger](PHASE2-LEDGER.md): every exit criterion, row by row.
- [Closeout plan](PHASE2-PLAN.md#8-closeout-plan-adr-195): the rounds.

## Packages

| Package | Rungs | Where it stands |
|---|---:|---|
| WP-14 `tapectl` on real cards | 4/4 | **Accepted** (Verification #364). A1–A9 pass on Windows 11. |
| WP-16 Ingest | 4/4 | **Accepted** (Verification #364). I1–I8 and own-host pass. |
| WP-15 App | 3/4 | G1, G3, G4 and G5 complete: C2 real-card session passed (Verification #370). Only G2 remains. |
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

## Round C2 (done)

Michael ran the C2 checklist with the exact cleared ZIP on Windows 11 Home 25H2. Verify was OK
on the first make and on the remake. Dumps were byte-identical. The mid-make pull and remake
behaved as specified, there were no lists, and polling stayed usable. The one finding (F370-1,
no Show details on a rejected single-song drop) is ruled intended in ADR-197. No rebuild.

## Current assignment (manual activation, ADR-192/195)

| Owner | Issue | Outcome wanted |
|---|---|---|
| Michael | [#631](https://github.com/mmsanders/Digital-Tape/issues/631) | G2: his wife's unaided run with the same ZIP, per [the protocol](WP15-G2-PROTOCOL.md). Return on #631 |

No Software or Verification task is open; none is needed before G2.

## Next rounds

1. **C3:** G2 (#631). If it fails, PM decides any fix; a second G2 needs a tester who hasn't seen
   the app.
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
