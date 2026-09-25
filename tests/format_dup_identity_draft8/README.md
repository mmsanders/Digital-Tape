# DRAFT-8 format/duplicate raw identity + duplicate long-operation verifier

Independent verifier-first publication for Digital-Tape-Verification issue #71.

This package was authored blind to the current engine implementation from the frozen DRAFT-8 specification bundle. It publishes fixtures, an independent raw-media parser/oracle, an exhaustive deterministic crash planner, the duplicate WP-12a contract oracle, self-tests/negative controls, a raw-only mechanical adapter contract, and a later product-evidence runner.

It is verifier authorship, not product acceptance.

## Frozen inputs

- Digital-Tape: 45c08bd7e25aeb6ca858faf4d30d139999f8dbd7
- Verification: fe432ffac622b9d9e9c68e566d2cb9881f2aee62
- spec/tapefs-v1.md SHA-256: 3bffa0ec46d7ba3779b02cbee6fac1edaf5094553f78270ee379759655147cbb
- spec/engine-api.md SHA-256: 537eadc423e1a7bde726d689206b8fe93bef164d57e48e8ff71e07eaf8a7e3a1
- spec/acceptance.md SHA-256: 7f78fba7b66b4fc6e96d15399c62468249bb30fbccbb59bf9f57b4532f56b6b7

## Planner

Raw crash scenarios include format and duplicate across seven destination shapes, both flush-required and write-through modes, four targeted superblock writes per scenario, before each write, every torn prefix 1 through 511, after each complete write, and each target following-flush fault.

Crash cases: 57,568.

Duplicate WP-12a/refusal contract cases: 43.

Total: 57,611.

Canonical case-set SHA-256:

c493e77dff948df48d9c67c51ef4b68f0a61d2e02615b2d08760a594e79dc4e3

## Raw-observation boundary

The product adapter supplies only concrete observations: raw media bytes, opaque operation tokens, numeric progress/event counters, exact arguments, direct transport/rate/position/ring facts, callback counts/depth, public call results, block traces, render bytes, and ordered call sequences.

It must not supply verifier conclusions. oracle.py rejects semantic verdict fields and independently derives operation survival/no-restart, no-work-on-BUSY, unchanged source state, callback non-recursion, continued audio, same-function completion, and terminal cartridge identity.

This correction preserves planner case membership, ordering, census, and digest.

## Self-test

Run:

    python3 tests/format_dup_identity_draft8/selftest.py

The self-test checks exact census/digest, mandatory raw shapes, partner ordering, generation-2 barrier path, exhaustion zeroing, representative exact durable-byte/remount outcomes, final identity boundary, all 43 contract cases, and negative controls for skipped injection, reversed order, wrong durability, identity drift, BUSY raw-progress mutation, forbidden product-side verdict fields, callback recursion counters, changed rate/ring bytes, silent post-failure render, zero-budget progress, argument-shape drift, and operation-token restart.

The repository-wide Verification package selftests workflow discovers this directory automatically through tests/*_draft8/selftest.py.

## Later product binding

Read ADAPTER.md first. The product adapter may emit only raw bytes and concrete public/API facts. It may not decide which semantic crash or WP-12a class is acceptable.

Production runner:

    python3 tests/format_dup_identity_draft8/runner.py [required provenance and adapter arguments]

See runner.py --help for exact required arguments. Production has no sampling or count override.

## Scope boundary

See COVERAGE.md for exact criteria and exclusions. In particular this does not duplicate the accepted WP-10 core package, promote crash/resume, full re-spool crash coverage, or the other two WP-12a in-progress rows.
