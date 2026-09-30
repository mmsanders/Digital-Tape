# WP-10 backlog rows (R54): public-observation adapter contract

Use public calls only and a caller-owned fault-injecting device. Do not import this oracle, read
private engine state, or emit verdicts: the oracle rejects `verdict`, `passed`, `permitted`,
`expected`, `outcome_ok`, `same_content`, `rerun_completed` and `row_ok`. Emit one
`wp10-backlog-r54-observation-v1` object per `oracle.iter_cases()` entry, in order, as gzip JSONL. Each
carries `schema`, `index` and `row`, plus the case's identity fields.

Mount records have the form `{result, repair_events, info?, pcm_sha256?}`:

- `info` comes from `tape_get_info` and is present only on `TAPE_OK`: `{uuid (hex), free_chunks,
  total_frames, entry_count, side_b_valid, needs_repair}`.
- `repair_events` lists every write and flush during the mount as
  `{"op":"write","lba","count","data_sha256"}` or `{"op":"flush"}`.
- `pcm_sha256` is the Side-A render at 1.0× on a writable mount.

`*_sha256` digests of durable media cover the `model.TRACKED` blocks, concatenated in sorted name
order.

## Row 1: mount repair crash

1. Build `model.cartridge(*model.REPAIR_SHAPES[shape])` on the 4-chunk / 9 s geometry.
2. Mount Side A on a writable device and cut power at the planned coordinate of the phase-4 repair:
   `["write", 0, landed]` or `["flush", 0]`.

Report:

- `fired`;
- `repair_trace_sha256` over the mount's write/flush callbacks up to the injection, with reads
  excluded;
- `durable_sha256`;
- `ro_A` (a read-only remount of those bytes);
- `rw_A` (a writable remount of a fresh copy);
- `durable_after_rw_sha256` (the durable digest after that writable remount).

## Row 2: dup re-run

1. Build `model.rerun_destination(shape)` as the destination. The source is a separate 4-chunk
   device, Side A `{0,0,128}` with chunk 0 block 0 = `model.SOURCE_AUDIO`.
2. Run `tape_dup(src, dst, FRESH_DUP_UUID, 0, 9, 65535)` until the planned injection fires.
3. Report `fired`, the first-run `trace_sha256` and `durable_sha256`.
4. On the **same destination device**, holding those durable bytes and with no format in between,
   call `tape_dup` again with the same arguments until `more_work == false`.

Report `rerun: {call, trace_sha256, dst_chunk_lbas, durable_sha256}`, then writable `rw_A` and
`rw_B` mounts of the result. Any `block_budget` may be used; call partitioning is not asserted.

## Row 3: completed copy shape

1. The source is a fresh cartridge on a device large enough for its timeline. Its superblock
   `label` (offset 88, 32 bytes, NUL-padded) is `oracle.ROW3_SOURCES` label, and its Side A holds
   the listed frame count.
2. Copy it onto `model.rerun_destination(destination)`.

Report:

- `source_label_hex` (32 raw bytes);
- `source_pcm_sha256` (the source's Side A render);
- `call`;
- `raw_after`: hex of `P`, `M`, `A0h` and `B0h` (512 B each);
- `mount_A` and `mount_B`, each `{result, info: {total_frames, side_b_valid, label}}`. `mount_A`
  also carries `pcm_sha256`.

Replay with `replay.py --adapter-kind product --adapter-source-sha SHA --product-commit SHA
--product-tree SHA`. A passing replay still needs independent disposition.
