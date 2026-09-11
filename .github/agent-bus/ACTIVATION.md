# Infrastructure installation and final instance hookup

**Michael authorized infrastructure integration on 8 September and cloud hookup on
11 September 2026.** Instances remain unbound pending account credentials and adapter proof. This supersedes the staged activation checklist.

## Installed by the integration

- Controller and tests on main; explicit workflow_dispatch commands.
- Label/bootstrap job and agent-bus-state receipt ledger, initialized empty.
- Dashboard source on main and Pages workflow.
- Role contracts, immutable approval snapshots, claims, barriers and bounded fuses.
- Sol/Opus strong mapping; Surge and three worker mailboxes.

Deployment evidence and the remaining repository-admin prerequisite are recorded below.
No queued work or active autonomous round is created merely by installing infrastructure.

## Repository-admin prerequisite — verified 9 September 2026

Michael configured the protected environment and the install/inspect job verified it.
Retain michael-round-gate with **mmsanders as its sole required reviewer**
and **administrator bypass disabled**. Leave **Prevent self-review off**, because Michael
both triggers and approves authorization. Do not grant runtime credentials approval authority.
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

## Bind particular instances

Start with [CLOUD-HOOKUP.md](CLOUD-HOOKUP.md) for all six Phase 1 instances and
[phase1-roster.json](phase1-roster.json) for required evidence. The September 9 simulated
plumbing test passed; it does not certify real provider wakeups or role identities.

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


## Verified rollout — 8 September 2026

- PR #26 merged as e509a6adf0b47141369f0fa55af05a68d8dd7ebd.
- [Install run 34216859686](https://github.com/mmsanders/Digital-Tape/actions/runs/34216859686)
  succeeded: labels created and empty ledger initialized at agent-bus-state commit
  9a659a56075d604b12e10f1da38ebfce224e9991. Fresh ledger read confirms all eight roles
  disabled, null actor/instance bindings, no current round, no tasks and no receipts.
- [Pages run 34216859708](https://github.com/mmsanders/Digital-Tape/actions/runs/34216859708)
  deployed successfully to https://mmsanders.github.io/Digital-Tape/.
  Authenticated inspection confirmed build_type=workflow, public=true and HTTPS enforced.
  No Pages settings change is outstanding. Direct HTTP checks returned 200 for the
  page, app.js and model.js, each byte-identical to dashboard/ on merged main.
- [Regression run 34216859567](https://github.com/mmsanders/Digital-Tape/actions/runs/34216859567)
  passed 25 controller cases, 6 dashboard cases and actual Chrome checks at 1280px/390px:
  eight cards, no horizontal overflow, injected issue title rendered safely as text.
- Product engine/spec/test checks remain green except the previously missing WP-11 goldens.
- **Gate:** Michael confirmed `michael-round-gate` exists (10 September 2026). Re-verify
  sole reviewer + admin bypass off before authorize if settings may have drifted.
- **Still deferred until hookup:** particular instance identities, inbound adapters,
  designated signal PRs and the protected real-adapter Round 0. See
  [HOOKUP-SURGE-WORKERS.md](HOOKUP-SURGE-WORKERS.md). No autonomous work ran from this note.

## Approving from the dashboard

The Round approval panel links directly to waiting authorize runs on main. Select
**Review approval in GitHub**, inspect the preflight scope, then **Review deployments →
michael-round-gate → Approve and deploy** while signed in as mmsanders. The fallback
**Open approval workflow** link works even when public API discovery is rate-limited.
The panel checks every 60 seconds while visible, independently of the ledger; a pending
authorization need not yet exist in the ledger. Waiting-run discovery is informational,
not proof that a particular environment is awaiting review; GitHub is authoritative.

Pages holds no credentials and cannot set an approval flag or approve on your behalf.
Direct approval within Pages would require a separately authenticated application.
See [GitHub's approval instructions](https://docs.github.com/en/actions/managing-workflow-runs/reviewing-deployments).
