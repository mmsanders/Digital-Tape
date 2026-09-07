# Digital Tape Agent Bus — staged design

> **STAGED / NOT LIVE.** This document lives on `staging/agent-bus-v1`. Nothing in this branch is an instruction to start autonomous work. Do not create bus labels, move staged workflows into `.github/workflows/`, or dispatch agent work until Michael explicitly authorizes activation.

## 1. Purpose

The Agent Bus is a GitHub-native coordination protocol for discrete agent work rounds. GitHub Issues and Pull Requests are the durable envelopes; labels are machine state; comments and reviews are the audit log.

The design has three goals:

1. Remove Michael from routine copying and handoff work.
2. Protect expensive frontier-model tokens by reserving PM/lead/independent-verification capacity for planning, judgment, review, and escalation rather than nitty-gritty execution.
3. Make runaway autonomous loops structurally difficult: work can cascade down and results can flow back up, but a round stops at the PM boundary and cannot restart without Michael.

## 2. Authority hierarchy

The routing hierarchy is strict:

```text
Michael
  |
  v
Program Manager (Claude Cowork)
  |
  +--> Software Lead (Claude Code)
  |       |
  |       +--> worker pool
  |
  +--> Hardware Lead (Claude Code)
  |       |
  |       +--> worker pool
  |
  +--> Verification Lead (ChatGPT Work)
          |
          +--> worker pool when delegation preserves independence
```

Worker pool, in preference order:

- `worker:chatgpt-chat` — preferred low-cost/general worker when an automatic adapter exists.
- `worker:grok` — available surge / implementation / investigation worker.
- other workers may be added later without changing the hierarchy.

### Non-negotiable routing rules

- PM may assign work only to leads.
- Leads may assign work to workers or perform it themselves.
- Workers may return work or requests only to their parent lead.
- Workers **must not** route to PM.
- Leads may return results or escalations only to PM.
- Leads **must not** route directly to Michael.
- PM may summarize and request a new round from Michael, but PM **may not accept task direction from another agent**.
- Only Michael may authorize a new PM round.
- No agent may skip a level upward or downward.

These are transport rules, not merely etiquette. The dispatcher must reject illegal transitions.

## 3. Round model

A round is a bounded unit of autonomous activity.

### 3.1 Round states

```text
DRAFT -> AUTHORIZED -> ACTIVE -> PM_REVIEW -> CLOSED
          ^                          |
          |                          v
          +------- Michael ----------+
```

- **DRAFT** — PM may prepare a proposed round plan, but nothing dispatches.
- **AUTHORIZED** — Michael has explicitly approved the round. This is the only event that permits PM-to-lead dispatch.
- **ACTIVE** — leads and workers may work, delegate, cycle locally, review, and escalate according to the hierarchy.
- **PM_REVIEW** — every root task has returned to PM; no lead or worker has queued/running work. The round is quiescent.
- **CLOSED** — PM has produced the executive summary for Michael. No automatic transition to another round exists.

### 3.2 The round barrier

A round is ready to stop when all of the following are true:

1. Every root task created by PM for that round is addressed to PM with `state:review` or is closed.
2. No issue or PR in the round has `state:queued`, `state:working`, or `state:blocked` below PM.
3. No lead has an unanswered child task outstanding.
4. No pending illegal-route or protocol-error item exists.

At that point the bus is **quiescent**. The PM may inspect the repository and issue history and produce an executive summary for Michael. It may not create or dispatch the next round until Michael explicitly authorizes it.

### 3.3 No implicit authorization

The following do **not** authorize a new round:

- closing the prior round;
- PM receiving all lead results;
- a worker suggesting follow-up work;
- a lead requesting more work;
- CI failure;
- a newly opened issue;
- a comment containing a trigger phrase;
- elapsed time;
- a scheduled listener run.

Only a Michael-originated authorization marker for the specific round ID may transition DRAFT -> AUTHORIZED.

## 4. GitHub object model

### 4.1 Work envelope

Each independently executable unit is one GitHub Issue or PR.

- Issue number / PR number is the idempotency key.
- One object has one active owner tier at a time.
- Parallel work uses child issues, never multiple simultaneous destination labels on one object.
- Comments contain context and results; comments are never execution triggers.

### 4.2 Labels

The staged label manifest is `.github/agent-bus/labels.yml`. Conceptually:

**Protocol**
- `agent-task`
- `round:<id>` (created per round or represented in issue body; implementation choice at activation)

**Destination**
- `to:pm`
- `to:software`
- `to:hardware`
- `to:verification`
- `to:worker-chatgpt`
- `to:worker-grok`

**State**
- `state:draft`
- `state:queued`
- `state:working`
- `state:review`
- `state:blocked`
- `state:protocol-error`

**Round control**
- `round:authorized`
- `round:quiescent`

Closed GitHub state means done; there is deliberately no `state:done` label.

### 4.3 Dispatch edge

`state:queued` is the bell.

To dispatch a complete envelope:

1. create/update body;
2. set exactly one destination;
3. set round ID and parent relationship;
4. perform any governance checks;
5. **last**, transition to `state:queued`.

Listeners should react to the *addition* of `state:queued` where event delivery is available. Polling listeners may search persistent queued state, but must atomically claim before doing expensive work.

### 4.4 Claim rule

