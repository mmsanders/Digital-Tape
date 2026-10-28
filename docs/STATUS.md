# Project status

**PM622 · 28 October 2026 PDT · input main `4f5810b6` · Verification main `5512a2d0`.**
Phase 1 is complete (36/36). Phase 2 is at **7/12** rungs and in closeout under
[ADR-195](DECISIONS.md#adr-195--phase-2-closeout-proportional-evidence-and-the-make-path).
Windows 11 x64 is the only current release platform. macOS is deferred (ADR-191), and Linux
stays as CI. The [Phase 2 ledger](PHASE2-LEDGER.md) has every exit criterion row by row. The
[closeout plan](PHASE2-PLAN.md#8-closeout-plan-adr-195) has the rounds.

## Packages

| Package | Rungs | Where it stands |
|---|---:|---|
| WP-14 `tapectl` on real cards | 3/4 | Every criterion except A6 passed on Windows 11 by 14 Oct. A6 evidence is in hand (64 GB card, last-sector reads above 4 GiB). It needs a negative control and a disposition under ADR-195. |
| WP-16 Ingest | 3/4 | Built, independently cleared and integrated (`1695552d`). I1–I8 evidence is in hand, including Windows 11 byte-identity runs. Needs a final disposition under ADR-195, including the own-host check. |
| WP-15 App | 1/4 | Window, drop, ingest on drop, label, card discovery, messages and packaging are built and integrated. **Make is not built**: the button is hard-wired off and `tapectl make` is not in the shipping binary. |
| **Total** | **7/12** | |

## What changed this round (PM622)

- New PM review: [PM622](REVIEW/PM622-CLOSEOUT-RESET.md) explains why rungs moved 6 → 7 in
  eleven days. The evidence demanded had outgrown the criteria. Work had moved to what could be
  proved rather than what was missing. Make had no implementation issue after ~18 Oct.
- ADR-195: outcome tests plus negative controls; no separate method-qualification or
  session-admission rounds; A6, WP-16 own-host, G1 and G3 methods clarified; `make` built now on
  the accepted WP-14 provision open; **Q-P2-1(b) ruled: port-level batching, engine unchanged.**
- APP-1, APP-1A and INGEST-1 amended to match. No criterion, guardrail or frozen interface
  changed.
- Recorded: Verification #361 disposed the single #618 native session as a bounded PASS. The
  app window opened and closed normally. Its background poller ran `tapectl cards` twice and got
  `offered 0` with no card inserted. The app ran unelevated at Medium integrity. No rung moved.

## Current assignments (manual activation, ADR-192)

| Owner | Issue | Outcome wanted |
|---|---|---|
| Software | [#624](https://github.com/mmsanders/Digital-Tape/issues/624) | `tapectl make`, UAC elevation of that one child, Make button wired, one Windows candidate ZIP |
| Verification | [V#364](https://github.com/mmsanders/digital-tape-verification/issues/364) | Stage 1: dispose WP-14 and WP-16 under ADR-195; author WP-15 tests and the C2 checklist. Stage 2: dispose Software's head |
| Michael | [#623](https://github.com/mmsanders/Digital-Tape/issues/623) | Merge the PM622 PR (the go signal), confirm or veto ADR-195, book the C2 session and G2 |

Software and Verification Stage 1 run in parallel. Verification Stage 2 waits on Software's
return. Leads start only when Michael starts them. No listener, kickoff or subworker.

## Next rounds

C2 is Michael's ~45-minute real-card session with the candidate. C3 is the final WP-15
disposition and G2 (his wife, unaided, witnessed). C4 is the exit ADR. Details in the
[closeout plan](PHASE2-PLAN.md#8-closeout-plan-adr-195).

## Holds that stand

- Guardrails 01–13; engine pinned at A8 `d96b4245`; format frozen; Structural Rule 1 for engine
  code; Verification independence and blindness.
- WP-14 A4 disk safety outranks everything. Make ships only after independent disposition.
  The app and ingest never run elevated.
- Hardware, firmware, fabrication and charging are parked. Card atomicity is unqualified.
  Phase 3 entry items from Q-P2-1: any-subset coverage of deferred faults, and guardrail 10
  measured on target.
- macOS deferred; WP-38 not taken.

## Preserved references

[PM622 review](REVIEW/PM622-CLOSEOUT-RESET.md), prior [PM620](REVIEW/PM620-METHOD-CONTROLS.md),
[verification integration](VERIFICATION-INTEGRATION.md), [package index](PACKAGES/README.md),
[human queue](FOR-MICHAEL.md). Earlier status revisions are unchanged in Git history
(PM620 status at `4f5810b6:docs/STATUS.md`).
