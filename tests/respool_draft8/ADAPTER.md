# WP-12 mechanical adapter contract

The adapter calls only frozen public APIs and records public-call results plus
ordered block-device callbacks. It must not inspect or expose private engine
state.

## Invocation

`wp12_respool_probe CASE_ID INPUT.vo08 OUTPUT.vo08`

Stdout is one JSON object:

```json
{"format":"WP12-RESPOOL-OBSERVATION-1","adapter_kind":"product","calls":[],"events":[]}
```

Each call record includes `phase`, `fn`, symbolic `result`,
`block_budget` when applicable, and `more_work`. Every block callback is
recorded in order:

`{"phase":"...","op":"read|write|flush","lba":N,"count":N,"rc":0}`

Flush omits `lba/count`. Do not filter writes or reorder callbacks to fit the
oracle.

## Semantic-call budget

This tranche is **not** WP-12a. Each respool semantic case uses exactly one
`tape_respool` call with:

`block_budget = 65535`

and requires terminal `more_work == false`.

The old synthetic script using two calls at budget 64 was invalid for a
two-pass fixture that copies two full chunks twice. Small-budget repeated
continuation is tested separately under WP-12a.

## Scripts

### `WP12-EMPTY`

The valid empty-B fixture deliberately contains a structurally valid slot at
`sequence=0xFFFFFFFF`. This proves a zero-consumption branch does not consult
sequence headroom.

1. mount Side B;
2. `tape_promote(...,65535,...)` → `TAPE_ERR_INVALID_ARG`,
   `more_work=false`, zero writes/flushes;
3. `tape_respool(...,65535,...)` → `TAPE_OK`,
   `more_work=false`, zero writes/flushes;
4. unmount → `TAPE_OK`.

### `WP12-TWOPASS`

Fixture: H=10, live B0 is one entry `(10,0,2*CHUNK_FRAMES)`,
`free_next=12`, and the all-slot sequence base is 700.

One generously-budgeted respool call must produce two **separate §8 commits**:

**Pass 1**
- copy the complete two-chunk timeline to `[12,14)`;
- flush copied data;
- write inactive B1 entry array for `(12,0,2*CF)`;
- flush;
- write one-block B1 header at sequence 701;
- flush.

Only at that B1 header write does the live Side-B set become `[12,14)`.

**Pass 2**
- now, and only now, copy the complete timeline to `[10,12)`;
- flush copied data;
- write inactive B0 entry array for `(10,0,2*CF)`;
- flush;
- write one-block B0 header at sequence 702;
- flush.

Final media must retain B1/701 as the superseded pass-1 generation and B0/702
as the live final generation.

The adapter must report the actual block counts. The two-chunk timeline occupies
2048 blocks, so a one-block placeholder write is not a conforming observation.

### `WP12-DECLINE`

H=10. Live B has ten one-frame entries occupying every chunk 11..20, making
timeline `len=1`. Chunk 10 is the only qualifying pass-1 destination.

Pass 1 compacts to one entry `(10,0,10)` at B1/701. Because the resulting
layout starts at H, no strictly-lower qualifying start exists; there is no pass
2.

### Refusals / headroom

- `WP12-FULL`: mount B; no qualifying pass-1 destination →
  `TAPE_ERR_CARTRIDGE_FULL`, terminal, zero writes/flushes.
- `WP12-DEGRADED`: mount **Side A** on equal-sequence divergent B slots;
  mount succeeds in degraded-B; respool → `TAPE_ERR_NO_VALID_INDEX`,
  terminal, zero writes/flushes. Do **not** request a Side-B mount—the mount
  itself must refuse that fixture.
- `WP12-SEQ-EXHAUSTED`: non-empty fixture with
  `cartridge_sequence=0xFFFFFFFD`; respool →
  `TAPE_ERR_SEQUENCE_EXHAUSTED`, terminal, zero writes/flushes.
- `WP12-ONE-COMMIT`: V3-003 geometry with sequence base
  `0xFFFFFFFC`; pass 1 commits B1 at `0xFFFFFFFD`; optional pass 2 is
  skipped even though the lower destination would otherwise exist.

### `WP12-STAGE-CLEAR`

The fixture is a mountable TapeFS §9.3.3 row-1 state:

- `promote_stage=1`;
- `promote_staging_chunk=S=3`;
- `a_high_water=4`;
- live A and B are both exactly `(3,0,128)`.

After all respool preconditions pass and before its first copy/index write,
stage clearing must be:

**partner superblock write → flush → candidate superblock write → flush**

with `sb_generation+1`, stage/staging cleared, and H unchanged. Only then may
re-spool copy to chunk 4 and commit B1/701.

## Live-set safety oracle

For every chunk-region write, Verification independently maintains the live A
and B chunk sets from the fixture and from observed B header commit points.

A chunk write fails the oracle if it:

- intersects the current live set of either side;
- falls below `a_high_water`;
- lies outside the case's independently expected pass destination; or
- occurs after the final expected pass.

For V3-003, this is what makes a write to `[10,12)` **before** B1/701 commits
a hard failure even if the final media later looks correct.

Ordinary stage-0 re-spool also fails on any write intersecting either
superblock; final-byte identity alone is insufficient.

## Permitted integration edits

Software may make only mechanical include/header/library changes and implement
the sparse device wrapper/callback logging needed to expose these observations.
Do not change fixtures, destinations, budget, call order, callback ordering,
expected slots/sequences, or oracle assertions to fit a product build.

Bit-exact PCM comparison is intentionally a later product/golden gate and must
not be synthesized by the mechanical adapter.
