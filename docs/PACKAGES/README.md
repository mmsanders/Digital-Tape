# Work packages

**1 November 2026.** Live assignments are GitHub role issues, not this index. Current state
is in [STATUS](../STATUS.md); the next phase is in [the Phase 3 plan](../PHASE3-PLAN.md); the
device is described in [DEVICE-DESIGN](../DEVICE-DESIGN.md).

| Phase | State |
|---|---|
| 0 Foundations | Specs frozen and signed (docs/PHASE0-FREEZE.md) |
| 1 Audio engine | **Complete** (36/36), 3 Oct 2026 |
| 2 Desktop tooling | **Complete** (12/12, G2 deferred), 1 Nov 2026 |
| 3 Bench firmware | **Open** since 2 Nov 2026 ([ledger](../PHASE3-LEDGER.md)) |
| 4–6 | Future |

## Foundations and specifications
| Package | Outcome | State |
|---|---|---|
| WP-01 | Repo, agent docs, decision log | Established |
| WP-02 | TAPEFS v1 specification | Frozen |
| WP-03 | Engine API specification | Frozen |
| WP-35 | Repo access and agent setup | Established |

## Phase 1 — audio engine (complete)
| Package | Outcome | State |
|---|---|---|
| WP-06 | Block device layer, superblock, index commit | Accepted (Verification #138) |
| WP-07 | Chunk allocator, copy-on-write Side B | Accepted (Verification #67) |
| WP-08 | [Playback, seek, variable-rate scrub](WP-08.md) | Accepted (Verification #143) |
| WP-09 | Record: overwrite, overdub, splice | Accepted (Verification #143) |
| WP-10 | Crash-injection harness | Accepted (Verification #141) |
| WP-11 | CLI harness and golden suite | Accepted (Verification #143); ten goldens approved by Michael |
| WP-12 | Re-spool / defragment | Accepted (Verification #143) |
| WP-13 | Embedded-readiness audit | Accepted (Verification #66) |
| WP-36 | Slot capability model | Accepted (Verification #57) |

## Phase 2 — desktop tooling (complete)
| Package | Outcome | State |
|---|---|---|
| WP-14 | [`tapectl` on real cards](WP-14.md) | Accepted, Windows 11 (Verification #364) |
| WP-16 | [Ingest](WP-16.md) | Accepted, Windows 11 (Verification #364) |
| WP-15 | [One-window app](WP-15.md) | Accepted with G2 deferred (Verification #364/#370, ADR-198) |
| WP-38 | Phone/web harness | Not taken; a later WASM build stays possible |

## Phase 3 — bench firmware (open)
| Package | Outcome |
|---|---|
| WP-05 | [Cards and bench parts](WP-05.md): bench parts list, card characterisation and the atomicity test |
| WP-17 | Teensy firmware skeleton, engine integration ([FW-1](../WP17-FIRMWARE-CONTRACT.md)) |
| WP-18 | Second card slot, insert detect, copy with LED progress |
| WP-19 | Codec, microphone, aux, speaker amplifier, output caps |
| WP-20 | Transport key reading and LED status (no solenoid) |
| WP-21 | Bench acceptance demo |

## Later phases
| Phase | Packages |
|---|---|
| 4 Mechanics | WP-22 transport production design, WP-23 enclosure, WP-24 cartridge shell and carrier, WP-25 abuse testing (Guardrail 13) |
| 5 Board | WP-26 schematic, WP-27 layout/BOM, WP-28 firmware port and UHS-I bring-up, WP-29 bring-up and rev B, WP-30 power budget, WP-34 thermal/safety budget, WP-37 thermal validation |
| 6 Build | WP-31 build units, WP-32 starter cartridge library, WP-33 field trial |

The September 2026 hardware package snapshots (WP-04, WP-24, WP-25) describe the superseded
solenoid design and 86 × 54 mm cartridge; they are in docs/archive/hardware/.
