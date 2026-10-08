# Read-optimized retained regression binding

**Issued:** 8 October 2026 PDT, ADR-172 / PM #384.
**Epoch:** `READOPT-D10-1`.
**Engine:** `d96b4245e04d74078f8938744b1394c3018516f7`.
**Audited execution:** Product #414 `a1b362268a53320e676359976593b2f01202ef13`,
root `137b69a43e8df86f921f5c4614971123c29362d1`.
**Independent authority:** [Verification #154 review](https://github.com/mmsanders/Digital-Tape-Verification/blob/a273355e8aa87b967ce66cf9f40e6a71e3ee9513/findings/P2-R1-WP14-READ2-414-2026-10-08.md),
merged `a273355e8aa87b967ce66cf9f40e6a71e3ee9513`.

## Ruling and boundary

P2READ-002 is valid: exact retained regeneration encodes the former read algorithm.
The issued playback optimization legally groups reads and removes rereads. Independent
review found every non-event field and ordered write/flush operation unchanged in
10,162 records (140 changed) across the six suites below. This permits a distinct
expected transcript binding; it does not accept Product #414 or waive a red gate.

Old accepted streams, compressed assets, hashes, build/engine pins, dispositions
and offline replay remain permanent and required. New expected streams use distinct
epoch paths and preserve their actual execution provenance. No historical pin may
be repointed or relabeled as execution/acceptance of this engine.

## Exhaustive epoch census

The raw JSONL hashes below are the independently audited expected bytes, not hashes
of normalized event-stripped comparisons. Archive/build hashes are in the review.
Other suites retain their existing bindings.

| CI suite | Preserved historical path | Cases | New raw JSONL SHA-256 |
|---|---|---:|---|
| wp06-closure-package | tests/wp06_closure_adapter/evidence/p1-r54-product | 7 | `a20201b1c4f07b1816dbadefa9a1d98a5271838d6e7a0e060a9364882209b048` |
| wp08-mapping-r56-package | tests/wp08_mapping_adapter/evidence/p1-r57-product | 62 | `b5fd5ea0c60ac816eeb133813716a80e9ffb30681cd3177b65f37131db0f7daa` |
| strengthen-r55-package | tests/strengthen_r55_adapter/evidence/p1-r56-product | 40 | `1def72c5e5b49400524c42d38a3b4d530fdf91f20b10c84528680109832a810a` |
| capacity-wp09-package | tests/capacity_wp09_adapter/evidence/p1-r53-product | 27 | `35435c591a40dbfe8bdbe261c5c2760e86280780b1c07069869ec5aa3cfaac9e` |
| history-wp09-package | tests/history_wp09_adapter/evidence/p1-r46-product | 10000 | `03ccf6174084c73af6cf681a9b8338257c85f4bd8044f9e980dc912923c1113d` |
| record-package | tests/record_adapter/evidence/p1-r25-product | 26 | `691345b23620ef83f91754f3b9a7d876cedc5547514bfcd823864d2d0a723b3c` |

## Mandatory binding checks

1. Publish an independent immutable declaration/checker on Verification main before
   Product import. Bind suite/census, old and new raw/archive hashes, frozen authority,
   adapter/build identities and truthful executed head/root/engine. Product adds new
   evidence pins with an explicit pending disposition; issuance is not acceptance.
2. Preserve required old-bundle authentication and offline behavior replay. Repeated
   execution of an old engine is unnecessary; retained bytes must remain available.
   New candidate execution regenerates the full raw stream exactly against the issued
   new hash. Never select current output as its own expected baseline, strip events,
   ignore reads, mask ordinal in raw regeneration, skip cases or use moving-main lookup.
3. The one-time epoch transition checks preserve every non-event observation field
   and ordered write/flush fact (only callback ordinal removed for that separate
   comparison). Preserve old/new full arrays and exact hashes. This diagnostic
   comparison is additional to raw equality and unchanged behavior oracles.
4. All existing behavior, write, persistence and PCM oracles, exact ten goldens,
   causal negative controls and READ-1 actual read/budget/work limits remain required.
   Independently demonstrate that wrong raw bytes, non-event/write/flush changes,
   missing cases and wrong provenance cannot obtain binding PASS.
5. Restore required accepted-binding regeneration and mutation gates. The unmutated
   baseline must pass; the benign comment mutation must survive; all seven existing
   behavior mutations must be genuinely caught. A baseline/provenance/engine-selector
   failure is not a causal behavior catch. Deliberate mutation runs may select the
   pinned unmutated epoch explicitly while retaining actual mutated-engine provenance;
   they cannot bypass a behavior oracle or conceal a failed starting baseline.
6. Ordinary epoch selection is pinned to this engine and authenticated adapter/build
   identity, fails closed on an unsupported binding and never falls back to freshly
   emitted evidence. A later engine or substantive adapter change needs a precise
   disposition; this is no general license to regenerate accepted baselines.

## Final PR execution clarification — ADR-173

P2READ-003 is resolved by explicit authority for one normal final replacement-PR
qualification ALL run, including the twelve unchanged finite member blocks and the
changed mutation member listed in ADR-173. Existing named checks, classifier, complete
matrices and lane verdicts remain required; no general qualification carriage or skip
is issued. This supersedes earlier no-repeat directions only for that final required
PR run. Selected cheap/regression and binding checks execute normally. READ-1's
already approved identity/canonical carriage and existing full-campaign guard remain;
no duplicate full READ-1 C60 or unchanged WP14 native-timeout campaign is requested.
No local duplicate campaign; retry only failed/missing necessary jobs with a reason.

## Acceptance and unchanged holds

All verifier changes precede engine changes in a clean replacement's import history.
Independent final-head disposition and all required checks green precede Software's
scoped integration. Preserve admissible READ-1 carriage with original #411 execution
identity; do not repeat unchanged full C60 for this binding correction.

READ-2 remains HELD until those gates pass. A8 remains PENDING; PM records its accepted
engine pin only after independent acceptance and integration. WP14 #392/#390,
native C60 final qualification, Windows10/physical witness, tested release/checklist,
media/hardware holds and Michael's reserved #390 merge remain. Frozen DRAFT-10,
render arithmetic, resources, write durability and <30 s target copy are unchanged.
Write/async/recording implementation remains separately unissued.
