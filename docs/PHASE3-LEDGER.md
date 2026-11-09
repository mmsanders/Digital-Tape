# Phase 3 ledger — every exit criterion, one row each

**Opened 2 November 2026 PDT ([ADR-201](DECISIONS.md#adr-201--phase-3-opened-round-1-issued)).**
This is the progress record for Phase 3. Each round closes named rows. Plan:
[PHASE3-PLAN](PHASE3-PLAN.md). PM does not accept; states follow independent records.

States:
- **PASSED:** independently passed;
- **IN ROUND:** assigned in a live issue;
- **TO DO:** not yet assigned.
- **BLOCKED:** a named unresolved prerequisite prevents the criterion from passing.

**ADR-208 (6 November): hands-on acceptance.** Timing/feel rows are firmware-timed and judged by Michael; caps use a phone app with a 5 dB margin; CID is not required; the power-cut test is Teensy self-run.

PM #666 review (5 November): [ADR-207](DECISIONS.md#adr-207--carry-integrated-hardware-and-cleared-kit-restore-portability-runner).
States cite independent results; candidate evidence is not merged implementation or package acceptance.

## Spec and entry items

| Item | State | Next |
|---|---|---|
| DRAFT-11 spec revision ([proposal](SPEC-DRAFT-11-PROPOSAL.md)) | IN ROUND | V380 preflight published; S2 disposition, open parameters and Michael authorization remain |
| Q-P2-1 any-subset completion (365 deferred load faults, 6 long cuts) | BLOCKED | V41995965: 365/365 actual faults pass (404/404 with prior receipts); six cuts unavailable on the exact fixture, zero executed. PM retains batching hold; no large-epoch/repeated-LBA completeness |
| Bench parts list approved and ordered | BLOCKED | ADR-208: Hardware revises the cart (no bench logic analyser, SPL meter or coupler; ~$30 instruments; load switch for the power-cut test); then Michael approves and orders |

## WP-05 — cards and bench parts

| # | State | Next |
|---|---|---|
| A-1 Identity (brand, part number, capacity, photo per card) | IN ROUND | Recorded 7 Nov in [evidence/cards](evidence/cards/README.md): PNY Elite-X 64 GB microSDXC U3 V30 A1, photos hashed; retail part number unknown (packaging gone). Verification checks the record with WP-05 |
| A-2 Sustained write on 80%-filled media | TO DO | Method re-review, then run |
| A-3 Against the C-60 copy requirement | TO DO | After A-2 |
| A-4 Reader not the bottleneck | TO DO | With A-2 |
| A-5 Bench parts support the bench and the rig | BLOCKED | Corrected cart integrated60dfe6aa; last confirmed not ordered, changed cart unapproved, no independent support/physical acceptance |
| A-6 Atomicity ≥ 1,000 qualifying cuts per card model, zero torn | BLOCKED | ADR-208 replaces the externally traced rig with a Teensy self-run test; earlier R374-1…5 instrument findings no longer apply. Hardware revises the method; Verification reviews it with a planted-tear negative control; needs bench parts |

## WP-17 — firmware skeleton ([FW-1](WP17-FIRMWARE-CONTRACT.md))

| # | State | Next |
|---|---|---|
| F1 Goldens byte-identical on target | IN ROUND | V98f46c94 carries host 14/14 PCM and 28/28 controls per platform onto integrated aa472667. V394/80d93c50 clears kit0db6ce5c off-target behavior; V397 reviews returned CI660/665, Software667 restores portability runner before integration; target PCM/I²S pending |
| F2 RAM/stack/.rodata budgets | IN ROUND | V98f46c94 carries static RAM 191600/204800, .rodata 1040/32768 PASS; V394/80d93c50 clears kit0db6ce5c off-target behavior; CI/metadata integration pending, ownership changes approved; actual target instance/stack pending |
| F3 Warm instant-on < 100 ms | TO DO | Firmware-timed and logged, Michael's verdict (ADR-208); needs the bench build |
| F4 Commit latency < 200 ms | TO DO | Firmware-timed with zero underruns, Michael's verdict (ADR-208); with recording (WP-19) |
| F5 Play/Stop and removal | TO DO | Bench, Michael witnesses |
| F6 Engine unchanged | PASSED | Vd7540127 / V98f46c94 confirm engine tree d96b4245; PM650 authenticates unchanged integration aa472667 |

## WP-18 to WP-21

Criteria are issued with their contracts after round 1:
- WP-18: second slot, copy correctness, progress from the callback.
- WP-19: audio paths, the two output caps, speaker mute, record source.
- WP-20: key reading, depth-sensitive scrub, LED status, record light.
- WP-21: the witnessed bench demo.
