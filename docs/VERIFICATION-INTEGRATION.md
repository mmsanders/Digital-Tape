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

## Imported playback/golden tranche — 12 September 2026

Source: `mmsanders/digital-tape-verification` publication
`7a22cbb4447c40c51b7c8b2282a685ed30a46ba6`, directory `tests/playback_draft8/`.
All 57 tracked files imported verbatim with modes preserved (six executables); the
product subtree hash reproduces `ff810814dbc8079c6903e6f85ed7ee312abd3076` exactly.

Imported from the **publication**, not from the corrected source commit
`d565403907ecea331a5dcf63efbd1c08d8bd732e` (tree
`aaa6dde86c9a0bdffa2b375361049ac670e26467`): the publication adds the retained
18-file `evidence/p1-r4-synthetic/` bundle, and importing the source tree alone
would have omitted it. Both hashes were authenticated before import.

Reproduced locally: deterministic fixture and candidate-PCM regeneration; the
package self-test — three families plus **18 controls** covering seek/boundary/grid
mutations, callback I/O during render, altered fixture and PCM bytes, tampered spec,
manifest-only kind relabel and ID mismatch, missing provenance, missing and tampered
evidence, tampered verifier identity, missing/nonzero/timed-out adapter exit, and
nonempty-destination rejection; offline replay of the retained P1-R4 v2 bundle
(PASS); and confirmation that the historical P1-R2 v1 bundle is refused as the wrong
schema rather than silently upgraded. **All synthetic — no engine executed.**

The candidate PCM under `tests/playback_draft8/golden/` is verifier-derived oracle
bytes, **not accepted WP-11 goldens**: Michael's human listening is a separate later
step, and nothing here is a listening claim.

Structural Rule 1: test-only, landing before any corresponding engine
implementation. **No playback operation exists in any engine.** The product adapter
is Software-owned at `tests/playback_adapter/`, outside the verifier subtree, and
identifies as `product` with a fixed adapter id; it compiles clean against the held
PR #20 public header and fails to link on four declared-but-undefined symbols —
`tape_seek`, `tape_set_rate`, `tape_render`, `tape_service` — none of which is
defined by either the main or the #20 archive. It does not compile against current
main, whose header predates the frozen DRAFT-8 API. Therefore **no product playback
evidence exists**, no v2 evidence directory was created, and the adapter's
observation schema has never been exercised against a real engine. Diagnostic-only:
raw logs in [the P1-R5 packet](verification/runs/2026-09-12-r5/README.md) and the
dependency/split map in [the P1-R5-SW return](REVIEW/returns/P1-R5-SW.md).

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
authorship, not accepted PCM or a product result. Software #63 owns ordered PR #60
integration and a held implementation/evidence candidate; verifier #7 owns the new
independent package.

## P1-R7 complete-playback and product-evidence disposition — 13 September 2026 UTC

Software merged PR #60 as `4517db7efba0d1a0933fc0dda1a607c5441197b7`.
The product `tests/playback_draft8/` tree is exactly
`ff810814dbc8079c6903e6f85ed7ee312abd3076`; Phase A changed no engine file.

Independent Verification #7 published the complete sibling at verifier main
`121f5f7ab03c9ce08c38329e518c49a1ca9b65a5`. Its pre-evidence source is
`54789cc6e6bbfd942857374e2e0b3305d05d2f2c`, source tree
`5527547b72b3e5c6d6fb91d41f3aa3bfa86fab7d`; the publication subtree with retained
synthetic evidence is `863b3a49c421bda1bebcf1a9760149bec7051048`, and the saved
evidence tree is `c67ea8fa128e06393839f968ae3cc949d84e5f2a`. PM reproduced
deterministic generation, ten families, sixteen new behavioral controls, all retained
P1-R4 controls, offline replay and the full verifier suite. No product code or adapter
was inspected. The sibling is ready for exact mechanical import, not acceptance.

Held draft PR #64 is currently `3dc5abb85e5b30200cf1553b9a06a83bc83c6d36`.
Its retained three-family product evidence tree is
`c1f173224ef5a312db438bd796e0090c4f329b5c`; offline replay passes, and PM reproduced
the same three byte-exact outcomes using the existing public adapter at that head.
That is a diagnostic result only. The committed return and packet incorrectly call
the pre-implementation merge `c108356c640e971967fb3a00d87e3f6003a129db` the
candidate head, while the packet and manifest also state different `libtape.a` hashes.
The manifest does not name the exact implementation commit. The evidence therefore
cannot yet support independent disposition of PR #64. Preserve it as superseded raw
history; Software must produce a fresh exact-head/build-bound bundle after importing
the complete sibling. Verification receives no product-observation issue until that
dependency is ready.

