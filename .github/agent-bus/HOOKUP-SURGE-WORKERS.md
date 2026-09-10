# Agent Bus — Surge + worker hookup package

**Status:** draft for Michael · 10 September 2026 · no roles enabled · no Round 0 run

This package is the deferred “bind particular instances” step from
[ACTIVATION.md](ACTIVATION.md). It does
**not** authorize work, map Grok capability classes, or replace live
`runtimes.json`. Land via this PR, then complete
[HOOKUP-MICHAEL-ACTIONS.md](HOOKUP-MICHAEL-ACTIONS.md) before enabling anything.

## What this unlocks

| Role | Intent |
|---|---|
| `surge` | Grok Bot as Surge Support: bounded proposal/analysis; PM dispositions; no merge/acceptance |
| `worker-chatgpt` / `worker-claude` / `worker-grok` | Economy/balanced workers that accept child tasks from Surge and other leads |

Hierarchy stays: Michael → PM → Software / Hardware / Verification / Surge → workers.
Results climb one level. Verification independence is unchanged.

## Files

| File | Purpose |
|---|---|
| [HOOKUP-MICHAEL-ACTIONS.md](HOOKUP-MICHAEL-ACTIONS.md) | Only the human-required steps |
| [runtimes.proposed.json](runtimes.proposed.json) | Proposed shape; all `enabled: false` |
| [ADAPTER-GROK-SURGE.md](ADAPTER-GROK-SURGE.md) | Claim/receipt adapter recipe for Grok-hosted Surge |
| [ADAPTER-WORKERS.md](ADAPTER-WORKERS.md) | Worker delegation + binding checklist |
| [ROUND0-CHECKLIST.md](ROUND0-CHECKLIST.md) | Harmless Round 0 proofs (Surge + one worker) |

## Hard rules (do not waive)

1. Role `actor` must be a **distinct non-human** GitHub identity — never `mmsanders`.
2. Grok `providers.grok` classes stay **null** until an adapter attests real model families.
3. No work without a winning `claimed:true` receipt for that `request_id`.
4. Merge runtime bindings only with **no active round**.
5. No live product round until Round 0 passes on the **real** adapters.

## Suggested landing

1. Docs live under `.github/agent-bus/` in this PR.
2. ACTIVATION.md links here from “Bind particular instances”.
3. Keep live `runtimes.json` disabled until bot logins exist and placeholders are replaced.
