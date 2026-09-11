# Phase 1 organization trial

Michael commissioned this organization on 11 September 2026. It applies through Phase 1;
reassess its effectiveness at Phase 1 exit before continuing into Phase 2. This is an
organization experiment, not a product phase acceptance or a release of existing holds.

## Roster

| Role | Assigned cloud runtime | Primary work |
|---|---|---|
| PM | ChatGPT Work / Astra | Plan rounds, delegate lead packages, arbitrate, check synthesis |
| Software Lead | Claude Code / Opus | Plan, delegate narrow implementation, review and integrate |
| Hardware Lead | Claude Code / Opus | Plan, delegate narrow hardware tasks, review evidence |
| Verification Lead | ChatGPT Work / Sol | Plan independent tests, preserve blindness, check and disposition |
| Surge Lead | Grok Bot | Coordinate bounded PM packages and review worker results |
| Workers | Grok or Grok Bot | Execute small focused child tasks and return evidence |

The machine-readable assignment and binding checklist is `.github/agent-bus/phase1-roster.json`.
Individual startup manifests live in `.github/agent-bus/roles/`. The execution truth remains
runtimes.json and the receipt ledger. Desired assignments are not proof of enabled listeners.
A model unavailable on the chosen surface is a setup block, not permission to substitute.
PM round forms request frontier (Astra); Software/Hardware and Verification request strong
(Opus/Sol). For high-consequence work that requires frontier on a non-frontier provider,
block for explicit reassignment; do not reduce the recorded risk to make a claim pass.

## Delegation and result checking

Leads spend their substantive turns on planning, decomposition, coordination and checking.
A child has one objective, a parent, an allowed file/scope boundary, expected artifact or
commit, meaningful validation and clear stop conditions. Prefer one function, one defect,
one CAD feature or one tightly scoped analysis over an entire work package. Do not split
work solely to increase task count. Use the approved child budget (default 6; hard max 12).

Workers return a result link/commit, actual checks and limitations. The parent reviews the
work, records accept/rework/block disposition, closes each child and returns the batch.
A worker report is not acceptance. Leads may directly resolve a small necessary exception,
but record why delegation was unsuitable and account for the lead effort.

PM initial planning is explicitly started by Michael; it can prepare the next draft.
The current bus's automatic PM mailbox is final quiescence only, not a general planning
inbox. Each new round still requires Michael's protected environment approval.
No unattended loop starts the next round after pm-close.

Surge is now a named trial coordinator, retaining bounded PM-assigned scope and no
standing spec issuance, merge, or independent acceptance power. Product authority remains
as in CLAUDE.md; Michael's infrastructure commission grants no permanent combined role.

## Independence and worker capacity

Start with the existing worker-grok mailbox, one bound worker instance processing its
queue. Multiple tasks can wait there; it is not a provisioned multi-instance worker pool.
Add parallel worker slots only after explicit controller/identity/receipt design and tests.
The old OpenAI and Claude worker slots remain disabled reserves, not fallback providers.

A Verification worker must be independently blinded. Do not put independent oracle
creation onto a Grok worker or shared cloud computer already used for implementation.
Until isolation is demonstrated, Sol authors that work itself and delegates only safe
auxiliary work that does not compromise blindness. A typed review-service child cannot
fan out. Maintain tests-before-implementation and the held PR #20 coverage boundaries.

## Phase 1 measurement and exit review

For each round, PM records in the final issue synthesis: approved scope, task count,
accepted/reworked/blocked tasks, lead direct-work exceptions, worker/lead invocations,
provider usage where available (unknown is not zero), elapsed time, human interventions,
idle/duplicate wakeups, context leaks and any guardrail incidents. Separate model wait,
GitHub transport latency and actual work time when evidence allows.

At Phase 1 exit, compare worker first-pass quality, review burden, total usage, speed and
human effort. Recommend retain/change/stop for each role and transport. Michael decides
whether to continue, change models, add workers or revert to another organization.
Missing real-adapter proof is a rollout blocker; the successful simulated plumbing run
is supporting infrastructure evidence only.