## P1-R8 complete import and contract-conflict disposition — 13 September 2026 UTC

Software #66 merged Phase A through PR #67 at product main
`14a593120b2400ea5baac79a3b143cd702edcdc0`. The product
`tests/playback_complete_draft8/` subtree is exactly independent Verification's
published tree `863b3a49c421bda1bebcf1a9760149bec7051048`, including retained
synthetic evidence tree `c67ea8fa128e06393839f968ae3cc949d84e5f2a`. The earlier
playback tree `ff810814dbc8079c6903e6f85ed7ee312abd3076` is unchanged. Clean
generation, self-test and synthetic replay reproduce; the only full product-gate
failure is the deliberate missing-WP-11-manifest gate. No engine file landed.

Held PR #64 is `bc53076448112ec3015de40e71c229e17d225c2f`, with tested-code
ancestor `43d2dbaa6434942df37e165b25edc6d45135fee2`. Its complete product
bundle is bound to that code and one build identity. Offline replay with the unmodified
published package reaches the oracle and fails at its first disagreement. PM did not
inspect implementation or adapter source and does not accept Software's diagnostic
scratch oracle.

Frozen-contract review identifies exactly three verifier-package defects: the
`intmin` family drops frame 0 contrary to §§6.2–6.3; the reverse scrub generator uses
the V5-005-rejected `max_pos - 1` instead of `(total_frames - 1) << 32`; and both
side families expect integer 6 where the frozen enum makes `TAPE_ERR_UNDERRUN` 18.
[P1-R8](REVIEW/P1-R8-PM-DISPOSITION.md) logs PM approval to regenerate only the
affected verifier-owned reverse candidate/evidence from the frozen grid snap. This is
package correction authority, not PCM/golden/listening acceptance.

Independent Verification owns the correction without consulting product code or
Software's diagnostic oracle. PR #64 remains draft and held; Software rerun and
candidate disposition wait for a corrected immutable verifier publication. Every
other acceptance and safety hold remains.

## P1-R9 corrected complete-playback publication — 13 September 2026 UTC

Verification #8 published its independent correction at verifier main
`62b18deb8b4fbe6e797b00d792ee9f46ac0a8059`. The corrected pre-evidence source
commit/tree are `1c1489a5b1c10f2baa8425557fd7bdfde3225575` /
`43ca6f6bbc1990d5ced6de3b2ce0d04f00aa7519`; the final complete package tree is
`6dbb23bb4626238b0f22427031a551d2ece454fd`, with retained P1-R8 synthetic
evidence tree `d867fc68c80a2217508868c4b339d160b55ec2cc`.

PM authenticated the changed-path and file-mode boundary and reproduced deterministic
generation, all ten corrected families, twenty controls including named F-1/F-2/F-3
negatives, the retained P1-R4 suite and eighteen controls, saved replay and the full
verifier suite. Only reverse scrub candidate PCM changed among generated inputs, from
`faae5cf8...` to `5f1794e8...`; fixtures and forward candidate remain byte-identical.
Frozen hashes, WP-08, the earlier playback tree `ff810814...` and prior complete
synthetic evidence `c67ea8fa...` are unchanged.

The saved P1-R8 observation is synthetic and binds the corrected source identity; it
is not a product run, golden, listening or acceptance. The corrected publication is
ready for exact mechanical product import. Structural Rule 1 requires that replacement
to land on main without engine/firmware changes before the held candidate reruns. The
existing failed product bundle remains immutable. PR #64 stays draft and held, and
Independent Verification receives no product-disposition issue until a fresh bound
bundle exists.

## P1-R10 corrected import and product-bundle routing — 13 September 2026 UTC

Software #70 merged the corrected complete publication through PR #71 at product
main `d52730ffb4c9d8e634eded9caca208dcacb0d046`. The product subtree is exactly
`6dbb23bb4626238b0f22427031a551d2ece454fd`, retained P1-R8 synthetic evidence
is `d867fc68c80a2217508868c4b339d160b55ec2cc`, retained P1-R6 synthetic evidence
is `c67ea8fa128e06393839f968ae3cc949d84e5f2a`, and no engine/firmware file changed.
PM reproduced generation, self-test and saved replay from clean main.

