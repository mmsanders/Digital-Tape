# Runtime contract — no instances bound yet

Normal product authorities remain in CLAUDE.md. Read docs/AGENT-BUS.md for controller
invariants and runtimes.json for the actual role/capability configuration. Surge is bounded;
Verification stays independent. No role starts work from a label, PR comment or dashboard.

## Universal adapter boundary

1. Use a distinct GitHub identity and configured instance id for the role. Never Michael's identity.
2. Receive a supported wakeup or read your cheap mailbox. PM reads only a quiescent round.
3. Fetch the current ledger and original Issue; verify scope and queued attempt.
4. Resolve capability without downgrade and send claim (or pm-claim) with queue_token.
5. Read the matching workflow receipt artifact. Only claimed:true is a winning claim.
6. Re-fetch the ledger and verify that claim id/actor/instance still belongs to this task.
7. Persist the request id as consumed before launching one substantive invocation.
8. Return through the controller using that claim. Keep all results/evidence discoverable.

Duplicate notifications/receipts never cause another invocation. A crashed or cancelled
transport is diagnosed from the ledger; never reclaim working automatically. Labels are
projections, not a compare-and-swap primitive. Runtime receipt consumption is an adapter
responsibility that must be demonstrated in Round 0 before production use.

## Command payloads

Use tools/agent-bus/client.py send COMMAND payload.json. It calls workflow_dispatch on
main with a unique request id. Keep the same id only for a retry of the exact same command.
All issue/parent numbers are integers. Store no secrets in payloads or public results.

| Command | JSON payload fields | Allowed actor |
|---|---|---|
| authorize | issue | Michael; protected human gate and unchanged snapshot required |
| ready | issue, parent, claim | Working parent lead; original root scope only |
| claim | issue, queue_token, resolved, model, adapter_revision | Configured task role |
| wait | issue, claim | Working root with registered children |
| return / block | issue, claim, result | Current claim owner |
| close-child | issue, claim, result | Parent lead in fan-in; claim is the parent's claim |
| pm-claim | issue, queue_token, resolved, model, adapter_revision | PM at quiescence only |
| pm-close | issue, claim, result | PM's final claim; result is executive synthesis |
| abort | issue, result | Michael; preserves evidence and stops the round |
| reconcile | {} | Cheap maintenance; cannot mint authorization or reclaim work |

result is text or a link to immutable evidence. Worker returns are automatically routed
to their native parent lead; root returns go to PM. Do not supply a new destination.
Parents explicitly close child results before returning. Typed Verification service
results return to the requesting Software/Hardware root, without transferring acceptance
or changing Verification's reporting line. A service cannot delegate further.

## Model routing

Strong = Sol/Opus; balanced = Terra/Sonnet; economy = Luna/Haiku; frontier = Astra
with no asserted Anthropic equivalent. An unmapped class blocks for explicit reassignment.
Actual model names must equal the configured family or use its family-prefix form; adjust
this reviewed mapping to runtime-exposed names during hookup rather than forging an attestation.
No automatic upshift/retry loop is implemented. Workers use economy/balanced only.

## Transport

manual means a supported boundary launch reads its mailbox; it is not an enabled listener.
pr-doorbell requires an open designated signal PR and actual provider trigger support.
The bot comment carries an issue number and queue token after durable dispatch; replaying
it alone cannot authorize work. Prefer a control PR for Verification so no uncovered
implementation is included in its wake context. No particular signal PR or instance is
configured in this delivery. CLI command/receipt plumbing is ready for those adapters.
