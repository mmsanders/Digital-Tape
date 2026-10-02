# WP-10 residue destinations product binding (DRAFT-10 V10-001)

Software-owned binding of the imported verifier package `tests/wp10_residue_d10`.

- Tree `e1b885301768d7b541a5704c526881a800d7116b`, from Verification #138's publication
  `5ca24fb9c0773e715889c235c339ef035e87d63b` on Verification main (merged as #139). Import commit `a34d409`.
- Case set `849a82ab2e8e4b207a52789e2c6e9dd247c3db947431e7beb4ed14916f04b1f8`: 8,208 groups,
  17,025,380 injections and 24,672 closure re-runs.
  - R1: torn last fallback zero, then the re-run.
  - R2: crafted residue.
  - R3: all-zero blank.
  - Each row runs for `tape_dup` and `tape_format`, in both durability modes.
- Engine: the V10-001 implementation commit `44dbf61` (`engine/src/raw_ops.c` only).

The canonical result is decided by the package's own `replay.py`. It is a Software return, not
acceptance, and makes no complete WP-10 claim.

## What runs

`wp10res_adapter.c` includes only `engine/include` and uses the public calls `tape_dup`,
`tape_format`, `tape_mount` and `tape_get_info`.

`run_product.py` writes one input file per shard. Each file holds:
- the tracked LBAs, in sorted name order;
- the call arguments;
- the fixture bases, from the package's `plan.base` / `plan.blank`;
- the dup source, as ADAPTER.md specifies it;
- the groups, from `plan.iter_groups()`.

Shards are contiguous, so their concatenation is in plan order for any `--jobs`. Neither
`oracle.py` nor the planner's injection list (`plan.rerun_injections`) is imported.

**Injection coordinates come from the adapter's own clean re-run trace** (ADAPTER.md R1 step 4):
- every flush;
- every landed length 0…512 of every write, under `all_writes`;
- every landed length 0…512 of every write to LBA 0 or the mirror, under `superblock_writes`.

## Binding choices for Verification to audit

- **Device.** The WP-10 adapters' fault-injecting device, carried from
  `tests/wp10_backlog_r54_adapter`, with a sparse (lba, block) list as storage, because a group
  touches about a dozen blocks.
  - A torn write lands its first `landed` bytes over the durable block.
  - A write-through write is durable at once.
  - A flush-required write is durable at the next flush. After a cut, the subset of unflushed
    writes that survives is fixed by the injection's ordinal within its group: pending write *i*
    is kept iff bit (n−1−i) of the ordinal is set.
  - A flush cut may or may not have taken effect, which that subset covers.
- **R1 first run.** On `base_<shape>`, the device is armed at `["write", 1, l1]`. `first_run` reports
  the trace up to and including the cut write, the settled durable digest and its mount code.
- **Re-runs.** Each run starts from a fresh device in the group's mode, holding the durable bytes,
  with no format in between. `dup` uses a fresh source device and instance every time:
  - 4-chunk, Side A `{0,0,128}`, chunk 0 block 0 `model.SOURCE_AUDIO`, empty label;
  - called as `tape_dup(src, dst, FRESH_DUP_UUID, 0, 9, 65535)` until `more_work == false`.
- **Closure (R2).** These are the injections that fall before the engine's first write to an LBA
  other than 0 or the mirror in the clean re-run's trace. After each one, an uninterrupted run
  goes from that injection's durable bytes.
- **Mount code.** A writable Side-A `tape_mount` on a fresh write-through device and instance.
  It reports the error name, or `OK.` followed by the first 8 hex of `tape_get_info().uuid`.

## Retained evidence (`evidence/p1-r60-product`)

The gzip is far over the 1 MiB tree limit. It is the release asset
`wp10-residue-d10-product-observations.jsonl.gz` under tag `evidence-p1-r60-wp10-residue`. Committed
beside it: `SHA256SUMS` (the asset's SHA-256 and the uncompressed stream's SHA-256),
`build-identity.json`, and the replay's `manifest.json`. That manifest binds the stream, the census,
the outcomes reached per phase and the product commit.

`run_product.py --replay` fetches the asset when it is absent and refuses a mismatch.
`--retained` regenerates the stream on the current engine, requires the stream SHA-256 to match, and
requires `replay.py` to reproduce the committed manifest exactly.

## Run

    make -C engine clean all
    make -C tests/wp10_residue_adapter clean all
    python3 tests/wp10_residue_adapter/run_product.py --evidence <fresh dir>
    python3 tests/wp10_residue_adapter/run_product.py --evidence <fresh dir> \
        --retained tests/wp10_residue_adapter/evidence/p1-r60-product
    python3 tests/wp10_residue_adapter/run_product.py \
        --replay tests/wp10_residue_adapter/evidence/p1-r60-product --out <fresh dir>

## Exclusions

Complete WP-10 claims, WP-12/12a, WP-11, hardware and release are excluded. **S3** (R29-B,
4,032 `BAD_MAGIC`-only cases) needs no action while the engine answers `BAD_MAGIC` there, and the
unchanged R29-B regeneration shows that it does.
