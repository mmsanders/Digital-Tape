# VT8-001 mechanical adapter contract

The adapter exists only to call the frozen **public API** and expose block-device/media observations to verifier code. It is not a product API and may not expose engine internals.

## Invocation

`vt8_ops_probe CASE_ID INPUT.vo08 OUTPUT.vo08`

It must return 0 only when the scripted public calls completed and it wrote the final compact media envelope. Stdout is one JSON object containing `events`; stderr is diagnostic only.

The `VO08` envelope is defined by `oracle.Media`: `"VO08"`, little-endian `block_count`, primary and mirror 512-byte superblocks, then A0/A1/B0/B1 65,536-byte slots. Unmapped audio reads may return deterministic poison/zero; audio writes must be accepted into a sparse block map and traced. The output envelope contains final metadata. Audio contents themselves are not an oracle in this tranche.

## Harness-owned event trace

Every block callback emits, in call order:

`{"phase":"...","op":"read|write|flush","lba":N,"count":N,"rc":0}`

`phase` is set by the wrapper immediately before each **public** call; it is not reported by the engine. At minimum use `mount`, `reset_b`, `seek`, `arm`, `feed`, `service`, `commit`, `unmount`, `remount`. Flush may omit `lba/count`.

The wrapper must reject out-of-range callback batches with widened arithmetic and may record write-byte hashes for diagnosis, but the verifier derives allocation and sequence from callback LBAs plus final raw metadata, not an engine-provided allocation/sequence claim.

## Case scripts

### `VT8-001-RB-ALLSLOT`

1. fresh caller-owned instance/rings;
2. mount **Side A**, resume 0, `warm == NULL`;
3. require mount success and degraded-B observable via public info;
4. call `tape_reset_side_b` once;
5. unmount;
6. fresh instance, remount **Side B** from the resulting media to establish recovery is selectable.

No additional mutator is permitted.

### `VT8-001-REC-ALLOCSEQ`

1. fresh instance/rings; mount **Side B**, resume 0, `warm == NULL`;
2. seek to frame 128 (the end of the one-entry timeline);
3. arm `TAPE_REC_SPLICE`;
4. feed exactly 128 deterministic stereo frames and require all 128 accepted;
5. call `tape_service` with a positive fixed block budget until `more_work == false`; impose a finite harness guard and fail on nontermination;
6. call `tape_commit` exactly once and require `TAPE_OK`;
7. unmount;
8. fresh instance, remount Side B from the final media.

The adapter may choose the deterministic 128-frame sample values; this tranche does not compare PCM. It may not call private allocator/index helpers to force the result.

## Permitted integration edits

Only mechanical include/header/library paths, symbol-equivalent build flags, and the sparse `tape_dev` wrapper are permitted. The actual product `tape.h` must be included. Do **not** change a fixture, expected sequence, operation argument, accepted result, callback classification, or oracle rule to make a product build pass.

Do not add an allocate-only or sequence-query API. Do not read internal allocator counters, private index structures, or operation state. If the public operations cannot produce the required observation, return that as an integration finding.
