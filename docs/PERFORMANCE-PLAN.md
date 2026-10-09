# Software performance framework

**7 October 2026 · PM strategy, ADR-168 · input main `9b300a8`.**
Active directions and stop conditions live in [Software #405](https://github.com/mmsanders/Digital-Tape/issues/405),
not this document. This framework does not issue engine/API/spec changes.

## Objective and fixed requirements

Remove redundant I/O, per-request overhead and avoidable CPU work.
**Whole-C60 copy remains <30 seconds on the target system.** Michael rejected
ADR-167's suggested relaxation. SDR50 is the primary planned mode, not a proven
50 MB/s payload rate. Overlapped reads/writes are a design objective, not an
excuse to return success before completion or durability.

Preserve exact PCM/goldens, committed-data recovery, source NULL-write binding,
zero-write refusals, memory/stack limits, one portable engine, independent
test-first ordering and the current <200 ms synchronous commit requirement.
Any necessary exception is an explicit PM contract delta before implementation.
Hardware/physical qualification remains in its existing phase.

## Sequence and dependency boundaries

| Stage | Intended outcome | Prerequisite / exit |
|---|---|---|
| Design preparation — urgent | Smallest playback fix boundary plus bounded transfer/overlap architecture | Current Software #405; one compact return, no product code |
| Read-only engine correction — first implementation | Buffer reuse, burst refills, bounded CPU/copy work at small render cadence | Scoped Phase2/A8 issuance; independent performance/behavior tests published first; exact-head disposition |
| Resume WP14 | Required native C60 completion and existing port/release gates | Pin the accepted engine under amended A8; #392 → Verification #146 directly; physical holds remain |
| Write/copy follow-on | Contiguous transfers and actual read/write overlap; safe serial fallback | Issued ownership/completion/error contract; appropriate arbitrary-persistence and partial-failure coverage before implementation |
| Record-finalization follow-on | Fewer barriers without losing committed recordings or hiding Stop latency | Separate recording contract/model delta; not a prerequisite for the urgent read fix |
| Target integration | DMA/idle scheduling, real copy/energy/deadline evidence | WP17/18/28 and qualified shipping bus/card; not activated by this framework |

Do not make WP14 wait for a complete copy-pipeline redesign. Preserve the held
#390 port work rather than folding an untested engine rewrite into it. Choose
the clean integration base before disposition, carry unaffected evidence, and
avoid re-acceptance solely because of a docs rebase.

## Playback correction

Retain valid buffered PCM and refill missing contiguous regions in useful,
budget-bounded bursts. Avoid both overlapping full-window rereads and replacing
them with whole-ring RAM moves. Keep 128-frame regression callbacks; service
must not spin when coverage is adequate. Render remains I/O-free and interrupt-safe.

Independent expectations cover exact output, requested bytes and call counts,
invalidation, wrap, fragmented mappings, reverse/scrub/rate changes, endpoints,
lookahead, warm input and small service budgets. Include controls that force
stale data and full-window rereads. Profile ordinary 1x CPU/memory-copy work;
do not create speculative fast paths at the expense of exact arithmetic.
Set workload-specific bounds before implementation, not from its observed result.

## Multi-block baseline and overlapped copy

First reduce one-block calls using valid contiguous runs, with bounded memory
and block budgets. Preserve barriers and handle partial/late errors. Measure
this serial baseline separately so batching is not mistaken for overlap.

The intended pipeline reads chunk N+1 from the source while writing chunk N
to the destination, using separate owned buffers. At start it fills; in steady
state read/write run concurrently; at the end it drains and finalizes.
Two buffers are a starting design, not a new fixed API size.

The engineering design must answer:

- **Where concurrency lives.** Existing synchronous callbacks cannot report
  completion before the buffer is safe. Compare a bounded prefetch design
  with an explicit submit/completion capability if needed; state the smallest
  API/funnel amendment. Do not fork copy behavior into firmware or add an
  opaque unbounded write-back cache.
- **Ownership.** Free, reading, ready and writing buffers have unambiguous
  ownership; reuse follows actual completion. Account for alignment,
  DMA-accessible placement, cache maintenance and caller lifetime.
- **Backpressure and failure.** Bound outstanding operations. Define partial
  writes, late failures, removal and cancellation/quiescence before release
  or unmount. Preserve source playback and destination-failure isolation.
- **Durability.** Distinguish accepted, transferred, durable and committed.
  A flush waits for applicable outstanding writes and actual durability.
  New valid identity follows durable prerequisites; progress is not success.
- **Proof of overlap.** Later independent delayed-device tests must observe
  read N+1 and write N simultaneously in flight, catch premature reuse and
  lost errors, and exercise the serial fallback. DMA enabled or a fast run
  alone does not establish overlap.
- **Real-time coexistence.** Source playback, record work and card stalls
  must fit the service/deadline model. The shared engine remains clock/OS-free.

For payload S, serial time is at least S/R + S/W. A functioning pipeline can
approach max(S/R,S/W), plus fill/drain, metadata, stalls and finalization.
635 MB at 50 MB/s each gives ideal 25.4 s serial or 12.7 s overlapped.
Neither is a hardware measurement. The <30 s gate includes the specified
end-to-end operation, not only bus-active time.

## Recording is a separate problem

[Published counts](https://github.com/mmsanders/Digital-Tape/issues/385#issuecomment-6003622851)
show duplication has about 1.24M single-block reads and writes but only eight
flushes. Load has 155,048 flushes. Do not conflate these bottlenecks.

Evaluate fuller-ring scheduling and bounded transaction/checkpoint durability,
retaining data-before-entries-before-header publication. Identify changes to
WP11 scheduling, engine-api §7 and tapefs §8 before implementation. Avoid an
unbounded final flush or an implicitly longer save delay. Arbitrary-subset/
reordered persistence, repeated-LBA versions, partial calls and late errors
need independent coverage. Raw-destructive simplification is optional separate
work; it is not required to obtain burst transfers or overlap.

## Firmware and measurement

Plan interrupt/event-driven DMA waits, not a permanent busy loop; bounded I2S
interrupts; rate-aware watermarks; and measured clock selection. 64 KiB gives
about 372 ms at 1x but 31 ms at 12x. Measure stalls and underruns, not just MB/s.

Future hardware evidence should distinguish per-card sustained read/write
rates, serial versus overlapped end-to-end copy, CPU/SD duty, energy per C60
and playback energy/hour. A laptop-reader benchmark can diagnose card capability
but cannot prove target performance. The prior formal card-test method needs
independent review before reuse. No hardware run or purchase is assigned here.

## Coordination and acceptance

One bounded Software design return supplies implementation feasibility and
test-interface facts; Verification owns independent expectations, not Software's
private tests. PM resolves precise contract deltas once, then pre-routes
publication → import → implementation → independent disposition.
Do not repeatedly rerun the known unchanged native timeout or remove required
dumps/coverage. Final required qualification, detach/reattach, both exact dumps
and physical/platform witness remain. No package rung advances from this plan.
