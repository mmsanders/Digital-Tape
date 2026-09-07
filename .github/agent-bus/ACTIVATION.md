# Agent Bus activation checklist

> **DO NOT EXECUTE THIS CHECKLIST WITHOUT MICHAEL'S EXPLICIT ACTIVATION APPROVAL.**
>
> The staging PR is intentionally inert. Activation is a separate change/operation.

## A. Preflight

- [ ] Michael has reviewed/approved `docs/AGENT-BUS.md` and `.github/agent-bus/ROLE-CONTRACTS.md`.
- [ ] No existing autonomous listener uses persistent comment text as an execution trigger for Digital-Tape.
- [ ] No `agent-round` is active.
- [ ] Runtime owners understand that agents request `state:ready`; only the bus adds `state:queued`.
- [ ] The existing Digital-Tape Verification ordering/independence rules remain authoritative.

## B. Identity and permissions

Best configuration: give each model runtime a distinct GitHub App/service identity with only the permissions it needs. That lets GitHub distinguish role-originated mutations.

If several agents share Michael's GitHub identity/token, the hierarchy still benefits from parentage, state validation, hard caps and standing role contracts, but GitHub cannot cryptographically prove which model made a mutation. Treat that as a known limitation, not as identity isolation.

The `michael-round-gate` must remain outside ordinary agent capability. In particular, agent adapters must not be granted an API/tool that can approve protected-environment deployments.

## C. Install labels

Review, then run once:

```bash
tools/agent-bus/bootstrap-labels.sh mmsanders/Digital-Tape
```

This is the first persistent repo-level mutation in activation.

## D. Configure the protected human gate

In repository Settings -> Environments:

1. create environment `michael-round-gate`;
2. require Michael as reviewer;
3. do not grant agent service identities reviewer authority;
4. ensure a workflow can be triggered by an agent but cannot pass the environment gate without the human approval action;
5. perform one harmless workflow test before enabling model listeners.

If all automation currently runs under Michael's GitHub identity, do **not** claim this provides cryptographic actor separation. The important operational property is that the deployment remains pending until a human approval action is performed and no agent adapter has a tool for that action.

## E. Configure adapter flags

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
AGENT_BUS_GROK_WORKER_ENABLED=true       # only if a real Grok listener/adapter is configured
AGENT_BUS_VERIFICATION_ENABLED=true      # only after ChatGPT Work listener is configured
```

Software/Hardware root listeners are not selected through child adapter flags; they receive only roots released by the protected round workflow and must be verified before the first Round 0 approval.

## F. Configure runtime listeners

Use `.github/agent-bus/ROLE-CONTRACTS.md` as the standing contract.

Minimum listener behavior:

```text
observe:  to:<me> + state:queued
claim:    queued -> working
re-fetch: require working + to:<me>
execute:  only after successful claim
return:   review/blocked according to hierarchy
```

Required mailbox filters:

```text
Software root:     is:issue is:open label:agent-root label:to:software label:state:queued
Hardware root:     is:issue is:open label:agent-root label:to:hardware label:state:queued
Verification root: is:issue is:open label:agent-root label:to:verification label:state:queued
Verification svc:  is:issue is:open label:kind:independent-review label:to:verification label:state:queued
ChatGPT worker:    is:issue is:open label:to:worker-chatgpt label:state:queued
Grok worker:       is:issue is:open label:to:worker-grok label:state:queued
PM final only:     is:issue is:open label:agent-round label:round:quiescent
```

PM must **not** listen to individual `to:pm state:review` root issues.

## G. Activate GitHub-side workflows

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

## H. Protocol tests

Run:

```bash
python3 tools/agent-bus/test_validate_transition.py
```

Deliberately verify these red cases in a sandbox/dry-run issue tree:

- [ ] agent attempts to add/act on work without an authorized round;
- [ ] worker tries to route directly to PM;
- [ ] worker task lacks native parent;
- [ ] task is nested below the allowed round -> root -> child depth;
- [ ] task has two destination labels;
- [ ] task has two lifecycle labels;
- [ ] child targets a disabled adapter;
- [ ] untyped Software -> Verification request;
- [ ] fourth dispatch cycle on a child;
- [ ] thirteenth child under one root;
- [ ] third typed independent-review child under one root;
- [ ] second draft/active round while another exists;
- [ ] manually adding `round:authorized` without bot proof;
- [ ] comment containing old trigger text causes no execution.

Every rejection must spend **zero model tokens**.

## I. Claim/idempotency test for every runtime

For each enabled runtime:

1. create one harmless queued test Issue addressed to it inside a protected Round 0 tree;
2. deliver the same notification twice;
3. verify only one listener wins `queued -> working`;
4. verify the duplicate sees non-queued state and exits before model invocation;
5. verify stale `state:working` does not cause automatic second execution.

Do not enable the runtime variable/listener until this passes.

## J. Round 0 dry run

Use harmless documentation-only work.

1. PM prepares one round and one or two lead roots, all draft/pending.
2. Confirm **nothing runs**.
3. Trigger authorization workflow; leave environment unapproved.
4. Confirm **nothing runs**.
5. Michael approves the protected environment.
6. Confirm all prepared roots release together.
7. One lead creates at least two worker children and enters waiting.
8. Confirm the first child return does **not** wake the lead.
9. Return the remaining child.
10. Confirm fan-in queues the lead exactly once.
11. Lead closes/dispositions children and returns its root to PM.
12. Confirm PM does not wake until every root has returned.
13. Confirm round becomes quiescent exactly once.
14. PM performs one executive synthesis and closes the round.
15. Confirm **no next round begins** and no queue is active.

## K. Go-live criterion

The bus is live only when Michael explicitly says it is live **after** Round 0 demonstrates:

- human authorization barrier;
- no comment triggers;
- gated ready -> queued dispatch;
- exactly-once claim behavior under duplicate notification;
- child fan-in batching;
- root/round hard fuses;
- PM quiescent stop;
- no automatic next round.
