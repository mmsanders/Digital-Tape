# Software — P1-R1-SW

**PM-issued 12 September 2026 UTC · Opus / Claude Code · no subworkers.**
Read [role](../ROLES/software.md), [round](README.md), [PM findings](P1-R1-PM-REVIEW.md),
[integration](../VERIFICATION-INTEGRATION.md) and tests/mount_draft8/COVERAGE.md.
Normal Software authority applies, narrowed by this round's engine boundary.

## Assignment

1. Fetch main and record SHA. Import **all tracked files**, byte-for-byte with
   executable modes, from verifier tests/ops_draft8/ at
   `a91138667673fcf19dc9e83c9034322b982b1771` into the same product path.
   Expected tree: `c8a43df69a6be8e2c34bf79a1d79933abf48286a`.
   Preserve historical self-test logs. Record source SHA/tree/file list and the
   diagnostic-only limitation outside the imported directory. Land this test-only
   import before any newly covered engine merge; no engine code in that import.
   P1-R1-V01/V02/V03 remain open in this baseline.
2. Run self-test and synthetic runner; label results synthetic. Build the adapter
   defined by imported ADAPTER.md with actual public tape.h, caller-owned storage,
   harness-owned sparse block callbacks and finite service guard. No private
   allocator/sequence helpers, invented API, fixture edits or outcome substitutions.
   Keep adapter work separate from the verifier oracle.
3. Attempt one diagnostic run against existing held #20 source at
   `2e0e8a4b7bff42797ac37901196e5ea348b2e392`; record any rebase exactly.
   If operations/symbols are absent, return precise compile/link/API gaps.
   **Do not implement missing recording/reset functionality to finish this round.**
   No new engine changes or engine merge are assigned in P1-R1.
4. Preserve complete evidence: product/engine/test/adapter SHAs, clean/dirty build
   state, compiler/flags/library and executable hashes, commands, exits, raw
   stdout/stderr/callbacks and exact input/output VO08 files with hashes.
   Baseline runner deletes temporary media: use an external wrapper to preserve
   envelopes before exit, without changing verifier assertions/runner. Missing media
   means incomplete evidence. Record public-call results, accepted frame count,
   remount results and finite service guard separately.
5. Produce a path/behavior/dependency matrix for the smallest possible covered
   mount split from #20. The 289/289 disposition does not prove mixed files or
   arbitrary later code safe. Submit the plan, not a wholesale merge. Keep WP-11
   missing-goldens failure visible.
6. Supply a read-only VR-P1-001 proposal: actual check names/triggers and a
   main-protection configuration compatible with Software integration and PM
   document publication. Do not enable/bypass rules, hide WP-11 failure or change
   repository settings. Michael decides that separately.

## Return and stop

Publish docs/REVIEW/returns/P1-R1-SW.md with immutable test-import/adapter links,
raw-run location or blocker, split matrix, actual checks and residual holds.
Keep product implementation changes held. If a revised verifier package appears,
record its SHA for PM; do not silently switch test versions mid-run or expand this
assignment. PM reviews the revised source next.

Stop after this return. Independent disposition belongs to Verification. Two VT8
cases do not accept WP-07, recording, full commit durability, state, PCM,
WP-10/11/12a/36 or all #20. Return non-mechanical changes to PM/Verification.
