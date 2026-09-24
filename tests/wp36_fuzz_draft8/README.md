# WP-36 100,000-sequence source-slot fuzz package

Independent Verification package for the DRAFT-8 acceptance criterion:

> 100,000 random transport input sequences against a source-slot device with
> `write == NULL` must never reach `dev_write`; the debug assertion must never fire.

This package is authored **before** a product binding. It contains no product-engine
expectation derived from implementation behavior.

## Normative inputs

- `spec/engine-api.md` §3.1 effective writability / debug `dev_write` instrument.
- `spec/engine-api.md` §§5–6 and §10 transport/state semantics.
- `spec/acceptance.md` WP-36.
- The prior `tests/slot_draft8` package is a deterministic precursor only; its five
  cases are not re-accepted here.

Frozen spec SHA-256 values:

- TapeFS: `3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb`
- Engine API: `537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1`
- Acceptance: `7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7`

## Reproducibility

- RNG: `splitmix64-v1`, implemented in `generator.py` rather than delegated to
  Python's `random` module.
- Master seed: `0x5730365a5eed2026`.
- Exactly `100000` independently derived sequence seeds.
- Each sequence has 8–32 operations.
- Exact generated census: **1,997,914 transport operations**.
- Full-plan SHA-256: `6a6637336eff798e6c7824af76e3d4f227eefcd9ff35e7850a14fd14a1d22bae`.
- Any product crash/assertion retains the exact failing generated sequence as a
  compact reproducer rather than a huge raw run log.

## Transport alphabet

Each sequence starts from a fresh successful mount on Side A or B and ends with
unmount. The random input alphabet is deliberately limited to **non-media-mutating
transport/state calls** whose validity follows directly from the frozen public API:

`tape_seek`, `tape_tell`, `tape_set_rate`, `tape_render`, `tape_service`,
`tape_status`, `tape_get_info`, and `tape_set_side`.

The generator exercises stopped, forward-playing and reverse-playing states; both
mount sides; same-side and cross-side `set_side`; in-range, exact-end and beyond-end
seeks; zero, positive, negative and `INT32` extreme rates; varied render counts and
service budgets. Recording and long-operation mutators are intentionally excluded;
the deterministic `slot_draft8` precursor already covers their read-only refusal
boundary and this criterion specifically says random **transport input** sequences.

## Commands

Verifier package self-test:

```sh
python3 tests/wp36_fuzz_draft8/selftest.py
```

Later real-product binding:

```sh
python3 tests/wp36_fuzz_draft8/runner.py \
  --adapter /path/to/wp36_fuzz_product_adapter \
  --evidence /path/to/evidence
```

The production runner has no sequence-count or seed override. Acceptance is fixed at
exactly 100,000 sequences and the committed seed.

A green verifier self-test is **not** WP-36 product acceptance. Structural Rule 1
requires Software to import these exact bytes first, then bind the product separately;
Verification must independently disposition that exact real-product evidence later.
