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
Finite mapping and idle limits are issued by ADR-170 below; asymptotic notation
alone is not an acceptance gate. A source-independent test-only observation seam counts refill/adoption copy bytes,
retained-range move bytes and mapping-entry visits at their actual operations. It is
absent from shipping builds, never supplies invented values, and has causal controls.
Verification defines observation schema/controls before implementation; instrumentation
cannot change outputs or production state. Host elapsed time is diagnostic.


## Finite mapping and idle acceptance — ADR-170 / P2READ-001

**Revision 2, 7 October 2026.** Supersedes only the unspecified asymptotic mapping,
seek and idle-bookkeeping criteria. Requested-byte/callback, PCM-copy/movement,
exact-output/resource limits and the pending engine pin are unchanged.

V counts every actual playback entry inspection, including lookup, prefix/search
construction and mapping maintenance, repeated inspections included. Include work
in API calls and service/render, not only device callbacks. Count after the stated
reset; never deduct setup because it occurred outside service. E is the number of
nonempty fixture mapping runs; B is requested payload blocks (not useful blocks).
If entry inspections exceed physical mapping-run count, use the larger number of
nonempty selected-side index entries as E. Empty mappings use E=0. Arithmetic uses
wide counters; no multiplication/accumulation wrap is permitted.

| Scope / reset boundary | Finite entry-visit ceiling |
|---|---|
| Issued cold forward 1x traversal, all budgets and fragmented workload; reset after mount before first service, through final render/service | V <= 4E + 4B + 32 |
| One arbitrary tape_seek API call, including lookup/setup performed in that call | V <= 2E + 32 |
| Fixed-direction/rate episode after seek/side/rate/content/warm discontinuity, including its initiating API call and all refill/render until the next discontinuity | V <= 4E + 4B + 4F + 32 |
| Each repeated idle service after done, unchanged covered playhead, no recording or long-operation obligation | V = 0 |

F is the sum of requested render frames in the episode, including short/underrun
requests. This is an upper bound on attempted sample lookups, not an assertion
that every requested frame must render. Initial seek/setup counts in both its
per-call limit and its episode total. Reset an episode immediately before its
initiating API call. A rate-direction change starts a new episode; no global
forward traversal ceiling is imposed across arbitrary jumps. Mount selection
validation remains outside the after-mount traversal reset; later playback mapping
setup belongs inside it. A failed-read episode reports V/B/F but does not claim
the no-error traversal bound; frozen error/extent/budget semantics still govern.

The coefficients admit a bounded setup pass and repeated endpoint/extent checks
per block or attempted sample, with 32 visits for fixed edge overhead. A monotone
walker is an algorithm-independent feasibility witness, not an implementation
mandate. They are chosen before Product implementation/observations. Unlike an
unspecified constant of 4096, they reject full-index rescans on large-E workloads.
Preflight must include short and long traversals with substantial E (including
the maximum conforming fixture), budget 1 and fragmented mappings; a forced
full-scan control must exceed the issued bound on at least one declared fixture.

For the idle-service row, additionally require zero payload I/O, zero playback
PCM copy/movement, and **at most 8 executed internal loop-body iterations per call**.
Count every iteration in playback-related engine helper loops reached by that
idle service, including mapping/refill helpers; never count only loops with a
particular name or only iterations doing I/O. This does not claim a total CPU
instruction count or hardware deadline. Audit the idle path after independent
tests are authored for absence of uncounted data-dependent loops/recursion or
blocking I/O; fixed scalar checks are allowed. A test-only idle_loop_iterations
counter, causal nonzero/zero controls and shipping absence evidence supplement
the entry/copy counters. No new callback/funnel or production state is authorized.

Verification owns the final source-independent schema/cases and independently
preflights these finite inequalities; no candidate-fitted constants or elapsed-time
substitute. Its published OBSERVATION.md counter definitions are suitable, including
all intermediate copy/inspection sites, real causal increments and preprocessing/
object/link shipping absence (symbol absence alone is insufficient). A genuine
frozen-semantic/resource conflict returns to PM; do not tune expectations to code.

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

**ACCEPTED / INTEGRATED — ADR-175, 8 October PDT.** Immutable WP14 A8 engine-tree
pin: `d96b4245e04d74078f8938744b1394c3018516f7`. Independent final READ-2 PASS
[Verification PR157](https://github.com/mmsanders/Digital-Tape-Verification/pull/157)
published at `f5fc69c15291dbc40f43690866d186d106459b43` for Product #419
head `7d0f67629214cc5a41d24725d6c28cffdc59f031`; integrated by Software
at `d5c2d5ef2912662ca34d32619f6b7310169e496e`, identical reviewed root
`57c7df2159ebc80a7295a21245404186725436c8`. Complete required checks pass.

WP14 must be byte-identical to that engine tree, add no engine edits, and pass all
Phase 1 goldens/replays. No moving-main equality or port write coalescing substitutes.
This pin satisfies the playback dependency, not WP14 A8 execution or package acceptance.
Existing #392/#146 now resume meaningful final WP14 qualification against it.
All A1–A7/A9, native C60, Windows10, real-card and release holds survive.

## Separate follow-ons

Serial contiguous mutation/copy needs its own issued contract and arbitrary-subset/
reordered persistence coverage. Async overlap additionally needs an issued optional
ABI/funnel, ownership, completion/error, budget and quiescence contract with deterministic
in-flight evidence and synchronous fallback. Recording cadence/checkpoints are separate.
The Software design recommendation is retained for feasibility, not normative issuance.
Whole-C60 copy remains <30 seconds through durable success on target.
