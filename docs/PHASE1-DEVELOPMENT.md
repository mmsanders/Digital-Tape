# Phase 1 — individual lead chats

**Michael-directed operating plan · 11 September 2026.** This supersedes the earlier
cloud automation and lead/worker trial. The signed Phase 0 scope and all remaining
product, test-coverage and safety holds remain unchanged.

| Role | Instance | Primary work |
|---|---|---|
| PM | ChatGPT Work chat, Astra | Plan, issue spec and briefs, resolve decisions, track scope and gates |
| Software | Claude Code chat, Opus | Implement covered software, maintain CI, integrate and review/merge within authority |
| Hardware | Separate Claude Code chat, Opus | Design hardware/mechanics, source parts, prepare and analyze measurement evidence |
| Verification | Separate ChatGPT Work chat, Sol | Independently author tests, run verification, disposition findings and acceptance |
| Surge | Grok | Miscellaneous bounded tasks primarily instructed directly by Michael |

## Start a lead

Paste its [role bootstrap](ROLES/README.md) into the selected chat. Give the chat repository
access, then have it read the current main and report its role, input commit, next task
and blockers. An existing chat should reread the current agreement and abandon its old
organization instructions. Historical conversations are not required. There is no separate
worker pool, listener, routine, credential-binding exercise or automated approval step.

## Work and handoff

1. Michael starts or resumes each lead chat. PM publishes bounded assignments and their
   stop conditions in docs/REVIEW. Read FOR-MICHAEL before starting; do not repeat settled questions.
2. Each lead does its assigned work directly. Keep work small and reviewable, but do not
   spawn subworkers or treat implementation/test authorship as exceptional lead work.
3. Record results durably in repo docs, issues or PRs: input/spec hashes, exact commits,
   changed files, meaningful commands and results, unresolved findings, next owner and stop point.
4. Software integrates under the test-before-implementation rule. Verification reports
   to PM independently; PM resolves spec/test disagreements. No lead accepts its own work.
5. PM updates status and the next brief. Michael carries a link or resumes the relevant
   chat when a handoff is ready. Posting an issue or updating main does not wake a chat.

Surge returns results to Michael and identifies the responsible lead for integration.
Michael may explicitly assign repository work, but a surge task alone grants no standing
merge, normative-spec or independent acceptance authority. Escalate conflicting assignments.

Michael clarified at the P1-R1 kickoff that **not every lead needs work each round**.
PM assigns only useful bounded work; an unassigned lead waits for an explicit task.
This is not a staffing quota or a requirement to invent parallel work. Current
assignments and stop conditions are in docs/REVIEW/README.md, readable directly
from main without Michael pasting instruction files into chats.

## Product entry point

Use [STATUS](STATUS.md), [current briefs](REVIEW/README.md), [package scope](PACKAGES/README.md)
and [freeze record](PHASE0-FREEZE.md). PR #20 remains held across uncovered behaviour;
mount-only evidence does not accept allocation, sequence, warm/state or operations.
WP-10 completion and WP-11 fixtures remain open. Fabrication and charging remain CLOSED.

The [working agreement](../CLAUDE.md) defines normal authority, verification blindness,
physical safety, purchase approvals and the expired Phase 0 exception. This operating
change does not reopen frozen spec bytes or grant any package acceptance.
