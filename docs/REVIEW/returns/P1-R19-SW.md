# P1-R19-SW — corrected VT8 import and held-product rerun

**Issue:** [#102](https://github.com/mmsanders/Digital-Tape/issues/102) ·
**Input product main:** `fba51ad403ad0fcc20019b88a7f34beaeb3c389f` ·
**Verifier publication:** `digital-tape-verification@15dd16eb499f5c148bff7c5b4b67ff75ae7a0f32`

Both phases completed. **Both VT8-001 cases PASS and offline replay PASSES**, with
the engine and the product adapter unchanged from the P1-R17 candidate. That is an
observation for PM and independent Verification, not acceptance of anything.

## Phase A — exact test-first import (merged)

| Item | Value |
|---|---|
| Import commit | `d0e0fe0fdaf3f7c5a84bbc01a67564794335a240` |
| Import PR | [#104](https://github.com/mmsanders/Digital-Tape/pull/104) |
| Merge commit | `48cc23fdbe6273dfe73f17fbdddf8e9fcc5ab3d9` (parents `fba51ad4…`, `d0e0fe0f…`) |
| `tests/ops_draft8` before | `4a862fa69ccb2fc4c9afe59c9c9161c3470f9263` |
| **`tests/ops_draft8` after** | **`3667a2830ba80dbcedad03b97870d1127001ab59`** — exactly the routed tree |

Imported with `git read-tree --prefix=tests/ops_draft8` from the exact verifier
commit, so modes and bytes carry over and subtree identity is a hash fact. The
**complete** subtree, including the retained `evidence/p1-r1-synthetic/` and
`evidence/p1-r18-synthetic/` sets — not the changed source paths.

Changed paths: 8 modified source files, 38 added evidence files, **all** under
`tests/ops_draft8/`. Paths changed outside that prefix: **0**.

## Phase B — unchanged held-product rerun

| Item | Value |
|---|---|
| PR #96 head before sync | `b26ffa02e8c6f016762689d2bad9aaa8b40b1fc1` |
| **Pre-run code commit** | `e1aaf5f3f441e5126e821a0bd2cfa54a98894294`, tree `0d340e1583fece209a2fc2516aeba8b1efb3610b` |
| Sync method | `git merge --no-ff origin/main` — **no force push, no rebase, no history replacement** |
| Merge parents | `b26ffa02…` (held head) and `48cc23fd…` (new main) |

**All 25 held engine/header/`tests/ops_adapter` blobs are byte-identical across the
synchronization.** Recorded before the merge and re-read after; `diff` is empty.
`engine/` stays tree `7f73812ff5ade35d95b848c0df1fd0458aad22ca` and
`tests/ops_adapter/` stays `6f6df812ae346933dff91aebb739feb0e2f0a113`. No
implementation was fixed, broadened or otherwise touched.

The two change sets are disjoint by construction: this branch changes nothing under
`tests/ops_draft8/`, and main changed nothing outside it.

### Results

| Case | Adapter outcome | Exit | Verdict |
|---|---|---|---|
| `VT8-001-RB-ALLSLOT` | `exited` | 0 | **PASS** |
| `VT8-001-REC-ALLOCSEQ` | `exited` | 0 | **PASS** |

Offline replay: **PASS** — evidence complete, hash-bound, DRAFT-8 authenticated,
both verdicts recomputed without invoking the engine or adapter.

Both P1-R17 findings are closed by the corrected package rather than by a product
edit: the fixture now derives `total_chunks` from its own `nominal_length_s`
(21 chunks, 23,553 blocks), and `VT8-EVIDENCE-2` plus the manifest-bound
`VT8-ADAPTER-STATUS-1` let runner and replay agree on adapter status either way.

## Exclusions and holds

Unchanged and unclaimed: warm start; overwrite/overdub; `tape_abort`; zero-frame
commit; crash/recovery; FAULTED quarantine; promote/re-spool/duplicate/format;
stage clearing (both fixtures are `promote_stage == 0`); interior splice; partial
-block drain; multi-chunk allocation; `CARTRIDGE_FULL` short accept; performance;
media atomicity; PCM; goldens; listening.

The `tape_arm` mode boundary from P1-R17 still stands and still needs PM
disposition: `TAPE_REC_SPLICE` only, with `TAPE_REC_OVERWRITE` and
`TAPE_REC_OVERDUB` refused `TAPE_ERR_INVALID_ARG` and zero writes — a divergence
from engine-api §7.

Structural Rule 1 served: corrected tests landed on main before any product change.
DRAFT-8 and WP-08 bytes unchanged. PR #20, #64 and **#96 remain held; #96 was not
merged.** WP-11 golden failure red, visible, unrequired. No self-acceptance, no
package acceptance, no hardware or purchase action.
