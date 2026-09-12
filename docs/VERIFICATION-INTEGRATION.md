# Independent verification integration

## Imported mount tranche — 7 September 2026

Source: `mmsanders/digital-tape-verification`, immutable commit
`4ee116fa040bb5ce040325e0076365abf8b0f8f9`, directory `tests/mount_draft8/`.
All tracked files imported verbatim. The nested `spec/` is an authenticated test
baseline, not another canonical publication point; product authority is `spec/`.
All four files compare byte-for-byte with the DRAFT-8 issued through PR #25.

Reproduction: `make -C tests/mount_draft8 check`. Reproduced locally: ten package
self-tests pass, including fixture authentication, 289 fixture verdicts, deliberately
bad observations, negative engine control, missing-engine failure and callback
instrumentation. These are NOT 289 passing engine tests or work-package acceptance.

The imported README, ADAPTER.md and COVERAGE.md are the independent authority for
the test boundary. The verifier's return and clean paper review are reproduced
under `docs/verification/` with their original authorship intact.

Structural Rule 1: this test-only change lands before any newly covered engine
implementation. The main engine still contains the older provisional read path.
Subsequent engine linking/execution is recorded below; the test-only import itself
made no engine-conformance claim. No assertions, expected results, fixture bytes or cases changed.

VT8-001 remains held: allocation events and running cartridge-sequence consumption
are not observable through this mount probe. No allocator, commit, operation,
rendered PCM, complete state-row or full WP-07 acceptance follows from this import.
PR #20 cannot merge wholesale. Full green WP-10, independent WP-11 goldens, WP-12a
and hardware acceptance remain separate requirements.

## Software execution — held implementation

The unchanged probe was linked to the real public header and engine archive.
The original PR #20 head returned 15 failures out of 289; two DRAFT-8 mount
reconciliations yielded 0/289 failures at published branch commit
740c97e998c7672d9e98916102be84430993521b. The [raw run packet](verification/runs/2026-09-07/README.md)
contains both lossless logs, reproduction commands and provenance. Independent
result disposition is now recorded below; no new engine code has been merged by
the P1-R1 PM publication.

Safe documentation and raw observations have been extracted from #20. Its remaining
code/harness boundary includes covered and uncovered behaviour in shared files.
Do not merge those files wholesale. A further split requires preserving the tested
behaviour and reviewing dependencies, or additional independently authored coverage.
Read the [current briefs](REVIEW/README.md) for the bounded next returns.

Publication order is recorded by the actual merge ancestry: exact spec #25,
independent tests #27, then software branch reconciliation. Importing hardware #18
and this documentation does not grant an engine coverage exception. The independent
test directory and both canonical integrity manifests remain unchanged.

## P1-R1 independent return — 12 September 2026 UTC

Source: verifier main `689c41909e6bbec499aeb0243008222d7a1c9f64`.
`findings/mount-observation-disposition-2026-09-11.md` is copied verbatim to
[the same report under docs/verification](verification/mount-observation-disposition-2026-09-11.md).
Verification recomputed 274/289 before and 289/289 after with zero integrity or
verdict defects. PM reproduced its audit; neither a new engine run nor a new
independent package acceptance is claimed. JSONL identifies adapter hashes; the
committed run packet supplies engine-SHA association.

The next baseline is verifier `tests/ops_draft8/` at
`a91138667673fcf19dc9e83c9034322b982b1771`, tree
`c8a43df69a6be8e2c34bf79a1d79933abf48286a`, unchanged at the return commit.
**Not imported by PM.** Software is assigned the exact test-only import, adapter
and diagnostic attempt. P1-R1-V01/V02/V03 require verifier-owned corrections before
this package supports operation acceptance. See [PM review](REVIEW/P1-R1-PM-REVIEW.md)
for reproducible gaps, source commitments and remaining coverage exclusions.
The revised package needs a new immutable source, exact subsequent import and raw
real-product observations independently dispositioned before expanding acceptance.
