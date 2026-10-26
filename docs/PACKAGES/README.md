# Work packages — current roadmap

**26 October2026 PDT · PM593.** Current Phase2 target: Windows11 x64;
macOS deferred, Linux existing CI. Live assignments are GitHub role issues,
not this index. [Status](../STATUS.md), [Phase2 plan](../PHASE2-PLAN.md) and
[independent integration](../VERIFICATION-INTEGRATION.md) govern current gates.

Phase1 is COMPLETE36/36. Phase2 remains6/12; numerical rungs are complete
criteria, not effort percentages. No new phase/hardware/firmware work is issued.

## Phase 0 — foundations and parked hardware
| Package | Outcome | Owner | Stream | Current boundary |
|---|---|---|---|---|
| WP-01 | Repo, agent docs, decision log | Agent | — | Established foundation; frozen interfaces and reserved approvals remain binding. |
| WP-02 | TAPEFS v1 specification | **PM** | spec | Established foundation; frozen interfaces and reserved approvals remain binding. |
| WP-03 | Engine API specification | **PM** | spec | Established foundation; frozen interfaces and reserved approvals remain binding. |
| WP-04 | Transport spike: Route A vs Route B | You | hardware | Parked through Phase2; safety/fabrication/charging holds and original resume criteria unchanged. |
| WP-05 | Parts order #1 | You | hardware | Parked through Phase2; safety/fabrication/charging holds and original resume criteria unchanged. |
| WP-34 | Thermal and safety budget | Hardware | hardware | Parked through Phase2; safety/fabrication/charging holds and original resume criteria unchanged. |
| WP-35 | Repo access and agent push setup | You | — | Established foundation; frozen interfaces and reserved approvals remain binding. |

