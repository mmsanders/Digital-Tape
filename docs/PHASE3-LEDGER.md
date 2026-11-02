# Phase 3 ledger — every exit criterion, one row each

**Opened 2 November 2026 PDT ([ADR-201](DECISIONS.md#adr-201--phase-3-opened-round-1-issued)).**
This is the progress record for Phase 3. Each round closes named rows. Plan:
[PHASE3-PLAN](PHASE3-PLAN.md). PM does not accept; states follow independent records.

States:
- **PASSED:** independently passed;
- **IN ROUND:** assigned in a live issue;
- **TO DO:** not yet assigned.

## Spec and entry items

| Item | State | Next |
|---|---|---|
| DRAFT-11 spec revision ([proposal](SPEC-DRAFT-11-PROPOSAL.md)) | IN ROUND | Verification preflight; Hardware speaker value; Michael authorizes |
| Q-P2-1 any-subset completion (365 deferred load faults, 6 long cuts) | IN ROUND | Verification P3-R1 |
| Bench parts list approved and ordered | IN ROUND | Hardware drafts; Michael approves |

## WP-05 — cards and bench parts

| # | State | Next |
|---|---|---|
| A-1 Identity (part number, capacity, revision, CID per card) | TO DO | Needs a reader or rig that reads CID |
| A-2 Sustained write on 80%-filled media | TO DO | Method re-review, then run |
| A-3 Against the C-60 copy requirement | TO DO | After A-2 |
| A-4 Reader not the bottleneck | TO DO | With A-2 |
| A-5 Bench parts support the bench and the rig | IN ROUND | Hardware P3-R1 |
| A-6 Atomicity ≥ 1,000 qualifying cuts per SKU/revision, zero torn | IN ROUND (rig design) | Hardware designs; Verification reviews the method; run after parts arrive |

## WP-17 — firmware skeleton ([FW-1](WP17-FIRMWARE-CONTRACT.md))

| # | State | Next |
|---|---|---|
| F1 Goldens byte-identical on target | IN ROUND | Software builds; Verification authors; target half after parts |
| F2 RAM/stack/.rodata budgets | IN ROUND | CI sizes now; stack high-water on target |
| F3 Warm instant-on < 100 ms | TO DO | Needs the logic analyser |
| F4 Commit latency < 200 ms | TO DO | With recording (WP-19) |
| F5 Play/Stop and removal | TO DO | Bench, Michael witnesses |
| F6 Engine unchanged | IN ROUND | CI tree check |

## WP-18 to WP-21

Criteria are issued with their contracts after round 1:
- WP-18: second slot, copy correctness, progress from the callback.
- WP-19: audio paths, the two output caps, speaker mute, record source.
- WP-20: key reading, depth-sensitive scrub, LED status, record light.
- WP-21: the witnessed bench demo.
