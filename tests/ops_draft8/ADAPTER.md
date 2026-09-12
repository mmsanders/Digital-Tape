# VT8-001 mechanical adapter contract

The adapter calls only the frozen **public API** and exposes public-call plus
block-device observations to verifier code. It is not a product API and may not expose
engine internals, private allocator/index state, or implementation-derived claims.

## Invocation and observation

`vt8_ops_probe CASE_ID INPUT.vo08 OUTPUT.vo08`

Exit 0 only when the scripted calls completed and final VO08 media was written.
Stdout must be one JSON object:

```json
{
  "format": "VT8-OPS-OBSERVATION-1",
  "adapter_kind": "product",
  "calls": [],
  "events": []
}
```

`adapter_kind` is exactly `product` for a real adapter or `synthetic` for the verifier
self-test. The runner supplies the immutable adapter source/build provenance; replay
checks that the observation identity agrees with the manifest.

Every public call appends one ordered `calls` object with `phase`, exact public
function name, symbolic `result`, and the result fields the script depends on. For
this tranche those include mounted side, `side_b_valid`, seek frame, record mode,
feed requested/accepted counts, and each service `block_budget`/`more_work` result.

Every block callback appends, in call order:

`{"phase":"...","op":"read|write|flush","lba":N,"count":N,"rc":0}`

Flush omits `lba/count`. The phase is set by the wrapper immediately before each
**public** call. The wrapper records every callback, including unexpected callbacks;
it must never filter observations to make a verdict pass. Callback batches are
range-checked with widened arithmetic. A nonzero callback return is evidence and
fails these conforming cases rather than being silently dropped.

The VO08 envelope is `"VO08"`, little-endian `block_count`, primary and mirror
512-byte superblocks, then A0/A1/B0/B1 65,536-byte slots. Sparse chunk contents may be
harness-owned; this tranche does not compare PCM bytes, but all audio writes are
traced and range checked.

## Script `VT8-001-RB-ALLSLOT`

1. fresh caller-owned instance/rings;
2. mount Side A, resume 0, `warm == NULL`; require `TAPE_OK`;
3. `tape_get_info`; require `TAPE_OK` and `side_b_valid == false`;
4. `tape_reset_side_b`; require `TAPE_OK`;
5. unmount; require `TAPE_OK`;
6. fresh instance, remount Side B from final media; require `TAPE_OK`.

No other mutator is permitted. At stage 0 reset moves no audio; its index commit must
be entries → flush → header → flush.

## Script `VT8-001-REC-ALLOCSEQ`

1. fresh instance/rings; mount Side B, resume 0, `warm == NULL`; require `TAPE_OK`;
2. seek to frame 128; require `TAPE_OK`;
3. arm `TAPE_REC_SPLICE`; require `TAPE_OK`;
4. feed exactly 128 deterministic stereo frames; require `TAPE_OK` and 128 accepted;
5. call `tape_service` with a positive fixed budget until `more_work == false`, with a
   finite harness guard; each result is recorded;
6. call `tape_commit` exactly once; require `TAPE_OK`;
7. unmount; require `TAPE_OK`;
8. fresh instance, remount Side B; require `TAPE_OK`.

The adapter may choose deterministic samples; no private allocator helper may force an
allocation. `tape_feed` performs no block I/O. Stage-0 `tape_arm` performs no block
I/O. Every service write must lie in the newly allocated chunk; a successful service
flush must follow the final chunk-data write before commit metadata begins. Commit is
metadata only and exactly entries → flush → header → flush.

## Permitted integration edits

Only mechanical include/header/library paths, symbol-equivalent build flags, and the
sparse `tape_dev` wrapper are permitted. Include the actual product public header.
Do not change fixtures, expected sequences, operation arguments, accepted results,
callback classification, ordering, ranges or oracle assertions to fit a product
build. Missing public operations/ABI are findings. Do not add allocate-only or
sequence-query APIs.
