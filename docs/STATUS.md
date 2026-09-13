# Project status

**Updated: 13 September 2026 UTC · Owner: PM · P1-R7 complete playback verifier tranche authenticated; held product evidence needs exact-head correction; scoped Phase 0 freeze unchanged.**

## Current checkpoint (assignments live in issues)

[P1-R1 review and disposition](REVIEW/P1-R1-PM-REVIEW.md) records Verification's
return at `689c41909e6bbec499aeb0243008222d7a1c9f64` and PM reproduction.
The recorded after-run is independently green for all 289 mount assertions only.
Verification resolved the flush-order, whole-trace and raw-media/replay findings in
verifier main `7ca24853ed32ddd327461594a31021cba4a408f3`; the hardened source tree
`4a862fa69ccb2fc4c9afe59c9c9161c3470f9263` is integrated byte-for-byte on product
main through PR #48. Its self-tests pass, but it has not run against the real engine:
six operations remain undefined, so no product observation or broader package
acceptance has occurred. See the [P1-R3 disposition](REVIEW/P1-R3-PM-DISPOSITION.md).
Verification corrected the first three-family playback package at verifier
`7a22cbb4447c40c51b7c8b2282a685ed30a46ba6`. Its source commit/tree is
`d565403907ecea331a5dcf63efbd1c08d8bd732e` /
`aaa6dde86c9a0bdffa2b375361049ac670e26467`; the complete published subtree with
saved synthetic evidence is `ff810814dbc8079c6903e6f85ed7ee312abd3076`.
PM reproduced its corrected identity, exit, timeout, tamper and retention controls.
Software merged PR #60 at `4517db7efba0d1a0933fc0dda1a607c5441197b7`,
placing that exact subtree and the product-side adapter/CI diagnostics on main without
engine changes. PM authenticated the import and package checks but did not review
adapter code. Software then opened held draft PR #64 at
`3dc5abb85e5b30200cf1553b9a06a83bc83c6d36`; its three-family product bundle
replays and PM reproduced the result, but the durable packet misidentifies the
pre-implementation merge `c108356...` as the candidate and records two different
engine-archive hashes. The observation is therefore not yet ready for independent
candidate disposition.
Verification #6 correctly stopped on the absent “exact” scrub table; PM has now
issued that deterministic vector in [WP-08](PACKAGES/WP-08.md). No listening,
PCM/WP-08/WP-11 or engine acceptance follows. See the
[P1-R6 disposition](REVIEW/P1-R6-PM-DISPOSITION.md). Verification #7 subsequently
published the complete ten-family sibling at verifier `121f5f7ab03c9ce08c38329e518c49a1ca9b65a5`;
PM authenticated its source and saved-evidence trees and reproduced its full suite.
It awaits exact product import. See the [P1-R7 disposition](REVIEW/P1-R7-PM-DISPOSITION.md).

Active assignments and their stop conditions are tracked exclusively in
[role-labeled issues](ISSUE-WORKFLOW.md). This status records evidence, not work
directions. The kickoff granted no engine merge or broader acceptance.

## Published

- DRAFT-8 issued verbatim through **#25**, main commit 5e92f4085b40d55ea605267b6ce8e0e2c997053c.
  Independent paper review: zero blockers, zero majors, one non-blocking wording question.
- Independent mount package landed test-first through **#27**, main commit
  dd49015d9a6c843489a81217be9f510748099248: 289 cases, ten package self-checks reproduced.
- Hardware **#18** merged at 3287235d3d9b17373762852ee3d2ad9a9529d98d.
  Fabrication Make gate now fails closed; packet rebuild no longer drifts with the date.
  Hardware CI passed all three jobs. This is engineering work, not safety qualification.
- Cleanup **#28** merged: current authority, question queue and role briefs replace stale round instructions.
  [Freeze record](PHASE0-FREEZE.md) records Michael’s signed scope and remaining holds.
- Hardware **#47** merged at `8d9e8bdffc245d797702a2b3a461348672b0644a`.
  It binds the proposed one-shot part and indexes remaining qualification gaps;
  timing remains provisional and all fabrication/charging holds remain.
- Software **#48** merged at `5b0f891222a68848a7c94282f335368c256f902a`.
  The exact hardened verifier tree and synthetic self-check CI are integrated;
  this is integration evidence, not a real-engine run or acceptance.
