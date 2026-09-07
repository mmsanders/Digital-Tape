# Agent Bus runtime contracts

> STAGED ONLY. These are standing listener/adapter rules for activation, not instructions to begin work from this branch.

The machine policy is `.github/agent-bus/protocol.yml`; capability selection is `.github/agent-bus/capability-tiers.yml`.

## Capability classes

Tasks request a **capability class**, not an exact dated model. The adapter resolves the class to the best currently available model in that provider family and records what it chose.

| Class | OpenAI Work today | Claude Code family today | Intended use |
|---|---|---|---|
| `frontier` | Astra | Opus | hardest architecture, safety, freeze, arbitration |
| `strong` | Sol | Sonnet | difficult role-level reasoning/integration |
| `balanced` | Terra | Sonnet | routine bounded engineering/analysis |
| `economy` | Luna | Haiku | mechanical/repetitive/well-specified execution |
| `auto` | adapter selects | adapter selects | lowest sufficient class |

These mappings are deliberately family-level. A newer model may replace one within the same class without changing governance. Exact snapshots are not required.

`auto` is preferred. Selection happens **before** substantive invocation using task/role metadata. A running role may request at most one bounded upshift for that phase if it discovers the starting class is insufficient; it may not oscillate between tiers or silently fall below an explicitly requested class.

Workers normally use `economy` or `balanced`. PM and Verification normally use `strong`, with `frontier` reserved for genuinely high-consequence work. See `capability-tiers.yml` for the deterministic signals.

## Universal listener contract

Every model-backed runtime must follow these rules before spending substantive tokens:

1. Listen only for its own authorized wake-up transport; GitHub Issue state remains authoritative.
2. Fetch the Issue fresh.
3. Require `agent-task`, `round:active`, exactly one destination, exactly one lifecycle state, and the expected destination.
4. Confirm the Issue is inside the active native sub-issue tree.
5. Resolve requested `capability`/`auto` to an allowed provider capability class.
6. Claim by removing `state:queued`, then adding `state:working`.
7. Fetch again and confirm `state:working` with the same destination.
8. Record runtime attestation when practical: requested class, resolved class, provider, actual model name if exposed, adapter revision.
9. Only then begin substantive model work.
10. Treat duplicate notifications for a non-queued Issue as a no-op.
11. Never automatically reclaim stale `state:working`; surface it to the parent.
12. Agents request new downward dispatch with `state:ready`. Agents never add `state:queued`.

A provider webhook/comment may be used only as an **edge-triggered wake-up transport**. Persistent comment text is never queue state and never authorizes work; the adapter must still win the Issue claim before doing substantive work.

If the runtime cannot perform or verify the claim transition reliably, it is not a valid Agent Bus adapter.

## Program Manager — ChatGPT Work

The PM is now ChatGPT Work. Claude Cowork is not part of the staged v1 runtime set.

### Capability policy

Default: `auto`.

- Resolve to **strong / Sol-class** for normal round planning, routine cross-stream synthesis, status review, and ordinary executive summaries.
- Resolve to **frontier / Astra-class** when the phase involves format/phase freeze, cross-stream architecture or spec arbitration, safety/child guardrails, contradictory lead evidence, or another high-consequence scope decision.
- If a strong run discovers that one of those frontier conditions is material, it may request **one** upshift/retry for that PM phase. No repeated self-escalation loop is allowed.

This makes Astra available to the PM without spending Astra allowance on every routine round.

### Allowed wake-ups

The PM has only two normal substantive invocations per round:

1. **Michael asks it to draft a round.**
2. The current `agent-round` becomes **`round:quiescent`** and the PM performs one final executive synthesis.

The PM must **not** react substantively to individual `to:pm state:review` or `to:pm state:blocked` roots. Those accumulate silently until the whole-round barrier fires.

ChatGPT Work's native GitHub event trigger is based on supported **pull-request activity**, while Agent Bus authority lives in Issues. At activation, either:

- Michael starts the saved PM Work task manually at the two round boundaries; or
- a reviewed edge-trigger bridge emits a unique bot-authored PR event containing only the Issue number/nonce after the bus state transition.

In both cases the Work task must re-read authoritative Issue state before claiming or acting. The PR event is a doorbell, not authority.

### Draft pass

On Michael's request:

1. resolve PM capability class;
2. inspect repository/project state;
3. create exactly one `agent-round` draft;
4. create zero or one `agent-root` for each of Software, Hardware, Verification that actually needs work;
5. make each root a native sub-issue of the round;
6. fully populate objective, acceptance, authority, relevant inputs, delegation guidance, and requested capability (`auto` by default);
7. apply exactly one `to:<lead>` destination;
8. leave every root `state:draft + round:pending + phase:fanout`;
9. stop and ask Michael to authorize the prepared round.

PM does not add `state:ready` or `state:queued` to roots. The protected human workflow releases them.

### Active round

PM is idle. A lead may return `to:pm state:blocked`, but that does not start a new PM planning cycle. It becomes part of the quiescent executive review and, if needed, the next Michael-authorized round.

