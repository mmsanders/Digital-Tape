# P1-R23 PM disposition — clean VT8 acceptance, card-method repair, and print-material route

**Date:** 20 September 2026 UTC  
**Input product main:** `662b07b0bb231f04e12542b905402ef9b980766e`  
**Input verifier main:** `391d6a8308edfca46f639c3a6567c220d7a7b95d`  
**PM issue:** #116

## Decision

1. Accept Verification's narrow disposition of the two exact clean PR #112
   observations. Route the unchanged, history-preserving integration decision to
   Software. This does not accept source, adapter design, invented refusal policies,
   other behavior, complete WP-07 or the verifier package.
2. Authenticate Hardware's PR #87 repair at `e520c2c...` as a bounded candidate for
   another independent method audit. No sustained-write acquisition is authorized
   before that audit accepts the exact repaired head.
3. Record Michael's current print policy: leave the existing library job configured
   for the library printer expected Monday; default new print work to the A1 Mini;
   retain the library for prints too large for the A1 Mini when PLA is suitable.
4. Ask Hardware for a sourced, A1-Mini-proven minimum materials plan and any next
   useful A1 Mini packet. Michael currently owns one spool of white Bambu PLA Basic.
   PETG and TPU are candidate needs, not approved purchases.
5. Advance no roadmap rung in this PM publication. Preserve every current product,
   physical, fabrication, charging, safety, wallet and regulatory hold.

## Verification #18 / clean PR #112

Verifier main `391d6a8308edfca46f639c3a6567c220d7a7b95d`, tree
`742d135b5d02850b69a8e34fb8a71db35012025d`, is a one-file child of
`f00da3ffbaab62833cce52b29c4999934a37a9d2`. The findings SHA-256 is
`6a3c90f04d7ba88c6c38af6495d383221480d1dc6f28032bd04804907d9939a3`.
PM authenticated the one-file return and reproduced the full verifier suite.

Accept the report narrowly. Held PR #112 evidence head
`15fbcfae0085d5e2f2cb983959fe063c2233fa40`, tree
`8f048f0296b7ffdcec216d26236d8d59ad392aa4`, is directly after pre-run code
`20505f4254b36c2100b9b1ec8f78aff8e95e252c`, tree
`305525d207ba60750f45229838c20599fd6fc4be`. The verifier package tree remains
`3667a2830ba80dbcedad03b97870d1127001ab59`; held PRs #20/#64/#96 are outside
the candidate ancestry. The complete packet authenticates, both retained executions
exit zero and the unmodified replay plus independent raw traversal pass.

`VT8-001-RB-ALLSLOT` accepts only the exact reset-Side-B call/transition, all-slot
sequence selection, durability order, unchanged protected regions, selectable B0 and
`free_next == H == 3`. `VT8-001-REC-ALLOCSEQ` accepts only the exact splice-mode
record call/transition, chunk-3 allocation/write, pre-metadata flush, B1 commit order,
sequence 701 and `free_next` transition 3 to 4.

Verification remained blind to product and adapter source. The candidate's splice-
only arm policy and stage-1 `TAPE_ERR_BUSY` policy are explicitly not accepted. They
do not occur in either exact observation: the recording case requests splice and both
cases independently decode at stage 0. Other modes, stage-1 clearing, splice
positions, partial/multi-chunk/short-accept/fault/recovery/warm/zero-frame paths,
atomicity, PCM, goldens, listening and complete WP-07 remain excluded.

Software may now make the exact integration decision. It must preserve the code-then-
evidence history and identities with a merge commit, make no source/evidence change,
keep the excluded policies documented as incomplete, and stop if integration changes
any authenticated byte or needs a scope expansion. PM does not merge product code.

## Hardware #115 / repaired PR #87

The exact repaired head is `e520c2c4de3fb917fb3e0e1bb72a91997cbe8333`, tree
`deece322ca9001c95c002a3c0cf8d937b14f4d29`, with sole parent the rejected head
`10471f37f432c44d6f5beac59d25b3771e057c38`. The repair changes only:

- `hardware/characterisation/audit_sustained_write.py`
- `hardware/characterisation/test_sustained_write.py`
- `hardware/measurements/2026-09-16-sustained-write/README.md`

The acquisition writer is unchanged. PM reproduced 26 retained controls over 30
top-level and 35 nested schema-2 fields. The repair closes nested object schemas,
strict integer identities, finite real timing, ordered final-fsync intervals,
controlled malformed-type rejection, declared window/criterion validation and the
raw-device null-accounting branch. Every named `P1-R21-V01` form now rejects by a
field-specific report rather than by traceback in Hardware's retained suite.

All five schema-1 records remain byte-identical to corrected ancestor
`c0e6a83ae44c2370288594b75915a214ba25deb7`. Card audit and fabrication-gate
controls pass; the real fabrication gate remains CLOSED with the same five blockers.

This is Hardware's self-audited repair. It does not close `P1-R21-V01`, authorize a
physical run or promote any stored result. Independent Verification owns a fresh
method-only audit of exact head `e520c2c...` before any acquisition.

## Printer, library and materials policy

Michael reports that the A1 Mini is currently performing a test print. That is an
owner activity, not a measured result or print-process acceptance. Hardware must not
rewrite the in-progress job's meaning after the fact.

The existing library test remains a library job and is expected to run when the
library is available Monday. Do not resize, split or otherwise reconfigure that test
for the A1 Mini. For new work, the A1 Mini is the default printer. The library remains
available for larger PLA parts that do not fit the A1 Mini. Each evidence record must
identify the actual printer, material, profile and part revision used; results do not
silently transfer across printer/material/process combinations.

Current owned filament is one spool of white Bambu PLA Basic. Hardware must produce
a minimal, sourced recommendation—not a shopping spree—for what additional material
is actually needed, which A1-Mini-compatible brand/product/profile is preferred, and
what drying/storage/nozzle or safety constraints apply. PETG and TPU must each be tied
to a specific part/function and test; Hardware may recommend against either. Open-
frame-inappropriate or unsupported engineering materials are out unless Hardware
identifies a safe supported process. A recommendation is not purchase authorization;
Michael decides every purchase.

Hardware may also identify and prepare one next useful A1 Mini packet if current
dependencies justify it. It must not alter the existing library packet, PR #92's
audit target, or claim that an internally printable packet is physically accepted.

## Routing and stop

- Software receives the unchanged, history-preserving PR #112 integration decision.
- Verification receives the exact PR #87 repaired method for independent re-audit.
- Hardware receives a separate material-selection and A1 Mini packet-planning task;
  PR #92 remains unchanged and held for later independent audit.
- Michael and Surge receive no issue. There is no new immediate hands, wallet,
  branch or protection task.

PM stops after publishing this disposition, refreshing the dashboard, issuing those
three bounded assignments and closing #116. Lead issue closure, an owner-reported
print or a materials recommendation does not imply acceptance or purchase approval.
