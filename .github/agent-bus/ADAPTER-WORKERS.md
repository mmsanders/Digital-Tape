# Adapter — workers accepting Surge / lead delegation

Workers: `worker-chatgpt`, `worker-claude`, `worker-grok`.

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
- [ ] `enabled: true` only after a dry claim against a harmless queued task
- [ ] Documented in Round 0 evidence

## worker-grok specific

`providers.grok` is currently all `null`. Do **not** enable `worker-grok` until the
adapter can attest real model family strings for at least `economy` (and `balanced`
if requested). Until then, leave the role disabled and use chatgpt/claude workers
for Round 0 if needed.

## worker-chatgpt / worker-claude

Use existing OpenAI/Anthropic mappings (luna/haiku economy; terra/sonnet balanced).
Attest actual runtime model names against those families at claim time.
