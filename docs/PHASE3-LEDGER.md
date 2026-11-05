# Phase 3 ledger — every exit criterion, one row each

**Opened 2 November 2026 PDT ([ADR-201](DECISIONS.md#adr-201--phase-3-opened-round-1-issued)).**
This is the progress record for Phase 3. Each round closes named rows. Plan:
[PHASE3-PLAN](PHASE3-PLAN.md). PM does not accept; states follow independent records.

States:
- **PASSED:** independently passed;
- **IN ROUND:** assigned in a live issue;
- **TO DO:** not yet assigned.
- **BLOCKED:** a named unresolved prerequisite prevents the criterion from passing.

PM #661 review (4 November): [ADR-206](DECISIONS.md#adr-206--own-hardware-integration-retain-census-and-review-regression-provenance).
States cite independent results; candidate evidence is not merged implementation or package acceptance.

## Spec and entry items

| Item | State | Next |
|---|---|---|
| DRAFT-11 spec revision ([proposal](SPEC-DRAFT-11-PROPOSAL.md)) | IN ROUND | V380 preflight published; S2 disposition, open parameters and Michael authorization remain |
| Q-P2-1 any-subset completion (365 deferred load faults, 6 long cuts) | BLOCKED | V41995965: 365/365 actual faults pass (404/404 with prior receipts); six cuts unavailable on the exact fixture, zero executed. PM retains batching hold; no large-epoch/repeated-LBA completeness |
| Bench parts list approved and ordered | IN ROUND | Minimum bench + rig selected; Michael confirms not ordered. Hardware651 returned correction delta; Software663 integrates it; changed items need approval |

## WP-05 — cards and bench parts

| # | State | Next |
|---|---|---|
| A-1 Identity (part number, capacity, revision, CID per card) | TO DO | Needs a reader or rig that reads CID |
| A-2 Sustained write on 80%-filled media | TO DO | Method re-review, then run |
| A-3 Against the C-60 copy requirement | TO DO | After A-2 |
| A-4 Reader not the bottleneck | TO DO | With A-2 |
| A-5 Bench parts support the bench and the rig | IN ROUND | Hardware651 returned corrected cart; Software663 integrates it; not ordered, changed cart unapproved, no independent acceptance |
| A-6 Atomicity ≥ 1,000 qualifying cuts per SKU/revision, zero torn | BLOCKED | V3d616c14 method NOT CLEARED: R374-1…5. V392/2fc2298b clears bounded c55e5ad judge corrections; unchanged judge in443a5a53 goes to Software663 for current-main integration/CI. No physical run; SPI characterization is not SD4 qualification |

## WP-17 — firmware skeleton ([FW-1](WP17-FIRMWARE-CONTRACT.md))

| # | State | Next |
|---|---|---|
| F1 Goldens byte-identical on target | IN ROUND | V98f46c94 carries host 14/14 PCM and 28/28 controls per platform onto integrated aa472667. Corrected BE1 kit0db6ce5c awaits V394 disposition; CI658 restores supported-platform retained census and binds review-regression ordering; target PCM/I²S pending |
| F2 RAM/stack/.rodata budgets | IN ROUND | V98f46c94 carries static RAM 191600/204800, .rodata 1040/32768 PASS; Corrected kit0db6ce5c awaits V394 review; scoped protected changes approved; actual target instance/stack pending |
| F3 Warm instant-on < 100 ms | TO DO | Needs the logic analyser |
| F4 Commit latency < 200 ms | TO DO | With recording (WP-19) |
| F5 Play/Stop and removal | TO DO | Bench, Michael witnesses |
| F6 Engine unchanged | PASSED | Vd7540127 / V98f46c94 confirm engine tree d96b4245; PM650 authenticates unchanged integration aa472667 |

## WP-18 to WP-21

Criteria are issued with their contracts after round 1:
- WP-18: second slot, copy correctness, progress from the callback.
- WP-19: audio paths, the two output caps, speaker mute, record source.
- WP-20: key reading, depth-sensitive scrub, LED status, record light.
- WP-21: the witnessed bench demo.
