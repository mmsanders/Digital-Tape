# Work directions through GitHub issues

**Michael-directed workflow · 12 September 2026 UTC.**
Issues are the single source for active work assignments. Main stores enduring role
charters, normative specifications, decisions, evidence, package definitions and
factual status. Do not keep a second current task list or per-round brief on main.

## Routing labels

| Role | Exact label | Open assignment queue |
|---|---|---|
| Software Lead | `software-lead` | [Software](https://github.com/mmsanders/Digital-Tape/issues?q=is%3Aissue%20is%3Aopen%20label%3Asoftware-lead) |
| Hardware Lead | `hardware-lead` | [Hardware](https://github.com/mmsanders/Digital-Tape/issues?q=is%3Aissue%20is%3Aopen%20label%3Ahardware-lead) |
| Verification Lead | `verification-lead` | [Verification](https://github.com/mmsanders/digital-tape-verification/issues?q=is%3Aissue%20is%3Aopen%20label%3Averification-lead) |
| Surge | `surge` | [Surge](https://github.com/mmsanders/Digital-Tape/issues?q=is%3Aissue%20is%3Aopen%20label%3Asurge) |
| Michael | `michael` | [Michael](https://github.com/mmsanders/Digital-Tape/issues?q=is%3Aissue%20is%3Aopen%20label%3Amichael) |
| PM | `pm` | [PM](https://github.com/mmsanders/Digital-Tape/issues?q=is%3Aissue%20is%3Aopen%20label%3Apm) |

These are routing labels, not model identities or GitHub user assignees. Give each
assignment one responsible-role label. Dependencies are linked issues, not extra
role labels that dispatch the same task to multiple leads. Label-only events and
GitHub author identity do not expand the role's product authority.

## PM issues the round

1. On Michael's explicit activation of a new PM round, create or refresh one open
   `pm`-labeled issue before acting. Record exact inputs, authority, bounded task,
   dependencies, holds and stop condition; post Started and final return comments,
   then close it at stop. Without that activation or an eligible PM issue, stop.
2. Decide useful bounded work and dependencies. Not every lead needs a task.
3. Create a new issue per assigned lead for that round, with the complete directions
   in its body and its role label. Use a title such as
   `[P1-R2-SW] Software Lead — <bounded outcome>`.
4. Include issuer/role, round and task ID, exact input commits/spec hashes or
   authoritative manifest, scope, dependencies, deliverables, checks/evidence,
   permissions/holds, next owner and stop condition. An immutable review link may
   provide evidence, but it must not substitute for the assignment body.
5. Do not create a no-work issue: an issue is an activation signal, not a round
   attendance record. Do not create another active copy of the same assignment.
   When superseding work, link the replacement and carry forward completed work
   and evidence. Historical reports are never fresh assignments.
6. PM/Michael scope changes must be explicit in the issue body and documented in a
   comment describing the change. A lead's progress report does not change scope.
   Unresolved conflicting instructions mean report a blocker, not choose a wider task.

## Lead picks up and returns

On manual activation or a Michael-configured notification, re-read the live issue.
Require the correct repository, matching role label, open state and authorized
bounded scope. Read comments for explicit scope changes, dependencies and prior
work. If it is closed, superseded or already returned, do not execute it again.
If dependencies are missing, report blocked and stop; do not start a polling loop.
If multiple independent issues exist, follow stated priority/dependency order;
report conflicts rather than silently combining scopes.

Fetch current main and follow the role's onboarding. Record main SHA, issue number
and update timestamp, and exact input/spec/test hashes. Post a short Started
comment so another activation can see work is in progress. There is one active
lead context per role; a label is not a lock and a duplicate event is not a second
worker assignment.

Perform only that issue's work, without subworkers. Return in an issue comment:
changes, exact output commits/PRs, meaningful commands actually run and outcomes,
immutable raw evidence, exclusions, remaining holds and next owner. Source,
fixtures and substantial reports remain versioned in the appropriate repository;
link them from the return. Mark the comment Ready for PM review or Blocked and stop.
Do not mark your own implementation independently accepted.

After posting the return, the lead closes its own issue. Closure means only that the
lead has stopped work on that bounded assignment; it does **not** mean the return is
correct, merged, accepted or independently verified. A blocked return may also be
closed once the blocker and next owner are explicit. Waiting for PM review is not
permission to rerun or start another task.

PM assesses the linked PRs, commits and evidence regardless of issue state. If a
correction or next tranche is useful, PM opens a new role-labeled issue with fresh
scope; PM does not use reopening as a substitute for a new assignment. Check success,
merge, issue closure and independent acceptance remain separate facts. Verification
signs only its documented scope. Michael closes his own resolved or superseded items.

## Activation and independence

Michael configures external listeners and will notify leads for this migration.
This repository change does not install listeners, guarantee delivery or claim a
chat has awakened. No automatic approval, delegation, old signaling bus, dashboard,
controller or subordinate worker is restored.

Keep Verification issues free of uncovered implementation source/private tests and
mixed implementation discussion. Link raw observations and verifier-owned sources;
put implementation findings in Software's issue and route spec questions to PM.
Preserve the signed freeze, test-first merge rule, all product/safety holds and
Michael's purchase/physical/final-signature authority.

## Migration record

At input main `d9bc6ebd10983711acade6d148895e78fd1a17e3`, P1-R1 work moved to
[Software #41](https://github.com/mmsanders/Digital-Tape/issues/41),
[Hardware #42](https://github.com/mmsanders/Digital-Tape/issues/42),
[Verification #3](https://github.com/mmsanders/digital-tape-verification/issues/3)
(which replaced the misrouted, closed Digital-Tape #43),
[Michael #44](https://github.com/mmsanders/Digital-Tape/issues/44), and
[PM #45](https://github.com/mmsanders/Digital-Tape/issues/45).
[Surge #46](https://github.com/mmsanders/Digital-Tape/issues/46) is a closed
not-planned record: no Surge work was invented. These are historical migration
links; query the open role queues above to determine live work.
