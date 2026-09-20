# Project status

**20 September 2026 UTC · main `d63b73d` · Owner: PM ·** Phase 1 holds three
independently accepted tranches (289 mount cases, ten playback families, two VT8-001
operation cases); no package, source or golden is accepted and the dashboard stays at
13 of 36.

This file is a state table, not a chronicle. Round-by-round narrative through P1-R24
is preserved verbatim in [the September status history](archive/status-history/2026-09-status.md).
Per-round integration narrative is in
[the verification integration history](archive/verification-integration-history.md).
Active assignments and stop conditions live only in
[role-labeled issues](ISSUE-WORKFLOW.md); this file records evidence, not work directions.

## Phase 1 packages

| Package | Independently accepted | Outstanding | Next owner |
|---|---|---|---|
| WP-06 block device, superblock, index commit | Exact 289/289 mount observations including row 3, at verifier `392d6bb9...` | Source and helper design; complete WP-06 package | Held — Software, scoped issue only |
| WP-07 chunk allocator, copy-on-write Side B | Two exact recorded observations — `VT8-001-RB-ALLSLOT` and `VT8-001-REC-ALLOCSEQ` — at verifier `e77b61f...`, re-confirmed on the clean PR #112 split at `391d6a8...` | Invented splice-only and stage-1 BUSY refusal policies; every unexercised branch; source; complete WP-07 | Held pending a later independently tested tranche |
| WP-08 playback, seek, variable-rate scrub | Exact ten corrected-cadence product observations, 698/698 per-render service in each direction, at verifier `392d6bb9...` | Source and helper design; complete WP-08; listening and goldens | Held — separate listening/golden route |
| WP-09 record: overwrite, overdub, splice | None | Contract issued; corresponding independent tests must land before implementation | Verification |
| WP-10 crash-injection harness | Narrow independent mount package landed | Complete crash/operation/state run is not green | Verification |
| WP-11 CLI harness and golden regression | Seven exact product PCM outputs byte-match verifier candidates | Candidate PCM is unlistened and is not an accepted golden; golden CI stays red | Held — needs Michael's own listening |
| WP-12 re-spool / defragment pass | None | Independent WP-12a coverage and acceptance | Verification |
| WP-13 embedded-readiness audit | None | Held #20 measurements (instance 156456 B, stack 1536/8192, rodata 1040/32768) are implementer evidence, not package acceptance | Held |
| WP-36 slot capability model | None | Contract issued; corresponding independent tests must land before implementation | Verification |

Engine implementation status: 16 of 21 public entry points are defined. `tape_abort`,
`tape_dup`, `tape_format`, `tape_promote` and `tape_respool` are declared and undefined.
Code exists well ahead of accepted coverage; that gap is coverage, not implementation.

## Held and next owner

| Work | State | Next owner |
|---|---|---|
| #20 engine | Held draft at `2e0e8a4...`; not an ancestor of main. Only the separate clean PR #77 mount/playback slice was merged. No wholesale import of allocator, recording, warm/state or other uncovered behavior. | Held; Software may work only from current scoped issues |
| VT8-001 / WP-07 | PR #112 is integrated at main `be7f8f2...` with exact accepted history preserved. Verification independently accepts only its two recorded observations; source, invented refusal policies, unexercised branches and complete WP-07 remain unaccepted | Held pending a later independently tested tranche; PR #96 remains held |
| WP-10 / operations freeze | Infrastructure present, actual complete engine crash run not green | Verification |
| WP-11 | Exact corrected-cadence product PCM hashes are independently byte-compared, but candidate PCM remains unlistened and is not an accepted golden; golden CI stays red | Held pending a separately issued listening/golden route |
| Hardware | Verification rejects PR #87 repaired head `e520c2c...` on `P1-R23-V01`'s eleven adjacent forms. PR #92 head `0943571...` remains held. PR #120 head `7b224ff...` is a stale-base, advice/method candidate awaiting independent A1MINI-01 audit. Timing stays PROVISIONAL and fabrication/charging stay CLOSED with five blockers | Hardware repairs PR #87; Verification audits exact PR #120 method without printing |
| Q-001 | Closed: Michael signed the exact scoped freeze on 8 September 2026 | PM recorded approval |
| WP-04 / WP-05 | Existing library test stays on the expected Monday library route; new prints default to the A1 Mini, with the library retained for oversized PLA. PR #87 is independently rejected; A1MINI-01 is unprinted and unaudited; identity, attribution, atomicity and qualification remain open | Hardware card-method repair plus Verification A1MINI-01 method audit; no Michael purchase/print issue |

## Risks

1. **Card atomicity is unqualified.** No media is qualified to WP-05 A-2; PR #87's method is independently rejected on `P1-R23-V01` and no new acquisition may run.
2. **Solenoid timing is unresolved** at the actual rail and parts; timing stays PROVISIONAL and the fabrication/charging gate stays CLOSED with five blockers.
3. **Mechanism and creep trials are unprinted.** A1MINI-01 rev 1 is an unprinted, unaudited method candidate; CAD checks are not measurements.
4. **Engine code is held by coverage, not by implementation.** Roughly 80% of the code exists against three accepted tranches; every further rung needs independent tests first.
5. **WP-11 goldens are missing by design.** Golden CI is red until Michael listens; no process change substitutes for that.

## Standing boundaries

**New independent package acceptances: none.** The three accepted tranches above are
exact recorded observations only — not source, helper design, complete WP-06/WP-07/WP-08,
merge status or goldens. Main ruleset 22084355 is active and strict. Missing WP-11 goldens
remain an explicit red gate.

Phase 1 operating format, role charters and the issue workflow are in
[CLAUDE.md §7](../CLAUDE.md), [role charters](ROLES/README.md) and
[the issue workflow](ISSUE-WORKFLOW.md). Hardware detail is in
[hardware status](STATUS-HARDWARE.md); the integration boundary is in
[verification integration](VERIFICATION-INTEGRATION.md); decisions are indexed in
[the decisions index](DECISIONS-INDEX.md).
