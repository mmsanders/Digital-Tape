# Project status

**7 October 2026 UTC · input main `9e902cf` · Owner: PM (ADR-169 playback issuance; #405 design reviewed) ·**
**Phase 1 exit criteria are met.** All nine Phase 1 engine packages (WP-06…WP-13, WP-36) are complete
and independently accepted, and the golden suite is green on main. The milestone, a voice spliced into
the middle of a song on a laptop, is heard and approved.
Michael approved all ten WP-11 golden references by ear on #367 (3 Oct). Verification #143 passed exact
Product #369 head `b61a9e9`:
- golden 10/10 bit-identical;
- the §8 differential 11,572,876/11,572,876 on host GCC, `arm-none-eabi` (qemu, Cortex-M3) and the
  static-assert configuration;
- mutation gate 7/7 caught;
- ledgers WP-08/09/12/12a zero open.

Michael merged #369 at `d93ca4e`; the tree is identical to the disposed head. Dashboard **36/36**.
Sources are public-domain Grieg (Musopen / Czech NSO) and a CC0 sung voice (`tests/golden/SOURCES.json`).
**Phase 2 is open (ADR-162, #381).** [The plan](PHASE2-PLAN.md) is ADOPTED: Windows 10 + current macOS;
WP-38 not taken; operations freeze declared. **P2-R1 blocked** (#399): [WP-14 contract](WP14-CLI-CONTRACT.md) unchanged; 128× playback rereads block native C60; #390 not accepted.
R1/D8 complete: #387 merged `47575af`; live strict ruleset has seven new contexts. Hardware stays parked.

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
| A verifier citation must be a commit on verification main; Verification merges its own publications | ADR-157, `verifier-publication.yml` |
| Rounds may be pre-routed: Verification disposes Software's head directly, PM enters once | ADR-158 |
| Rule 1 ordering covers every IMPORTS-declared package, not only `*_draft8` | ADR-159, #370 (merged `529c404`) |
| Size budgets and the 1 MiB evidence limit are enforced | `repo-hygiene.yml` |

Every new gate has a negative control that is proven to go red. Run them with
`tools/ci/verify-*`.

## Phase 1 packages

| Package | Independently accepted | Outstanding | Next owner |
|---|---|---|---|
| WP-06 block device, superblock, index commit | Exact 289/289 mount, 8/8 writability and 34/34 NOT_MOUNTED evidence integrated; Verification #98 PASS on #297's corrected 38/38 sequential cases and nine causal controls, integrated at main `8dfe543`; Verification #121 PASS on #326's 7/7 closure-gap rows, integrated at `230e47e` | **COMPLETE.** Verification #138 ledger (`3d54eccb`): 40 accepted, 2 WP-06e rows unreachable by spec (V10-002), none open | Accepted / integrated |
| WP-07 chunk allocator, copy-on-write Side B | **COMPLETE.** Verification PR #67 accepted the frozen 10,000-sequence allocator/COW package; its exact evidence was mechanically carried onto post-WP13 main and integrated by product PR #215 | None for frozen WP-07 | Accepted / integrated |
| WP-08 playback, seek, variable-rate scrub | Earlier ten corrected-cadence families and 16/16 set-side/warm-start observations; Verification #95 PASS on #287's 33/33 bounded cross-run cases and seven causal controls, integrated at main `abd8481`; Verification #122 PASS on #327's 41/41 two-toolchain vectors, integrated at `523a7fd` | **COMPLETE.** Ledger: all behaviour rows covered, L04 confirmed on exact #369, and L01/L14 closed by WP-11 goldens plus Michael's #367 approval | Accepted / integrated |
| WP-09 record: overwrite, overdub, splice | Earlier 26/26 observations; Verification #96 PASS on #288's 10,000 edits, 25 checkpoints and eight causal controls, integrated unchanged at main `fa25ae0`; Verification #107 PASS on #311's 27/27 capacity short accept, integrated unchanged at main `66c6abc` | **COMPLETE.** Ledger: all behaviour rows covered (#346 gaps), and L01 closed by WP-11 goldens plus #367 | Accepted / integrated |
| WP-10 crash-injection harness | Verification PR #69 accepted the bounded core tranche. Verification #83 accepted 57,611/57,611 bounded R29-B cases, integrated at main `867fd4a`. Verification #86 accepted exact R29-A PR #263; Software #267 integrated its unchanged package/engine identities at main `215204b`. Verification #119 PASS on #318 (57,539; engine `81ad8ec2`) and #120 on #330 (68,854), integrated at `b05f6af`/`d1ef202` | **COMPLETE.** Verification #141: DRAFT-10 ledger 63 rows, zero open; V10-001 bound and disposed | Accepted / integrated |
| WP-11 CLI harness and golden regression | Verification #143 PASS on exact #369 `b61a9e9`: `tapectl` per `docs/WP11-CLI-CONTRACT.md`; golden 10/10; the §8 differential on three configurations; mutation 7/7. Michael approved all 10 references (#367) | **COMPLETE.** Golden CI green on main `d93ca4e` | Accepted / integrated |
| WP-12 re-spool / defragment pass | Exact 8/8 re-spool evidence is integrated. Verification #81 accepted corrected PR #236's 4,209,696-case R29-C evidence/provenance, carrying PR #79 behavior. Verification #87 accepted exact combined PR #272's three-row composition; Software #276 integrated its accepted identities unchanged at main `788cb76`. Verification #123 PASS on #328's 7/7 gap cases, integrated at `e4e15a0` | **COMPLETE.** `wp11_ledgers_r63`: WP-12/12a 36 rows (31 covered, 2 unreachable, 3 vacuous), zero open | Accepted / integrated |
| WP-13 embedded-readiness audit | **DRAFT-9 is independently accepted and integrated.** Verification #83 authenticated all six gates at exact PR #241 head `74f1173`, including 16/16 sources, exactly four funnels and zero forbidden/ambiguous calls; Software #255 integrated it at main `867fd4a` | Carried to DRAFT-10 (#361); the gate is green and no measured value moved | Accepted / integrated |
| WP-36 slot capability model | **COMPLETE.** Verification PR #57 accepted the deterministic precursor plus the exact 100,000-sequence / 1,997,914-operation literal-NULL source-slot campaign; product PR #200 integrated it unchanged | None for frozen WP-36 | Accepted / integrated |

Phase 1 acceptance is engine and laptop acceptance only. It makes no hardware, media, wake-latency,
85 dB-cap, copy-time or release claim. The caller-owned position table and the harness-only
operation token remain PM rulings (ADR-156), not independently accepted engine behaviour.

## Held and next owner

| Work | Held since | State | Next owner |
|---|---|---|---|
| Operations freeze | closed | **Declared** 5 Oct (ADR-162); DRAFT-10 hashes unchanged | Spec revision only |
| Phase 2 / P2-R1 | — | WP-14 #390 `dbe6283` not disposed; complete authored verifier package `56e25cc1` imported. Run `37560629496`: images all CI platforms/native Linux pass; native Mac/Server2025 C60 times out, census skipped. Physical/Windows10 holds | Verification #146 read-only preflight/publication; then scoped Software correction; #392 resumes WP14 after accepted engine pin |
| Erratum E-1 | — | Michael approved FAT16 default; [overlay/manifest](SPEC-ERRATA.md) preserve DRAFT-10 bytes. Exact overlay confirmed by Verification `ce60d34`; produced-card OS readability still held | Verification #146; Michael #386 |
| Q-P2-1 copy call shape (#379) | — | Engine moves chunk data one block per device call; guardrail 10 risk on the device. (a) answered at `6837102`: existing modes miss any-subset/reordered persistence. Software counts: C-60 load 155048 flushes, dup 1.24M reads/writes. No batching permission | [ADR-168 framework](PERFORMANCE-PLAN.md); retain <30 s; design #405 reviewed; async ABI unissued; model before write changes |
| Hardware | 2026-09-18 | **PARKED through Phase 2** (#309; extended 3 Oct, ADR-160). Held PRs #87, #92, #120, #197, #198, #296 closed unmerged; heads and restore commands in [the parked hardware PR record](PACKAGES/README.md#parked-hardware-pr-record). Timing PROVISIONAL; fabrication/charging CLOSED with five blockers | Resumes at Phase 3 or on Michael's request, starting with Verification review of #87/#92 |
| DRAFT-10 spec revision (#308) | closed | **Issued 1 Oct** at `d8243c9` on Michael's authorization of V10-001…V10-005; docket closed | Implemented and accepted (#141) |
| Q-001 | closed | Closed: Michael signed the exact scoped freeze on 8 September 2026 | PM recorded approval |
| WP-04 / WP-05 | 2026-09-18 | PARKED with Hardware. #87's method rejected (`P1-R23-V01`) and closed; latch root cause recorded in the roadmap; identity, attribution, atomicity and qualification remain open | None PM-issued; resume with Hardware |

**Held since** is the date the hold became visible: the day the held PR was opened,
where the hold is a PR (#20 on 3 September, #96 on 19 September, #87 on 18 September),
and `—` where the item is blocked on coverage rather than by a dated hold event.
`CLAUDE.md` §4 requires escalation to PM past three days;
`.github/workflows/stream-age.yml` checks it daily so the rule is not left to memory.

## Risks

1. **Card atomicity is unqualified.** No media is qualified to WP-05 A-2; PR #87's method is independently rejected on `P1-R23-V01` and no new acquisition may run.
2. **Solenoid timing is unresolved** at the actual rail and parts; timing stays PROVISIONAL and the fabrication/charging gate stays CLOSED with five blockers.
3. **No audited mechanism or creep trial exists.** Michael's informal prints (clasps appear to work, 3 Oct) are owner observations, not trials; the WP-04 latch is not functional yet; CAD checks are not measurements.
4. **Laptop acceptance is not product acceptance.** Wake latency, the 85 dB cap, C-60 copy time and firmware bit-identity on target are untested until later phases.
5. **I/O performance (#399/#379).** C60 side: ~81.3 GB read for 635 MB audio (128×); firmware impact inferred. Dup: ~1.24M reads/writes; load: 155048 flushes. [ADR-168 plan](PERFORMANCE-PLAN.md): urgent burst reuse; contiguous transfers and true overlap; <30 s retained. ADR-169 read-only exception issued; verifier-first; engine pin pending.
6. **Process debt:** six zero-parent snapshot roots (22 Sep) sit in main's history. They are harmless but confuse naive history scans (ADR-159).

## Standing boundaries

**Complete independent package acceptance exists for every Phase 1 package**: WP-06 (#138), WP-07 (#67),
WP-08/09/11/12 (#143 plus Michael #367), WP-10 (#141), WP-13 (#83, carried by #361) and WP-36 (#57).
Each holds within its exact recorded boundary.
Pilot CI evidence: docs 51 s/1.6 job-minutes; host 1m42s/12.4; full 167. ADR-166 preserves criteria and stops unchanged timeout reruns.
ADR-169 issues read-only playback scope, tests first; #405 design published #407. <30 s retained; write/async/target work unissued. No WP-14 acceptance; strict ruleset 22084355 and golden gates remain.

The lead operating format, role charters and the issue workflow are in
[CLAUDE.md §7](../CLAUDE.md), [role charters](ROLES/README.md) and
[the issue workflow](ISSUE-WORKFLOW.md). Hardware detail is in
[hardware status](STATUS-HARDWARE.md); the integration boundary is in
[verification integration](VERIFICATION-INTEGRATION.md); decisions are indexed in
[the decisions index](DECISIONS-INDEX.md).
