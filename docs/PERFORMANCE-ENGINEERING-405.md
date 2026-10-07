# Performance engineering return — Software #405

**Revision 1 · 7 October 2026 · Ready for PM review · design only.**
This is Software's feasibility return under [#405](https://github.com/mmsanders/Digital-Tape/issues/405),
not a contract, independent oracle, implementation permission or acceptance.
PM strategy remains [ADR-168's framework](PERFORMANCE-PLAN.md).

## Inputs and observed boundary

| Input | Exact identity |
|---|---|
| Onboarded/current main and branch base | `4ec0b3c81c9ada0b327112bc16b9d9faf4ee835a` |
| Assignment Product input; frozen DRAFT-10 manifest | `9b300a8c4ef9b05bdcacceec7bb27a09254891d5` |
| Held WP14 PR #390 | `dbe6283dd6393e615e2bc18ef4a6c81673c7efc1` |
| Issued Verification publication | `56e25cc1736fdc62a6d9bc4e6cdc09d5f8cac1b2` |
| ADR-165 WP14 contract publication | `6f362f093435ab1a1501055b3bb1cdbe37a5b04c` |
| #405 scope read | Open, software-lead; updated `2026-10-07T15:03:02Z` |

DRAFT-10 hashes: tapefs `2a6a9f7b6fe1e5f9e3fe068b3c6460a81256276082bb7e336c01dbf1e9c17eba`,
engine-api `aa042e41e35b02bf2bb6b3896e59340a947720c27dc5fc52a24d657ccd66b33a`,
acceptance `50aa63bd751fdc6b4636de0eb48253887be19b7ec2841768449217b4e9b9e547`.
All recommendations below preserve the frozen bytes until PM explicitly issues any delta.

At the base, `engine/src/play.c` resets `play_frames` when its target first frame changes,
then refills with one-block reads. It also copies each fetched block into the play buffer.
The corrected #392 observation is therefore consistent with source: approximately 159M
reads/81.3 GB for 635 MB audio. This turn did not rerun that observation.
`raw_ops.c` assembles duplicate output one block at a time; both source read and
destination write consume budget. `record.c` tracks unflushed data and flushes when
accepted recording work drains. Dup's roughly eight flushes and load's 155,048
flushes are different problems ([published counts](https://github.com/mmsanders/Digital-Tape/issues/385#issuecomment-6003622851)).
No target rates, overlap, energy or new resource measurements are claimed.

## 1. Smallest urgent playback slice

Change only common-engine read buffering, mapping/refill cursors and their invalidation
plumbing in lifecycle/content-change paths. Preserve recording writes, barriers,
long-operation algorithms, ports, public signatures and the exact §6/§8 render arithmetic.
A playback-buffer invalidation edit in a mutator is included only to prevent stale PCM;
it must not change that mutator's on-media work. Import independent tests first.

Recommend a circular PCM window or equivalent bounded tiles inside the existing
caller-owned minimum 64 KiB ring. Advancing 128 rendered frames changes cursors,
not the location of every retained sample. Refill a free region only below a coverage
watermark; aim for 32 KiB contiguous requests on the declared large-budget workload.
A useful burst is capped by remaining block budget, physical entry extent, ring/free
region, device extent and the selected transfer ceiling. Partial block edges use
bounded staging; aligned interiors can read directly into an unexposed free region.
Never read across a mapping discontinuity just to obtain a larger call.

The service loop must converge with an unchanged playhead: when its refill obligation
is met, `more_work=false`, and repeated service before more consumption performs zero
playback I/O. Below the watermark, `more_work=true` only for work that another service
call can actually advance. While armed it still includes the existing recording
obligation. Budget 1 must make progress; budget 0 keeps the current refusal.
A ring need not be completely full after every 128-frame render.

Retain valid samples on an in-range seek only when timeline identity/content is
unchanged; discard unreachable coverage on other seeks. Side switch always invalidates,
even when selecting the current side. Mount/unmount, replacement index/content and
failed/incomplete reads cannot expose stale PCM. Direction changes may retain an
intersection but must acquire reverse coverage and interpolation lookahead before use.
Preserve the end snap, final frame, fractional samples, all int32 rates, underrun and
FAULTED ring-drain behavior. The efficient envelope below covers selected rates only;
the whole accepted arithmetic domain remains correct.

Warm input remains contiguous `tape_warm_start` PCM with the existing ordered validation;
adopt or copy its accepted range once into the chosen representation. Do not reinterpret
the caller's descriptor as internal tile metadata. Publish only fully completed
coverage. No OS/interrupt primitive enters the portable engine. Host tests use controlled
service/render interleaving; target integration must establish coherent cursor
publication and protect retained samples from refill/ISR races without waiting for SD
inside the audio ISR. C99 alone does not license unsynchronised concurrent state access.

### Proposed independently issued envelope

These are workload-derived design proposals for PM/Verification, not thresholds fitted
to a candidate. Keep metadata/mount reads separately classified; include all chunk-data
reads, including wasted/retried reads, in the payload counters. Bounds apply to no-error
runs with a 65,536-byte ring and cold mount unless specified.

| Workload | Proposed bound and rationale |
|---|---|
| Contiguous forward 1×, start 0, S PCM bytes; service budget 1024 until done, render ≤128 | Payload blocks ≤ ceil(S/512) + 130; payload callbacks ≤ ceil(S/32768) + 2. One traversal plus bounded alignment/lookahead/window edges; 32 KiB useful bursts, no per-render replacement reads |
| Same full C60: S=635,040,000 | ≤1,240,443 payload blocks (635,106,816 bytes), ≤19,382 payload callbacks. Nominal traversal is 1,240,313 blocks/19,380 bursts |
| Same contiguous traversal, budget b in {1,2,7,64} | ≤ceil(S/512)+130 blocks; callbacks ≤ceil(S/32768)×ceil(64/min(b,64))+2. Small budgets subdivide useful transfers without rereading retained PCM; no burst-size lower limit overrides b |
| Monotone fragmented 1×, E nonempty mapping runs | Blocks ≤ceil(S/512)+2E+128; calls ≤ceil(S/32768)+2E+2 at budget 1024. Entry edges may require two partial-block visits and split burst rounding; never cross invalid physical extents |
| Repeated service with unchanged covered playhead, stopped or playing | Zero new payload reads and zero retained-PCM movement once service reports done; termination must not depend on a subsequent render |
| Seeks, direction/rate changes, warm-start and content invalidation | Exact PCM first; report refill episodes, unique required physical blocks, edge blocks and transferred bytes separately. Verification issues episode-specific bounds; no global C60 traversal bound is claimed for arbitrary jumping/extreme rates |

For the monotone forward cases, total service PCM copy work should be ≤ payload bytes
read + one 64 KiB initial warm adoption (zero for cold); retained PCM must not be moved
at each render. Output stores are naturally 4 bytes per rendered frame. Publish a
test-only counter definition for refill copy bytes and retained-range move bytes,
plus a static/profile check that finds whole-ring memmove. Idle service takes constant
bookkeeping work. Mapping should advance a bounded entry cursor so a monotone pass
visits O(E + transferred blocks) entries, rather than scanning the entire index at
each block; arbitrary seek may perform a bounded O(E) lookup.
The asymptotic work bound is the proposed CPU criterion; host cycle/time profiles are
diagnostic and target worst-case ISR/service latency remains a later measurement.
Do not add a special 1× renderer to this first slice unless needed to meet an independently
issued CPU bound; exact arithmetic already works and a buffering fix is urgent.

### Precise issuance needed before implementation

| Authority surface | Narrow proposed change |
|---|---|
| Phase2 plan §1 exit item 3, exclusions; §3 host independence | Permit this named read-only common-engine exception, preserving Rule 1, all Phase 1 replays/goldens and all other engine holds |
| WP14 A8; WP14 contract §1 and §8 | Replace moving-main equality with equality to the explicitly accepted playback-engine tree after independent disposition. WP14 adds no engine changes beyond that pin; ports remain uncoalesced for writes |
| New playback performance addendum | Issue selected workloads/counter definitions, service refill/done semantics and CPU/copy bounds. §6.3 already permits bounded multi-block reads and does not require full-ring refill on each render |
| Frozen engine-api §3/§4/§5/§6/§8 | No signature, buffer-minimum, frame-arithmetic or format change proposed. If PM elects to add normative refill text to frozen §6.3, issue the exact amendment/manifest through the normal approval path; this note is not that issuance |

No write-persistence model expansion is a prerequisite for this read-only slice.
The counter seam can be a verifier-owned counting device plus narrowly issued test-only
CPU/copy observations; no production introspection API is required.

## 2. Transfer baseline, then actual overlap

First batch serial payload transfers into valid contiguous runs, retaining synchronous
callbacks and existing publication barriers. Use a bounded caller-owned workspace;
prototype envelope for copy design is two 16 KiB buffers, 32 KiB total, not a mandated
ABI or permission to enlarge RAM. Never borrow playback/record storage that is live.
Account separately for engine .data/.bss/instance ≤200 KiB, stack ≤8 KiB, rodata ≤32 KiB
and actual target buffers/DMA descriptors/cache-line padding. Resource availability
must be measured before choosing the final workspace; no stack-sized transfer arrays.

| Approach | Concurrency and recommendation |
|---|---|
| Existing synchronous callbacks with interrupt-driven DMA waits | Keeps ABI and safe ownership; improves CPU duty and batching, but read-then-write remains serial |
| Bounded port prefetch | Could speculate a source read into port-owned storage while destination write blocks, but engine mapping/next extent, budgets, cancellation and playback arbitration become implicit. Ordinary synchronous callbacks do not identify the next logical copy run. A hidden cache would move ownership/error semantics to each port. Do not choose this as the shared copy architecture |
| Explicit opt-in submit/completion capability | Recommended follow-on: common engine owns two-buffer copy state; caller/ports own hardware. Capability absent selects the same algorithm's synchronous serial path. Requires a versioned optional configuration/API, not an incompatible silent change to tape_dev |

The async contract must specify submit-read/submit-write, nonblocking completion query
and quiescence/cancel mechanics, with bounded request tokens. Exact ABI is for PM issuance:
retain existing init/dev users through an opt-in extension rather than adding mandatory
callbacks to every binding. All new indirect calls need named dev.h funnels plus the
WP13 source/audit contract update; current §3 permits exactly four funnels.
An async write capability must never circumvent NULL-write or effective writability.
Serial ports remain conforming; one engine owns mapping, compaction and barrier order.

### Ownership and completion model to issue

| Buffer state | Owner and permitted next event |
|---|---|
| FREE | Engine may assign a bounded logical/physical extent and submit a read |
| READING | Source port owns buffer/token; engine/render/destination cannot access it |
| READY | Successful whole requested read completed; engine may compact permitted edge data and submit destination write |
| WRITING | Destination port owns immutable bytes/token; buffer cannot be refilled or released |
| FREE after write completion | Transfer done, reuse allowed; durability not implied |
| Cancelling/error drain | Stop new submits; keep buffers/tokens alive until both ports confirm quiescence |

Maximum outstanding: one read per source device and one write per destination,
two buffers total. No unbounded queue; lack of a free buffer is backpressure, not
permission to overwrite. Distinct controller/bus resources are required to obtain
physical overlap. Alignment is at least block and target DMA/cache-line compatible,
with caller-supplied padded regions on isolated cache lines. Source read completion
must include visibility/cache invalidation; destination submit requires completed CPU
writes/cache clean; quiescence includes no remaining DMA references.

The port must guarantee eventual completion or acknowledged quiescence, with target stall/timeout policy owned by the caller. A submit rejection transfers no ownership and schedules no I/O. A completion identifies
its token/extent and success or error exactly once. Until a port can report a reliable
partial prefix, any short read/write is whole-request failure: never advance from
untrusted partial PCM and never report success from a partial destination write.
Even failed writes may have persisted any subset. Late errors latch to the operation;
completion polling/reuse cannot erase them. Destination removal cancels/drains both
requests before return, buffer release or unmount. Destination-only errors leave
source rate/position/ring untouched; source read errors likewise do not invent a
source write fault. Own-device write/flush errors retain FAULTED quarantine.
Internal cancellation is teardown, not a newly authorized child-visible cancel control.

Block budget is charged once at submit for every requested source/destination block;
outstanding work cannot be submitted beyond the current call's budget. Completion
does not charge twice. Small-budget continuations preserve pending read/write state
and progress. Waiting-for-completion sets more_work truthfully; the caller uses
port events/waits rather than an engine clock or a busy loop. PM must explicitly
amend §9.1 for operations pending across calls and for termination/quiescence before
the source instance becomes callable/unmountable again. Concurrent source playback
reads take priority when coverage is low; share the source controller through bounded
arbitration and never overwrite its play ring. Do not pause/mute playback silently.

The existing synchronous callback always returns only when its buffer is safe;
never return early from it as a surrogate submit. Flush/finalization drains all
applicable writes and then executes the actual media barrier. Progress must distinguish
accepted, transferred, durable and committed; callback block counts are work counts,
not a saved/success indication. Keep the current WIP/invalidation, entries/header,
mirror/primary and identity-last stages. No valid identity publication until every
required payload/metadata predecessor is durable. No raw-destructive outcome change
is needed for batching/overlap.

### Event model and time budget

| Phase | Source controller | Destination controller |
|---|---|---|
| Fill | Read 0 into A | Idle |
| Steady 1 | Read 1 into B | Write 0 from A |
| Steady 2, only after both completions | Read 2 into A | Write 1 from B |
| Drain | Idle | Write final READY buffer |
| Finalize | Source playback remains serviced | Drain writes, barriers, metadata/identity publication per protocol |

If one leg completes early, it waits for safe swap; this conservative two-buffer
schedule already overlaps. A delayed-device test must hold Write 0 incomplete,
observe Read 1 submitted before Write 0 completes, and detect premature reuse,
late/partial failures, cancellation races and fallback. MB/s or DMA flags cannot
substitute for this causal trace.

For S=635.04 MB (decimal payload), excluding padding/metadata:
serial ≥ S/R + S/W; two-buffer pipeline approximately
max(S/R,S/W) + min(Q/R,Q/W), plus software/command overhead, playback, stalls and
durable finalization. Q is the buffer payload size (16 KiB in this example).

| Sustained payload rates R/W | Ideal serial | Ideal overlapped, before overhead |
|---|---:|---:|
| 50/50 MB/s | 25.402 s | 12.701 s + fill/drain correction |
| 25/25 MB/s | 50.803 s | 25.402 s + fill/drain correction |
| 50/25 MB/s | 38.102 s | 25.402 s + fill/drain correction |

At 25 MB/s the overlapped budget leaves under 4.6 s for every other cost.
For symmetric legs, serial needs >42.336 MB/s before overhead; overlap needs
>21.168 MB/s before overhead. **Acceptance remains whole-C60 <30 s on target,
through durable success.** SDR50/High Speed labels are bus plans, not payload
measurements. Host C60 round-trip timings do not prove this device-copy gate.

## 3. Recording durability is a separate contract

Prefer fuller-ring scheduling as the first low-complexity candidate, but WP11 common
rules and WP14 §4 explicitly require 1024-frame feed/service-until-done. Issue a separate
cadence change and capacity/owed-frame behavior before using it; do not hide skipped
barriers in the port. Retain zero-frame no-op, reservation-before-accept, COW and quarantine.

For a later checkpoint design, distinguish accepted/owed, transferred/reusable,
durable payload watermark and committed index. A failed late write remains attached
to the pending transaction even after the input buffer was reusable. Committed data
stays reachable; transferred fresh chunks are not advertised as saved recordings.

Recommend preserving synchronous commit by a defined bounded preparation stage:
drain remaining payload and make it durable before frames_owed clears/commit becomes
callable. Checkpoints keep outstanding dirty work bounded by a measured limit P,
not the entire recording. Entry barrier and header barrier remain in commit.
If service can release recording buffer space before durability, engine-api §7's
owed/commit eligibility and tapefs §8.1's already-durable statement need exact wording;
a separate preparation flag/API is required if the existing owed flag cannot express
both meanings truthfully. WP11/WP14 load scheduling then follows that contract.
The 97-block/two-flush commit bound is retained only if preparation does the payload
barrier first. P and background preparation latency must fit actual media stalls;
do not promise <200 ms from block counts alone or shift an unbounded flush to Stop.
If this cannot meet the existing synchronous limit/buffered-time limit, return a
blocker for a separate user-visible save-latency ruling, not a silent allowance.

Before write schedule changes, independent coverage must model arbitrary subsets
and reorderings within barrier epochs, repeated-LBA versions, partial multi-block
failure, late error/removal, failed/no-op barriers, publication before prerequisites,
and interruption/retry. Exhaust small epochs with declared reductions; sampled large
masks do not establish exhaustive C60 coverage. Existing none/all/prefix models alone
are insufficient. Dup batching has its own coverage and does not wait for recording
finalization or inherit a recording flush-count goal.

## 4. Ordered slices and verification interface

| Order / owner | Scope and prerequisite | Exit / next owner |
|---|---|---|
| 0 PM | Dispose this docs return; issue precise Phase2/A8/read envelope exception | Independently authored playback package next; no model/write dependency |
| 1 Verification → Software | Counting-device/performance and behavior cases; publication first; then one import commit and one bounded playback implementation commit | Exact-head independent disposition, authorized integration; PM records accepted engine pin |
| 2 Software #392 → Verification #146 | Resume held #390 using that issued engine pin; reconcile clean base without discarding transport/release work | Final required native C60, census, goldens/replays and direct exact-head disposition; Windows10/physical/release holds remain |
| 3 Verification → Software | Serial multi-block copy/write contract and persistence model first; synchronous shared-engine baseline | Exact transfer/barrier/error tests and independent disposition; measure baseline separately |
| 4 Verification → Software | Issued async capability/funnel/budget/quiescence contract and delayed-device package first | Shared-engine two-buffer overlap plus synchronous fallback; prove simultaneous in-flight read/write |
| Separate recording lane | Cadence first, then checkpoint/preparation only if justified and model covered | Exact frozen §7/tapefs §8/WP11 deltas; retain Stop limit or return separate ruling |
| Parked WP17/18/28 | DMA events, board/cache/controller integration and firmware scheduling | Qualified bus/card, sustained rates, stalls/underruns, durable-copy time, energy and CPU duty on target |

Verification can author independently from issued workload tables, public API calls,
device LBA/count/buffer/completion/barrier traces and exact expected PCM. Counters
must distinguish metadata/payload, requested/completed bytes, successful/failed calls,
and service/render events; reset point and excluded mount reads must be explicit.
Async observations additionally need token, buffer identity, ownership events,
outstanding depth, accepted/transferred/durable/committed markers and quiescence.
CPU/copy test observations belong to a narrowly issued test-only seam absent from
shipping binaries, with negative controls. No implementation source or this note's
code-level discussion goes into Verification's blind queue; PM sends only the issued
contract and source-independent facts.

Required causal controls include forced whole-window reread, stale-buffer reuse,
retained-ring movement, missing lookahead, budget overrun, early completion/buffer reuse,
dropped late error and barrier-before-drain. Verification owns their expectations.
No private replacement oracle is supplied here. Keep the ten goldens unchanged.

## Validation, blockers and stop

This return used connector reads of the pinned source/contracts and arithmetic review;
no engine run, benchmark, resource gate, independent disposition or physical test.
Git cloning failed in this runtime. The docs PR's own required CI is the validation
route; docs-only skipped engine jobs are not engine evidence.

Implementation blockers are precise PM issuance and independent publication; async
work additionally needs the explicit ABI/funnel contract, buffer/resource accounting,
partial/late-error semantics and persistence coverage. Target-controller concurrency,
card stall behavior and DMA placement are unmeasured target integration questions,
not reasons to delay the read fix. Hardware remains parked, fabrication/charging closed.
No purchase or physical run is assigned. No unchanged full-C60 timeout rerun is needed.

Stop after this docs-only return and close #405. Next owner is PM for scoped issuance,
then Verification for blind tests. #392/#390 retain ownership/evidence and the existing
direct handoff; nothing here accepts WP14 or advances a package rung.
