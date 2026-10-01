# WP-08 mapped-run rows: coverage

| Row | Ledger | Cases | Controls (exact kill sets, derived from the mapping) |
|---|---|---|---|
| `WP08.seek_boundary.mapped_runs` | WP08-L03 | 60 = 2 sides × 5 crossings × {−1, 0, +1} × {+1.0×, −1.0×} | `ignore_start_frame` 60, `chunk_crossing_wraps` 19, `sort_entries_by_physical` 60, `side_a_plays_b_index` 30, `reverse_crossing_stale` 4, `render_reads_device` 60 |
| `WP08.reverse_end.mapped_timeline` | WP08-L10 | 2 = one per side | each of the six controls kills both cases, except `side_a_plays_b_index` (Side A only) |

The totals across both rows are 62, 21, 62, 31, 6 and 62. The case-set SHA-256 is `9eca914a4f2ed87db31bb5cd1212b89dec52731e37cdd76e1fb8aa2af8424e30`.

## The fixture

`rows.py` defines one C69-layout cartridge with five physical runs. Side A plays them in the order `E2 E0 E4 E3 E1`; Side B plays them in the order `E0 E1 E2 E3 E4`.

| Run | Entry | What it exercises |
|---|---|---|
| E0 | `{3, 1000, 300}` | A non-zero, block-unaligned start that spans four blocks |
| E1 | `{3, 100, 50}` | The same chunk as E0 at a lower offset: the splice-trim shape |
| E2 | `{1, 131000, 200}` | A run that crosses the chunk 1 → 2 boundary (tapefs §5.1) |
| E3 | `{4, 127, 3}` | A run that starts on a block's last frame |
| E4 | `{0, 5, 6}` | The lowest chunk, at an odd offset |

- **Crossings.** Each side has four run boundaries plus the intra-run chunk crossing:
  - Side B: 300, 350, **422**, 550 and 553.
  - Side A: **72**, 200, 500, 506 and 509.
- **Validity.** `a_high_water` is 5, so both indices are §5.2-valid: they satisfy the Side-A bound, and the intervals are disjoint.
- **Audio.** It is coordinate-unique, so any wrong mapping is visible as a specific wrong frame. The oracle names that frame.

## Row 1: V4-010 on mapped runs

For every crossing `b` and `N ∈ {b−1, b, b+1}`, the adapter runs `seek(N)`, sets the rate to ±1.0×, services to completion, then calls `render(4)`. The oracle requires:

- the four frames `N, N±1, N±2, N±3` of the side's timeline, derived from the audio pattern and tapefs §5.1;
- `rendered` 4, `TAPE_OK`, tell `N±4` and both flags false;
- no callbacks outside mount and service, and reads only, in range;
- every service call within its `block_budget`, ending with `more_work == false`.

## Row 2: V5-005 over the whole mapped timeline

The adapter runs `seek(559)`, which clamps to `max_pos`, sets the rate to −1.0×, then repeats service-to-completion and `render(32)`. The oracle requires:

- the exact reverse of the 559-frame timeline;
- 17 full renders and an 18th of 15 frames;
- tell after each render;
- `at_start` true exactly once frame 0 has been emitted (§6.2), and `at_end` never set.

## What is pinned, and what is not

- **Pinned, because the spec forces it:**
  - §6.3 fetch-emit-advance and the reverse snap;
  - §6.2 at ±1.0× from grid positions, where §8 interpolation is the identity;
  - §6 "seek and set_rate clear both flags";
  - render with zero callbacks;
  - service at most `block_budget` blocks per call, with no writes or flushes during playback.
- **Not pinned (#115):** which blocks service reads, their order, the per-call split within the budget, or the number of service calls.

## Why these rows are genuine gaps

Each mapping mutant above passes every accepted WP-08 fixture:

- **V95 and V122 cannot see `ignore_start_frame`, `sort_entries_by_physical` or `chunk_crossing_wraps`.** Their runs sit at `start_frame` 0 in their own chunks, ascending, at most 7 frames long, so all three mutations change nothing.
- **Side-A boundary seeks are never exercised.** The R15 side families render Side A only forward from 0.
- **playback_draft8 is not accepted evidence.** It has non-zero starts, but its only Product bundle was never dispositioned.

The `side_a_plays_b_index` control is also caught by the R15 side families. It is here so that the Side-A leg's controls are causal.

## Excluded

- Listened goldens (WP-11, Michael-held).
- Fractional-rate interpolation across mapped boundaries. V95 already crosses physically discontiguous runs at fractional rates, and the mapping defect classes above are rate-independent.
- Rows already covered (see `LEDGER.md`).
- Product bindings, hardware and release.
