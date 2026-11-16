# Changing the engine or the format — the strict track

This is the full procedure for the strict track named in [CLAUDE.md](../CLAUDE.md) §3. It
applies to `engine/`, the frozen product spec (`spec/tapefs-v1.md`, `spec/engine-api.md`,
`spec/acceptance.md`), the goldens and the imported verifier packages under `tests/`.
Nothing else is on this track ([ADR-210](DECISIONS.md#adr-210--light-process-outside-the-engine)).

The engine is pinned and the format is frozen, so this procedure is rarely needed. Read it
when an engine or format change is actually proposed, not before.

The text below is the working agreement's former §3, unchanged.

## Spec → independent tests → implementation

1. **Structural Rule 1:** corresponding independent tests land before new engine
   implementation. Public branches do not waive verifier blindness. A narrow tranche
   licenses only its documented coverage boundary.

   **They land in history, not necessarily in a separate merge.** A tranche is one
   branch carrying two commits: an import commit byte-identical to a verifier
   publication whose hash predates it, then the implementation commit. The protocol is
   Verification publishes → Software returns that branch → CI proves it → Verification
   disposes blind → PM disposes. What disappears is a round whose only product was a
   separate merge commit; what does not disappear is blindness.

   Review-discovered regressions on a held branch preserve the original reviewed
   lineage (ADR-206). A new, immutable review package may follow the reviewed
   implementation only under the independently tested provenance/order contract:
   full reviewed-ancestor identity, independent publication attestation, import
   before the corresponding corrective implementation, no prior imported-tree
   edits and no combined import/fix commit. This does not claim retrospective
   tests-first coverage or waive the rule for unrelated new behavior. The gate
   correction is independently disposed and integrated through PR665/ADR-209.
   The current gate authenticates that narrow route; all other ordering stays strict.

   The guarantee moved into CI, it was not dropped.
   `.github/workflows/evidence-integrity.yml` proves the imported subtree is
   byte-identical to the declared publication (`tests/IMPORTS.json`), that ordinary
   verifier-tree changes precede `engine/`/`firmware/` changes, that late review imports
   satisfy the independently attested exception, and that no commit does both.
   Package self-tests/offline replay are green, and spec bytes in evidence trees
   match `spec/VERSION.md`.
   `tools/ci/verify-structural-rule-1.py` proves that ordering check goes red.
   The implementer still cannot tune an assertion: the tree it imported is fixed by a
   hash Verification published first, and `tests/IMPORTS.json` is Michael-owned in
   CODEOWNERS, so declaring a different tree is not a lead's to do quietly.
   `.github/workflows/verifier-publication.yml` adds the cross-repository half (ADR-157):
   every cited `source_commit` must be on `digital-tape-verification/main` with its
   declared tree. A PR head is not a publication; Verification merges its own.
2. Integration is mechanical only if it cannot change whether correct code passes:
   include/link paths and equivalent symbol/type plumbing. Assertions, values,
   tolerances, ordering, ranges, skips and case deletion are not mechanical.
   Return these to Verification/PM; never relax tests to fit code.
Private or unpublished scaffolding is not an exception to a task's tests-first rule.
Declare interfaces before code where needed; publish the independent expectations
before implementing covered behavior.

3. Spec/test disagreement is a PM decision, not bargaining with the implementer.
   An API absent from the spec is a finding; do not invent it to compile a test.
4. Authorship, harness checks, engine execution, independent disposition, merge and
   package acceptance are separate facts. A green run alone does not accept a
   package or freeze operations.
5. Goldens are independent, byte-exact and human-listened. Regeneration requires
   logged PM approval. Missing fixtures stay visible; do not hide a red gate.
6. **Proportional evidence (ADR-195).** A criterion is proved by a test of the outcome it
   names plus a negative control that shows the test can fail. Mechanism forensics (kernel
   traces, PID/handle attribution) are required only where a criterion names them. A method is
   qualified by its own controls in the tranche that uses it, not in a separate round.

Completed verification work is published on digital-tape-verification/main and
imported with source SHA, files and coverage into Digital-Tape. All checkpoint
material needed to resume is here. Future deliveries may use that repo or Michael’s
transport. Access failure never justifies opening implementation to fill the gap.
PM authenticates exact candidate hashes before issuance.

The phrase **Request Independent Review** is an advisory opt-in, not acceptance or
a waiver. Tooling/hardware and engine behaviour already covered by landed tests may
use it. Untested engine review requires PM escalation and preserves blindness.
