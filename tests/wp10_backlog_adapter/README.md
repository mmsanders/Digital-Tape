# WP-10 backlog rows 1–3 product binding

Software-owned binding of the imported verifier package `tests/wp10_backlog_r53`.

- Tree `7f80e382fc915aec4d9b8e1a9226b6c22a2da3f8`, from Verification #110 / PR #113 commit
  `fd139dfa42a9447d889c700b0818e3d1f9099e81` (branch `verification/issue-110-wp10-backlog`).
- Case set `036e255e…aaf3`, with 79,820 cases:
  - row 1: 24,660 injections and 2 completions;
  - row 2: 28,760 C69 and 26,392 R29-B;
  - row 3: 6 groups.
- The eight `deps.py` pins equal the accepted `crash_core_draft8` and
  `format_dup_identity_draft8` blobs on main.
- Built on main `66c6abc6` (after #311, before #318); engine tree `054d27ab…`.
  `build-identity.json` records the engine tree, which is not pinned (the #320 pattern).
  No engine change.

**Canonical result, decided by the package's own `replay.py`: FAIL.** It stops at the
first row-2 C69 case, on a plan finding. Rows 1 and 3, all 26,392 R29-B row-2 cases,
and 292 C69 row-2 cases pass. The other 28,468 C69 row-2 cases fail only on the
snapshot-binding field this README's finding describes. Neither acceptance nor a
complete WP-10 claim is made.

## What runs

Everything includes only `engine/include` and uses the public API. The package's
`oracle.py` is never imported. `run_product.py` restates the plan order:

- row 1 from `dupfrag.SCENARIOS` / `dupfrag.injections`;
- row 2 from the accepted campaigns' models, loaded through the package's own pinned
  `deps.py`;
- row 3 as record modes × durability modes.

It assembles one `wp10-backlog-r53-observation-v1` object per case, in plan order.

| Program | Rows | Derived from |
|---|---|---|
| `wp10b_row1.c` | 1 | held #318's `wp10c_adapter.c`: the same fault-injecting sparse device, durability settling, trace format and `ro_A`/`rw_A`/`rw_B` remounts. The changes are per-device geometry (the source is 8 chunks, the destination 4) and `dst_chunk_lbas`, which records every destination read/write block at or above `LBA_CHUNK_BASE`, except the mirror, before any range check. |
| `wp10b_c69_worker.c` | 2 (C69) | the accepted `tests/crash_core_adapter/wp10_core_worker.c` (`46ec919d…`). Its one change: after the fresh post-crash remount, `tape_get_info`'s `total_chunks`/`free_chunks` are reported. |
| `wp10b_r29b_worker.c` | 2 (R29-B) | the accepted `tests/format_dup_identity_adapter/r29_format_dup_worker.c` (`c6a43b9d…`), cut to its crash path. Its contract families and their `tape_internal.h` white-box access are removed, and the same two `tape_get_info` fields are reported. |
| `wp10b_row3.c` | 3 | new. On the C69 record fixture it runs mount B, seek 0, arm, feed 384 frames, then `tape_service(1)` until done. It records the clean service trace, then replays and cuts power at every service write (landed 0..512) and every observed service flush. Each cut is followed by a fresh writable Side-B remount and a whole-side render. |

## Binding choices for Verification to audit

- **Row-2 membership.** It is restated from the accepted campaigns' own models via
  `deps`: a C69 or R29-B case is included when its model's post-crash state remounts
  `TAPE_OK`. That reproduces `oracle.row2_cases` exactly (28,760 and 26,392). #318
  restated its order from `model.py` the same way.
- **Row-2 snapshot.** `post_snapshot_sha256` is the SHA-256 of the canonical compact
  JSON of the worker's `post_snapshot`. That is the compact snapshot object each
  accepted binding already emits, built from raw durable bytes.
- **Row-1 source.** The superblock is the pinned R29-B builder's
  `superblock(generation=1, uuid=OLD_UUID_A, high=8, nominal=21)`, with
  `total_chunks` (8) and `lba_superblock_mirror` (10,240) rewritten for this
  geometry and the CRC recomputed.
  - Side A is `SRC_ENTRIES` at sequence 1.
  - Side B is a valid empty index at sequence 2.
  - Every referenced frame is `dupfrag.src_frame`.
- **Row 3.**
  - The stimulus is frame i = (1000 + i, −1000 − i).
  - A flush-required cut discards every unflushed write.
  - A torn write lands its first `landed` bytes over the durable block.
  - `prefix_len` counts service-phase callbacks, reads included, through the injected
    one.

## Finding: row 2 binds C69 to summary digests the accepted campaign never binds

`oracle.check_row2` requires `post_snapshot_sha256 ==
sha256(canonical(C69.oracle.expected_snapshot(case, C69.oracle._fixture_snapshot(case))))`.
That object has two summary fields the accepted C69 oracle never compares (it
compares `_raw_parts` and chunk digests against the observed pre-snapshot):

- **`image_sha256`.** The C69 model copies the pre-operation image digest forward
  unchanged (`expected_snapshot` never recomputes it). A real post-crash image whose
  metadata changed cannot hash to it.
- **`chunk_sha256`.** The row-2 model is built from the pristine fixture, not the
  case's observed pre-snapshot. For `record_commit`, the case's own setup
  (`setup_record`: feed one frame, service) writes an audio chunk before the crash
  scope. The durable chunk set therefore differs from the fixture's.

`diagnostic_row2_c69.py` is non-canonical. It re-runs every planned C69 row-2 case and
checks five facts per case. In **all 28,760** of them:

- the Product's superblocks and index slots equal the row-2 model's;
- its full bytes pass the accepted campaign's own comparison (`_raw_parts` against
  the model built from the observed pre-snapshot);
- its chunk digests equal its own pre-snapshot;
- `free_chunks` equals `total_chunks − max(a_high_water, live-B last+1)`, which is row
  2's actual assertion;
- the only differing fields are `image_sha256` and, for `record_commit`,
  `chunk_sha256`.

The 292 passing cases are the ones whose metadata did not change. Its report is
`evidence/p1-r54-product/diagnostic-row2-c69.json`.

A Product binding could satisfy the plan only by emitting the model's digests instead
of its own snapshot, which would be fabricating the observation. Suggested
correction for Verification is either of these:

- bind row 2 to the metadata parts (`primary_hex`, `mirror_hex`, `slots`) of the
  fixture-based model;
- bind to `_raw_parts` of the model built from the observed pre-snapshot, as the
  accepted campaign does.

Either way the `free_chunks` assertion is unchanged. No engine change is involved.

## Run

    make -C engine clean all
    make -C tests/wp10_backlog_adapter clean all
    python3 tests/wp10_backlog_adapter/run_product.py --evidence <fresh dir> \
        --retained tests/wp10_backlog_adapter/evidence/p1-r54-product
    python3 tests/wp10_backlog_adapter/run_product.py \
        --replay tests/wp10_backlog_adapter/evidence/p1-r54-product/observations.jsonl.gz \
        --retained tests/wp10_backlog_adapter/evidence/p1-r54-product --out <fresh dir>
    python3 -B tests/wp10_backlog_adapter/negative_controls.py <dir>/observations.jsonl.gz
    python3 -B tests/wp10_backlog_adapter/diagnostic_row2_c69.py --out <report.json>

The canonical run takes about 5 minutes and the diagnostic about 4. With `--retained`,
the fresh JSONL must equal the committed SHA-256 before replay. `--replay` works
offline.

`negative_controls.py` is non-canonical. It prints the per-row census of
`oracle.check` outcomes. It then requires the oracle to reject 9 single-fact
mutations of passing Product observations:

- **Row 1:**
  - a destination chunk id ≥ `total_chunks`;
  - a layout-preserving chunk address;
  - a changed source;
  - a wrong `free_chunks`.
- **Row 2:** a frontier off by one, and another durable state.
- **Row 3:**
  - metadata changed before commit;
  - a wrong remount;
  - an extra service write.

It exits 1 if a control survives, or if any failure falls outside the row-2 C69
finding.

## Retained evidence (`evidence/p1-r54-product`)

The evidence was produced on Linux (gcc 13.3). It is the complete stream as a
deterministic gzip of 853,031 bytes, under the 1 MiB tree limit, so no release asset
is needed.

| File | SHA-256 |
|---|---|
| `observations.jsonl` (39,804,565 bytes, not committed) | `7d9da70ac817ba0bc251b06aaa7bb989e616c43a81b630bc7fee9fe3edff6ce9` |
| `observations.jsonl.gz` | `17f86d1bf2744ae180d13cb7152e8c4b77dcb8e04a4c517682e84ed565a4ce18` |
| `build-identity.json` | `43e5230adec7fcb713e9cfc78b797afb3f2b1996e8fdc7dddce3574a650f1bb9` |
| `diagnostic-row2-c69.json` (non-canonical) | `4291fbe8e56725df424cf6301b6560692664fb0ea87e59ff18201c551de4ae60` |
| adapter sources, combined digest | `2b66c4f779cdb125c1bf3fdec0af17c85914e38dddf137cb57b5d4b6aa5ff29c` |

## Exclusions

The remaining 6 backlog rows (Verification #118), WP-12/WP-12a, WP-11, hardware and
release. No complete WP-10 claim.