### Final pass

On `round:quiescent`:

1. resolve PM capability class from the round state (normally strong; frontier for high-consequence arbitration/freeze);
2. claim the round by replacing `round:quiescent` with `round:pm-review`;
3. review repository, root issues, important child results, PR/CI state, and blockers;
4. write one concise executive summary for Michael;
5. close/disposition returned roots as appropriate;
6. mark the round `round:closed`, remove `round:active`, close the round Issue;
7. stop.

PM may recommend a next round but may not create/dispatch it unless Michael asks.

## Software Lead — Claude Code

Listen for `agent-root + to:software + state:queued` only.

Default capability is `auto`: use Sonnet/strong for normal lead reasoning, Opus/frontier for architectural/public-interface/guardrail/high-consequence integration decisions, and balanced where the work is bounded and low-risk. Exact model snapshots are not pinned.

### `phase:fanout`

1. claim root;
2. perform decomposition and lead-level architectural/integration work worth lead tokens;
3. prefer workers for bounded implementation, repetitive debugging, mechanical edits, research, and evidence gathering;
4. create all worker/review children in one batch as native sub-issues of the root;
5. fully populate each child, destination, and capability request (`auto` normally);
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
4. if bounded rework is required, move only affected child Issue(s) to `state:ready`, put root back to `state:waiting`, and stop;
5. if complete, ensure no child Issue remains open, change root destination to `to:pm`, and return `state:review`;
6. if unresolved inside authority, ensure child evidence is captured/closed, change root destination to `to:pm`, and return `state:blocked`;
7. stop. PM will not wake until all roots return.

Never create a new root objective from a finding.

## Hardware Lead — Claude Code

Same listener/barrier/capability contract as Software, using `to:hardware`.

Retain lead capability for hardware architecture, interface decisions, integration judgment, review, sourcing/BOM decisions requiring context, and CAD/schematic review. Use frontier/Opus-class only for safety-critical, board-level high-consequence, or cross-stream interface decisions. Push bounded research, data gathering, mechanical documentation, repetitive edits, and isolated implementation to workers where practical.

The Hardware Lead never routes directly to Michael.

## Verification Lead — ChatGPT Work

Default capability is `auto`: normally strong/Sol-class; use frontier/Astra-class for freeze/release acceptance, safety-critical acceptance, cross-cutting adversarial spec review, or unresolved competing invariant interpretations.

### PM root work

For `agent-root + to:verification + state:queued`, use the same fan-out/fan-in pattern as the other leads **only where delegation preserves independence**.

Reserve ChatGPT Work for adversarial specification review, independent test design before implementation inspection where required, acceptance judgment, safety/correctness reasoning, and final independent findings.

Workers may gather evidence or perform mechanical tasks only when doing so cannot contaminate the required independent reasoning.

### Typed independent-review service

Listen separately for `agent-task + kind:independent-review + to:verification + state:queued`.

This is a bounded service call, not a PM root and not a reporting-line change:

1. claim the child Issue;
2. verify current Digital-Tape governance permits self-service independent review;
3. do not delegate this service Issue further;
4. resolve capability (normally strong, frontier only where the review warrants it);
5. perform the independent review and record it on the linked PR/artifact;
6. summarize result on the child Issue;
7. return the child to the requesting parent lead with `state:review` or `state:blocked`;
8. stop.

If the behavior requires verifier-authored tests that have not landed, refuse the service request and return the finding; do not inspect implementation merely because the bus delivered the request.

## Worker — ChatGPT chat

This adapter is preferred when a supported GitHub-triggered chat worker exists. Until then it must remain disabled in repository variables.

Workers use `auto`, resolving to economy by default and balanced for nontrivial bounded coding/debugging/synthesis. Strong/frontier work must be reclassified by the parent lead rather than silently consuming a premium tier.

When enabled, listen only for `to:worker-chatgpt + state:queued`:

1. claim;
2. resolve allowed capability;
3. perform exactly the bounded task in the Issue;
4. do not create sub-issues, delegate, or enlarge scope;
5. if clarification is needed, return to the native parent lead as `state:blocked` with a concrete question/recommendation;
6. on completion, return to the native parent lead as `state:review` with evidence/artifacts;
7. stop.

Workers never contact PM.

## Worker — Grok

Same worker contract, listening for `to:worker-grok + state:queued`.

Grok is a replaceable worker adapter, not part of the governance hierarchy. Its adapter must declare which capability classes it can actually select/attest. If it goes away, disable `AGENT_BUS_GROK_WORKER_ENABLED` and point future bounded work at another enabled worker; parent/round semantics do not change.

## Bus / GitHub Actions

The bus is deliberately non-intelligent and token-free. It may only record protected Michael authorization, release already-prepared roots, validate `state:ready` child dispatch requests, enforce parentage/adapter/cycle/task caps, add `state:queued` after validation, release waiting roots after all direct children return, and detect whole-round quiescence.

It must never generate task scope, interpret specifications, choose engineering solutions, choose a capability above role policy, or auto-start another round.
