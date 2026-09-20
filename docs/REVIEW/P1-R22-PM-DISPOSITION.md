# P1-R22 PM disposition — clean VT8 candidate, rugged-source return, and card-method rejection

**Date:** 19 September 2026 UTC  
**Input product main:** `86a1ba0874812ef4ca052a4dbc6baad2b16addb6`  
**Input verifier main:** `f00da3ffbaab62833cce52b29c4999934a37a9d2`  
**PM issue:** #113

## Decision

1. Authenticate Software's clean held PR #112 and its fresh two-case evidence for
   routing to blind independent Verification. This is not source, helper, WP-07 or
   package acceptance, and PR #112 is not mergeable yet.
2. Accept Verification's exact rejection of Hardware PR #87 as the controlling
   method disposition. The earlier ordered-trace defects are repaired, but
   `P1-R21-V01` blocks every new sustained-write acquisition until the complete
   schema is closed and safely typed.
3. Authenticate Hardware's PR #92 source-method return as a bounded candidate for a
   later independent audit. CS-1 through CS-5 are transcribed for the method only;
   they are not yet independently accepted and do not authorize apparatus, printing,
   physical testing, qualification or a regulatory claim.
4. Advance no roadmap rung. Preserve all held PRs and every physical, fabrication,
   charging, safety, wallet, listening and uncovered-behavior hold.

## Software #110 / held PR #112

The exact held head is `15fbcfae0085d5e2f2cb983959fe063c2233fa40`, tree
`8f048f0296b7ffdcec216d26236d8d59ad392aa4`, with sole parent
`20505f4254b36c2100b9b1ec8f78aff8e95e252c`. That pre-run code commit has tree
`305525d207ba60750f45229838c20599fd6fc4be` and is directly rooted at assigned
main `86a1ba0874812ef4ca052a4dbc6baad2b16addb6`.

PM reproduced that PR #20 head `2e0e8a4...`, PR #64 head `c18aa42...`, both held
PR #96 identities `b26ffa0...` and `088226a...` are not ancestors. The verifier
package tree remains exactly `3667a2830ba80dbcedad03b97870d1127001ab59`.

The evidence commit is structurally after the code commit. Its manifest SHA-256 is
`e0af6d607d21579309ad97abcb89f69be6721e3d63c9226ee9af36799c565f44` and
its run-log SHA-256 is
`e61a5ddfbb6bd3ead1400812fd683617ed1819936e6d80eacb7dcc3bb1bea03f`.
PM ran the unmodified offline replay: both `VT8-001-RB-ALLSLOT` and
`VT8-001-REC-ALLOCSEQ` replay PASS. The independent package self-test, spec hashes,
build, scaffolding tests and 15/15 red-capable meta-gate also pass. CI has ten green
substantive jobs; only the deliberate WP-11 missing-golden job is red.

This authenticates a candidate and raw observation packet only. The implementation
changes ten source/adapter paths and contains branches not exercised by the two cases.
Software explicitly identifies two candidate-only refusals that are not frozen-spec
semantics: splice-only `tape_arm`, and `TAPE_ERR_BUSY` on stage-1 media instead of
the required clearing behavior. Independent Verification must disposition the exact
two observed cases without broadening them and must report whether either invented
refusal contaminates the observed paths or candidate boundary. All other modes,
splice positions, partial/multi-chunk paths, short accepts, fault/recovery paths,
zero-frame behavior, warm state, privileged operations, atomicity, PCM, goldens,
listening and complete WP-07 remain excluded.

## Verification #17 / Hardware PR #87

Verifier main `f00da3ffbaab62833cce52b29c4999934a37a9d2`, tree
`dd2031338601186690474567544a4eaa154a75ec`, is a one-file child of
`e77b61fe420e48444cf0791c74fc7e296ef0ccf6`. The findings blob is
`659837ffd5ed5e8c59ba07f48863238f873b6404`, SHA-256
`cc48b96b85b2981de063b8d522808e6764259652e6aefba54994d21bf449d1da`.
PM reproduced the full verifier suite.

Accept the exact method disposition. PR #87 head
`10471f37f432c44d6f5beac59d25b3771e057c38` closes the prior thirteen-mutation
trace defect, and the five legacy JSON records are byte-identical to corrected
ancestor `c0e6a83ae44c2370288594b75915a214ba25deb7`. That does not make the method
ready for acquisition.

New blocker `P1-R21-V01` is controlling. Thirteen malformed schema-2 forms pass and
one malformed timestamp type crashes the auditor. The failures include reversed
closing-fsync timestamps, missing/unknown nested fsync fields, Boolean sequence and
window identities accepted as integers, integral floats accepted for byte/capacity
counts, unvalidated declared window/criterion metadata, and unknown nested fill or
capacity fields. Hardware must close every nested schema and primitive type, require
finite non-negative integers where specified, order the final flush timestamps,
validate or remove redundant metadata, and retain a targeted red control for each
reported mutation. No physical card run may precede another independent audit.

## Hardware #111 / held PR #92

The exact returned head is `0943571e83126795797c33a0aa92706247dbaa65`.
Its bounded source-method commit changes only:

- `hardware/rugged/protocol.py`
- `hardware/rugged/sharp.py`
- `hardware/rugged/test_sharp.py`
- `spec/hw/VERSION.md`
- `spec/hw/ruggedization.md`

PM reproduced 23 retained sharp controls, 51 independently restated source values
and 42 field-specific red mutations. Hardware's rugged, spec, packet, duplicate and
fabrication-gate control suites pass. The two-plate A1 Mini packet and CAD payload are
unchanged from the preceding held head. The real fabrication gate remains CLOSED with
the same five blockers.

The method now records the authenticated Probe B, sharp-edge tape/apparatus,
exemptions, access rules and applicable conditioning/drop/torque/tension/compression
inputs, while explicitly denying regulatory equivalence or compliance. CS-1 through
CS-5 are closed only as Hardware-authored transcription. Independent Verification
has not audited this exact head, no apparatus exists, and RG-8 through RG-10 remain
open. Therefore no print, probe construction, physical run, qualification, purchase,
child-safety claim or regulatory determination follows.

## Routing and stop

- Verification receives PR #112 first for blind, exact-case disposition.
- Hardware receives only the `P1-R21-V01` method repair on PR #87.
- PR #92 waits held for a later independent audit; Software receives no new work
  while PR #112 is under independent review.
- Michael and Surge receive no issue. There is no new hands, wallet, branch or
  protection action.

PM stops after publishing this disposition, refreshing the hand-maintained dashboard,
issuing those two bounded assignments, and closing #113. Lead issue closure remains a
work-stop signal, not acceptance.
