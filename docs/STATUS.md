# Project status

**Updated: 12 September 2026 UTC · Owner: PM · P1-R4 dashboard published; Hardware control integrated; Verification correction active; scoped Phase 0 freeze unchanged.**

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
Verification has also published a first three-family playback package at verifier
`48be424c5b5959c6e87c645a49ecc33a7026a30a`, tree
`c6c1418a016220cca216eeb42f782a09556d6020`. Its synthetic checks pass, but replay
does not yet bind the recorded adapter identity/exit and the runner replaces an
existing evidence directory. Verification #5 owns that correction; no import,
product run, listening approval or acceptance follows yet.

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
| VT8-001 / WP-07 | Exact hardened tree `4a862fa...` is on main; self-tests pass, but seek, arm, feed, service, commit and reset_side_b remain undefined and no real product run or acceptance exists | Verification #4 remains active; no Software issue |
| WP-10 / operations freeze | Infrastructure present, actual complete engine crash run not green | Verification |
| WP-11 | First three-family playback package is published independently, but its replay identity/evidence-retention correction remains open; candidate PCM is not listened to or accepted and golden CI stays red | Verification #5, then PM; Michael listening only after corrected import/product evidence is separately issued |
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

P1-R4 validation reproduced the Hardware 30-check suite and its targeted deletion
control; the real fabrication gate stayed CLOSED at exit 2 with five blockers.
Verification playback regeneration, self-tests and saved synthetic replay pass, but
PM's manifest-only relabel reproducer still passes incorrectly and is assigned in
Verification #5. Dashboard behavior tests cover pagination, PR exclusion, both issue
repositories, escaping and failed-refresh handling; Pages deployment is green.

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
