# Transport product adapter

Mechanical product-side binding for the independently published
tests/transport_draft8 package.

The adapter drives only public tape.h calls and records public results plus
block-device callback observations. It does not inspect engine internals and
does not reproduce or modify verifier assertions.

Run:

    make -C engine all
    make -C tests/transport_adapter all
    python3 tests/transport_adapter/run_product.py \
      --evidence tests/transport_adapter/evidence/p1-r25-product

The runner constructs the exact verifier-owned VO08 fixture for each of the 16
published cases, executes the real engine, and applies the unchanged imported
oracle. A green run is product observation evidence for blind Verification
disposition, not Software acceptance and not a listened/golden claim.

Deliberate exclusions are those of the verifier package: warm-buffer sample
identity/listening, broader playback/rate goldens, crash injection, and
long-operation continuation/state behavior.
