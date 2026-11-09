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

PM #669 latest review (8 November): [ADR-209](DECISIONS.md#adr-209--finish-pre-parts-interfaces-and-put-the-first-board-on-the-critical-path).
States cite independent results; candidate evidence is not merged implementation or package acceptance.

## Spec and entry items

| Item | State | Next |
|---|---|---|
| DRAFT-11 spec revision ([proposal](SPEC-DRAFT-11-PROPOSAL.md)) | IN ROUND | V398 preflight200ecef7 findings corrected; S2 exact source-backed value, open parameters, exact-bundle review and Michael authorization remain |
| Q-P2-1 any-subset completion (365 deferred load faults, 6 long cuts) | BLOCKED | V41995965: 365/365 actual faults pass (404/404 with prior receipts); six cuts unavailable on the exact fixture, zero executed. PM retains batching hold; no large-epoch/repeated-LBA completeness |
| Bench parts list approved and ordered | BLOCKED | Teensy now blocks real-board validation. Hardware675 verifies small first-order cart; Michael approves/orders. Full rig/speaker order need not delay ordinary playback bench |

## WP-05 — cards and bench parts

| # | State | Next |
|---|---|---|
| A-1 Identity (brand, part number, capacity, photo per card) | IN ROUND | Recorded 7 Nov in [evidence/cards](evidence/cards/README.md): PNY Elite-X 64 GB microSDXC U3 V30 A1, photos hashed; retail part number unknown (packaging gone). V405 checks actual model/photo/unit record under ADR208; no invented retail part number/CID requirement |
| A-2 Sustained write on 80%-filled media | TO DO | Method re-review, then run |
| A-3 Against the C-60 copy requirement | TO DO | After A-2 |
| A-4 Reader not the bottleneck | TO DO | With A-2 |
| A-5 Bench parts support the bench and the rig | BLOCKED | Hardware675 stages buy-first Teensy/audio/connections separately from later rig/features; no order/changed-cart approval or physical acceptance |
| A-6 Atomicity ≥ 1,000 qualifying cuts per card model, zero torn | BLOCKED | V398 planted-tear logic11 cases pass. Hardware675/V405 bind and implement new selfrun-r1/plan5 with ADR209 P3/P4/SPI decisions; complete method/card run pending, needs parts. No retired instrument gates |

## WP-17 — firmware skeleton ([FW-1](WP17-FIRMWARE-CONTRACT.md))

| # | State | Next |
|---|---|---|
| F1 Goldens byte-identical on target | IN ROUND | V98f46c94 carries host 14/14 PCM and 28/28 controls per platform onto integrated aa472667. V394 kit clearance carried into integrated8893c99 with119/119 CI checks; target PCM/I2S needs Teensy+audio board,674 readies first-board capture; target PCM/I²S pending |
| F2 RAM/stack/.rodata budgets | IN ROUND | V98f46c94 carries static RAM 191600/204800, .rodata 1040/32768 PASS; Kit integrated8893c99 after119/119 CI checks; static scope carries,674 prepares source/binary/log linkage; actual target instance/stack pending |
| F3 Warm instant-on < 100 ms | IN ROUND | Software674 declares then implements independently bound timer/capture route with V405; off-target controls before parts, actual timing still needs bench and matched Michael verdict |
| F4 Commit latency < 200 ms | TO DO | Firmware-timed with zero underruns, Michael's verdict (ADR-208); with recording (WP-19) |
| F5 Play/Stop and removal | TO DO | Bench, Michael witnesses |
| F6 Engine unchanged | PASSED | Vd7540127 / V98f46c94 confirm engine tree d96b4245; PM650 authenticates unchanged integration aa472667 |

## WP-18 to WP-21

Criteria are issued with their contracts after round 1:
- WP-18: second slot, copy correctness, progress from the callback.
- WP-19: audio paths, the two output caps, speaker mute, record source.
- WP-20: key reading, depth-sensitive scrub, LED status, record light.
- WP-21: the witnessed bench demo.
