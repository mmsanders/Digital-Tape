# Project status

**4 November 2026 PDT. Phase 3 OPEN** ([ADR-201](DECISIONS.md#adr-201--phase-3-opened-round-1-issued)). Phases 1 and 2 are complete.
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

Round 2 continuation (Michael starts each):

| Owner | Issue | Outcome |
|---|---|---|
| Software | [#658](https://github.com/mmsanders/Digital-Tape/issues/658) | First priority: separate CI-only change; deferred macOS manual-only, supported-platform aggregates remain fail closed |
| Software | [#652](https://github.com/mmsanders/Digital-Tape/issues/652) | Kit d62e0de0 implemented, awaits V388 exact-head review; scoped CODEOWNERS approval recorded, owner entries still to add |
| Hardware | [#651](https://github.com/mmsanders/Digital-Tape/issues/651) | Exact18852b5 HOLD for setup-proof/credit and loader-exception defects; import PR387 only after merged publication, fix in same PR646 |
| Verification | [V#388](https://github.com/mmsanders/digital-tape-verification/issues/388) | Publish ready Hardware review/tests, dispose kit now, then returned CI658 policy and Hardware fixes |

Latest [PM657 review](REVIEW/PM657-P3-2026-11-04.md) / ADR-205 records Michael's
explicit CODEOWNERS approval for the scoped imports/workflow/owner additions and
bounded CI658 policy. Ownership, independent disposition and required CI remain.
Kit's 109/4 and53/47 self/CI results are readiness evidence, not clearance.
Both macOS jobs in41857074135 were cancelled with no runner/steps; the required
aggregate failures block merge until CI658 lands. Normal required CI is Windows11
plus Linux; macOS remains manual-only and deferred, with historical evidence retained.
V382/IF3/records bindings are published; Hardware independently passes27/71/229,
but PR387 reproduces two new defects (six red cases). Its CI is green, publication
still pending. No target/package advance: **1/12** (F6); integrated FW-1 aa472667 carries.
All365 deferred faults pass; six long cuts remain unavailable/unexecuted; batching held.
Rig NOT CLEARED; E0-E4/dry-run controls unmeasured; SPI is not native qualification.
Target PCM/I2S/instance/stack/timing/removal and DRAFT-11 remain pending. No physical
session ready. Last owner-confirmed parts status: not ordered; changed cart unapproved.

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
