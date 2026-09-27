# Project status

**27 September 2026 UTC · input main `867fd4a` · Owner: Verification #84 ·** Phase 1 has
three complete independently accepted packages: **WP-07 allocator/COW, WP-13 embedded
readiness and WP-36 slot capability**. The accepted bounded WP-10 core crash tranche is
also integrated through product PR #217 / Verification PR #69, but full WP-10 remains
open. The dashboard remains **21/36 rungs (58%)**. Accepted bounded R29-B and DRAFT-9
WP-13 are integrated at main `867fd4a`. Held R29-A PR #257 validates 44,309/44,311
cases in Software's diagnostic sweep; its two reds expose an unreachable
allocating-decline verifier branch, while two more cases pass vacuously. Verification
#84 owns one final bounded package correction and binding audit. No rung advanced.

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
| WP-07 chunk allocator, copy-on-write Side B | **COMPLETE.** Verification PR #67 accepted the frozen 10,000-sequence allocator/COW package; its exact evidence was mechanically carried onto post-WP13 main and integrated by product PR #215 | None for frozen WP-07 | Accepted / integrated |
| WP-08 playback, seek, variable-rate scrub | Exact ten corrected-cadence playback observation families plus exact 16/16 set-side/warm-start product observations; transport evidence independently replayed PASS by verifier PR #41 / `334ab2a...` and integrated via product PR #171 at main `e598b82...` | Source/helper design, complete WP-08, byte-exact/listened warm samples and broader goldens remain open | Held pending later independently tested coverage; listening/goldens remain separately held |
| WP-09 record: overwrite, overdub, splice | Exact 26/26 product observations independently replayed PASS by verifier PR #39 / `e9e6ec7...`; corrected verifier-first integration merged in product PR #167 at main `1db7135...` | PCM/listening, crash/durability, 10,000-edit history, short-accept, reset-B stage clearing and other stated exclusions remain open; complete WP-09 remains unaccepted | Held pending later independently tested coverage |
| WP-10 crash-injection harness | Verification PR #69 accepted the bounded core tranche. Verification #83 accepted 57,611/57,611 bounded R29-B cases at exact PR #241 head `74f1173`; Software #255 integrated that candidate at main `867fd4a` | R29-A PR #257 passes 44,309/44,311 in Software's full sweep, including all 44,204 crash cases, but four allocating-decline cases are invalid or vacuous package coverage. Full operations and WP-12a remain open | Verification #84 final package correction/binding audit |
| WP-11 CLI harness and golden regression | Seven exact product PCM outputs byte-match verifier candidates | Candidate PCM is unlistened and is not an accepted golden; golden CI stays red | Held — needs Michael's own listening |
| WP-12 re-spool / defragment pass | Exact 8/8 respool product evidence independently accepted via Verification #44 / PR #45 and integrated through the #180 chain | Verification narrowly authenticated #227's retained raw public observations but rejected its continuity/no-restart and budget-1 claims. Corrected R29-C requires a fresh product binding/run; WP-12a and complete WP-12 acceptance remain separate | Software — corrected R29-C binding and fresh evidence |
| WP-13 embedded-readiness audit | **DRAFT-9 is independently accepted and integrated.** Verification #83 authenticated all six gates at exact PR #241 head `74f1173`, including 16/16 sources, exactly four funnels and zero forbidden/ambiguous calls; Software #255 integrated it at main `867fd4a` | None for the accepted DRAFT-9 boundary | Accepted / integrated |
| WP-36 slot capability model | **COMPLETE.** Verification PR #57 accepted the deterministic precursor plus the exact 100,000-sequence / 1,997,914-operation literal-NULL source-slot campaign; product PR #200 integrated it unchanged | None for frozen WP-36 | Accepted / integrated |

Engine implementation now includes respool and bounded format/duplicate paths, while
held PR #257 carries the corrected Promote implementation. Its Software evidence is
not acceptance: **do not use Promote in a new consumer or release** before the final
corrected R29-A import/run and independent disposition. The
caller-owned position table and harness-only operation token are PM-ruled in
ADR-156, not independently accepted engine behavior.

## Held and next owner

| Work | Held since | State | Next owner |
|---|---|---|---|
| WP-10 / operations freeze | — | Bounded core and R29-B are accepted/integrated. R29-A PR #257 is held: 44,309/44,311 Software observations validate, but two impossible allocating-decline cases fail and two pass vacuously | Verification #84 corrects the package and audits bindings; PM then issues one mechanical repack/rerun |
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
4. **Engine progress is still coverage-limited.** WP-07, WP-13 and WP-36 are complete within their exact accepted boundaries; bounded R29-B is integrated. Promote remains held on PR #257 pending Verification #84's final correction/audit and a fresh exact-tree product run. This is not complete WP-10 or WP-12a. WP-06/WP-08/WP-09/WP-12 and WP-11 listening/goldens remain incomplete.
5. **WP-11 goldens are missing by design.** Golden CI is red until Michael listens; no process change substitutes for that.

## Standing boundaries

**Complete independent package acceptance exists for WP-07, WP-13 and WP-36.**
WP-07 was accepted by Verification #67 and integrated by product #215; the DRAFT-8
WP-13 baseline by Verification #66 / product #206, with DRAFT-9 re-accepted at exact
held PR #241 head by Verification #83; WP-36 by Verification #57 / product #200.
WP-10 has accepted bounded tranches, not complete-package acceptance. WP-11 still
requires Michael's listening before golden acceptance.
Main ruleset 22084355 remains active and strict. Missing WP-11 goldens remain an explicit red gate.

Phase 1 operating format, role charters and the issue workflow are in
[CLAUDE.md §7](../CLAUDE.md), [role charters](ROLES/README.md) and
[the issue workflow](ISSUE-WORKFLOW.md). Hardware detail is in
[hardware status](STATUS-HARDWARE.md); the integration boundary is in
[verification integration](VERIFICATION-INTEGRATION.md); decisions are indexed in
[the decisions index](DECISIONS-INDEX.md).
