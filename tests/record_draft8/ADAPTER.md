# WP-09 mechanical adapter contract

The adapter calls only the frozen **public API** and exposes public-call plus
block-device observations. It is not a product API and must not expose engine
internals or private allocator state.

## Invocation

`wp09_rec_probe CASE_ID INPUT.vo08 OUTPUT.vo08`

Exit 0 only when the scripted calls completed and final VO08 media was written.
Stdout is one JSON object:

```json
{
  "format": "WP09-REC-OBSERVATION-1",
  "adapter_kind": "product",
  "calls": [],
  "events": []
}
```

`adapter_kind` is `product` or `synthetic`. Every public call appends one
ordered `calls` object with `phase`, `fn`, symbolic `result`, and the
fields the script depends on. These include, as applicable, `side`, `frame`,
`mode`, `requested`, `accepted`, `more_work`, `rate_q16_16` and
`rendered`.

For `tape_feed` and the one-frame tail `tape_render` probes, the adapter must
also report `events_from_call`: the exact number of block callbacks raised
inside that public call. Omitting the field is not equivalent to zero.

Every block callback appends, in order:

`{"phase":"...","op":"read|write|flush","lba":N,"count":N,"rc":0}`

Flush omits `lba/count`. The wrapper records **every** callback; it must never
filter observations to make a verdict pass. The `phase` is the public call
that caused the callback (for example `feed`, `service`, `commit`,
`arm`, `tail-service` or `tail-render`).

## Shared stage-0 fixture

60-second nominal tape. Derived `total_chunks = 21`. Medium is 23,553 blocks.
Live A0 sequence 10, structurally valid A1 at 700 with `side=1` (invalid for
A), live B0 `[(0,0,256)]` at sequence 20, B1 empty.
`a_high_water == free_next == 3`, `cartridge_sequence == 700`.

Most record cases mount Side B with `warm == NULL`. Case-specific fixtures for
empty-B, exact-boundary and stage-1 behavior are constructed independently in
the verifier and must be reproduced byte-for-byte by the adapter.

## Stage-1 fixture rule

The two stage tests do **not** use an arbitrary `promote_stage=1` cartridge.
They use a shape that DRAFT-8 mount is required to accept under TapeFS §4.2 and
§9.3.3 row 1:

- `promote_stage = 1`
- `promote_staging_chunk = S = 3`
- `a_high_water = 4` (`S + len`, with `len = 1`)
- live A and live B are both exactly `[(3,0,128)]`

`WP09-STAGE-REFUSE` additionally puts the structurally-valid all-slot
`cartridge_sequence` at `0xFFFFFFFD`; mount still succeeds because that high
sequence slot is not semantically valid for Side A. Arm must then refuse before
the stage-clearing write.

## Scripts

The basic happy-path record sequence is:

1. fresh instance; `tape_mount(B)`;
2. `tape_seek(CASE.seek)`;
3. `tape_arm(CASE.mode)`;
4. `tape_feed` exactly the scripted request;
5. `tape_service` repeatedly until `more_work == false`;
6. `tape_commit`;
7. unmount and remount B.

Covered happy-path variants include overwrite mid/end, overdub mid, splice at
t=0/mid/exact-run-boundary/end, splice into empty B, multi-chunk overwrite and
the successful stage-clear-then-record path.

### Empty-commit matrix

For each mode (overwrite, overdub, splice) at start, middle and end of the
non-empty 256-frame fixture:

1. mount B, seek, arm;
2. call `tape_commit` with zero accepted frames and require `TAPE_OK`;
3. verify the adapter observed zero writes and zero flushes and the final VO08
   bytes equal the input;
4. seek an existing frame (`min(original_seek, 255)`);
5. set rate to +1.0×;
6. service until complete;
7. render exactly one frame and require `rendered == 1` with
   `events_from_call == 0`;
8. stop, unmount and remount.

The render probe establishes that the pre-existing timeline remains usable
after the no-op; it is not a golden-PCM comparison.

### Armed BUSY / refusal scripts

- `WP09-ARMED-BUSY`: after arm, exactly one `tape_seek(0)` and one
  `tape_set_rate(+1.0×)` both return `TAPE_ERR_BUSY`; `tape_abort` then
  allows a successful unmount.
- `WP09-RO-SIDE-A`: mount A; arm overwrite → `TAPE_ERR_READ_ONLY`; unmount.
- `WP09-SEQ-EXHAUSTED`, `WP09-INDEX-FULL`, `WP09-STAGE-REFUSE`: mount,
  seek 0, arm must return the named refusal; zero writes/flushes; unmount.
- `WP09-CART-FULL`: arm succeeds; `tape_feed(64)` returns
  `TAPE_ERR_CARTRIDGE_FULL` with `accepted==0`, explicit
  `events_from_call==0`, and no raw feed callbacks; abort and unmount.
- `WP09-ABORT-DISARM`: arm, abort `TAPE_OK`, then unmount `TAPE_OK`.
  The successful unmount is the observable proof that abort actually disarmed.

Modes use the frozen `TAPE_REC_OVERWRITE`, `TAPE_REC_OVERDUB` and
`TAPE_REC_SPLICE` values.

## Trace requirements

For every non-empty ordinary record, the verifier requires:

- feed request and accepted count exactly match the script;
- an explicit zero feed callback count and zero raw feed callbacks;
- service reaches `more_work == false`;
- service writes stay entirely inside the independently derived allocation;
- ordinary stage-0 paths issue no write intersecting either superblock;
- commit writes only the inactive B slot and the observable order is
  **entries → flush → one-block header → flush**, with exactly two commit
  flushes and no write after the final flush;
- unmount and remount succeed.

For stage clearing, the arm-phase block trace must be exactly the logical update
order required by TapeFS §4.6:
**partner write → flush → candidate write → flush**. The first recording write
must occur only after that sequence completes.

## Permitted integration edits

Software may change only mechanical include/header/library paths and add a sparse
`tape_dev` wrapper needed to expose the observations above. Do not change
fixtures, expected entries, arguments, accepted results, callback
classification, phase labeling or oracle assertions to fit a product build.

Product PCM/golden evidence is deliberately not encoded in this adapter yet.
That remains a separate later observation/listening gate rather than something
the mechanical adapter may synthesize.
