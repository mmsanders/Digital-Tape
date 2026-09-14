# P1-R14 PM disposition — corrected cadence package ready for exact product rerun

**Date:** 14 September 2026 UTC  
**PM issue:** [#82](https://github.com/mmsanders/Digital-Tape/issues/82)  
**Input product main:** `a87263aa4f006233d1b855a9736c41995b8343ce`  
**Input verifier main:** `e3a25bf3b9eda6581b5de524e5bd5fa2c032e0da`

## Verifier correction authenticates

Verification issue
[#11](https://github.com/mmsanders/digital-tape-verification/issues/11) returned a
linear three-commit correction directly atop assigned verifier input `bc0f7ec6...`:

1. source commit/tree `1f7fe3f79d326c4a6e37f8c301c97c110d481619` /
   `fe79113bfe600268585b382fab218e2bbf687a7e` changes exactly eight
   verifier-owned complete-playback package files;
2. evidence commit/tree `05e193209542d204669b32f485dad21007a084ee` /
   `006d1a0875797d05bf7d137652ac97209c16c4ef` adds exactly 32 retained
   evidence files after the source existed; and
3. return commit/tree `e3a25bf3b9eda6581b5de524e5bd5fa2c032e0da` /
   `b5bbe816457312169b02da1fe3fe245b9bc08a4f` adds one findings file,
   blob `e46eddfe69c0254b16e0310650e5f969c59e631d`, SHA-256
   `3c4e203c94125e0a5fa642dc937c8c58247ebe8560c6f7b19f0e3d9ebbc8a392`.

The corrected package subtree at the evidence commit is
`467a34bb0a84672c5bdef9059f2dd326d6435eb6`; retained P1-R13 synthetic
evidence is `3323542c187f4121beddb3c8960ed2e35992e586`. PM matched every reported
source mode/blob/SHA-256, all five tree identities and all 30 manifest-bound files;
there are no missing or unbound evidence paths. Frozen DRAFT-8 and WP-08 hashes match.
Both scrub candidate PCM hashes remain unchanged.

PM reproduced deterministic fixture/candidate generation, the package self-test,
saved offline replay and the full verifier suite. Both scrub directions contain 698
render requests and 698 immediately preceding completed service sequences across 16
rate rows. The separate forward and reverse controls reconstruct the old once-per-row
cadence and both go red. The package reports ten families, 22 behavioral controls and
all retained P1-R4 controls passing. Verification Actions run
[34796561532](https://github.com/mmsanders/digital-tape-verification/actions/runs/34796561532)
also passed.

This cures `P1-R12-V01` for verifier-package correctness only. It does not revive or
accept the old product observations, product adapter/probe, implementation, complete
WP-08, PCM, WP-11 golden, listening result or merge.

## Exact import and fresh trace are next

Software issue [#83](https://github.com/mmsanders/Digital-Tape/issues/83) owns the
only new lead task. Structural Rule 1 is explicit:

- Phase A mechanically imports only exact package tree `467a34bb...` and may merge
  that test/evidence-only PR after all ten required checks pass; then
- Phase B preserves draft PR #77 history, brings the post-import main into it without
  rewriting history, changes only the Software-owned playback probe cadence, and
  produces a fresh hash-bound product trace from a recorded pre-run commit.

The fresh trace must show 698/698 completed per-render service sequences in both
directions, replay under the unmodified imported package, retain PCM as unlistened
candidate bytes, and record the 289-case mount regression. Software must not change
engine/header/harness blobs or import allocator work, and must stop before merging
PR #77. A later independent Verification issue will disposition the new raw product
evidence.

No Verification, Hardware, Surge or Michael issue is opened now. Michael #49 is
unchanged and non-blocking, so it receives no routine comment. PR #20, #64 and #77,
playback observation acceptance, the narrow mount-observation boundary, frozen hashes,
WP-11 red/listening, uncovered allocator/recording/crash/warm/state/operation/
performance behavior, purchases, card qualification, fabrication, charging, safety
and Michael-reserved approvals remain held.
