# Agent Bus runtime contracts

> STAGED ONLY. These are standing listener/adapter rules for activation, not instructions to begin work from this branch.

The machine policy is `.github/agent-bus/protocol.yml`; this file states what each runtime should actually do.

## Universal listener contract

Every model-backed runtime must follow these rules before spending tokens:

1. Listen only for its own `to:<role> + state:queued` Issues. Never trigger from comment text.
2. Fetch the issue fresh.
3. Require `agent-task`, `round:active`, exactly one destination, exactly one lifecycle state, and the expected destination.
4. Confirm the issue is inside the active native sub-issue tree.
5. Claim by removing `state:queued`, then adding `state:working`.
6. Fetch again and confirm `state:working` with the same destination.
7. Only then invoke the expensive model / begin substantive work.
8. Treat duplicate notifications for a non-queued issue as a no-op.
9. Never automatically reclaim stale `state:working`; surface it to the parent.
10. Agents request new downward dispatch with `state:ready`. Agents never add `state:queued`.

If the runtime cannot perform the claim transition reliably, it is not a valid Agent Bus adapter.

## Program Manager — Claude Cowork

### Allowed wake-ups

The PM has only two normal expensive invocations per round:

1. **Michael asks it to draft a round.**
2. The current `agent-round` changes to **`round:quiescent`** and the PM performs one final executive synthesis.

The PM must **not** listen to individual `to:pm state:review` or `to:pm state:blocked` roots. Those accumulate silently until the whole-round barrier fires.

### Draft pass

On Michael's request:

1. inspect repository/project state;
2. create exactly one `agent-round` draft;
3. create zero or one `agent-root` for each of Software, Hardware, Verification that actually needs work;
4. make each root a native sub-issue of the round;
5. fully populate objective, acceptance, authority, relevant inputs and delegation guidance;
6. apply exactly one `to:<lead>` destination;
7. leave every root `state:draft + round:pending + phase:fanout`;
8. stop and ask Michael to authorize the prepared round.

PM does not add `state:ready` or `state:queued` to roots. The protected human workflow releases them.

### Active round

PM is idle. A lead may return `to:pm state:blocked`, but that does not wake PM early. It becomes part of the quiescent executive review and, if needed, the next Michael-authorized round.

### Final pass

On `round:quiescent`:

1. claim the round by replacing `round:quiescent` with `round:pm-review`;
2. review repository, root issues, important child results, PR/CI state, and blockers;
3. write one concise executive summary for Michael;
4. close/disposition returned roots as appropriate;
5. mark the round `round:closed`, remove `round:active`, close the round issue;
6. stop.

PM may recommend a next round but may not create/dispatch it unless Michael asks.

## Software Lead — Claude Code

Listen for `agent-root + to:software + state:queued` only.

### `phase:fanout`

1. claim root;
2. perform decomposition and any lead-level architectural/integration work worth Claude Code tokens;
3. prefer workers for bounded implementation, repetitive debugging, mechanical edits, research, and evidence gathering;
4. create all worker/review children in one batch as native sub-issues of the root;
5. fully populate each child and destination;
6. for a permitted independent review, add `kind:independent-review + to:verification`;
7. for normal children choose one enabled worker destination;
8. request child dispatch with `state:ready`, never `state:queued`;
9. if children exist, put the root `state:waiting` and stop;
10. if no children are needed, finish the root and return it directly to PM review/blocked.

Do not wake merely because one worker returns.

### `phase:fanin`

1. claim root once after the bus barrier releases it;
2. review all direct children as a batch;
3. close children whose results are accepted/dispositioned;
4. if bounded rework is required, move only affected child issue(s) to `state:ready`, put root back to `state:waiting`, and stop;
5. if complete, ensure no child issue remains open, change root destination to `to:pm`, and return `state:review`;
6. if unresolved inside authority, ensure child evidence is captured/closed, change root destination to `to:pm`, and return `state:blocked`;
7. stop. PM will not wake until all roots return.

Never create a new root objective from a finding.

## Hardware Lead — Claude Code

Same listener/barrier contract as Software, using `to:hardware`.

Retain Claude Code tokens for hardware architecture, interface decisions, integration judgment, review, sourcing/BOM decisions requiring context, and CAD/schematic review. Push bounded research, data gathering, mechanical documentation, repetitive edits, and isolated implementation to workers where practical.

The Hardware Lead never routes directly to Michael.

## Verification Lead — ChatGPT Work

### PM root work

For `agent-root + to:verification + state:queued`, use the same fan-out/fan-in pattern as the other leads **only where delegation preserves independence**.

Reserve ChatGPT Work for:

- adversarial specification review;
- independent test design before implementation inspection where required;
- acceptance judgment;
- safety/correctness reasoning;
- final independent findings.

Workers may gather evidence or perform mechanical tasks only when doing so cannot contaminate the required independent reasoning.

### Typed independent-review service

Listen separately for `agent-task + kind:independent-review + to:verification + state:queued`.

This is a bounded service call, not a PM root and not a reporting-line change:

1. claim the child issue;
2. verify current Digital-Tape governance permits self-service independent review;
3. **do not delegate this service issue further**;
4. perform the independent review and record the review on the linked PR/artifact;
5. summarize result on the child issue;
6. return the child to the requesting parent lead with `state:review` or `state:blocked`;
7. stop.

If the behavior requires verifier-authored tests that have not landed, refuse the service request and return the finding; do not inspect implementation merely because the bus delivered the request.

## Worker — ChatGPT chat

This adapter is preferred when a supported GitHub-triggered chat worker exists. Until then it must remain disabled in repository variables.

When enabled, listen only for `to:worker-chatgpt + state:queued`:

1. claim;
2. perform exactly the bounded task in the issue;
3. do not create sub-issues, delegate, or enlarge scope;
4. if clarification is needed, return to the native parent lead as `state:blocked` with a concrete question/recommendation;
5. on completion, return to the native parent lead as `state:review` with evidence/artifacts;
6. stop.

Workers never contact PM.

## Worker — Grok

Same worker contract, listening for `to:worker-grok + state:queued`.

Grok is a replaceable worker adapter, not part of the governance hierarchy. If it goes away, disable `AGENT_BUS_GROK_WORKER_ENABLED` and point future bounded work at another enabled worker; parent/round semantics do not change.

## Bus / GitHub Actions

The bus is deliberately non-intelligent and token-free. It may only:

- record protected Michael authorization;
- release already-prepared roots;
- validate `state:ready` child dispatch requests;
- enforce parentage, adapter and cycle/task caps;
- add `state:queued` after validation;
- release waiting roots after all direct children return;
- detect whole-round quiescence.

It must never generate task scope, interpret specifications, choose engineering solutions, or auto-start another round.
