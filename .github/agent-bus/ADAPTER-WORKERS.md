# Adapter — workers accepting Surge / lead delegation

Phase 1 worker: `worker-grok` (Grok/Grok Bot). `worker-chatgpt` and `worker-claude`
remain disabled reserves. Start with one bound worker mailbox; parallel instance pools
require a separately designed and tested identity/claim boundary.

Capability band: **economy** and **balanced** only (auto → economy).

## Delegation path

1. Lead root (Software / Hardware / Verification / Surge) is authorized and claimed.
2. Lead creates a native child issue under that root (title/body = work envelope).
3. Lead sends `ready` → controller validates ancestry, budgets, destination → child
   becomes `queued` with a `queue_token`.
4. Worker wakes (manual mailbox or tested doorbell), claims with its bound actor.
5. Worker returns `return` or `block` with evidence; destination is the parent lead.
6. Parent `close-child` with disposition; only then may the root return to PM.

A typed Verification **service** child is separate (Software/Hardware only, within
approved eligibility). Workers do not host independent-review services.

## Binding checklist (each worker)

- [ ] Distinct bot GitHub login (not Michael, not shared across roles)
- [ ] PAT/App creds with Issues R/W + Actions write + Contents read
- [ ] `runtimes.json`: actor, instance, provider, transport filled
- [ ] Provider capability classes non-null for economy (and balanced if used)
- [ ] Adapter implements claim/receipt consume-once
- [ ] Ready adapter/bindings first; enable only for gated harmless Round 0, then prove a claim
- [ ] Product work only after Round 0 evidence has been reviewed
- [ ] Documented in Round 0 evidence

## worker-grok specific

`providers.grok` is currently all `null`. Do **not** enable `worker-grok` until the
adapter can attest real model family strings for at least `economy` (and `balanced`
if requested). Until then, leave the role disabled; do not silently substitute another provider.

## worker-chatgpt / worker-claude

Inactive for this trial. Any future reassignment requires Michael and truthful
provider mappings. Shared Grok implementation workers cannot author blinded independent
tests; see docs/PHASE1-AGENT-TRIAL.md.
