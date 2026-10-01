# #130 rows: coverage

| Row | Ledger | Cases | Controls (exact kill sets) |
|---|---|---|---|
| `WP09.overdub.full_scale_saturation` | WP09-L02 | 3: start (0), middle (16), straddling the end (40) | `overdub_wraps` 3, `negative_rail_32767` 3, `positive_overflow_wraps` 3, `append_mixed_with_last_frame` 1 (straddle only) |
| `WP10.respool_render.trace_floor` | V-R55-01 | 5: the #118 row-3 fixtures | `under_report_one_event`: all 48 single-event drops (24 writes, 24 flushes) go red; `drop_second_commit`: exactly the three fixtures §9.4 forces to two commits |

The case-set SHA-256 is `5b14062694cfc1ef219612d8086bac56e0a1536680c129537548b687cfbc5fe0`.

## Row 1

The 16 `(existing, incoming)` pairs in `rows.COMBOS` include:

- the criterion's own case on both signs: `32767 + 32767 → 32767` and `−32768 + −32768 → −32768`;
- one LSB past each rail;
- landing exactly on each rail;
- opposite full scale (→ −1);
- mid-scale overflow.

The left channel walks the pairs forward. The right channel walks them backward with the roles swapped, so both channels see every pair.

- **Start and middle** each mix all 16 pairs.
- **Straddle-end** mixes 8 and appends 8. §11 says the appended frames, which include −32768 and 32767, pass through unchanged.

The oracle compares the full remounted Side B render with `rows.expected_timeline`. Its arithmetic is engine-api §8's int32 sum plus clamp, written out independently.

## Row 2 (V-R55-01)

The #118 row-3 oracle enumerates crash injections from the binding's own clean trace. It does not pin #115 partitioning. So an *adapter* that omits one write, or one non-final flush, and then enumerates from the shortened trace passes it.

The self-test demonstrates exactly that: the pinned #118 oracle accepts 43 of the 48 single-event drops. The only ones it catches are the five final flushes.

This row restores the floor the spec does force. A conforming engine cannot go below it, whatever its partitioning:

- **tapefs §8**, per commit: chunk data ≥ ⌈4T/512⌉ blocks → flush → entry block 1 of the inactive slot → flush → exactly one header block → flush.
- **tapefs §9.4**: the fixture's commit count.

Pass-1 placement is not pinned (#115), which is why RS-REFERENCES-A admits 1 or 2 commits. Extra flushes, extra chunk blocks and reads are also allowed.

**Authoring sanity check, not a disposition.** I regenerated the accepted Product row-3 clean traces during #128; that JSONL is byte-identical to the retained Product evidence. They meet this floor exactly: 2 commits = 6 writes and 6 flushes, or 1 commit = 3 and 3.

## Excluded

- Listened goldens (WP-11, Michael-held).
- Rows already covered (see `LEDGER.md`).
- The accepted `wp10_final_r54` subtree, which is unchanged.
- Product bindings, hardware and release.
