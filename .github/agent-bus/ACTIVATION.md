# Agent Bus activation checklist

> **DO NOT EXECUTE THIS CHECKLIST WITHOUT MICHAEL'S EXPLICIT ACTIVATION APPROVAL.**
>
> The staging PR is intentionally inert. Activation is a separate change/operation.

## A. Preflight

- [ ] Michael has reviewed/approved `docs/AGENT-BUS.md`, `.github/agent-bus/ROLE-CONTRACTS.md`, and `.github/agent-bus/capability-tiers.yml`.
- [ ] Program Manager runtime is ChatGPT Work; Claude Cowork is not configured as an Agent Bus runtime.
- [ ] No existing autonomous listener uses persistent comment text as queue authority for Digital-Tape.
- [ ] No `agent-round` is active.
- [ ] Runtime owners understand that agents request `state:ready`; only the bus adds `state:queued`.
- [ ] The existing Digital-Tape Verification ordering/independence rules remain authoritative.

## B. Identity and permissions

Best configuration: give each runtime a distinct GitHub App/service identity with only the permissions it needs. That lets GitHub distinguish role-originated mutations.

If several agents share Michael's GitHub identity/token, hierarchy still benefits from parentage, state validation, hard caps and standing role contracts, but GitHub cannot cryptographically prove which runtime made a mutation. Treat that as a known limitation.

The `michael-round-gate` must remain outside ordinary agent capability. Agent adapters must not be granted an API/tool that can approve protected-environment deployments.

## C. Capability routing

Review `.github/agent-bus/capability-tiers.yml` against the models actually available at activation.

The protocol cares about classes rather than dated models:

```text
frontier  -> current highest-capability family (today: Astra / Opus)
strong    -> difficult role reasoning       (today: Sol / Sonnet)
balanced  -> bounded engineering            (today: Terra / Sonnet)
economy   -> mechanical/repetitive           (today: Luna / Haiku)
auto      -> lowest sufficient allowed class
```

Activation requirements:

- [ ] each adapter declares which classes it can actually select;
- [ ] explicit requests are never silently downgraded below the requested class;
- [ ] unavailable requested classes block or request an explicit fallback;
- [ ] runtime records requested/resolved class and actual model name where exposed;
- [ ] PM Work defaults to `auto`, normally strong/Sol-class, frontier/Astra-class for freeze/architecture/safety/hard arbitration;
- [ ] Verification Work follows the same strong/frontier discipline;
- [ ] workers default to economy and may auto-promote only to balanced;
- [ ] one bounded capability upshift per PM/Verification phase is enforced by adapter policy;
- [ ] capability-weighted estimates are reported as planning units, not exact provider billing/tokens.

## D. Install labels

Review, then run once:

```bash
tools/agent-bus/bootstrap-labels.sh mmsanders/Digital-Tape
```

This is the first persistent repo-level mutation in activation.

## E. Configure the protected human gate

In repository Settings -> Environments:

1. create environment `michael-round-gate`;
2. require Michael as reviewer;
3. do not grant agent service identities reviewer authority;
4. ensure a workflow can be triggered by an agent but cannot pass the environment gate without human approval;
5. perform one harmless workflow test before enabling model listeners.

If all automation currently runs under Michael's GitHub identity, do **not** claim this provides cryptographic actor separation. The important operational property is that deployment remains pending until a human approval action is performed and no agent adapter has a tool for that action.

## F. Configure adapter flags

The cheap dispatch gate rejects destinations whose adapters are not explicitly enabled.

Repository variables:

```text
AGENT_BUS_CHATGPT_WORKER_ENABLED=false
AGENT_BUS_GROK_WORKER_ENABLED=false
AGENT_BUS_VERIFICATION_ENABLED=false
```

Flip a variable to `true` only after its runtime listener passes the claim/idempotency test below.

Initial expected setup if ordinary ChatGPT chat cannot be invoked from GitHub:

```text
AGENT_BUS_CHATGPT_WORKER_ENABLED=false
AGENT_BUS_GROK_WORKER_ENABLED=true       # only if a real Grok adapter exists
AGENT_BUS_VERIFICATION_ENABLED=true      # only after ChatGPT Work transport is configured
```

Software/Hardware root listeners and PM Work are verified separately before Round 0.

## G. Configure runtime wake-up transports

Use `.github/agent-bus/ROLE-CONTRACTS.md` as the standing contract.

Authoritative execution sequence:

```text
wake/doorbell -> fetch authoritative Issue -> verify queued -> resolve capability
-> claim queued->working -> re-fetch -> attest runtime -> substantive model work
```

Required Issue mailboxes:

