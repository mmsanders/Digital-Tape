# Final source-independent observation boundary — ADR-170

This definition precedes Product changes. PM resolved P2READ-001 in ADR-170 at
Product merge `5e6d5fd6cfce64031ba12b37fc367145b5fe18dd`.
It chooses no buffer layout, watermark or implementation algorithm.

## Device transport

Verifier-built fixtures own TAPEFS geometry and logical-to-physical frame mappings.
The adapter calls the public API, never imports the oracle or emits expected values.
Record every callback unfiltered: operation, LBA, block count, return code, API-call
ordinal and injection identity. A successful multi-block read copies actual fixture
bytes; a failing callback poisons its destination and reports failure. Errors carry
zero completed blocks unless the device contract separately provides a completion
count; the public callback provides none. Count requested blocks even on failure.

The independent replay classifies each requested block by the fixture's geometry:
payload, metadata/reserved or out of extent. It checks mapping-run boundaries, total
requested blocks per service call, zero render I/O and literal NULL source-slot write
binding. Nothing in the port may cache or coalesce away engine requests.

## Narrow test-only engine observations

Per-call uint64 monotonic counters, reset after cold mount, report:

| Counter | Increment at the actual operation |
|---|---|
| refill_copy_bytes | Each byte copied from successful device-read storage into play PCM storage |
| warm_adoption_copy_bytes | Each byte copied from an accepted warm descriptor into play PCM storage |
| retained_move_bytes | Each already valid PCM byte relocated within/between retained ranges |
| mapping_entry_visits | Every actual entry inspection for playback mapping, prefix construction/search or lookup |
| idle_loop_iterations | Every executed body iteration in playback-related engine loops reached by the call, including service/refill/mapping helpers; no name filtering |

Direct reads into the final play ring incur no extra copy bytes. Counters count all
intermediate copies, including scalar loops, not only calls named memcpy/memmove.
Output stores are excluded. Copy events must distinguish new PCM from relocation;
an operation doing both increments both categories for their actual bytes. Metadata
copies and recording stores are not playback-copy evidence.

Use direct compile-time test instrumentation, with caller-owned/test-owned counters;
no new public device callback, fifth funnel, private-state snapshot, runtime consumer
API or shipping state. Observations must never drive a Product branch or change PCM.
Counter object keys are exactly these five names, unsigned 64-bit integer deltas
for each API call. Counters are observed before/after the call and must not wrap.
No public engine-state reset or callback is added. Cold traversal accumulation
resets after mount; warm/mount/seek/side/rate/content episodes start before the
initiating API, including its actual playback work. Mount-selection validation
is not playback mapping and is outside the cold reset. Use the larger physical
run/selected-side nonempty-entry count E; failed calls still report actual work.

`oracle.Work` implements V<=4E+4B+32 for traversal, V<=2E+32 per seek,
V<=4E+4B+4F+32 for fixed-direction/rate episodes, and zero I/O/mapping/PCM
work with <=8 loop iterations for each repeated already-done idle service.
B counts requested payload blocks, including redundant/failed requests; F counts
requested render frames, including underruns. No instruction-count/target-deadline
claim follows. Error runs retain extent/budget/PCM semantics and report counters;
their no-error volume ceiling is not asserted.

## Required causal and absence evidence for the complete package

The eventual package must detect actual candidate whole-window rereads, single-block
large-budget amplification, stale invalidation/warm coverage, retained-window movement,
missing interpolation lookahead and sum-of-counts budget overrun. Schema mutation
selftests alone are not these Product controls.

For each seam counter, execute a bounded test-build control that deliberately performs
the observed copy/move/entry inspections; require the independently known nonzero
delta. Include zero-work controls. A constant-zero invented seam must fail. Deliberate
work must occur at the same observation path used by real Product operations.

Compare instrumented and shipping runs for exact PCM/results/status and device traces.
Check shipping preprocessor/object/link evidence for absence of the seam definitions,
references and storage, including static/inlined sites; symbol absence alone cannot
prove compiled-out instrumentation. Audit actual increment sites after the matching
independent behavior tests are authored, preserving the independence order.

The executable `controls.py` requires actual normal and zero `seam_work` operations
with known 256/128/64 copy/move bytes and 9 visits/loop iterations, and an invented-zero
counter control that fails. It also requires twelve real Product defect controls;
`ADAPTER.md` specifies each causal action. Software supplies mechanical binding and
actual-site instrumentation after publication, not expected verdicts or counter setters.
