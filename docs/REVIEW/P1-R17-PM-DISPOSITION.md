# P1-R17 PM disposition — clean integration, card audit and ruggedization review

**Date:** 18 September 2026 UTC  
**PM issue:** [#93](https://github.com/mmsanders/Digital-Tape/issues/93)  
**Input product main:** `4e1d248b62866871613775a50ab931f4a4597a52`  
**Input verifier main:** `392d6bb9c948a5924fe18728fab04202bc8e337e`

## PR #77 is integrated at the accepted observation boundary

Software #90 synchronized the clean candidate and merged PR #77 with history
preserved. Product main `4e1d248b62866871613775a50ab931f4a4597a52`, tree
`5c8801b096632f7c0d9672713f19f3face2e8c84`, has parents `faeaf26...` and
`e0bde559...`. The recorded evidence commit `9204512b...` remains in ancestry above
the recorded pre-run code `b94ee2e3...`; all 17 exercised implementation/header/
harness blobs remain byte-identical to that pre-run commit and the accepted
product-evidence tree remains `365dc5e8...`.

Held PR #20 head `2e0e8a4b...` and PR #64 head `c18aa42...` are not ancestors.
`engine/src/alloc.c` and `tests/harness/test_alloc.c` remain absent. Frozen DRAFT-8
and all verifier package trees are unchanged. The ten required contexts were green
at the integrated head; the separate missing-WP-11-golden job remained red, visible
and unrequired.

Accept the integration topology, identity and scope. Do not widen the independent
result: Verification accepted the exact ten corrected-cadence playback observations
and exact 289 mount records, not source/helper design, a complete WP-06/WP-08
implementation, listening, goldens or package acceptance. The partial integration
does not reach the dashboard's complete-implementation rung.

## PR #87 is ready for independent evidence audit

Hardware #91 corrected PR #87 to head
`c0e6a83ae44c2370288594b75915a214ba25deb7`, tree
`4421e11258690936f02734c176589ff0c3dad826`. Its five raw JSON blobs are unchanged
from the submitted physical runs. PM reran `analyse.py`; it recomputed the stored
verdicts from every raw window and reproduced the recorded 15.34 MB/s onn-control
failure and 25.41–27.36 MB/s PNY results. The 80%-filled PNY observation clears the
23.3 MB/s screening bar at 27.36 MB/s. The record now separates measured facts,
hypotheses and exclusions and no longer claims that the data are fit to proceed.

Route those exact bytes for independent audit. The audit can accept or reject only
the recorded path/sample observations and derivation. Manufacturer part number,
revision, per-sample CID and order provenance remain absent; host caching, ambient
conditions and reader temperature were not measured. One reader/host path cannot
attribute speed to the card. Card qualification, exact-SKU binding, atomicity,
production end-to-end copy and C-90 remain outside the packet.

## PR #92 is a reviewable proposal, not an accepted protocol

Hardware #91 also returned draft PR #92 at
`7b8063182e0a335c1f8e3e9dfabfefe79e74fbc4`, tree
`bedb241e712d18097d64f71da4022fe254ebcfa7`. It adds a player-wide failure-mode/
mitigation matrix, proposed staged drop and rough-play methods, negative controls,
an owned-printer process baseline and a retained fail-open control for the hardware
spec manifest. PM reproduced `make -C hardware check`. PM also reproduced the real
fabrication gate as **CLOSED, exit 2, with five blockers**.

The proposal is directionally suitable for the ruggedization design input, but its
method is not accepted yet. Independent review must challenge the rationale and
repeatability of the 1.0 m concrete drop family; orientation selection and cumulative
ordering; the definition and feasibility of the 3 Hz, 150 mm hand-shake; two-unit
screening boundary; tumble method; torque/unmate-force baselines; the sensitivity of
both negative controls; and the provenance and internal-use framing of sharp-edge,
sharp-point and small-parts criteria. No live-cell destructive test is authorized.

The old combined WP04-01 plate has a 228 x 119 mm part extent and declares a
240 x 131 mm minimum bed including clearance. PM approves Hardware's **split-plate
direction** only: keep all WP-24 bases and matching lids together on one plate and
place the WP-04 button experiment on another. Execution remains contingent on the
machine's actual usable build volume being recorded. A rebuild must preserve the
blind map, full sweep, bed-position controls, source generation and packet gates;
it creates a new packet revision and is not itself permission to print. Hardware is
not activated this round because independent criteria review is the next dependency.

## Next routed work and preserved holds

Verification receives one issue in `mmsanders/digital-tape-verification`: independently
audit the exact PR #87 card packet and review the exact PR #92 ruggedization/process
proposal, publishing findings on verifier main without editing or merging product.

Software receives one held implementation/evidence issue for the two cases already
covered by `tests/ops_draft8/`: `VT8-001-RB-ALLSLOT` and
`VT8-001-REC-ALLOCSEQ`. It may implement only the public-operation/dependency slice
needed by those cases on current main, run the unchanged product adapter and publish
raw replayable evidence. It must stop before merge for independent disposition. No
stubs, verifier-test changes, private observation hooks or imports from held PR #20/
#64 are licensed.

No Hardware, Surge or Michael issue is opened. Missing card identity and machine
facts do not block the independent reviews or the software tranche, so Michael #49
is not refreshed.

Structural Rule 1, frozen DRAFT-8/WP-08 bytes, PR #20/#64 holds, every explicit
VT8 exclusion, WP-11 missing-golden red/listening hold, card atomicity/qualification,
fabrication, charging, safety, wallet/physical work and all Michael-reserved approvals
remain. The dashboard remains 13/36 rungs: no complete implementation or package rung
was newly reached.
