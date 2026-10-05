# qp21-count — device calls per C-60 operation (Q-P2-1(b) input)

[Phase 2 plan §5](../../docs/PHASE2-PLAN.md#5-q-p2-1--copy-throughput-and-the-one-block-call-shape-from-379)
asks Software for a count of block-device calls per C-60 operation on `dev_sim`,
with no hardware, as input to PM's P2-R2 ruling between port-level batching and
multi-block engine calls. This is that count. It changes no engine code and makes
no timing or throughput claim.

```sh
make -C tools/qp21-count run     # ~5 s; needs ~1.3 GB of sparse image space
```

## Method

The engine sees `dev_sim` (engine/port), which counts calls. Below it, `count.c`
adds a tally layer counting blocks, the per-call block-count histogram, and how many
calls continue their stream's previous LBA run. Below that is the file port over a
sparse image. The two layers' call counts must agree, and the run fails otherwise.

The calls are shaped as `tapectl` makes them (docs/WP11-CLI-CONTRACT.md):
- 1024-frame feeds;
- service until done before each feed;
- a 1024-block budget for service, promote, respool and dup.

A C-60 is 3600 s: 1212 chunks on a 1,243,137-block device (the `GEOMETRY_OK` minimum).

| Case | What runs |
|---|---|
| **load** | Format a blank C-60, then do what `tapectl load` does: record 3600 s onto Side B (overwrite from 0), commit, promote. Record and promote are counted separately. Format is excluded. |
| **tape_dup** | That loaded C-60 onto a blank C-60 device. Source and destination are counted separately. |
| **respool** | A blank C-60. Record 25 min on Side B, then 64 one-second overdubs spread across it, each a separate commit (128 entries). Re-spool runs both passes, because Side A is empty and leaves room. Overdub is used because an overwrite truncates after the playhead. |

Postconditions are checked:
- the load and the copy each hold 3600 s;
- re-spool leaves one entry and the same timeline length.

## Result (main `4372832`, engine unchanged, Linux x86-64)

| Operation | read calls | write calls | flush calls | blocks read | blocks written | max blocks/call |
|---|---|---|---|---|---|---|
| load: record 3600 s | 0 | 1,240,315 | **155,042** | 0 | 1,240,315 | 1 |
| load: promote | 0 | 6 | 6 | 0 | 6 | 1 |
| **load total** | 0 | 1,240,321 | 155,048 | 0 | 1,240,321 | 1 |
| tape_dup, source | 1,240,313 | 0 | 0 | 1,240,313 | 0 | 1 |
| tape_dup, destination | 2 | 1,240,323 | 8 | 2 | 1,240,323 | 1 |
| respool, 1500 s in 128 entries | 1,055,392 | 1,033,598 | 6 | 1,055,392 | 1,033,598 | 1 |

What the numbers say, without interpretation of cost:

- **Every call is one block.** No read or write in any case moves more than one block.
- **The streams are already sequential.**
  - Record writes: 1,240,312 of 1,240,315 continue the previous write's LBA run.
  - `tape_dup`: 1,240,312 of 1,240,313 reads, and 1,240,312 of 1,240,323 writes.
  - Respool: 1,033,558 reads and 1,033,592 writes.

  A port that coalesces adjacent single-block calls between flushes would see long runs.
- **Promote of a load is adopt-in-place.** It is 6 superblock and index writes, with no chunk copy.
- **Record flushes once per drain of the record ring.** `tapectl` services before every 1024-frame (8-block) feed, so a C-60 load issues **155,042 flushes**, one per 8 blocks. On a desktop file port that is cheap. Under WP-14's durable flush (`fsync` / `F_FULLFSYNC` / `FlushFileBuffers` on a real card) every one of them waits for the card. The flush count is set by the caller's feed/service cadence, not by the engine's call width. It is reported to #385 as an input alongside this table.
- `tape_dup` issues 8 flushes and respool issues 6. Theirs are bounded by commits, not by data.
