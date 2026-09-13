# P1-R11 PM disposition — independent playback result and clean split

**Date:** 13 September 2026 UTC  
**PM issue:** [#74](https://github.com/mmsanders/Digital-Tape/issues/74)  
**Input product main:** `d52730ffb4c9d8e634eded9caca208dcacb0d046`  
**Published P1-R10 main:** `6a8b2fb481cf43a8d84aad6c74336fc4a2a50d96`  
**Input verifier main:** `17d345ef23a9bbdb3e781f3451f4a8797a1a6f1c`

## Main ruleset repaired and P1-R10 published

Michael updated active ruleset `22084355` after the P1-R10 blocker. The required
hardware-only `print packet is printable` context is gone; the ten remaining required
contexts are emitted by the all-PR engine workflow. Strict latest-main testing is now
enabled. Pull requests, resolved conversations, no deletion and no force-push remain;
zero approvals and no bypass actors preserve the current individual-lead workflow.

PM rechecked PR #73 at exact head
`0aa8940e60359924179cf51cd9af30c39701103a`: all ten required contexts passed,
the expected missing-WP-11-golden job remained red and unrequired, main had not moved,
and GitHub reported the PR mergeable. PR #73 then merged normally at
`6a8b2fb481cf43a8d84aad6c74336fc4a2a50d96`. The P1-R10 disposition, ADR-144,
current workflow and dashboard are therefore durable on main. No bypass or setting
change was made by PM.

## Verification return accepted at its exact boundary

Verification issue
[#9](https://github.com/mmsanders/digital-tape-verification/issues/9) published one
new finding file at verifier commit
`17d345ef23a9bbdb3e781f3451f4a8797a1a6f1c`; its sole parent is the assigned
verifier input `62b18deb8b4fbe6e797b00d792ee9f46ac0a8059`. No verifier test, oracle,
fixture, candidate or workflow changed.

The independent report authenticates product evidence commit
`c18aa42579ef7c5ea92a4d70972d6a2daa6698bb`, evidence tree
`34bad4611b6849ed586c7ec701fa7ddafef0cb12`, and sole pre-run parent
`5f44b97fe9fb3342fce3b58236a75ea27b4898a6`. PM independently recomputed the
manifest, observation and result SHA-256 values as `02900981...5461`,
`24a35a3c...7ce4` and `1fb3437a...f742`, and reran the corrected package's
unmodified replay against the committed bundle; it passes.

Accept Verification's narrow disposition: the exact raw product observations for
`empty_zero`, `empty_nonzero`, `nonempty_zero`, `one_intmax`, `reverse_zero`,
`intmin`, `scrub_forward`, `scrub_reverse`, `side_playing` and `side_idle` are
independently accepted. All seven PCM-bearing families are byte-exact, with the
recorded 1, 1, 2, 88,200, 88,200, 2 and 1 frame counts. This is independent
acceptance of those observations only. It is not source review, implementation-wide
or WP-08 completion, merge authority, a WP-11 golden, or human listening.

## Next integration boundary

PR #64 cannot merge: its branch contains broad held #20 history and files outside the
accepted playback boundary. Software issue
[#75](https://github.com/mmsanders/Digital-Tape/issues/75) therefore owns a fresh,
clean, draft candidate from published main. It must isolate only the dependency-complete
playback/status/side-switch slice exercised by the accepted observations, preserve
accepted bytes where possible, exclude uncovered behavior, and stop if the boundary
cannot be isolated. A new pre-run commit and immutable product bundle are required so
independent Verification can disposition the exact clean integration candidate before
any implementation merge.

Verification, Hardware, Surge and Michael receive no new issue this round. Candidate
PCM remains unlistened and WP-11 stays red; PM will not wake Michael without an exact
ready listening task. PR #20 and PR #64 remain draft and held. Frozen hashes,
test-first order, uncovered recording/crash/warm-start/state/operation work,
purchases, card qualification, fabrication and charging holds remain unchanged.
