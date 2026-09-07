# Digital Tape Agent Bus — staged design

> **STAGED / NOT LIVE.** This file is on `staging/agent-bus-v1`. Nothing here authorizes autonomous work. Do not create bus labels, enable adapters, configure the human gate, or move staged workflows into `.github/workflows/` until Michael explicitly approves activation.

## 1. The architecture

The Agent Bus is a GitHub-native control plane for discrete autonomous work rounds.

- **Issues are authoritative work envelopes.**
- **Native GitHub sub-issues are the hierarchy.**
- PRs are linked implementation/review artifacts, never queue state.
- Labels hold machine state.
- Comments/reviews hold evidence and history; they are never execution triggers.
- Cheap GitHub workflows operate the gates/barriers between model invocations.

The hierarchy is:

```text
Michael
  |
  v
PM — Claude Cowork
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

Hard routing rules:

- PM prepares root work only for leads.
- Leads may work themselves or create bounded worker children.
- Workers return only to their native parent lead; never PM, never another worker.
- Leads return root results/blockers only to PM; never Michael.
- PM does not accept ordinary queued work from agents.
- No agent creates new root scope during an active round.
- Only Michael can release another round.

There is one narrow lateral service edge: Software/Hardware may create a `kind:independent-review` child for Verification when existing Digital-Tape governance permits self-service review. It is not an authority transfer and cannot change scope.

## 2. Why the dispatch bell belongs to GitHub, not agents

Agents **never add `state:queued`**.

A lead creates or revises a child issue, completes its body/destination/parentage, then requests dispatch with:

```text
state:ready
```

The cheap `validate-ready` workflow checks:

- exactly one destination and lifecycle state;
- current protected round authorization;
- native parent and round ancestry;
- hierarchy legality;
- independent-review typing;
- worker/Verification adapter enabled state;
- child-count cap;
- independent-review cap;
- dispatch/rework cycle cap.

Only after those checks does the bus remove `state:ready` and add:

```text
state:queued
```

**`state:queued` is therefore a bus-issued capability to spend model tokens.** Expensive listeners ignore `state:ready` completely.

This is stronger than letting every agent write the execution trigger itself.

## 3. Round lifecycle

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

Michael asks the PM to plan a round. PM spends one frontier invocation to inspect state and prepare:

1. one `agent-round` issue in `round:draft`;
2. zero or one `agent-root` for each participating lead;
3. each root as a native sub-issue of the round;
4. each root fully specified and labelled `state:draft + round:pending + phase:fanout + to:<lead>`.

The PM then stops. A prepared plan is not authorization.

### Human release

`authorize-round.yml` is staged to use a protected GitHub Environment named `michael-round-gate`. Even if an agent triggers the workflow, the authorization job cannot execute until the required human reviewer approves it.

On approval the workflow:

1. records bot-authored authorization provenance;
2. marks the round authorized/active;
3. releases the already-prepared roots directly from draft to queued.

A manually-added `round:authorized` label without protected-workflow provenance is invalid.

### Active round

The PM is idle during the active round. Leads and workers may only satisfy already-authorized root acceptance criteria. Useful new scope is logged for the PM's final summary, not started autonomously.

If a lead cannot resolve a problem within its authority, it returns the root `to:pm state:blocked` and stops. PM does not wake early to start another downward cycle.

### Whole-round barrier

The round becomes quiescent only when all lead roots have returned `to:pm state:review` or `to:pm state:blocked` and no open child work remains.

Then PM wakes exactly once, reviews the repo/evidence, gives Michael an executive summary and recommendation, closes the round, and stops. A new downward wave requires another Michael-approved round.

## 4. Lead fan-out / fan-in

This is the main frontier-token saver.

### Fan-out

A root initially arrives:

```text
agent-root
round:active
phase:fanout
to:<lead>
state:queued
```

The lead claims it once, does the high-value decomposition/judgment work, then creates all useful child Issues as native sub-issues in one batch.

Normal child destination:

```text
to:worker-chatgpt
```

or

```text
to:worker-grok
```

Permitted high-value exception:

```text
kind:independent-review
to:verification
```

Each child requests dispatch with `state:ready`. If any children exist, the lead puts its root in `state:waiting` and goes idle.

### Worker returns do not wake the lead individually

Workers independently claim queued children and return them `state:review` or `state:blocked` to their native parent lead.

The lead does **not** listen to each return.

### Fan-in

The cheap `release-lead-fanin` workflow watches child states. When every open direct child of a waiting root has returned and none remains ready/queued/working/waiting, the bus re-queues the root and changes it to `phase:fanin`.

The lead wakes once and integrates the batch.

It either:

- accepts/dispositions and closes all child issues, then returns the root to PM;
- or requests bounded rework on affected children with `state:ready`, puts the root back to waiting, and stops.

Thus N worker results normally cost **one** lead fan-in invocation instead of N.

## 5. Task lifecycle

```text
DRAFT --lead requests--> READY --bus validates--> QUEUED --destination claims--> WORKING
                                                                    |
                                                                    +--> REVIEW
                                                                    +--> BLOCKED
                                                                    +--> WAITING --bus fan-in--> QUEUED
