# WP-10 R53 public-observation adapter contract

Build a separate adapter at the Product identity PM supplies. Use public calls only and a
caller-owned fault-injecting file device. The adapter must not import this oracle, read private
engine state, or emit verdicts. The oracle rejects fields named `verdict`, `passed`, `permitted`,
`expected`, `outcome_ok`, `selected_copy`, `phase` or `row`. Emit one `wp10-r53-observation-v1`
JSON object per case in `oracle.iter_cases()` order, as gzip JSONL.

## Fixtures

Build every destination from `model.destination(shape)` on a 4-chunk / 9-second device
(`block_count` = `format_dup_identity_draft8.fixture.BLOCK_COUNT`). Unlisted blocks are zero.

The duplicate source is a separate device that mounts Side A:

- **128 frames:** one entry `{0,0,128}`, chunk 0 block 0 = `model.SOURCE_AUDIO`.
- **Empty:** a freshly `tape_format`-ed cartridge.

Calls:

- **dup:** `tape_dup(src, dst, FRESH_DUP_UUID, epoch 0, dst_nominal_length_s 9, block_budget 65535)`,
  repeated until `more_work == false`.
- **format:** `tape_format(dst, FRESH_FORMAT_UUID, epoch 0, label "", 9)`.

## Crash cases

The device must fire exactly one injection at the planned coordinate:

- `["write", k, landed]`: power is cut during the k-th write callback (0-based). The first
  `landed` bytes of that block become durable (0 = before, 512 = after).
- `["flush", j]`: power is cut inside the j-th flush.

In flush-required mode, completed writes since the last successful flush may or may not be
durable; choose any subset. Write-through makes every completed write durable at once.

Record:

- `fired: true`;
- `trace_sha256`: SHA-256 of the canonical JSON list of every callback up to and including the
  injected one, `{"op":"write","lba","count","data_sha256"}` (the full intended block) or
  `{"op":"flush"}`;
- `durable_sha256`: SHA-256 of the durable bytes of the `model.TRACKED` blocks, concatenated in
  sorted name order.

Then take three fresh devices holding those durable bytes and mount each:

1. **`ro_A`**: `write = NULL`, Side A.
2. **`rw_A`**: writable, Side A. Add `pcm_sha256` of rendering the whole side at 1.0× from
   frame 0.
3. **`rw_B`**: writable, Side B.

Each mount is `{result, repair_events, info}`. `info` is `{uuid (hex), free_chunks, total_frames,
entry_count, side_b_valid, needs_repair}` from `tape_get_info`, present only on `TAPE_OK`.
`repair_events` lists every callback made by the mount, in the trace format.

Dup cases also carry `source_sha256_before` and `source_sha256_after`: SHA-256 of the whole
source device image.

On the first failure, retain a reproducer: the case, the raw bytes of every tracked block, and
the full trace.

## Completion and family cases

**`complete`** runs the operation uninjected. Record `call` (`{fn, result[, more_work]}`), the
full-run `trace_sha256`, `durable_sha256`, and the same three mounts.

**`empty_family`**, on the completed empty copy:

1. `tape_mount(B)`, recorded as `mount_B`.
2. Record `family`: `tape_promote(65535)`, `tape_respool(65535)`, `tape_arm()`, then a zero-frame
   `tape_commit()`. Each entry is `{fn, result[, more_work], block_events}`.

Replay with `replay.py --adapter-kind product --adapter-source-sha SHA --product-commit SHA
--product-tree SHA`. A passing Product replay still needs independent disposition. The replay
manifest records the count of `TAPE_ERR_CRC` answers under the PM finding.
