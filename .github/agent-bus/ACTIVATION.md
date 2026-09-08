# Infrastructure installation and final instance hookup

**Michael authorized infrastructure integration on 8 September 2026.** Particular
agent instances are deliberately unbound. This supersedes the staged activation checklist.

## Installed by the integration

- Controller and tests on main; explicit workflow_dispatch commands.
- Label/bootstrap job and agent-bus-state receipt ledger, initialized empty.
- Dashboard source on main and Pages workflow.
- Role contracts, immutable approval snapshots, claims, barriers and bounded fuses.
- Sol/Opus strong mapping; Surge and three worker mailboxes.

Deployment evidence and any repository-admin prerequisite are recorded below after rollout.
No queued work or active autonomous round is created merely by installing infrastructure.

## Repository-admin prerequisites before any autonomous round

The connected repository tools cannot configure protected environments. In Settings →
Environments create michael-round-gate with **mmsanders as its sole required reviewer**
and **administrator bypass disabled**. Do not grant runtime credentials approval authority.
The controller checks these exact properties and refuses authorization if absent.
Michael must trigger the authorize workflow on main and review its preflight snapshot,
then approve the deployment. Preparing issues is not approval.

Use normal protected-main review and restrict writes to agent-bus-state/control-plane code
to trusted automation/administrators. Runtime identities need Issues read/write and Actions
write for command dispatch; ordinary adapters do not need to write the ledger directly.
Implementation branch credentials must preserve the project's normal integration controls.
An administrator remains a trusted principal; this is not a sandbox against that principal.

Pages must use GitHub Actions as its publishing source. The existing gh-pages branch is
historical; dashboard/ on main is the maintained source. Do not edit two independent copies.

## Bind particular instances — explicitly deferred to the next step with Michael

1. Pick actual PM/Software/Hardware/Verification/Surge and worker instances. Keep roles separate.
2. For each enabled role, set actor (distinct non-human GitHub identity), instance id, provider
   and transport in runtimes.json. Leave unavailable roles disabled. Do not share Michael's identity.
3. Map provider-exposed model names/classes truthfully. Grok stays unmapped until demonstrated.
   Strong is Sol/Opus; an unavailable frontier request blocks instead of downgrading.
4. Configure manual boundary launch or a tested pr-doorbell with a designated open control PR.
   No generic chat invocation or unsupported inbound trigger is assumed to exist.
5. Implement the cheap pre-invocation claim/receipt-consumption step from ROLE-CONTRACTS.md.
   PM listens only at quiescence; leads wait behind fan-in. Do not wake a lead for each child.
6. Merge configuration only with no active round. The install job refreshes displayed bindings.
7. Run one harmless Round 0 after Michael approves its exact snapshot: prove missing authorization,
   double delivery/claim, wrong role, a worker result batch, blocked-child disposition,
   quiescence, one PM final claim and no next-round restart. Verify the actual provider adapter,
   not just controller unit tests. Use low-cost non-product tasks with no purchases or safety acts.

All agent instances and signal PRs are currently unbound. No adapter is certified by this
infrastructure-only delivery; it creates no independent product acceptance.
