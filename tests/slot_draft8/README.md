# WP-36 — independent DRAFT-8 source-slot tranche

This package is the deterministic public-API precursor to acceptance WP-36. A source-slot device has a **literal `dev.write == NULL`**. Effective writability must be false; playback remains usable; mounted W-gated operations must refuse before any internal `dev_write` attempt; mount-time superblock repair must be skipped.

Canonical DRAFT-8 SHA-256 inputs:

- `tapefs-v1.md`: `3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb`
- `engine-api.md`: `537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1`
- `acceptance.md`: `7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7`

| ID | Script |
|---|---|
| `WP36-SRC-A` | mount A; `writable=false`; seek/rate/service/render succeed; no write attempt |
| `WP36-SRC-B` | same on B |
| `WP36-SRC-MUTATORS-B` | arm/reset_b/promote/respool → `READ_ONLY`; refused arm leaves feed/commit → `BUSY` |
| `WP36-SRC-MUTATORS-A` | repeat W-gated reset_b/promote/respool from A, proving writability is mount-wide rather than a side proxy |
| `WP36-SRC-REPAIR-A` | one invalid superblock partner; mount succeeds, `needs_repair=true`, no repair write/flush |

Run verifier mechanics:

```sh
python3 tests/slot_draft8/selftest.py
```

Run product evidence:

```sh
python3 tests/slot_draft8/runner.py --adapter ./wp36_slot_probe --log wp36-slot.jsonl
```

The product adapter must use a real NULL write callback and a debug engine build. If product code reaches the frozen §3.1 `dev_write` assertion, the adapter process fails and the verifier runner marks the case failed. Thus the property is observable even though no NULL write callback exists to log the attempted write.

Scope language is intentionally narrow. After a refused arm, `tape_feed` and `tape_commit` are `TAPE_ERR_BUSY`, not `READ_ONLY`, because the instance never entered the armed row. `tape_format` and destination `tape_dup` are raw-device operations outside the mounted effective-writability predicate.

Not covered: the required 100,000 random transport sequences, v1.1 WP-06a, raw format/dup gating, or product-source acceptance. A green deterministic product run is a prerequisite, **not WP-36 acceptance**.
