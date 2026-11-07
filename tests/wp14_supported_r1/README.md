# ADR206 supported-platform companion oracle r1

NEW immutable import path: tests/wp14_supported_r1. Depends on the unchanged
sibling tests/wp14_r1; never replaces or edits that three-platform tree.
Authoritative input: Verification394 / PM661 / ADR206 at d72ca088; Software658
comment6640086870 adopted without another declaration round. No new adapter or
CI implementation was inspected to author these expectations.

`qualification_supported.audit_platforms(images,natives,head,platforms=None)`
applies the original per-platform audit body unchanged to the selected set.
The default remains linux,macos,windows. Explicit selections must be sorted,
unique subsets of those names including linux AND windows. Invalid selection
raises ValueError; Software's declared CLI must map it to usage64. Both document
maps must exactly equal the selected set. Return keeps original completeness
fields and accepted:false, adding platforms and deferred. Adapter adds ignored.
The selftest proves AST identity of the original per-platform loop and detects
statement removal. This is code preservation evidence, not a substitute native
Product run or an assertion that synthetic data passed a complete native audit.

`retained.audit_retained(natives,captures,platforms,resolver=None)` is the companion
saved-byte expectation oracle. It authenticates named artifact roots, every
capture_artifacts entry, large-artifacts index and indexed bytes, snapshot
metadata/blocks/logical bytes, and round-trip dump bytes; it returns relocation
proof without changing original request/response strings. All named results must
be nonempty; path escapes, absent bytes, ambiguous paths and mismatches fail.
Optional resolver restores a missing logical file at the already-bounded path
from the retained compressed/sparse representation. Restoration is mechanical;
the oracle always hashes the resulting logical bytes. Existing Software
restoration/IO bindings may remain mechanical; Software must not reimplement or
relax completeness. Keep the original three-platform default path unchanged.
`ignored_inputs` lists present unnamed image/native documents/artifact roots.

Adapter contract already adopted:

```
python tests/wp14_adapter/census.py --head SHA --platforms linux,windows --captures DIR --relocations OUT.json BUNDLE
```

Missing flag means the original three-platform default. Invalid/duplicate/missing
platform selections exit64. Missing named documents/artifacts, mutated bytes,
removed cases, malformed/empty results fail nonzero. Output is the original
completeness JSON plus platforms/deferred/ignored; accepted stays false.
Required wp14-package-census restores downloaded Windows/Linux completeness and
retained-byte audit plus Git identity, depends on the Linux/Windows package legs
and belongs to fail-closed qualification. Original manual workflow remains
byte-identical (MANUAL-SHA256) and dispatch-only; no fake macOS result.

```
python -B tests/wp14_supported_r1/selftest.py
python -B tests/wp14_supported_r1/dag.py --selftest
python -B tests/wp14_supported_r1/dag.py --product PRODUCT
python -B tests/wp14_supported_r1/run_adapter.py --adapter PRODUCT/tests/wp14_adapter/census.py --bundle COMPLETE_TWO_PLATFORM_BUNDLE --captures DOWNLOADED_CAPTURES --head SHA --out NEW_OUTPUT
```

DAG checks need PyYAML6.0.3. Candidate replay requires actual complete named
artifacts, tests positive completeness and ignored unnamed evidence, then usage,
missing files/artifacts, retained mismatch, case deletion and malformed/empty
results. It preserves source data with task-owned hard-link clones; mutations
replace clone entries, never write through a link. Source and output must support
hard links on the same filesystem. No recursive deletion/cleanup or physical IO.
The complete replay is NOT claimed executed before a corrected adapter exists.

Synthetic selftests separately prove platform validation, unchanged per-platform
assertions, actual saved-byte positives and detecting hash/path/missing/index/
snapshot/dump/empty-result controls. DAG fixtures catch required-census removal,
Git-identity-only substitution, dependency/selection/aggregate weakening and
required macOS. Candidate DAG replay also drives the actual lane-verdict CLI.
Neither fixture selftests nor a green CI gate accepts a target/session or platform.
No raw campaigns or goldens are regenerated/committed.
