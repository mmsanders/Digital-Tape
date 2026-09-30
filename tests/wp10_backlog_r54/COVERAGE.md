# WP-10 backlog rows (R54): coverage

| Row | Criterion | Injection points (exhaustive) | Controls |
|---|---|---|---|
| 1 | `WP10.session.load.mount_repair_write`: tapefs §4.1 phase 4 | 4 shapes × 2 modes × (513 + 1) = **4,112** | `repair_rewrites_candidate`, `repair_bumps_generation` (both also outcome-only) |
| 2 | `WP10.dup.rerun_completes`: acceptance "Duplicate", "the re-run path must be exercised" | blank 11,302 + healthy 13,358 + equal-divergent 13,358 + exhaustion-candidate 13,358 + exhaustion-equal-divergent 13,358 = **64,734** | `rerun_noop_when_incomplete` (also outcome-only), `rerun_skips_barrier` (trace-level; see below) |
| 3 | `WP10.dup.destination_shape.mounts_both_sides_high_label`: tapefs §9.5 step 4, V7-004 | 4 labelled sources × 2 destinations = **8** completions (not crash-bearing) | `label_not_copied`, `b0_written_side_a`, `high_water_floor` |

Rows 1 and 2 split exactly 50/50 by durability mode (2,056/2,056 and 32,367/32,367). The case-set
SHA-256 is `6808330224da3129371f482e1828eab36b801d7caa13652dfc69a99e7493aaf3`.

## Row 1

The four shapes are: primary-only, mirror-only, current primary with a stale generation-6 mirror,
and current mirror with a stale generation-6 primary. The injection covers the one partner write
(before, torn 1…511, after) and its flush, in both modes.

After every injection:

- the durable bytes are a permitted state;
- read-only and writable remounts both succeed, with the **same content** (UUID, frames, entries,
  `free_chunks`);
- the writable remount finishes the repair exactly, with the partner equal to the candidate;
- `sb_generation` stays at the candidate's and both index sequences are unchanged, so repair
  advanced neither counter.

A torn partner fails CRC, so the candidate still wins.

## Row 2

Every write and flush boundary of the §9.5 copy is interrupted, and `tape_dup` is then re-run on the
**same destination device**. The re-run's own §9.5 write order is derived from the crashed bytes
(item-5 classification, step-1 template or fallback). That planner reproduces the accepted R29-B
step-1 writes byte-for-byte on all seven R29-B shapes.

The re-run must:

- return `TAPE_OK` with `more_work == false`;
- address only chunk `[0, len_A)`;
- reach the exact completed copy, mounting on both sides.

Every §9.5 crash-table class is reached before a re-run: `BAD_MAGIC` blank, old cartridge unchanged,
`INCONSISTENT`, surviving copy, `INCOMPLETE`, fallback-zeroed `BAD_MAGIC`, and completed. The
self-test re-plans and re-runs from every possible durable image.

`rerun_skips_barrier` can only be caught through the trace. A re-run that omits step 1 still ends in
byte-identical completed media, because step 4 rewrites both superblocks. Only the §9.5 write order,
or a crash inside the re-run, exposes it. The oracle binds the re-run's trace for exactly that reason.

## Row 3

Sources have 0, 128, `CHUNK_FRAMES` and `CHUNK_FRAMES + 1` frames, each with a distinct non-empty
UTF-8 label, copied onto blank and reusable destinations. The raw result must have:

- `sb_generation` 1, `state` VALID and the fresh UUID;
- `a_high_water == ceil(frames / CHUNK_FRAMES)` (0, 1, 1, 2);
- a label byte-identical to the source's;
- A0 at `side` 0, sequence 1 and B0 at `side` 1, sequence 2, both with the source's `total_frames`.

The copy must mount on Side A **and** Side B, with the label in `tape_info` and the rendered audio
equal to the source's.

## Accounting

Only what tapefs forces is pinned: the §9.5 order, and one-block writes of one-block payloads. The
repair is one partner block and a flush (§4.1). Budget-per-call and write partitioning of multi-block
copies are not pinned (#115). Row 3 checks only final state.

## Backlog

Three rows remain, in `backlog-update.json`:

1. reset B / stage-clear one short
2. zero-needed reserved cells
3. post-crash re-spool render

Excluded: those rows, Product binding, WP-12/WP-12a, WP-11 and hardware. No complete WP-10 claim.
