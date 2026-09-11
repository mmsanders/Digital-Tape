# Round 0 — Surge + one worker

Harmless, low-cost, non-product tasks only. No purchases, no safety acts, no engine
implementation. Prove adapters, not product acceptance.

Prerequisites: `michael-round-gate` correct; `surge` + one worker enabled; PM (+ any
other roots in the round) bound if the prepared round requires them; no active round
at start.

## Proofs (from ACTIVATION, tailored)

- [ ] **Missing authorization fails closed** — attempt without gate approval / wrong
      environment does not queue real work
- [ ] **Snapshot integrity** — edit round/root after preflight → authorize refuses
- [ ] **Double delivery / claim** — replay same `request_id` → `claimed: false` /
      duplicate; no second substantive invocation
- [ ] **Wrong role** — worker token cannot claim Surge queue (and vice versa)
- [ ] **Worker batch** — Surge (or other lead) `ready`s a child → worker claims →
      `return` with evidence → parent `close-child`
- [ ] **Blocked child** — worker `block` → parent dispositions without silent fuse close
- [ ] **Fan-in / wait** — lead `wait`s; release only when children returned/closed
- [ ] **Quiescence** — all roots returned and children closed → PM barrier appears once
- [ ] **PM final** — one `pm-claim` / `pm-close`; **no automatic next-round restart**
- [ ] **Grok attestation** (if surge or worker-grok enabled) — claim uses real model
      family; unmapped class blocks instead of downgrading

## Evidence to keep

- Authorize run URL + approval actor
- Receipt artifacts for claim/return/close-child/pm-close
- Ledger snapshots showing bindings and empty post-round current
- Adapter revision strings used

After green Round 0, product rounds still need Michael’s per-round authorize approval.
