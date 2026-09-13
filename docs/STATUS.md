# Project status

**Updated: 13 September 2026 UTC · Owner: PM · P1-R6 draft playback import authenticated; missing scrub table issued; scoped Phase 0 freeze unchanged.**

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
Software draft PR #60 now imports the complete subtree exactly and adds product-side
adapter/CI diagnostics without engine changes. PM authenticated the import and
package checks but did not review adapter code. No product run exists because current
main has a pre-DRAFT-8 header and held PR #20 lacks all four playback operations.
Verification #6 correctly stopped on the absent “exact” scrub table; PM has now
issued that deterministic vector in [WP-08](PACKAGES/WP-08.md). No listening,
PCM/WP-08/WP-11 or engine acceptance follows. See the
[P1-R6 disposition](REVIEW/P1-R6-PM-DISPOSITION.md).

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
| WP-11 | Draft PR #60 contains the exact corrected package and synthetic-only adapter diagnostic; no product PCM exists, candidate PCM is unlistened/unaccepted, and golden CI stays red | Software integration/candidate development, then independent product-observation disposition; Michael listening only after product PCM evidence |
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

P1-R6 validation reproduced draft PR #60's exact 57-file verifier subtree, playback
generation/self-test/replay, frozen-spec gate and product CI. Actions run 34725672675
has eight green jobs and only the intentionally visible missing-WP-11 golden job red.
The retained diagnostic has no product run: main fails on the old mount signature and
held #20 lacks seek, set-rate, render and service definitions. Verification #6's
schedule blocker is valid and resolved at the product-input layer by the exact WP-08
table; its test work still requires a fresh issue. Michael #49 remains outside the
immediate laptop critical path. Dashboard deployment is unchanged and green.

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
