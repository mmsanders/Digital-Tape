# WP-36 100,000-sequence product binding

Software-owned mechanical adapter for the independently published
`tests/wp36_fuzz_draft8/` package.

Structural Rule 1 is preserved on this branch:

1. verifier-only import commit `c9c8a107a365ffefe5be2d87fad292b09a879723`;
2. this product-binding commit.

The adapter is persistent because the verifier streams all 100,000 generated
sequences through one process. Every sequence nevertheless gets a freshly zeroed
engine instance and freshly zeroed caller-owned playback/recording rings, mounted
against the original verifier fixture.

The source device uses a literal `tape_dev.write = NULL`; no counting, swallowing,
or rejecting write wrapper exists. Engine and adapter are built after a clean with
`-UNDEBUG`, and adapter compilation fails if `NDEBUG` is defined. Reaching the
engine's frozen NULL-write assertion therefore kills the process and is observed by
the unchanged verifier runner as a failure with a compact exact reproducer.

Run the exact production evidence path:

    python3 tests/wp36_fuzz_draft8/selftest.py
    make -C engine clean
    make -C engine all CFLAGS=-UNDEBUG
    make -C tests/wp36_fuzz_adapter all
    PRODUCT_COMMIT="$(git rev-parse HEAD)" \
      python3 tests/wp36_fuzz_adapter/run_product.py \
      --evidence tests/wp36_fuzz_adapter/evidence/p1-r26-product

The verifier owns the generator, fixed sequence count, seed, operation order,
expectations, runner and failure reproducer. Software owns only public-API plumbing and
provenance retention.

A green run is authenticated Software product evidence only. Independent Verification
must disposition the exact candidate before merge/acceptance.
