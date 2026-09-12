# Project status

**Updated: 12 September 2026 UTC · Owner: PM · Phase 1 P1-R1 kicked off; scoped Phase 0 freeze unchanged.**

## Kickoff checkpoint (assignments live in issues)

[P1-R1 review and disposition](REVIEW/P1-R1-PM-REVIEW.md) records Verification's
return at `689c41909e6bbec499aeb0243008222d7a1c9f64` and PM reproduction.
The recorded after-run is independently green for all 289 mount assertions only.
Two new operation cases are ready for diagnostic import, but review found
flush-order, illegal-I/O detection and raw-media retention gaps (P1-R1-V01–V03).
No product operation run or broader package acceptance has occurred.

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

## Held and next owner

| Work | State | Next owner |
|---|---|---|
| #20 engine | Recorded 289/289 mount observations independently dispositioned at tested commit 740c97e998c7672d9e98916102be84430993521b. PR remains draft at 2e0e8a4b7bff42797ac37901196e5ea348b2e392; main has older provisional engine. No wholesale merge. | Software / PM; see current issues |
| VT8-001 / WP-07 | Two verifier-authored operation cases at a91138667673fcf19dc9e83c9034322b982b1771; synthetic self-tests only. Baseline has P1-R1-V01–V03 gaps; no product acceptance. | Software / Verification; see current issues |
| WP-10 / operations freeze | Infrastructure present, actual complete engine crash run not green | Verification |
| WP-11 | Runner present; fixtures absent; golden CI remains red | Verification, then Michael listens |
| Hardware | No board fabrication or cell charging; IR-015 acceptances and IR-018-16 qualification open | Hardware / independent Verification; see current issues |
| Q-001 | Closed: Michael signed the exact scoped freeze on 8 September 2026 | PM recorded approval |
| WP-04 / WP-05 | Print packet ready; old card cart withdrawn | Michael / Hardware; see current issues |

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

Transition validation: [engine CI](https://github.com/mmsanders/Digital-Tape/actions/runs/34654162368)
passed the independent package self-checks, build, spec hashes, guardrails, negative
controls and scaffolding checks. Only the known missing WP-11 goldens failed. No files
under spec/, engine/, firmware/, tests/ or hardware/ changed in this transition.

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
