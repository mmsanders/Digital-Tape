# Independent WP-13 embedded-readiness verifier — DRAFT-9

This package implements the complete frozen WP-13 embedded-readiness acceptance
surface as six independent machine-readable gates.

Authorship boundary: the package was defined from the authenticated DRAFT-9 candidate
specifications in Product PR #247 without inspecting Product PR #241 or the current
product engine implementation.

## Frozen inputs

Authoring source: Digital-Tape PR #247 exact head
`ae96779a8a90f20ba6b497d7e63c93ac04cbce95`, based on
`895c99f233a90a2f2e8e78f299653c15d833da69`.

Authenticated DRAFT-9 hashes:
- `spec/tapefs-v1.md`:
  `3f08ec6d11070c1e10edcf7cacbcd93ff694257f042b71b53200e158621fa19d`
- `spec/engine-api.md`:
  `383817326705d98bda6a96480f8185e911113927d35c53c02d1458adb72baea6`
- `spec/acceptance.md`:
  `ae77d13c868fd39a882b5bd3ebf459557792432ce895bc7bf58be7fc2c33825d`

Exact copies of those files and `spec/VERSION.md` are embedded in this package.
The self-test hashes the copies, and product evidence must repeat the same bundle
revision and hash map. The accepted `embedded_readiness_draft8` package remains
untouched.

The six gates are exactly:
1. `.data + .bss + tape_instance_size() <= 200 KiB`;
2. `.rodata <= 32 KiB`;
3. no allocator symbol links;
4. maximum stack <= 8 KiB by complete call-graph analysis;
5. no indirect call outside exactly four named funnels in `engine/src/dev.h`:
   `dev_read` → `tape_dev.read`, `dev_write` → `tape_dev.write`,
   `dev_flush` → `tape_dev.flush`, and `dev_progress` → the caller-supplied
   `tape_progress_fn`;
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
python3 tests/embedded_readiness_draft9/selftest.py
```

The repository-wide verifier package workflow also executes this automatically.

A green self-test proves the verifier logic can distinguish conforming and
nonconforming synthetic evidence. It is **not product acceptance**.

## Later product binding

Software imports the immutable package byte-for-byte under Structural Rule 1, then
mechanically produces the raw and normalized evidence specified by `ADAPTER.md`.
The normalized evidence is evaluated with:

```sh
python3 tests/embedded_readiness_draft9/runner.py \
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
