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

## Imported VT8-001 operation tranche — 12 September 2026

Source: `mmsanders/digital-tape-verification`, immutable commit
`a91138667673fcf19dc9e83c9034322b982b1771`, directory `tests/ops_draft8/`.
All 8 tracked files imported verbatim with executable modes preserved; the product
subtree hash reproduces the expected tree
`c8a43df69a6be8e2c34bf79a1d79933abf48286a`. Both historical self-test logs under
`evidence/` are unmodified. No engine code is part of this import.

Reproduced locally: `python3 tests/ops_draft8/selftest.py` passes, accepting two
conforming synthetic observations and catching all six required mutations, with
output byte-identical to the package's own `evidence/selftest.log`;
`runner.py --adapter _synthetic_adapter.py` reports 2/2. **Both are synthetic
runner/oracle plumbing evidence, not engine runs.**

Structural Rule 1: this test-only import lands before any corresponding engine
implementation. **`VT8-001-RB-ALLSLOT` and `VT8-001-REC-ALLOCSEQ` have never
executed against an engine**, so P1-R1-V01/V02/V03 remain open and allocation
events and all-slot running-sequence consumption remain unobserved. No assertion,
fixture, expected sequence, operation argument or exclusion was changed.

The mechanical adapter required by the imported `ADAPTER.md` is Software-owned at
`tests/ops_adapter/`, deliberately outside the verifier oracle's directory. It
**compiles clean** against the held PR #20 public header and then fails to link on
six declared-but-undefined public symbols — `tape_seek`, `tape_arm`, `tape_feed`,
`tape_service`, `tape_commit`, `tape_reset_side_b` — so no product observation for
this tranche is obtainable from any engine that exists today. The adapter also does
not compile against current main, whose public header predates the frozen DRAFT-8
API. Diagnostic-only: raw evidence and the exact gaps are in
[the run packet](verification/runs/2026-09-12/README.md) and
[the P1-R1-SW return](REVIEW/returns/P1-R1-SW.md).

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
Read the [current assignment issues](ISSUE-WORKFLOW.md) for the bounded next returns.

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
**Not imported by PM at this checkpoint.** Current import/adapter work directions
are in role-labeled issues. P1-R1-V01/V02/V03 require verifier-owned corrections before
this package supports operation acceptance. See [PM review](REVIEW/P1-R1-PM-REVIEW.md)
for reproducible gaps, source commitments and remaining coverage exclusions.
The revised package needs a new immutable source, exact subsequent import and raw
real-product observations independently dispositioned before expanding acceptance.

## P1-R2 package disposition — 12 September 2026 UTC

Verification resolved P1-R1-V01/V02/V03 and D01 in verifier main
`7ca24853ed32ddd327461594a31021cba4a408f3`. The hardened source commit is
`dcc4d7cdb357cf0b082071390c762c25b650f617`; the exact `tests/ops_draft8/` tree is
`4a862fa69ccb2fc4c9afe59c9c9161c3470f9263`. PM reproduced its self-test and offline
saved-evidence replay. The old tree `c8a43df...` in draft Software PR #48 remains
authenticated historical diagnostic input but is superseded for integration.

The hardened package is ready for an exact mechanical product import. That statement
accepts neither an engine nor a product observation. No current engine links the six
operations required by both cases, and no raw product VO08 result exists. Do not merge
a mount split while the §5.5 all-slot running-sequence derivation stays unobservable,
do not import uncovered allocator behavior to satisfy a link, and do not relax the
new evidence contract. Active integration work, if any, is in the Software issue.
