# Software lead — Claude Code cloud setup evidence

**Recorded 11 September 2026 against main `feb5fd9c1634d9e3e439165ec1abec2ee9d92b68`.**
Setup-only bootstrap return required by [the Software manifest](roles/software.md) and
[the cloud hookup checklist](CLOUD-HOOKUP.md). Prepared by the instance described in §1.

## Scope of this document

This records what one Claude Code cloud instance can and cannot do, so Michael can
decide about binding. It is **not** a binding, a claim, a round, an acceptance, or a
capability attestation the controller would honour. `runtimes.json`,
`phase1-roster.json` and the `agent-bus-state` ledger are unchanged; `software` remains
`enabled: false` with null actor and instance. No product work was performed, no
uncovered implementation was inspected, no listener was activated, and no credential
is reproduced here. `binding_readiness.py` still reports `ready_for_binding_review: false`.

## 1. Instance

| Field | Value |
|---|---|
| Surface | Claude Code cloud session, `environment_kind: anthropic_cloud` |
| Session id | `session_01QrXdKt7NkQjw17V5q84rAi` |
| Instance URL | `https://claude.ai/code/session_01QrXdKt7NkQjw17V5q84rAi` |
| Environment id | `env_01NT3oPz6HjiN45HoSaxXUeG` |
| Origin | `web_claude_ai` (a chat-started session) |
| Permission mode | `auto` |
| Working checkout | `mmsanders/Digital-Tape`, branch `claude/blissful-cray-g15q7o` |

**This is a session, not a routine.** CLOUD-HOOKUP asks for a named
`DT Software Lead` routine created at `claude.ai/code/routines` with Cloud + Opus
selected. Listing this account's routines returns an empty set: **zero routines exist**.
So there is no per-routine URL, no per-routine token and no `trigger_id` to record.
A running chat session is not the cloud-resumable role instance the roster describes.

## 2. Model

Reported by the session-description tool, not asserted from training:

- `session_context.model`: the Opus 5 identifier `claude-opus-5`
- `external_metadata.last_served_model`: `claude-opus-5`
- `external_metadata.user_switched_model`: `claude-opus-5`
- `configured_model`: `claude-fable-5-1` — the creation-time value; the session was
  switched afterwards. Both are recorded because the two disagree and the roster's
  model selection must be truthful about which one served the turn.

The capability class requested for `software` is **strong**, which `runtimes.json`
maps to the `anthropic` family string `opus`.

**The runtime-exposed id does not attest that family.** `bus.capability()` requires
`model == family or model.startswith(family + '-')`. Checked directly against the
committed mapping with a synthetic enabled role (no repo file modified):

| Model string offered | Result |
|---|---|
| `opus` | attests |
| `opus-5` | attests |
| `claude-opus-5` | **rejected** — `actual model does not attest configured capability family` |
| `claude-sonnet-5` | rejected |
| `claude-fable-5-1` | rejected |

A truthful `claim` from this surface therefore fails closed today. This is the
misalignment CLOUD-HOOKUP step 4 anticipated: the reviewed short families are not
interchangeable with the providers' real ids, and the documented OpenAI ids
(`gpt-6-astra`, `gpt-5.6-sol`) would fail the same check against `astra` / `sol`.
Fixing it means adjusting the reviewed mapping to runtime-exposed names and rerunning
the bus regressions — **not** sending `opus` as a cosmetic attestation. That mapping is
PM/Michael's to approve, so it is reported rather than applied.

## 3. GitHub dispatch method and authenticated identity

