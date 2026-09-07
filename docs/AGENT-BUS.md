# Digital Tape Agent Bus — staged design

> **STAGED / NOT LIVE.** This file is on `staging/agent-bus-v1`. Nothing here authorizes autonomous work. Do not create bus labels, enable adapters, configure the human gate, or move staged workflows into `.github/workflows/` until Michael explicitly approves activation.

## 1. The architecture

The Agent Bus is a GitHub-native control plane for discrete autonomous work rounds.

- **Issues are authoritative work envelopes.**
- **Native GitHub sub-issues are the hierarchy.**
- PRs are linked implementation/review artifacts and may be used as edge-trigger transport for runtimes that only support PR webhooks; PRs never hold queue/barrier authority.
- Labels hold machine state.
- Comments/reviews hold evidence and history. Persistent comment text never authorizes execution.
- Cheap GitHub workflows operate the gates/barriers between model invocations.

The hierarchy is:

```text
Michael
  |
  v
PM — ChatGPT Work
  |
  +--> Software Lead — Claude Code
  |       +--> ChatGPT-chat / Grok workers
  |
  +--> Hardware Lead — Claude Code
  |       +--> ChatGPT-chat / Grok workers
  |
  +--> Verification Lead — ChatGPT Work
          +--> ChatGPT-chat / Grok workers where independence permits
```

Claude Cowork is not part of staged v1.

Hard routing rules:

- PM prepares root work only for leads.
- Leads may work themselves or create bounded worker children.
- Workers return only to their native parent lead; never PM, never another worker.
- Leads return root results/blockers only to PM; never Michael.
- PM does not accept ordinary queued work from agents.
- No agent creates new root scope during an active round.
- Only Michael can release another round.

There is one narrow lateral service edge: Software/Hardware may create a `kind:independent-review` child for Verification when existing Digital-Tape governance permits self-service review. It is not an authority transfer and cannot change scope.

## 2. Capability classes, not model pins

The bus does not care about dated model IDs. It asks for a **capability class** and lets each adapter choose the best currently available model in that provider family.

Current mapping:

| Capability | OpenAI Work | Claude Code | Typical use |
|---|---|---|---|
| `frontier` | Astra | Opus | hardest architecture, safety, freeze, arbitration |
| `strong` | Sol | Sonnet | difficult role-level reasoning/integration |
| `balanced` | Terra | Sonnet | routine bounded engineering/analysis |
| `economy` | Luna | Haiku | mechanical/repetitive/well-specified execution |
| `auto` | adapter chooses | adapter chooses | lowest sufficient tier |

Provider lineups will change. Moving from one current model to its successor **inside the same capability class is not a protocol change**.

`auto` is the normal setting. The policy in `.github/agent-bus/capability-tiers.yml` chooses the lowest sufficient starting class from role and task metadata. A running role may request at most one upward retry in a phase if it discovers it was under-tiered; repeated self-escalation or up/down oscillation is forbidden.

Examples:

- PM routine planning/status -> normally `strong` (Sol-class).
- PM phase/format freeze, cross-stream architecture, safety or hard arbitration -> `frontier` (Astra-class).
- Claude Code lead routine decomposition/integration -> normally `strong` (Sonnet-class).
- Lead high-consequence architecture/guardrail decision -> `frontier` (Opus-class).
- Worker mechanical edit/research -> `economy` (Haiku/Luna-like class).
- Worker bounded nontrivial coding/debugging -> `balanced`.

Workers do not silently promote themselves into premium classes. If a child truly needs `strong`/`frontier`, its parent lead reclassifies it or retains the work.

For rough planning, capability classes have heuristic allowance weights: economy 1, balanced 2, strong 4, frontier 8. These are **relative planning units**, not claims about provider billing or exact token metering.

## 3. Why the dispatch bell belongs to GitHub, not agents

Agents **never add `state:queued`**.

A lead creates or revises a child Issue, completes its body/destination/parentage/capability request, then requests dispatch with:

```text
state:ready
```

The cheap `validate-ready` workflow checks hierarchy, round authorization, native ancestry, adapter availability and hard cycle/task budgets. Only after those checks does the bus remove `state:ready` and add:

```text
state:queued
```

**`state:queued` is therefore the bus-issued capability to spend model tokens.** Expensive runtimes ignore `state:ready`.

