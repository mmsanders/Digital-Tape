# P1-R18 PM disposition — evidence audit, VT8 fixture blocker and method correction

**Date:** 19 September 2026 UTC  
**PM issue:** [#97](https://github.com/mmsanders/Digital-Tape/issues/97)  
**Input product main:** `a277ee7d52b26a5cf100b6d3bd69e2b6f6638802`  
**Input verifier main:** `62630b8a1e6dea18d8c4b22057fce06577411896`

## Independent card audit accepts arithmetic, not WP-05 A-2

Verification #13 published one findings file at verifier main
`62630b8a1e6dea18d8c4b22057fce06577411896`, tree
`3a8511cfe67d29ab78233ad56a84f7b6ce90a7aa`, blob
`713d497510a8ec33016b4d09d7ab6648e064798d` and SHA-256
`2b1dd9e8ae18419acaf1da5c22e8b1b75d8750caef9590e32689427986cd3d52`.
PM authenticated those identities and reran the full verifier suite.

Accept the narrow finding. All five immutable JSON blobs and all 95 stored rate
values reproduce: the onn control fails at 15.34 MB/s; PNY samples pass at 26.18,
25.41, 27.36 and 25.88 MB/s. This accepts the recorded path/host/reader labels,
exact minima and pass/fail arithmetic only.

The packet does **not** complete WP-05 A-2. It stores rounded rates rather than
primitive per-window byte and monotonic-time measurements, ignores `os.write()`
return counts, records no final file size, and does not prove the filled state with
capacity/free/occupancy measurements. Its analyser trusts the stored mean, and its
claimed adjacent-pair check actually uses fixed non-overlapping pairs. Exact card
identity, attribution, qualification, atomicity, production end-to-end copy and C-90
remain outside the result. Hardware must correct the measurement and analysis path
before Michael is asked for any rerun.

## Ruggedization proposal is not yet executable or auditable

Verification finds PR #92 directionally useful but rejects it as a test method.
The drop orientations, order, release, height tolerance and attitude are incomplete;
the 150 mm shake definition and manual feasibility are ambiguous; and the tumble
apparatus and counting method are missing. Torque, gap and unmate-force instruments,
baselines, thresholds and non-disturbing inspection order are unspecified. The two
negative controls are not guaranteed measured red controls. Child-safety methods do
not bind exact sourced editions/sections and operative procedures. Stage gates,
dummy equivalence, restart rules and failed-article retention are incomplete.

The owned-printer split remains only a direction. Hardware must separate position
from between-job repeatability, bind calibrated instruments and uncertainty, define
quantitative process criteria, and preserve the WP-24 matched pair, blind/full sweeps
and bed-position controls. Any rebuilt packet remains contingent on Michael's
machine-confirmed usable volume. No physical trial, fabrication or charging is
authorized. The fabrication gate remains **CLOSED**, exit 2, with five blockers.

## Draft PR #96 stops on an invalid verifier-owned fixture

Software #95 returned held draft PR
[#96](https://github.com/mmsanders/Digital-Tape/pull/96) at current head
`b26ffa02e8c6f016762689d2bad9aaa8b40b1fc1`, tree
`a1c8cad36eb3d5766c7c904bcdc8f109a5c67126`. Its evidence commit has sole parent
pre-run code commit `00008d9a44e6ed6ef8ae003609989dee2958a688`, tree
`e2cc6f3bea402988e32ee4dd382ec8c98beafd13`. Held PR #20/#64 heads are not
ancestors. The earlier Software-reported pair was withdrawn by a disclosed
force-push; only this current immutable pair is authoritative.

The unchanged verifier tree `4a862fa69ccb2fc4c9afe59c9c9161c3470f9263`
generates both VT8-001 superblocks with `nominal_length_s = 60`,
`total_chunks = 16` and 18,433 device blocks. Frozen DRAFT-8 derives 21 chunks for
60 seconds and requires at least 23,552 blocks before the reserved last block.
It also requires the stored chunk count to equal the derived count. Both fixtures
are therefore unmountable by every conforming engine. Both product cases correctly
stop at first mount with `TAPE_ERR_GEOMETRY` and zero writes; this is a verifier
package blocker, not a product failure.

The package has a second closure defect: the runner appends a nonzero-adapter error
outside the verifier result, while offline replay recomputes only the verifier check.
PM reproduced the saved-verdict mismatch for both retained failing bundles. A
verifier-owned diagnostic fixture change can make the two cases pass, but that has
no independent coverage or acceptance and cannot substitute for a principled
package correction.

PR #96 remains draft and held even after that correction. PM authenticated identity,
scope and the stop condition but did not review implementation source. Software's
return also discloses uncovered stage clearing and recording/allocation/refusal/fault
branches, and `tape_arm` currently rejects valid overwrite and overdub modes despite
the frozen Engine API. A corrected two-case run cannot establish a complete frozen
API implementation or merge readiness. The separate WP-11 missing-golden job remains
red and unrequired; no listening or golden acceptance follows.

## P1-R18 routing and unchanged holds

Independent Verification owns the verifier-only fixture and replay correction,
including controls that prove generated media satisfy frozen geometry before an
adapter can run and that nonzero adapter exits replay exactly. It must publish source
before retained synthetic evidence and stop before product import, execution or
acceptance. It remains blind to PR #96 product/adapter source.

Hardware owns corrections to the PR #87 measurement path and the PR #92 method,
without rerunning cards or conducting physical abuse tests this round. Software and
Surge receive no issue: Software waits for the corrected immutable verifier package,
and Surge has no independent tranche. Michael receives no issue or routine comment;
machine volume and new physical runs are not yet on the critical path.

Structural Rule 1, frozen DRAFT-8/WP-08 bytes, PR #20/#64/#96 holds, every explicit
VT8 exclusion, WP-11 missing-golden red/listening hold, uncovered product behavior,
card identity/atomicity/qualification, fabrication, charging, safety, wallet/physical
work and all Michael-reserved approvals remain. The dashboard stays at 13/36 rungs:
no complete implementation or package rung was newly reached.
