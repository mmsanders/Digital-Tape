# Surge and workers — Phase 1 hookup

The full Phase 1 roster is in [phase1-roster.json](phase1-roster.json); follow
[CLOUD-HOOKUP.md](CLOUD-HOOKUP.md) for account setup and real-adapter proof.
Michael selected Grok Bot for Surge and Grok/Grok Bot for workers on 11 September.
OpenAI/Claude worker slots remain disabled reserves. No fallback is automatic.

[Surge manifest](roles/surge.md) · [Worker manifest](roles/worker-grok.md) ·
[Surge adapter](ADAPTER-GROK-SURGE.md) · [Worker adapter](ADAPTER-WORKERS.md) ·
[Round 0 checklist](ROUND0-CHECKLIST.md).

runtimes.proposed.json is a disabled snapshot of the current desired configuration,
not permission to replace verified runtime mappings later. Actual identity and model
strings must be supplied from the provider, not copied from examples.
