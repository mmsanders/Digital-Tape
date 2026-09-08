# For Michael — current question queue

**Updated: 8 September 2026.** Every review round starts here after refreshing main.
PM records your answers directly; leads do not ask again from archived packets.

## Q-001 — Signed and closed, 8 September 2026

Michael approved the exact scope in [PHASE0-FREEZE.md](PHASE0-FREEZE.md):
“Consider it signed by me, and do what you need to do to represent that in main.”
Do not ask again. Operations/state, implementation acceptance, card qualification
and hardware safety remain separately held.

## M-01 — Print the current packet

The rev-5 [print card](../hardware/packets/wp04-01/CARD.md) and
[plate.stl](../hardware/packets/wp04-01/plate.stl) are on main after #18.
Use the current card: SUPPORTS OFF; four clasp bases have four mating lids.
The repeated D/M/H mechanisms are deliberate blind controls, not accidental duplicates.
Geometry fits the verified 250 × 210 mm bed; estimated print time is about two hours.

**Please return:** whether the plate has been printed, material/brand and staff settings,
and the completed results card. Keep the blind mapping out of the ranking exercise.
If staff access changed, confirm the six-plates/month allowance and whether a failed
print consumes a request. No new printer purchase is proposed.

## M-03 — Parts order: old cart withdrawn

Your direction is recorded: **no 64 GB cards; prefer cheap 4 GB V30; micro or full-size.**
The old six-card ~$115 cart is not approved or checkout-ready.
[Order status](FOR-MICHAEL-ORDER-1A.md) gives the sourcing gap and one documented fallback
for discussion; no purchase or capacity substitution is authorized.

The bench cart is also an estimate pending exact-part/timing review, not permission
to charge a cell or fabricate a board. Every purchase still comes to you.

## Verification handoff

Please pass [the current verification brief](REVIEW/verification-lead.md) for independent
disposition of the raw mount observations and planning the still-uncovered tests.
The brief is on main; no need to repaste historical instructions.

## Already settled

- PM commits its own spec/dispositions/briefs; leads read main.
- Context resets should start from START-HERE and the current role brief.
- No printer purchase; use library plates.
- Cartridge uses a clasp, with no sustained closed-position preload.
- Safety measurements: you witness, Verification audits method/raw data/uncertainty.
- Vendor access is environment-specific; leads must recheck their own tools before
  asking you to change access. The old blanket “all vendor domains blocked” claim
  is not a current project-wide fact.


## Agent Bus — final setup boundary

Signaling infrastructure and the [Pages dashboard](https://mmsanders.github.io/Digital-Tape/)
are deployed. Particular instances remain unbound as requested.
Before authorizing any round, create **michael-round-gate** in repository Settings →
Environments, require **mmsanders alone** as reviewer, and disable administrator bypass.
The connected tools cannot change that admin setting; the controller refuses to run a
round without it. Pages itself is configured and deployed successfully.

Then choose actual instances/adapters with the [hookup checklist](../.github/agent-bus/ACTIVATION.md).
No API purchase, token-bearing browser UI, automatic model listener or autonomous round
has been introduced. Strong capability is Sol/Opus; unavailable classes block explicitly.
