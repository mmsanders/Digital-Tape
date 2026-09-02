# Suite 3 invariant checklist (pre-DRAFT-3 scaffold)

Status: structure only. Normative field names and exact validators must be reconciled against DRAFT-3 before these become acceptance tests.

Generate arbitrary, parameterised cartridge geometries and arbitrary valid edit sequences. Do not assume a 90-minute cartridge.

After each successful operation, and after remount at every injected write/flush boundary, assert:

1. Timeline length equals the sum of every run's `frame_count`, using overflow-checked arithmetic.
2. Every run is structurally valid: nonzero length where required; start frame is within its first chunk; the number of occupied consecutive chunks is computed without truncation; and `first_chunk_id + occupied_chunks` neither wraps nor exceeds the chunk store.
3. Every chunk occupied by a Side A run is strictly below `a_high_water`; checking only `first_chunk_id` is insufficient.
4. Every Side B-owned allocation is at or above `a_high_water`. Side B may reference Side A runs below the mark, but must never write them.
5. No allocated space below the derived `free_next` is unreachable from the live index. Stale bytes in free chunks at or above `free_next` are permitted.
6. Re-spool preserves rendered PCM bit-exactly and commits only after writing to a region disjoint from every chunk referenced by the live pre-operation index.
7. Re-spool refuses with `TAPE_ERR_CARTRIDGE_FULL` when free space is less than the timeline length, without changing the mounted cartridge state.
8. Any edit sequence followed by re-spool renders identically to the same sequence without re-spool.
9. After a completed promote, `a_high_water` equals the promoted timeline's occupied chunk count and no allocated space is unreachable.
10. Each crash point in either promote phase remounts to one complete, valid generation permitted by DRAFT-3; Side A is never a mixture of generations.
11. Promote followed by reset B has the DRAFT-3-specified idempotent result.
12. Sequence and superblock-generation comparisons remain correct at their specified exhaustion boundary; do not infer modular wrap semantics unless DRAFT-3 explicitly permits them.

Required generated edge cases include empty timelines, one-frame runs, exact chunk boundaries, maximum-length runs, final-chunk partial runs, arithmetic maxima, fragmented B layouts, runs whose first chunk is valid but last chunk is out of range, and run ends immediately below/at/above `a_high_water`.

## Generator obligations

- Seed must be explicit and printed/reported with every failure so a generated edit sequence is exactly replayable.
- Geometry is input data: `total_chunks`, `nominal_length_s`, high-water mark, entry capacity, and sequence/generation proximity to exhaustion are varied independently within DRAFT-3-valid bounds.
- Generated operations must include reset, overwrite, overdub, splice, re-spool, promote, remount, and no-op/boundary operations once their DRAFT-3 state matrix is available.
- Invalid-media generation is a separate family from valid edit sequences. It must mutate one invariant at a time, repair CRCs where needed, and assert rejection before out-of-range I/O or media repair.
- Shrinking must preserve the failure: first remove operations, then entries/runs, then frames/chunks, then geometry, while retaining the same violated invariant.

## Oracle separation

The property oracle must not call engine helpers or reuse engine parsing/arithmetic. It independently decodes little-endian fields, checks CRCs, expands run coverage with overflow-checked arithmetic, and renders reference PCM when audio equivalence is asserted. This prevents the same defect from appearing in both implementation and test oracle.

## Crash-state quantification

For each generated operation, use the clean trace to enumerate every block-write outcome: zero bytes landed, every torn prefix 1..511, and the full 512-byte block landed, plus every flush failure. After simulated power loss, remount only from durable media and run the complete invariant set. Sampling is not acceptable for the per-operation I/O trace.
