# Verification — P1-R1-V

**PM-issued 12 September 2026 UTC · Sol / separate Work chat · no subworkers.**
Read [role](../ROLES/verification.md), [round](README.md) and
[PM review/reproducers](P1-R1-PM-REVIEW.md). Report independently to PM.
The 289-case raw mount disposition is received and recorded. Do not redo unchanged
paper review or request the gzip logs again; no broader acceptance follows.

## Assignment: make the two-case operation package auditable

Start from verifier main `689c41909e6bbec499aeb0243008222d7a1c9f64`; record actual
input SHA and any subsequent changes. Product DRAFT-8 remains normative.

1. Independently reproduce/disposition **P1-R1-V01/V02** against TapeFS §§7–8 and
   Engine API §§6–7. Add ordered recording durability checks (including the
   chunk-data barrier before metadata), whole-trace checks for illegal I/O by the
   scripted calls, callback range/result validation and targeted negative controls.
   Preserve legitimate reads, public semantics and narrow case scope. PM's synthetic
   reproducer demonstrates a gap; it is not a replacement oracle or permission to
   consult implementation.
2. Resolve **P1-R1-V03**: persist hash-bound raw input/final VO08 media, complete
   observations and build/source provenance; enable offline verdict recomputation
   without the engine. Test missing/tampered evidence failure. Authenticate actual
   fetched spec bytes against DRAFT-8, not just hardcoded provenance labels.
   Clarify adapter/public-call result evidence and synthetic/product identification.
3. Reproduce both conforming cases and all original six mutations plus new controls.
   Run the synthetic adapter and replay saved artifacts. Publish immutable source
   and an explicit coverage/exclusion matrix tied to assertion IDs/spec sections.
   Synthetic runs are never product acceptance.
4. Resolve **P1-R1-D01**: mark DRAFT-6 WP10/WP11/WP12A plans historical or reconcile
   active claims with DRAFT-8 citations. Supply a short dependency-ordered next-tranche
   proposal for playback/goldens, recording/random edits, complete crash closure
   (including V7-001 two-interruption closure), and long-operation/state coverage.
   Planning only for these additional tranches this round, not all tests at once.

## Boundaries and return

Do not inspect engine source, #20 diff/mixed discussion, private implementer tests
or uncovered implementation to derive expectations. Software is importing the old
baseline and building an adapter; missing-operation gaps may result. That work does
not change your oracle or require waiting. No spec edits or relaxed expectations.

Publish a verifier-main return with immutable commit, changed files, old/new package
hashes, finding dispositions, actual tests, saved evidence/replay, adapter-contract
changes and residual exclusions. Identify genuine spec ambiguity for PM; old V6
labels alone do not reopen frozen bytes.

Stop when the revised package and plan are ready for PM review. Real-product result
disposition against revised tests is a subsequent bounded return after exact import
and complete raw evidence. No full WP-07/WP-10 acceptance, operations/state freeze,
WP-11 completion or hardware qualification. Hardware audit is not assigned to
Verification this round; PM will schedule it with an exact evidence packet.
