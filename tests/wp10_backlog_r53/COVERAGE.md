# WP-10 backlog rows 1–3: coverage

| Row | Criterion | Injection points (exhaustive) | Controls |
|---|---|---|---|
| 1 | Acceptance WP-10 "Duplicate, destination shape" (ii): a layout-preserving copy is rejected by construction | DUP-FRAG-BLANK 11,302 + DUP-FRAG-REUSABLE 13,358 = **24,660** (12,330 per mode) + 2 completions | `layout_preserving`, `fragment_order`, both with and without trace binding |
| 2 | Universal assertion: `free_next == max(a_high_water, live-B last+1)` after every injection, for C69 and R29-B | C69 **28,760 / 28,760**; R29-B **26,392 / 57,568** (the rest cannot remount) = **55,152** (27,570 flush-required, 27,582 write-through) | `frontier_other_generation`, `ignores_a_high_water`, `format_empty_b_frontier`; C69 snapshot (#124): `c69_post_metadata_diverges`, `c69_post_chunk_diverges`, `c69_pre_metadata_drift`, `c69_setup_alters_live_chunk` |
| 3 | Recording session: injections at `tape_service` audio writes before commit, overwrite / overdub / splice | Per mode and durability mode: 3 one-block writes × 513 + one per observed flush (synthetic 1,542 × 6 = **9,252**) | `service_writes_live_chunk`, `service_commits_index`, `service_missing_final_flush`, `frontier_counts_uncommitted_audio` |

## Row 1

**Source (a "C-90"):** 21 s, 8 chunks. Side A is `{6,0,40}, {2,5,50}, {7,100,38}`: 128 frames, out
of chunk order, with two fragments at chunk ids the destination lacks.

**Destination (a "C-60"):** 9 s, 4 chunks, blank or reusable. It passes capacity: `len_A` = 1 ≤ 4.

**Checks:**

- Every destination chunk-region callback, read or write (excluding the mirror LBA), lies in
  `[0, len_A)`. None addresses a chunk id ≥ `total_chunks`.
- The completed copy is `A0 = {0,0,128}` with `a_high_water` 1, and renders the three fragments in
  timeline order.
- Crash outcomes use the #105 durability model and mount classifier: tapefs §8.1, §4.1/§4.2 and the
  §9.5 table.

## Row 2

The frontier is observed only where it exists: on an injection whose durable state remounts. For
each accepted case, the oracle rebuilds that case's durable post-crash state with the campaign's own
pinned model (`crash_core_draft8.oracle.expected_snapshot` or
`format_dup_identity_draft8.oracle.expected_snapshot`). It binds the Product observation to that
state, derives the frontier from the selected superblock and live-B index, and requires
`tape_get_info` `free_chunks == total_chunks − frontier`.

- **R29-B** is bound by the SHA-256 of the whole compact post-crash snapshot.
- **C69** is bound exactly as the accepted C69 oracle binds it (corrected in #124, below).

- Degraded-B uses `a_high_water` (tapefs §4.2 step 4).
- Superseded chunks are never counted, because only live-B entries enter the maximum.
- R29-B's other 31,176 injections remount `INCOMPLETE`, `INCONSISTENT`, `BAD_MAGIC` or `VERSION`.
  They are not re-run, because the assertion cannot observe them.

This row adds an assertion; it does not re-accept either campaign.

### #124 correction: C69 snapshot binding

The #110 publication hashed the **whole** expected C69 snapshot, simulated from the **fixture**. That
bound two things the accepted C69 campaign (`crash_core_draft8/oracle.py` `validate_case`) does not:

1. `image_sha256`. `expected_snapshot` deep-copies its `pre` and never recomputes this field, so it
   carried the fixture image's digest forward stale. The accepted `_raw_parts` omits it.
2. The fixture's chunk digests. The accepted campaign simulates from the **observed** pre-snapshot, in
   which `record_commit` setup has lawfully written the fed audio into pending chunk 2
   (`_expected_pre_metadata`).

A correct engine therefore failed every C69 case except the 292 whose durable image never changed and
that are not `record_commit` (28 `reset_b` first, 84 `stage_clear` first, 180 `stage_clear` closure).
That is exactly the 28,468 / 28,760 PM upheld on Product #329.

C69 observations now carry pre/post metadata digests and chunk digests (schema v2, `ADAPTER.md`). The
check is the accepted campaign's own:

- pre metadata equals the fixture, and only `record_commit`'s chunk 2 may differ from it;
- post metadata equals `expected_snapshot` from that pre-state;
- post chunk digests equal pre.

The self-test proves, on all 28,760 C69 cases, that simulating from the fixture's metadata equals
simulating from any observed pre-state with those constraints. It also runs one real-bytes case per C69
shape (lawful chunk-2 audio, true `image_sha256`). The #110 binding rejects each of these wrongly and the
corrected binding accepts each. Four new controls must each still kill a real divergence, with an exact
kill census:

| Control | Kills |
|---|---|
| post-crash metadata byte | 28,760 C69 cases |
| post-crash chunk digest | 28,760 C69 cases |
| pre-operation metadata drift | 28,760 C69 cases |
| setup altering live chunk 0 | the 6,168 `record_commit` cases |

The `free_chunks` frontier assertion, R29-B, row 1, row 3 and the case set are unchanged.

## Row 3

The fixture is C69's record fixture: `a_high_water` 2, A0 and B0 at chunk 0, `free_next` 2. The
session feeds 384 frames and services at `block_budget` 1. engine-api §7 requires all chunk data to
be durable before commit is callable, but does not fix `tape_service`'s flush count. So the plan
fixes the three one-block audio writes at chunk 2, and enumerates flush boundaries from each
binding's own clean trace. The last flush must follow the last write.

After every injection:

- the superblocks and all four index slots are byte-identical;
- live chunk 0 is byte-identical;
- Side B remounts as the pre-operation generation: `free_chunks` 3, `total_frames` 131,072, one
  entry, exact PCM.

The post-operation generation is unreachable here, because commit has not started.

## Backlog

The remaining backlog, now 6 rows, is in `backlog-update.json`:

1. mount repair crash
2. dup re-run
3. dup Side-B mount / label
4. reset / stage-clear one short
5. zero-needed reserved cells
6. post-crash re-spool render

Excluded: those 6 rows, Product binding, WP-12/WP-12a, WP-11 and hardware. No complete WP-10 claim.
