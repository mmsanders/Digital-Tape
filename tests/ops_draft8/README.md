# VT8-001 — first operation-observation tranche

This verifier-owned package closes the smallest useful slice of `VT8-001` left by the DRAFT-8 mount tranche. It is authored from the frozen DRAFT-8 contract and **does not inspect or import product implementation**.

Frozen hashes:

- TapeFS `3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb`
- Engine API `537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1`
- Acceptance `7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7`

## Covered IDs

### `VT8-001-RB-ALLSLOT`

Public operation: mount Side A on a degraded-B cartridge, then `tape_reset_side_b`.

The fixture deliberately combines:

- live A at sequence 10;
- a structurally valid A-partner header at sequence **900** that is semantically invalid for A;
- B0/B1 both semantically valid at equal sequence 500, so B is degraded.

Required observation: recovery writes B0 at sequence **901**, copies the live A entries with `side=1`, moves/writes **no chunk data**, leaves the stage-0 superblock byte-identical, and produces a remount-selectable B. This proves that reset uses TapeFS §5.5's maximum over **all structurally valid slots**, not a live-side or semantically-valid maximum.

### `VT8-001-REC-ALLOCSEQ`

Public operations: mount Side B, seek to the end, `tape_arm(TAPE_REC_SPLICE)`, feed 128 stereo frames, service until no work remains, `tape_commit`, unmount/remount.

The fixture has `a_high_water == free_next == 3`, live B sequence 20, and a structurally valid but A-semantically-invalid partner at sequence **700**.

Required observation: service audio writes lie wholly in newly allocated chunk **3** (never below `a_high_water`); the committed B1 index is `[(0,0,128),(3,0,128)]` at sequence **701**; stage-0 ordinary recording leaves the superblock / `sb_generation` unchanged; remount derives `free_next == 4`; all structurally valid slot sequences remain unique.

## Deliberate exclusions

This tranche does **not** claim full WP-07 or WP-10. It does not exercise non-NULL warm start, playback/state transitions, overwrite/overdub, stage clearing, reset timing, 10,000 edit sequences, promote, re-spool, duplicate, format, long-operation continuations, crash injection, FAULTED behavior, or golden PCM. Those exclusions remain exactly the boundary stated by the previous mount tranche.

The recording case observes allocation from callback LBAs and final committed media; there is no allocate-only API and none is requested.

## Local oracle self-test

`python3 selftest.py`

The self-test is **not an engine run**. It validates that the independent oracle accepts two conforming synthetic observations and rejects six targeted mutations: live-only sequence bases for reset/record, reset chunk movement, an allocation below `H/free_next`, an ordinary-recording `sb_generation` increment, and an overlapping committed index.

## Product run

After PM/Software mechanically supplies the adapter described in `ADAPTER.md`:

`python3 runner.py --adapter /path/to/vt8_ops_probe --log evidence/product.jsonl`

The runner emits provenance, adapter SHA-256, immutable fixture hashes, raw callback observations and PASS/FAIL per case. A missing adapter is an error, never a skip.
