# Full re-spool crash + WP-12a product binding

This directory is Software-owned mechanical plumbing for the immutable verifier at
`tests/respool_full_draft8/` (corrected tree `7e98b40c…`, schema
`WP10-RESPOOL-OBSERVATION-2`).

The branch is two commits (#235): the byte-identical verifier import, then this
binding, CI and any implementation the unchanged package exposes. The first
canonical failure is recorded on a binding-only head before any engine change.

## Exhaustive crash execution

The crash worker runs the real product re-spool once per verifier pass to capture the
actual callback sequence and write payloads. The exhaustive fault device then walks that
real callback stream in canonical order. For every callback coordinate it materializes
all verifier-authored cuts (before, every 1..511-byte torn prefix, after, or flush fault)
against separate working/durable images.

Cases sharing a callback prefix use a checkpoint rather than re-running thousands of
already-identical product callbacks. This is not sampling: every canonical planner case
is materialized once, and every durable variant is freshly mounted through the real
engine with a real `tape_get_info`. The Python side exposes the worker's raw bytes and
measurements to the unchanged verifier oracle; it does not decide old/new safety.

The 4,209,696-case campaign is partitioned mechanically by fixture/pass/mode and eight
contiguous slices per group. The aggregate job checks exact range partitioning, the
published planner digest and every frozen census.

## Functional / long-operation gate

Before crash shards start, `run_functional.py` replays the clean/headroom rows and the
full verifier-owned WP-12a long-operation object against public API calls. This keeps a
known continuation/state-machine defect from wasting the exhaustive crash campaign.

Passing observations are reduced to authenticated summaries. Any failing shard retains
the verifier's compact `WP10-RESPOOL-FAILURE-1` reproducer.

## Schema 2 continuity facts

The long-operation probe reports, instead of operation labels, the cumulative
chronological list of chunk-region write LBAs before and after each relevant call.
The list is harness bookkeeping from the device wrapper: every successful write in
`[TAPE_LBA_CHUNK_BASE, block_count - 1)`, one LBA per block. The mirror superblock
is excluded because it is metadata, not copied audio. Every small-budget call uses
`block_budget = 1`. Zero-budget `state_before`/`state_after` are the raw logged
chunk-write count. None of these fields is engine-sourced operation identity, and
the probe emits no operation token.

## Evidence identities

`provenance.py` is the only place the issued product base (`ac1f1bf`), the
verifier import commit (`375d55ff`) and the verifier tree (`7e98b40c`) are
written. Before any case runs, `run_functional.py`, `run_shard.py` and
`aggregate.py` verify them against git history. They check that the import's
parent is the base, that the import carries the pinned tree, that the import is
an ancestor of HEAD, and that HEAD still carries the pinned tree. They also
refuse the two PR #227 identities that the first PR #236 package emitted by
mistake (Verification PR #79). `test_provenance.py` runs in CI ahead of both
campaigns and shows each check going red. CI checks out full history for these
jobs so the check has the commits to compare.
