# WP-06 R44 sequential product binding

Software-owned binding of the imported R44 verifier package
`tests/sequential_wp06_r44`.

- Tree `21d4507149d6b565242df2120148b95eadcadd2f`.
- Verification PR #91 head `db2a56901d44defa753d8a715c639be232838215`.
- 38 cases; plan `0a6100ce…6ba0`.

Nothing here edits the verifier tree or decides a verdict. The package's own
`runner.py` and `oracle.check` decide every case.

`wp06_adapter.c` includes only `engine/include`. It builds each case on a fresh
sparse in-memory block device and runs it on a fresh `tape_t`. It records:

- every `tape_*` result;
- the public `tape_get_info` fields;
- every `dev_read`/`dev_write`/`dev_flush` callback in order, including
  injected failures;
- the six raw regions at each named snapshot (superblocks, and the full
  128-block A0/A1/B0/B1 slots), read outside the engine.

It reports no private phase, candidate, selected slot or `free_next`.

## Run

    make -C engine clean all
    make -C tests/sequential_wp06_adapter clean all
    python3 tests/sequential_wp06_adapter/run_product.py --evidence <fresh dir> \
        --retained tests/sequential_wp06_adapter/evidence/p1-r46-product
    python3 tests/sequential_wp06_adapter/run_product.py \
        --replay tests/sequential_wp06_adapter/evidence/p1-r46-product --out <fresh dir>
    python3 tests/sequential_wp06_adapter/diagnostic_findings.py <dir>/observations.jsonl

`run_product.py` first checks:

- the verifier tree at HEAD;
- the import commit `1ae9297`, whose parent is the declared base `2890ea1e`;
- the issued engine tree `054d27ab`.

It then runs the adapter and writes the unabridged `observations.jsonl`, a
deterministic gzip, `build-identity.json` (sources, build command and
per-case fixture SHA-256), `commit-census.json` and `SHA256SUMS`. Finally it
calls `runner.py`, which writes the non-overwriting manifest bound to the
Product commit/tree and the adapter source SHA-256.

With `--retained`, the fresh JSONL must be byte-identical to the committed
evidence. `--replay` works offline: it checks the committed hashes and replays
the retained JSONL through `runner.py`, with no adapter run.

## Retained evidence

`evidence/p1-r46-product/` holds the gzip (under 1 MiB), so no release asset is
needed. `SHA256SUMS` carries the hash of the decompressed 40 MB JSONL. There is
no committed manifest, because a manifest names the commit that contains it.
CI writes one per run against the head it checked out.

## Binding choices for Verification to audit

**B1 — Base cartridge.** Degraded and refusal fixtures start from one real
cartridge built through the public API:

1. format (nominal 60 s, 21 chunks, fixed UUID);
2. mount B;
3. record 100 frames;
4. commit;
5. promote to completion;
6. unmount.

**B2 — Degradations.** Only named fields are rewritten, and CRCs are
recomputed.

| Case | Rewrite |
|---|---|
| Repair, invalid | Partner superblock zeroed |
| Repair, stale | Partner `sb_generation − 1` |
| Degraded-invalid | B0 and B1 headers zeroed |
| Degraded-divergent | Live B header copied into the other slot at the same sequence, with `frame_count`/`total_frames` halved |
| Refusal, bad A | A0/A1 made equal-sequence divergent the same way |
| Refusal, bad stage | Primary set to `promote_stage = 1`, staging chunk 5 |

Both refusals also make the mirror stale.

**B3 — Repair failure injection.** The first partner write or flush inside
`tape_mount` returns rc 5. The retry uses a new instance on the same device
with healthy callbacks, after unmounting the first.

**B4 — Round trips.** Each round trip formats a fresh device sized for its
own `nominal_length_s`: 60 s (21 chunks) by default, with two exceptions:

- entry-block-boundary uses 128 s (44 chunks);
- max-entries uses 12,175 s (4,097 chunks).

Records append with `TAPE_REC_OVERWRITE` at the timeline end, and every
recording is serviced until owed frames clear. Entry-block-boundary makes 42
preparatory one-frame commits, and max-entries makes 4,095. Each is followed by
the measured recording.

- `TAPE_REC_SPLICE` was not used: engine-api reserves two entries for it, so
  the 4,096th entry would be refused (`TAPE_ERR_INDEX_FULL`).
- The measured `tape_commit` is step `commit`. Earlier commits are in step
  `mount1`.

**B5 — Degraded operations.**

- `dup_source` loops `tape_dup` with budget 65,536 to a blank destination
  device.
- The `reset_b` flow is: `after_reset` snapshot; `remount` (unmount, new
  instance, mount A, info); `after_remount` snapshot; `switch`
  (`tape_set_side(B)`); `exercise` info.

## Findings for PM/Verification

The canonical replay is **FAIL, 4 of 38**. The adapter binds no engine change;
engine tree `054d27ab` is unchanged.

`diagnostic_findings.py` is non-canonical and feeds nothing to `runner.py`. It
shows that these two findings account for all four failures: with both
translations applied, the oracle passes all 38.

- **F1 — `tape_reset_b` is not a public function.**
  - Cases: `degraded-invalid-reset_b`, `degraded-divergent-reset_b`.
  - The oracle maps op `reset_b` to `tape_reset_b`. engine-api and
    acceptance WP-06f name `tape_reset_side_b`, and that is what the adapter
    calls and records.
  - The adapter does not relabel it.
- **F2 — The oracle counts write callbacks as blocks.**
  - Cases: `roundtrip-entry-block-boundary`, `roundtrip-max-entries`.
  - tapefs §8 and engine-api invariant 24 bound `tape_commit` in **blocks**
    (at most 97). The device contract passes a block `count` per callback.
  - The engine writes the entry array with one multi-block callback, then
    block 0: 3 and 97 blocks in 2 callbacks each (`commit-census.json`). The
    oracle requires 3 and 97 *events*.
  - Splitting the engine's write would satisfy the count without changing a
    block on media, so it is not bound here. Remount confirms the state: 43/43
    and 4,096/4,096 entries and frames.

## Boundary

The following stay outside this tranche: full WP-06/WP-10, card atomicity, the
WP-11 golden/listening check, and hardware. A Software run is evidence, not
acceptance.