Some providers can only wake from particular webhook events. A unique bot-authored PR comment/event may therefore act as a **doorbell** after `state:queued` exists. The comment itself is never authority: the adapter must fetch the Issue and successfully claim `queued -> working` before substantive work. Re-delivering the same event becomes a no-op because the Issue is no longer queued.

## 4. Round lifecycle

```text
PM DRAFTS
   |
   | protected Michael approval
   v
AUTHORIZED + ACTIVE
   |
   | leads/workers execute behind barriers
   v
QUIESCENT
   |
   | one PM executive synthesis
   v
CLOSED
   |
   X  no automatic restart
```

### PM draft pass

Michael asks the ChatGPT Work PM to plan a round. The PM resolves its capability (`strong` normally, `frontier` for freeze/architecture/safety/hard arbitration), inspects state, and prepares:

1. one `agent-round` Issue in `round:draft`;
2. zero or one `agent-root` for each participating lead;
3. each root as a native sub-issue of the round;
4. each root fully specified and labelled `state:draft + round:pending + phase:fanout + to:<lead>`;
5. a capability request for each root, normally `auto`.

The PM then stops. A prepared plan is not authorization.

### Human release

`authorize-round.yml` is staged to use a protected GitHub Environment named `michael-round-gate`. Even if an agent triggers the workflow, the authorization job cannot execute until the required human reviewer approves it.

On approval the workflow records bot-authored authorization provenance, marks the round authorized/active, and releases the already-prepared roots directly from draft to queued.

A manually-added `round:authorized` label without protected-workflow provenance is invalid.

### Active round

The PM is idle during the active round. Leads and workers may only satisfy already-authorized root acceptance criteria. Useful new scope is logged for the PM's final summary, not started autonomously.

If a lead cannot resolve a problem within its authority, it returns the root `to:pm state:blocked` and stops. PM does not wake early to start another downward cycle.

### Whole-round barrier

The round becomes quiescent only when all lead roots have returned `to:pm state:review` or `to:pm state:blocked` and no open child work remains.

Then the ChatGPT Work PM wakes once, resolves the appropriate capability tier, reviews the repo/evidence, gives Michael an executive summary and recommendation, closes the round, and stops. A new downward wave requires another Michael-approved round.

## 5. ChatGPT Work wake-up boundary

ChatGPT Work is now both PM and Verification runtime. Native event-triggered Work tasks currently support GitHub **pull-request activity**, while Agent Bus control state is deliberately stored in Issues.

Activation therefore has two legitimate options:

1. **Manual boundary launch:** Michael runs the saved PM Work task at draft/final boundaries. No copying is required; the task reads GitHub itself.
2. **PR edge bridge:** after the bus authorizes a Work invocation, GitHub emits a unique bot-authored event on a designated/relevant PR containing the authoritative Issue number and nonce. Work wakes from that event, then re-fetches and claims the Issue. The PR event is transport only.

Verification naturally often has a relevant implementation PR. PM may require a designated control/signal PR if fully automatic wake-up is desired. That bridge should be built/tested during activation rather than pretending GitHub Issue events directly wake Work.

## 6. Lead fan-out / fan-in

This is the main frontier-token saver.

A root initially arrives `agent-root + round:active + phase:fanout + to:<lead> + state:queued`. The lead claims it once, does high-value decomposition/judgment, and creates useful child Issues as native sub-issues in one batch.

Each child specifies `Capability class`, normally `auto`, and requests dispatch with `state:ready`. Normal destinations are enabled low-cost workers. Permitted high-value exception: `kind:independent-review + to:verification`.

If children exist, the lead puts its root in `state:waiting` and goes idle. Worker returns do **not** wake the lead individually.

The cheap `release-lead-fanin` workflow watches child states. When the batch has returned, the bus re-queues the root as `phase:fanin`. The lead wakes once and integrates all results. It either closes/dispositions the children and returns the root to PM, or requests bounded rework on only affected children and waits again.

Thus N worker results normally cost **one** lead fan-in invocation instead of N.

## 7. Task lifecycle and claim rule

```text
DRAFT --lead requests--> READY --bus validates--> QUEUED --destination claims--> WORKING
                                                                    |
                                                                    +--> REVIEW
                                                                    +--> BLOCKED
                                                                    +--> WAITING --bus fan-in--> QUEUED
```

`state:protocol-error` is a non-executing sink for invalid envelopes.

Before substantive model work:

