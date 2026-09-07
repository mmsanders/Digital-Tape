# Digital Tape Agent Bus — staged design

> **STAGED / NOT LIVE.** This document lives on `staging/agent-bus-v1`. Nothing in this branch authorizes autonomous work. Do not create the bus labels, configure adapters, or move staged workflows into `.github/workflows/` until Michael explicitly approves activation.

## 1. What this is

The Agent Bus is a GitHub-native coordination protocol for discrete autonomous work rounds.

- **GitHub Issues are the authoritative work envelopes.**
- **Native GitHub sub-issues define parent/child work.**
- PRs are implementation/review artifacts linked from task issues; PR labels may be informative but never control the bus.
- Labels are machine state.
- Comments and PR reviews are the audit log, never triggers.

The bus is designed around two scarce resources: Michael's attention and frontier-model tokens. It therefore batches work at expensive-agent boundaries and makes every round stop at PM review until Michael authorizes another one.

## 2. Hierarchy and authority

```text
Michael
  |
  v
Program Manager — Claude Cowork
  |
  +--> Software Lead — Claude Code
  |       |
  |       +--> ChatGPT-chat / Grok workers
  |
  +--> Hardware Lead — Claude Code
  |       |
  |       +--> ChatGPT-chat / Grok workers
  |
  +--> Verification Lead — ChatGPT Work
          |
          +--> ChatGPT-chat / Grok workers where independence is preserved
```

### Hard routing rules

- PM assigns root work only to leads.
- Leads may perform high-value work themselves or delegate bounded work to workers.
- Workers return only to their **parent lead**; never to PM and never to another worker.
- Leads return root results or blocked escalations only to PM; never to Michael.
- PM does not accept ordinary queued work from agents.
- PM may act on a `round:quiescent` completion signal only to inspect, synthesize, and report to Michael.
- Only Michael may release a new round through the protected human gate.
- No agent may create new root scope during an active round.

### Narrow lateral exception: independent review

Software or Hardware may create a typed `kind:independent-review` child issue addressed to Verification when the existing Digital-Tape governance says that review is self-service. This is a **service edge, not an authority edge**: it cannot change scope, does not make Verification report to the requesting lead, and does not replace PM-owned acceptance sign-off.

If verifier-authored tests have not yet landed for new engine behavior, the Software Lead must not use this exception; its root returns to PM as blocked/finding, consistent with the existing Verification seam.

## 3. Round lifecycle

```text
PM DRAFTS
   |
   | Michael approves protected environment
   v
AUTHORIZED / ACTIVE
   |
   | leads fan out -> workers -> fan in
   v
QUIESCENT
   |
   | one PM executive synthesis
   v
CLOSED
   |
   X  no automatic restart
```

### 3.1 PM drafts before authorization

To save PM tokens, the PM does its planning **before** the human gate:

1. create one `agent-round` issue in `round:draft`;
2. prepare at most one root `agent-task` per participating lead;
3. attach those roots as native sub-issues of the round issue;
4. roots remain `state:draft`, `round:pending`, and `phase:fanout`;
5. PM stops.

The PM has therefore already issued the directions, but nothing is dispatchable yet.

### 3.2 Michael releases the round

The staged `authorize-round.yml` uses a protected GitHub Environment named `michael-round-gate`. Even if an agent triggers the workflow, the authorization job cannot run until the required human reviewer approves it.

The authorization job records bot-authored provenance, marks the round `round:authorized` + `round:active`, and releases the prepared root tasks from draft/pending to active/queued.

A manually added `round:authorized` label without the protected-workflow provenance is invalid.

### 3.3 Active round

During an active round the PM is idle. Leads and workers may work only inside the already-authorized root scope.

A lead can:

- do the assignment itself and return the root to PM;
- create worker sub-issues;
- create a permitted typed independent-review child;
- rework a child inside existing acceptance criteria, subject to cycle caps;
- return the root `to:pm state:blocked` if the lead cannot resolve something within scope.

A lead cannot turn a finding into a new root objective. That waits for Michael's next round.

### 3.4 Quiescent round

The round is quiescent when every root is returned `to:pm state:review` or `to:pm state:blocked`, and nothing below PM remains queued, working, waiting, or in protocol error.

The PM then gets **one** completion wake-up. It may:

- review the repository and round evidence;
- synthesize the lead results and blockers;
- give Michael an executive project-state summary;
- recommend the next round.

It may **not** dispatch more work in that round. The next downward wave requires a new Michael-approved round.

## 4. Task lifecycle

Task labels are declared in `.github/agent-bus/labels.yml`.

```text
DRAFT --dispatch--> QUEUED --claim--> WORKING
                                 |        |
                                 |        +--> REVIEW
                                 |        +--> BLOCKED
                                 |        +--> WAITING --fan-in barrier--> QUEUED
                                 |
                                 +--> PROTOCOL-ERROR (on invalid envelope)
```

`state:queued` is the dispatch edge. It is always added last, after the body, destination, parent and governance checks are complete.

### Claim before token spend

Every listener must:

1. fetch the issue fresh;
2. verify destination, state, parent, round authorization and route;
3. change `state:queued` -> `state:working`;
4. fetch again and confirm the claim;
5. **only then** invoke the expensive model or mutate repository state.

