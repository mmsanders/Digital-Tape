# WP-10 final backlog (#118): coverage, PM finding and closing ledger

| Row | Criterion | Cases | Controls |
|---|---|---|---|
| 1 | `WP10.counters.v5_015.reset_b_and_stage_clear_generation`: `tape_reset_side_b` one `sequence` short, and §8 stage clearing (via reset B, arm, re-spool) one `sb_generation` short | **13 contract cases**: 8 one-short refusals and 5 exact-threshold successes | `reset_b_ignores_sequence_headroom`, `stage_clear_before_headroom`, `stage_clear_generation_not_counted`, each with an **exact kill set** |
| 2 | `WP10.headroom.zero_needed_reserved.empty_respool_each_counter_each_value`: empty re-spool at `sequence` and at `sb_generation` = `0xFFFFFFFE` and `0xFFFFFFFF`, each counter separately | **4 cells + 2 converses** | `zero_needed_consults_counters` (the DRAFT-7 predicate, V7-002), `respool_ignores_sequence_headroom`, each with an exact kill set |
| 3 | `WP10.op.respool.post_crash_render`: after every re-spool injection, Side B renders bit-identically and Side A is unchanged | **5 fixtures**; the synthetic binding yields 24,672 exhaustive injections | `respool_commits_before_copying`, `respool_pass1_onto_live_b` |
| 4 | `WP10.dup.rerun_crash` (new, from #116): exhaustive crashes inside the `tape_dup` re-run, from each §9.5 interruption class | **207,560** (103,780 per mode) over 16 representatives | `rerun_skips_barrier`, `rerun_final_keeps_old_uuid`, both **also killed with trace binding off** |

The case-set SHA-256 is `159b4ac64a5e653df2625a025f5f8cf13bcb90fed9a11905a1733f7a97167cd1`. NOTHING-TO-DO promote
at the reserved values is not re-authored, because #105 records it as accepted (R29-A, 4 cases).

## Row 1

The fixtures are the accepted C69 builders with crafted counters. "One short" means the counter plus the
branch's own `needed` exceeds `0xFFFFFFFD`. Each refusal must return `TAPE_ERR_SEQUENCE_EXHAUSTED` with **zero
write callbacks** and a byte-identical device.

| Case | Crafted counters | What it checks |
|---|---|---|
| RB-HEALTHY-* | live-B `sequence` `0xFFFFFFFD` (short) / `0xFFFFFFFC` (threshold) | Threshold commits B1 at `0xFFFFFFFD` with Side A's entries |
| RB-DEGRADED-* | B0 = B1 at those sequences | Threshold writes **B0** directly (§9.2) |
| SC-RESETB-GEN / SEQ-SHORT, SC-ARM-GEN / SEQ-SHORT, SC-RESPOOL-GEN / SEQ-SHORT | stage-1 media (§9.3.3 RESUME row 1) with `sb_generation` or `sequence` at `0xFFFFFFFD` | "After their own preconditions have passed — including §4.5's counter headroom, which counts both the clearing write and the commit": no clearing write before the refusal |
| SC-*-THRESHOLD | both counters at `0xFFFFFFFC` | Stage clearing writes the mirror then the primary, flushing after each, before any other write. Both copies become `promote_stage` 0, staging 0, `a_high_water` unchanged, generation `0xFFFFFFFD`. Reset B commits at `0xFFFFFFFD`; arm commits nothing. Re-spool commits one entry at `0xFFFFFFFD` and skips pass 2 because headroom allows one commit (§9.4) |

## Row 2

| Cell | Result |
|---|---|
| Empty Side B at each counter × {`0xFFFFFFFE`, `0xFFFFFFFF`}, the other counter ordinary | `TAPE_OK`, `more_work` false, zero writes, byte-identical media |
| Converse 1: non-empty Side B at `sequence` `0xFFFFFFFE` | Refuses, because `needed` ≥ 1 |
| Converse 2: non-empty Side B at `sb_generation` `0xFFFFFFFF` | Completes. The generation is not consulted (`needed` 0) and is not advanced (both superblocks byte-identical) |

The converses show the cells pass because `needed == 0`, not because the counters are ignored.

## Row 3

Frame counts are small, so exhaustive injection is tractable, and every chunk carries a coordinate-unique
frame pattern.

| Fixture | Shape |
|---|---|
| RS-TWOPASS | pass 2 can run |
| RS-REFERENCES-A | B references only A's chunk, the post-reset-B shape |
| RS-FRAGMENTED | 3 entries, out of order, mid-chunk starts, one crossing a block boundary |
| RS-CHUNK-CROSSING | one entry spans chunks 2 and 3 |
| RS-ONE-COMMIT | `sequence` `0xFFFFFFFC`, so §9.4 skips pass 2 |

Engine write order and partitioning are not pinned (the #115 ruling). The binding enumerates injections
from its own clean trace: every write × landed 0..512, plus every flush, in both modes. The oracle then
requires the following:

- **Completeness:** the crash list covers exactly the clean trace's injection points, and each fires at
  its `prefix_len`.
- **After every crash:**
  - Side B mounts with the same `total_frames` and `side_b_valid`.
  - Its entry count is either the pre-state count or 1.
  - It renders **bit-identically** to the pattern-derived timeline.
  - Side A renders unchanged.
- **Clean run:** completes, leaves one entry, flushes after its last write, and makes every chunk write at
  or above `a_high_water`.

A layout that references a chunk overwritten before its commit cannot render bit-identically, because the
pattern is unique per (chunk, frame).

## Row 4

**Representatives.** There is one per (destination shape, §9.5 interruption class): the first first-run
injection in plan order whose durable image is **unique**, so every conforming binding holds the same bytes
before its re-run. That gives 16 representatives covering the classes `BAD_MAGIC`, old cartridge,
`INCONSISTENT`, `INCOMPLETE` and completed copy.

**Injections.** The re-run's own tapefs §9.5 transaction is planned from the crashed state (item 5
classification, as in #116) and injected exhaustively in both modes.

**Checks.**
- The trace follows §9.5.
- The durable image is a state the §8.1 model permits.
- Each remount (`ro_A`, `rw_A`, `rw_B`) equals the classifier's prediction.

**The #116 property, stated on observations alone.** No writable Side-A remount may show the previous UUID
with the source's audio, or the fresh UUID with the previous album.

- The self-test proves this over **every** permitted durable image of every planned injection, except in
  the cells below.
- `rerun_skips_barrier` and `rerun_final_keeps_old_uuid` are killed even with trace binding off.

## PM finding V-R54-03: a torn exhausted-generation fallback can resurrect the previous superblock

**Reachable state.** Two power cuts, each tearing a superblock write inside the bytes the old and fresh
superblocks share, make a cartridge mount under the previous UUID while it plays the copied source. Any
engine that follows the frozen contract reaches this state, in these 48 cells (`oracle.PM_FINDING_CELLS`):

1. **Destination.** The shape is `exhaustion_candidate` or `exhaustion_equal_divergent`, with
   `sb_generation` `0xFFFFFFFD`. tapefs §9.5 therefore takes the §4.5 zeroing fallback: zero the partner,
   then the candidate.
2. **First cut.** It lands inside the candidate's zero write after **1 byte**. The magic now fails, but
   bytes 1–511 of the previous superblock survive: old UUID, generation `0xFFFFFFFD`, CRC.
3. **Re-run.** It sees no valid superblock and takes the blank path, so there is no step-1 barrier. It
   zeroes the slots, copies the source, commits A0 and B0, and writes the fresh mirror at generation 1.
4. **Second cut.** It lands inside the fresh **primary** write after **1–12 bytes**. Those bytes (magic,
   version) are identical in both superblocks, so the torn block is exactly the previous superblock, with a
   valid CRC.
5. **Mount.** tapefs §4.1 picks the higher generation, `0xFFFFFFFD`, over the fresh mirror at 1. The
   cartridge mounts under the **previous UUID** with the **source's indices and audio**.

**Scope.**
- There are 12 landed values × 2 modes × 2 shapes. Each cell has a single permitted image, so every
  conforming engine lands in it.
- The oracle stays exact: the remounts must equal the classifier's prediction. The cells are counted
  (`v_r54_03_resurrected_previous_superblock`) instead of failed.
- An identity violation anywhere else is a failure.

**Clauses.** The finding sits between these clauses:
- tapefs §9.5 item 5: a destination with no structurally valid superblock is treated as blank, with no
  barrier.
- The §4.5 zeroing fallback.
- tapefs §4.1: higher `sb_generation` wins.
- acceptance WP-10: "no injection point yields a cartridge that mounts under the destination's previous
  UUID".

**Likely fix (PM's decision).** Treat a destination as blank only when both superblock blocks are all zero.
Otherwise the re-run zeroes both superblock blocks (partner first) before step 2, so a later torn fresh write
lands over zeros and not over a surviving old block.

## Closing ledger

`coverage-ledger.json` gives every row of #105's 61-row ledger a closing status, plus the new
`WP10.dup.rerun_crash`, and `audit.py` checks it. Nothing is left uncovered:

| Status | Rows |
|---|---:|
| accepted exact evidence | 48 |
| published; Product binding independently disposed PASS | 7: #105 rows (Product #318, Verification #119) and #116 rows (Product #330, Verification #120) |
| published; Product binding pending | 7: #110 rows (Product #329, rebind onto the #124-corrected subtree) and the 4 rows here |

PM's `{BAD_MAGIC, CRC}` ruling on the torn blank-mirror row is carried. That row is covered by the #105
package, which asserts both results.

**Excluded:** Product binding of this package, WP-12/WP-12a, WP-11, card atomicity and hardware. No complete
WP-10 claim is made until every Product binding is independently disposed.
