# P1-R8 PM disposition — complete playback import and verifier conflicts

**Date:** 13 September 2026 UTC  
**PM issue:** [#68](https://github.com/mmsanders/Digital-Tape/issues/68)  
**Input product main:** `14a593120b2400ea5baac79a3b143cd702edcdc0`  
**Input verifier main:** `121f5f7ab03c9ce08c38329e518c49a1ca9b65a5`  
**Held PR #64 head assessed:** `bc53076448112ec3015de40e71c229e17d225c2f`

## Test-first import authenticated

Software #66 merged Phase A through PR #67 at the input product-main commit. The
complete product subtree `tests/playback_complete_draft8/` is tree
`863b3a49c421bda1bebcf1a9760149bec7051048`, exactly equal to independent
Verification's published subtree at the input verifier commit. Its retained synthetic
evidence is tree `c67ea8fa128e06393839f968ae3cc949d84e5f2a`; the earlier playback
subtree remains `ff810814dbc8079c6903e6f85ed7ee312abd3076`.

PM reproduced deterministic fixture/candidate generation, the complete self-test and
the retained synthetic replay from a clean detached checkout. The full product gate
run passes build, frozen-spec integrity, guardrails, meta-gates and scaffolding; only
the already-known WP-11 missing-golden-manifest gate is red. Phase A changed no engine
or firmware file. This is exact test import and package-plumbing evidence, not product,
PCM, golden or work-package acceptance.

## Held product evidence authenticated, not accepted

Software's Phase-B tested-code commit is
`43d2dbaa6434942df37e165b25edc6d45135fee2`; it is an ancestor of the held
PR head. The retained complete product bundle is
`docs/verification/runs/2026-09-13-r7/product-evidence/`. Its manifest binds the
verifier publication/tree, tested-code commit and one build identity; PM's offline
replay reaches the unmodified oracle and returns `FAIL: tape_render.rendered`.
The verifier subtrees are unchanged on the held branch.

PM did not inspect or accept Software's implementation or adapter source. Software's
scratch-oracle isolation is diagnostic only. It reports that setting aside three
disputed expectations leaves 1,625 calls and five compared PCM families green, but
neither that scratch result nor issue closure is an independent verdict.

## Contract arbitration

All three disputes are defects in the complete verifier package. The frozen DRAFT-8
bytes and hashes remain authoritative and unchanged.

| Finding | Package expectation | Frozen DRAFT-8 requirement | PM disposition |
|---|---|---|---|
| F-1 `intmin` | Reverse from frame 1 at `INT32_MIN` renders only frame 1, then reports start | §6.2 lands on frame 0 without setting `at_start`; §6.3 emits frame 0 on the next pass, then stops. The earlier package also requires all reverse frames including frame 0. | Correct the case to `rendered = 2`, output frames 1 then 0, tell 0 and `at_start = true`. |
| F-2 reverse scrub | Candidate starts at `max_pos - 1` | §6.3 snaps to `(total_frames - 1) << 32`. V5-005 explicitly rejects `max_pos - 1` as the DRAFT-5 off-grid defect; the earlier package retains that formulation as a negative control. | Regenerate only the affected verifier-owned reverse candidate/evidence from the grid-aligned snap, with old bytes retained in history. This document is the logged PM approval for that golden-adjacent candidate regeneration; it is not golden/listening acceptance. |
| F-3 side switch | Short post-switch render returns result 6 | Frozen enum value 6 is `TAPE_ERR_GEOMETRY`; `TAPE_ERR_UNDERRUN` is 18, and §5 requires underrun while the invalidated ring is short. | Correct both side-family expectations to result 18. |

The package source itself confirms all three conflicts: `oracle.py` encodes one frame
for F-1 and result 6 for F-3, while `generate_fixture.py` uses `maxpos - 1` for F-2.
No frozen-spec ambiguity or change request exists.

## Routing and holds

Independent Verification is the only ready next owner. It receives a verifier-repo
issue to re-derive and correct exactly F-1/F-2/F-3 without inspecting product code,
PR source or Software's diagnostic oracle, retain targeted negative controls, publish
a new immutable source and evidence identity, and keep candidate PCM unlistened and
unaccepted. Software receives no issue until that corrected independent package is
published. Hardware and Surge also have no newly unblocked bounded work.

PR #20 and PR #64 remain draft and held; no implementation merge follows from this
arbitration. WP-11 remains red and human listening remains held until an authenticated
product run passes the corrected independent package and PM separately routes the PCM.
All test-weakening, synthetic relabel, frozen-spec, card purchase/qualification,
fabrication, charging and repository-setting holds remain. Michael #49 remains open
but does not block this verifier correction.
