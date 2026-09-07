# Coverage and merge boundary — DRAFT-8 candidate

**289 independently authored mount cases; zero product-engine runs.** “Ready” below
means test source ready to land, not accepted implementation. `coverage.csv` expands
every mount case ID and its assigned result. These fixtures do not come from format,
recording or an implementation-supplied image generator.

| Spec / acceptance | Test IDs or source | Assertion ready | Dependency / uncovered remainder |
|---|---|---|---|
| TapeFS §2.1 / §4.1 phase 0; WP-06d | `M-phase0-*`, `M-addressable-but-no-store` | Geometry refusal at 0, 1, 2, 2047, 2048 with no callbacks; 2049 reaches admission and refuses store geometry | Format/duplicate pre-read guards not exercised |
| TapeFS §§1–4 phase 2; WP-06d | `M-geometry-*`, `M-device-u32-max`, `M-all-store-owned-A`, `M-timeline-u32-max` | Constants, all six LBAs, exact stored chunk count, water bound, zero/overflowed nominal length, five valid durations and mirror-overlap neighbours, u32 boundary | Raw-device creators and timing/capacity paths deferred |
| TapeFS §4.1 phase 1; WP-06 | `M-no-magic`, `M-bad-crc`, `M-equal-super-divergent`, `M-newer-*`, `M-repair-*` | Magic/CRC structural selection, greater generation before semantic admission, equal-divergent refusal, candidate selected against current water line | Ordinary superblock update/identity assignment and repeated-interruption closure deferred |
| TapeFS §4.1 phase 2; WP-06a/b/d | `M-admit-*`, `M-precedence-*`, `M-repair-*-minor` | Major before state, defined fields before WIP, WIP before geometry; v1.1 writable=false; refusal writes nothing; no read-only repair | Mutator READ_ONLY and feed/commit BUSY results not exercised |
| TapeFS §4.1 phase 4; WP-06a/g | `M-repair-*` (20 variants) | Either candidate location, stale or corrupt partner, RW/NULL-write/newer-minor/write-fail/flush-fail; exact candidate bytes, generation retained, one partner block, flush after successful write; needs_repair and queryability | No subsequent mutator/FAULTED matrix trial; no repair crash injection |
| TapeFS §§5.1–5.4; WP-06/c/d/g | `M-index-*`, `M-valid-*`, `M-generated-*`, `M-timeline-u32-max` | CRC, assignment, entry cap, totals, zero count/length, start and run bounds, checked u32 maxima, all-chunk A water bound, frame disjointness, shared chunks, order independence; no chunk reads | PCM reconstruction/playback, every possible malformed input, resource/timing budgets remain uncovered |
| TapeFS §5.3; WP-06 | `M-A-equal-sequence-*`, `M-A-newest-*`, `M-A-invalid-newest-fallback-*`, `M-B-newest-determines-free`, `M-B-invalid-high-slot-excluded` | Equal sequence refused even for identical A slot bytes; full validity before newest selection; invalid index never repaired | Actual commit/inactive-slot write protocol deferred |
| TapeFS §5.5 running cartridge sequence; WP-06/WP-07 | `M-structural-high-sequence-semantic-invalid` | Mount admission only; ignores semantic-invalid partner for selection | **Counter value/use NOT observable in public mount API.** All-slot structural maximum, branch headroom and successive sequence consumption require written commit headers |
| TapeFS §4.2/§4.4; WP-06f | `M-index-*-0/1`, `M-A-equal-sequence-*`, `M-degraded-*` | A failure on either requested side; both B failure causes; degraded-A success, own B error on B mount; derived free pointer=H; stage-1 degraded branch before stage oracle | All fifteen degraded state cells, side switching, reset-B to B0, new sequence surviving remount, promote/respool refusals remain deferred |
| TapeFS §4.2/§9.3.3; WP-06e/g | `M-stage-row*`, `M-stage-unmatched-*` | One accepted fixture per resume row on both requested sides, S=0 guard, four individually-valid unmatched shapes refused before repair | **Crafted mount-state classification only.** No injected crash, stage clearing, resume completion, arm or recording trial |
| TapeFS §4.1 phase ordering; WP-06g | Every refusal; `run.py` | Zero writes and flushes for every failing fixture; failed mounts cannot proceed to queries/arm; no repair-before-validation | Covers listed fixtures only, not a universal proof for all possible byte strings |
| Engine API §5/§6 mount positioning | `M-resume-*`, `M-empty-*`, `M-timeline-u32-max` | Zero, inside, end, beyond, 2^32, u64 maximum resume values; total/entry info; warm=NULL | Warm descriptor validation, endpoint flags, unmount/seek/set-side transitions and audio playback deferred |
| WP-06h | None | None in this tranche | Entire not-mounted row (including tell output untouched) deferred; no full WP-06h claim |
| TapeFS §7; engine invariant 12; WP-06f / WP-07 | `M-ownership-*`, `M-all-store-owned-A`, `M-B-*`, degraded cases | free_chunks derives from live B on either mount side; lawful shared A references; holes retained; cross-chunk maxima; full/empty boundaries | No new allocation or ordinary audio write executed |
| TapeFS §7; engine invariants 5/10; WP-07 | `ownership.py`, `test_ownership_boundaries` | Independent ordinary bump-allocation and audio-write predicates; boundary/mutation self-checks | **Predicates only.** Operation trace adapter absent; no evidence against allocator. Re-spool/promote exceptions require separate per-operation oracles |
| WP-07 complete acceptance | None | No package acceptance | Reset <1 s/no moved chunks, **10,000 random edit sequences**, committed-index disjointness, post-edit remount/free pointer and actual allocation destinations all remain outstanding |
| WP-06 commit portion; WP-10/11/12a/36 | None new | Existing verifier harness remains green independently | No 97-block/two-flush commit proof, crash closure, golden PCM, full state matrix or 100,000 source-slot transport trials |

## What PM may integrate

All files in this directory are independent verifier material ready to land as candidate
labelled test source. PM must authenticate canonical issuance first. Software may link
`mount_probe.c` mechanically through the real public header without altering assertions.
No test branch remains necessary after this package's publication on verification main;
**product test integration and engine execution are still pending**.

Only the listed mount/admission/selection/info/repair behaviour has executable product
assertions ready. “Read path” here does **not** include rendered PCM. This matrix does
not assert what PR #20 contains: its source, diffs, tests and discussion were not read.
PM/software must compare that implementation surface with this matrix and retain
uncovered allocator, commit, operation and playback behaviour on held branches.

## Next independent acceptance step

After byte-identical PM issuance and test-first landing, execute this probe against the
corresponding implementation; preserve the JSONL; independently review its outcomes.
Mechanical compilation is not acceptance. A clean run can establish only this matrix's
assertions. Then author the operation tests and trace adapters needed for allocator /
running sequence observation, including the full WP-07 random-edit requirement.
The existing zero-blocker/zero-major paper verdict remains separate; actual green
WP-10 is still required for operations/state freeze. Hardware holds are unchanged.
