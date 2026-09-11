# Hardware Lead — setup-only bootstrap report

**Recorded 11 September 2026 from main at `feb5fd9c1634d9e3e439165ec1abec2ee9d92b68`.**

This is the setup-only return required by
[roles/hardware.md](roles/hardware.md). It reports observed capability and gaps.
It claims no product work, binds no instance, mints no attestation, dispatched no
controller command and changes neither `runtimes.json` nor `phase1-roster.json`.
`hardware` remains `enabled: false` with null actor/instance.

## 1. Instance URL / id

| Field | Observed |
|---|---|
| Session id | `session_01KopS8n5KcaGMzQ2F7exLk8` |
| URL | https://claude.ai/code/session_01KopS8n5KcaGMzQ2F7exLk8 |
| Environment id | `env_01NT3oPz6HjiN45HoSaxXUeG` (`anthropic_cloud`) |
| Origin | `web_claude_ai` — manually started session |

**Gap.** This is an ad-hoc cloud session, not the `DT Hardware Lead` **routine**
that [CLOUD-HOOKUP.md](CLOUD-HOOKUP.md) requires. The trigger list for this account
is empty, so no routine exists for this role. The "fresh session per firing" and
per-routine API trigger properties are therefore not demonstrated here. A session id
is not a stable routine instance id; do not enter this id as the roster binding.

## 2. Model identifier

Runtime-exposed id is `claude-opus-5` on all three fields (configured, session
context and last served). Effort `high`, permission mode `auto`.

This satisfies the family-prefix form of `providers.anthropic.strong = "opus"`, so
the assigned strong class is met without downgrade. Per ROLE-CONTRACTS model
routing, the reviewed mapping should be aligned to the runtime-exposed string at
hookup. Recording that alignment is PM's, not this role's.

## 3. GitHub workflow-dispatch method and authenticated identity

**Blocker — `gh` CLI is absent.** `tools/agent-bus/client.py` shells out to
`gh workflow run` for `send` and `gh api` for `mailbox`; neither path runs in this
environment as written. The documented command transport is unavailable here.

Dispatch is otherwise reachable through the GitHub MCP `actions_run_trigger`
(`run_workflow`), which can supply `agent-bus.yml` on main with
`command` / `request_id` / `payload`.

**Blocker — identity is Michael's.** That connection authenticates as
`mmsanders` (id 78818921). `agent-bus.yml` stamps `BUS_ACTOR` from
`github.triggering_actor`, so any command sent from here would enter the ledger as
Michael, and an `authorize` would forge his round approval. This is the exact
identity gap CLOUD-HOOKUP predicted and it violates universal adapter boundary 1
("Never Michael's identity"). **No dispatch of any command, including the harmless
`reconcile`, was performed.** A distinct non-human actor with Contents read, Issues
read/write and Actions write is a prerequisite to any hardware binding.

**Read path works without `gh`.** The ledger is readable directly from
`origin/agent-bus-state:state.json`. Current contents: `current: null`, empty
`rounds`, `tasks` and `receipts`; all roles `enabled: false`. There is no queued
hardware work and nothing to claim. `binding_readiness.py` reports
`ready_for_binding_review: false` with all six roles missing every evidence field.

## 4. Supported event trigger

The controller supports only `manual` and `pr-doorbell`. What this surface actually
offers, and why none of it is yet a certified doorbell:

| Mechanism | Reality |
|---|---|
| Scheduled routine / cron | Time-based only; no claim-driven wake. Hookup says keep recurring triggers off during setup. |
| PR-activity subscription | Real GitHub PR events (comments, CI, reviews). Closest to `pr-doorbell`, but it wakes an already-running session rather than firing a fresh one, and the subscription dies with the session. |
| Inbound webhook URL | Available, but scoped to this session and gone when it ends; not a durable per-routine endpoint. |
| Per-routine API trigger URL/token | Not provisioned — no routine exists for this role. |

**Every one of these starts a model turn before any claim check.** That is the
pre-model deduplication distinction CLOUD-HOOKUP item 5 asks to capture: none of
them is the cheap adapter the contract describes, so duplicate or empty deliveries
would each cost a substantive invocation. No designated signal PR is configured, and
a `github-actions[bot]` comment wake remains untested on this surface.

## 5. Durable receipt-consumption storage

**None available.** The container is ephemeral and reclaimed after inactivity, the
scratchpad is session-scoped, and a routine firing would start from a fresh session
carrying no prior state. Adapter boundary step 7 — persist the request id as
consumed *before* launching one substantive invocation — cannot be satisfied by this
surface as configured.

The controller's own `state['receipts']` fingerprint check does dedupe commands, but
it acts after dispatch and inside the workflow; it does not prevent a duplicate model
launch, which is the cost this step exists to bound. A private credential/state store
outside the repo is the obvious candidate. Selecting and paying for one is Michael's
decision, so it is reported, not chosen.

## Environment and toolchain notes

- `make -C hardware fabrication-gate` reproduced **CLOSED** (exit 1) here, naming the
  unbound 74HC221 variant and the assumed ±14 % timing term. `fabrication-gate-test`
  passed 8 checks plus its negative control and 3 CLI tests.
- CadQuery and `kicad-cli` are **not installed** in this container. CAD rebuild and
  ERC/DRC work must run in GitHub CI, matching the existing note in
  [STATUS-HARDWARE.md](../../docs/STATUS-HARDWARE.md). A missing dependency is not a
  passing test.
- `michael-round-gate` protection could not be verified from here; no environments
  read is exposed to this session and no credential was extracted to attempt one.
  `bus.py` fails closed if it is absent or misconfigured.

## Consequences for the delegation mandate

`worker-grok` is `enabled: false` with no instance, and Grok capability classes are
all null. There is currently **no bound worker to delegate to**, so the Phase 1
delegation-first workflow cannot be exercised by this role yet. That is a setup
block to resolve before hardware rounds start, not a licence for the lead to absorb
the worker experiment by doing every task directly.

## Blocking list for binding

1. Create the `DT Hardware Lead` Claude Code cloud routine; report its durable instance id.
2. Provision a distinct non-human GitHub actor and prove its dispatch identity.
3. Provide a dispatch path that does not require the absent `gh` CLI, or install it.
4. Certify an exact supported wake event and a designated control PR.
5. Provide durable receipt-consumption storage outside the session.
6. Bind a worker instance before delegated hardware rounds.

Until all six are closed, `hardware` stays disabled and no Round 0 claim is possible.