```text
Software root:     is:issue is:open label:agent-root label:to:software label:state:queued
Hardware root:     is:issue is:open label:agent-root label:to:hardware label:state:queued
Verification root: is:issue is:open label:agent-root label:to:verification label:state:queued
Verification svc:  is:issue is:open label:kind:independent-review label:to:verification label:state:queued
ChatGPT worker:    is:issue is:open label:to:worker-chatgpt label:state:queued
Grok worker:       is:issue is:open label:to:worker-grok label:state:queued
PM final only:     is:issue is:open label:agent-round label:round:quiescent
```

PM must **not** act on individual `to:pm state:review` root issues.

### ChatGPT Work PM / Verification transport

Native Work event-triggered GitHub tasks currently respond to supported **pull-request activity**, while Agent Bus authority lives in Issues.

Choose and test one of these patterns:

1. **Manual boundary PM launch** — Michael runs a saved PM Work task for round draft/final. The task reads GitHub itself; no files/text are copied.
2. **PR edge bridge** — after an authoritative Issue becomes executable, a GitHub Action emits a unique bot-authored event on a designated/relevant PR containing only the Issue number, attempt and nonce. Work wakes from the event, then re-fetches and claims the Issue.

For Verification, the linked implementation PR is usually the natural event source. For fully automatic PM wake-up, use a reviewed designated control/signal PR or another supported Work event bridge.

A PR comment/event is a **doorbell only**. Replaying it must spend zero substantive tokens if the Issue is no longer queued.

## H. Activate GitHub-side workflows

Move the reviewed files into the live workflow directory in one activation PR:

```text
.github/agent-bus/workflows/authorize-round.yml
    -> .github/workflows/agent-bus-authorize-round.yml
.github/agent-bus/workflows/validate-ready.yml
    -> .github/workflows/agent-bus-validate-ready.yml
.github/agent-bus/workflows/release-lead-fanin.yml
    -> .github/workflows/agent-bus-release-lead-fanin.yml
.github/agent-bus/workflows/detect-quiescence.yml
    -> .github/workflows/agent-bus-detect-quiescence.yml
```

Do not move them piecemeal into production while listeners are already live.

## I. Protocol and capability tests

Run:

```bash
python3 tools/agent-bus/test_validate_transition.py
```

Deliberately verify these red cases in a sandbox/dry-run Issue tree:

- [ ] agent attempts to act without an authorized round;
- [ ] worker tries to route directly to PM;
- [ ] worker task lacks native parent;
- [ ] task exceeds allowed round -> root -> child depth;
- [ ] task has two destination labels;
- [ ] task has two lifecycle labels;
- [ ] child targets a disabled adapter;
- [ ] untyped Software -> Verification request;
- [ ] fourth dispatch cycle on a child;
- [ ] thirteenth child under one root;
- [ ] third typed independent-review child under one root;
- [ ] second draft/active round while another exists;
- [ ] manually adding `round:authorized` without bot proof;
- [ ] replayed/persistent old trigger text cannot authorize work;
- [ ] requested capability unavailable -> block, not silent downgrade;
- [ ] worker requesting frontier without parent reclassification -> reject/block;
- [ ] second PM/Verification self-upshift in one phase -> reject.

Every rejection should spend zero substantive model tokens.

## J. Claim/idempotency test for every runtime

For each enabled runtime:

1. create one harmless queued test Issue addressed to it inside protected Round 0;
2. deliver the same wake-up notification twice;
3. verify only one invocation wins `queued -> working`;
4. verify duplicate delivery sees non-queued state and exits before substantive work;
5. verify stale `state:working` does not cause automatic second execution;
6. verify runtime attestation includes requested/resolved capability and actual model when exposed.

Do not enable the runtime until this passes.

## K. Round 0 dry run

Use harmless documentation-only work.

1. PM Work prepares one round and one or two lead roots, all draft/pending.
2. Confirm nothing runs.
3. Trigger authorization workflow; leave environment unapproved.
4. Confirm nothing runs.
5. Michael approves protected environment.
6. Confirm all prepared roots release together.
7. Confirm each runtime resolves/records a capability class before substantive work.
8. One lead creates at least two worker children and enters waiting.
9. Confirm first child return does not wake lead.
10. Return remaining child.
11. Confirm fan-in queues lead exactly once.
12. Lead closes/dispositions children and returns root to PM.
13. Confirm PM does not act until every root has returned.
14. Confirm round becomes quiescent exactly once.
15. Run/wake PM Work final synthesis, using strong or frontier according to the capability router.
16. PM closes round.
17. Confirm **no next round begins** and no queue is active.

## L. Go-live criterion

The bus is live only when Michael explicitly says it is live **after** Round 0 demonstrates human authorization, gated dispatch, exactly-once claim behavior, capability resolution without silent downgrade, child fan-in batching, root/round hard fuses, PM quiescent stop, and no automatic next round.