1. receive authorized wake-up/doorbell;
2. fetch queued Issue fresh;
3. verify destination, state, round and ancestry;
4. resolve requested capability to an allowed runtime class;
5. remove `state:queued` and add `state:working`;
6. fetch again and confirm claim;
7. record runtime/capability attestation when practical;
8. only then invoke/do substantive work.

Duplicate notifications against a non-queued Issue are no-ops.

## 8. Loop and spend fuses

Current staged limits:

| Fuse | Default | Hard cap |
|---|---:|---:|
| Worker children per lead root | 6 | 12 |
| Rework cycles per child | 2 | 3 total queued cycles |
| Independent-review service calls per Software/Hardware root | 1 | 2 |
| Root queue cycles | normally 1–2 | 3 |
| Capability upshifts per PM/Verification phase | 0 | 1 |

A hard-cap increase is a protocol change requiring Michael approval, not something an agent may decide mid-round. A stale `state:working` task is never automatically claimed by a second expensive agent.

## 9. Token allocation policy

### ChatGPT Work / PM

Expected pattern: approximately **two substantive PM invocations per round** — draft/preparation and final executive synthesis. Default `auto` normally resolves to Sol/strong; Astra/frontier is reserved for the highest-consequence rounds or arbitration.

### Claude Code / Software + Hardware Leads

Use adaptive lead capability for decomposition, architecture/interface judgment, integration, review and merge decisions. Batch delegation at fan-out; batch review at fan-in. Do not wake on individual worker returns.

### ChatGPT Work / Verification

Normally Sol/strong; Astra/frontier for freeze/release or safety-critical/cross-cutting adversarial judgment. Mechanical evidence gathering may be delegated only when independence is preserved.

### ChatGPT chat / Grok workers

Preferred execution pool for bounded implementation, investigation, repetitive debugging, mechanical edits and evidence collection. Default economy, balanced when the child genuinely requires more local reasoning.

`to:worker-chatgpt` remains disabled until there is a real supported inbound adapter. The bus rejects disabled destinations rather than pretending work was dispatched. Grok can be the initial worker adapter if callable at activation.

## 10. Verification seam stays intact

Transport/capability automation does not weaken existing Digital-Tape rules:

- Verification still reports to PM.
- Test-before-implementation ordering remains intact where required.
- A typed review child may point to a PR, but the Issue is the bus envelope.
- A self-service independent review must be refused when verifier-authored tests have not yet landed for the behavior.
- Verification service children cannot delegate further; Verification root work may delegate only where independence survives.

## 11. Failure containment

- Persistent trigger strings are never execution authority.
- Agents cannot directly mint `state:queued`.
- One active round maximum.
- One root maximum per participating lead.
- Round -> root -> child is the maximum task depth.
- Workers cannot create another layer of delegation.
- Out-of-scope discoveries wait for the next human-approved round.
- Protocol-invalid ready requests become `state:protocol-error` without waking a model.
- Round completion never starts another round.
- Runtime capability cannot silently downgrade below an explicit request.
- Auto capability escalation is bounded.

If every agent shares the same GitHub account/token, GitHub cannot cryptographically distinguish which model authored a mutation. Runtime identity separation requires distinct GitHub App/service identities. The human round barrier remains separately protected by the GitHub Environment approval.

## 12. Files staged here

- `.github/agent-bus/protocol.yml` — machine policy and budgets.
- `.github/agent-bus/capability-tiers.yml` — provider-neutral capability routing.
- `.github/agent-bus/labels.yml` — label manifest, not applied.
- `.github/agent-bus/ROLE-CONTRACTS.md` — exact PM/lead/worker behavior.
- `.github/ISSUE_TEMPLATE/agent-round.yml` — bounded round draft.
- `.github/ISSUE_TEMPLATE/agent-root.yml` — PM-prepared lead root with capability request.
- `.github/ISSUE_TEMPLATE/agent-task.yml` — lead child envelope with capability request.
- staged workflows for authorization, dispatch validation, fan-in and quiescence.
- protocol validator/tests and activation checklist.

## 13. Activation boundary

This branch intentionally does **not** activate the bus.

Activation is a separate explicit operation after review: install labels; configure `michael-round-gate`; configure only real runtime adapters; validate capability resolution/attestation; move approved staged workflows live; run deliberate red cases; dry-run one harmless Round 0 through human release, fan-out, fan-in, Work wake-up transport, quiescence and PM stop; only then treat the bus as live.

Merging documentation by itself must never execute an agent.
