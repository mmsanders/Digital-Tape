# P1-R7 PM disposition — complete playback tranche and held product evidence

**Date:** 13 September 2026 UTC  
**PM issue:** [#65](https://github.com/mmsanders/Digital-Tape/issues/65)  
**Input product main:** `4517db7efba0d1a0933fc0dda1a607c5441197b7`  
**Input verifier main:** `121f5f7ab03c9ce08c38329e518c49a1ca9b65a5`

## Software return

Software #63 completed Phase A by merging PR #60 as the exact test/adaptor-only
commit `4517db7efba0d1a0933fc0dda1a607c5441197b7`. The product playback subtree is
`ff810814dbc8079c6903e6f85ed7ee312abd3076`, identical to the authenticated
verifier publication. Phase A has no engine or firmware delta and grants no package,
product, PCM or golden acceptance.

Phase B produced held draft [PR #64](https://github.com/mmsanders/Digital-Tape/pull/64)
at `3dc5abb85e5b30200cf1553b9a06a83bc83c6d36`. PM did not inspect or review its
implementation or Software-owned scaffolding. Its retained three-family product
evidence tree is `c1f173224ef5a312db438bd796e0090c4f329b5c`; offline replay passes,
and a fresh PM reproduction using the existing public adapter at the actual PR head
again produced three byte-exact family results. These are product observations, not
independent acceptance.

The return is not ready to route for independent candidate disposition. Both the
versioned return and packet name `c108356c640e971967fb3a00d87e3f6003a129db` as
the candidate head, but that commit is the merge of held #20 with test-only main and
precedes the implementation commit. The actual PR head is `3dc5abb...`. The packet
also names `libtape.a` SHA-256 `41eb993f...`, while the evidence manifest names
`fdacb6d2...`; the manifest does not identify an exact implementation commit. PM's
reproduction cannot repair the provenance of the already committed run. Preserve the
bundle unchanged as superseded history and produce a new exact binding.

## Independent Verification return

Verification #7 independently authored the complete boundary, scrub and side-switch
sibling without inspecting any product implementation, adapter, PR or product run.
Publication is `121f5f7ab03c9ce08c38329e518c49a1ca9b65a5`; source commit/tree are
`54789cc6e6bbfd942857374e2e0b3305d05d2f2c` /
`5527547b72b3e5c6d6fb91d41f3aa3bfa86fab7d`. The complete published subtree,
including retained synthetic evidence, is `863b3a49c421bda1bebcf1a9760149bec7051048`;
the saved evidence tree is `c67ea8fa128e06393839f968ae3cc949d84e5f2a`.

PM reproduced deterministic fixture/candidate generation, ten families, sixteen new
named behavioral mutations, the retained three-family/eighteen-control P1-R4 suite,
saved-evidence replay and `make -C tests check`. All pass. The package authenticates
the frozen hashes and PM-issued WP-08 input. It is ready for exact mechanical import;
its PCM is verifier-generated, synthetic, unlistened and unaccepted.

## Dependency order and holds

Software is the only ready next owner. It must first import the complete published
verifier subtree exactly onto main. Only after that test-first merge may it add the
minimum independently covered status/side-switch behavior to the held candidate and
produce a fresh complete product bundle. Code must be committed before the evidence
run so the manifest can name the exact code commit; source, archive and adapter build
identities must be singular and consistent. The existing evidence remains immutable.

Independent Verification receives no issue until the corrected complete product
bundle exists. Hardware and Surge have no useful bounded work this round. Michael
#49 remains open but does not block the laptop path; its branch-retention list must
include every open PR head at deletion time.

PR #20 and PR #64 remain draft and held. No implementation merge, header-only update,
test weakening, synthetic relabel, PCM/golden/listening acceptance, card purchase or
qualification, fabrication, cell charging, repository-setting change or frozen-spec
edit is authorized. Issue closure remains a stop marker, not acceptance.
