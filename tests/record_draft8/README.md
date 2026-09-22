# WP-09 — independent DRAFT-8 record tranche

Verifier-owned package authored from the frozen DRAFT-8 contract without
inspection of product implementation. It is **pre-product coverage**, not full
WP-09 / WP-11 acceptance.

Normative DRAFT-8 SHA-256 values:

- TapeFS `3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb`
- Engine API `537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1`
- Acceptance `7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7`

Frozen geometry is the same 60-second / 21-chunk / 23,553-block medium used by
the other DRAFT-8 verifier packages.

## Structural record families

| ID | Script |
|---|---|
| `WP09-OW-MID` | seek 128, overwrite 64 frames |
| `WP09-OW-END` | seek 256, overwrite 64 frames (append) |
| `WP09-OD-MID` | seek 128, overdub 64 frames |
| `WP09-SP-T0` | seek 0, splice 64 frames |
| `WP09-SP-MID` | seek 128, splice 64 frames |
| `WP09-SP-END` | seek 256, splice 64 frames (append) |
| `WP09-SP-BOUNDARY` | splice 64 frames at an exact boundary between two existing runs |
| `WP09-SP-EMPTY-B` | splice 64 frames onto a valid empty Side B |
| `WP09-OW-MULTICHUNK` | overwrite `CHUNK_FRAMES + 64`, allocating exactly two fresh chunks |

The non-empty cases assert exact index shape, allocation range, feed/service
behavior, inactive-slot commit, sequence selection and strict
entries → flush → header → flush ordering. Ordinary stage-0 recording is also
checked for **no superblock write callbacks**, not merely unchanged final bytes.

## Zero-accepted commit matrix

DRAFT-8 acceptance requires all three modes at start, middle and end of a
non-empty timeline. The matrix is complete:

| Mode | start | middle | end |
|---|---|---|---|
| overwrite | `WP09-EMPTY-OW-START` | `WP09-EMPTY-COMMIT` | `WP09-EMPTY-OW-END` |
| overdub | `WP09-EMPTY-OD-START` | `WP09-EMPTY-OD` | `WP09-EMPTY-OD-END` |
| splice | `WP09-EMPTY-SP-START` | `WP09-EMPTY-SP` | `WP09-EMPTY-SP-END` |

Every row requires `TAPE_OK`, zero writes, zero flushes and byte-identical
media. After commit the script services playback and renders one existing frame,
so a no-op cannot pass merely by leaving plausible index bytes while losing the
usable tail.

## Refusal / state rows

| ID | Assertion |
|---|---|
| `WP09-ARMED-BUSY` | armed seek and set-rate independently return `TAPE_ERR_BUSY`; abort disarms |
| `WP09-RO-SIDE-A` | Side-A arm → `TAPE_ERR_READ_ONLY`, zero writes |
| `WP09-SEQ-EXHAUSTED` | sequence headroom refusal happens at arm, zero writes |
| `WP09-INDEX-FULL` | splice arm on 4096-entry live B → `TAPE_ERR_INDEX_FULL`, zero writes |
| `WP09-CART-FULL` | already-full cartridge: arm succeeds, feed accepts 0 and reports `TAPE_ERR_CARTRIDGE_FULL` with no I/O |
| `WP09-ABORT-DISARM` | abort writes nothing and a following unmount succeeds |
| `WP09-STAGE-REFUSE` | a **mountable §9.3.3 row-1** stage state plus exhausted sequence refuses before clearing stage |
| `WP09-STAGE-CLEAR` | a **mountable §9.3.3 row-1** stage state clears partner-first with both flushes before recording proceeds |

The stage fixtures deliberately match the frozen mount-time stage oracle; an
arbitrary `promote_stage=1` fixture is invalid test input because DRAFT-8 mount
must reject unmatched resume shapes.

## Saturation arithmetic

`selftest.py` includes seven independent reference vectors for the exact
Engine API §8 saturating-add formula. These vectors prove the verifier's
arithmetic oracle only. They are **not** product PCM evidence; real-engine
overdub bytes remain a later product/golden observation.

## Self-test

```sh
python3 tests/record_draft8/selftest.py
```

The self-test runs all conforming synthetic cases and targeted mutations for
wrong commit order, missing flushes, unauthorized superblock writes, feed I/O,
unfinished service, BUSY failures, abort-not-disarming, exact-boundary splice,
multi-chunk over/under-write, empty-commit writes/flushes/tail loss, and
stage-clear ordering.

A synthetic green run is package evidence only. It is not product acceptance
and not a listened golden.

See `COVERAGE.md` for the assertion/exclusion matrix and `ADAPTER.md` for the
product-adapter contract. Next owner after independent review is Software for a
mechanical public-API adapter and raw product observations, followed by
Verification disposition. Do not merge this branch onto verification `main`
as acceptance merely because the synthetic package is green.
