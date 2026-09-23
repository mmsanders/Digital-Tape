# WP-06h not-mounted product binding

Software-owned mechanical binding for the independently published
`tests/notmounted_draft8/` package.

The verifier tree is fixed at
`f5ea4a64044cb5741565a36249f15756b2524015`, published by
Digital-Tape-Verification commit
`2f0fe952244bf40b4658f6a94904470349871c17`.

This adapter does **not** copy or modify verifier-owned source. The Makefile compiles
the exact `tests/notmounted_draft8/wp06h_probe.c` against the product public
`tape.h` and links it to the real `libtape.a`. The product wrapper then invokes
the unchanged verifier `runner.py`, retains its complete JSONL observation stream,
and records immutable product/verifier provenance.

Issue #159 covers only the post-integration Engine API §10 not-mounted sweep:

- 17 ordinary APIs before mount;
- the same 17 APIs after a successful mount → unmount;
- `tape_tell`'s caller sentinel must remain untouched on refusal;
- `tape_dup` is exercised only as an unmounted source.

Explicitly excluded: `tape_init`, `tape_mount`, `tape_format`,
destination-side `tape_dup`, crash/continuation behavior, and broader source/package
acceptance.

Run:

```sh
make -C engine all
make -C tests/notmounted_adapter all
PRODUCT_COMMIT="$(git rev-parse HEAD)" \
  python3 tests/notmounted_adapter/run_product.py \
  --evidence tests/notmounted_adapter/evidence/p1-r25-product
```
