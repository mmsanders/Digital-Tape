# Playback performance addendum — P2 read-only exception

**PM issued 7 October 2026 · ADR-169 · authority PM #384 / Software #405 return.**
Applies after this publication reaches Product main. This document contains only public
requirements; it is sufficient for blind test authoring. It chooses no buffer representation.

## Scope and unchanged authority

Permit one common-engine playback read-efficiency tranche in Phase 2. Only read
buffering, refill/mapping work and necessary invalidation may change. Invalidation
in content-changing operations must not alter writes, barriers, allocation or crash
outcomes. No copy/record rewrite, async device capability, port cache, public signature,
render arithmetic, format, ring minimum or resource-limit change is authorized.
DRAFT-10 remains byte-for-byte frozen; engine-api §§6/8 remain governing behavior.
If a proposed expectation contradicts those sections, return the exact conflict to PM
before implementation. This is a supplementary performance requirement, not permission
to revise frozen service/render semantics.

Structural Rule 1 applies: independently authored tests published on Verification main,
then an import-only commit, then bounded implementation/binding. All Phase 1 replays,
ten unchanged goldens and resource/audit gates must pass. Green CI is not acceptance.
Concurrent target/ISR scheduling and hardware measurements remain parked.

## Workloads and counters

A no-error cold-mounted traversal uses a 65,536-byte play ring, forward 1×, position
zero, service-until-done before rendering 128 frames (last request may be shorter),
through exact end. Service budgets are independently tested at 1, 2, 7, 64 and 1024.
S is logical PCM bytes; N=ceil(S/512); T=ceil(S/32768); c=min(budget,64).
The payload is physically contiguous unless the fragmented workload is named.
A multi-block call must respect physical mapping/device extents and the remaining
call budget; sum callback counts, not callbacks, when checking the block budget.

Reset counters immediately after cold mount and before the first traversal service.
Classify metadata separately from chunk-data LBAs using verifier-owned fixture mappings.
Count **all requested payload blocks and callbacks**, including redundant requests;
record completed blocks, errors, service/render events and metadata separately.
A read-failure run has its own behavior expectations, not the no-error efficiency bound.
No consumer/port cache may hide requested engine I/O.

| Workload | Required maximum |
|---|---|
| Contiguous traversal at each named budget | Payload blocks N+130; callbacks T×ceil(64/c)+ceil(130/c) |
| Contiguous full C60, S=635,040,000, budget 1024 | 1,240,443 payload blocks / 635,106,816 requested bytes; 19,383 callbacks |
| Monotone fragmented traversal, E nonempty physical mapping runs, budget 1024 | Payload blocks N+2E+128; callbacks T+2E+3 |
| Repeated service after done, unchanged covered playhead, stopped or playing | No new payload reads or retained-PCM movement; finite convergence without requiring render |

The allowance covers two window/alignment edges plus interpolation lookahead.
Its request bound accounts for subdivision of the same edge allowance at small
budgets; unlike a fixed '+2 calls', it does not become inconsistent with extra
allowed blocks at budget 1. These are ceilings, not required wasted reads or required
32 KiB internal buffers. No bound overrides exact PCM, device extent or budget safety.

For contiguous and monotone forward runs, refill/adoption PCM-copy bytes must not
exceed requested payload bytes plus the accepted warm descriptor byte count (zero
for cold). Retained-range movement must be zero during ordinary monotone advancement;
one-time warm adoption is counted separately. Output stores are excluded (4 bytes/frame).
Repeated idle service has constant bounded bookkeeping. A monotone pass must visit
O(E + requested blocks) mapping entries; arbitrary seek may perform bounded O(E) lookup.
A source-independent test-only observation seam counts refill/adoption copy bytes,
retained-range move bytes and mapping-entry visits at their actual operations. It is
absent from shipping builds, never supplies invented values, and has causal controls.
Verification defines observation schema/controls before implementation; instrumentation
cannot change outputs or production state. Host elapsed time is diagnostic.

## Correctness and independent preflight

Exact frozen PCM/results/status remain required across wrap, fragmented runs, seek,
side selection (including same-side), mount/unmount, changed content, warm input,
reverse, fractional and extreme int32 rates, start/end/final frame, lookahead,
small budgets, underrun and FAULTED buffered drain. Failed/incomplete reads cannot
publish stale or incomplete samples. Render performs zero device I/O and never blocks.
Service budget 1 progresses; budget 0 retains its existing result. Service reports
done when its current obligations are satisfied; recording obligations remain unchanged.
No mandatory full-ring refill, new watermark value or reduced rate domain is issued.

Verification independently derives exact behavior/episode bounds for discontinuous
workloads; the global forward bound does not apply to arbitrary jumps. Preflight
fixtures, counter classification, budget subdivision, resource feasibility and the
service-until-done/render cadence against the frozen contract. Return a real conflict,
rather than silently loosening a bound or consulting uncovered implementation.
Include causal controls for whole-window reread, one-block large-budget transfer
amplification, stale coverage, retained-window movement, missing lookahead and budget
overrun; synthetic positives only test the harness.

## WP14 A8 and acceptance pin

WP14 may use only the separately independently accepted and integrated playback
engine tree authorized by this addendum. Until disposition, the engine pin is
**PENDING**: WP14 cannot claim A8 against a candidate engine. After acceptance,
Software reports the exact integrated engine tree and Verification's disposition;
PM records the pin here before #392's final WP14 gate. WP14 must be byte-identical
to that engine tree, add no engine edits, and pass all Phase 1 goldens/replays.
No moving-main equality or port write coalescing substitutes for this pin.
All A1–A7/A9, native C60, Windows 10, real-card and release holds survive.

## Separate follow-ons

Serial contiguous mutation/copy needs its own issued contract and arbitrary-subset/
reordered persistence coverage. Async overlap additionally needs an issued optional
ABI/funnel, ownership, completion/error, budget and quiescence contract with deterministic
in-flight evidence and synchronous fallback. Recording cadence/checkpoints are separate.
The Software design recommendation is retained for feasibility, not normative issuance.
Whole-C60 copy remains <30 seconds through durable success on target.
