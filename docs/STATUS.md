# Project status

**Updated: 11 September 2026 · Owner: PM · Phase 0 scoped format/API freeze signed.**

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
| #20 engine | DRAFT-8 reconciled; 289 mount cases pass at tested commit 740c97e998c7672d9e98916102be84430993521b. Only ten engine/harness files remain in the PR; current branch 2e0e8a4b7bff42797ac37901196e5ea348b2e392 carries identical implementation. Main still has older provisional engine. | Verification dispositions raw mount observations; Software preserves untested boundary |
| VT8-001 / WP-07 | Allocation events and running sequence consumption untested independently; warm/state/operation exclusions also remain | Verification authors next tests before implementation merge |
| WP-10 / operations freeze | Infrastructure present, actual complete engine crash run not green | Verification |
| WP-11 | Runner present; fixtures absent; golden CI remains red | Verification, then Michael listens |
| Hardware | No board fabrication or cell charging; IR-015 acceptances and IR-018-16 qualification open | Hardware supplies evidence; Verification independently audits |
| Q-001 | Closed: Michael signed the exact scoped freeze on 8 September 2026 | PM recorded approval |
| WP-04 / WP-05 | Print packet ready; old card cart withdrawn | Michael prints; Hardware re-sources cheap small cards |

**New independent package acceptances: none.** Mount observations were run by Software,
not independently dispositioned. CAD checks are not measurements. Do not report all CI
green: missing WP-11 goldens are an explicit unresolved gate.

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
Leads perform their own scoped work; there are no subworkers or automatic rounds.

Read the [development plan](PHASE1-DEVELOPMENT.md), [role instructions](ROLES/README.md)
and [current briefs](REVIEW/README.md). Michael starts/resumes chats; the repo holds
assignments, decisions and evidence. This operating change grants no new package
acceptance and changes none of the product holds above.
