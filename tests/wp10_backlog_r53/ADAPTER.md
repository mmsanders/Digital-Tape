# WP-10 backlog rows 1–3: public-observation adapter contract

Use public calls only and a caller-owned fault-injecting device. Do not import this oracle, read
private engine state, or emit verdicts: the oracle rejects `verdict`, `passed`, `permitted`,
`expected`, `outcome_ok`, `selected_copy`, `row_ok`, `free_next_ok` and `frontier`. Emit one
`wp10-backlog-r53-observation-v1` object per `oracle.iter_cases()` entry, in order, as gzip JSONL.
Every object carries `schema`, `index`, `row` and `kind`.

## Row 1: fragmented dup onto a smaller destination

- **Destination:** build it from `dupfrag.destination(shape)` on the R29-B 4-chunk / 9 s geometry.
- **Source:** a separate 8-chunk / 21 s device. Side A is `dupfrag.SRC_ENTRIES` with
  `a_high_water` 8, and every referenced frame is `dupfrag.src_frame(chunk, frame)`. Side B is any
  valid index; the label is zero.
- **Call:** `tape_dup(src, dst, FRESH_DUP_UUID, epoch 0, 9, 65535)` until `more_work == false`.

Record everything from `wp10_closure_r53/ADAPTER.md` (trace, durable digest, `ro_A` / `rw_A` / `rw_B`
remounts, source hashes). Add `dst_chunk_lbas`: the sorted unique LBAs of every destination
read/write callback at or above `LBA_CHUNK_BASE`, excluding the mirror LBA, up to the crash. Record
out-of-range attempts too; a callback outside the device must fail and be recorded, not trap.

## Row 2: frontier after C69 and R29-B injections

Re-run the accepted campaign's case (`campaign` `C69` or `R29B`, same `case_index`) with its
existing, already-disposed Product binding. After the fresh remount (C69: Side B, or Side A for
`reset_b/degraded_equal`; R29-B: Side A), also call `tape_get_info`.

Emit:

- `campaign` and `case_index`;
- `post_snapshot_sha256`: SHA-256 of that campaign's compact post-crash snapshot object, as canonical
  compact sorted-key JSON;
- `remount: {side, result, total_chunks, free_chunks}`.

## Row 3: recording service writes

The fixture is `crash_core_draft8.fixture.record_fixture()`. Per `record_mode` and durability mode,
run the setup exactly as `oracle.check_row3` spells out:

1. mount B;
2. seek 0;
3. arm the mode;
4. feed 384 frames, fully accepted, with zero feed callbacks.

Then run `tape_service(1)` until `more_work == false`.

Record that clean run's `events` (every read/write/flush callback, with `lba`/`count`) and
`frames_owed_after`. Then, for each injection in `oracle.record_injections(n_flush)`, in order,
replay the same setup on a fresh device and cut power at that write (`landed` 0..512) or flush.
Record:

- `fired`, and `prefix_len` (1-based index of the injected callback in the clean trace);
- `meta_sha256`: primary SB ‖ A0 ‖ A1 ‖ B0 ‖ B1 slots (65,536 B each) ‖ mirror SB;
- `chunk0_sha256`;
- `remount`: a fresh writable Side-B mount with `{side, result, info: {free_chunks, total_frames,
  entry_count, side_b_valid, needs_repair}, pcm_sha256}`, where `pcm_sha256` covers the whole side
  rendered at 1.0×.

Replay with `replay.py --adapter-kind product --adapter-source-sha SHA --product-commit SHA
--product-tree SHA`. A passing replay still needs independent disposition.
