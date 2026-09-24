# WP-07 allocator/COW product binding

Software-owned mechanical binding for the independently published
\`tests/allocator_cow_draft8/\` package.

Structural Rule 1 is preserved on this tranche:

1. verifier-only import commit \`7ac78154a4024288ef34c21b8fd0d5c95b3bace2\`;
2. the following product-binding commit.

The verifier invokes \`adapter.py\` as the persistent JSON-line protocol endpoint.
The Python shim does not decide allocator/index correctness. It authenticates the two
verifier fixture files, forwards each verifier-owned plan exactly to the compiled C
worker, adds only raw timing-environment fields to reset-stress output, and relays the
worker's observation.

\`wp07_product_worker.c\` links only against the public product API. Each random
sequence is a fresh worker process that reloads the exact fuzz fixture, which gives the
required fresh media and fresh engine instance. It records every \`dev_write(lba,count)\`
callback before any range/error handling, emits raw B0/B1 header/entry bytes, executes
the public API calls, and never emits decoded ownership/free-next/live-index verdicts.

The reset call is surrounded by a hard one-second process watchdog and is measured with
\`CLOCK_MONOTONIC\`. A watchdog firing kills the worker and therefore fails the
verifier session closed.

A green Software run is product evidence only. PR integration remains held for
independent Verification disposition.
