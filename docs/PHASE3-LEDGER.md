# Phase 3 ledger — every exit criterion, one row each

**Opened 2 November 2026 PDT ([ADR-201](DECISIONS.md#adr-201--phase-3-opened-round-1-issued)).**
This is the progress record for Phase 3. Each round closes named rows. Plan:
[PHASE3-PLAN](PHASE3-PLAN.md). PM does not accept; states follow independent records.

States:
- **PASSED:** independently passed;
- **IN ROUND:** assigned in a live issue;
- **TO DO:** not yet assigned.
- **BLOCKED:** a named unresolved prerequisite prevents the criterion from passing.

PM #648 review (2 November): [ADR-202](DECISIONS.md#adr-202--round-1-disposition-and-fw-1-recognition-clarification).
States cite independent results; candidate evidence is not merged implementation or package acceptance.

## Spec and entry items

| Item | State | Next |
|---|---|---|
| DRAFT-11 spec revision ([proposal](SPEC-DRAFT-11-PROPOSAL.md)) | IN ROUND | Preflight requires revision (F374-1…5); corrected proposal awaits re-review, S2 disposition and Michael authorization |
| Q-P2-1 any-subset completion (365 deferred load faults, 6 long cuts) | BLOCKED | V41995965: 365/365 actual faults pass (404/404 with prior receipts); six cuts unavailable on the exact fixture, zero executed. PM retains batching hold; no large-epoch/repeated-LBA completeness |
| Bench parts list approved and ordered | IN ROUND | Hardware drafts; Michael approves |

## WP-05 — cards and bench parts

| # | State | Next |
|---|---|---|
| A-1 Identity (part number, capacity, revision, CID per card) | TO DO | Needs a reader or rig that reads CID |
| A-2 Sustained write on 80%-filled media | TO DO | Method re-review, then run |
| A-3 Against the C-60 copy requirement | TO DO | After A-2 |
| A-4 Reader not the bottleneck | TO DO | With A-2 |
| A-5 Bench parts support the bench and the rig | IN ROUND | Hardware P3-R1 |
| A-6 Atomicity ≥ 1,000 qualifying cuts per SKU/revision, zero torn | BLOCKED | V3d616c14 method NOT CLEARED: R374-1…5. Hardware #641 corrects method/judge/electrical evidence; fresh independent review before any run. SPI characterization is not SD4 qualification |

## WP-17 — firmware skeleton ([FW-1](WP17-FIRMWARE-CONTRACT.md))

| # | State | Next |
|---|---|---|
| F1 Goldens byte-identical on target | IN ROUND | Vd7540127: host 14/14 PCM comparisons and 28/28 controls per platform; target PCM/I²S pending |
| F2 RAM/stack/.rodata budgets | IN ROUND | Vd7540127: static RAM 191600/204800, engine .rodata 1040/32768 PASS; painted target stack pending |
| F3 Warm instant-on < 100 ms | TO DO | Needs the logic analyser |
| F4 Commit latency < 200 ms | TO DO | With recording (WP-19) |
| F5 Play/Stop and removal | TO DO | Bench, Michael witnesses |
| F6 Engine unchanged | PASSED | Vd7540127 independently confirms entire engine tree d96b4245 on candidate ee478a91; candidate unmerged/held |

## WP-18 to WP-21

Criteria are issued with their contracts after round 1:
- WP-18: second slot, copy correctness, progress from the callback.
- WP-19: audio paths, the two output caps, speaker mute, record source.
- WP-20: key reading, depth-sensitive scrub, LED status, record light.
- WP-21: the witnessed bench demo.