- Hardware **#54** merged after Software review at
  `20aa6bbcf886d8f87b4e34c4af4afb0c091703fc`. The supply-envelope criterion now
  has a retained targeted negative control; timing and safety status are unchanged.
- The simplified read-only [lead queue](https://mmsanders.github.io/Digital-Tape/)
  is deployed from main through Pages run
  [34720715628](https://github.com/mmsanders/Digital-Tape/actions/runs/34720715628).
  It reports open role-labeled issues only and grants no work or acceptance.

## Held and next owner

| Work | State | Next owner |
|---|---|---|
| #20 engine | Recorded 289/289 mount observations independently dispositioned at tested commit 740c97e998c7672d9e98916102be84430993521b. PR remains draft at 2e0e8a4b7bff42797ac37901196e5ea348b2e392; main has older provisional engine. No wholesale merge. | Software / PM; see current issues |
| VT8-001 / WP-07 | Exact hardened tree `4a862fa...` is on main; self-tests pass, but seek, arm, feed, service, commit and reset_side_b remain undefined and no real product run or acceptance exists | Held pending covered implementation sequencing; no current Verification correction |
| WP-10 / operations freeze | Infrastructure present, actual complete engine crash run not green | Verification |
| WP-11 | Exact first playback package is on main; PR #64 retains narrow product PCM, but candidate/build provenance is inconsistent and the complete sibling is not imported. Candidate PCM is unlistened/unaccepted and golden CI stays red | Software correction/import, then independent product-observation disposition; Michael listening only after authenticated product PCM evidence |
| Hardware | PR #54 retains the targeted supply-envelope negative control; timing stays PROVISIONAL and fabrication/charging stay CLOSED with five blockers | Await exact physical/independent dependencies; no Hardware issue |
| Q-001 | Closed: Michael signed the exact scoped freeze on 8 September 2026 | PM recorded approval |
| WP-04 / WP-05 | Rev-5 plate printing, no results card yet; two-arm V30/U3 evaluation selected, no purchase/qualification | Michael; see current issue |

**New independent package acceptances: none.** Software's mount observations now
have Verification's narrow independent disposition, reproduced by PM. That is not
full WP-06/WP-07 or #20 acceptance. CAD checks are not measurements. Missing WP-11
goldens remain an explicit red gate. VR-P1-001 main-protection risk remains open;
Michael must authorize settings changes.

Risks: unqualified card atomicity, unresolved solenoid timing at the actual rail/parts,
unprinted mechanism/creep trials, and code still held by coverage. These are visible
dependencies, not evidence against the exact-byte paper review. See
[verification integration](VERIFICATION-INTEGRATION.md) and
[hardware status](STATUS-HARDWARE.md).

P1-R7 validation confirms the first verifier tree is on main exactly at
`ff810814dbc8079c6903e6f85ed7ee312abd3076`. The complete verifier source tree is
`5527547b72b3e5c6d6fb91d41f3aa3bfa86fab7d`, its complete publication subtree is
`863b3a49c421bda1bebcf1a9760149bec7051048`, and its saved synthetic evidence tree is
`c67ea8fa128e06393839f968ae3cc949d84e5f2a`; generation, 10 families, 16 new
behavioral controls, retained P1-R4 controls, offline replay and the full verifier
suite reproduce green. PR #64's retained three-family bundle also replays and a fresh
PM run at the actual head produces the same three byte-exact outcomes, but the
committed candidate/build provenance is internally inconsistent and is held for
Software correction before Verification spends a disposition round. The hand-maintained
dashboard now records WP-08 at the test-on-main rung, 13 of 36. Michael #49 remains
outside the immediate laptop critical path.

## Phase 1 operating format — 11 September

Development proceeds through individual lead chats: Astra PM in ChatGPT Work,
Sol independent Verification in Work, Opus Software and Hardware in separate Claude Code
chats. Grok provides miscellaneous surge work primarily assigned directly by Michael.
Leads perform their own scoped work without subworkers. Issue activation is
configured separately by Michael; there is no automatic product approval.

Read the [development plan](PHASE1-DEVELOPMENT.md), [role charters](ROLES/README.md)
and [issue workflow](ISSUE-WORKFLOW.md). Michael configures listeners or resumes
leads manually. Issues hold active assignments; main holds decisions and evidence.
Routing changes grant no package acceptance and change none of the product holds.
