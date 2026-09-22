# WP-06h — not-mounted contract

Independent deterministic package for Engine API §10's **Not mounted** row and acceptance WP-06h / V5-009.

Canonical DRAFT-8 SHA-256 inputs:

- `tapefs-v1.md`: `3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb`
- `engine-api.md`: `537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1`
- `acceptance.md`: `7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7`

The suite creates **34 isolated cases**: 17 ordinary API calls × {before mount, after unmount}. Each case runs in a fresh adapter process. This prevents an earlier defective call from contaminating the state used to judge a later one.

Every target call must return `TAPE_ERR_NOT_MOUNTED`. The two `tape_tell` cases additionally require the caller's sentinel out-value to remain untouched.

Run verifier mechanics:

```sh
python3 tests/notmounted_draft8/selftest.py
```

Run product evidence after mechanically compiling `wp06h_probe.c` against the real public API:

```sh
python3 tests/notmounted_draft8/runner.py --adapter ./wp06h_probe --log wp06h.jsonl
```

A green synthetic self-test is not product evidence or package acceptance.
