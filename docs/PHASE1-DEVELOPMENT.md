# Phase 1 — individual leads, issue-based assignments

**Michael-directed plan · 12 September 2026 UTC.**
This updates assignment delivery: complete work directions live in role-labeled
GitHub issues, not per-round files on main. The signed Phase 0 scope and all product,
coverage and safety holds remain unchanged.

| Role | Instance | Work authority |
|---|---|---|
| PM | Astra / ChatGPT Work | Spec, scope, gates, decisions and issue assignments |
| Software | Opus / Claude Code | Covered software, CI and mechanical integration |
| Hardware | Opus / separate Claude Code | Mechanics, sourcing and qualification evidence |
| Verification | Sol / separate Work chat | Independent tests, evidence disposition and acceptance |
| Surge | Grok | Miscellaneous bounded tasks primarily directed by Michael |

Use [role charters](ROLES/README.md) and [the issue workflow](ISSUE-WORKFLOW.md).
Each lead performs its own work; no subworkers. PM creates a new issue for each
lead assigned useful work in a round, applying the appropriate role label.
Not every lead must be assigned. Read open issues and their current scope updates,
carry forward work already done, return evidence in the issue, and stop at its boundary.

Michael configures issue listeners and notifies leads this transition round.
Activation can also be manual. This plan does not install or verify a listener
and does not restore the archived controller, signaling bus or dashboard.
Notifications are prompts to inspect live issue state, not new product authority.

Main remains authoritative for product spec, charters, decisions and evidence.
[STATUS](STATUS.md), [package scope](PACKAGES/README.md) and
[freeze record](PHASE0-FREEZE.md) describe facts and gates; they do not assign work.
Closed issues, Git history and historical reviews must not revive old directions.

PR #20 remains held across uncovered behavior; narrow mount evidence accepts no
allocator, running-sequence, warm/state or operation package. WP-10 completion,
WP-11 fixtures, independent hardware acceptance and card qualification remain open.
Fabrication and cell charging stay CLOSED. Only Michael approves purchases and
reserved physical/signature decisions. Issue closure is not independent acceptance.
