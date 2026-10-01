# #130 rows: public-observation adapter contract

- Use public calls only, on caller-owned devices.
- Do not import this oracle, read private engine state, or emit verdicts. The oracle rejects `verdict`,
  `passed`, `expected`, `expected_pcm`, `outcome_ok`, `row_ok`, `floor_ok`, `commit_count` and `saturated`.
- Emit one `wp09-gaps-r56-observation-v1` object per `oracle.iter_cases()` entry, in order, as gzip JSONL.
- Every object carries `schema`, `index`, `row`, `kind` and the case's identity field: `position` or `fixture`.

## Row 1: full-scale overdub (`kind` `overdub_saturation`), 3 cases

**Fixture.** Build `rows.overdub_image()` byte for byte, on a writable device.
- It uses the C69 layout and `a_high_water` 2.
- A0 is an empty Side-A index.
- B0 is `{2, 0, 48}`, whose 48 frames are `rows.base_frame(p)`.

Emit `image_sha256`, the SHA-256 of the device image before the first call.

**Calls.** `at = rows.POSITIONS[position]`. Record every call as `{fn, <arguments>, result, <outputs>}`:

1. `tape_mount(B, 0, NULL)`, recorded as `{fn: "tape_mount", side: "B", resume_frame: 0, warm: null}`.
2. `tape_seek(at)`, recorded as `{fn: "tape_seek", frame}`.
3. `tape_arm(TAPE_REC_OVERDUB)`, recorded as `{fn: "tape_arm", mode: "TAPE_REC_OVERDUB"}`.
4. `tape_feed(rows.input_frames(at), 16)`, recorded as `{fn: "tape_feed", frames: 16, pcm_hex, accepted}`. `pcm_hex` is the little-endian stereo s16 input you passed.
5. `tape_service(64)` until `more_work == false`. Record each call as `{fn: "tape_service", block_budget: 64, more_work}`.
6. `tape_commit`, then `tape_unmount`.
7. `tape_mount(B, 0, NULL)` again on the same device, then `tape_seek(0)` and `tape_set_rate(65536)`.
8. Repeat until a render returns fewer than 32 frames:
   - `tape_service(64)` until `more_work == false`;
   - `tape_render(32)`, recorded as `{fn: "tape_render", requested: 32, rendered, pcm_hex}`.

The oracle concatenates the renders. They must equal `rows.expected_timeline(at)` exactly. That is engine-api §8's clamp, and §11's "overdub at end: append; input passes through unchanged".

## Row 2: V-R55-01 trace floor (`kind` `respool_floor`), 5 cases

For each fixture, emit `wp10_final_record`: **the unchanged `wp10_final_r54` row-3 observation** for that fixture. It is the object your accepted `wp10_final_r54` binding produces, `schema` and `index` included.

No new driver is needed: wrap the existing binding's row-3 output. The oracle then does two things:

1. It reruns the pinned #118 row-3 check.
2. It requires the clean trace to meet the floor below.

**The floor, per commit** (tapefs §8). Commits are segmented at each B header write.

| Step | Requirement |
|---|---|
| 1 | Chunk data covering at least ⌈4T/512⌉ blocks |
| 2 | A flush |
| 3 | Entry block 1 of the inactive slot |
| 4 | A flush |
| 5 | Exactly one header block of that slot |
| 6 | A flush |

**Commit count** (tapefs §9.4):

| Fixture | Commits allowed |
|---|---|
| RS-TWOPASS, RS-FRAGMENTED, RS-CHUNK-CROSSING | 2 |
| RS-ONE-COMMIT | 1 |
| RS-REFERENCES-A | 1 or 2 |

## Replay

```
replay.py EVIDENCE.jsonl.gz --manifest M.json --adapter-kind product --adapter-source-sha SHA \
  --product-commit SHA --product-tree SHA
```

A passing replay still needs independent disposition.
