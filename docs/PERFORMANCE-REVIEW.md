# Performance review — revised PM recommendation

**7 October 2026 UTC · PM #384 · intake #402 · discussion #399**  
**Status: design recommendation, not a normative issuance or implementation assignment.**

**7 October follow-up (ADR-168): Michael rejected relaxing the <30 s copy requirement.**
The copy-limit option below is withdrawn, not queued. The [software framework](PERFORMANCE-PLAN.md)
now prioritizes urgent playback recovery, contiguous transfers and actual read/write overlap.

This supersedes the remedy proposal in ADR-166 / #399, not its operational holds.
Protecting committed recordings does not require the observed playback rereads.
The stronger plan is to fix byte amplification, request amplification and CPU work
together, then separately simplify the write schedule and reconsider costly product limits.

## Evidence and limits

Input Product main: `d3f1e7bc20e87f7b3143b68a094459706f5930e9`.
Software #390: `dbe6283dd6393e615e2bc18ef4a6c81673c7efc1`, not independently disposed.
Verification publication: `56e25cc1736fdc62a6d9bc4e6cdc09d5f8cac1b2`;
`tests/wp14_r1` tree: `e1ef171ffdd7464314b4b838a7d904b1a94f5409`.

- [Corrected Software observations](https://github.com/mmsanders/digital-tape-verification/issues/146#issuecomment-6031550598):
  158,751,945 reads / about 81.3 GB per 635 MB C60 side. Native macOS and
  Server 2025 C60 still exceed 7200 s; images and native Linux pass.
- [Separate simulator counts](https://github.com/mmsanders/Digital-Tape/issues/385#issuecomment-6003622851):
  about 1.24M reads and 1.24M writes for dup; 155,048 flushes for load,
  including six promote barriers. These are not SD-card timings.
- [Verification's preflight/model review](https://github.com/mmsanders/digital-tape-verification/blob/6837102116ed94f80b8a6454713ffb1e7c076427/findings/P2-R1-WP14-PREFLIGHT-2026-10-05.md)
  identifies the missing arbitrary-subset/reordered-persistence model.
- This review uses lead observations, frozen contracts and hardware planning,
  not PM implementation review or new execution evidence. Calculated ceilings
  below are design comparisons, not measured speedups or battery-life claims.

## 1. First remedy: preserve audio, refill in bursts, avoid moving it repeatedly

Buffer reuse alone is insufficient: replacing one consumed 512-byte block on
every 128-frame callback still leaves about 1.24M small reads per C60 side.
Likewise, moving the remaining 64 KiB in RAM on every callback merely relocates
the amplification from the card to the CPU.

Prefer a circular buffer or bounded tiles with cursors. Retain valid samples,
publish completed regions safely to the interrupt-side renderer, and refill
contiguous missing regions in useful multi-block bursts when coverage falls
below a watermark. A service invocation with sufficient coverage can do no I/O;
`more_work` must truthfully describe the service contract, not cause the caller
to spin waiting for audio consumption. Do not expose one chosen tile size as a
new public-format requirement.

For illustration, PCM is 176,400 bytes/s. A C60 side contains 635,040,000 PCM
bytes. Ideal contiguous 32 KiB reads need about **19,380 calls**, versus the
observed 158,751,945. That is roughly **128× fewer bytes and 8,192× fewer calls**
in this workload before metadata, boundaries and fragmentation. It is not a
wall-time multiplier. The API already carries a block count; service budgets
remain counts of blocks, not counts of callbacks.

Retain the 128-frame regression cadence. Larger desktop render requests can
help the host but cannot establish efficiency at firmware interrupt cadence.
The shared engine should own this fix; duplicating an audio cache in every
port leaves engine work and invalidation complexity intact.

Independent coverage needs exact output plus read-byte and call-count bounds
for declared contiguous and fragmented workloads. Include small budgets,
ring wrap, seeks, side/content/mount invalidation, reverse and rate changes,
end-frame/lookahead behavior, warm-start input and render/service interleaving.
The caller's contiguous warm-start PCM descriptor must remain valid even if
the engine's internal indexing changes. No allocation, oversized buffer or
blocking renderer is licensed.

Software should also profile the common aligned 1× path: advancing an index
cursor and copying PCM can avoid repeated mapping searches and fractional
arithmetic where the exact formula reduces to a copy. This is a candidate
optimization, not a claim that current code performs those searches.
Fractional/reverse paths and every golden must remain exact.

**Dependency correction to the earlier recommendation:** this read-only fix
does not wait for the expanded write-persistence campaign. It does require
independent tests before engine implementation, a narrow Phase 2/A8 exception,
and disposition of the changed engine before the WP14 candidate can rely on it.

## 2. Write efficiency: distinguish buffer completion from durable publication

The earlier fuller-record-ring proposal is useful but under-aims. More bytes per
drain could reduce roughly 155k flushes to roughly 9.7k. A better candidate is to
make durability barriers follow transactions or bounded checkpoints, rather
than every small buffer drain.

Ordinary recording writes fresh chunks; the committed index still names the
old recording. Flushing those fresh chunks repeatedly does **not** make an
unfinished recording recoverable: no committed index names it.
[tapefs §7–8](../spec/tapefs-v1.md#7-ownership-reference-and-allocation) already provides the useful
separation: payload before durable entries before durable header publication.

Model four different events explicitly: accepted by the engine, transferred
so the caller's buffer is reusable, durable on the medium, and committed into
the selected recording. Never return transfer success while DMA still owns
a caller buffer, and never return flush success before its real barrier.

Candidate design: stream fresh payload, establish its durability at finalization
(with bounded background checkpoints if needed), then preserve the entry and
header barriers. Report saved only after the final barrier. An ordinary
transaction can conceptually use one payload barrier plus the two metadata
barriers, rather than one payload barrier per drain. Error quarantine,
zero-frame no-op, capacity reservation, Side A ownership and source-slot
NULL-write binding stay intact.

This needs an explicit contract treatment. Currently engine-api §7.1 and
tapefs §8.1 say all payload is durable before commit is callable, with exactly
two commit flushes. Either a defined preparation stage preserves that split,
or finalization/commit semantics change. The port must not silently discard
engine-requested flushes. No exact new flush count is promised for load,
promote, repair or interrupted-operation recovery.

**Do not move an unbounded wait to the Stop button.** Firmware acceptance
requires synchronous commit below 200 ms and below the ring's buffered time.
A huge host dirty backlog, slow SD busy interval or late error can defeat that
even when the number of writes is bounded. First examine bounded checkpoints
and finalization scheduling. If that is insufficient, explicitly consider a
short visible “saving” interval with asynchronous finalization; that relaxes
save latency/API behavior, not the success guarantee. It is optional and
unissued, not an assumed one-second allowance.

SD and host benefits differ. Host full-durability calls can be expensive;
an SD write may already wait through required card-busy periods. Firmware
must obey those periods, and flush elimination alone may save little there.
Multi-block transfers and fewer command/stop cycles still deserve measurement.
Use engine-visible contiguous runs rather than a hidden write-back port with
another ownership, ordering and error state machine.

**The persistence-model gap is present already.** Sequential host calls do not
prove sequential durable arrival. None/all/prefix modes cannot justify all
unflushed subsets even without new coalescing. Preserve existing bounded
acceptance, but do not present it as proof of the omitted space. Before changing
write scheduling, Verification needs a bounded independent model covering
arbitrary persistence subsets, repeated-LBA versions, partial multi-block and
late failures, dropped barriers, identity-before-data and multiple interruptions.
Use exhaustive small epochs plus justified equivalence reductions and declared
large-case masks; do not claim sampled masks exhaust a full C60's combinations.

## 3. Hardware and battery: stop unnecessary work, then let the CPU wait

The planned board is RT1062 at up to 600 MHz, with two USDHC controllers and
I²S audio. [#379 / the package roadmap](PACKAGES/README.md) makes SDR50 the
primary path and High Speed the fallback; older board prose has not yet been
revised because Hardware is parked.

NXP documents USDHC ADMA and interrupt completion. Its blocking transfer
function polls status flags: “using DMA” alone does not mean the CPU sleeps.
A synchronous engine callback can start DMA, wait on an interrupt/event with
the CPU idle, and return only when data/buffer ownership is safe. This can
preserve the callback ABI; pipelining both cards is a separate architectural
choice. Audit DMA-accessible memory, cache-line alignment and ownership, and
clean/invalidate correctly with the selected SDK. Cache maintenance must not
race the renderer or touch unrelated dirty data on shared cache lines.
[NXP USDHC driver](https://mcuxpresso.nxp.com/api_doc/dev/1336/group__usdhc.html);
[NXP AN12042](https://www.nxp.com/docs/en/application-note/AN12042.pdf).

Prefer I²S DMA with bounded audio interrupts, background service driven by
buffer coverage, and idle waits between useful bursts. Measure the lowest
clock that meets worst-case deadlines, then boost only when necessary.
NXP's RT1060 power guidance describes WFI/System Idle and clock reduction;
its example low-power configurations can disable clocks audio needs.
Preserve the active audio/SD clock tree rather than copying a mode blindly.
[NXP AN12245](https://www.nxp.com/docs/en/application-note/AN12245.pdf).

The ring's time coverage is **rate-dependent**: 64 KiB gives about 372 ms at
1×, but only **31 ms at the specified 12× scrub**. A half-ring refill threshold
then leaves about 15.5 ms. Average MB/s says nothing about meeting that deadline
during card busy periods or concurrent copy/record activity. Choose burst size,
headroom and arbitration from measured worst-case latency. A larger permitted
caller-owned buffer may help; a reduced scrub ceiling would be a separate
product/golden change, not the first remedy.

The current thermal model estimates 363 mW for the MCU out of 740 mW playback
loads, plus 149 mW for the source card. These are estimates, not measurements.
They justify investigating CPU/SD duty cycle, not a battery-life multiplier.
On hardware resume measure playback energy/hour, copy joules/C60, active CPU
and SD time, worst service latency, minimum buffered time and underruns.
Race-to-idle versus a slower clock is an energy measurement, not a slogan.

Two parked reconciliation points: the thermal model assumes muted audio during
copy while engine-api §10 preserves playback; and firmware resume checkpoints
must avoid a physical flash erase on every state change. Preserve the current
logical checkpoint policy while considering wear-leveled append records.
Do not reopen Hardware, buy parts, alter the generated thermal table or claim
card qualification from this paper review.

## 4. Small relaxations worth considering

| Candidate | What changes | Benefit and cost |
|---|---|---|
| Copy-time relaxation — WITHDRAWN by Michael, ADR-168 | <30 s target-system acceptance remains mandatory | Improve transfer shape and overlap; measure before proposing any future requirement change |
| Recording durability follows bounded checkpoints/finalization | Internal service/commit contract; a visible save delay only if separately chosen | Far fewer barriers while retaining saved-data recovery; finalization latency and late-error handling must be bounded |
| Format/dup can invalidate the explicitly chosen destination immediately after refusal checks | Raw destructive crash outcomes and some diagnostics; ordinary recording protection unchanged | Removes much old-generation/WIP classification; interrupted destination can be unformatted and require retry |
| Lower scrub maximum or pause playback during copy | Child-visible behavior and goldens/acceptance | Potential deadline/scheduling relief, but not recommended before efficient buffering and measurement |

**Copy arithmetic needs correction before choosing an architecture.** With
synchronous read-then-write and no overlap, minimum time is
`S/read_rate + S/write_rate`, not `S/min(read_rate, write_rate)`.
At 25 MB/s each, 635,040,000 bytes takes **at least 50.8 s**; at 50 MB/s each,
**25.4 s**, before metadata, padding, barriers and overhead.
Actual High Speed/SDR50 payload rates will be lower than bus ceilings.
Two truly overlapping controllers can approach the slower leg instead, but
require buffers, completion/error handling and safe arbitration; adding DMA
to sequential callbacks does not create overlap. Existing roughly 29-second
High Speed projections need that overlap assumption made explicit.
SDR50 remains the current hardware choice unless deliberately revised.

**A simpler destructive protocol deserves a small proof before implementation.**
After alias, writability, geometry and capacity refusals have all passed with
zero writes, invalidate both destination identity blocks and make that
invalidation durable before touching payload or metadata. Initialize fresh
metadata, including stale alternative index slots, stream the copy, and publish
fresh identity last behind the required barriers. Avoid inheriting the old
destination's generations at this new-identity boundary.

Before invalidation, the destination may still be its old state. During work
it may be unmountable; after successful publication it is the new cartridge.
For initially malformed media, diagnostic preservation would need an explicit
outcome definition too. Source data remains unchanged. The tradeoff is losing
some exact early “old destination still selectable” guarantees and WIP error
classification after a destructive command has begun. That is narrower than
weakening ordinary recording COW.

This is not yet a proven protocol. Verification must model torn invalidations,
either identity surviving, failed barriers, stale indices, publication failures
and a second interruption/retry. Existing tests change only after an issued
contract. Keep this out of the urgent read-fix tranche.

## 5. Spend fewer lead and verification cycles

Keep one shared performance envelope with exact bytes, requested bytes, request
counts and declared workloads. A stale-cache control and a forced-full-refill
control must demonstrate that correctness/performance checks can fail.
On target, add scheduling/energy observations to the existing firmware
qualification rather than creating a separate approval gate for every metric.

During development, run affected compact regressions and small crash controls
first; schedule the existing full native/C60 qualification on the meaningful
final candidate. Any CI trigger/label change is operational work for Software,
not a quiet waiver. All currently required final jobs, real detach/reattach,
both dumps, byte equality and Windows 10/physical evidence remain required.
No incomplete run is PASS and no cached image substitutes for a raw-device test.

Compact exact traces can reduce orchestration cost: counters and run-length
extents, streaming byte comparison/digests, and complete ordered failure/barrier
records. The trace contract and its tamper/completeness controls must establish
equivalence before substituting this representation. Do not drop a required
readback or reuse a previous verification result merely to reduce execution.

Issue one combined correction with clear staged dependencies rather than a PM
round for each buffer detail. Carry unaffected evidence and use direct
Software → Verification disposition. The staged recommendation is:

1. Burst playback reuse and CPU-work bounds, independent tests first.
2. Contiguous transfer and write-finalization design with the persistence model;
   select the necessary contract delta before implementation.
3. Separately decide copy-time/save-latency/destructive-destination tradeoffs.
4. Record firmware/energy implications now; execute them in their existing phase.

## Contract boundary and next decision

No TAPEFS byte-format migration is presently justified. No permission to weaken
committed-data recovery, source/refusal protection, exact audio, memory limits,
independent tests or physical qualification is proposed.

The first stage requires a scoped Phase 2 / WP14 A8 exception and performance
criteria even if public API/format bytes stay the same. Transfer shape touches
current WP14 no-batching restrictions; recording finalization touches engine-api
§7, tapefs §8 and WP11 scheduling; optional copy or raw-transaction changes
touch their precise guardrails/crash tables. Issue the actual chosen text and
new frozen manifest/approval where applicable, rather than treating this report
as authorization.

ADR-166's operational disposition stands: no repeated unchanged timeout runs,
no acceptance from incomplete native execution, #390/release/witness held,
direct #392 → #146 routing, Hardware parked. Phase 1 remains 36/36; Phase 2
remains 2/12 authored coverage, with no implemented or accepted WP14 rung.
