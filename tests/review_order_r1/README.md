# V394 narrow review-regression policy fixtures r1

Read [CONTRACT](CONTRACT.md) before implementing a gate. This is a new package;
no existing gate delta was inspected to author it. Ordinary tests-first ordering,
byte identity, publication-main and ownership protections remain in force.

25 real-Git cases:3 allowed histories and22 refusals. Includes ordinary order,
review/import/correction lineage and final metadata without history rewrite;
missing/short/forged/nonancestor/stale review_of; preexisting and previous tree
edits; no later correction, correction before import, simultaneous import/fix;
unreachable publication/attestation, missing/forged attestation, changed imported
bytes, unattested chronology, unrelated correction and unrelated earlier/later
late imports. All timestamps are identical. Generated repos are fsck-checked.

```
python -B tests/review_order_r1/run.py --selftest --out NEW_OUTPUT
python -B tests/review_order_r1/run.py --gate FUTURE_GATE.py --out NEW_OUTPUT
```

Selftest generates fixtures and proves always-green/always-red harness controls
are caught. It executes NO Product gate and supplies no gate implementation or
acceptance model. Actual replay drives the declared future gate over the real
histories. Required gate candidate is not yet returned.

REVIEW-ATTESTATIONS.json independently binds the actual held d62e0de0, unchanged
7927f905/a2540d46 publication, importceb36177, correction0b450903 and reviewed
0db6ce5c lineage; ready laneA disposition is published at80d93c50. This new ledger
adds machine-readable provenance without changing old package bytes. Software
must cite this ledger's eventual merged source SHA/path/entry under protected
review_attestation metadata, plus full review_of and review_fix in final IMPORTS.
The ledger attests publication before import/fix; Git lineage and source/main
identity still must be verified. A Product-owned boolean is never sufficient.
Semantic correction and historic publication facts come from independent review;
Git timestamps alone cannot prove them. The exact trust boundary is explicit in
CONTRACT.md; if rejected by PM, return the needed authenticated receipt contract
rather than shipping a weaker gate.

No Product/engine/firmware implementation, history rewrite, target/physical or
merge waiver is included. Raw generated .git histories are local/CI artifacts;
only generators, expectations and small summaries are committed.
