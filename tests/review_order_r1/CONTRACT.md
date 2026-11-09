# ADR206 review-regression ordering fixture contract r1

No gate implementation has been inspected or edited for this new behavior.
This package supplies real Git histories, protected final manifest metadata,
independent publication/attestation fixtures and expected outcomes.

Software658 shall expose a bounded gate entry point (standalone or wrapper):

```
python GATE --repo PRODUCT --base SHA --head SHA --verification-repo VERIFIER --verification-main SHA --manifest tests/IMPORTS.json
```

It returns0 only for compliant lineage/identities; any refusal is nonzero.
Fixture repos are local, offline and exclusively task-owned. Production must obtain
VERIFIER/main from the authenticated independent repository, never a Product-chosen
branch or a claimed JSON boolean. Existing source/main, byte-identity, selftest,
CODEOWNERS/protection and ordinary ordering checks remain mandatory integrations.
This entry point proves the ordering/provenance slice only, never all integrity.

New optional fields on a NEW review-regression package in final protected IMPORTS:
`review_of` (full40-hex reviewed Product implementation SHA), `review_fix` (full40-hex
corrective implementation SHA), and `review_attestation` with full immutable
`source_commit`, `path`, and `entry` in the independent repository. Final metadata
may be added in a metadata-only commit after the fix: a future fix SHA cannot be
embedded in its ancestor import without a content-addressing cycle. Do not rewrite
the old import or reviewed history to manufacture that cycle. At first import,
the ordinary source_commit/tree identity must already match the final entry.

The independent attestation entry binds source repository/commit/path/tree,
review_of, exact first import_commit, corresponding fix_commit, and the cleared
corrective reviewed_head, covered_paths and publication_before_import_and_fix:true. It attests that the cited regression publication was
published before the import/correction; the gate authenticates the statement from
VERIFIER/main and proves the corresponding Product ancestry/tree identities.
It is issued as part of the independent corrected-head review, not authored by
Software or trusted from Product metadata. The original independent TEST PACKAGE
is still published before implementation; a later corrected-head attestation
adds machine-readable lineage without changing that package or claiming it was
tests-first for the held original. This closes the cross-repository provenance
boundary by independent attestation, not by comparing user-set Git timestamps.

Gate conditions: reviewed SHA is on the held branch before the new path's first
import; all earlier implementation commits in that lineage are ancestors of the
reviewed candidate (a stale reviewed SHA cannot excuse newer unreviewed code);
the correction changes an attested covered path; import is strictly before the attested corresponding correction on the same
lineage; no commit combines package changes and implementation; no preexisting
import tree edits; first-import and final package tree equal the immutable source;
source and attestation both reachable from authenticated verifier/main; registry
and protected fields agree exactly. Ordinary imports, unrelated late imports and
unrelated new behavior retain the original rule. The attestation is not an
exemption for every future import or engine change.

A gate can prove declared lineage/tree identities, not the semantic claim that a
code delta fixes a behavioral defect, nor historic main reachability from current
Git objects alone. Independent corrected-head disposition and the independently
published publication-before-correction attestation supply those facts. If PM does
not accept this explicit trust boundary, the precise missing input is an approved
authenticated publication-event receipt contract; do not replace it with timestamps
or a branch-provided boolean. Return that contract gap before implementation.

Run `generate.py --out NEW_DIRECTORY` to create cases; `run.py --gate GATE --out
NEW_DIRECTORY` generates and drives the actual future gate. Generation/selftest
executes no Product gate. All commits intentionally have identical timestamps;
lineage and trusted published identities, not clock ordering, decide results.
