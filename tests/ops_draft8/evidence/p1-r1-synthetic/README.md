# P1-R1 synthetic verifier evidence

This bundle is **verifier-package evidence only**. It contains no product-engine execution and makes no product acceptance claim.

Source verifier commit: `dcc4d7cdb357cf0b082071390c762c25b650f617`.
Source `tests/ops_draft8/` tree: `4a862fa69ccb2fc4c9afe59c9c9161c3470f9263`.

The two synthetic cases pass the hardened oracle. Input and output VO08 media are persisted as deterministic gzip archives with both archive SHA-256 and decompressed raw-media SHA-256 in `manifest.json`. Exact authenticated DRAFT-8 spec bytes are included under `spec/` using the same Git blobs already authenticated by the mount tranche.

Offline replay is `python3 tests/ops_draft8/replay.py tests/ops_draft8/evidence/p1-r1-synthetic` from a checkout containing this bundle. Missing or tampered evidence is a failing condition.
