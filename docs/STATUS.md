# Project status

**8 November 2026 PST. Phase 3 OPEN** ([ADR-201](DECISIONS.md#adr-201--phase-3-opened-round-1-issued)). Phases 1 and 2 are complete.
Progress: [Phase 3 ledger](PHASE3-LEDGER.md).

## Completed

| Phase | Result |
|---|---|
| 1 Audio engine | 36/36 accepted (3 Oct 2026) |
| 2 Desktop tooling | 12/12, with the G2 unaided test deferred (1 Nov 2026). `tapectl` on real cards, ingest and the one-window app are accepted for Windows 11. Michael made real cartridges through the app |

Package detail: [packages](PACKAGES/README.md) and [verification integration](VERIFICATION-INTEGRATION.md).
The desktop tool's scope is frozen (ADR-198): it loads cartridges, nothing more.

## Phase 3

[Phase 3 plan](PHASE3-PLAN.md):
- the shared engine on a Teensy 4.1 bench build, with keys, LED status, headphones and speaker;
- the card power-cut test on the PNY cards;
- the deferred crash coverage before firmware write batching.

The device design has moved:
- mechanical latching side keys and no solenoid (LED status instead);
- depth-sensitive Rew/FF;
- a speaker with its own loudness cap;
- a microphone, aux in, and aux out shared with the headphone jack.

See [DEVICE-DESIGN](DEVICE-DESIGN.md).

**ADR-208 governs hands-on methods.** Firmware self-timing plus Michael's matched
[record](MICHAEL-CHECKS.md); phone-app cap margin, optional CID, no retired laboratory
instrument/uncertainty gate. Strict counted/structural facts and cap margins remain.

## Current assignments

[PM669 latest review](REVIEW/PM669-PREPARTS-2026-11-08.md) / ADR-209:

| Owner | Issue | Outcome before parts |
|---|---|---|
| Software | [#674](https://github.com/mmsanders/Digital-Tape/issues/674) | Declare F3 serial/timer/build/record interface; after independent binding implement hooks/offline capture and first-board packet |
| Hardware | [#675](https://github.com/mmsanders/Digital-Tape/issues/675) | Finish declared selfrun-r1 host checker after tests; verify small first-order cart and resolve S2 research gap; same PR673 |
| Verification | [V#405](https://github.com/mmsanders/digital-tape-verification/issues/405) | Bind ready selfrun declaration now, timing declaration when returned; publish tests before code and review exact heads |

Michael manually starts each issue; no listeners or subworkers. Closed667/658/652,
V397/V398 are completed inputs, not new work.

## Latest disposed work

Hardware646 integrated60dfe6aa carries V392 unchanged. V397 clears runnera4ed3e71,
census78f1631f and orderdbaa5a03. Software integrated PR672 at3558a88a (113 checks),
PR660 at211f8a9d and PR665 atc30881d9 (111/111 each). Earlier CI blockers are fixed.
BE-1 kit PR654 integrated8893c99 from4976cad0 after119/119 successes; V394 clearance
carries unchanged checker/helper/imports, with protected metadata-only provenance.
No target/package acceptance follows. Engine remains d96b4245.
V398 publishes DRAFT11 wording findings200ecef7,41/10 UNBOUND timing semantics
9aa2716a and11 planted-tear judge cases321c5236. PR673/c32f1a56 declares new plan5
selfrun-r1; not implemented. Complete self-run method remains NOT CLEARED.
PM resolves CID disagreement diagnostic-only (P3B), completed-before OLD run FAIL
(P4), declared5us/200mV logical boundaries, and SPI model-atomicity scope with
explicit residual bus risk. No native-SD4 equivalence or physical qualification.
F398 wording corrected; old DRAFT10/engine/goldens stay frozen. S2 and owner
authorization still precede DRAFT11 issuance. No retired calibrated rig gate returns.

## Parts and critical path

**The missing Teensy now blocks actual target bring-up and validation.** Useful
pre-parts work remains in674/675/405, but cannot establish target PCM/I2S, stack,
timing, removal or real card cuts. Buy-first recommendation: Teensy4.1, compatible
RevD/D2 audio adapter, required headers/connections, basic breadboard/wires/buttons,
USB data cable if not owned. Teensy alone enables boot/USB/native-SD preparation;
audio needs the adapter. Ordinary playback does not wait for the rig or speaker.
Hardware675 verifies the small cart; no current price/stock guarantee from old totals.
Later speaker/mic/LED/Hall/second-slot and power-cut parts are separate purchases.
No order has been confirmed; changed cart remains Michael's approval/payment.
Still **1/12 passed (F6)**. A1 identity review, F1/F2 preparation and F3 off-target
work are in round; A5/A6 blocked by parts/remaining method work. No bench session
is executed/authorized here.365 deferred faults pass; six long cuts unavailable;
batching held. Physical controls, cards, target/caps and DRAFT11 remain pending.

## Holds that stand

- Guardrails 01–13; engine pinned at `d96b4245`; format frozen; Structural Rule 1 for engine
  code; Verification independence.
- Host scope frozen. The app and ingest never run elevated; WP-14 A4 disk safety outranks
  everything.
- Fabrication and charging CLOSED. No card is qualified yet.
- Deferred, not waived:
  - G2: run [the protocol](WP15-G2-PROTOCOL.md) before the app goes to anyone else for real use;
  - macOS (ADR-205: retained manual checks, excluded from normal required aggregates);
  - the ADR-196 limitations.

[Hardware status](STATUS-HARDWARE.md) · [human queue](FOR-MICHAEL.md) · [decisions index](DECISIONS-INDEX.md)
