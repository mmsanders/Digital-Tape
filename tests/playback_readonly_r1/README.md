# ADR-169/170 READ-1: complete independent authored package

Verification #146, 7 October 2026 UTC. This completes independent authored coverage,
schema, fixture backend, executable oracles and controls. It is **not Product acceptance**.
Once merged with green publication CI, its immutable source/tree goes directly to
Software #409 for import then scoped implementation/binding.

Read [ADR-170 preflight](PREFLIGHT-ADR170.md), [coverage](COVERAGE.md),
[observation schema](OBSERVATION.md) and [adapter contract](ADAPTER.md).
Historical PREFLIGHT.md preserves #151's partial checkpoint; PM resolved P2READ-001
with fixed mapping/seek/episode/idle bounds before this executable authorship.
No Product source, private tests or Software design note was inspected.
No Product run or acceptance is claimed. Existing WP14 evidence is preserved.

Latest authority is `authority/ADR170-PLAYBACK-PERFORMANCE-ADDENDUM.md`, source
`26d3cb320ac6ce76dd2e26e22e1af4d4e7c0adbf`, Product #410 merge
`5e6d5fd6cfce64031ba12b37fc367145b5fe18dd`. Historical #408 copies remain authenticated
in INPUTS.json, alongside byte-exact standalone DRAFT-10 API/TAPEFS/VERSION copies.
This subtree has no dependency on WP14's held implementation branch or private code.

## Publication checks

```sh
python3 -B tests/playback_readonly_r1/check_pins.py
python3 -B tests/playback_readonly_r1/selftest.py
python3 -B tests/playback_readonly_r1/cases.py
```

Selftests include actual C99 callback-backend execution, but ZERO Product execution.
The machine census is 59 cases / 3 meaningful rows / 12 required actual Product
controls plus seam nonzero/zero controls and shipping absence/equivalence audits.

## Actual candidate execution and replay

```sh
python3 tests/playback_readonly_r1/runner.py --adapter /abs/read1-adapter \
  --shipping-adapter /abs/read1-shipping-adapter --out /abs/read1-run \
  --baseline-adapter /abs/prechange-adapter \
  --baseline-product-commit 9e902cf04b6d0c02363870fb9bc201e40239b509 \
  --product-commit PRODUCT_SHA --engine-tree ENGINE_TREE --adapter-sha256 BINARY_SHA256
python3 tests/playback_readonly_r1/controls.py --adapter /abs/read1-adapter \
  --out /abs/read1-controls --product-commit PRODUCT_SHA --engine-tree ENGINE_TREE
python3 tests/playback_readonly_r1/qualification.py --run /abs/read1-run \
  --controls /abs/read1-controls --product-commit PRODUCT_SHA --engine-tree ENGINE_TREE
python3 tests/playback_readonly_r1/absence.py --shipping /abs/absence/manifest.json \
  --leak-control /abs/leak/manifest.json --product-commit PRODUCT_SHA --engine-tree ENGINE_TREE
python3 tests/playback_readonly_r1/runner.py --replay /abs/read1-run/observations.jsonl.gz \
  --out /abs/read1-replay
```

No `--case` selection can qualify as a complete campaign. Offline replay checks
facts/schedule but cannot create actual Product evidence. Large raw evidence goes
to hashed release assets. The counting device itself has no consumer cache; host
time is diagnostic. [READ2.md](READ2.md) defines exact import/provenance, causal-site,
shipping absence, golden/Phase1 and resource checks beyond the manifest gate.

Next owner after immutable publication: Software #409. Verification #146 retains
READ-2 and WP14 final disposition; A8 stays PENDING and all existing holds survive.
