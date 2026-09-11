# Connect the Phase 1 cloud leads

Prepared 11 September 2026. Account setup and real runtime binding are not complete.
Use [the roster](phase1-roster.json) and the [six role manifests](roles/). Cloud-hosted
means the service can resume without Michael's laptop; it does not mean a model should
spend tokens continuously while no approved work is queued.

## Create six named instances

| Name | Surface | Selection | Paste this manifest |
|---|---|---|---|
| DT PM | ChatGPT Work on web | Astra | [pm.md](roles/pm.md) |
| DT Software Lead | Claude Code cloud routine | Opus | [software.md](roles/software.md) |
| DT Hardware Lead | Claude Code cloud routine | Opus | [hardware.md](roles/hardware.md) |
| DT Verification Lead | Separate ChatGPT Work web context | Sol | [verification.md](roles/verification.md) |
| DT Surge Lead | Grok Bot | Actual Grok model to attest | [surge.md](roles/surge.md) |
| DT Grok Worker | Separate Grok Bot or verified cloud Grok adapter | Economy/balanced mapping to attest | [worker-grok.md](roles/worker-grok.md) |

Do not start hourly model polling merely to make the accounts appear connected. First
run each manifest's setup-only bootstrap. Return the instance URL/id, actual model id,
GitHub actor, wake mechanism and durable receipt storage. Paste no tokens into chat or Git.

## ChatGPT Work: PM and independent Verification

Create two separate web Work chats/projects and select Astra for PM and Sol for
Verification in the model switcher. Connect authorized GitHub access and paste the
matching bootstrap. Keep Verification's inputs limited to issued specs and independent
test evidence; do not clone/load uncovered implementation as startup context.

Web tasks support cloud app-event triggers, and an in-chat task can reuse that chat's
context. Desktop local tasks need the computer running. Codex CLI/IDE do not supply the
web Scheduled interface. An ordinary chat being open is not an inbound listener.
[Official web tasks guide](https://learn.chatgpt.com/docs/automations)
[Official model selection](https://learn.chatgpt.com/docs/models)

**Known gap:** the GitHub event schema exposed to this PM session supports created HUMAN
PR comments, not a certified github-actions[bot] comment wake. Its automation creation
interface also does not select Astra/Sol or bind a different chat. Do not create a
repo-wide automation here and call it the new PM or independent Verification lead.
Create the task in the chosen role context only after proving its supported exact event.
The current bot-comment doorbell therefore remains uncertified for Work.

If that surface cannot provide authenticated commands and the required event trigger,
report the gap. A separately authenticated relay/Workspace Agent or hosted API adapter
is a possible follow-up, not something already deployed or included in chat credits.
Do not substitute one without Michael selecting the account/surface and any new spend.

## Claude Code: Software and Hardware

Open [Claude Code routines](https://claude.ai/code/routines). Create two routines with
the names above, select **Cloud**, **Opus**, Digital-Tape and the corresponding saved
bootstrap instructions. Use separate cloud environments for role credentials/workspaces.
Keep recurring triggers off during setup. Include only needed connectors.

Routines run on Anthropic-managed infrastructure, expose a model selector, and create a
fresh session per firing. API triggers have a per-routine URL/token; GitHub triggers
support PR events with filters. The documented event list does not establish a comment-
created wake for our existing doorbell. Prefer a verified API trigger through a cheap
adapter once configured; save its secret in a private credential store, never the repo.
[Official routines setup](https://code.claude.com/docs/en/routines)

**Identity gap:** Claude's normal connected GitHub actions appear as your account.
That is not the distinct bus actor. The role's adapter must authenticate command dispatch
as its own registered bot identity. Merely exporting BUS_ACTOR does not change the
workflow's github.triggering_actor. Prove the actual actor from a harmless dispatch.
Cloud branch-push permissions may also be narrower than normal Software merge authority;
verify an authorized integration path rather than assuming the clone token can merge.

## Grok Bot: Surge and workers

Create separate Bots named DT Surge Lead and DT Grok Worker, edit their profiles and
paste the corresponding manifests. Connect GitHub and have each report its real model,
command transport and available account event integration. Grok Bot has persistent cloud
computers; event routines are available where supported, and account integrations are
separate from plugins. Test the exact wake before enabling it.
[Create Bots](https://docs.x.ai/grok-bot/bots)
[Cloud operation](https://docs.x.ai/grok-bot/overview)
[Routine triggers](https://docs.x.ai/grok-bot/skills-routines-and-automations)

Bots in one account share a computer, files and logins. Separate names alone are not
credential or Verification isolation. Use a role-authenticated adapter; do not leave
multiple role tokens or independent test context readable on a shared implementation
computer. If the service cannot isolate secrets, a separate account or scoped remote
credential service is required. Ordinary Grok chat alone is not a proven hosted worker.
Grok classes stay null until actual model/capability evidence exists; never claim Sol/Opus
just to satisfy the bus. No OpenAI/Claude worker fallback is authorized by this roster.

## Bind only after evidence exists

1. Keep Michael's human gate: sole reviewer mmsanders, no admin bypass, self-review allowed.
   It was verified on 9 September; do not recreate it.
2. Provide distinct non-human GitHub actors for the six roles. A GitHub App per role or
   properly provisioned machine identity is an option, but prove its actual dispatch
   identity before entering it. Needed bus permissions: Contents read, Issues read/write,
   Actions write. Code integration rights are separate. No role receives human approval.
3. Complete the roster's instance/actor/trigger/adapter evidence fields. Set actual
   runtimes actor/instance/provider/transport, keeping enabled false during preparation.
   Read-only `python3 tools/agent-bus/binding_readiness.py` lists remaining gaps.
4. Align provider family strings with actual IDs (for example the documented OpenAI
   gpt-6-astra / gpt-5.6-sol names). The existing short families are not interchangeable
   with arbitrary provider IDs. Preserve truthful tier assignment and rerun regressions.
5. The cheap adapter checks the mailbox, obtains the exclusive claim, durably consumes
   its receipt, then launches one substantive model turn and routes the return. A native
   routine that starts an LLM before checking the claim can cost tokens for empty or
   duplicate events; it is not proof of pre-model deduplication. Capture this distinction.
6. With no active round, enable only ready roles for a harmless **real-adapter Round 0**
   under Michael's gate. Test actual actor isolation, duplicate delivery/launch, cloud
   resume after closing the phone/laptop, model selection, returned artifacts and cleanup.
   Enablement is necessary to claim in Round 0; it does not itself license product work.
7. Record Round 0 evidence and only then start Phase 1 product rounds. Reassess at Phase 1 exit.

Supported transports in the current controller are manual and pr-doorbell. A routine URL,
MCP connection, or callback written into this document is not an implemented third transport.
No cloud relay, routine, external account, or live listener was provisioned by this document.
