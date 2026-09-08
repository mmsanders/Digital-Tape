# Agent Bus — bounded rounds and auditable claims

**Infrastructure v2, 8 September 2026.** Michael authorized integration after signing
Phase 0. Particular agent instances remain unbound; no model is launched by this code.
[Dashboard](https://mmsanders.github.io/Digital-Tape/) · [review findings](AGENT-BUS-REVIEW.md)
· [instance hookup](../.github/agent-bus/ACTIVATION.md)

## Authority and hierarchy

Michael → PM → Software / Hardware / Verification / bounded Surge → workers.
Results return one level upward. Surge has no normative or acceptance authority.
Verification retains its reporting line, independence and test-before-code boundary.
A typed Software/Hardware → Verification service is permitted only within the eligibility
approved in the root before the round. A task label never waives those restrictions.

Issue title/body and native sub-issue parentage define the work envelope. Authorization,
frozen scope hashes, dispatch cycles and exclusive claims are recorded in state.json on
the agent-bus-state branch. Labels are a recoverable projection of those receipts;
comments and the dashboard are observations, not authority. Trusted repo administrators
and anyone able to replace the control-plane code/ledger remain inside the trust boundary.
Distinct runtime identities prevent ordinary cross-role commands; this is not a security
sandbox against a malicious repository administrator.

## One controller, explicit commands

The old four-workflow label chain is replaced by .github/workflows/agent-bus.yml.
Every mutation runs in one serialized job group with queue:max (up to 100 pending jobs)
and uses the GitHub Contents SHA compare-and-swap before publishing labels or a receipt.
No shell interpolates issue content. Events written with GITHUB_TOKEN need not trigger
another workflow: each command completes its own fan-in/quiescence reconciliation.
No polling agent, automatic retry loop, or paid model listener is installed.

The workflow runs trusted main code. Commands from other refs do not execute. A protected
authorization job runs the exact preflight commit and rejects any change to its approved
round, root membership, title/body, capabilities or runtime policy while approval waited.
Every later claim checks the stored scope and parentage again. Edited/reparented/closed
work fails closed. Arbitrary label changes cannot authorize or claim it.

PM prepares one open draft round and at most one root per participating lead. All roots
and PM must have enabled bindings before authorization. Michael requests authorize and
approves the protected michael-round-gate environment. It must list Michael alone as
reviewer with admin bypass disabled. A missing environment never silently authorizes work.
The controller releases the approved roots and stores the exact approval digest/run.

Leads claim, create native child issues inside approved scope, and submit ready commands
with their root claim. The controller validates ancestry, enabled destination, capability,
approved child/review budgets and dispatch fuse. After fan-out the lead uses wait. Only
when every direct child has returned review/blocked or been closed does one fan-in queue
release occur. Leads explicitly disposition children before returning to PM. Fuses never
silently close evidence or create another invocation.

After every root returns and all children are closed, PM gets one quiescent-round claim.
PM closes it with an executive summary. No completion event starts another round.
Missing results or exhausted fuses stay visible; Michael can abort with a recorded reason.

## Claims and retries

A queue token identifies one dispatch attempt. The runtime submits claim with that token,
a unique request_id, resolved capability, actual model family/name and adapter revision.
Only the configured destination identity can win. The committed receipt has claimed:true
for the winning command; a duplicate request returns claimed:false. Reusing an id for
different content is rejected. Another claim after the queue is consumed fails.

The adapter must consume a winning receipt at most once, persist its consumed request id,
and re-read the ledger before substantive work. A successful label PATCH is never a lock.
There is no automatic lease expiry or stale-working reclamation. A transport failure after
a committed claim needs diagnosis using the receipt/ledger, not another model launch.
GitHub concurrency has a finite queue and no total ordering guarantee; a cancelled request
may be retried with the same request id. Never treat a cancelled run as a successful claim.

## Capability and budget policy

Canonical runtime/model mapping: .github/agent-bus/runtimes.json.
OpenAI: frontier Astra, strong Sol, balanced Terra, economy Luna.
Anthropic: strong Opus, balanced Sonnet, economy Haiku. Frontier is deliberately unmapped;
no provider downgrade is hidden behind the frontier label. Grok is unmapped until its
adapter can attest actual classes. These are project routing choices, not model rankings.

Auto uses economy for workers and strong for leads/PM. Explicit high-consequence work
requires frontier for leads/PM; an unavailable class blocks for deliberate reassignment.
Ordinary workers can explicitly request balanced; they cannot select strong/frontier.
PM/Verification accept strong/frontier only. Model family attestations cannot downgrade
an explicit request. Provider credentials and secrets never belong in the public ledger.

Approved total child budget defaults to 6, hard maximum 12 (including closed tasks and
review services). Independent services default to 1, hard maximum 2. All task claims have
a three-dispatch ceiling including root fan-in. There is no automatic capability upshift;
a failed choice returns for deliberate replanning, avoiding oscillation and extra calls.
A completed round does not automatically authorize a follow-on round.

## Runtime transport and dashboard

The cheap client is tools/agent-bus/client.py. workflow_dispatch carries structured JSON
commands. Mailbox reads return queued receipts for one role; PM reads only quiescent rounds.
Adapters may use a manual boundary launch or a configured PR doorbell. A PR doorbell is
emitted only after a durable queued receipt and contains a unique queue token. It never
contains product implementation for Verification to inspect. Provider support for inbound
PR events must be tested at hookup; it is not assumed to exist for ordinary chat sessions.

The Pages dashboard is maintained under dashboard/ on main and deployed by pages.yml.
It reads one public ledger snapshot every 60 seconds while visible. It shows binding
status, native-parent worker groups, distinct ready/queued states, cycles, capability and
explicit stale/error state. It does not infer agent liveness or usage from PRs/commits,
or expose a browser token or write control. Text is rendered as text nodes.

## Reproduce

    python3 -m unittest discover -s tools/agent-bus -p 'test_*.py' -v
    node --test tools/agent-bus/test_dashboard.cjs

These are infrastructure regression tests, not independent product acceptance.
GitHub installation/deployment and the remaining admin/instance setup are recorded in
ACTIVATION.md. Do not declare a live autonomous round until its harmless Round 0 proves
the protected human gate, each adapter claim and final no-restart condition.
