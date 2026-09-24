# Full re-spool DRAFT-8 verifier

Independent verifier-first publication for Digital-Tape-Verification issue #72:
full WP-12 re-spool shapes, exhaustive WP-10 pass crash durability, counter
boundaries, and the re-spool row of WP-12a.

## Frozen inputs

- Digital-Tape: `45c08bd7e25aeb6ca858faf4d30d139999f8dbd7`
- Digital-Tape-Verification: `fe432ffac622b9d9e9c68e566d2cb9881f2aee62`
- TapeFS: `3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb`
- engine-api: `537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1`
- acceptance: `7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7`

The package pins the previously published independent
`tests/respool_draft8/oracle.py` by Git blob SHA
`3c63f190e87915f410a199128e1a08590b8ee6bd`; it does not import product code.

## Contents

- `planner.py` — canonical **4,209,696-case** crash manifest and SHA-256.
- `fixture.py` — verifier-owned clean/crash fixtures, canonical copied-block
  preimages/payloads, raw data digests and pinned narrow-oracle loader.
- `oracle.py` — independent byte-exact torn-write/metadata model, selected-layout
  oracle, fresh-remount allocation-frontier check, disjoint-destination,
  bit-identity, pass-2 live-copy, state-matrix and FAULTED checks.
- `selftest.py` — positive synthetic controls plus seven red controls.
- `reproducer.py` — exact JSON failure-retention format including raw target blocks
  and fresh-remount tape_info.
- `ADAPTER.md` — later product-binding boundary; raw observations only.
- `COVERAGE.md` — exact frozen criteria, counts, exclusions and API notes.

## Run

```sh
python3 tests/respool_full_draft8/selftest.py
```

The repository workflow `.github/workflows/verifier-package-selftests.yml`
(**Verification package selftests**, job **verifier package selftests**) discovers
`tests/*_draft8/selftest.py` automatically.

Expected planner output:

- cases: **4,209,696**
- flush_required: **2,104,848**
- write_through: **2,104,848**
- V3-003 pass 1: **2,103,306**
- V3-003 pass 2: **2,103,306**
- no-lower-run pass 1: **3,084**
- canonical case-set SHA-256:
  `02c52de7a7c51a6ffafe5c9d5afad9c23032b72fc11aaf206bb27a9c9506d3e1`

Every copied 512-byte audio block is exhaustively injected at before-write, every
torn prefix 1…511, and after-write in both durability models. Metadata writes use the
same exhaustive write model, and all relevant flushes are faulted.

DRAFT-8's public `tape_info` has no `free_next` field. Product binding therefore
exposes raw `total_chunks` and `free_chunks` from the fresh crash remount;
Verification derives the runtime frontier and compares it independently with
invariant 12 from raw selected media.

This package is not product acceptance. Software must first import the immutable
publication under Structural Rule 1 and provide raw observations through
`ADAPTER.md`; independent Verification then disposes that evidence.
