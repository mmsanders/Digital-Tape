# WP-12 respool product adapter — #179 composition return

Mechanical product-side binding for the independently published
`tests/respool_draft8` package.

The composition base is the exact authoritative promote candidate from PR #178,
`edf6447c832ff6599b51f60d2a009268b587f3b0`. The respool engine implementation
is mechanically carried from PR #176. The adapter now executes all eight
published cases in verifier order; `WP12-EMPTY` calls the real
`tape_promote` first and then `tape_respool`, exactly as the independent
adapter contract requires.

Run:

    make -C engine all
    make -C tests/respool_adapter all
    python3 tests/respool_adapter/run_product.py \
      --evidence tests/respool_adapter/evidence/p1-r25-product

The runner applies the unchanged verifier-owned `fixture_contract_errors()` and
`check()` functions to raw public-call and block-callback observations.

A green result is Software observation evidence for blind Verification
disposition only. It is not acceptance and does not claim WP-12a
continuation/BUSY/re-entry/argument-stability/FAULTED behavior, WP-10 crash
closure, or bit-exact/listened audio goldens.
