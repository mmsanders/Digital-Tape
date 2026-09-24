# Full re-spool crash + WP-12a product binding

This directory is Software-owned mechanical plumbing for the immutable verifier at
\`tests/respool_full_draft8/\`.

The branch ordering is verifier-first:

1. import the verifier package byte-identically;
2. add this binding/CI without engine changes;
3. only then may a product implementation commit respond to a real verifier failure.

## Exhaustive crash execution

The crash worker runs the real product re-spool once per verifier pass to capture the
actual callback sequence and write payloads. The exhaustive fault device then walks that
real callback stream in canonical order. For every callback coordinate it materializes
all verifier-authored cuts (before, every 1..511-byte torn prefix, after, or flush fault)
against separate working/durable images.

Cases sharing a callback prefix use a checkpoint rather than re-running thousands of
already-identical product callbacks. This is not sampling: every canonical planner case
is materialized once, and every durable variant is freshly mounted through the real
engine with a real \`tape_get_info\`. The Python side exposes the worker's raw bytes and
measurements to the unchanged verifier oracle; it does not decide old/new safety.

The 4,209,696-case campaign is partitioned mechanically by fixture/pass/mode and eight
contiguous slices per group. The aggregate job checks exact range partitioning, the
published planner digest and every frozen census.

## Functional / long-operation gate

Before crash shards start, \`run_functional.py\` replays the clean/headroom rows and the
full verifier-owned WP-12a long-operation object against public API calls. This keeps a
known continuation/state-machine defect from wasting the exhaustive crash campaign.

Passing observations are reduced to authenticated summaries. Any failing shard retains
the verifier's compact \`WP10-RESPOOL-FAILURE-1\` reproducer.
