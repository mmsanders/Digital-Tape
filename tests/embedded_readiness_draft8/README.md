# Independent WP-13 embedded-readiness verifier — DRAFT-8

This package implements the complete frozen WP-13 embedded-readiness acceptance
surface as six independent machine-readable gates.

Authorship boundary: the package was defined from the authenticated DRAFT-8 public
specifications before inspecting the current product engine implementation.

## Frozen inputs

Authoring integration point: Digital-Tape
`e4a356586fd67d118868ba457e26d2c9805e7c7a`.

Authoritative DRAFT-8 hashes:
- `spec/tapefs-v1.md`:
  `3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb`
- `spec/engine-api.md`:
  `537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1`
- `spec/acceptance.md`:
  `7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7`

The six gates are exactly:
1. `.data + .bss + tape_instance_size() <= 200 KiB`;
2. `.rodata <= 32 KiB`;
3. no allocator symbol links;
4. maximum stack <= 8 KiB by complete call-graph analysis;
5. no indirect call outside the three frozen `dev_*` callback funnels;
6. no engine-owned mutable state outside caller-owned `mem`.

## Files

- `oracle.py` — verifier-owned six-row evaluator.
- `runner.py` — consumes normalized product evidence and emits
  `WP13-EMBEDDED-RESULT-1`.
- `instance_size_probe.c` — verifier-owned public-API measurement of
  `tape_instance_size()`.
- `ADAPTER.md` — exact later Software build/evidence contract.
- `COVERAGE.md` — frozen assertion matrix and exclusions.
- `selftest.py` — synthetic green fixture plus red controls for every gate and
  fail-closed provenance/completeness boundaries.

## Self-test

Run:

```sh
python3 tests/embedded_readiness_draft8/selftest.py
```

The repository-wide verifier package workflow also executes this automatically.

A green self-test proves the verifier logic can distinguish conforming and
nonconforming synthetic evidence. It is **not product acceptance**.

## Later product binding

Software imports the immutable package byte-for-byte under Structural Rule 1, then
mechanically produces the raw and normalized evidence specified by `ADAPTER.md`.
The normalized evidence is evaluated with:

```sh
python3 tests/embedded_readiness_draft8/runner.py \
  --evidence PRODUCT-EVIDENCE.json \
  --result RESULT.json
```

The raw tool outputs, complete inventories and build logs are retained for independent
Verification audit. A Software-generated green result is never self-acceptance.

## Acceptance boundary

If an exact later product candidate passes all six rows and independent Verification
authenticates the raw evidence/binding, this package is intended to be sufficient for
complete frozen WP-13 package acceptance unless a spec-grounded missing criterion is
identified.

No claim is made here about runtime behavior, audio, crash safety, hardware, or any
other work package.
