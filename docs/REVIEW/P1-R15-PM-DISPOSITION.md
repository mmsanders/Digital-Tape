# P1-R15 PM disposition — corrected-cadence product evidence routed independently

**Date:** 18 September 2026 UTC  
**PM issue:** [#86](https://github.com/mmsanders/Digital-Tape/issues/86)  
**Input product main:** `888f4dafcddcc4d7b96e8ec8e250dd5bb4062b63`  
**Input verifier main:** `e3a25bf3b9eda6581b5de524e5bd5fa2c032e0da`

## Software return authenticates for routing

Software issue [#83](https://github.com/mmsanders/Digital-Tape/issues/83) completed
both ordered P1-R14 phases. Phase A merged PR #85 at product main
`888f4dafcddcc4d7b96e8ec8e250dd5bb4062b63`; the imported
`tests/playback_complete_draft8/` tree is exactly the corrected verifier publication
`467a34bb0a84672c5bdef9059f2dd326d6435eb6`. Structural Rule 1 therefore remains
test-first.

Held draft PR #77 is now `b252b536574c777d2998e5a79aac66c6a73fe21b`.
Its ancestry-sync commit `5b8d62938a0ed5010fac658235de110ffadfbd0c`
preserves the prior clean split and current main. The recorded pre-run commit/tree are
`b94ee2e33fd7fb8f6691e76a83d2392b6717e8a7` /
`9a801f8b7e61f498e4a0459a640bc1aacf706c66`; held PR #20 and #64 heads are not
ancestors. Against PR #77's prior head, the product/probe-scope path map changes only
`tests/playback_adapter/complete_probe.c`; engine, firmware, public header, harness,
mount and test-Makefile blobs are unchanged, and allocator paths remain absent. This
is path/blob authentication, not PM source review.

Evidence commit/tree `9204512b7f3f06ce6ce202db9f1e2a92e56e8d0b` /
`78ecbe71ec38d854f77989408bd3f0b8a15fe623` has sole parent the pre-run commit.
The complete run tree is `db88b71a833f07d24c443b989998a649c0405527`;
the product-evidence tree is `365dc5e83263e9c3a16d224c986e64c7895ab5cb`.
The final PR-head commit changes only the return and run README, so the raw evidence
bytes remain anchored at the evidence commit.

PM recomputed the 30-entry manifest with no missing or extra evidence files. SHA-256:

- manifest `1e7f3aa6668ef91b652710247ac7a90ce8ebdc1d1350b483fd7b075834b07e72`;
- observation `4be2a12ca7c638ce256f6b09c2bda99a09e4fd42b63bad182491d8d084f0c7a8`;
- result `1fb3437a3fffb668ce92e3e6391f4d06d1ead07b8b24889a0264c9fe0d75f742`;
- staged verifier-package tree `2852667b98209f84143d96c5515c8819794c09f0`.

Unmodified offline replay and the complete-package self-test pass. Direct raw-record
recomputation finds, in each scrub direction, 698 renders, 698 service calls, all 698
renders immediately preceded by a completed `tape_service(1024)` call, 16 rate calls,
88,200 rendered frames and no short render. All callbacks are reads with return 0:
90,003 forward and 90,056 reverse. The seven PCM files match their verifier candidates.
These are authenticated observations, not acceptance or listening.

The mount packet has 289 records identical to the previously dispositioned clean run
after its provenance header. Its current executable hash differs. The packet binds the
exact pre-run commit, source hashes and current build, but PM does not transfer the
earlier mount disposition or accept the submitted build-reproducibility explanation.
Independent Verification must decide whether that provenance supports this narrow run.

PR-head Actions run 34803225440 has all ten required contexts green. The separate,
unrequired missing-WP-11-manifest job remains deliberately red.

## Independent disposition is the only next assignment

Verification issue
[#12](https://github.com/mmsanders/digital-tape-verification/issues/12) owns a blind
disposition of the exact raw evidence, cadence, family/PCM/callback records and mount
provenance. It must not inspect product or adapter source, Software returns, private
tests, or PR #77/#64/#20 diffs or discussions. It decides whether the product trace
cures `P1-R12-V01` and publishes its exact accepted/rejected boundary on verifier main.

No Software issue is opened for build reproducibility this round. The binary-hash
difference does not presently block playback-evidence review, and Verification's
independent provenance disposition is the next dependency. Open a later Software task
only if that return identifies a material evidence defect. No Hardware, Surge or
Michael issue is opened; Michael #49 is unchanged and non-blocking.

PR #77 stays draft and unmerged. PR #20/#64, playback acceptance, the narrow mount
boundary, frozen hashes, WP-11 red/listening, uncovered allocator/recording/crash/
warm/state/operation/performance behavior, purchases, card qualification, fabrication,
charging, safety and Michael-reserved approvals all remain held.
