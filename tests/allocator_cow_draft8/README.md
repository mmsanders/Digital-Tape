# Independent WP-07 allocator / copy-on-write verifier — DRAFT-8

This package publishes the remaining frozen WP-07 acceptance surface independently of
the product implementation.

Authorship boundary: expectations were derived from authenticated DRAFT-8 public
specifications before inspecting the current product engine implementation.

## Frozen inputs

Authoring integration point:
`e4a356586fd67d118868ba457e26d2c9805e7c7a`.

DRAFT-8 hashes:
- `spec/tapefs-v1.md`:
  `3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb`
- `spec/engine-api.md`:
  `537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1`
- `spec/acceptance.md`:
  `7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7`

## Package contents

- `generator.py` — fixed SplitMix64-v1 10,000-sequence edit generator.
- `fixture.py` — compact verifier-owned COW and maximum-entry reset fixtures.
- `oracle.py` — independent raw-index, write-destination, free-next and timing oracle.
- `runner.py` — fail-closed streaming product runner with compact evidence retention.
- `synthetic_adapter.py` — verifier plumbing stand-in used only by self-tests.
- `selftest.py` — deterministic plan check plus positive/negative controls.
- `ADAPTER.md` — exact later Software binding protocol.
- `COVERAGE.md` — assertion matrix, fixed census and exclusions.

## Fixed campaign

Production is not configurable:

- RNG: `splitmix64-v1`
- master seed: `573037a110c02026`
- sequences: **10,000**
- total random actions: **65,026**
- edits: **59,423**
- resets: **5,603**
- canonical plan SHA-256:
  `dd2a25b5d45ee5fe343cf48d2168ffa275bbb5adb6f3cd398559ae56529da9cd`

The random alphabet covers overwrite, overdub, splice, reset, start/mid/end and
chunk-boundary edit points, multiple positive feed sizes, and service budgets from 1
through 1024 blocks.

## What the verifier observes

The later Software adapter returns raw device-level facts, not verdicts:

- every `dev_write(lba,count)` callback in scope;
- exact B0/B1 index header + entry-array bytes before/after actions;
- actual public API results;
- actual accepted frame counts;
- actual resolved seek values;
- monotonic reset timing and environment.

Verification independently:
- maps writes to chunk ids;
- distinguishes writes/allocations from mere index references;
- validates index CRC and §5.2 rules;
- enforces physical-frame interval disjointness;
- selects the live B slot;
- derives invariant-12 `free_next`;
- behaviorally probes the first allocation after every remount.

No private product allocator variable is trusted.

## Reference vs ownership

The fixture deliberately contains legal Side-B references below `a_high_water`,
including two entries sharing chunk 0 but occupying adjacent, non-overlapping physical
frames. This state must pass.

A chunk write/allocation below the same floor must fail. That distinction is a core
purpose of this package.

## Reset timing

A separate verifier fixture puts the maximum 4,096 entries in Side A as disjoint
one-frame intervals in one A-owned chunk. The later adapter times
`tape_reset_side_b` itself with CLOCK_MONOTONIC under a hard one-second watchdog.

Acceptance requires both:
- elapsed < 1,000,000,000 ns;
- zero chunk-region writes.

The live B index after reset must contain all 4,096 references, preventing a no-op
implementation from satisfying the timing test vacuously.

## Self-test

Run:

```sh
python3 tests/allocator_cow_draft8/selftest.py
```

The repository-wide verifier package workflow runs it automatically.

A green self-test demonstrates verifier logic and red controls only. It is not product
evidence.

## Later product binding

Software imports the immutable package byte-for-byte under Structural Rule 1 and adds
only the mechanical adapter/build/evidence glue described in `ADAPTER.md`.

The production command is:

```sh
python3 tests/allocator_cow_draft8/runner.py \
  --adapter PRODUCT_ADAPTER \
  --evidence EVIDENCE_DIR
```

There is intentionally no production seed or sequence-count argument.

The exact product evidence must return to independent Verification for disposition.

## Acceptance boundary

If a later exact product candidate passes this exact package and independent
Verification authenticates its binding/raw evidence, this tranche is intended to close
the remaining frozen WP-07 criterion unless a spec-grounded omission is found.

It does **not** claim WP-09 recording/golden acceptance merely because record APIs are
exercised, and it does not claim WP-10 crash durability.