## Phase 1 — audio engine, COMPLETE
| Package | Outcome | Owner | Stream | Current boundary |
|---|---|---|---|---|
| WP-06 | Block device layer, superblock, index commit | Agent | 1 | **COMPLETE.** Verification #138's DRAFT-10 ledger closes WP-06: 40 rows independently accepted and integrated (mount, writability, NOT_MOUNTED, #297 sequential, #326 closure gaps), 2 WP-06e rows unreachable by spec (V10-002), none open |
| WP-07 | Chunk allocator, copy-on-write Side B | Agent | 1 | **COMPLETE / independently accepted.** Verification PR #67 accepted the frozen 10,000-sequence allocator/COW package. Product PR #215 mechanically carried the accepted bytes onto post-WP13 main and integrated them unchanged |
| WP-08 | Playback, seek, variable-rate scrub | Agent | 1 | **COMPLETE.** Every behaviour row is covered. L01/L14 close on the WP-11 goldens approved by Michael (#367). Verification #143 PASS on exact #369 |
| WP-09 | Record: overwrite, overdub, splice | Agent | 1 | **COMPLETE.** Every behaviour row is covered (#346). L01 closes on the WP-11 goldens approved by Michael (#367). Verification #143 PASS on exact #369 |
| WP-10 | Crash-injection harness | Verification | 2 | **COMPLETE.** Verification #141 passed exact Product #362 (V10-001) and closed the DRAFT-10 WP-10 ledger: 63 rows, zero open; earlier bounded tranches carried within their exact boundaries |
| WP-11 | CLI harness and golden-file regression suite | Verification | 2 | **COMPLETE.** `tapectl` per `docs/WP11-CLI-CONTRACT.md`; ten golden references from public-domain Grieg plus a CC0 voice, approved by Michael (#367) and bit-identical in CI; the §8 differential on three configurations; mutation 7/7. Verification #143 PASS on exact #369, merged at `d93ca4e` |
| WP-12 | Re-spool / defragment pass | Agent | 1 | **COMPLETE.** WP-12/12a ledger: 36 rows, zero open (`wp11_ledgers_r63`; Verification #143) |
| WP-13 | Embedded-readiness audit | Agent | 1 | **COMPLETE / independently accepted.** Verification PR #66 independently reproduced all six frozen gates from raw evidence and accepted exact product PR #206; integrated on main |
| WP-36 | Slot capability model | Agent | 1 | **COMPLETE / independently accepted.** Verification PR #57 accepted the frozen package after the deterministic 5/5 precursor plus the exact 100,000-sequence / 1,997,914-operation literal-NULL source-slot campaign. Product PR #200 integrated the exact accepted tree unchanged at main `e4a3565...` |

## Phase 2 — current desktop tooling
| Package | Outcome | Owner | Stream | Current boundary |
|---|---|---|---|---|
| WP-14 | [Real-card CLI](WP-14.md) | Software/Verification |3|3/4; nativeA6 request/offset linkage remains held, no new physical test issued. |
| WP-15 | [One-window Windows app](WP-15.md) | Software/Verification |3|1/4;584 source integrated,328 human visual partial reviewed.594/332 fixes console/receipts;585/325 final bundle waits. Full native/S3/G2 coverage incomplete. |
| WP-16 | [Ingest](WP-16.md) | Software/Verification |3|2/4;595/333 resolves exact459/454 integration scope versus final own-host/native gates; no unchecked merge or obsolete Mac condition. |
| WP-38 | Phone/web harness | — |3|Not taken in Phase2. Future WASM possibility preserved; resume only on explicit authorization. |

No current human action:589 reviewed/partial closed; no repeat or Show Details
recovery requested. Source fixes do not retrospectively qualify original564 or585.
Shipping Make/elevation disabled. No current G1 observer or raw-card/S3 run issued.
[PM593 closeout](../REVIEW/PM593-CLOSEOUT-2026-10-26.md) records exact evidence,
closures/restoration pointers and remaining gates. Manual role pickup only.

## Phase 3 — future scope, not activated
| Package | Outcome | Owner | Stream | Current boundary |
|---|---|---|---|---|
| WP-17 | Teensy firmware skeleton, engine integration | Agent | 4 | Not activated; original package/dependency/acceptance and safety boundaries carry. |
| WP-18 | Dual card, hot-swap detect, copy with LED row | Either | 4 | Not activated; original package/dependency/acceptance and safety boundaries carry. |
| WP-19 | Line-in, mic, gain staging, output limit | Either | 4 | Not activated; original package/dependency/acceptance and safety boundaries carry. |
| WP-20 | Button matrix, solenoid driver, interlock | You | 4 | Not activated; original package/dependency/acceptance and safety boundaries carry. |
| WP-21 | Bench acceptance demo | Either | 4 | Not activated; original package/dependency/acceptance and safety boundaries carry. |

## Phase 4 — future scope, not activated
| Package | Outcome | Owner | Stream | Current boundary |
|---|---|---|---|---|
| WP-22 | Transport mechanism, production design | You | hardware | Not activated; original package/dependency/acceptance and safety boundaries carry. |
| WP-23 | Enclosure CAD | Either | hardware | Not activated; original package/dependency/acceptance and safety boundaries carry. |
| WP-24 | Cartridge shell and carrier PCB | Either | hardware | Not activated; original package/dependency/acceptance and safety boundaries carry. |
| WP-25 | Abuse testing | You | hardware | Not activated; original package/dependency/acceptance and safety boundaries carry. |

## Phase 5 — future scope, not activated
| Package | Outcome | Owner | Stream | Current boundary |
|---|---|---|---|---|
| WP-26 | Schematic capture and review | Agent | hardware | Not activated; original package/dependency/acceptance and safety boundaries carry. |
| WP-27 | Layout, DFM, assembly BOM | Agent | hardware | Not activated; original package/dependency/acceptance and safety boundaries carry. |
| WP-28 | Firmware port and UHS-I bring-up | Agent | 5 | Not activated; original package/dependency/acceptance and safety boundaries carry. |
| WP-29 | Bring-up and rev B | Either | 5 | Not activated; original package/dependency/acceptance and safety boundaries carry. |
| WP-30 | Power budget and runtime validation | Either | 5 | Not activated; original package/dependency/acceptance and safety boundaries carry. |
| WP-37 | Thermal validation and abuse | Either | 5 | Not activated; original package/dependency/acceptance and safety boundaries carry. |

## Phase 6 — future scope, not activated
| Package | Outcome | Owner | Stream | Current boundary |
|---|---|---|---|---|
| WP-31 | Build the units | You | — | Not activated; original package/dependency/acceptance and safety boundaries carry. |
| WP-32 | Starter cartridge library | Either | 3 | Not activated; original package/dependency/acceptance and safety boundaries carry. |
| WP-33 | Field trial | You | — | Not activated; original package/dependency/acceptance and safety boundaries carry. |

## Historical detail and preservation

Prior roadmap revisions, duration estimates, parked PR restore refs, kickoff
retrospective, technical resume conditions and per-file template remain unchanged
in Git history. This current index does not republish or link unrelated owner-
specific historical material. No historical commit, package criterion, raw record
or restore ref is deleted. Specific package files and normative spec remain
authoritative; generic future rows do not waive safety or detailed resume conditions.
