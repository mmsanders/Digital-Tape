# WP-12 respool product adapter — partial #154 return

Mechanical product-side binding for the independently published
`tests/respool_draft8` package.

This branch deliberately does **not** define, emulate, or stub `tape_promote`.
Issue #155 is the authoritative Software lane for that public operation. The
verifier's `WP12-EMPTY` script calls both promote and respool to assert their
opposite empty-side behavior, so a complete eight-case product run cannot be
truthful until #155 is composed.

The current partial runner executes the other seven cases against the real
engine and applies the verifier's unchanged `check()` to their raw public-call
and block-callback observations.

Run:

    make -C engine all
    make -C tests/respool_adapter all
    python3 tests/respool_adapter/run_product_partial.py \
      --evidence tests/respool_adapter/evidence/p1-r25-partial

A green result is Software observation evidence only. It is not independent
acceptance and does not claim WP-12a continuation/state, crash closure, or audio
goldens.
