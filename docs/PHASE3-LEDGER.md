# Phase 3 ledger — every exit criterion, one row each

**Opened 2 November 2026 PDT ([ADR-201](DECISIONS.md#adr-201--phase-3-opened-round-1-issued)).**
This is the progress record for Phase 3. Each round closes named rows. Plan:
[PHASE3-PLAN](PHASE3-PLAN.md). PM does not accept; states follow independent records.

States:
- **PASSED:** independently passed;
- **IN ROUND:** assigned in a live issue;
- **TO DO:** not yet assigned.
- **BLOCKED:** a named unresolved prerequisite prevents the criterion from passing.

PM #650 review (2 November): [ADR-203](DECISIONS.md#adr-203--firmware-integration-recorded-off-target-round-2-issued).
States cite independent results; candidate evidence is not merged implementation or package acceptance.

## Spec and entry items

| Item | State | Next |
|---|---|---|
| DRAFT-11 spec revision ([proposal](SPEC-DRAFT-11-PROPOSAL.md)) | IN ROUND | V380 revised-proposal preflight; S2 disposition, open parameters and Michael authorization remain |
| Q-P2-1 any-subset completion (365 deferred load faults, 6 long cuts) | BLOCKED | V41995965: 365/365 actual faults pass (404/404 with prior receipts); six cuts unavailable on the exact fixture, zero executed. PM retains batching hold; no large-epoch/repeated-LBA completeness |
| Bench parts list approved and ordered | IN ROUND | Minimum bench + rig selected; Michael confirms not ordered. Hardware651 reconciles correction delta; changed items need approval |

## WP-05 — cards and bench parts

| # | State | Next |
|---|---|---|
| A-1 Identity (part number, capacity, revision, CID per card) | TO DO | Needs a reader or rig that reads CID |
| A-2 Sustained write on 80%-filled media | TO DO | Method re-review, then run |
| A-3 Against the C-60 copy requirement | TO DO | After A-2 |
| A-4 Reader not the bottleneck | TO DO | With A-2 |
| A-5 Bench parts support the bench and the rig | IN ROUND | Hardware651 reconciles selected cart with corrected method; no parts in hand or independent acceptance |
| A-6 Atomicity ≥ 1,000 qualifying cuts per SKU/revision, zero torn | BLOCKED | V3d616c14 method NOT CLEARED: R374-1…5. Hardware651 corrects, V380 authors tests/reviews. No physical run; SPI characterization is not SD4 qualification |

## WP-17 — firmware skeleton ([FW-1](WP17-FIRMWARE-CONTRACT.md))

| # | State | Next |
|---|---|---|
| F1 Goldens byte-identical on target | IN ROUND | V98f46c94 carries host 14/14 PCM and 28/28 controls per platform onto integrated aa472667. Software652/V380 prepare BE-1; target PCM/I²S pending |
| F2 RAM/stack/.rodata budgets | IN ROUND | V98f46c94 carries static RAM 191600/204800, .rodata 1040/32768 PASS; Software652/V380 prepare capture kit; actual target instance/stack pending |
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
