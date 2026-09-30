# WP-12 R53 public-observation adapter contract

Build a separate adapter at the Product identity PM supplies. It must use only public calls and a
caller-owned file-backed simulator. It must not import this oracle, read private engine state, or
emit verdicts. The oracle rejects fields named `verdict`, `passed`, `faulted`, `is_faulted`,
`state`, `transport_state`, `render_identical`, `operation_survived`, `restarted` or `expected`.
Emit one `wp12-r53-observation-v1` JSON object per plan case, in plan order, as gzip JSONL. Use a
fresh device per case.

## Fixtures

Every case reports `fixture_metadata_sha256`: SHA-256 of the raw primary SB (512 B), mirror SB
(512 B), and slots A0, A1, B0, B1 (65,536 B each), read back from the device before mount.

- `RENDER-*` and `respool_v3_003` use `respool_draft8/oracle.py`: `media(H, entries)` with the
  `RENDER_FIXTURES` entries in `fixtures.py`, or `media(10, [(10, 0, 2*CF)])`.
- `promote_fresh_alloc_full` uses `promote_draft8/fixture.py` `scenario_initial("fresh_alloc_full")`.
- For render fixtures, every chunk referenced by a live Side-B entry holds `fixtures.chunk_audio(c)`
  over the whole chunk. `fixtures.frame_bytes` is the per-frame definition.

## Render cases

1. `tape_mount(B)`.
2. **pre:** `tape_seek(0)`, then `tape_set_rate(65536)`. Then repeat
   `tape_service` until `more_work == false` followed by `tape_render(4096)`, until a render
   returns fewer than 4096 frames. Then `tape_set_rate(0)`.
3. Call `tape_respool(64)` until `more_work == false`.
4. **post_same_session:** repeat step 2 on the same instance.
5. `tape_unmount`, then a fresh `tape_mount(B)` from durable bytes.
6. **post_remount:** repeat step 2.

Record for each phase: `seek`, `set_rate`, and every render as `{requested, rendered, result,
block_events}`. Also record `pcm_bytes` and `pcm_sha256` over the concatenated little-endian output,
plus `tell` from `tape_tell` and `at_end` from `tape_status` after the final render, and `stop`.
Record `respool` as `[{fn, block_budget, result, more_work}]`, plus `unmount`, `remount`, and
`post_b_slots` (raw B0/B1 hex read after the respool loop).

## Fault cases

Call `tape_mount(mount_side)`, then call the long operation repeatedly with the plan's
`block_budget`. Record each call as `{fn, block_budget, result, more_work, events}`. An event is
`{op, lba, count, rc}`, or `{op, rc}` for a flush, for every real callback. The simulator returns
non-zero at exactly one callback:

- `first_of_call`: the first callback of kind `op` issued during call number `call` (0-based).
- `first_after_write`: the first flush after the write of `count` block(s) at `lba` (392 is B1's
  header block: the V5-001 pass-1 header flush).

Stop calling the operation after the failing call. Then record
`device_sha256_at_fault` over the whole device image. Probe the 15 columns in
`fault_probe_order` on the same instance. The call lists are:

- `status_info_tell`: `tape_status`, `tape_get_info`, `tape_tell`.
- `dup`: a separate blank destination device, whose events go in `dst_block_events`.
- `feed`: supply real frames.
- `set_side`: `TAPE_SIDE_A`.
- Every other column: its single call, with any valid arguments.

Each cell is `{column, calls: [{fn, result}], block_events}`. Record
`device_sha256_before_unmount` immediately before the `unmount` probe.

Replay with `replay.py --adapter-kind product --adapter-source-sha SHA --product-commit SHA
--product-tree SHA`. A passing Product replay still needs independent disposition; it is not
self-acceptance.
