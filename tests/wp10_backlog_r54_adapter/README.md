# WP-10 backlog r54 product binding (mount repair crash, dup re-run, dup shape)

Software-owned binding of the imported verifier package `tests/wp10_backlog_r54`.

- Tree `d6e9a2427ed9b6c4b703c65dc44eb7e13224cabc`, from Verification #116 / PR #117 commit
  `dea9b521ccee76a69cfd0d517903eb27474d41fc` (branch `verification/issue-116-wp10-backlog`).
- Case set `6808330224da3129371f482e1828eab36b801d7caa13652dfc69a99e7493aaf3`, 68,854 cases:
  - row 1 (`WP10.session.load.mount_repair_write`): 4 shapes, 4,112 injections;
  - row 2 (`WP10.dup.rerun_completes`): 5 shapes, 64,734 injections;
  - row 3 (`WP10.dup.destination_shape.mounts_both_sides_high_label`): 4 sources × 2 destinations.
- Built on main `66c6abc6` (after #311, before #318); engine tree `054d27ab…`.
  `build-identity.json` records the engine tree, which is not pinned (the #320 pattern).
  No engine change.

**Canonical result, decided by the package's own `replay.py`: PASS, 68,854 observations.**
That is a Software return, not acceptance, and no complete WP-10 claim.

## What runs

`wp10r54_adapter.c` includes only `engine/include` and uses the public API. The package's
`oracle.py` is never imported. `run_product.py` restates the plan order from the package's
`model.py` (`REPAIR_SHAPES`, `RERUN_SHAPES`, `injections`, `repair_ops`, `dup_ops`) and the
row-3 source table from `ADAPTER.md`, and refuses to run unless the restated plan hashes to
the recorded case set. It writes one input file (fixtures, tracked LBAs, cases) and the
adapter emits one `wp10-backlog-r54-observation-v1` object per case, in plan order.

The fault-injecting sparse device, durability settling (flush-required cuts discard every
unflushed write; write-through cuts keep every completed write; a torn write lands its first
`landed` bytes) and the trace format are carried from `tests/wp10_backlog_adapter/wp10b_row1.c`
(PR #329, itself from held #318's `wp10c_adapter.c`). The three case drivers are new.

## Binding choices for Verification to audit

- **Fixtures.** Row 1 `model.cartridge(*REPAIR_SHAPES[shape])`; row 2 and row-3 destinations
  `model.rerun_destination(shape)`; each placed at the `model.TRACKED` LBAs of a
  `B.BLOCK_COUNT` (4-chunk / 9 s) device, every other block zero.
- **Sources.** One builder for the row-2 source and the four row-3 sources, on the same
  4-chunk geometry: the pinned R29-B `superblock(generation=1, uuid=OLD_UUID_A,
  high=ceil(frames / CHUNK_FRAMES))` with `model.with_label` applied, at LBA 0 and the mirror;
  Side A `{0,0,frames}` (or an empty index) at sequence 1; Side B a valid empty index at
  sequence 2; chunk 0 block 0 `model.SOURCE_AUDIO` for 128 frames, all other audio zero. The
  row-2 source is that builder with 128 frames and no label.
- **Injection.** The device counts writes and flushes from its first call. Row 1 arms it for
  the writable Side-A mount; row 2 for the first `tape_dup` run (`FRESH_DUP_UUID`, `0`, `9`,
  budget 65535, repeated until `more_work == false` or the cut). `fired` is the device's own
  record that the planned call was reached.
- **Row 2 re-run.** After settling, the same `struct dev` is reset to hold exactly the settled
  durable bytes, in the same durability mode, with no format in between; `tape_dup` runs again
  with the same arguments, from a fresh source instance, until `more_work == false`.
  `dst_chunk_lbas` is every destination block the re-run read or wrote at or above
  `LBA_CHUNK_BASE`, except the mirror, recorded before any range check, sorted.
- **Mounts.** Each remount is a fresh write-through device and instance holding the bytes
  under test. `repair_events` are the mount's writes/flushes. `pcm_sha256` is a 1.0× render of
  the whole side from frame 0 (`tape_render`, little-endian). Row-1 `ro_A` mounts through a
  NULL-write binding; `durable_after_rw_sha256` is the tracked digest after `rw_A`.
- **Row 3.** `source_label_hex` is raw superblock bytes 88..120 of the source fixture;
  `source_pcm_sha256` is the source Side-A render through a read-only mount. `raw_after` is
  LBA 0, the mirror, `LBA_A0` and `LBA_B0` of the destination after the copy.

## Evidence (`evidence/p1-r54-product/`)

| File | SHA-256 |
|---|---|
| `observations.jsonl` (71,735,125 bytes, not retained) | `3a0cff6118e938cf6a59ef2c3b85149a67885b27c63a33a18deed36f8ab9347e` |
| `observations.jsonl.gz` (1,030,787 bytes) | `b4492d4bda9b4b2700c0f755c72e4d89034da0dae27c7760b0f0f5e9699ca631` |
| `build-identity.json` | `d1f0a25ba7f4bd77f99152c4c86840177818f6ad62335498f311614da44617bd` |

The gzip is standard gzip written with zlib `Z_FILTERED` at level 9 (mtime 0, no name), which
keeps it under the 1 MiB tree limit; the stdlib default strategy gives 1,059,060 bytes.
`run_product.py` refuses to write a gzip over 1 MiB. GCC and Clang builds regenerate the same
JSONL.

```sh
make -C engine clean all && make -C tests/wp10_backlog_r54_adapter clean all
python3 tests/wp10_backlog_r54_adapter/run_product.py --evidence OUT \
  --retained tests/wp10_backlog_r54_adapter/evidence/p1-r54-product
python3 tests/wp10_backlog_r54_adapter/run_product.py \
  --replay tests/wp10_backlog_r54_adapter/evidence/p1-r54-product/observations.jsonl.gz \
  --retained tests/wp10_backlog_r54_adapter/evidence/p1-r54-product --out OUT2
python3 -B tests/wp10_backlog_r54_adapter/negative_controls.py OUT/observations.jsonl.gz
```

`negative_controls.py` (not canonical) runs `oracle.check` per case (4,112 / 64,734 / 8 PASS,
0 FAIL) and then requires it to reject 12 single-fact mutations of passing Product observations:
4 per row. All 12 are killed. The CI job `wp10-backlog-r54-package` runs the package audit and
self-test, the offline replay, the canonical regeneration against the committed SHA-256, and
the controls.
