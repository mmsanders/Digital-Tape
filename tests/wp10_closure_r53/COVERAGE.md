# WP-10 R53 coverage, ranking and backlog

`coverage-ledger.json` splits acceptance §Stream 2 WP-10 into 61 rows:

- 48 bound to accepted evidence: core crash #68/#69 (28,760), R29-C #81 (4,209,696), R29-A #86
  (44,307), R29-B #83 (57,611), the combined #272 re-run #87, and the R25/mount dispositions.
- 3 uncovered, reachable rows published here.
- 9 uncovered rows ranked as backlog.
- 1 contract conflict for PM.

## Ranking rule

Rows are ranked by the harm the missing check guards against. Destroying data or silently
substituting it ranks first, then an unmountable cartridge, then a wrong or merely unhelpful result.

| Rank | Row | Harm if broken | Here |
|---:|---|---|---|
| 1 | Empty-source duplicate, every boundary (V5-002) | Destroys a good destination cartridge **and** leaves one with no selectable Side A; the spec's own blocker | **Published** |
| 2 | Format/dup steps 2–3 on a reusable destination holding another album's sequence-500/501 index (absorbs dup shape regression (iii)) | Silent substitution: the copy plays the old album, or an interrupted run mounts under the previous identity | **Published** |
| 3 | Blank-media format and duplicate table | First-use cartridge unmountable after the mirror is durable; wrong `needs_repair`; missed write-through outcome | **Published** |
| 4 | Backlog 1: layout-preserving dup C-90 → C-60 | Addresses chunk ≥ `total_chunks`: writes past the store, can clobber the mirror superblock | backlog |
| 5 | Backlog 2: `free_next` after every injection in C69 and R29-B families | Stale frontier: the next recording overwrites live audio | backlog |
| 6 | Backlog 3: record `tape_service` audio writes before commit | Live chunk overwritten under crash (mitigated by accepted WP-07 disjointness) | backlog |
| 7 | Backlog 4: mount phase-4 repair write | Torn or wrong-copy repair leaves an unmountable cartridge | backlog |
| 8 | Backlog 5: dup re-run after interruption completes | Destination stuck `INCOMPLETE` (recoverable by format) | backlog |
| 9 | Backlog 6: completed dup mounts on Side B, label copy | Unusable sandbox side | backlog |
| 10 | Backlog 7: reset B sequence / stage-clear generation one short | Wrong error code or a partial write before refusal | backlog |
| 11 | Backlog 8: empty re-spool zero-needed cells at 0xFFFFFFFE, each counter separately | Wrong error code | backlog |
| 12 | Backlog 9: post-crash `tape_render` of re-spool layouts | Raw bytes already proven; render path only | backlog |

## Published package: exhaustive, not sampled

| Scenario | Row | Writes | Flushes | Injection points |
|---|---|---:|---:|---:|
| DUP-EMPTY-BLANK | 1 | 8 | 4 | 8,216 |
| DUP-EMPTY-REUSABLE | 1 | 10 | 6 | 10,272 |
| DUP-REUSABLE-STALE | 2 | 13 | 10 | 13,358 |
| FMT-REUSABLE-STALE | 2 | 8 | 6 | 8,220 |
| FMT-BLANK | 3 | 6 | 4 | 6,164 |
| DUP-BLANK | 3 | 11 | 8 | 11,302 |
| **Total** | | | | **57,532** |

Each count is `2 modes × (writes × 513 + flushes)`: before, every torn prefix 1…511 and after at
every block write, plus a fault at every flush. The split is flush-required 28,766 and
write-through 28,766 (torn 57,232, before 112, after 112, flush 76). The census adds 6 completion
cases and 1 empty-family case; the case-set SHA-256 is
`72717654d563905b8e76c79959757b0ae625a3f2353944c2818baf35ca83bf0e`.

Durability model (tapefs §8.1):

- A torn prefix is durable in both modes.
- A completed write is durable immediately in write-through.
- In flush-required mode, a completed but unflushed write may or may not be durable, so the
  oracle enumerates every combination.

After each injection the adapter reports the write/flush trace and the durable bytes. It then
remounts from those bytes three ways: Side A read-only, Side A writable (with the rendered PCM),
and Side B writable. The oracle requires all of the following:

- the trace is exactly the §9.5/§9.6 order;
- the durable bytes are a state the model permits;
- each remount's result, `uuid`, `free_chunks`, `total_frames`, `entry_count`, `side_b_valid` and
  `needs_repair` equal the classifier's prediction from those bytes;
- the phase-4 repair events are exact;
- rendered Side A is the selected generation's audio;
- the duplicate's source device is unchanged.

The classifier follows tapefs §4.1/§4.2/§5.2/§5.3. The self-test cross-checks it against a
separate restatement of the §9.5/§9.6 permitted-outcome tables on all 83,394 possible durable
images.

Causal controls: every control must go red in each scenario it targets, both with and without
trace binding. Without trace binding, the outcome checks alone must catch each defect.

| Row | Controls |
|---|---|
| 1 | `empty_source_zero_frame_entry` (the V5-002 regression), `empty_family_promote_accepts`, `source_written` |
| 2 | `slot1_not_zeroed`, `template_flush_skipped` |
| 3 | `primary_before_mirror`, `needs_repair_hidden` |

## PM finding (contract conflict)

tapefs §4.1 phase 1 says "neither valid → `TAPE_ERR_BAD_MAGIC` or `TAPE_ERR_CRC`" without a rule
for choosing. But tapefs §9.5/§9.6 and acceptance WP-10 "Format, blank media" permit only
`TAPE_ERR_BAD_MAGIC` before and inside the step-4 mirror write. A torn blank-media mirror write
that lands at least 8 bytes has intact magic and a bad CRC, and 3,024 crash cases here reach that
state. The oracle admits `{BAD_MAGIC, CRC}` there only, and replay counts every CRC answer. PM
should rule which result is normative.

Excluded: Product binding, WP-12/WP-12a state-matrix rows (#104), WP-11 listening or goldens, card
atomicity, hardware, and re-running accepted campaigns. No complete WP-10 claim is made.
