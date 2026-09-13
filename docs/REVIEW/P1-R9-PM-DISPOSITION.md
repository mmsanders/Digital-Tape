# P1-R9 PM disposition — corrected complete-playback publication

**Date:** 13 September 2026 UTC  
**PM issue:** [#69](https://github.com/mmsanders/Digital-Tape/issues/69)  
**Input product main:** `add1a255607720d71f62688ece8d9036d40fba82`  
**Input verifier main:** `62b18deb8b4fbe6e797b00d792ee9f46ac0a8059`  
**Held PR #64 head:** `bc53076448112ec3015de40e71c229e17d225c2f`

## Independent correction authenticated

Verification #8 independently re-derived and corrected the three P1-R8 findings
without inspecting product implementation, adapter source, Software's return, held
product observations or the diagnostic scratch oracle. The corrected pre-evidence
source commit/tree are `1c1489a5b1c10f2baa8425557fd7bdfde3225575` /
`43ca6f6bbc1990d5ced6de3b2ce0d04f00aa7519`. Final verifier publication is the
input verifier-main commit; the complete published subtree is
`6dbb23bb4626238b0f22427031a551d2ece454fd`, and retained P1-R8 synthetic
evidence is `d867fc68c80a2217508868c4b339d160b55ec2cc`.

PM authenticated the commit ancestry, tree identities, changed paths, file modes,
frozen inputs, generated outputs and evidence manifest. The source delta from the
prior complete publication is confined to eleven package paths: the reverse candidate,
the oracle/generator/synthetic model and their runner/replay/package/self-test identity
and explanatory files. The prior P1-R6 synthetic evidence remains exactly
`c67ea8fa128e06393839f968ae3cc949d84e5f2a`; the earlier three-family playback
tree remains `ff810814dbc8079c6903e6f85ed7ee312abd3076`.

Exactly the authorized behavior changed:

- F-1 now emits frame 1 and then frame 0 for the `INT32_MIN` case before reporting
  `at_start`;
- F-2 grid-snaps reverse scrub to `(total_frames - 1) << 32`;
- F-3 expects `TAPE_ERR_UNDERRUN = 18` in both side-switch families.

Only `candidate/scrub-reverse.pcm` changed among the six generated inputs, from
SHA-256 `faae5cf894f9a7b2d84e9f9c99a36184ddd776e3cdc6de734e935c4f35f4f5d6`
to `5f1794e8dcd7c1b3e2c390a1aef33039f5b88b20f682c56c4aa6f94051bd8fa1`.
All four fixtures and forward scrub are unchanged. The frozen TapeFS, Engine API and
acceptance hashes and WP-08 hash remain exact.

PM reproduced deterministic generation, all ten corrected families, twenty behavioral
controls including the named F-1/F-2/F-3 negatives, the retained P1-R4 suite and its
eighteen controls, saved offline replay and the full verifier suite. All pass. The
saved observation is synthetic, exits zero, binds the corrected source commit/tree
and reports byte-exact results for every PCM family. This authenticates package
readiness only; it is not product, PCM, golden, listening, WP-08 or WP-11 acceptance.

## Next dependency and holds

The corrected final publication is ready for exact mechanical import onto product
main. Software is the only ready next owner. It must replace the existing complete
subtree with the exact published tree before any further candidate work, with no
engine/firmware delta in that import. After that test-first merge, Software may merge
the new main into the existing held PR #64 branch without rewriting history and run
the unchanged candidate against the unmodified corrected package. The previous failing
bundle stays immutable; the new run must be retained separately and bound to a code
commit that exists before the run plus one consistent engine/adapter build identity.
Any genuine product mismatch stops the assignment rather than licensing test edits or
an unassigned behavior change.

Independent Verification receives no issue until a fresh product bundle exists.
Hardware and Surge have no newly unblocked bounded work. PR #20 and PR #64 remain
draft and held; no implementation merge is authorized. WP-11 stays red, and human
listening remains held until a passing authenticated product bundle is independently
dispositioned and PM separately routes candidate PCM. Frozen hashes, test strength,
card purchase/qualification, fabrication, charging, repository settings and every
other current hold remain unchanged. Michael #49 remains outside this laptop-path
dependency.
