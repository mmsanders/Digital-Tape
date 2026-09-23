# WP-36 deterministic source-slot product binding

Software-owned mechanical binding for the independently published
tests/slot_draft8 package.

The source device passed to the real engine has a literal write == NULL.
There is no write wrapper that counts or swallows writes. The flush callback remains
present because tape_init requires it and because an improper repair flush is an
observable verifier failure.

The adapter exercises only the five deterministic public-API scripts published by
Verification:

- playback from Side A;
- playback from Side B;
- mounted mutator refusals from Side B;
- the same effective-writability refusals from Side A;
- read-only superblock-repair suppression.

Debug assertions are part of the evidence boundary. The engine is rebuilt with
-UNDEBUG; the adapter also compiles with -UNDEBUG and refuses compilation if
NDEBUG is defined. Thus an erroneous internal dev_write on the NULL-write source
slot terminates the product adapter and the unchanged verifier runner marks the
case failed.

Run:

    python3 tests/slot_draft8/selftest.py
    make -C engine clean
    make -C engine all CFLAGS=-UNDEBUG
    make -C tests/slot_adapter all
    PRODUCT_COMMIT="$(git rev-parse HEAD)" \
      python3 tests/slot_adapter/run_product.py \
      --evidence tests/slot_adapter/evidence/p1-r25-product

This is deterministic precursor evidence only. It is not the required WP-36
100,000-sequence acceptance run and is not complete WP-36/source/golden acceptance.
