# P1-R5 PM disposition — corrected playback evidence and unblocked laptop work

**Date:** 12 September 2026 UTC  
**Owner:** PM under [#58](https://github.com/mmsanders/Digital-Tape/issues/58)  
**Product input:** `b7f92dbb5ef4e59d9dd4ae268937ebbac31225ca`  
**Verifier input/publication:** `7a22cbb4447c40c51b7c8b2282a685ed30a46ba6`

## Corrected playback-package disposition

Verification #5 corrected the first DRAFT-8 playback package without changing its
fixture, candidate PCM, authenticated spec copies, three playback families or
documented exclusions. The corrected source commit is
`d565403907ecea331a5dcf63efbd1c08d8bd732e`; its pre-evidence
`tests/playback_draft8/` tree is
`aaa6dde86c9a0bdffa2b375361049ac670e26467`. The complete published subtree,
including retained P1-R4 synthetic evidence, is
`ff810814dbc8079c6903e6f85ed7ee312abd3076`.

PM reproduced deterministic fixture/candidate-PCM generation, the playback
self-test, the full verifier `make -C tests check` suite, and offline replay of the
saved P1-R4 evidence. Replay reported all three families PASS. The self-test caught
manifest-only synthetic-to-product relabeling, adapter-ID mismatch, missing source
or build provenance, missing/nonzero exit, timeout, missing/tampered evidence and
verifier-source drift. Its nonempty-destination control retained the existing
sentinel bytes. The saved manifest SHA-256 is
`b915e44b65e293fe9765b3437b2491ee297136cf6561e2010cc50c3d048d61ed`.

The correction is ready for exact mechanical import. That disposition authenticates
the verifier package and evidence controls only. The saved run is explicitly
synthetic; no product engine ran, no human listened, and no PCM, WP-08, WP-11 or
engine behavior is accepted.

## Dependency decision

Michael #49 is not on the critical path to the next laptop-software work. Software
can import the corrected package, add mechanical product-adapter plumbing and retain
an exact link/run diagnostic without implementing uncovered operations. Independent
Verification can author the next playback boundary/ramp/side-switch tranche from
the frozen specification in parallel.

Michael's print result and card purchase/readback remain necessary for the physical
hardware/media path, but not for this laptop tranche. Human listening is deliberately
not requested until an exact package import and product-generated PCM evidence exist.
Branch protection and cleanup remain important process/risk work but do not prevent
the bounded technical tasks. Michael may therefore defer his issue without stopping
Phase 1 laptop development.

## Issued work and holds

- [Software #59](https://github.com/mmsanders/Digital-Tape/issues/59) owns exact
  import, product-adapter plumbing and a no-stub diagnostic/split return.
- [Verification #6](https://github.com/mmsanders/digital-tape-verification/issues/6)
  owns independent zero/one/extreme-rate, ramp and side-switch coverage.
- Hardware and Surge have no useful bounded task and receive no issue.
- Michael #49 remains the single physical/purchase/settings/cleanup item; no new
  Michael issue was created.

Draft PR #20 remains held. No implementation merge, public-header-only upgrade,
test weakening, fixture/golden rewrite, synthetic relabel, listening acceptance,
card qualification, purchase, timing qualification, fabrication, charging or
frozen-spec change is authorized. Issue closure remains evidence that a lead stopped,
not correctness or acceptance.
