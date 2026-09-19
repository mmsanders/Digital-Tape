# P1-R19 PM disposition — corrected VT8 package and hardware-method returns

**Date:** 19 September 2026 UTC  
**Input product main:** `44aeac087c5f970c30b75a001b95ca7d0c089da4`  
**Input verifier main:** `15dd16eb499f5c148bff7c5b4b67ff75ae7a0f32`

## Decision

PM authenticates Verification #14's corrected VT8 verifier publication and routes
its exact complete `tests/ops_draft8` tree for test-first product import. PM also
authenticates Hardware #99's method returns: PR #87 is ready for an independent
method/tool audit, while PR #92 has resolved B01–B03 and B05–B06 but still lacks an
executable, source-bound sharp-point/sharp-edge screen under B04.

These are routing decisions, not product, card, ruggedization, safety or package
acceptance. PR #20, #64 and #96 remain held. No physical rerun, destructive test,
fabrication, charging, listening or golden promotion is authorized.

## Corrected VT8 verifier package

Verification published source first at
`eb5d7867c604b2c8a07e05597b8b9f07071b539e`, then retained evidence and findings at
verifier main `15dd16eb499f5c148bff7c5b4b67ff75ae7a0f32`. The corrected source operations
tree is `12d2a95e879dd0b7b891387ebdc166f0be0c854e`; the complete published subtree is
`3667a2830ba80dbcedad03b97870d1127001ab59`.

The frozen 60-second geometry now derives 21 chunks and a 23,553-block device:
reserved chunk blocks are `[2048, 23552)` and block 23,552 remains the final reserved
block. Generator-side controls reject a stored/derived chunk mismatch and undersized
media. `VT8-EVIDENCE-2` and the manifest-bound `VT8-ADAPTER-STATUS-1` retain nonzero
adapter status so the runner and offline replay agree; missing, tampered and relabeled
status controls go red.

PM reproduced the package self-test, exact replay of both retained P1-R18 synthetic
cases and the full verifier suite. This authenticates verifier-package correctness
only. The complete tree includes earlier retained P1-R1 evidence as well as the new
P1-R18 evidence; Software must import that exact tree with modes preserved rather
than assembling selected files. Only after the import is on main may Software rerun
the unchanged held PR #96 product adapter and retain fresh evidence. Software must
not expand uncovered implementation or merge the held PR.

## Sustained-write method

Hardware PR #87 head `da97a8534ef6940f1cb8337e9c9fb7b403dc4804` leaves the five
raw legacy JSON records unchanged. Its schema-2 method loops over short writes and
retains each requested and returned byte count, call count, monotonic timestamps,
flush state, offsets, final size, and before/after capacity, free, used and occupancy
values. Analysis derives summaries and evaluates every adjacent-pair window. It also
withdraws the earlier 1.0% agreement statement: the retained legacy records have a
3.0% worst-window spread.

PM reproduced all retained method controls, the hardware regression suite and the
real fabrication gate's same five-blocker closed result. Independent Verification
must now audit this exact head and disposition only method readiness. The old files
still lack schema-2 primitives, and no new card run, A-2 completion, identity,
attribution, atomicity, qualification or production copy result is claimed.

## Ruggedization method

Hardware PR #92 head `33b904a8f5a2d406187e49270231ef011eb2cc44` now specifies the
ordered cumulative drops, trapdoor and tolerances; center-of-mass shake and tumble
mechanics; nine measured checks; direction-aware red controls; staging, restart,
quarantine and dummy equivalence; and quantitative owned-printer controls. PM
reproduced its eleven retained protocol controls and the hardware regressions.

B04 is not closed. Small-parts screening is specified, but sharp-point and sharp-edge
screening remains a summary and R-3 remains a judgement call. Hardware must bind the
internal screen to the current official text and figures in
[16 CFR 1500.48](https://www.ecfr.gov/current/title-16/chapter-II/subchapter-C/part-1500/section-1500.48)
and [16 CFR 1500.49](https://www.ecfr.gov/current/title-16/chapter-II/subchapter-C/part-1500/section-1500.49),
record the source edition/date and applicable intended-age probe basis, transcribe
the exact figure dimensions, forces, motions and pass/fail criteria, and add retained
semantic controls. This remains an internal engineering screen, not a regulatory or
safety certification.

No machine-confirmed A1 Mini usable volume is recorded, so the print packet must not
be rebuilt yet. Missing rugged-test instruments or purchase authority also prevent
physical execution, but neither dependency blocks the document/tool correction.

## Preserved boundary

- Structural Rule 1 remains mandatory: corrected independent tests land before a
  newly covered product change.
- DRAFT-8 and WP-08 remain frozen. Exact accepted playback and mount observations
  stay narrow; source/helper and complete-package acceptance do not follow.
- WP-11 remains red/listening-held. No candidate PCM is an accepted golden.
- Card identity, atomicity, filled-condition qualification and end-to-end copy remain
  open. Fabrication and charging stay closed.
- Ruggedized, child-resistant mechanical design remains a design input before final
  enclosure CAD. No physical safety acceptance follows from a documented method.

The dashboard remains at 13 of 36 fully reached Phase 1 rungs. This round activates
Software for ordered VT8 import/rerun, Verification for PR #87's independent method
audit, and Hardware for B04's exact sourced method closure. Surge and Michael receive
no issue because they have no bounded work in this round.