```

`state:protocol-error` is a non-executing sink for invalid envelopes.

### Claim rule

Before any model tokens are spent:

1. fetch queued Issue fresh;
2. verify destination, state, round and ancestry;
3. remove `state:queued` and add `state:working`;
4. fetch again and confirm claim;
5. only then invoke the substantive model/run.

Duplicate notifications against a non-queued issue are no-ops.

## 6. Loop and spend fuses

Current staged limits:

| Fuse | Default | Hard cap |
|---|---:|---:|
| Worker children per lead root | 6 | 12 |
| Rework cycles per child | 2 | 3 total queued cycles |
| Independent-review service calls per Software/Hardware root | 1 | 2 |
| Root queue cycles | normally 1–2 | 3 |

A hard-cap increase is a protocol change requiring Michael approval, not something an agent may decide mid-round.

A stale `state:working` task is never automatically claimed by a second expensive agent.

## 7. Token allocation policy

### Claude Cowork / PM

Expected expensive pattern: **two invocations per round** — draft/preparation, then final executive synthesis. PM sleeps during the active work wave.

Use PM tokens for roadmap, spec, architecture, arbitration and synthesis, not implementation or repeated repository polling.

### Claude Code / Software + Hardware Leads

Use for decomposition, architecture/interface judgment, integration, review and merge decisions. Batch delegation at fan-out; batch review at fan-in. Do not wake on individual worker returns.

### ChatGPT Work / Verification

Reserve for adversarial spec reasoning, independent test design and acceptance judgment. Typed lateral review calls are bounded. Mechanical evidence gathering may be delegated only when independence is preserved.

### ChatGPT chat / Grok

Preferred execution pool for bounded implementation, investigation, repetitive debugging, mechanical edits and evidence collection.

`to:worker-chatgpt` is deliberately defined now, but remains disabled until there is a real supported GitHub-triggered chat adapter. The bus will reject it while disabled rather than pretending the work was dispatched. Grok can be the initial worker adapter if that is the callable pool available at activation.

## 8. Verification seam stays intact

Transport automation does not weaken the current Digital-Tape rules:

- Verification still reports to PM.
- Test-before-implementation ordering remains intact where required.
- A typed review child may point to a PR, but the Issue is the bus envelope.
- A self-service independent review must be refused when verifier-authored tests have not yet landed for the behavior.
- Verification service children cannot delegate further; Verification root work may delegate only where independence survives.

## 9. Failure containment

- Comments never trigger execution.
- Agents cannot directly mint `state:queued`.
- One active round maximum.
- One root maximum per participating lead.
- Round -> root -> child is the maximum task depth.
- Workers cannot create another layer of delegation.
- Out-of-scope discoveries wait for the next human-approved round.
- Protocol-invalid ready requests become `state:protocol-error` without waking a model.
- Round completion never starts another round.

If every agent shares the same GitHub account/token, GitHub cannot cryptographically distinguish which model authored a mutation. The hierarchy is still strongly constrained by ancestry, labels, fuses and standing role contracts, but runtime identity separation requires distinct GitHub App/service identities. The human round barrier remains separately protected by the GitHub Environment approval.

## 10. Files staged here

- `.github/agent-bus/protocol.yml` — machine policy and budgets.
- `.github/agent-bus/labels.yml` — label manifest, not applied.
- `.github/agent-bus/ROLE-CONTRACTS.md` — exact PM/lead/worker listener behavior.
- `.github/ISSUE_TEMPLATE/agent-round.yml` — bounded round draft.
- `.github/ISSUE_TEMPLATE/agent-root.yml` — PM-prepared lead root.
- `.github/ISSUE_TEMPLATE/agent-task.yml` — lead child envelope.
- `.github/agent-bus/workflows/authorize-round.yml` — protected human release, inert here.
- `.github/agent-bus/workflows/validate-ready.yml` — cheap dispatch gate, inert here.
- `.github/agent-bus/workflows/release-lead-fanin.yml` — lead barrier, inert here.
- `.github/agent-bus/workflows/detect-quiescence.yml` — PM barrier, inert here.
- `tools/agent-bus/validate_transition.py` — side-effect-free protocol validator.
- `tools/agent-bus/test_validate_transition.py` — red/green protocol tests.

## 11. Activation boundary

This branch intentionally does **not** activate the bus.

Activation is a separate explicit operation after review:

1. create the label set;
2. create/configure `michael-round-gate` with Michael as required reviewer;
3. configure only runtime adapters that truly exist;
4. set adapter-enable repository variables;
5. move approved staged workflows into `.github/workflows/`;
6. run protocol tests and deliberate red cases;
7. prove no agent can execute from `state:ready` or an unapproved round;
8. dry-run one harmless Round 0 through root fan-out, child fan-in, whole-round quiescence and PM stop;
9. only then treat the bus as live.

Merging documentation by itself must never execute an agent.