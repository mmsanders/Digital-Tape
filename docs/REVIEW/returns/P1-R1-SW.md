# P1-R1-SW return — Software Lead

**Issue:** [#41](https://github.com/mmsanders/Digital-Tape/issues/41) (`software-lead`, updated `2026-09-12T05:27:09Z`).
**Returned:** 12 September 2026 UTC. **Next owner:** PM, then Verification for independent disposition.
**Status:** Ready for PM review. Items 1, 2, 5 and 6 delivered; item 3 returns a
blocker-shaped finding by design; item 4 is complete except for media that no run
could produce.

Nothing in this return is acceptance of anything. No engine implementation changed.

## Inputs, exactly

| Input | Value |
|---|---|
| Product main at pickup | `40507bf` — parent is `d9bc6ebd10983711acade6d148895e78fd1a17e3`, the SHA the issue names |
| Spec bundle | gate green; TapeFS `3bffa0ec…47cbb`, Engine API `537eadc4…7e3a1`, Acceptance `7f78fba7…56bbb` |
| Verifier package | `mmsanders/digital-tape-verification` `a91138667673fcf19dc9e83c9034322b982b1771`, `tests/ops_draft8/` |
| Verifier tree | `c8a43df69a6be8e2c34bf79a1d79933abf48286a` — **matches the expected tree in the issue** |
| Held engine | PR #20 head `2e0e8a4b7bff42797ac37901196e5ea348b2e392` |
| Toolchain | `cc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0`; Python 3.11.15 |
| Raw evidence | [`docs/verification/runs/2026-09-12/`](../../verification/runs/2026-09-12/README.md) |

## 1. Test-only import — done

All 8 tracked files imported into `tests/ops_draft8/` with `git archive`, so bytes
and modes never passed through a copy. Blob hashes and modes on the product side
are identical to the verifier side, and the product subtree hash reproduces
`c8a43df69a6be8e2c34bf79a1d79933abf48286a`.

| Mode | Blob | Path |
|---|---|---|
| `100644` | `373005b1ef74176f6f28d75c81801fd5997c519d` | `ADAPTER.md` |
| `100644` | `5b463cc0347f5eea802b87f800d7d981fe9237d2` | `README.md` |
| `100755` | `c67a0ffa3afb578c8bca8c611d0926bd5067e7a1` | `_synthetic_adapter.py` |
| `100644` | `443be133190bff00c4b39292ee723008f91e2bd9` | `evidence/runner-selftest.jsonl` |
| `100644` | `b8d40fe1e97839c0515570b271c237fae6c678ff` | `evidence/selftest.log` |
| `100644` | `213b5526044532f314e9d8ab1bf7ec5ee74beb2a` | `oracle.py` |
| `100755` | `c50dc81be8497da066fa0b9216cdf08935c4f541` | `runner.py` |
| `100755` | `dca0d651baf466f10504078b8c9f45c6d05c0558` | `selftest.py` |

Three executable modes preserved. Both historical self-test logs under
`evidence/` are untouched. No engine code is in this import. Nothing inside the
imported directory was edited, and the diagnostic-only limitation is recorded
here and in `docs/VERIFICATION-INTEGRATION.md`, outside that directory.

**P1-R1-V01/V02/V03 remain open in this baseline.** Importing test source grants
no coverage: these two case IDs have never executed against any engine.

## 2. Self-test, synthetic runner, adapter — done

- `python3 selftest.py` → PASS: 2 conforming observations accepted, **6 targeted
  mutations caught**. Output is **byte-identical** to the package's own
  `evidence/selftest.log`.
- `python3 runner.py --adapter ./_synthetic_adapter.py` → 2 cases, 0 failed.

Both results are **SYNTHETIC**. They exercise the verifier's own oracle and
runner plumbing against a Python stand-in. No engine ran. They say nothing about
any implementation.

The adapter is built at [`tests/ops_adapter/`](../../../tests/ops_adapter/README.md),
deliberately outside the verifier oracle's directory:

- `vt8_ops_probe.c` — the two scripted case sequences through the **public** API
  only, including the real product `tape.h` via `-DTAPE_PUBLIC_HEADER`.
- caller-owned instance and both rings; `warm == NULL`; fresh instance for each
  remount.
- harness-owned **sparse** block map: an audio chunk is backed only once written,
  so unmapped audio reads stay deterministic poison; every batch is range-checked
  with widened 64-bit arithmetic before any copy.
- **finite service guard**: `tape_service` is driven at a fixed positive block
  budget under a 4096-call bound; nontermination fails the case instead of hanging.
- `preserve.sh`, an external wrapper that copies both VO08 envelopes out before
  the runner's `TemporaryDirectory` is removed. It does not touch the runner, the
  oracle, any fixture or any assertion.

No private allocator or sequence helper is called, no product API was invented,
no fixture or expected outcome was edited.

## 3. Diagnostic run against held #20 — precise gap, no implementation

One attempt, staged so a compile gap and a link gap stay separable. No rebase was
needed or performed: `2e0e8a4b` was extracted with `git archive` into a scratch
tree and built there, so the product checkout stayed clean.

**Compile: clean.** The adapter compiles with no error or warning under
`-std=c99 -Wall -Wextra -Werror -pedantic` against #20's public header. This is
itself the useful half of the finding: **the public API surface is complete and
correct for VT8-001. Nothing needs to be added to `tape.h`.**

**Link: fails on exactly six symbols** that #20's header declares and no
translation unit defines:

| Missing symbol | Needed by |
|---|---|
| `tape_reset_side_b` | `VT8-001-RB-ALLSLOT` |
| `tape_seek` | `VT8-001-REC-ALLOCSEQ` |
| `tape_arm` | `VT8-001-REC-ALLOCSEQ` |
| `tape_feed` | `VT8-001-REC-ALLOCSEQ` |
| `tape_service` | `VT8-001-REC-ALLOCSEQ` |
| `tape_commit` | `VT8-001-REC-ALLOCSEQ` |

`tape_instance_size`, `tape_init`, `tape_mount`, `tape_get_info`, `tape_tell` and
`tape_unmount` all resolve. This is the loud failure #20's own header documents
as intended ("Calling one is a link error"). **I did not implement any of the six**,
per the issue. Raw log: `pr20-link-diagnostic.log`.

Consequence for the round: **VT8-001 cannot produce a product observation against
any engine that exists today.** No engine in the repository or on the held branch
defines recording or reset. The runner correctly refuses to skip — with no adapter
executable it exits 2 with `adapter executable missing`, so this gap cannot go
quietly green.

### Second finding: current main's public header predates the frozen API

The adapter does not even compile against `engine/include/tape.h` on main. Main's
header is older than the frozen DRAFT-8 Engine API (`537eadc4…`):

| Surface | Frozen spec §5/§6 | Current main |
|---|---|---|
| `tape_mount` | `(tape*, tape_side, uint64_t, const tape_warm_start *warm)` | `(tape*, tape_side, uint64_t, const void*, size_t)` |
| `tape_tell` | `tape_result tape_tell(const tape*, uint64_t *out)` | `uint64_t tape_tell(const tape*)` |
| `tape_info` | includes `version_minor`, `side_b_valid`, `warm_start_used` | all three absent |

This is a factual divergence between main and the signed freeze, not a request to
change either. It also means main is not a valid link target for **either**
independent package. PM should decide whether closing it is in scope for a later
round; I am not doing it under this issue.

## 4. Evidence — complete except for media that no run produced

Recorded in the [run packet](../../verification/runs/2026-09-12/README.md): product
and engine and verifier SHAs, the verifier tree hash, clean build state, compiler
identity and exact flags, adapter and wrapper SHA-256, every command with its exit
status, raw stdout/stderr, and SHA-256 of each evidence file.

Recorded separately as the issue asks: public-call results, accepted frame count,
remount results and the finite service guard are distinct fields the adapter emits
(`calls[]`, `feed.accepted`, `remount.*`, `service.iterations` /
`service.guard_tripped`), additive to the `events` array the oracle consumes.
**None of these has a value yet** — no run occurred.

**There are no VO08 envelopes in the packet.** The diagnostic never produced a
linkable executable, so the runner never invoked an adapter and no media was ever
written. `preserve.sh` is in place and will capture both envelopes on the first
run that links. This is an absent run, not lost media; I am flagging it rather
than presenting the packet as a complete product-run record.

## 5. Smallest covered mount split from #20 — matrix and plan

The disposition on main confirms 289/289 for the mount tranche's assertions and
nothing else. I reproduced that against a four-object split built from `2e0e8a4b`
(`crc32.o mount.o tapefs.o alloc.o`): 289 cases, 0 failed, seed `0xd8a607`
(`mount-split-289.jsonl`). Reproduction, not acceptance.

### Path / behaviour / dependency matrix

| #20 path | Behaviour | Covered by landed tests? | Dependency / verdict |
|---|---|---|---|
| `engine/include/tape_dev.h` | device interface, `tape_result` enum, §3.1 predicate commentary | Required by every case | **In.** Prerequisite for any link. |
| `engine/include/tape.h` | DRAFT-8 public surface | Mount subset exercised; ops only *declared* | **In.** Declarations of uncovered ops are inert — calling one is a link error, which is the intended loud failure, not latent behaviour. |
| `engine/src/crc32.c` | CRC-32 | Yes (`M-bad-crc`, all index CRC cases, plus `test_crc32` 21 checks) | **In.** No dependencies. |
| `engine/src/tapefs.c` | superblock/index parse, geometry, §5.2 validity, disjointness, `tape_derive_free_next` | Yes — the bulk of the 289 | **In.** Depends only on `crc32.c`. |
| `engine/src/mount.c` | phases 0–4, both sides, degraded-B, stage oracle, repair, info, `tape_tell`, `tape_unmount`, `tape_set_side` | Yes | **In.** Depends on `tapefs.c` **and on one symbol in `alloc.c`** — see below. |
| `engine/src/tape_internal.h` | private state, internal declarations | Mixed | **In, with a named caveat.** See "what rides along". |
| `engine/src/alloc.c` | `tape_chunks_for_frames`, `tape_may_reference`, `tape_may_allocate`, `tape_alloc_run` | **Partly.** Only `tape_chunks_for_frames` has a covered use. | **Split point.** See below. |
| `tests/harness/media.h` | implementer fixture builder | Software scaffolding | In. Not a coverage claim. |
| `tests/harness/test_mount.c` | implementer mount tests | Software scaffolding (60 checks) | In. Never a substitute for independent tests. |
| `tests/harness/test_alloc.c` | implementer allocator tests | Software scaffolding for **uncovered** behaviour | **Out**, unless `alloc.c` goes in. |
| `tests/Makefile` | adds `test_alloc` to the glob | Build plumbing | Follows whatever `alloc.c` does. |

### `alloc.c` is the real split point, and the split is not file-clean

`mount.o` has an undefined reference to `tape_chunks_for_frames`, which lives in
`alloc.c`. Dropping `alloc.o` from the archive fails the link — measured, not
assumed:

```
mount.c:401: undefined reference to `tape_chunks_for_frames'
```

The single use is in `check_stage_oracle`, computing the chunk length of Side A's
timeline for §9.3.3 resume row 3. That use **is** covered: COVERAGE.md lists one
accepted fixture per resume row on both requested sides (`M-stage-row*`).

The other three `alloc.c` functions are the WP-07 allocator. COVERAGE.md is
explicit that `ownership.py` supplies **predicates only**, with no trace adapter
and "no evidence against allocator". In a mount-only engine they are referenced
by nothing but `tests/harness/test_alloc.c`.

Three options, with my recommendation:

1. **Include `alloc.c` whole.** Smallest diff, mechanical, link works today — but
   merges `tape_alloc_run`/`tape_may_allocate`/`tape_may_reference` with zero
   executable independent coverage. Reachable only through the six unimplemented
   operations, so not reachable in practice, but still uncovered code on main.
2. **Move `tape_chunks_for_frames` into `tapefs.c`** (or a covered helper file)
   and leave the three allocator predicates on the held branch. Then the mount
   split is genuinely self-contained. This is a real code change and explicitly
   **not** mechanical, so it is a proposal for PM, not something I did.
3. **Wait for VT8-001 to execute.** Blocked: nothing implements the six operations.

**Recommendation: option 2**, as a separately reviewed, PM-approved change — it is
the only one that makes "smallest covered split" true rather than approximately
true. Option 1 is acceptable if PM would rather not touch code this round, provided
the residual is recorded as uncovered-but-unreachable rather than covered.

### What rides along even in the smallest split

Stated so it is not discovered later. `struct tape` in `tape_internal.h` carries
fields that mount **derives** but only uncovered operations **consume**:
`rate_q16_16`, `at_end`/`at_start`, `play_ring_valid`, `faulted`, `free_next`,
and `cartridge_sequence`.

`cartridge_sequence` is the one that matters. Mount derives §5.5's maximum over
all four structurally valid slots, and `tape_info` has no sequence field — so
**no landed executable test can observe whether that derivation is right.** That
is precisely the hole VT8-001 exists to close, and VT8-001 cannot run. So:
merging any mount split lands the §5.5 derivation on main with its correctness
unobserved. That is a bounded, named risk for PM to accept or refuse; it is not
mine to wave through, and it is the strongest argument for not merging any split
until an engine can link VT8-001.

**The 289/289 disposition does not make mixed files or later code safe.** This
matrix is a plan. I am not proposing a merge in this round and no wholesale #20
merge is proposed at any point.

## 6. VR-P1-001 — read-only proposal

Proposal only. I changed no repository setting, enabled and bypassed no rule, and
hid no failure. Michael decides; I have no admin action pending.

### Actual check names and triggers, as they exist today

GitHub reports these as `<workflow> / <job name>`. Triggers for both workflows:
`push` on `**`, `pull_request`, `workflow_dispatch`.

| Check name | Currently |
|---|---|
| `engine / build (-Werror)` | green |
| `engine / spec bundle matches VERSION.md` | green |
| `engine / guardrail gates` | green |
| `engine / gates can go red` | green (15/15 negative controls) |
| `engine / scaffolding + verifier infrastructure` | green |
| `engine / independent DRAFT-8 mount package self-checks (not engine acceptance)` | green (10/10) |
| `engine / golden suite (awaiting WP-11 fixtures)` | **RED, by design — WP-11 fixtures absent** |
| `hardware / KiCad ERC / DRC` | green |
| `hardware / print packet is printable` | green |
| `hardware / CAD rebuilds, and the geometry matches the analysis` | green |

I re-ran the full gate set locally at this commit: every gate above green, golden
red on `no tests/golden/MANIFEST`. The WP-11 red stays visible and stays out of
any required set.

### Proposed protection for `main`

| Setting | Proposed | Why |
|---|---|---|
| Require a pull request before merging | **on** | PM commits docs/spec directly today; that still works through a PR. |
| Required approvals | **0** | More would deadlock a five-context project with one implementer and a deliberately blind verifier. Structural Rule 1 is enforced by required checks and review discipline, not by an approval counter. |
| Dismiss stale approvals | off | Nothing to dismiss at 0. |
| Required status checks | the six green `engine /` jobs above **plus** `hardware / print packet is printable` | Every one is deterministic and currently green. |
| **Excluded** from required checks | `engine / golden suite (awaiting WP-11 fixtures)`; `hardware / KiCad ERC / DRC`; `hardware / CAD rebuilds…` | Golden is the known-red WP-11 gate: requiring it blocks all work, and *removing its red* to satisfy protection would be hiding a gate. The two KiCad/CAD jobs depend on external tooling (CadQuery) whose absence is a failure, not a skip — they should stay visible and non-blocking until their environment is pinned. |
| Require branches up to date | off | Forces a serial rebase queue for no safety gain at this size. |
| Require conversation resolution | on | Cheap, and it matches "return findings to Verification/PM". |
| Require linear history | off | Merging base into a branch is the documented way to resolve a conflict without rewriting someone's branch. |
| Force pushes / deletions | **blocked** | Protects landed spec hashes, imported verifier trees and the freeze record. |
| Enforce for administrators | **PM decision.** Recommend **on**, with Michael retaining the ability to lift it. | On is the honest setting; Michael's reserved authority is exercised by changing the rule deliberately, not by routinely bypassing it. |

Compatibility check, since the issue asks for it: PM keeps publishing docs and spec
directly — a PR with 0 required approvals and green checks is a single step and
needs no reviewer. Software integration is unaffected. Nothing here can be read as
granting merge authority over held engine code: the coverage hold is a product
rule, and no branch-protection setting implements or relaxes it.

**Suggested additional check, not enabled.** `tests/ops_draft8` has no CI job, so
the package I just imported currently runs nowhere in CI. I did not add one —
item 6 is read-only and this is a check-set change. Proposed for PM/Michael:

```yaml
  ops-package:
    name: independent VT8-001 package self-checks (synthetic, not engine acceptance)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python3 tests/ops_draft8/selftest.py
```

The name carries "synthetic, not engine acceptance" deliberately: the job proves
the oracle catches its six mutations, and must never be mistaken for a product run.

## Residual holds — all intact

Structural Rule 1; PR #20 held with no wholesale merge and no merge proposed;
VT8-001 unexecuted, so allocation-event and all-slot running-sequence consumption
remain **unobserved**; warm-start, state-transition, operation, overwrite/overdub,
stage-clearing, promote, re-spool, duplicate, format, crash-injection, FAULTED and
rendered-PCM exclusions unchanged; full WP-07 including the 10,000 random-edit
requirement, complete green WP-10, WP-11 goldens, WP-12a, WP-36 all open; frozen
DRAFT-8 hashes unchanged; WP-11 golden CI still red and visible; hardware
fabrication/charging gate verified **CLOSED** (exit 2); no purchase, no card
substitution; Michael's reserved approvals untouched.

Two VT8-001 cases — which have not run — accept nothing.

## What PM needs to decide

1. `alloc.c` split: option 1, 2 or 3 above. My recommendation is 2.
2. Whether merging any mount split is acceptable while §5.5's
   `cartridge_sequence` derivation stays unobservable.
3. Who implements the six missing operations, and in what order relative to
   VT8-001 — noting Structural Rule 1 is already satisfied for these two case IDs,
   because their tests are now landed on main and the implementation is not.
4. Whether main's public-header divergence from the frozen API is in scope for a
   later round.
5. VR-P1-001: forward the protection table to Michael, and whether to add the
   proposed `ops-package` CI job.
