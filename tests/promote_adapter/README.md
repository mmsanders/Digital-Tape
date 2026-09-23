# Promote DRAFT-8 product adapter

This directory is Software-owned mechanical binding for the independently
published tests/promote_draft8 package. It does not change verifier-owned
fixtures, oracle logic, expected results, counter values, or mount-side choices.

wp_promote_probe expands the verifier's VO08 metadata envelope into an
in-memory block device, supplies deterministic zero-filled chunk payloads, mounts
the real engine on the side required by ADAPTER.md, clears setup I/O from the
trace, and drives tape_promote with block_budget=64 until terminal. It then
serializes the resulting superblocks/index slots back into VO08 and emits the
complete promote callback trace.

Run:

    make -C engine all
    make -C tests/promote_adapter all
    PRODUCT_COMMIT=$(git rev-parse HEAD) \
      python3 tests/promote_adapter/run_product.py \
      --evidence tests/promote_adapter/evidence/p1-r25-product

The wrapper refuses to run unless the imported verifier tree is exactly
2b79e0b07016da3521917c5a276e36994ccccfa6, published by independent
Verification at e5e06b06f1aa0755a3b0b15133f1ce680e17f7af.

Acceptance boundary: this is raw product evidence for the 16-row
classification/uninterrupted-FRESH tranche. RESUME/crash closure, copied-audio
golden/listening identity, stored-position integration, broad continuation
identity/re-entry, and progress-callback semantics are not claimed here.