**Identity: this instance authenticates as `mmsanders` (user id 78818921) — Michael's
own account.** That is a blocker, not a detail. ROLE-CONTRACTS universal adapter
boundary rule 1 says "Use a distinct GitHub identity ... Never Michael's identity."
CLOUD-HOOKUP predicted this ("Claude's normal connected GitHub actions appear as your
account. That is not the distinct bus actor"), and it is now confirmed rather than
assumed. No `github_actor` value can honestly be entered in the roster from here.
Because every dispatch this instance could make would carry that identity, no further
harmless-dispatch proof was run; it could only re-confirm the same wrong actor.

**Transport: `tools/agent-bus/client.py` does not run on this surface.** Both its
`send` and `mailbox` subcommands shell out to `gh`, and the `gh` CLI is **not installed**
in this container (`gh: command not found`); no `hub` either. The CLI plumbing that
ACTIVATION describes as ready is ready for adapters that have `gh`, which this one lacks.

Working substitutes that exist here:

- **Dispatch** — the GitHub MCP `actions_run_trigger` tool, `method: run_workflow`,
  `workflow_id: agent-bus.yml`, `ref: main`, supplying the workflow's three declared
  inputs (`command`, `request_id`, `payload`). Not exercised: it would dispatch as
  `mmsanders`.
- **Mailbox read** — `git fetch origin agent-bus-state` and read `state.json` from that
  ref. Done read-only for this report; it confirms all roles `enabled: false`,
  `software` provider `anthropic`, transport `manual`, ledger empty of receipts.

So the role's command path is reachable in principle but **fails the identity
requirement**, and the shipped client is unusable without either `gh` or a
GitHub-MCP-based equivalent.

## 4. Supported event trigger

No routine exists, so no routine trigger could be tested. Wake mechanisms actually
available to this session, with what each does and does not prove:

| Mechanism | What it is | Bus relevance |
|---|---|---|
| PR activity subscription | Wakes this session on PR comments, CI results and reviews | Closest thing to a doorbell, but it is a **session** subscription that dies with the session, and it is not a certified `github-actions[bot]` comment wake |
| Inbound webhook | Per-session URL plus sealed credential; POST wakes the session | Ends when the session ends; must be re-created on resume |
| Scheduled routine / one-shot reminder | Cron or single future wake into this or a fresh session | A timer, not an event trigger; polling on a timer is what CLOUD-HOOKUP tells us not to do to look connected |

None of these is the `pr-doorbell` transport the controller supports: that needs an open
designated signal PR **and** proven provider trigger support for the bot comment that
carries the issue number and queue token. The documented routine feature set (API
trigger with per-routine URL/token; GitHub PR event triggers with filters) remains
**unverified** here because no routine was created. The uncertified bot-comment
doorbell gap recorded for the Work surface is therefore unresolved for this surface too.

## 5. Durable receipt-consumption storage

**None is provisioned. This is the deepest blocker of the five.**

ROLE-CONTRACTS step 7 requires the adapter to persist the request id as consumed
*before* launching one substantive invocation, and states plainly that duplicate
notifications or receipts must never cause another invocation. This instance has:

- an **ephemeral container** — the filesystem is reclaimed after inactivity or when the
  session ends, so nothing written to disk survives to deduplicate a later wake;
- **no bound credential store, key-value store or private gist** for consumed ids;
- a **fresh session per routine firing** by design, which means a routine-based binding
  starts with no memory of what it already consumed.

Worse for the design, and exactly the distinction CLOUD-HOOKUP step 5 asks us to
capture: **a native Claude routine wakes the model first and could only check the claim
afterwards.** That inverts the required order. It is not a cheap pre-model adapter, it
cannot demonstrate pre-model deduplication, and it would spend a substantive turn on
empty or duplicate events. Round 0's "double delivery / claim" proof cannot pass on a
native routine alone.

The only durable stores reachable from here are the repository and the ledger branch —
both written through the controller as `mmsanders`, and neither a pre-model consumption
record.

## Blockers, in the order they must be cleared

1. **Distinct non-human actor.** Provide a GitHub App or machine identity for
   `software` with Contents read, Issues read/write, Actions write, and prove its real
   dispatch identity. Until then rule 1 is violated by construction.
2. **Cheap pre-model adapter with durable state.** A native routine cannot satisfy
   steps 5-7. Something outside the model must read the mailbox, claim, durably record
   the request id, and only then launch one turn.
3. **Model family mapping.** Align `runtimes.json` families with runtime-exposed ids
   (both providers), then rerun the bus regressions. PM decision; not applied here.
4. **Client transport.** Either install `gh` in the role's cloud environment or add a
   supported non-`gh` path, so `client.py` works where the role actually runs.
5. **Role instance shape.** Create the named cloud routine if a routine is the intended
   binding, or record that the role binds as a session and accept that its
   subscriptions and webhooks do not survive session end.

Item 3 is a small documented change. Items 1, 2 and 5 are account and design work that
this instance cannot perform for itself, and item 2 in particular is not something more
prompting can fix.

## Integration-path caveat

CLOUD-HOOKUP warns that cloud branch-push permissions may be narrower than normal
Software merge authority. Not established either way in this report: this session pushed
a branch and opened a draft PR for this document, which demonstrates branch write, and
demonstrates nothing about merge rights. Verify an authorized integration path before
assuming the clone token can merge.

## Reproduce

```
python3 tools/agent-bus/binding_readiness.py        # still ready_for_binding_review: false
git fetch origin agent-bus-state                    # ledger: all roles enabled: false
command -v gh                                       # absent on this surface
```

The model-attestation table is reproduced by calling `bus.capability()` with a
deep-copied config whose `software` role is enabled, passing each model string; the
committed `runtimes.json` is not modified. `runtimes.proposed.json` is byte-identical to
`runtimes.json`, so it does not already carry the mapping fix.

## Standing holds unchanged by this document

PR #20 stays held at its coverage boundary. Tests-before-implementation, Verification
blindness, the missing WP-11 goldens gate and the closed hardware fabrication gate are
untouched. No round is authorized; `michael-round-gate` could not be inspected from this
surface and STATUS records it as still absent.
