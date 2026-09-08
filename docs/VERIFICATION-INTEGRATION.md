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
result disposition is pending; no new engine code has been merged to main.

Safe documentation and raw observations have been extracted from #20. Its remaining
code/harness boundary includes covered and uncovered behaviour in shared files.
Do not merge those files wholesale. A further split requires preserving the tested
behaviour and reviewing dependencies, or additional independently authored coverage.
Read the [Verification brief](REVIEW/verification-lead.md) for the bounded next return.

Publication order is recorded by the actual merge ancestry: exact spec #25,
independent tests #27, then software branch reconciliation. Importing hardware #18
and this documentation does not grant an engine coverage exception. The independent
test directory and both canonical integrity manifests remain unchanged.
