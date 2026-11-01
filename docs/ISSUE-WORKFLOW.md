# Work directions through GitHub issues

Issues are the only source of active work assignments. Main holds role charters, specs,
decisions, evidence, package definitions and status. Don't keep a second task list or a
per-round brief on main.

## Routing labels

| Role | Label | Open queue |
|---|---|---|
| Software Lead | `software-lead` | [Software](https://github.com/mmsanders/Digital-Tape/issues?q=is%3Aissue%20is%3Aopen%20label%3Asoftware-lead) |
| Hardware Lead | `hardware-lead` | [Hardware](https://github.com/mmsanders/Digital-Tape/issues?q=is%3Aissue%20is%3Aopen%20label%3Ahardware-lead) |
| Verification Lead | `verification-lead` | [Verification](https://github.com/mmsanders/digital-tape-verification/issues?q=is%3Aissue%20is%3Aopen%20label%3Averification-lead) (in the verification repo) |
| Surge | `surge` | [Surge](https://github.com/mmsanders/Digital-Tape/issues?q=is%3Aissue%20is%3Aopen%20label%3Asurge) |
| Michael | `michael` | [Michael](https://github.com/mmsanders/Digital-Tape/issues?q=is%3Aissue%20is%3Aopen%20label%3Amichael) |
| PM | `pm` | [PM](https://github.com/mmsanders/Digital-Tape/issues?q=is%3Aissue%20is%3Aopen%20label%3Apm) |
| Inbound, no lead | `intake` | [Intake](https://github.com/mmsanders/Digital-Tape/issues?q=is%3Aissue%20is%3Aopen%20label%3Aintake) |

`intake` holds unscheduled input from Michael. It is not an assignment; see [intake](INTAKE.md).
Each assignment carries exactly one role label. Labels are routing, not model identity or
authority.

## Activation

Michael starts each issue manually. PM posts issues and sends no kickoff messages; no
listener is active. Once started, a lead may continue into the next named stage of the
same issue if that stage's input has already arrived. It never starts another issue,
polls or waits.

## PM issues a round

1. When Michael starts a PM round, PM opens one `pm` issue with inputs, authority, bounded
   task, holds and stop condition. PM posts its return there and closes it at the stop.
2. PM decides the useful work. Not every lead needs a task, and PM doesn't create no-work
   issues.
3. Each assigned lead gets its own issue with complete directions in the body:
   - inputs, with exact commits or hashes;
   - scope and stages;
   - deliverables and evidence;
   - holds;
   - next owner and stop condition.
   
   Title it like `[P3-R1-SW] Software Lead — <outcome>`.
4. A Verification publishing task stops only when its PR is merged into verification main
   (merge commit). Cite only merged commits; a PR head is a candidate (ADR-157).
5. Rounds may be pre-routed (ADR-158): Verification disposes Software's exact head
   directly, and the Software issue authorizes integrating that head once cleared.
6. Scope changes go in the issue body or a scope-update comment from PM or Michael. A
   lead's progress report doesn't change scope.
7. Before closing a PM issue, PM refreshes `site/lead-queue/index.html` from the newly
   disposed facts and runs `node test-dashboard.cjs` in that folder. Rungs move only
   when their gate is fully reached.

## Size and ordering

- Size each issue to an outcome (ADR-195), not a step. Corrections found by Verification
  stay inside the same pair of issues.
- If a candidate needs a clean base, assign it **before** independent disposition. Never
  send already-accepted evidence through another independent round because its base
  changed. Record that the disposition carries over to identical evidence.

## A lead picks up and returns

1. Re-read the live issue. It must be in the right repository, carry your role label, be
   open and be in scope. Read the comments for scope updates.
2. Closed, superseded or already returned work is not run again. Missing dependencies
   mean report blocked and stop.
3. Fetch main. Record the main SHA, issue number and exact input hashes. Post a short
   Started comment.
4. Do only that issue's work, with no subworkers.
5. Return in an issue comment, headed **[Software Lead]**, **[Verification Lead]**,
   **[Hardware Lead]** or **[PM]**, with:
   - what changed, with exact commits and PRs;
   - the commands actually run and their outcomes;
   - evidence links;
   - exclusions, remaining holds and next owner.
6. Mark the return Ready for review or Blocked. Close your own issue. Closure means you
   stopped. It doesn't mean the work is correct, merged or accepted.

**Citing CI:**
- The `engine` workflow (`ci.yml`) runs on pull requests, main pushes and manual
  dispatch. Cite the PR's `pull_request` run, which tests the head merged with current
  main.
- For an exact-head run, dispatch the workflow on the branch and cite that run.
- A docs-only PR (`docs/**` outside `docs/verification/**`, `site/**`, root `*.md`)
  skips the engine jobs. That is not engine evidence.

PM assesses linked PRs and evidence regardless of issue state, and opens a fresh issue for
any correction or next task rather than reopening. Michael closes his own items.

## Independence

- Keep Verification issues free of uncovered implementation source and implementation
  discussion. Put implementation findings in Software's issue and spec questions in a
  PM issue.
- The signed freeze, the tests-first rule, product and safety holds, and Michael's
  purchase, physical and sign-off authority survive issue routing.
