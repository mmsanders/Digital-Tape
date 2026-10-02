# WP-10 residue destinations (DRAFT-10, V10-001): public-observation adapter contract

Use public calls only (`tape_dup`, `tape_format`, `tape_mount`, `tape_get_info`) and a caller-owned
fault-injecting device. Do not import this oracle, read private engine state, or emit verdicts. The
oracle rejects `verdict`, `passed`, `permitted`, `expected`, `outcome_ok`, `row_ok`, `phase` and
`category`.

Emit one `wp10-residue-d10-observation-v1` JSON object per `plan.iter_groups()` entry, in order, one per
line (plain or gzip JSONL). Each object carries `schema` and the group identity fields: `index`, `row`,
`op`, `mode`, plus `shape`, `l1`, `scope` or `variant` where present.

## Conventions

- **Geometry.** Use the R29-B 4-chunk / 9 s geometry (`format_dup_identity_draft8/fixture.py`).
- **Destination blocks.** Use the `model.TRACKED` blocks from `plan.base(*shape)` or `plan.blank(variant)`.
  Every other block is zero.
- **`dup` arguments.** The source is a separate 4-chunk device whose Side A is `{0,0,128}`, with chunk 0
  block 0 = `model.SOURCE_AUDIO`. Its label is empty. Call `tape_dup(src, dst, FRESH_DUP_UUID, 0, 9,
  65535)` until `more_work == false`.
- **`format` arguments.** Call `tape_format(dst, FRESH_FORMAT_UUID, 0, "", 9)`.
- **Budget.** Any `block_budget` may be used. Call partitioning is not asserted.
- **Device modes.** The `mode` applies to the device for the whole group, including the first run and every
  re-run.
  - `flush_required`: a completed write is durable only after the next flush. On power loss, any subset of
    the unflushed writes may survive.
  - `write_through`: a completed write is durable at once.
- **Injection coordinates.** Count from 0, separately for writes and flushes.
  - `["write", k, landed]` cuts power during the k-th write callback, with `landed` bytes (0…512) of it on
    the medium.
  - `["flush", j]` cuts power at the j-th flush. That flush may or may not have taken effect.
- **Durable digest.** `durable_sha256` is the SHA-256 of the durable `model.TRACKED` blocks, concatenated
  in sorted name order. `d16` is its first 16 hex characters.
- **Mount code.** Remount the durable bytes with a writable `tape_mount` on Side A and report:
  - the error name (`TAPE_ERR_BAD_MAGIC`, `TAPE_ERR_CRC`, …); or
  - `OK.` followed by the first 8 hex characters of `tape_get_info().uuid`.

## R1: torn last fallback zero, then the re-run (shape (a))

1. On `plan.base(*plan.EXHAUSTION_SHAPES[shape])`, run `op` and cut at `["write", 1, l1]`. That is the §4.5
   fallback's last zero, torn after `l1` bytes.
2. Report `first_run: {trace_sha256, durable_sha256, mount}`. The trace covers every write and flush
   callback up to and including the cut one. The cut write is recorded with the full data the engine passed,
   in the `plan.trace` form `{"op":"write","lba","count","data_sha256"} | {"op":"flush"}`.
3. **Clean re-run.** On a copy of those durable bytes, run `op` uninterrupted. Report
   `rerun: {call: {fn, result, more_work}, trace_sha256, durable_sha256, mount}`.
4. **Injections.** Take the coordinate list from that clean re-run's own trace:
   - every flush;
   - every landed length 0…512 of every write whose LBA is a superblock LBA (0 or the mirror), when
     `scope == "superblock_writes"`;
   - every landed length 0…512 of every write, when `scope == "all_writes"`.

   List coordinates in call order. For each one, start again from the step-1 durable bytes, run `op`, cut
   there, and append `"<d16> <mount code>"` to `injections`.

## R2: crafted residue (shapes (b)–(d))

1. The precondition is `plan.base(*plan.RESIDUE_SHAPES[shape])`. Report
   `precondition: {durable_sha256, mount}`.
2. Report `rerun` and `injections` exactly as in R1 (`scope` is `all_writes`).
3. **Closure.** Some injections fall before the engine's first write to a non-superblock LBA, which is the
   residue-zeroing phase. After each of those remounts, run `op` again, uninterrupted, on the same durable
   bytes. Append `"<trace16> <final d16> <mount code>"` to `closure`, in the same order. `trace16` is the
   first 16 hex characters of that run's `trace_sha256`.

## R3: all-zero blank

Run `op` uninterrupted on `plan.blank(variant)`. Report `call`, `trace_sha256`, `write_lbas` (the LBA of
every write callback, in order), `durable_sha256` and `mount`.

## Replay

```sh
python3 replay.py OBS.jsonl.gz --manifest PRODUCT-MANIFEST.json --adapter-kind product \
  --adapter-source-sha SHA --product-commit SHA --product-tree SHA
```

A passing replay still needs an independent disposition.
