# WP-06a writability product binding

Software-owned mechanical binding for the independently published
`tests/writability_draft8/` package.

The verifier tree is fixed at
`786221daaf80d15406d9cccf19691c2337ff5908`, published by
Digital-Tape-Verification commit
`d875730ee5cedc6b88e40fcfe30aa4d81918f549`.

This adapter does **not** copy or modify verifier-owned source. The Makefile compiles
the exact `tests/writability_draft8/wp06a_probe.c` against the product public
`tape.h` and links it to the real `libtape.a`. The product wrapper then invokes
the unchanged verifier `runner.py`, retains its complete JSONL observation stream,
and records immutable product/verifier provenance.

Covered by issue #157 only:

- v1.1 effective-read-only reporting and mutator refusal precedence;
- mount-time invalid/stale superblock repair suppression;
- zero `dev_write` callbacks and byte-identical output media across all eight
  published WP-06a cases.

Explicitly excluded: WP-36 NULL-source behavior, raw `tape_format` /
`tape_dup` gating, crash/continuation behavior, and any broader package or source
acceptance.

Run:

```sh
make -C engine all
make -C tests/writability_adapter all
PRODUCT_COMMIT="$(git rev-parse HEAD)" \
  python3 tests/writability_adapter/run_product.py \
  --evidence tests/writability_adapter/evidence/p1-r25-product
```
