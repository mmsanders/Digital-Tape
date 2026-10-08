# READ-1 public-contract preflight — 7 October 2026

## Inputs and independence

- Live Verification #146 updated `2026-10-07T15:36:26Z`.
- Verification input main `56e25cc1736fdc62a6d9bc4e6cdc09d5f8cac1b2`.
- Product input main `1f4285177876a048d761f40bd6d843fc9428512d`.
- Public ADR-169 contract source `71fcc52e47959c58e5373997ab7ee0a34bf4e2cf`;
  underlying Product input `9e902cf04b6d0c02363870fb9bc201e40239b509`.
- Required Product AGENTS, CLAUDE, STATUS, verification charter and live issue read.
- Frozen engine-api §§3–6/8/11/12, lifecycle/warm predicates and §7.2 FAULTED
  semantics read on demand. TAPEFS §§1/2/4/5 used for geometry/mapping.
- No uncovered Product implementation, design note or private tests inspected.

## Consistent performance arithmetic

For C60, S = 635,040,000 bytes, N = ceil(S/512) = 1,240,313 blocks,
T = ceil(S/32768) = 19,380 transfer units. The issued edge allowance is 130 blocks;
the maximum requested bytes is (N+130)*512 = 635,106,816. Requested volume counts
padding and rereads, not just useful PCM. Each callback's count consumes budget;
a callback-count check alone would miss a single over-budget multi-block request.

| Budget | c | Maximum payload blocks | Maximum payload callbacks |
|---|---:|---:|---:|
| 1 | 1 | 1,240,443 | 1,240,450 |
| 2 | 2 | 1,240,443 | 620,225 |
| 7 | 7 | 1,240,443 | 193,819 |
| 64 | 64 | 1,240,443 | 19,383 |
| 1024 | 64 | 1,240,443 | 19,383 |

The ceilings need not be simultaneously attained. At budget 1 the callback ceiling
is seven above the block ceiling because each nominal 64-block transfer is subdivided
individually in the formula. That is harmless slack, not an inconsistency.

For fragmented traversal use the verifier's actual nonempty physical mapping runs E,
including discontinuities within a shared chunk. Each run contributes at most two
block-alignment edges; N+2E+128 and T+2E+3 are consistent ceilings at budget 1024.
Requests may not cross a discontinuity simply because their LBAs are contiguous.
Metadata and failures are classified separately, never deducted from service budget.

## P2READ-001 — mapping-work acceptance bound is underdetermined

The addendum requires: “A monotone pass must visit O(E + requested blocks) mapping
entries; arbitrary seek may perform bounded O(E) lookup.” It also requires constant
bounded idle bookkeeping. It specifies no coefficients or finite work ceiling.

Let B be requested payload blocks and consider a repeated full index scan costing
V = E*B visits. The frozen format permits only 0 <= E <= 4096. Therefore:

    V <= 4096*B <= 4096*(E+B).

On the valid domain this costly repeated-scan algorithm satisfies the literal
O(E+B) claim with constant 4096. So does a streaming walker with roughly E+B visits.
Even extending B without bound cannot distinguish them while E remains capped.
The same finite-domain problem affects "bounded O(E)" lookup and "constant bounded"
idle work when their constants are unspecified. Mapping counters can report work;
they cannot turn this requirement into one unique acceptance threshold.

A verifier-chosen coefficient K would reject some literally conforming linear
algorithms with larger constants. Treating such a choice as an issued requirement
would silently tighten the public contract. A few timing/scaling samples would also
not establish an unspecified asymptotic claim. This is a public-contract finding,
not an implementation finding; no candidate observations were used to derive it.

**Required PM ruling:** issue a finite mapping-visit inequality, including setup,
seek, reverse/discontinuous and repeated idle episodes, or explicitly authorize an
independently chosen finite coverage criterion with a declared acceptance boundary.
Define which work counter establishes idle bookkeeping if work beyond entry visits
is intended. Keep the existing requested-block/callback, PCM-copy, retained-movement,
exact-output and resource limits unchanged.

**Recommendation:** retain the work requirement and make it measurable. Express a
monotone ceiling as K*(E+B)+C with fixed issued K/C, a separate seek ceiling Kseek*E+Cseek,
and a per-idle-call ceiling. Include every actual entry inspection and prefix-index
search/build visit after the counter reset. No implementation-derived constants,
timeout substitute or waived CPU gate. PM may use algorithm-independent feasibility
reasoning; Software need not supply private code to this Verification context.

**Safe default:** author no numeric mapping-work verdict and grant no complete
READ-1 activation until the ruling. Preserve all existing test publications/holds.

## Behavioral and resource preflight

The 65,536-byte ring holds 16,384 stereo frames. A 128-frame render at 1x advances
512 bytes, so repeated 64 KiB whole-window rereads are observable without elapsed
time. A small-budget service loop must converge without advancing the playhead.
No public contract requires a particular ring representation or a full-ring fill.
The existing 200 KiB engine RAM, 8 KiB stack and 32 KiB rodata gates still apply;
paper capacity reasoning is not a measurement or an accepted resource result.

For reverse/fractional/extreme rates, compute positions, interpolation and flags
from frozen §§6.2/6.3/8. At INT32 extremes a 128-frame request can exceed ring coverage;
an exact served prefix followed by UNDERRUN is distinct from an endpoint shortfall.
Do not assert that service-until-done necessarily permits all 128 output frames at
every accepted rate. Nor may a test redefine done as a mandatory full-ring refill.

Discontinuous runs must be divided at seek/side/mount/content/warm invalidations.
The global forward ceiling does not apply across arbitrary jumps. For a new 1x
contiguous suffix, derive N/T from that suffix and retain the issued edge allowance;
for arbitrary-rate episodes distinguish needed sample coverage from optional prefetch.
A speculative universal numeric discontinuous bound is not implied by ring size alone.
Document any proposed additional bound for PM approval rather than fit a candidate.

Same-side selection invalidates the ring exactly like cross-side selection. Failed
reads cannot make failed destination bytes available as PCM. Write/flush failure
creates FAULTED; a read failure alone does not establish that quarantine state.
FAULTED drain must use only already valid buffered PCM, perform no device I/O and
eventually underrun. Warm validity follows the ordered descriptor predicate, including
64-bit range arithmetic, and needs sample identity checks as well as the used flag.
Content-change scenarios use unchanged public mutators and carried persistence
coverage; this read tranche cannot introduce new write outcomes.

## Census, stop condition and holds

This checkpoint contains one paper finding, five independently calculated C60 budget
rows, a proposed observation boundary, **zero executable acceptance cases**, zero
Product runs and zero Product controls. It is deliberately not the required complete
READ-1 package. Existing WP14 package `56e25cc1` and subtree
`e1ef171ffdd7464314b4b838a7d904b1a94f5409` remain untouched.

Current stop: the issue explicitly requires impossible/ambiguous expectations to be
returned to PM before code. P2READ-001 is returned for that ruling; Verification
continues READ-1 after it. No complete publication handoff or READ-2 PASS is implied.
WP14 A8 engine pin remains PENDING. Native C60, Windows 10/physical witness,
tested release/checklist, card/hardware and Michael's #390 merge holds survive.
