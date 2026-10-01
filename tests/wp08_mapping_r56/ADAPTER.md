# WP-08 mapped-run rows: public-observation adapter contract

- Use public calls only, on a caller-owned device.
- Do not import this oracle, read private engine state, or emit verdicts. The oracle rejects `verdict`,
  `passed`, `expected`, `expected_pcm`, `outcome_ok`, `row_ok`, `timeline`, `physical`, `chunk` and `mapping`.
- Emit one `wp08-mapping-r56-observation-v1` object per `oracle.iter_cases()` entry, in order, as gzip JSONL.

## Fixture

- Build the device image **byte for byte** from `rows.image()`: 7,169 blocks, the C69 layout (5 chunks, 12 s).
  - `a_high_water` is 5.
  - A0 (sequence 1) and B0 (sequence 2) carry the same five physical runs in different timeline orders.
  - Every frame of every chunk holds the #118 coordinate-unique pattern.
- A fresh device per case.
- The oracle checks `image_sha256` (SHA-256 of the device image before mount) and `block_count`.

## Calls (every case)

Each call is recorded as `{fn, <arguments>, result, <outputs>, events}`. `events` lists **every** block-device callback made during that call, unfiltered:

- a read or write as `{op, lba, count, rc}`;
- a flush as `{op: "flush", rc}`.

1. `tape_mount(side, 0, NULL)`, recorded as `{fn: "tape_mount", side: "A"|"B", resume_frame: 0, warm: null, result}`.
2. `tape_seek(seek)`, recorded as `{fn: "tape_seek", frame, result}`.
3. `tape_set_rate(rate)`, recorded as `{fn: "tape_set_rate", rate, result}`.
4. `tape_service(64)` until `more_work == false`. Record each call as `{fn: "tape_service", block_budget: 64, result, more_work}`.
5. `tape_render(requested)`, recorded as `{fn: "tape_render", requested, result, rendered, pcm_hex}`. `pcm_hex` is the rendered little-endian stereo s16 frames only.
6. `tape_tell`, recorded as `{fn: "tape_tell", result, frame}`.
7. `tape_status`, recorded as `{fn: "tape_status", result, at_start, at_end}`.

The rows differ in the arguments and in how often steps 4–7 repeat:

| | Row 1 (`seek_boundary`) | Row 2 (`reverse_end`) |
|---|---|---|
| `seek` | The case's `seek` | `total_frames` (559), which clamps to `max_pos` |
| `rate` | The case's `rate`, ±65,536 | −65,536 |
| `requested` | 4 | 32 |
| Steps 4–7 | Once | Repeated until a render returns fewer than 32 frames |

Top-level fields:

| Field | Row 1 | Row 2 |
|---|---|---|
| `schema`, `index`, `row`, `kind`, `side`, `image_sha256`, `block_count`, `calls` | ✓ | ✓ |
| `crossing`, `seek`, `rate` | ✓ | — |

## Replay

```
replay.py EVIDENCE.jsonl.gz --manifest M.json --adapter-kind product --adapter-source-sha SHA \
  --product-commit SHA --product-tree SHA
```

A passing replay still needs independent disposition.
