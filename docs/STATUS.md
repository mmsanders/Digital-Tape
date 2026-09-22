# Project status

**22 September 2026 UTC · input main `a310521` · Owner: PM ·** Phase 1 now holds
four independently accepted evidence tranches: 289 mount cases, ten playback families,
two VT8-001 operation cases, and the exact 26-case WP-09 record bundle at product
`9d3649d...`. No package, source or golden is accepted and the dashboard stays at
13 of 36. WP-09's corrected verifier publication is merged in Verification at
`e9e6ec7...`; Software #165 owns the clean verifier-first product integration/rerun.

This file is a state table, not a chronicle. Round-by-round narrative through P1-R24
is preserved verbatim in [the September status history](archive/status-history/2026-09-status.md).
Per-round integration narrative is in
[the verification integration history](archive/verification-integration-history.md).
Active assignments and stop conditions live only in
[role-labeled issues](ISSUE-WORKFLOW.md); this file records evidence, not work directions.

## Before you run anything

**Raw evidence is not in the tree.** The two large observations live in release
`evidence-2026-09`; the committed `.sha256` beside each run is the citation. Any command
that replays a retained bundle needs this first:

```sh
tools/fetch-evidence.sh          # downloads, verifies, refuses a mismatch
```

**Required reading is four documents plus your issue** (CLAUDE.md §4): `AGENTS.md`,
`CLAUDE.md`, this file, your own charter. Everything else is read on demand through
[the decisions index](DECISIONS-INDEX.md) and [spec/NAVIGATION.md](../spec/NAVIGATION.md).

**What changed in the remediation round**, none of it affecting acceptance:

| Change | Where |
|---|---|
| A tranche is one branch, two commits: import then implementation | CLAUDE.md §3.1, ADR-155 |
| CI does the mechanical authentication; PM rules on substance | `evidence-integrity.yml`, ADR (D-3) |
| Tranche minimum: 3 coverage rows or 25 cases; split before disposition | ADR-153 |
| Inbound `intake` queue; default disposition RECORDED — PARKED | [intake](INTAKE.md), ADR-154 |
| Held streams over three days are escalated automatically | `stream-age.yml` |
| Size budgets and the 1 MiB evidence limit are enforced | `repo-hygiene.yml` |

Every new gate has a negative control that is proven to go red. Run them with
`tools/ci/verify-*`.

## Phase 1 packages

| Package | Independently accepted | Outstanding | Next owner |
|---|---|---|---|
| WP-06 block device, superblock, index commit | Exact 289/289 mount observations including row 3, at verifier `392d6bb9...` | `writability_draft8` and `notmounted_draft8` are independently published/imported but unexecuted on the real product; source/helper design and complete WP-06 remain open | Queued — Software after the current record tranche |
| WP-07 chunk allocator, copy-on-write Side B | Two exact recorded observations — `VT8-001-RB-ALLSLOT` and `VT8-001-REC-ALLOCSEQ` — at verifier `e77b61f...`, re-confirmed on the clean PR #112 split at `391d6a8...` | Invented splice-only and stage-1 BUSY refusal policies; every unexercised branch; source; complete WP-07 | Held pending a later independently tested tranche |
| WP-08 playback, seek, variable-rate scrub | Exact ten corrected-cadence product observations, 698/698 per-render service in each direction, at verifier `392d6bb9...` | `transport_draft8` adds independent set-side/warm-start coverage on main but has no real-product disposition; source/helper design, complete WP-08, listening and goldens remain open | Queued — Software for the new transport tranche; listening/goldens remain separately held |
| WP-09 record: overwrite, overdub, splice | Exact 26/26 retained product observations at `9d3649d...`, independently replayed PASS by verifier PR #39 / `e9e6ec7...` under the corrected ARMED-BUSY oracle | Clean verifier-first product integration and ordinary rerun remain; PCM/listening, crash/durability, 10,000-edit history, short-accept, reset-B stage clearing and other stated exclusions remain open | **Software #165** |
| WP-10 crash-injection harness | Narrow independent mount package landed | Complete crash/operation/state run is not green | Verification |
| WP-11 CLI harness and golden regression | Seven exact product PCM outputs byte-match verifier candidates | Candidate PCM is unlistened and is not an accepted golden; golden CI stays red | Held — needs Michael's own listening |
| WP-12 re-spool / defragment pass | None | `respool_draft8` is independently published/imported via #142; real-product execution is outstanding and WP-12a continuation/BUSY/re-entry/FAULTED coverage remains separate | Queued — Software, then Verification |
| WP-13 embedded-readiness audit | None | Held #20 measurements (instance 156456 B, stack 1536/8192, rodata 1040/32768) are implementer evidence, not package acceptance | Held |
| WP-36 slot capability model | None | `slot_draft8` deterministic source-slot coverage is independently published/imported via #143; real-product execution is outstanding and the required 100,000-sequence acceptance run remains separate | Queued — Software, then Verification |

