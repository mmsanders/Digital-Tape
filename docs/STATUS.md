# Project status

**24 September 2026 UTC · input main `e4a3565` · Owner: PM ·** Phase 1 now has its
first complete independently accepted package: **WP-36 slot capability**. Verification
PR #57 accepted the frozen package after the deterministic 5/5 precursor plus the exact
100,000-sequence / 1,997,914-operation NULL-write transport campaign; product PR #200
integrated the exact accepted tree unchanged. Narrow accepted evidence for mount,
playback, VT8-001, WP-09 record, transport/warm, promote, respool, format/dup,
writability and NOT_MOUNTED remains as before. The dashboard advances from **13/36
to 16/36** because WP-36 moves from 1/4 to 4/4; no other package rung changes.

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
| WP-06 block device, superblock, index commit | Exact 289/289 mount observations plus independently accepted 8/8 writability and 34/34 NOT_MOUNTED product evidence, all integrated on current main | Source/helper design and complete WP-06 remain open; these narrow tranches do not accept the package | Held pending a later independently tested tranche |
| WP-07 chunk allocator, copy-on-write Side B | Two exact recorded observations — `VT8-001-RB-ALLSLOT` and `VT8-001-REC-ALLOCSEQ` — at verifier `e77b61f...`, re-confirmed on the clean PR #112 split at `391d6a8...` | Invented splice-only and stage-1 BUSY refusal policies; every unexercised branch; source; complete WP-07 | Held pending a later independently tested tranche |
| WP-08 playback, seek, variable-rate scrub | Exact ten corrected-cadence playback observation families plus exact 16/16 set-side/warm-start product observations; transport evidence independently replayed PASS by verifier PR #41 / `334ab2a...` and integrated via product PR #171 at main `e598b82...` | Source/helper design, complete WP-08, byte-exact/listened warm samples and broader goldens remain open | Held pending later independently tested coverage; listening/goldens remain separately held |
| WP-09 record: overwrite, overdub, splice | Exact 26/26 product observations independently replayed PASS by verifier PR #39 / `e9e6ec7...`; corrected verifier-first integration merged in product PR #167 at main `1db7135...` | PCM/listening, crash/durability, 10,000-edit history, short-accept, reset-B stage clearing and other stated exclusions remain open; complete WP-09 remains unaccepted | Held pending later independently tested coverage |
| WP-10 crash-injection harness | Narrow independent mount package landed | Complete crash/operation/state run is not green | Verification |
| WP-11 CLI harness and golden regression | Seven exact product PCM outputs byte-match verifier candidates | Candidate PCM is unlistened and is not an accepted golden; golden CI stays red | Held — needs Michael's own listening |
| WP-12 re-spool / defragment pass | Exact 8/8 respool product evidence independently accepted via Verification #44 / PR #45 and integrated through the #180 chain | WP-12a continuation/BUSY/re-entry/FAULTED coverage and complete WP-12 acceptance remain separate | Held pending a later independently tested tranche |
| WP-13 embedded-readiness audit | None | Held #20 measurements (instance 156456 B, stack 1536/8192, rodata 1040/32768) are implementer evidence, not package acceptance | Held |
| WP-36 slot capability model | Deterministic source-slot precursor independently accepted 5/5 via Verification PR #53 and integrated via product PR #191; literal NULL-write/debug-assert boundary authenticated | Required 100,000 random transport-sequence acceptance run remains outstanding; complete WP-36 remains unaccepted | Verification — issue #54 authors the independent fuzz tranche before any new product binding |

Engine implementation now includes promote, respool and the bounded format/duplicate
paths exercised by the accepted tranches. Coverage still trails implementation in several
packages; that gap is coverage, not package acceptance.

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
4. **Engine progress is still coverage-limited.** WP-36 is now fully accepted and integrated, while the remaining engine packages still require independent closure—especially allocator/COW history, crash durability, long-operation state behavior, embedded-readiness audit and WP-11 goldens/listening.
5. **WP-11 goldens are missing by design.** Golden CI is red until Michael listens; no process change substitutes for that.

## Standing boundaries

**New independent package acceptance: WP-36.** Verification PR #57 explicitly
accepted the complete frozen WP-36 package for exact product PR #200, and Software
merged that exact accepted tree unchanged at main `e4a3565...`. The other accepted
evidence remains narrow observation coverage only—not source/helper design or complete
package acceptance. WP-11 still requires Michael's listening before golden acceptance.
Main ruleset 22084355 remains active and strict. Missing WP-11 goldens remain an explicit red gate.

Phase 1 operating format, role charters and the issue workflow are in
[CLAUDE.md §7](../CLAUDE.md), [role charters](ROLES/README.md) and
[the issue workflow](ISSUE-WORKFLOW.md). Hardware detail is in
[hardware status](STATUS-HARDWARE.md); the integration boundary is in
[verification integration](VERIFICATION-INTEGRATION.md); decisions are indexed in
[the decisions index](DECISIONS-INDEX.md).
