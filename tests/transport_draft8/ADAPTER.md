# Mechanical adapter contract

`wp_transport_probe CASE_ID INPUT.vo08 OUTPUT.vo08`

Stdout is one JSON object:

```json
{"format":"WP-TRANSPORT-OBSERVATION-1","adapter_kind":"product","calls":[],"events":[]}
```

The adapter is mechanical: it calls only frozen public APIs and records the
arguments/results needed by the independent oracle. It must not inspect private
engine state, reinterpret the expected result, or substitute an easier fixture.

The supplied `INPUT.vo08` must be the exact case fixture. The synthetic adapter
decodes it and exits non-zero if it does not match.

## Block observations

Every device callback is reported in order:

`{"phase":"...","op":"read|write|flush","lba":N,"count":N,"rc":0}`

Transport/warm cases may read media during mount/service, but they must never
write it. `tape_render` must report `events_from_call=0`; no raw callback may
carry a render phase.

## set_side cases

### `SS-PLAYING-A-TO-B`

This is the required WP-08 Playing transition.

1. cold-mount Side A;
2. set +1.0x;
3. service to completion;
4. render exactly 256 Side-A frames, establishing the end state;
5. observe `at_end=true`;
6. call `tape_set_side(B)` while still Playing;
7. require position 0, both endpoint flags false, `warm_start_used=false`,
   `total_frames=64`, `entry_count=1`, `entries_free=4095`;
8. **before any Side-B service**, `tape_render(1)` must return
   `TAPE_ERR_UNDERRUN`, `rendered=0`, zero callbacks;
9. service Side B to completion;
10. render one frame, then `tape_tell` must report frame 1.

The final tell is the public proof that the retained rate is exactly +1.0x; a
reset-to-zero or altered nonzero rate does not pass.

### `SS-IDLE-A-TO-B`

1. cold-mount A and seek to frame 10 while stopped;
2. set_side(B);
3. assert the same position/flags/info transition;
4. only **after** the switch, set +1.0x;
5. before service, render(1) → `TAPE_ERR_UNDERRUN`, rendered 0;
6. service, render one, tell → frame 1.

This is the separate idle half required by WP-08.

### `SS-SAME-A`

Mount A, seek 10, set_side(A). Because the frozen §5 transition applies on a
successful call, position must reset to 0 and Side-A metadata remain selected.

### Degraded-B

`SS-DEGRADED-B` mounts Side A on a fixture whose B0/B1 are both structurally
valid at the same sequence with different entry arrays. Observe
`side_b_valid=false`, seek to 10, then:

- `tape_set_side(B)` → `TAPE_ERR_NO_VALID_INDEX`;
- position remains 10;
- Side-A metadata remains selected;
- zero writes.

`SS-DEGRADED-SAME-A` separately proves the §10 ᴮ exception:
`tape_set_side(A)` remains allowed while degraded-B.

### Armed refusal

`SS-ARMED-BUSY` mounts B, seeks to 10, arms overwrite, attempts set_side(A)
and requires `TAPE_ERR_BUSY`. Position and B metadata must remain unchanged;
abort and unmount must then succeed.

## Warm-start cases

The adapter must report the **actual descriptor arguments supplied to
`tape_mount`**. Merely reporting `warm_start_used=false` is insufficient.

For every non-NULL descriptor record:

- `warm_data_present`;
- `warm_data_bytes`;
- `warm_valid_frames`;
- `warm_start_frame`;
- `warm_uuid_hex`;
- `warm_side`;
- mount `resume_frame`;
- resulting `warm_start_used`.

For `WARM-NULL`, report `warm_present=false` and do not expose descriptor
fields that could only have been read by dereferencing it.

The fixtures are ordered so that each later-negative case satisfies every
earlier predicate:

| Case | Unique intended condition |
|---|---|
| `WARM-NULL` | descriptor pointer is NULL |
| `WARM-DATA-NULL` | descriptor valid enough to reach the data-pointer check, but `data==NULL` |
| `WARM-ZERO-FRAMES` | non-NULL data, `valid_frames==0` |
| `WARM-SHORT-BUF` | 16 frames but `data_bytes=63 < 16×4` |
| `WARM-PAST-END` | `start=250, frames=16` on a 256-frame A timeline |
| `WARM-U32-OVERFLOW` | `start=0xFFFFFFF8, frames=16`; checked 64-bit end must exceed timeline instead of wrapping |
| `WARM-RESUME-OUT` | valid range `[32,48)`, resume=48 |
| `WARM-UUID` | all earlier predicates valid; UUID alone differs |
| `WARM-SIDE` | all earlier predicates including UUID valid; side alone is B instead of mounted A |
| `WARM-VALID-METADATA` | every metadata predicate valid; must set `warm_start_used=true` |

All negative rows cold-mount normally and require `warm_start_used=false` from
both mount observation and `tape_get_info`. The positive row proves the engine
does not simply ignore every warm descriptor.

The positive row establishes **metadata acceptance only**. It does not claim
that the retained samples are bit-identical to listened PCM; that remains a
WP-11 golden gate.

## Permitted integration edits

Software may change only mechanical include/library paths and implement the
public-API wrapper/callback logging needed for these observations. Do not alter
fixtures, descriptor values, call ordering, expected return codes, or oracle
assertions to fit the product build.