Engine implementation status: 16 of 21 public entry points are defined. `tape_abort`,
`tape_dup`, `tape_format`, `tape_promote` and `tape_respool` are declared and undefined.
Code exists well ahead of accepted coverage; that gap is coverage, not implementation.

## Held and next owner

| Work | Held since | State | Next owner |
|---|---|---|---|
| #20 engine | 2026-09-03 | Held draft at `2e0e8a4...`; not an ancestor of main. Only the separate clean PR #77 mount/playback slice was merged. No wholesale import of allocator, recording, warm/state or other uncovered behavior. | Held; Software may work only from current scoped issues |
| VT8-001 / WP-07 | 2026-09-19 | PR #112 is integrated at main `be7f8f2...` with exact accepted history preserved. Verification independently accepts only its two recorded observations; source, invented refusal policies, unexercised branches and complete WP-07 remain unaccepted | Held pending a later independently tested tranche; PR #96 remains held |
| WP-10 / operations freeze | — | Infrastructure present, actual complete engine crash run not green | Verification |
| WP-11 | — | Exact corrected-cadence product PCM hashes are independently byte-compared, but candidate PCM remains unlistened and is not an accepted golden; golden CI stays red | Held pending a separately issued listening/golden route |
| Hardware | 2026-09-18 | Verification rejects PR #87 repaired head `e520c2c...` on `P1-R23-V01`'s eleven adjacent forms. PR #92 head `0943571...` remains held. PR #120 head `7b224ff...` is a stale-base, advice/method candidate awaiting independent A1MINI-01 audit. Timing stays PROVISIONAL and fabrication/charging stay CLOSED with five blockers | Hardware repairs PR #87; Verification audits exact PR #120 method without printing |
| Q-001 | closed | Closed: Michael signed the exact scoped freeze on 8 September 2026 | PM recorded approval |
| WP-04 / WP-05 | 2026-09-18 | Existing library test stays on the expected Monday library route; new prints default to the A1 Mini, with the library retained for oversized PLA. PR #87 is independently rejected; A1MINI-01 is unprinted and unaudited; identity, attribution, atomicity and qualification remain open | Hardware card-method repair plus Verification A1MINI-01 method audit; no Michael purchase/print issue |

**Held since** is the date the hold became visible: the day the held PR was opened,
where the hold is a PR (#20 on 3 September, #96 on 19 September, #87 on 18 September),
and `—` where the item is blocked on coverage rather than by a dated hold event.
`CLAUDE.md` §4 requires escalation to PM past three days;
`.github/workflows/stream-age.yml` checks it daily so the rule is not left to memory.

## Risks

1. **Card atomicity is unqualified.** No media is qualified to WP-05 A-2; PR #87's method is independently rejected on `P1-R23-V01` and no new acquisition may run.
2. **Solenoid timing is unresolved** at the actual rail and parts; timing stays PROVISIONAL and the fabrication/charging gate stays CLOSED with five blockers.
3. **Mechanism and creep trials are unprinted.** A1MINI-01 rev 1 is an unprinted, unaudited method candidate; CAD checks are not measurements.
4. **Engine code is held by coverage/integration, not by implementation.** WP-09 now has an independently accepted 26-case evidence tranche, but its implementation is still held pending the corrected verifier-first clean integration in #165.
5. **WP-11 goldens are missing by design.** Golden CI is red until Michael listens; no process change substitutes for that.

## Standing boundaries

**New independent package acceptances: none.** Four evidence tranches are independently
accepted as exact recorded observations only — not source, helper design, complete
packages, merge status or goldens. WP-09 contributes the exact 26-case retained bundle;
its corrected verifier is published, but clean product integration/rerun is still held
in #165. The other newly imported verifier packages remain test publications only until
exact real-product evidence is independently dispositioned.
Main ruleset 22084355 remains active and strict. Missing WP-11 goldens remain an explicit red gate.

Phase 1 operating format, role charters and the issue workflow are in
[CLAUDE.md §7](../CLAUDE.md), [role charters](ROLES/README.md) and
[the issue workflow](ISSUE-WORKFLOW.md). Hardware detail is in
[hardware status](STATUS-HARDWARE.md); the integration boundary is in
[verification integration](VERIFICATION-INTEGRATION.md); decisions are indexed in
[the decisions index](DECISIONS-INDEX.md).