A persistent comment never launches work.

## 5. Fan-out / fan-in barriers

This is the main token-saving mechanism.

### Initial lead invocation

A root arrives as:

```text
agent-root
round:active
phase:fanout
to:<lead>
state:queued
```

The lead claims it once, decomposes the assignment, and creates all useful child issues in a batch. Each child is a **native GitHub sub-issue** of the root.

If children were created, the lead changes the root to `state:waiting` and goes idle.

### Worker execution

Workers independently claim their child issues and return them to their parent lead as `state:review` or `state:blocked`.

**Returning one worker must not wake the lead.**

### Fan-in release

A cheap GitHub workflow watches task-state changes. Only when all open direct children of a waiting root have returned review/blocked and none are queued/working/waiting does it release the root:

```text
state:waiting -> state:queued
phase:fanout  -> phase:fanin
```

The lead wakes once and reviews the whole batch.

If bounded rework is needed, it re-queues only the affected child tasks and returns the root to `state:waiting`. If not, it returns the root to PM.

This turns N worker completions into roughly **one** lead integration invocation rather than N lead invocations.

## 6. Token budgets and loop fuses

The machine-readable defaults live in `.github/agent-bus/protocol.yml`.

Current staged defaults:

| Resource | Default | Hard cap |
|---|---:|---:|
| Worker children per lead root | 6 | 12 |
| Rework cycles per worker child | 2 | 3 queue/claim cycles |
| Typed independent-review calls per root | 1 | 2 |

The intent is not to force every task to use six workers. The normal case should be fewer. These are fuses against accidental task explosions.

### Frontier-token policy

**Claude Cowork / PM**
- expected pattern: draft round + roots once; final executive synthesis once;
- do not use for mechanical repo inspection or implementation.

**Claude Code / Software and Hardware Leads**
- use for decomposition, architectural judgment, integration, review and merge decisions;
- batch worker delegation in fan-out;
- sleep behind the fan-in barrier instead of waking on every worker return.

**ChatGPT Work / Verification Lead**
- reserve for adversarial spec reasoning, independent test design and acceptance judgment;
- delegate mechanical evidence gathering only when independence is preserved;
- typed lateral review calls are bounded because they consume this scarce pool.

**ChatGPT chat / Grok workers**
- preferred for bounded implementation, research, debugging, mechanical edits and evidence collection.

### ChatGPT chat caveat

The protocol reserves `to:worker-chatgpt`, because that is the preferred long-term worker pool. However, an ordinary interactive ChatGPT chat does not currently give this repo a generic GitHub-triggered inbound endpoint merely by existing. The bus must not pretend otherwise.

So `to:worker-chatgpt` stays disabled until a supported adapter is configured. Grok or another callable worker can serve as the initial worker adapter if needed.

## 7. Independent Verification

The bus changes transport, not governance.

- Verification remains independent and reports to PM.
- Existing test-before-implementation ordering remains intact.
- A typed independent-review child can point at a PR, but the Issue is the bus envelope and the PR is the artifact being reviewed.
- The review result is recorded on the PR and summarized on the child issue.
- A self-service review must be refused/routed back as a finding when the current Digital-Tape rules require PM escalation.

## 8. Failure containment

### Duplicate delivery

The system assumes notifications can be delivered more than once. Execution remains safe because the issue must still be `state:queued` and successfully claimed before any model tokens are spent.

### Stale working task

Do not automatically launch a second expensive agent against a stale `state:working` task. Surface it as blocked for its parent lead.

### Illegal route

Do not execute. Mark `state:protocol-error` when permitted, explain the violated rule in a comment, and stop.

### Scope expansion

If a worker or lead discovers useful work outside the current root acceptance criteria, record it as a finding/recommendation. Do not create a new autonomous objective. PM includes it in the executive summary; Michael decides whether the next round contains it.

### Runaway cycling

Queue/claim cycles are counted from GitHub issue events. Once a child reaches the configured hard cap, it cannot be automatically re-queued. Its lead must return the root blocked or carry the unresolved item to PM review.

## 9. Why Issues, not a shared file

A shared coordination file would create merge conflicts, noisy commits, stale branch state, and poor representation of parallel work. Issues already provide stable IDs, sub-issues, labels, history and closure semantics without touching product code.

The repository's existing governance already uses Issues for PM escalation. The Agent Bus extends that pattern instead of inventing a competing transport.

## 10. Activation boundary

This branch intentionally does **not** activate anything.

Activation is a separate explicit operation after review. It should:

1. create the declared labels;
2. create the protected `michael-round-gate` GitHub Environment with Michael as required reviewer;
3. verify the human gate with a harmless dry run;
4. configure only worker/runtime adapters that truly exist;
5. move the approved staged workflows from `.github/agent-bus/workflows/` into `.github/workflows/`;
6. run protocol tests and deliberate red cases;
7. create one Round 0 draft and root tasks;
8. prove nothing runs before Michael's approval;
9. approve Round 0 manually and verify the fan-out/fan-in/PM-stop sequence;
10. only then treat the bus as live.

Merging documentation alone must never cause agent execution.