# Adapter — Grok Bot as Surge

Authority: CLAUDE.md Surge support — bounded proposal/analysis assigned by PM; no
standing lead normative issuance, acceptance, or merge. PM dispositions Surge work.
Agent Bus treats Surge as a lead root for fan-out to workers, then return to PM.

## Identity

| Field | Value |
|---|---|
| Role | `surge` |
| GitHub `actor` | Bot login from runtimes (never `mmsanders`) |
| `instance` | e.g. `grok-bot-surge-1` |
| Provider | `grok` (classes must be attested before enable) |
| Transport | `manual` first; `pr-doorbell` optional later |

Grok Bot’s day-to-day GitHub connector may still be Michael’s account for **human
repo ops**. Bus **claims** must use the Surge bot token/`gh` auth as `BUS_ACTOR`.

## Wake (manual)

1. Michael (or a standing reminder) tells Surge: “check Agent Bus mailbox.”
2. Or Surge runs on a schedule: read mailbox only; do nothing if empty.

```bash
python3 tools/agent-bus/client.py mailbox surge
```

Queued work appears only when `enabled: true`, a round is active, and this role has
`state: queued` tasks.

## Universal claim loop (ROLE-CONTRACTS)

For each queued item:

1. Fetch current ledger (`agent-bus-state` / `state.json`) and the Issue; verify scope.
2. Resolve capability **without silent downgrade**. If `providers.grok` cannot supply
   the requested class, **stop** and return for reassignment — do not forge attestation.
3. `claim` with `queue_token`, unique `request_id`, resolved class, actual model name,
   and `adapter_revision`.
4. Read the workflow receipt artifact. Proceed only if `claimed: true`.
5. Re-fetch ledger; confirm claim id/actor/instance still match.
6. Persist the consumed `request_id` before any substantive work.
7. Do the bounded assignment; keep evidence discoverable.
8. `return` / `block` / `wait` / `ready` / `close-child` as appropriate through
   `client.py send`, always with the active claim id.

```bash
python3 tools/agent-bus/client.py send claim payload.json
# payload: issue, queue_token, resolved, model, adapter_revision
```

Duplicate notifications never launch a second model call. Diagnose cancelled/crashed
transport from the ledger; never auto-reclaim.

## Fan-out to workers

As a lead root (when the approved round includes a Surge root):

1. Create **native child issues** under the root, inside approved scope/budgets.
2. Label destination `to:worker-*` (not another lead) for normal children.
3. `ready` with the parent claim so the controller queues the child.
4. `wait` when children are dispatched; do not wake on every child completion —
   fan-in releases once.
5. `close-child` with disposition before root `return` to PM.

Workers cannot select strong/frontier. Surge may request strong/frontier only within
the lead band once Grok classes exist; until then keep Surge disabled or fail closed.

## Never

- Claim or dispatch as `mmsanders`
- Treat labels, PR comments, or the dashboard as authorization
- Start work from a label alone
- Downgrade an explicit capability request
- Merge product code or issue acceptance under the Surge role
- Enable `provider: grok` while all grok classes are null
