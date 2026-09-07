# Working-agreement appendix for Agent Bus activation

> STAGED TEXT. Do not treat this as part of `CLAUDE.md` until the Agent Bus activation change explicitly lands it there.

## Agent Bus — live coordination transport

GitHub Issues are the project's authoritative agent-to-agent transport. See `docs/AGENT-BUS.md`, `.github/agent-bus/ROLE-CONTRACTS.md`, and `.github/agent-bus/capability-tiers.yml`.

### Runtime roles

- Program Manager: **ChatGPT Work**.
- Software Lead: Claude Code.
- Hardware Lead: Claude Code.
- Verification Lead: ChatGPT Work.
- Bounded workers: enabled ChatGPT-chat/Grok or replacement adapters.

Claude Cowork is not part of Agent Bus v1.

### The round barrier

Autonomous work occurs only inside a Michael-authorized Agent Bus round. The PM prepares the round and one root task per participating lead **before** authorization. A protected GitHub Environment is the only mechanism that releases those roots.

During the active round the PM sleeps. Leads fan work out to bounded worker sub-issues and sleep behind the fan-in barrier. When all roots return, the round becomes quiescent and the PM wakes once for executive synthesis. PM may not dispatch another wave until Michael authorizes another round.

### Capability classes

Tasks request `auto`, `frontier`, `strong`, `balanced`, or `economy`, not exact model snapshots. Adapters select the current provider model in the requested class and should record the resolved class/model when exposed.

Current intent: Astra/Opus = frontier; Sol/Sonnet = strong; Terra/Sonnet = balanced; Luna/Haiku = economy. `auto` chooses the lowest sufficient class. Provider model replacements inside a class do not change governance.

PM and Verification normally use strong capability and reserve frontier for freeze, safety, cross-stream architecture, hard arbitration, and comparable high-consequence work. Workers normally use economy/balanced. Automatic upshift loops are prohibited; a PM/Verification phase gets at most one bounded upshift.

### The dispatch bell

**Agents never add `state:queued`.**

A lead requests child dispatch with `state:ready`. The cheap GitHub protocol gate validates round authorization, native parentage, hierarchy, adapter availability and hard cycle/task budgets. Only the bus adds `state:queued`, and expensive runtimes act only after successfully claiming that Issue.

Persistent comment text is never execution authority. A provider-specific bot-authored PR event may be used as an edge-triggered **doorbell** after the bus has queued work, but the runtime must re-read and claim the authoritative Issue before substantive execution.

### Hierarchy

- PM -> lead root only.
- Lead -> direct worker child only.
- Worker -> native parent lead only.
- Lead root -> PM review/blocked only.
- No worker -> PM.
- No lead -> Michael.
- No new root scope inside an active round.

The only lateral service edge is `kind:independent-review` from Software/Hardware to Verification where existing independent-review rules permit self-service. It is not an authority transfer.

### Independent review phrase

The phrase `Request Independent Review` remains useful human-readable intent in a PR, but it is not queue authority. Automated independent review is requested by a native child Issue carrying `kind:independent-review`, linked to the PR, and routed through the Agent Bus gate.

All pre-existing Verification structural rules remain unchanged. In particular, a bus request does not permit implementation inspection before verifier-authored tests where the charter forbids it.

### Token economy

ChatGPT Work and Claude Code are scarce judgment pools. Prefer bounded economy/balanced worker delegation where quality and independence permit. Leads batch fan-out and fan-in; they do not wake on each worker return. PM does not wake on each lead return. Capability-weighted invocation estimates are planning heuristics, not provider billing claims.

### Hard stop

No round completion event starts another round. When PM closes a round after executive synthesis, the entire autonomous system is idle until Michael authorizes the next one.