Held PR #64 head `c18aa42579ef7c5ea92a4d70972d6a2daa6698bb` retains a fresh product
bundle under `docs/verification/runs/2026-09-13-r9/product-evidence/`, built from
pre-run code commit `5f44b97fe9fb3342fce3b58236a75ea27b4898a6`. The engine, firmware,
product adapter and harness are unchanged from the earlier failing candidate. The
manifest binds the exact corrected verifier source/tree, product adapter identity,
zero exit, empty stderr and one consistent build identity. PM ran the package's
unmodified offline replay against the committed bytes; all ten families pass and
all seven PCM outputs are byte-exact.

This is a ready product observation, not independent acceptance. Verification issue
[#9](https://github.com/mmsanders/digital-tape-verification/issues/9) owns the
narrow disposition using the raw evidence and verifier-owned package while remaining
blind to product/adapter source. PR #64 stays draft and held. Candidate PCM remains
unlistened and is not a WP-11 golden; all uncovered families and current product,
hardware and safety holds remain.

## P1-R11 independent product-observation disposition — 13 September 2026 UTC

Verification issue #9 published one findings file at verifier main
`17d345ef23a9bbdb3e781f3451f4a8797a1a6f1c`, directly atop assigned input
`62b18deb8b4fbe6e797b00d792ee9f46ac0a8059`. It changed no test, oracle,
fixture, candidate or workflow. Verification remained blind to product/adapter source
and independently authenticated the complete raw bundle, staged-package identity,
product adapter agreement, exit, all callback and public-call records, exact scrub
schedule and saved-result equality.

The narrow disposition accepts the ten recorded product-observation families at
evidence commit/tree `c18aa42579ef7c5ea92a4d70972d6a2daa6698bb` /
`34bad4611b6849ed586c7ec701fa7ddafef0cb12`, whose sole parent is pre-run code
commit `5f44b97fe9fb3342fce3b58236a75ea27b4898a6`. PM recomputed the report's
manifest, observation and result hashes and reran the unmodified offline replay; all
match and pass. Seven PCM-bearing families are byte-exact; the three no-PCM families'
call/state observations pass.

This is independent acceptance of the exact raw observations only. PR #64 contains
broad held #20 ancestry and cannot merge. Software #75 owns a fresh clean draft from
main, the narrowest dependency-complete accepted playback slice, and a new exact
product bundle. That bundle requires its own independent disposition before any
implementation merge. Candidate PCM remains unlistened and not a WP-11 golden;
all other holds remain.

## P1-R12 clean split and exact-evidence routing — 13 September 2026 UTC

Software #75 returned held draft PR #77 at
`f100937aed1437401218003db3edbb07d8e4f543`. Its evidence commit has sole parent
`86eb3b77756042c365e2d0353018b981c39c99e8`, the pre-run code commit directly
atop assigned base `6a8b2fb481cf43a8d84aad6c74336fc4a2a50d96`. Neither the broad PR #20/#64
heads nor the accepted broad code-under-test are ancestors. Eleven carried files
have exact accepted blobs; `alloc.c` and allocator scaffolding are absent. The one
required mount dependency, `tape_chunks_for_frames`, is isolated in `chunks.c` and
is claimed only through the independently covered TapeFS §9.3.3 row-3 mount path.
This boundary remains held and is not PM source review or acceptance.

The clean run, product-evidence and staged-package trees are respectively
`a6c1dfeb1e35399301adcabf5adc90ef0e067307`,
`1671bcb37abccb21cb59234792ba35e984a3eb5f` and
`b097c2a91fabf55677c9a7f866020d22d83ee90e`. PM authenticated every one of the
30 manifest-bound files, exact corrected source tree `6dbb23bb...`, product identity,
zero exit and empty stderr. Offline replay passes. A fresh PM run reproduces exact
observation/result hashes `24a35a3c...7ce4` / `1fb3437a...f742`; a fresh mount run
reproduces all 289 case records, differing only in the expected local executable
path/build-hash provenance line. These are PM observations, not independent acceptance.

Verification issue #10 owns a blind disposition of the exact bundle and mount log,
including the named §9.3.3 row-3 cases. It may inspect verifier-owned packages, public
contracts, raw evidence and Git identity metadata only. PR #77, #64 and #20 remain
draft/held. No source, complete WP-06/WP-08, helper design, PCM/golden/listening or
merge acceptance follows; all uncovered product and hardware/safety holds remain.
