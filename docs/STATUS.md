# Project status

**29 September 2026 UTC · input main `39d2076` · Owner: Verification #107/#108/#105, Software #313/#314, PM #308 ·**
Phase 1 has three complete independently accepted packages: **WP-07 allocator/COW, WP-13
embedded readiness and WP-36 slot capability**. The accepted bounded WP-10 core crash
tranche is integrated through product PR #217 / Verification PR #69, but full WP-10
remains open. The dashboard remains **21/36 rungs (58%)**. Bounded R29-A/B/C, WP-06
#297 (38/38), WP-08 #287 (33/33) and WP-09 #288 (10,000 edits) are independently
accepted and integrated; per-round detail is in the archives below.
PM #305 (R53) status. Product PR #311 binds WP-09 capacity short accept at 27/27 with no
engine change, and awaits independent disposition in Verification #107. Product PR #312
passes 5 of 7 WP-06 gap rows. PM upheld Software's finding that the verifier's live-B floor
predicate rejects lawful promote phase 2 and re-spool pass 2 (TapeFS §9.3.2, §9.4).
Verification #108 corrects it, and #312 is held for a rebind. PM dispositioned two
publications as ready for binding: the corrected WP-08 two-toolchain arithmetic
(`3dbd225`, 41 vectors; Software #313) and WP-12/WP-12a closure gaps (`bbaa4f0`, 3 rows /
7 cases; Software #314). Verification #105 (WP-10 ledger) is in progress, and PM #308
holds the WP-06e spec question. Verifier evidence is not Product acceptance.
No rung advanced.

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
| WP-06 block device, superblock, index commit | Exact 289/289 mount, 8/8 writability and 34/34 NOT_MOUNTED evidence integrated; Verification #98 PASS on #297's corrected 38/38 sequential cases and nine causal controls, integrated at main `8dfe543` | Complete WP-06 open; two WP-06e clauses unreachable under frozen stage oracle | Verification #108 — floor-predicate fix, then #312 rebind; PM #308 — spec decision |
| WP-07 chunk allocator, copy-on-write Side B | **COMPLETE.** Verification PR #67 accepted the frozen 10,000-sequence allocator/COW package; its exact evidence was mechanically carried onto post-WP13 main and integrated by product PR #215 | None for frozen WP-07 | Accepted / integrated |
| WP-08 playback, seek, variable-rate scrub | Earlier ten corrected-cadence families and 16/16 set-side/warm-start observations; Verification #95 PASS on #287's 33/33 bounded cross-run cases and seven causal controls, integrated at main `abd8481` | Two-toolchain publication `3dbd225` PASS-ready (41 vectors), not Product-bound; complete WP-08 and listened goldens open | Software #313 — Structural Rule 1 binding |
| WP-09 record: overwrite, overdub, splice | Earlier 26/26 observations; Verification #96 PASS on #288's 10,000 edits, 25 checkpoints and eight causal controls, integrated unchanged at main `fa25ae0` | Capacity short accept bound in held PR #311 (27/27), not independently disposed; full WP-09 open | Verification #107 — independent disposition |
| WP-10 crash-injection harness | Verification PR #69 accepted the bounded core tranche. Verification #83 accepted 57,611/57,611 bounded R29-B cases, integrated at main `867fd4a`. Verification #86 accepted exact R29-A PR #263; Software #267 integrated its unchanged package/engine identities at main `215204b` | Full operations and WP-12a remain open | Verification #105 — DRAFT-9 criterion ledger, top three gaps |
| WP-11 CLI harness and golden regression | Seven exact product PCM outputs byte-match verifier candidates | Candidate PCM is unlistened and is not an accepted golden; golden CI stays red | Held — needs Michael's own listening |
| WP-12 re-spool / defragment pass | Exact 8/8 re-spool evidence is integrated. Verification #81 accepted corrected PR #236's 4,209,696-case R29-C evidence/provenance, carrying PR #79 behavior. Verification #87 accepted exact combined PR #272's three-row composition; Software #276 integrated its accepted identities unchanged at main `788cb76` | Complete WP-12/WP-12a remain separate | Software #314 — bind 3 gap rows from `bbaa4f0`; ledger 28/36 already accepted |
| WP-13 embedded-readiness audit | **DRAFT-9 is independently accepted and integrated.** Verification #83 authenticated all six gates at exact PR #241 head `74f1173`, including 16/16 sources, exactly four funnels and zero forbidden/ambiguous calls; Software #255 integrated it at main `867fd4a` | None for the accepted DRAFT-9 boundary | Accepted / integrated |
| WP-36 slot capability model | **COMPLETE.** Verification PR #57 accepted the deterministic precursor plus the exact 100,000-sequence / 1,997,914-operation literal-NULL source-slot campaign; product PR #200 integrated it unchanged | None for frozen WP-36 | Accepted / integrated |

Engine implementation now includes respool, bounded format/duplicate paths and the
independently accepted R29-A Promote tranche integrated at main `215204b`. This is
bounded evidence, not complete WP-10/WP-12a or a general release claim. The caller-owned
position table and harness-only operation token are PM-ruled in ADR-156, not
independently accepted engine behavior.

## Held and next owner

| Work | Held since | State | Next owner |
|---|---|---|---|
| WP-10 / operations freeze | — | Bounded core, R29-B, R29-A and exact combined R29-C PR #272 are independently accepted and integrated; complete operations/WP-12a remain open | Held pending further independent coverage |
| WP-11 | — | Exact corrected-cadence product PCM hashes are independently byte-compared, but candidate PCM remains unlistened and is not an accepted golden; golden CI stays red | Held pending a separately issued listening/golden route |
| Hardware | 2026-09-18 | **PARKED by Michael 29 Sep ([#309](https://github.com/mmsanders/Digital-Tape/issues/309)).** PR #87 repair `e294d51` unaudited; Verification #20 (A1MINI-01, PR #120) closed without a finding; PR #92 held. Timing PROVISIONAL; fabrication/charging CLOSED with five blockers | None PM-issued; Michael works with Hardware directly. Resume on Michael `REQUEST:` or Phase 2 |
| Q-001 | closed | Closed: Michael signed the exact scoped freeze on 8 September 2026 | PM recorded approval |
| WP-04 / WP-05 | 2026-09-18 | PARKED with Hardware (#309). PR #87 not re-audited; A1MINI-01 unaudited; identity, attribution, atomicity and qualification remain open | None PM-issued; resume with Hardware |

**Held since** is the date the hold became visible: the day the held PR was opened,
where the hold is a PR (#20 on 3 September, #96 on 19 September, #87 on 18 September),
and `—` where the item is blocked on coverage rather than by a dated hold event.
`CLAUDE.md` §4 requires escalation to PM past three days;
`.github/workflows/stream-age.yml` checks it daily so the rule is not left to memory.

## Risks

1. **Card atomicity is unqualified.** No media is qualified to WP-05 A-2; PR #87's method is independently rejected on `P1-R23-V01` and no new acquisition may run.
2. **Solenoid timing is unresolved** at the actual rail and parts; timing stays PROVISIONAL and the fabrication/charging gate stays CLOSED with five blockers.
3. **Mechanism and creep trials are unprinted.** A1MINI-01 rev 1 is an unprinted, unaudited method candidate; CAD checks are not measurements.
4. **Engine progress is still coverage-limited.** WP-07, WP-13 and WP-36 are complete within exact boundaries; bounded R29-A/B/C, WP-06/#297, WP-08/#287 and WP-09/#288 are integrated. WP-10, WP-12, WP-12a and WP-11 listening/goldens remain incomplete.
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
