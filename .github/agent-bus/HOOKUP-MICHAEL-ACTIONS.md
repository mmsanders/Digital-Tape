# Michael — actions only you can take

Complete in order. Nothing here starts an autonomous product round.

## 1. Gate (done if already confirmed)

In **Settings → Environments → `michael-round-gate`**:

- Required reviewer: **`mmsanders` alone**
- **Allow administrators to bypass** configured protection rules: **off**
- **Prevent self-review**: **off** (you both trigger and approve)

Also ensure a non-protected control environment exists for ordinary commands if the
workflow expects it (`agent-bus-control` on current `agent-bus.yml`).

## 2. Create distinct bot GitHub identities

Create **separate** machine users (or GitHub Apps acting as bots). Do **not** reuse
`mmsanders` for any role actor.

Minimum useful set for Surge + Grok workers:

| Suggested login (examples) | Binds as |
|---|---|
| `dt-surge-bot` (your choice of name) | `surge` |
| `dt-worker-grok-bot` | `worker-grok` |

Optional later: `dt-worker-chatgpt-bot`, `dt-worker-claude-bot`, plus PM/Software/Hardware/Verification bots when those instances are chosen.

Each runtime identity needs, at least:

- Issues: read/write (task envelopes, labels as projections)
- Actions: write (workflow_dispatch via `tools/agent-bus/client.py`)
- Contents: read (ledger on `agent-bus-state`; checkout for adapters)

Ordinary adapters do **not** need to write the ledger directly; the controller does.

Issue a fine-grained or classic PAT per bot. Store secrets only in private credential
stores / Actions secrets — **never** in `runtimes.json`, issues, or the public ledger.

## 3. Fill and merge bindings (no active round)

1. Confirm dashboard/ledger shows **no current round**.
2. Copy [runtimes.proposed.json](runtimes.proposed.json) → replace every
   `REPLACE_WITH_*` placeholder with real logins/instance ids.
3. Leave `enabled: false` until the matching adapter is ready to claim.
4. When an adapter is ready: set that role’s `enabled: true` only.
5. Merge to main. Install job refreshes displayed bindings.

**Grok capability:** leave `providers.grok` all `null` until you have demonstrated
actual model family names. Enabling `surge` or `worker-grok` with provider `grok`
while classes are null will fail closed on capability resolution.

Interim option if you must exercise Surge before Grok attestation: do **not** fake
Grok classes. Either keep Surge disabled, or bind a different provider only if the
**actual** model that runs claims is that provider’s family (truthful attestation).
A Grok Bot runtime should not claim `sol`/`opus`.

## 4. Transport choice

- **`manual` (recommended first):** wake Surge/worker by telling the instance to read
  its mailbox (`python3 tools/agent-bus/client.py mailbox <role>`), then claim.
- **`pr-doorbell`:** open a designated control PR; set `transport.pr` to that number;
  prove the provider actually wakes on the bot comment. Prefer a control PR that
  carries no uncovered implementation for Verification.

## 5. Round 0

After at least `surge` + one worker are enabled with working adapters, run
[ROUND0-CHECKLIST.md](ROUND0-CHECKLIST.md) under your protected approval. Low-cost,
non-product tasks only.
