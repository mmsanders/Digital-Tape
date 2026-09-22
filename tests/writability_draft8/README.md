# WP-06a — v1.1 effective writability

Independent deterministic package for the WP-06a effective-writability barrier. A **writable device** (real non-NULL `dev.write`) carrying v1.1 media must mount successfully but become effectively read-only.

Canonical DRAFT-8 SHA-256 inputs:

- `tapefs-v1.md`: `3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb`
- `engine-api.md`: `537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1`
- `acceptance.md`: `7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7`

Coverage deliberately separates two questions:

1. **Version barrier on healthy media:** arm/reset_b/promote/respool are READ_ONLY; feed/commit remain BUSY because arm never succeeds.
2. **Mount-time repair barrier:** both an invalid partner and a valid stale partner leave `needs_repair=true` and produce zero write callbacks.

Run verifier mechanics:

```sh
python3 tests/writability_draft8/selftest.py
```

Run product evidence after mechanically compiling `wp06a_probe.c` against the real public API:

```sh
python3 tests/writability_draft8/runner.py --adapter ./wp06a_probe --log wp06a.jsonl
```

A green synthetic self-test is not product evidence or package acceptance. Product observations, exact-import authentication, independent disposition, and PM disposition remain separate.
