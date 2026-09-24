# Independent WP-10 core crash tranche — DRAFT-8

This package starts the Phase-1 WP-10 crash long pole with a bounded independent
publication covering record commit, reset-B, and §8 stage clearing.

It was authored from the authenticated DRAFT-8 public specifications before inspecting
the current product engine implementation.

## Frozen inputs

Authoring integration point:
`e4a356586fd67d118868ba457e26d2c9805e7c7a`

DRAFT-8 hashes:
- `spec/tapefs-v1.md`:
  `3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb`
- `spec/engine-api.md`:
  `537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1`
- `spec/acceptance.md`:
  `7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7`

## Files

- `planner.py` — immutable exhaustive 28,760-case injection manifest.
- `fixture.py` — deterministic raw TAPEFS fixtures and exact expected metadata.
- `media.py` — independent raw-superblock/index parser and mount-state oracle.
- `oracle.py` — byte-exact durability simulation and case disposition.
- `runner.py` — fail-closed streaming product evidence runner.
- `synthetic_adapter.py` — verifier-only plumbing stand-in.
- `selftest.py` — planner/media/oracle controls and required red tests.
- `ADAPTER.md` — exact later Software fault-device/binding contract.
- `COVERAGE.md` — injection counts, fixtures, assertions and exclusions.

## Exhaustive bounded case set

First-interruption cases: **16,448**.

V7-001 two-interruption stage-clear closure cases: **12,312**.

Total: **28,760**.

Canonical case-set SHA-256:

`6c924fd7bdd54b180084fe58cc50ef49d96fc068b968b8022383685ecf235c96`

Every first-interruption target runs in both:
- flush-required;
- write-through.

Every targeted 512-byte write gets:
- before-write cut;
- all 511 torn-prefix lengths;
- after-full-write cut.

Every target flush gets an interruption. Stage-clear closure repeats all 513 partner
write outcomes over four recovery seed shapes, all three public entry paths, and both
durability modes.

## Independent oracle

The product adapter never supplies an authoritative "old/new" classification.

The verifier:
1. starts from exact fixture bytes;
2. knows the exact DRAFT-8 block bytes that the bounded logical transaction must write;
3. simulates working versus durable media for the requested fault and durability mode;
4. compares product durable bytes to that simulation;
5. independently parses superblock CRC/generation/admission;
6. independently parses/selects indices and checks §5.2/interval disjointness;
7. verifies the actual fresh product remount result agrees with the durable-byte oracle.

For record commit, the newly recorded chunk is made durable before the commit crash
scope begins. Its exact audio value is not judged here; its hash is frozen at the
pre-commit boundary and must remain unchanged across every commit crash. That tests
persistence without claiming WP-09 golden acceptance.

## Durability convention

A successful flush makes preceding writes durable.

A completed unflushed write:
- is not yet durable in `flush_required`;
- is immediately durable in `write_through`.

A torn write explicitly lands its verifier-selected prefix into durable media in both
modes.

This distinction is byte-tested; the package does not simply accept old or new at
every boundary.

## Stage-clear closure

The four V7-001 seeds cover both orientations of:
- exactly one current structurally valid superblock;
- current higher-generation candidate beside a stale lower-generation partner.

The stale copy deliberately has `a_high_water = 1` while live Side A is chunk 2.
If a second interruption ever rolls selection back to it, independent mount parsing
fails Side A — the regression is therefore directly observable.

## Self-test

Run:

```sh
python3 tests/crash_core_draft8/selftest.py
```

The repository-wide verifier package workflow runs it automatically.

Self-tests cover:
- exact planner count and digest;
- fixture/mount semantics;
- representative exact-byte outcomes from every bounded family;
- skipped injection;
- wrong durability-mode interpretation;
- illegal torn outcome;
- stale-partner rollback;
- missing second-interruption family;
- malformed provenance;
- persistent protocol smoke.

A green synthetic self-test is verifier plumbing only, never product acceptance.

## Later product binding

Software imports the immutable package byte-for-byte under Structural Rule 1 and adds
only the product/fault-device adapter specified in `ADAPTER.md`.

Production invocation:

```sh
python3 tests/crash_core_draft8/runner.py \
  --adapter PRODUCT_ADAPTER \
  --evidence EVIDENCE_DIR
```

The production CLI intentionally has no case-count or sampling override.

Exact product evidence must return to independent Verification for disposition.

## Acceptance boundary

A later green product run can accept only this bounded WP-10 tranche. It is expressly
not complete WP-10; the excluded promote, format/dup, re-spool and counter/sequence
crash families remain later work.
