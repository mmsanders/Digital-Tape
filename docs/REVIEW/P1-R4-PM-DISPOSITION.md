# P1-R4 PM disposition — lead queue, Hardware control and playback hold

**Date:** 12 September 2026 UTC  
**Owner:** PM under [#55](https://github.com/mmsanders/Digital-Tape/issues/55) and resumed [#57](https://github.com/mmsanders/Digital-Tape/issues/57)  
**Initial product main:** `91268789cc5a5026baa9bb7e3120671626897a74`  
**Resume product main:** `20aa6bbcf886d8f87b4e34c4af4afb0c091703fc`  
**Verifier main:** `48be424c5b5959c6e87c645a49ecc33a7026a30a`

## Dashboard publication

Michael authorized replacing the old Pages retirement/agent-dashboard surface with
Surge PR #53's simplified lead queue. PM retained its presentation and hardened its
data behavior: complete issue pagination, pull-request exclusion, both product and
Verification queues, escaped API text, bounded requests and refreshes, and an
explicit unknown state after a failed refresh. `node test-dashboard.cjs` passes.

PR #53 merged to `gh-pages` at
`69b66ed0cf9f76a45fde0a50b618debfbfbc7c23`. A first deployment was correctly
rejected because the `github-pages` environment allows only `main`. PM changed no
environment rule. The same dashboard source and a dashboard-only artifact workflow
were then published from the allowed branch at
`dfe97001c602eb3b0f2deeec0baf63af162baf02`. Pages run
[34720715628](https://github.com/mmsanders/Digital-Tape/actions/runs/34720715628)
passed, and the live URL serves `Digital Tape · Lead queue`.

The page maps open role-labeled issues to green/clear or yellow/open cards. It does
not inspect chats, wake leads, assign work or represent correctness or acceptance.
No retired signaling bus, controller, worker pool or activity inference is restored.

## Lead return disposition

Hardware PR #54 was reviewed and merged by Software at
`20aa6bbcf886d8f87b4e34c4af4afb0c091703fc`. PM reproduced the 30-check solenoid
suite, generic and supply-specific mutations, hardware spec/thermal checks and
fabrication regression. The real fabrication gate remains CLOSED at exit 2 with
five blockers. This closes the retained-control correction only; it is no safety,
measurement, part or fabrication acceptance.

Verification issue #4 published playback tree
`c6c1418a016220cca216eeb42f782a09556d6020`. PM reproduced deterministic fixture
generation, the full verifier suite and 3/3 saved synthetic replay. A manifest-only
synthetic-to-product relabel with a different adapter ID still replayed PASS; replay
also does not bind adapter exit, and the runner deletes an existing evidence
destination. Verification issue #5 owns the correction. Import, product execution,
human listening and WP-08/WP-11 acceptance remain held.

## Active work and holds

- Verification #5 is active in `digital-tape-verification`; no duplicate issue.
- Michael #49 remains active for print, card, protection and branch cleanup.
- No Hardware or Surge issue is useful after their returned work. Software receives
  no additional task after integrating #54.
- Draft PR #20, frozen specification hashes, missing accepted WP-11 goldens, card
  qualification, purchases, timing qualification, fabrication and charging holds
  remain unchanged.