Before work:

1. fetch object fresh;
2. verify it is open, `agent-task`, addressed to this agent, and `state:queued`;
3. verify route is legal for its parent;
4. verify round is ACTIVE;
5. replace `state:queued` with `state:working`;
6. fetch again and confirm claim;
7. only then spend model tokens or mutate repository state.

Never execute the same issue/PR concurrently.

## 5. Legal transitions

### 5.1 Michael / PM boundary

```text
Michael -> PM : authorize round only
PM -> Michael : executive summary / request for next-round authorization only
```

No other agent may originate `round:authorized`. PM never claims a normal `to:pm state:queued` task. Lead results arrive as `to:pm state:review`; PM reviews them only inside the current authorized round.

### 5.2 PM / lead boundary

During an authorized round:

```text
PM -> lead       : state:queued
lead -> PM       : state:review | state:blocked
```

A lead may cycle a PM-returned item back down only while the same round remains ACTIVE and only if doing so is necessary to satisfy the original root assignment. It may not manufacture a new root objective.

### 5.3 Lead / worker boundary

```text
lead -> worker   : state:queued
worker -> lead   : state:review | state:blocked
lead -> worker   : state:queued   (rework/help cycle allowed)
```

This is where most local iteration should occur. Worker-to-worker routing is prohibited unless a future explicit policy adds a worker coordinator.

### 5.4 Verification independence

The Agent Bus does not weaken the existing Verification seam.

- Independent Verification continues to report to PM, not Software Lead.
- A Software Lead may request independent review of a PR only where existing Digital-Tape governance permits self-service review.
- If engine behavior lacks verifier-authored landed tests, route the question to PM rather than using the bus to bypass the structural rule.
- Verification may delegate mechanical or evidence-gathering work to a worker only when doing so does not expose implementation before independent tests are authored or otherwise compromise independence.

## 6. Token-economy policy

Expensive agents should spend tokens on work that requires their role-specific judgment.

### Program Manager — Claude Cowork
Use for:
- round planning;
- scope and architecture decisions;
- spec ownership;
- cross-stream arbitration;
- final executive synthesis.

Avoid for:
- repetitive repository inspection;
- mechanical edits;
- bulk research that a worker can summarize;
- implementation.

### Software / Hardware Leads — Claude Code
Use for:
- decomposition;
- high-leverage implementation decisions;
- code/hardware review;
- integration and merge decisions;
- escalations.

Delegate when practical:
- isolated code changes;
- test plumbing;
- documentation mechanics;
- research/investigation;
- repetitive debugging;
- bounded refactors.

### Verification Lead — ChatGPT Work
Use for:
- adversarial spec reasoning;
- independent test design;
- acceptance judgment;
- cross-cutting safety/correctness review.

Delegate only tasks that preserve independence and do not require the Verification Lead's judgment.

### Workers — ChatGPT chat / Grok
Default destination for bounded execution and investigation. Workers receive self-contained tasks and return concise evidence/results to their parent lead.

**Current platform caveat:** an ordinary interactive ChatGPT chat does not inherently expose a GitHub-triggered inbound execution endpoint. The staged bus therefore defines `to:worker-chatgpt`, but activation requires a supported adapter. Until such an adapter exists, route that worker class to Grok or another callable worker rather than pretending the dispatch occurred.

## 7. Failure containment

### 7.1 Loop prevention

- No PM inbound queue.
- No automatic round restart.
- One parent per child.
- One destination per object.
- `queued -> working` claim before token spend.
- Maximum upward move: one hierarchy edge.
- Maximum downward move: one hierarchy edge.
- Rework may only serve the parent task's existing acceptance criteria.
- New scope requires escalation to parent, ultimately PM, and waits for a future Michael-authorized round if it exceeds current scope.

### 7.2 Stale work

A stale `state:working` task must not be automatically restarted by another expensive agent. It should be marked `state:blocked` or surfaced to the parent lead for a deliberate decision.

### 7.3 Protocol violation

If an illegal route or inconsistent label set is observed:

1. do not execute;
2. set `state:protocol-error` if permitted;
3. comment with the violated rule;
4. return one level upward if a legal parent exists;
5. otherwise stop.

Protocol errors never trigger PM work automatically.

## 8. Recommended issue body

```markdown
## Request
<one bounded objective>

## Round
<round id>

## Parent
<#issue or `Michael` for PM round authorization>

## Requested by
<role>

## Deliverable
<what must be returned>

## Acceptance
- <observable condition>
- <observable condition>

## Authority / constraints
<role-specific limits>

## Relevant inputs
<specs, PRs, files, decisions>

## Return to
<parent role>

## Token policy
Delegate bounded execution to workers when it preserves quality and role independence.
```

## 9. Activation boundary

This branch intentionally does **not** activate the bus.

Activation is a separate, explicit change after Michael approves the staged PR. The activation operation should:

1. review this protocol;
2. create the label set;
3. move/copy approved workflow files from `.github/agent-bus/workflows/` to `.github/workflows/`;
4. configure only the worker adapters actually available;
5. configure least-privilege credentials per role;
6. run dry-run protocol tests;
7. create Round 0 in DRAFT state;
8. require Michael to perform the first explicit DRAFT -> AUTHORIZED transition.

Merging this staged design alone must not cause an agent to run.