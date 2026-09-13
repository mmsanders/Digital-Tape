# P1-R12 PM disposition — clean playback/mount candidate routed independently

**Date:** 13 September 2026 UTC  
**PM issue:** [#78](https://github.com/mmsanders/Digital-Tape/issues/78)  
**Input product main:** `f1213430d10d4c0b62d173af532135daf56aca58`  
**Input verifier main:** `17d345ef23a9bbdb3e781f3451f4a8797a1a6f1c`

## Software return is a clean held candidate

Software issue [#75](https://github.com/mmsanders/Digital-Tape/issues/75) returned
draft PR [#77](https://github.com/mmsanders/Digital-Tape/pull/77) at
`f100937aed1437401218003db3edbb07d8e4f543`. Its sole parent is pre-run code
commit `86eb3b77756042c365e2d0353018b981c39c99e8`, whose sole parent is the
assigned base `6a8b2fb481cf43a8d84aad6c74336fc4a2a50d96`. The broad PR #20 and #64
heads, the earlier PR #64 head and accepted code-under-test commit are not ancestors.
PR #77 remains draft and held; issue closure is only Software's stop.

Eleven carried files have the same modes and blobs as accepted code-under-test
`5f44b97fe9fb3342fce3b58236a75ea27b4898a6`. The uncovered `alloc.c` and its
scaffolding are absent. Software isolated the one link dependency,
`tape_chunks_for_frames`, into new `engine/src/chunks.c` rather than importing the
allocator. The helper is used by the TapeFS §9.3.3 mount row-3 path represented by
the landed independent mount package. This is a reasonable held integration boundary,
not PM source review or implementation acceptance. Independent disposition of the
new exact observations remains required before Software considers a merge.

## Evidence authentication

The immutable run tree is `a6c1dfeb1e35399301adcabf5adc90ef0e067307`; its
product-evidence tree is `1671bcb37abccb21cb59234792ba35e984a3eb5f` and staged
package tree is `b097c2a91fabf55677c9a7f866020d22d83ee90e`. The source package stays
the corrected verifier tree `6dbb23bb4626238b0f22427031a551d2ece454fd`. Shared
staged files compare exactly; only verifier-only Makefile, synthetic adapter, self-test
and retained synthetic evidence are intentionally absent from the run stage.

PM recomputed all 30 manifest-bound paths with no missing or extra file. Manifest,
observation, result and mount-log SHA-256 values are respectively
`c243b1dd2aab34b817a68e7da8ebb17f5e0169aff52e1b9c7d5131ac441ba37a`,
`24a35a3cd5a8364d1909f0ee3e0a90d196b4c1afdedfb3bf9d38d34c775e7ce4`,
`1fb3437a3fffb668ce92e3e6391f4d06d1ead07b8b24889a0264c9fe0d75f742`
and `0d753bf8b54a650815402d492e2ddc4a80a49d706ed22c749698b887755319d9`.
The unmodified offline replay passes.

PM rebuilt pre-run commit `86eb3b7...` and reran both packages. The fresh complete
playback observation and result are byte-identical to the committed evidence at the
two hashes above. The mount package reports 289/289 with seed `0xd8a607`; all 289
case records are byte-identical to the committed log. Its provenance line differs
only in the expected local executable path and build hash. This is PM reproduction,
not independent acceptance.

All ten required PR #77 checks passed. The deliberate
`golden suite (awaiting WP-11 fixtures)` job remains red and unrequired.

## Independent next step

Verification issue
[#10](https://github.com/mmsanders/digital-tape-verification/issues/10) owns a blind
disposition of the exact clean playback bundle and mount log, including the named
§9.3.3 row-3 cases. Verification may inspect public contracts, verifier-owned packages,
Git identity metadata and raw evidence only—not product/adapter source, private Software
tests, the PR diff or Software's narrative. It may accept or reject exact observations,
not the source, helper design, complete packages or a merge.

No Software, Hardware, Surge or Michael issue is opened in this round. Candidate PCM
is still verifier-derived, unlistened and not a WP-11 golden, so there is no ready
Michael listening packet. No routine Michael comment or branch KEEP list is published.
PR #20, #64 and #77, frozen hashes, Structural Rule 1, uncovered allocator/recording/
crash/warm/state/operation/performance behavior, purchases, card qualification,
fabrication, charging, safety and Michael-reserved approvals remain held.
