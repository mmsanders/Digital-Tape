# Project status

**3 November 2026 PDT. Phase 3 OPEN** ([ADR-201](DECISIONS.md#adr-201--phase-3-opened-round-1-issued)). Phases 1 and 2 are complete.
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

See [DEVICE-DESIGN](DEVICE-DESIGN.md). Still open: the copy button and the promote-B-to-A
key combination.

## Current assignments

Round 2 (Michael starts each; parts not ordered):

| Owner | Issue | Outcome |
|---|---|---|
| Hardware | [#651](https://github.com/mmsanders/Digital-Tape/issues/651) | Returned 2faa1180: R374-1 implemented, R374-2/5 declared; awaits V382 bindings/review on existing PR646 |
| Software | [#652](https://github.com/mmsanders/Digital-Tape/issues/652) | BE1-IF/2 declared at 97a55022 / PR654; checker waits for V382 executable fixtures |
| Verification | [V#382](https://github.com/mmsanders/digital-tape-verification/issues/382) | Bind both received schemas to executable fixtures, review R374-1 and later exact heads; ready lanes publish separately |

Latest [PM655 review](REVIEW/PM655-P3-R2-2026-11-03.md) / ADR-204: V378 `98f46c94`
cleared the admission correction (28 cases / four controls). Software integrated at
`aa472667` with unchanged cleared implementation and 117 current-base checks passing.
F6 remains PASSED (**1/12** defined criteria); target/package acceptance is pending.
V41995965 passes all 365 deferred faults;
six long cuts are unavailable on the issued fixture, not executed. Batching stays held.
V3d616c14: rig method NOT CLEARED (R374-1…5); Hardware #651 owns corrections. SPI
characterization is not native SD4 qualification. DRAFT-11 preflight requires revision;
proposal remains unissued. Target PCM/I²S, stack, timing and controls/removal await the bench.
Michael's minimum bench + rig selection stands; parts **not ordered** (2 November).
No fresh physical session is ready. A corrected-rig cart delta is not an approved purchase.

V380 d23a90f7 published 27 rig regressions and preflight; no corrected-head clearance.
Both declarations are now received. Completed-write OLD rollback fails run integrity
only with qualified proof outside uncertainty; boundary equality remains ambiguous.

## Holds that stand

- Guardrails 01–13; engine pinned at `d96b4245`; format frozen; Structural Rule 1 for engine
  code; Verification independence.
- Host scope frozen. The app and ingest never run elevated; WP-14 A4 disk safety outranks
  everything.
- Fabrication and charging CLOSED. No card is qualified yet.
- Deferred, not waived:
  - G2: run [the protocol](WP15-G2-PROTOCOL.md) before the app goes to anyone else for real use;
  - macOS;
  - the ADR-196 limitations.

[Hardware status](STATUS-HARDWARE.md) · [human queue](FOR-MICHAEL.md) · [decisions index](DECISIONS-INDEX.md)
