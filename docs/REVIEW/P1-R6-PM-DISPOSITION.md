# P1-R6 PM disposition — playback import and scrub-table blocker

**Date:** 13 September 2026 UTC  
**Owner:** PM under [#61](https://github.com/mmsanders/Digital-Tape/issues/61)  
**Product input:** `fd2b73fe50e3e5e8e2d02b8876256a6ed8f4b57b`  
**Verifier input:** `a6b2630a55f7260a74e529d22f84aa94b8d7341f`

## Software #59 / PR #60

Software returned draft PR #60 at
`b2c16aac98605a94206e4af2fc04d8db1305ddb6`. Its changed-file inventory contains
the verifier import, Software-owned adapter/CI, and diagnostic documentation only;
no engine implementation file changed. PM did not inspect or review adapter code.

PM independently reproduced the imported `tests/playback_draft8/` tree as
`ff810814dbc8079c6903e6f85ed7ee312abd3076`, identical in mode/blob/path to all 57
files at verifier publication `7a22cbb4447c40c51b7c8b2282a685ed30a46ba6`.
Fixture generation, the package self-test and saved P1-R4 replay pass. The frozen
spec hashes pass. `tools/ci/all.sh` remains green except for the known, intentionally
visible missing-WP-11-manifest gate. PR Actions run 34725672675 likewise reports
eight green jobs and only `golden suite (awaiting WP-11 fixtures)` red.

The retained Software diagnostic reports current main cannot compile the adapter
because its header predates frozen DRAFT-8, while held PR #20 compiles and then fails
to link on exactly `tape_seek`, `tape_set_rate`, `tape_render` and `tape_service`.
No engine implements those operations; no stub or product evidence was produced.
This is an authenticated integration/diagnostic return, not code review or product
acceptance. Software retains authority to review/merge the test-only PR and develop
a held implementation candidate; independent Verification must disposition any
future raw product observation before implementation merge.

## Verification #6 blocker

Verification correctly stopped before authorship. Frozen acceptance text calls for
an “exact table” but provides only the continuous envelope, leaving cadence, Q16.16
rounding, render counts, hold window and reverse initial condition undefined. Those
choices change byte-exact PCM and are PM-owned product inputs.

PM resolves P1-R5-V01 by publishing [WP-08](../PACKAGES/WP-08.md), the missing
external deterministic table and call schedule. It samples the already-issued linear
envelope every 100 ms for 1.5 seconds, uses enumerated signed Q16.16 values, observes
500 ms at ±12.0×, and fixes service/render chunking and direction starts. This is a
package-level verifier/firmware vector referenced by the frozen acceptance row. It
does not change the authenticated TapeFS/API/acceptance bytes or their arithmetic,
nor does it accept a fixture or PCM.

## Continuation and holds

[Software #63](https://github.com/mmsanders/Digital-Tape/issues/63) owns review and,
if sound, merge of PR #60 as test/adaptor integration; only after that exact tree is
on main may it prepare an unmerged playback implementation candidate and raw product
evidence. [Verifier #7](https://github.com/mmsanders/digital-tape-verification/issues/7)
owns independent boundary/ramp/side-switch authorship against the exact WP-08 table.
Hardware and Surge have no useful bounded work this round.

PR #20 remains draft and held. No header-only main update, engine merge, test
weakening, synthetic relabel, PCM/golden/listening acceptance, card qualification,
purchase, fabrication, charging or frozen-hash change is authorized. Issue closure
continues to mean only that a lead stopped.
