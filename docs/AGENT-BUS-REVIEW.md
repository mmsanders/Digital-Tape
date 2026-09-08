# Agent Bus / Pages integration review

**Reviewer:** assigned infrastructure integrator, 8 September 2026.
**Inputs:** PR #26 at a5e195dcfda2d6e76bcb40f003f1171ca0b140aa;
Pages branch ed2449e48d1efaa44311e7bf4d02ceae10b40da9; current working agreement.
This is implementation review under Michael's assignment, not independent product acceptance.

| Finding | Disposition |
|---|---|
| Strong mapped to Sonnet; Opus also advertised as frontier without distinct policy | Strong is Sol/Opus. Anthropic frontier is unset; no silent downgrade. One canonical runtime mapping |
| Label-written workflow chain assumes GITHUB_TOKEN events trigger subsequent workflows | Replaced with one explicit workflow_dispatch controller and inline reconciliation |
| Two PATCHes for claims allow concurrent winners and intermediate invalid states | Serialized ledger writes with SHA compare-and-swap, unique queue tokens, per-command receipts and adapter consumption contract |
| Generic bot comments accepted as authorization; mutable roots after approval | Protected environment plus exact pre/post approval snapshot and stored scope/config digest |
| Pure validator early returns bypass authorization/ancestry checks; live shell duplicates policy | Removed obsolete validator/workflows; one tested implementation checks current authorization before claims/returns |
| Only child adapter flags checked; roots could dispatch to missing listeners | All root/PM/child roles require configured, enabled bindings; all shipped disabled |
| Review-kind label alone bypasses self-service eligibility | Eligibility must be approved in root; child evidence and matching eligibility required; blindness remains a human judgment boundary |
| Budget forms ignored below hard ceilings; incomplete state/depth/closed-child checks | Approved budgets enforced, closed children count, exact native hierarchy/scope checked on every active command |
| Fan-in only observes child events; already-returned children can strand a newly waiting parent | Reconcile in the same wait/return/close command |
| Root fuse auto-closes evidence; quiescence insufficiently authenticates tree | Fuse fails closed; explicit dispositions only; validate all tracked tasks and actual child membership |
| Forms use about instead of description and contain invalid unquoted backtick YAML | Replaced with valid GitHub Issue Forms |
| Surge missing from protocol; worker destinations limited to two runtimes | Bounded Surge root plus OpenAI/Claude/Grok worker mailboxes; no instances selected |
| PM dashboard says Cowork; ready treated as queued; workers all assigned to Software | Correct roles and explicit ledger states/native-parent grouping |
| Dashboard guesses activity from branch/commit text; 20s nine-endpoint polling | One receipt snapshot per minute while visible; explicit binding and stale state |
| Issue titles/errors inserted into innerHTML | Text-node rendering with fixed-origin issue links; adversarial title check |
| Dashboard lives only on a stale branch with no main deployment source | Source integrated under dashboard/ and a Pages deployment workflow on main |

## Limits retained deliberately

Trusted main/ledger writers and repository administrators can alter the controller; branch
protection and least-privilege runtime credentials belong to final admin/adapter setup.
There is no claim of cryptographic separation for agents sharing Michael's credentials;
enabled runtime bindings explicitly reject that configuration. Semantic scope fit and
independent-review eligibility cannot be proven solely by syntax checks.

The implementation grants at most one durable claim per queue attempt. Exactly-once model
execution also requires the adapter to persist receipt consumption. There is no automatic
reclamation after a crash and no hidden token-spending retry. No instances are hooked up.

GitHub behavior checked against primary documentation:
[workflow triggering](https://docs.github.com/actions/using-workflows/triggering-a-workflow),
[concurrency and finite queue](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency),
[native sub-issues](https://docs.github.com/en/rest/issues/sub-issues),
[environment protection](https://docs.github.com/rest/deployments/environments), and
[Pages publishing](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).
