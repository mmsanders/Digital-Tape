# P1-R13 PM disposition — mount observation accepted; playback cadence blocked

**Date:** 14 September 2026 UTC  
**PM issue:** [#80](https://github.com/mmsanders/Digital-Tape/issues/80)  
**Input product main:** `26d7cebc735b897cccec4185d75c5c64100b81fd`  
**Input verifier main:** `bc0f7ec6ba05a1e7bb7033d99922e7b739abd10d`

## Verification return authenticates and changes the playback disposition

Verification issue
[#10](https://github.com/mmsanders/digital-tape-verification/issues/10) returned one
new findings file at verifier commit
`bc0f7ec6ba05a1e7bb7033d99922e7b739abd10d`, tree
`630f4fa1e32bd1c80827d8b26b8ac0ea76194e69`, directly atop assigned input
`17d345ef23a9bbdb3e781f3451f4a8797a1a6f1c`. The file blob is
`11a499b391d38958912394e1cf37ee2b04cbd78d`. PM confirmed that it is the only
changed path and reran the full verifier suite successfully. Closure of #10 records
Verification's stop, not PM or merge acceptance.

Finding `P1-R12-V01` is valid against the frozen WP-08 text. WP-08 requires a
completed `tape_service(block_budget == 1024)` sequence before **every** scrub
render request. The exact held observation contains 698 renders in each direction,
but only the first render in each of the 16 rate rows immediately follows a completed
service sequence. PM independently counted 682 omissions in `scrub_forward` and 682
in `scrub_reverse`, with 116 and 24 total service calls respectively. The existing
oracle, self-test and replay accept that weaker once-per-row cadence, so their green
results cannot establish the assigned call vector.

The observation hash `24a35a3c...7ce4` is shared by the earlier broad and current
clean runs. Therefore the earlier ten-family playback-observation acceptance cannot
be relied on while this package defect remains. PM suspends playback advancement as
a whole rather than inventing a partial acceptance split that Verification did not
issue. No accepted implementation or package rung is removed because none had been
granted.

## Narrow mount result stands

Verification independently recomputed all 289 exact mount verdicts: 289 pass and
zero fail. The row-3 cases `M-stage-row3-side0` and `M-stage-row3-side1` return 0;
`M-stage-unmatched-row3-H-boundary` returns 8 (`TAPE_ERR_INCONSISTENT`); all three
perform zero writes, flushes and chunk reads. PM accepts this independent disposition
only for the exact recorded mount observations and the named §9.3.3 boundary.

That result does not accept `chunks.c`, the extracted helper design, allocator,
complete WP-06/WP-08, source generally or a merge. The executable hash
`57b8274e...3ed7` identifies the tested executable bytes; association with pre-run
commit `86eb3b7...` remains a separate Git/run-packet fact.

## Correct verifier first; keep the product candidate held

Verification issue
[#11](https://github.com/mmsanders/digital-tape-verification/issues/11) owns the only
new lead task. It must require a completed service sequence before every scrub render,
add named controls that reject the old cadence in both directions, deterministically
regenerate verifier-owned synthetic evidence, and publish a source-before-evidence
correction. It stops before product import or execution and may establish only
verifier-package correctness.

PR #77 remains draft and held. After PM authenticates a corrected verifier return,
Software may receive a later issue for exact mechanical import and a fresh trace;
that trace will still require a new independent disposition before merge
consideration. No Software, Hardware, Surge or Michael issue is opened now. Michael
#49 is unchanged and non-blocking, so it receives no routine comment.

Candidate PCM remains verifier-derived, unlistened and not a WP-11 golden. PR #20,
#64 and #77, frozen hashes, Structural Rule 1, deliberate WP-11 red/listening status,
uncovered allocator/recording/crash/warm/state/operation/performance behavior,
purchases, card qualification, fabrication, charging, safety and Michael-reserved
approvals remain held.
