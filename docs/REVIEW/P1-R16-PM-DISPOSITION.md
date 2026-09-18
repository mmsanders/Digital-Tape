# P1-R16 PM disposition — exact product observations, card data and ruggedization

**Date:** 18 September 2026 UTC  
**PM issue:** [#88](https://github.com/mmsanders/Digital-Tape/issues/88)  
**Input product main:** `9143fd94626d5fba80976ba1c47ad28c2fd49a36`  
**Input verifier main:** `392d6bb9c948a5924fe18728fab04202bc8e337e`

## Verification return accepted at its exact boundary

Verification #12 added one findings file at verifier commit
`392d6bb9c948a5924fe18728fab04202bc8e337e`, tree
`53d4ad25023ccd788017518b01da661c30541ba0`, blob
`bd1166e7831bb28a95a2d12f5078596388bdf375`, SHA-256
`ded9a314fb636a8d6fceca9593054849f28b4bc49f8a6ec5cac7e22c0330c532`.
PM authenticated those identities and reran `make -C tests check`; the full verifier
suite passed.

Accept the independent disposition narrowly. The exact ten corrected-cadence playback
observations and exact 289 mount records are accepted. Each scrub direction has 698
renders, 698 immediately preceding completed `tape_service(1024)` sequences and
88,200 frames with no short render. All seven PCM outputs match verifier candidates
byte-for-byte. `P1-R12-V01` is cured for this exact evidence. The PCM remains
unlistened and is not a WP-11 golden.

Finding `P1-R15-V01` is valid and non-blocking. The evidence commit contains outer
run tree `ea34ba25cd5b67e739038b59f14dbecf69747d0f`, not the stale
`db88b71a...` value quoted in the P1-R15 route. Only two self-referential README rows
differ; the evidence commit/tree, inner product-evidence tree, staged verifier package
and all raw digests remain authenticated.

This return is not source/helper review, reproducible-binary acceptance, complete
WP-06/WP-08 or implementation acceptance, listening or package acceptance. PR #20
and #64 remain held. Software may now perform a bounded current-main integration of
only PR #77's clean independently observed slice, preserving exact accepted blobs,
Structural Rule 1 and every uncovered-behaviour exclusion.

## Hardware PR #87 is useful submitted evidence, not qualification

PR #87 head `be0950a5b83bcd11f6eb37e8f6c4a5fbbc88fe9b`, tree
`af9847d2369a7c047dc4d445aed839b6d371ad70`, contains five raw JSON runs, a
derivation script and a measurement record. PM reran `analyse.py`; all stored verdicts
match the raw-window recomputation:

| Run | Fill | Worst 64 MB window | C-60 screen |
|---|---:|---:|---:|
| onn V10 | unfilled | 15.34 MB/s | fail |
| PNY sample 1 | unfilled | 26.18 MB/s | pass |
| PNY sample 2 | unfilled | 25.41 MB/s | pass |
| PNY sample 3 | unfilled | 25.88 MB/s | pass |
| PNY sample 3 | 80% | 27.36 MB/s | pass |

The negative control demonstrates the calculation can fail. The three unfilled PNY
samples agree to 1.0% on the submitted adjacent-pair metric. The one filled trial did
not reveal a long stall. These are useful physical-sample/path observations pending
independent audit.

Keep A-2's 80%-fill condition. Low logical product occupancy does not establish the
flash translation layer's prior-write or garbage-collection state over service life,
and the submitted filled run passes, so relaxing the stress condition buys nothing.
The four unfilled runs are screening/unit/control evidence; they do not each have to
satisfy the filled-run setup and are not four A-2 failures. At least one conforming
filled run is required per exact candidate SKU/revision.

Do not claim card qualification or card-speed attribution. Exact manufacturer part
number, revision and CID are absent; the reader/shared path appears limiting; host
caching and thermal conditions are incompletely recorded; no atomicity run or
production end-to-end copy exists. C-90 is not reopened. PR #87 remains a draft until
Hardware corrects the scope language, completes identity/provenance as far as the
physical record permits and returns a packet ready for independent audit.

PM also reproduced the hardware regression targets as green and the real fabrication
gate as **CLOSED, exit 2, with five blockers**. No fabrication or cell charging is
authorized.

## Ruggedization is now a design input

Guardrail 13 and WP-25 make child-resistant rough-use performance a player-wide
requirement before final enclosure CAD. The loaded player must be designed against
drops, shaking and repeated rough handling without battery exposure/motion, sharp or
hazardous detached parts, unintended opening, exposed conductors, cartridge ejection,
hidden loose parts or loss of basic controls/audio/transport function.

Hardware must first publish the system shock/load path and failure-mode matrix, then
an auditable drop/shake protocol. Trials progress from dummy mass/inert components to
a representative assembled unit in the intended material/process. WP-24's cartridge
shell drop criterion remains separate. PETG, TPU, foam, ribs, compliant mounts,
locking connectors and strain relief are candidate mechanisms, not frozen solutions.
Verification reviews the criteria before physical testing and audits the resulting
evidence; Hardware does not accept its own design.

Michael's A1 Mini purchase replaces the library-only print assumption. It does not
qualify the printer, material, slicer settings or a printed part. Hardware must revise
the packet/process around the owned printer and record repeatability before relying on
dimensions or abuse results.

## Round routing and preserved holds

Software receives one bounded clean-integration issue for PR #77. Hardware receives
one issue covering PR #87 correction/audit readiness, the A1 Mini process transition
and the pre-CAD ruggedization architecture/test plan. Verification is not activated
until Hardware has an auditable packet; Surge has no assignment. Michael #49 changes
materially only to note that the cards and printer are now purchased and the old
library/two-arm tasks are superseded; no new hands task is created.

PR #20/#64, uncovered allocator/recording/crash/recovery/warm-start/state/operations/
performance behavior, frozen DRAFT-8/WP-08 bytes, Structural Rule 1, WP-11 red and
listening hold, card qualification/atomicity, fabrication, charging, safety and all
Michael-reserved approvals remain. The dashboard stays at 13/36 rungs because exact
observation acceptance and requirement issuance do not complete an implementation or
package rung.
