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

**Active package: hardened verifier tree `4a862fa69ccb2fc4c9afe59c9c9161c3470f9263`**
from `mmsanders/digital-tape-verification` commit
`dcc4d7cdb357cf0b082071390c762c25b650f617`, directory `tests/ops_draft8/`.
All 11 tracked files imported verbatim with modes preserved; the product subtree
hash reproduces that tree exactly. The earlier baseline tree
`c8a43df69a6be8e2c34bf79a1d79933abf48286a` (source
`a91138667673fcf19dc9e83c9034322b982b1771`) is **provenance only** and is no
longer the active package; PM superseded it for integration.

The hardened package adds `hardened.py` (trace, ordering and public-call-result
validation layered over the unchanged `oracle.py`), `replay.py` (offline verdict
recomputation from a hash-bound evidence bundle) and `COVERAGE.md`. `runner.py`
now retains the input and final VO08 media, stdout, stderr, observation, per-case
result and a manifest, and requires explicit adapter source/build provenance,
verifier source identity and a synthetic-versus-product adapter kind.

Reproduced locally: `python3 tests/ops_draft8/selftest.py` passes — two conforming
observations, **twelve oracle controls**, tampered-spec-bytes detection, and both
missing-evidence and tampered-evidence replay failures. A synthetic evidence bundle
was created against the authenticated DRAFT-8 spec bytes and replayed offline;
both pass. **All of this is synthetic runner/oracle plumbing evidence. No engine
ran.**

Structural Rule 1: this import remains test-only and lands before any corresponding
engine implementation. **`VT8-001-RB-ALLSLOT` and `VT8-001-REC-ALLOCSEQ` have still
never executed against an engine**, so allocation events and all-slot
running-sequence consumption remain unobserved. No assertion, fixture, expected
sequence, operation argument, ordering, range or exclusion was changed.

The mechanical adapter is Software-owned at `tests/ops_adapter/`, outside the
verifier tree, and was adapted to the revised observation contract: the
`VT8-OPS-OBSERVATION-1` envelope, ordered public-call results with the fields each
script depends on, product/synthetic identity, complete callback rc and range
records including unexpected callbacks, and a finite service guard. Media retention
and offline replay are now the runner's responsibility, so the older `preserve.sh`
wrapper was removed as obsolete.

It **compiles clean** against the held PR #20 public header and still fails to link
on the same six declared-but-undefined public symbols — `tape_seek`, `tape_arm`,
`tape_feed`, `tape_service`, `tape_commit`, `tape_reset_side_b` — so no product
observation for this tranche is obtainable from any engine that exists today. It
also does not compile against current main, whose public header predates the frozen
DRAFT-8 API. Consequently **the adapter's observation schema has never been
exercised against a real engine**; it is written against the imported `ADAPTER.md`
and `hardened.py`, and the first product run is where it is actually tested.
Diagnostic-only: raw evidence in
[the P1-R2 packet](verification/runs/2026-09-12-r2/README.md) and
[the P1-R2-SW return](REVIEW/returns/P1-R2-SW.md); the superseded baseline
diagnostic is in [the P1-R1 packet](verification/runs/2026-09-12/README.md).

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

## P1-R4 playback-package disposition — 12 September 2026 UTC

Verification issue #4 published the first independently derived three-family
playback package at verifier main
`48be424c5b5959c6e87c645a49ecc33a7026a30a`, tree
`c6c1418a016220cca216eeb42f782a09556d6020`. It covers forward 1.0x, seek boundary
first-frame behavior and exact -1.0x reverse-from-end candidate PCM. Deterministic
fixture regeneration, package self-tests and 3/3 saved synthetic replay reproduce.

PM found that changing only the saved manifest's adapter kind from synthetic to
product and its adapter ID still replays PASS while the observation retains the
original synthetic identity. Replay also ignores the recorded adapter exit, and the
runner deletes an existing evidence destination. Verification #5 then owned the
bounded identity, exit, timeout and evidence-retention correction, so import remained
held at this P1-R4 checkpoint. The corrected disposition follows. Candidate PCM
remains unlistened and unaccepted; no product engine has run it and no WP-08/WP-11
acceptance follows.

## P1-R5 corrected playback-package disposition — 12 September 2026 UTC

Verification #5 published the corrected source at
`d565403907ecea331a5dcf63efbd1c08d8bd732e`, pre-evidence
`tests/playback_draft8/` tree `aaa6dde86c9a0bdffa2b375361049ac670e26467`.
Verifier main `7a22cbb4447c40c51b7c8b2282a685ed30a46ba6` adds the retained P1-R4
synthetic evidence and return; its complete playback subtree is
`ff810814dbc8079c6903e6f85ed7ee312abd3076`.

PM reproduced deterministic generation, playback self-tests, the full verifier
suite and saved 3/3 offline replay. The corrected evidence schema binds manifest and
observation adapter kind/ID, source/build declarations, a retained zero-exit record,
complete file hashes and verifier source identity. Negative controls catch the prior
manifest-only relabel and ID mismatch plus missing provenance/exit/evidence, nonzero
exit, bounded timeout, tampering and verifier drift. A nonempty evidence destination
is rejected before writes and its existing sentinel bytes survive.

This package is ready for an exact mechanical import from the complete published
tree. It is not a product execution or independent acceptance of PCM or engine
behavior. Software #59 owns the import and no-stub product-adapter diagnostic;
Verification #6 independently owns the next playback boundary/ramp/side-switch
tranche. Human listening remains a separate Michael assignment only after product
PCM evidence exists. PR #20 and every remaining coverage, hardware and safety hold
stay in force.

## P1-R6 draft import and schedule-blocker disposition — 13 September 2026 UTC

Software #59 returned draft PR #60 at
`b2c16aac98605a94206e4af2fc04d8db1305ddb6`. PM authenticated its complete
`tests/playback_draft8/` subtree as
`ff810814dbc8079c6903e6f85ed7ee312abd3076`: all 57 mode/blob/path entries match
verifier publication `7a22cbb4447c40c51b7c8b2282a685ed30a46ba6` exactly. Generation,
self-test, saved P1-R4 replay and the frozen-spec gate reproduce. Actions run
34725672675 has eight green jobs; only the existing missing-WP-11-manifest job is
red. PM did not inspect or review Software-owned adapter code.

The Software diagnostic retains no product evidence because no engine implements
`tape_seek`, `tape_set_rate`, `tape_render` or `tape_service`. Current main also has
the pre-DRAFT-8 mount signature. PR #60 is therefore test/adaptor integration plus
an honest compile/link result, not product execution or acceptance. Software must
review/merge within its authority; any later implementation remains unmerged until
independent Verification dispositions the raw product observation.

Verifier main `a6b2630a55f7260a74e529d22f84aa94b8d7341f` records P1-R5-V01:
the acceptance criterion refers to an exact scrub table but the authenticated bundle
contains only its continuous envelope. Verification correctly published no partial
oracle. PM resolves the missing external input in
[the WP-08 package](PACKAGES/WP-08.md): exact 100 ms timestamps, signed Q16.16 rows,
render counts, a 500 ms hold window, direction starts and service/render subdivision.
The DRAFT-8 files and hashes do not change. The new table is an input for independent
authorship, not accepted PCM or a product result.
