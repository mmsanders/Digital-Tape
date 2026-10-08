# Software binding for independent READ-1

The verifier-owned `tests/playback_readonly_r1` is imported unchanged from
Verification publication `e5ee1608faa4ad0c15774e8155ddf32164355f1a`, tree
`f8b67c549499bea8d05ade53f7f49fcf3a356131`. Its runner, oracle, fixtures,
counting backend and controls own all expectations. No acceptance follows from
Software's results; READ-2 disposition on the exact held head is required.

Run from the repository root, on a clean committed candidate:

```
python3 -B tests/playback_readonly_adapter/qualify.py --out /absolute/evidence
```

The script builds instrumented, shipping and pinned pre-change baseline engines,
executes the complete canonical 59-case campaign, actual defect/seam controls,
shipping equivalence, absence/leak control and offline replay. `--small` is a
58-case diagnostic only; it cannot pass the complete qualification gate.
The executable launchers, libraries, compiler/flags, sources, head/tree, callback
traces, compressed observations and raw three-layer absence artifacts are hashed.
The READ-1 workflow publishes the resulting evidence as a hashed release asset.
Existing engine CI independently executes the retained Phase1 and WP13 lanes.
Images are regenerated from the untouched verifier fixture builder; the archive
omits these reproducible sparse images, retaining every raw callback log instead.

## Playback layout and publication

The caller ring retains one timeline interval with a circular starting slot.
Completed covered windows remain unchanged until half their capacity is consumed;
refills retain overlap in place and request only the missing range. A dedicated
32768-byte device-read batch supports up to 64 requested blocks, capped by the
remaining shared service budget and the current physical mapping run. The final
read block remains in that batch for a subsequent partial boundary; it is never
copied into a second cache. Successful PCM is copied to final circular slots once.
A nonzero callback publishes none of its destination, including a modified prefix.
Reverse left-gap filling retains progress across budgeted calls and publishes that
gap only when complete. Mapping uses a bidirectional entry cursor, with no prefix
array or per-sample scan. Invalid coverage resets the cursor and device-read cache.
Accepted warm PCM is adopted into caller storage with bounded overlap-safe copying.
The buffered timeline endpoint remains available for FAULTED draining even when
an unsuccessful commit has updated the live in-memory index. This adds playback
state only; write sequencing, recording and commit algorithms are unchanged.

## Actual observation and control sites

`engine/src/read1_observe.h` is entirely conditional on `TAPE_READ1_OBSERVE`.
Shipping has no counter/control definitions, references or storage. The test-owned
object lives in `bridge.c`; `adapter.py` snapshots it around the actual public call
(and render's public tell/status). No counter changes drive an ordinary engine path.

| Counter | Actual site |
|---|---|
| refill copy bytes | Both wrap segments in `play_copy`, immediately with their real copies |
| warm adoption copy bytes | Accepted bounded adoption in `tape_mount` |
| retained move bytes | No ordinary movement; actual relocation in the retained-movement control |
| mapping entry visits | Each inspected entry in `play_map`, including the preceding entry used to move backwards |
| loop iterations | Each service/refill, mapping and render loop body, plus actual idle/control helper bodies |

`seam_work` executes bounded real copying, adoption, movement, entry inspection
and loop work on isolated test-owned storage through the same observation macros.
Its volatile sink preserves the work; no counter setter or estimated result is used.
The invented-zero control suppresses the bridge's reported deltas after real work,
which the independent control rejects. Other controls execute real read-window
restarts, count=1 splitting, full entry scans, retained relocation, skipped side or
commit invalidation, incorrect adopted PCM, omitted lookahead, excessive device
count or deliberate idle helper work. They are absent from shipping preprocessing.
The leak control deliberately compiles the observation sites and test storage into
the otherwise matching engine build, producing real markers at all three layers.
READ2's independent actual-site/build completeness audit remains required.

No frozen API/spec, ring minimum, golden, imported test, write algorithm, hardware
or asynchronous operation is changed. Held WP14 work resumes only after independent
READ-2 PASS, authorized integration and PM's A8 engine pin.
